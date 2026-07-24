"""smoke C28：檔案生命週期（Sprint 126；自 smoke_check.py 分檔，行數紀律慣例）。

離屏可驗：檔案選單五項與快捷鍵、髒判定（插字髒／undo 回存檔點轉乾淨＝引用
同一性核心）、標題 * 跟隨、寫檔 round-trip（load 重讀 dict 相等）、儲存防呆
（未命名轉另存）、_force_suffix 三態、開啟（歷史清空／未知樣式與壞檔守門）、
新建（髒確認分支）、closeEvent 髒確認分支（替身函式，modal 屬真視窗項）、
匯入後存檔重開內容一致。三個 modal（另存／開啟對話框、關閉確認按鈕）與
真視窗手感待 Owner（GAPS #19 批次）。
"""
import json
import tempfile
from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMenu

from cjkfolio.document import document_to_dict, load_document
from editor.file_actions import FileActionsMixin

ROOT = Path(__file__).resolve().parents[1]


def check_file(EditorWindow, doc_path) -> None:
    win = EditorWindow(str(doc_path))

    # 檔案選單五項與快捷鍵（findChildren 慣例）
    menu = next(
        m for m in win.menuBar().findChildren(QMenu) if m.title() == "檔案")
    acts = [a for a in menu.actions() if not a.isSeparator()]
    assert [a.text() for a in acts] == \
        ["新建", "開啟…", "儲存", "另存新檔…", "匯入稿件…（txt／md／docx）",
         "轉存為 PDF…"], \
        f"檔案選單項異常：{[a.text() for a in acts]}"
    keys = {a.text(): a.shortcut().toString() for a in acts}
    assert keys["新建"] == "Ctrl+N" and keys["開啟…"] == "Ctrl+O", keys
    assert keys["儲存"] == "Ctrl+S" and keys["另存新檔…"] == "Ctrl+Shift+S", keys

    # 髒判定與標題 *：開檔乾淨 → 插字髒 → undo 回存檔點轉乾淨（引用同一性）
    assert not win._is_dirty() and not win.windowTitle().endswith("*")
    win.cursor = (0, 0)
    win._ime.setText("存")
    win._on_ime_commit()
    assert win._is_dirty() and win.windowTitle().endswith("*"), "插字後未標髒"
    win._on_undo()
    assert not win._is_dirty() and not win.windowTitle().endswith("*"), \
        "undo 回存檔點應轉乾淨（document 引用同一性）"
    win._on_redo()
    assert win._is_dirty(), "redo 後應回髒"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 寫檔核心：round-trip 相等、_doc_path 跟隨、乾淨、標題 * 消失
        out = tmp / "存檔驗證.doc.json"
        assert win._write_document(out)
        assert not win._is_dirty() and win._doc_path == out
        assert not win.windowTitle().endswith("*")
        assert document_to_dict(load_document(out)) == document_to_dict(win.doc), \
            "存檔 round-trip 不相等"
        assert "已儲存" in win.statusBar().currentMessage()

        # 儲存（非另存）：檔已存在且 .doc.json → 直接寫回
        win.cursor = (0, 0)
        win._ime.setText("再")
        win._on_ime_commit()
        assert win._is_dirty()
        assert win._save_document() and not win._is_dirty()

        # 開啟：歷史清空、回第一頁、乾淨、頁面面板同步
        saved_dict = document_to_dict(win.doc)
        assert win._open_document(out)
        assert not win.session.can_undo(), "開啟後 undo 歷史應清空"
        assert win.page.number == 1 and not win._is_dirty()
        assert document_to_dict(win.doc) == saved_dict
        assert win._page_panel.count() == len(win.layout_result.pages)

        # 未知樣式守門：檔案據實被擋、目前文件引用不動
        bad = tmp / "壞樣式.doc.json"
        data = json.loads(out.read_text(encoding="utf-8"))
        data["paragraphs"][0]["style"] = "不存在的樣式"
        bad.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        before = win.doc
        assert not win._open_document(bad)
        assert win.doc is before and "沒有的樣式" in win.statusBar().currentMessage()

        # 壞檔守門：非 JSON
        broken = tmp / "壞檔.doc.json"
        broken.write_text("not json", encoding="utf-8")
        assert not win._open_document(broken) and win.doc is before

        # 另存路徑強制 .doc.json（純函式三態）
        force = FileActionsMixin._force_suffix
        assert force(tmp / "a").name == "a.doc.json"
        assert force(tmp / "a.json").name == "a.doc.json"
        assert force(tmp / "a.doc.json").name == "a.doc.json"

        # 儲存防呆：未命名（檔不存在）轉另存，不寫 _doc_path
        win_blank = EditorWindow(None)
        win_blank._ime.setText("新")
        win_blank._on_ime_commit()
        assert win_blank._is_dirty()
        called = []
        win_blank._save_document_as = lambda: called.append(True) or True
        assert win_blank._save_document() and called == [True], \
            "未命名儲存應轉另存"
        assert not (ROOT / "未命名.doc.json").exists(), "未命名不得落地 repo"

        # 新建：髒＋取消 → 不動；放行 → 空紙面未命名乾淨
        win_blank._confirm_discard = lambda action: False
        doc_keep = win_blank.doc
        win_blank._new_document()
        assert win_blank.doc is doc_keep, "取消新建不得動文件"
        win_blank._confirm_discard = lambda action: True
        win_blank._new_document()
        assert win_blank.page is None and not win_blank._is_dirty()
        assert "未命名" in win_blank.windowTitle()

        # closeEvent 髒確認分支：取消 → ignore（視窗照常）；放行 → 接受
        win.cursor = (0, 0)
        win._ime.setText("關")
        win._on_ime_commit()
        assert win._is_dirty()
        win._confirm_discard = lambda action: False
        ev = QCloseEvent()
        win.closeEvent(ev)
        assert not ev.isAccepted(), "取消關閉應 ignore"
        win._confirm_discard = lambda action: True
        ev2 = QCloseEvent()
        win.closeEvent(ev2)
        assert ev2.isAccepted(), "放行關閉應接受"

        # 匯入 md → 髒 → 存檔 → 重開內容一致（匯入成果自此可保存）
        win2 = EditorWindow(None)
        win2._import_manuscript_dialog(str(ROOT / "samples" / "jiejiao-manxing-ch1.md"))
        assert win2._is_dirty(), "匯入取代文件後應為髒"
        md_out = tmp / "匯入落地.doc.json"
        assert win2._write_document(md_out)
        n_para = len(win2.doc.paragraphs)
        assert win2._open_document(md_out)
        assert len(win2.doc.paragraphs) == n_para
        for w in (win, win_blank, win2):
            w._shutdown_thumbnails()

    print(
        "C28 檔案生命週期：檔案選單五項快捷鍵＋髒標記（插字髒、undo 回存檔點轉乾"
        "淨、標題 * 跟隨）＋存檔 round-trip＋未命名轉另存（不落地 repo）＋開啟"
        "（歷史清空、未知樣式與壞檔守門）＋新建與關閉確認分支＋匯入存檔重開一致"
    )
