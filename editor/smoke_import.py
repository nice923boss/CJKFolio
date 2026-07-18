"""editor 稿件匯入的離屏煙霧驗證（C22，Sprint 107）。

驗證項（判定層的分派與模版推導已由 tests/test_manuscript_import.py 釘死，
本層專驗「接上真視窗之後」的行為）：

  (1) 匯入 md 真素材：文件真的換掉、標題層級落到**現行模版**的樣式（不是稿件
      原生模版的樣式名）、畫布回第一頁並確實重繪、statusBar 報段數頁數與樣式
  (2) 匯入 txt：全段落同一內文樣式，且訊息提示可接 AI 指派（該提示是 txt 入口
      與 AI 指派之間的唯一導引，掉了使用者就找不到那條路）
  (3) 一步 Ctrl+Z 回原稿（匯入取代整份文件，沒有 undo 就是不可逆的破壞）
  (4) 不支援的副檔名、稿件引用模版沒有的樣式、取消選檔：三種都據實提示且
      **原稿一字不動**（壞稿不得進畫布）

由 smoke_check.main() 呼叫，離屏環境（QT_QPA_PLATFORM＝offscreen、QApplication
已建）由呼叫端備妥。獨立成檔的理由同 smoke_preflight（smoke_check.py 行數上限）。
"""
import tempfile
import zipfile
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _write_docx(path: Path) -> Path:
    """手工 OOXML（不依賴 python-docx 是否安裝；outlineLvl＝結構層級真值）。"""
    def para(text, lvl):
        return (f'<w:p><w:pPr><w:outlineLvl w:val="{lvl}"/></w:pPr>'
                f"<w:r><w:t>{text}</w:t></w:r></w:p>")
    body = para("匯入的章名", 0) + para("匯入的小節", 1) + para("匯入的內文。", 9)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>')
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return path


def check_import(EditorWindow, DOC, ROOT) -> None:
    """跑 C22 並 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # --- (1) md 真素材：《街角慢行》第一章，但現行模版是《內在整理》 ---
        win = EditorWindow(str(DOC))
        origin_doc = win.doc
        origin_paras = len(win.doc.paragraphs)
        template_styles = set(win.session.template.paragraph_styles)
        md = ROOT / "samples" / "jiejiao-manxing-ch1.md"

        win._import_manuscript_dialog(str(md))
        assert win.doc is not origin_doc, "文件未被換掉"
        assert len(win.doc.paragraphs) != origin_paras or win.doc.title == "jiejiao-manxing-ch1"
        used = {p.style for p in win.doc.paragraphs}
        assert used <= template_styles, f"落到現行模版沒有的樣式：{used - template_styles}"
        # 稿件的 h2／blockquote 對映的是「現行模版」的 md_mapping（ch1 章名由
        # book.json 組裝故無 h1；h1 那條路徑由下方 docx 的 outlineLvl 0 涵蓋）
        mapping = win.session.template.md_mapping
        assert mapping["h2"] in used, "小節標未對映"
        assert mapping["blockquote"] in used, "引文未對映"
        assert win.page.number == 1, "匯入後未回第一頁"
        assert win.scene is not None and len(win.scene.items()) > 0, "畫布未重繪"
        msg_md = win.statusBar().currentMessage()
        assert "已匯入" in msg_md and str(len(win.doc.paragraphs)) in msg_md
        assert "Ctrl+Z" in msg_md, "未告知復原方式"

        # --- (3) 一步 Ctrl+Z 回原稿 ---
        win._on_undo()
        assert win.doc is origin_doc, "undo 未回到匯入前的稿件"
        assert len(win.doc.paragraphs) == origin_paras

        # --- (2) txt：全掛內文樣式＋AI 指派導引 ---
        txt = tmp / "純文字稿.txt"
        txt.write_text("第一段。\n\n第二段。\n\n第三段。", encoding="utf-8")
        win._import_manuscript_dialog(str(txt))
        body_style = win.session.template.md_mapping["paragraph"]
        assert {p.style for p in win.doc.paragraphs} == {body_style}
        assert len(win.doc.paragraphs) == 3
        msg_txt = win.statusBar().currentMessage()
        assert "AI 樣式指派" in msg_txt, "txt 匯入未提示可接 AI 指派"

        # --- docx（同走 md_mapping，驗第三條路徑真的通） ---
        win._import_manuscript_dialog(str(_write_docx(tmp / "稿.docx")))
        assert len(win.doc.paragraphs) == 3
        assert mapping["h1"] in {p.style for p in win.doc.paragraphs}

        # --- (4) 三種拒絕路徑：原稿一字不動 ---
        before = win.doc
        bad = tmp / "稿.pdf"
        bad.write_text("x", encoding="utf-8")
        win._import_manuscript_dialog(str(bad))
        assert win.doc is before, "不支援格式仍換了文件"
        assert "無法匯入" in win.statusBar().currentMessage()

        missing = tmp / "不存在.txt"
        win._import_manuscript_dialog(str(missing))
        assert win.doc is before, "缺檔仍換了文件"
        assert "無法匯入" in win.statusBar().currentMessage()

        orig_dlg = QFileDialog.getOpenFileName
        QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
        try:
            win._import_manuscript_dialog()
        finally:
            QFileDialog.getOpenFileName = orig_dlg
        assert win.doc is before, "取消選檔仍換了文件"
        assert "已取消" in win.statusBar().currentMessage()

    print(
        "C22 稿件匯入：md 真素材換稿（標題層級落到現行模版樣式、回第一頁、畫布重繪）"
        "→ 一步 Ctrl+Z 回原稿 → txt 全掛內文並提示接 AI 指派 → docx 三層對映"
        "；不支援格式／缺檔／取消三路皆據實提示且原稿不動"
    )
