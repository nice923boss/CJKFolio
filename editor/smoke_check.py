"""editor 畫布骨架的離屏煙霧驗證（Gate 5：可跑＋建構＋幾何同源反查）。

不入 pytest 基線（Sprint 17：GUI 套件不綁核心基線）；獨立跑：
  python editor/smoke_check.py
驗證項（皆離屏可自主驗證，不含視覺與 IME）：
  C1 QApplication＋scene 可建、雙層畫布建構無誤
  C2 互動層字格數 > 0、底圖 pixmap 存在
  C3 hit-test 反查 100%（每字格中心 itemAt → (placed_idx, cell_idx) 全對）
  C4 resolve_hit 反查文件游標與文件段 text 一致（cjk 字格 span 切片＝cell.text）
  C5 編輯回路（IME 提交 → 插字 reflow → 游標跟隨）
  C6 文字框互動層（Sprint 58）：框字格 hit-test 100%＋FrameCellHit round-trip
     （含串接續框 span 錨鏈首 text）＋app 點框字格分流
  C7〜C10 app session 接線／畫布鍵盤編輯／AI 設定面板／樣式面板（Sprint 61〜64）
  C11 拖曳範圍選取（Sprint 65）：跨段選取 → 刪除／套字元樣式／IME 替換
  C12 樣式管理 UI（Sprint 71）：雙擊編輯／新增／刪除／另存模版、undo 同步面板
  C13 改名入口＋色票面板（Sprint 78）：改名全書同步、色票新增／改值／刪除守門
  C14 AI 指派校正 UI（Sprint 79）：逐段確認與批次改派（單一 undo 步）、警告不沉默
  C15 模版庫面板（Sprint 80）：清單套用整份模版（壞檔守門）＋草稿併入入口
  C16〜C18 preflight 面板三分區／背景執行緒與快取／X-4 與 ICC 選取、C23 字型授權分區
     （Sprint 87〜112，實作抽於 editor/smoke_preflight.py：本檔逾 800 行上限）
  C19 畫布置圖 UI（Sprint 102，實作抽於 editor/smoke_images.py）：拖放置入、
     拖曳移動、拖角等比縮放、Delete 移除，各一步 undo；缺圖不炸
  C26 畫布縮放平移（Sprint 124，實作抽於 editor/smoke_view.py）：檢視選單與
     快捷鍵、Ctrl+滾輪／Shift+滾輪、開窗整頁 fit、重繪保留視角、拖曳平移
  C27 頁面導航與縮圖面板（Sprint 125，實作抽於 editor/smoke_nav.py）：頁碼
     指示器、版面選單、面板點選跳頁、背景縮圖渲染與世代守門
  C28 檔案生命週期（Sprint 126，實作抽於 editor/smoke_file.py）：儲存／另存
     ／開啟／新建、髒標記與關閉確認、round-trip 與守門
  C29 轉存 PDF 介面（Sprint 127，實作抽於 editor/smoke_export.py）：檔案選單
     轉存項＋Ctrl+E、空白守門、背景 export_pdf 真產出成品（PyMuPDF 讀回驗）、
     X-4 未選 ICC 擋 accept、取消與重入據實提示
視覺對位與 IME 直排輸入需真視窗與 Owner 鍵盤實測（GAPS #19），非本驗證範圍。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # 必須在 Qt import 前

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QTransform  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsScene,
)

from cjkfolio.document import document_from_dict, load_document  # noqa: E402
from cjkfolio.layout import layout_document  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from editor.app import EditorWindow  # noqa: E402
from editor.smoke_ai import check_ai_assign  # noqa: E402
from editor.smoke_images import check_images, check_wrap_ui  # noqa: E402
from editor.smoke_import import check_import  # noqa: E402
from editor.smoke_file import check_file  # noqa: E402
from editor.smoke_export import check_export  # noqa: E402
from editor.smoke_find import check_find  # noqa: E402
from editor.smoke_info import check_info  # noqa: E402
from editor.smoke_master import check_master  # noqa: E402
from editor.smoke_nav import check_nav  # noqa: E402
from editor.smoke_preflight import check_preflight  # noqa: E402
from editor.smoke_spread import check_spread  # noqa: E402
from editor.smoke_view import check_view  # noqa: E402
from editor.canvas import (  # noqa: E402
    build_page_scene,
    iter_cell_rects,
    iter_frame_cell_rects,
    page_frame_placements,
    resolve_frame_hit,
    resolve_hit,
)

DOC = ROOT / "samples" / "case-divider.doc.json"
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
DPI = 150


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    doc = load_document(str(DOC))
    template = load_template(str(TEMPLATE))
    layout = layout_document(doc, template)
    page = layout.pages[0]

    app = QApplication.instance() or QApplication([])
    scene = QGraphicsScene()
    items = build_page_scene(scene, template, doc, layout, page, dpi=DPI)

    # C1/C2 雙層畫布建構
    has_base = any(isinstance(it, QGraphicsPixmapItem) for it in scene.items())
    assert has_base, "底圖 pixmap 未加入 scene"
    assert len(items) > 0, "互動層字格數為 0"
    print(
        f"C1/C2 雙層畫布：底圖 pixmap 存在、互動層 {len(items)} 格"
        f"（platform={app.platformName()}）"
    )

    # C3 hit-test 反查 100%
    scale = DPI / 72.0
    master = template.masters[doc.master]
    total = hit = 0
    for pi, ci, x, y, w, h, _kind in iter_cell_rects(
        template, master, page, page.number, scale
    ):
        total += 1
        found = scene.itemAt(QPointF(x + w / 2, y + h / 2), QTransform())
        if found is not None and found.data(0) == (pi, ci):
            hit += 1
    assert hit == total, f"hit-test 反查非全對：{hit}/{total}"
    print(f"C3 hit-test 反查：{hit}/{total} 全對")

    # C4 resolve_hit → 文件游標，cjk 字格 span 切片＝cell.text
    checked = 0
    for pi, ci, *_ in iter_cell_rects(template, master, page, page.number, scale):
        cellhit = resolve_hit(doc, page, pi, ci)
        if (
            cellhit.kind == "cjk"
            and cellhit.para_idx is not None
            and cellhit.span is not None
        ):
            s, e = cellhit.span
            src = doc.paragraphs[cellhit.para_idx].text[s:e]
            assert src == cellhit.text, f"span 切片 {src!r} != cell.text {cellhit.text!r}"
            checked += 1
    assert checked > 0, "無可驗 provenance 的 cjk 字格"
    sample = resolve_hit(doc, page, 0, 0)
    print(
        f"C4 provenance：{checked} 個 cjk 字格 span 切片＝cell.text；"
        f"樣本 段{sample.para_idx} 字{sample.span}＝「{sample.text}」樣式 {sample.style}"
    )

    # C5 編輯引擎回路（app 接線離屏驗）：選內文字格 → IME 提交 → 插字 reflow 重繪、游標跟隨
    win = EditorWindow(str(DOC))
    cur = None
    for pi, pl in enumerate(win.page.placed):
        if pl.style != "內文-明體直排":
            continue
        for ci, cell in enumerate(pl.line.cells):
            if cell.kind == "cjk" and cell.span is not None:
                cur = (pi, ci)
                break
        if cur is not None:
            break
    assert cur is not None, "找不到內文 cjk 字格可測編輯回路"
    para_idx = win.page.placed[cur[0]].para_idx
    old_text = win.doc.paragraphs[para_idx].text
    win.cursor = cur
    win._ime.setText("測試")
    win._on_ime_commit()
    new_text = win.doc.paragraphs[para_idx].text
    assert len(new_text) == len(old_text) + 2 and "測試" in new_text, \
        f"插入未反映於文件：{old_text!r} → {new_text!r}"
    assert win.layout_result.violations == [], f"reflow 有禁則違規：{win.layout_result.violations}"
    assert win._highlight is not None, "reflow 後游標未重新高亮"
    assert win.cursor is not None
    landed = win.page.placed[win.cursor[0]].line.cells[win.cursor[1]]
    assert landed.text == "試", f"游標未跟隨到最後插入字，落在 {landed.text!r}"
    print(
        f"C5 編輯回路：段{para_idx}內文插入「測試」→ reflow"
        f"（{len(win.layout_result.pages)} 頁、0 違規），游標跟隨到「{landed.text}」"
    )

    # C6 文字框互動層（Sprint 58）：框字格 hit-test＋FrameCellHit round-trip＋app 分流
    frame_doc_dict = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": "框示範（自擬）", "template": "neizai-zhengli",
                 "master": "A-內文版"},
        "paragraphs": [{"text": "留白是安放的開始。", "style": "內文-明體直排"}],
        "text_frames": [
            {"text": "安放選擇收納歸位" * 3, "style": "旁注-手札圖注", "page": 1,
             "rect": [300.0, 120.0, 340.0, 200.0], "thread": "說"},  # 2 欄×9＝18 字
            {"style": "旁注-手札圖注", "page": 1,
             "rect": [200.0, 120.0, 240.0, 200.0], "thread": "說"},  # 串接續框接 6 字
            {"text": "獨立圖說", "style": "旁注-手札圖注", "page": 1,
             "rect": [260.0, 320.0, 290.0, 420.0]},
        ],
    }
    fdoc = document_from_dict(frame_doc_dict)
    flayout = layout_document(fdoc, template)
    fpage = flayout.pages[0]
    fscene = QGraphicsScene()
    build_page_scene(fscene, template, fdoc, flayout, fpage, dpi=DPI)
    placements = page_frame_placements(template, fdoc, flayout, fpage)
    assert [pl.frame_idx for pl in placements] == [0, 1, 2], \
        f"frame_idx 非文件序：{[pl.frame_idx for pl in placements]}"
    ftotal = fhit = rt = 0
    for fi, li, ci, x, y, w, h, _k in iter_frame_cell_rects(placements, scale):
        ftotal += 1
        found = fscene.itemAt(QPointF(x + w / 2, y + h / 2), QTransform())
        if found is not None and found.data(0) == ("frame", fi, li, ci):
            fhit += 1
    assert ftotal == fhit == 28, f"框字格 hit-test 非全對：{fhit}/{ftotal}（預期 28）"
    for pl in placements:
        for li, fl in enumerate(pl.lines):
            for ci, cell in enumerate(fl.line.cells):
                fh = resolve_frame_hit(fpage.number, pl, li, ci)
                s, e = fh.span
                src = fdoc.text_frames[fh.source_idx].text[s:e]
                assert src == cell.text, f"框 span 切片 {src!r} != {cell.text!r}"
                rt += 1
    tail = next(pl for pl in placements if pl.frame_idx == 1)
    assert tail.source_idx == 0, "串接續框 source_idx 未錨鏈首"
    assert tail.lines[0].line.cells[0].span == (18, 19), \
        f"續框首格 span 非接續鏈首：{tail.lines[0].line.cells[0].span}"
    with tempfile.TemporaryDirectory() as td:
        fpath = Path(td) / "frame-demo.doc.json"
        fpath.write_text(json.dumps(frame_doc_dict, ensure_ascii=False),
                         encoding="utf-8")
        fwin = EditorWindow(str(fpath))
        frame_keys = [k for k in fwin._item_by_key if k and k[0] == "frame"]
        assert len(frame_keys) == 28, f"app 框字格 item 數 {len(frame_keys)}（預期 28）"
        fwin._on_pick(fwin._item_by_key[("frame", 1, 0, 0)])
        msg = fwin.statusBar().currentMessage()
        assert "框游標" in msg and "來源框 0" in msg, f"app 框分流訊息異常：{msg}"
        assert fwin.cursor is None, "點框字格不應設 body 插入游標"
        print(
            f"C6 文字框互動層：框字格 hit-test {fhit}/{ftotal} 全對、"
            f"{rt} 格 FrameCellHit round-trip（續框 span 錨鏈首 (18, 19)）、"
            "app 點框字格分流顯示框游標"
        )

        # C7 app session 接線（Sprint 61）：IME 提交入框＋Ctrl+Z／Y 統一歷史
        orig_head = fdoc.text_frames[0].text
        edited_head = orig_head[:19] + "新" + orig_head[19:]
        fwin._ime.setText("新")
        fwin._on_ime_commit()  # 框游標（C6 已點 ("frame",1,0,0)，span (18,19)）→ 插入框
        assert fwin.doc.text_frames[0].text == edited_head, "IME 提交未入框"
        assert fwin.frame_cursor is not None and fwin.frame_cursor[1] == 1, \
            "框游標未跟隨到續框"
        assert fwin._highlight is not None, "框插入後未重新高亮"
        fwin._on_undo()
        assert fwin.doc.text_frames[0].text == orig_head, "Ctrl+Z 未回退框編輯"
        fwin._on_redo()
        assert fwin.doc.text_frames[0].text == edited_head, "Ctrl+Y 未重做框編輯"
        body_key = next(k for k in fwin._item_by_key if k and k[0] != "frame")
        fwin._on_pick(fwin._item_by_key[body_key])
        assert fwin.cursor is not None and fwin.frame_cursor is None, \
            "點 body 字格未互斥清除框游標"
        fwin._ime.setText("好")
        fwin._on_ime_commit()
        assert "好" in fwin.doc.paragraphs[0].text, "IME 提交未入 body"
        fwin._on_undo()  # 回退 body 插入
        assert "好" not in fwin.doc.paragraphs[0].text
        assert fwin.doc.text_frames[0].text == edited_head
        fwin._on_undo()  # 回退框插入（統一歷史依序）
        assert fwin.doc.text_frames[0].text == orig_head
        print(
            "C7 app session 接線：IME 提交入框（游標跨框跟隨）＋"
            "undo／redo 統一歷史（body、框依序回退）"
        )

        # C8 畫布鍵盤編輯（Sprint 62）：Backspace 刪字（body／框）、Enter 分段
        def key_event(k):
            return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)

        body_key2 = next(
            k for k in fwin._item_by_key
            if k and k[0] != "frame"
            and fwin.page.placed[k[0]].line.cells[k[1]].kind == "cjk")
        fwin._on_pick(fwin._item_by_key[body_key2])
        hit8 = resolve_hit(fwin.doc, fwin.page, *body_key2)
        before_len = len(fwin.doc.paragraphs[hit8.para_idx].text)
        assert fwin._on_key(key_event(Qt.Key.Key_Backspace)), "Backspace 未被處理"
        assert len(fwin.doc.paragraphs[hit8.para_idx].text) == before_len - 1, \
            "Backspace 未刪 body 游標字"
        fwin._on_undo()
        n_paras = len(fwin.doc.paragraphs)
        fwin._on_pick(fwin._item_by_key[body_key2])
        assert fwin._on_key(key_event(Qt.Key.Key_Return)), "Enter 未被處理"
        assert len(fwin.doc.paragraphs) == n_paras + 1, "Enter 未分段"
        fwin._on_undo()
        fwin._on_pick(fwin._item_by_key[("frame", 0, 0, 0)])  # 鏈首首字「安」
        head_before = fwin.doc.text_frames[0].text
        assert fwin._on_key(key_event(Qt.Key.Key_Backspace)), "框 Backspace 未被處理"
        assert fwin.doc.text_frames[0].text == head_before[1:], "Backspace 未刪框游標字"
        fwin._on_undo()
        assert fwin.doc.text_frames[0].text == head_before
    win2 = EditorWindow(str(ROOT / "samples" / "chapter-opening.doc.json"))  # 2 頁樣張
    assert win2.page.number == 1 and len(win2.layout_result.pages) == 2
    win2._on_key(key_event(Qt.Key.Key_PageDown))
    assert win2.page.number == 2, "PgDn 未換頁"
    win2._on_key(key_event(Qt.Key.Key_PageDown))
    assert win2.page.number == 2, "末頁 PgDn 應停留"
    win2._on_key(key_event(Qt.Key.Key_PageUp))
    assert win2.page.number == 1, "PgUp 未回頁"
    print(
        "C8 畫布鍵盤編輯：Backspace 刪字（body＋框，undo 可回）、Enter 分段、"
        "PgUp／PgDn 換頁（含首末頁停留）"
    )

    # C9 AI 設定面板（Sprint 63）：三欄位 round-trip、金鑰遮罩、壞檔警示不 crash
    from PySide6.QtWidgets import QLineEdit

    from cjkfolio.ai_config import load_ai_config
    from editor.ai_panel import DEFAULT_CONFIG_PATH, AiConfigDialog

    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "ai-config.local.json"
        dlg = AiConfigDialog(config_path=cfg_path)
        assert dlg._api_key.echoMode() == QLineEdit.EchoMode.Password, "金鑰欄未遮罩"
        assert dlg.current_config().base_url == "" and not dlg._notice.text()
        dlg._base_url.setText("http://localhost:8000/v1")
        dlg._api_key.setText("測試金鑰-abc")
        dlg._model.setText("qwen3-32b")
        dlg._on_save()
        saved = load_ai_config(cfg_path)
        assert (saved.base_url, saved.api_key, saved.model) == (
            "http://localhost:8000/v1", "測試金鑰-abc", "qwen3-32b"), "面板儲存 round-trip 失敗"
        dlg2 = AiConfigDialog(config_path=cfg_path)  # 既有值帶入
        assert dlg2.current_config() == saved
        cfg_path.write_text("{壞 JSON", encoding="utf-8")
        dlg3 = AiConfigDialog(config_path=cfg_path)  # 壞檔＝空值開啟＋警示列（不 crash）
        assert dlg3.current_config().api_key == ""
        assert "無法解析" in dlg3._notice.text()
        assert "測試金鑰" not in dlg3._notice.text(), "警示訊息不得回帶欄位值"
    real_loaded = ""
    if DEFAULT_CONFIG_PATH.exists():  # R5：使用者既有本機設定實載（值零輸出）
        dlg4 = AiConfigDialog(config_path=DEFAULT_CONFIG_PATH)
        cfg4 = dlg4.current_config()
        real_loaded = f"；R5 真實設定檔載入欄位非空數＝{sum(bool(v) for v in (cfg4.base_url, cfg4.api_key, cfg4.model))}/3（值零輸出）"
    print(f"C9 AI 設定面板：round-trip 三欄位全對、金鑰遮罩、壞檔警示不含值{real_loaded}")

    # C10 樣式面板（Sprint 64）：點選套段落／字元樣式至游標段／游標字、undo 可回
    hit10 = resolve_hit(win.doc, win.page, *win.cursor)  # C5 游標在內文「試」
    p10 = hit10.para_idx
    win._style_panel.pick_para_style("引文-仿宋語錄")
    styles = {pl.style for pg in win.layout_result.pages for pl in pg.placed
              if pl.para_idx == p10}
    assert styles == {"引文-仿宋語錄"}, f"段落樣式未套用：{styles}"
    win._style_panel.pick_char_style("內文強調-明體W9")
    hit10b = resolve_hit(win.doc, win.page, *win.cursor)
    cell10 = win.page.placed[win.cursor[0]].line.cells[win.cursor[1]]
    assert cell10.char_style == "內文強調-明體W9", "字元樣式未套用至游標字"
    win._style_panel.pick_char_style(None)
    cell10c = win.page.placed[win.cursor[0]].line.cells[win.cursor[1]]
    assert cell10c.char_style is None, "字元樣式未清除"
    for _ in range(3):
        win._on_undo()
    styles_back = {pl.style for pg in win.layout_result.pages for pl in pg.placed
                   if pl.para_idx == p10}
    assert styles_back == {"內文-明體直排"}, f"undo 未回原段落樣式：{styles_back}"
    assert hit10b.para_idx == p10
    print(
        "C10 樣式面板：段落樣式套游標段（引文-仿宋語錄）＋字元樣式套游標字"
        "（內文強調-明體W9→清除）＋三步 undo 回原"
    )

    # C11 拖曳範圍選取（Sprint 65）：跨段選取 → 刪除／套字元樣式／IME 替換，undo 可回
    from cjkfolio.editing import DocCursor, DocSpan

    win11 = EditorWindow(str(DOC))
    orig_texts = [p.text for p in win11.doc.paragraphs]

    def cell_key(w, para_idx, char_pos):
        for pi, pl in enumerate(w.page.placed):
            if pl.para_idx != para_idx:
                continue
            for ci, cell in enumerate(pl.line.cells):
                if cell.span is not None and cell.span[0] == char_pos:
                    return (pi, ci)
        raise AssertionError(f"找不到 段{para_idx} 字位{char_pos} 的字格")

    a_key = cell_key(win11, 3, 0)  # 段3「三」（內文）
    b_key = cell_key(win11, 5, 0)  # 段5「夫」（內文）
    win11._on_pick(win11._item_by_key[a_key])
    assert win11._drag_anchor is not None and win11.selection is None
    win11._on_drag(win11._item_by_key[a_key])  # 拖回起點字格＝維持單游標
    assert win11.selection is None, "同格拖曳不應產生選取"
    win11._on_drag(win11._item_by_key[b_key])
    want = DocSpan(DocCursor(3, 0), DocCursor(5, 1))
    assert win11.selection == want, f"選取範圍異常：{win11.selection}"
    # 選取 shading＝段3 全 14 字＋段4「【成員】」4 字＋段5 首字＝19 格
    assert len(win11._sel_items) == 19, f"選取 shading 數異常：{len(win11._sel_items)}"
    win11._on_pick(win11._item_by_key[b_key])
    win11._on_drag(win11._item_by_key[a_key])  # 反向拖曳＝同一範圍（起訖正規化）
    assert win11.selection == want, f"反向拖曳未正規化起訖：{win11.selection}"
    # Backspace 刪選取：段3＋段5 併段（承頭段樣式）、段4 移除、undo 回原
    assert win11._on_key(key_event(Qt.Key.Key_Backspace)), "選取 Backspace 未被處理"
    assert len(win11.doc.paragraphs) == 4, f"跨段刪除後段數 {len(win11.doc.paragraphs)}"
    assert win11.doc.paragraphs[3].text == orig_texts[5][1:], \
        f"併段內容異常：{win11.doc.paragraphs[3].text!r}"
    assert win11.selection is None and win11._sel_items == []
    win11._on_undo()
    assert [p.text for p in win11.doc.paragraphs] == orig_texts, "undo 未回拖曳刪除前"
    # 字元樣式面板吃選取範圍（Sprint 64 預告）：跨段套用、選取保留、undo 回原
    win11._on_pick(win11._item_by_key[a_key])
    win11._on_drag(win11._item_by_key[b_key])
    win11._style_panel.pick_char_style("內文強調-明體W9")
    c3 = next(cell for pl in win11.page.placed if pl.para_idx == 3
              for cell in pl.line.cells if cell.span == (0, 1))
    c5 = next(cell for pl in win11.page.placed if pl.para_idx == 5
              for cell in pl.line.cells if cell.span == (0, 1))
    assert c3.char_style == c5.char_style == "內文強調-明體W9", "選取套字元樣式未跨段生效"
    assert win11.selection == want, "套樣式後選取未保留"
    assert len(win11._sel_items) == 19, "套樣式後選取 shading 未重畫"
    win11._on_undo()
    assert win11.selection is None
    # IME 提交替換選取：跨段替換為「極簡」、undo 回原
    win11._on_pick(win11._item_by_key[a_key])
    win11._on_drag(win11._item_by_key[b_key])
    win11._ime.setText("極簡")
    win11._on_ime_commit()
    assert len(win11.doc.paragraphs) == 4
    assert win11.doc.paragraphs[3].text == "極簡" + orig_texts[5][1:], \
        f"替換選取內容異常：{win11.doc.paragraphs[3].text!r}"
    win11._on_undo()
    assert [p.text for p in win11.doc.paragraphs] == orig_texts, "undo 未回替換前"
    # 框字格不支援拖曳選取（v1 設計）：不設拖曳起點、不產生選取
    with tempfile.TemporaryDirectory() as td11:
        fpath11 = Path(td11) / "frame-demo.doc.json"
        fpath11.write_text(json.dumps(frame_doc_dict, ensure_ascii=False),
                           encoding="utf-8")
        fwin11 = EditorWindow(str(fpath11))
        fwin11._on_pick(fwin11._item_by_key[("frame", 0, 0, 0)])
        assert fwin11._drag_anchor is None, "框字格不應成為拖曳選取起點"
        fwin11._on_drag(fwin11._item_by_key[("frame", 0, 0, 1)])
        assert fwin11.selection is None, "框拖曳不應產生選取"
    print(
        "C11 拖曳範圍選取：跨段選取 19 格 shading（同格退回單游標、反向拖曳正規化）"
        "＋Backspace 刪選取併段＋字元樣式套選取（選取保留）＋IME 替換選取"
        "（皆 undo 可回）＋框拖曳不選取"
    )

    # C12 樣式管理 UI（Sprint 71）：雙擊編輯對話框、新增／刪除、另存模版、undo 同步面板
    from cjkfolio.styles import load_template as load_template_file
    from editor.style_panel import StyleEditDialog

    BODY12 = "內文-明體直排"
    win12 = EditorWindow(str(DOC))
    n_para_items = win12._style_panel.para_list.count()
    dlg12 = StyleEditDialog(
        "para", win12.template.paragraph_styles[BODY12],
        lambda ch: win12._apply_style_definition("para", BODY12, ch))
    dlg12._edits["size_pt"].setText("16")
    dlg12._on_save()
    assert win12.template.paragraph_styles[BODY12].size_pt == 16.0, "對話框編輯未套用"
    dlg12b = StyleEditDialog(
        "para", win12.template.paragraph_styles[BODY12],
        lambda ch: win12._apply_style_definition("para", BODY12, ch))
    dlg12b._edits["size_pt"].setText("十六")
    dlg12b._on_save()
    assert "無法套用" in dlg12b._notice.text(), "非法值未顯示於對話框警示列"
    assert win12.template.paragraph_styles[BODY12].size_pt == 16.0, "非法值污染了現態"
    item12 = win12._style_panel.para_list.findItems(
        BODY12, Qt.MatchFlag.MatchExactly)[0]
    win12._style_panel.para_list.setCurrentItem(item12)
    win12._create_style("para", name="面板-自擬新樣式")
    assert "面板-自擬新樣式" in win12.template.paragraph_styles, "選單新增未生效"
    assert win12._style_panel.para_list.count() == n_para_items + 1, "面板清單未同步新增"
    win12._remove_selected_style("para", name=BODY12)  # 文件使用中 → 快速失敗顯示訊息
    assert BODY12 in win12.template.paragraph_styles
    assert "無法刪除" in win12.statusBar().currentMessage()
    win12._remove_selected_style("para", name="面板-自擬新樣式")
    assert "面板-自擬新樣式" not in win12.template.paragraph_styles, "選單刪除未生效"
    assert win12._style_panel.para_list.count() == n_para_items, "面板清單未同步刪除"
    with tempfile.TemporaryDirectory() as td12:
        tpath = Path(td12) / "面板另存.json"
        win12._save_template_to(tpath)
        assert load_template_file(tpath).paragraph_styles[BODY12].size_pt == 16.0, \
            "另存模版未含樣式編輯結果"
    for _ in range(3):  # 刪除 → 新增 → 編輯 依序回退
        win12._on_undo()
    assert win12.template.paragraph_styles[BODY12].size_pt == 11.5, "undo 未回樣式編輯前"
    assert win12._style_panel.para_list.count() == n_para_items, "undo 後面板未同步"
    print(
        "C12 樣式管理 UI：雙擊編輯 16pt 全書重排（非法值留對話框警示）＋新增／刪除"
        "（含文件使用中守門）＋面板清單同步＋另存模版重載 16pt＋三步 undo 回原"
    )

    # C13 改名入口＋色票面板（Sprint 78）：改名全書同步、色票新增／改值／刪除守門、undo 回原
    from editor.style_panel import SwatchEditDialog

    BODY13 = "內文-明體直排"
    win13 = EditorWindow(str(DOC))
    win13._style_panel.select_style("para", BODY13)
    win13._rename_selected_style("para", new_name="內文-改名測試")
    assert "內文-改名測試" in win13.template.paragraph_styles, "選單改名未生效"
    assert BODY13 not in win13.template.paragraph_styles
    assert all(p.style != BODY13 for p in win13.doc.paragraphs), "文件段落參照未同步改名"
    assert win13._style_panel.para_list.findItems(
        "內文-改名測試", Qt.MatchFlag.MatchExactly), "面板清單未同步新名"
    win13._style_panel.select_style("para", "內文-改名測試")
    win13._rename_selected_style("para", new_name="引文-仿宋語錄")  # 同名衝突 → 守門
    assert "無法改名" in win13.statusBar().currentMessage(), "衝突改名未顯示訊息"
    assert "內文-改名測試" in win13.template.paragraph_styles, "衝突改名污染了現態"

    n_swatch = win13._style_panel.swatch_list.count()
    win13._create_swatch(name="測試灰")
    assert win13.template.colors["測試灰"].cmyk == (0.0, 0.0, 0.0, 1.0), "新增色票未生效"
    assert win13._style_panel.swatch_list.count() == n_swatch + 1, "面板色票清單未同步"
    assert win13._apply_style_definition(
        "para", "內文-改名測試", {"color": "測試灰"}) is None  # 樣式掛色（UI 路徑）
    dlg13 = SwatchEditDialog(
        win13.template.colors["測試灰"],
        lambda ch: win13._apply_swatch_definition("測試灰", ch))
    dlg13._cmyk.setText("0, 0, 0, 0.4")
    dlg13._on_save()
    assert win13.template.colors["測試灰"].cmyk == (0.0, 0.0, 0.0, 0.4), "色票改值未套用"
    dlg13b = SwatchEditDialog(
        win13.template.colors["測試灰"],
        lambda ch: win13._apply_swatch_definition("測試灰", ch))
    dlg13b._cmyk.setText("2, 0, 0, 0")  # 越界 → 留對話框警示、現態不污染
    dlg13b._on_save()
    assert "無法套用" in dlg13b._notice.text(), "色票非法值未顯示於警示列"
    assert win13.template.colors["測試灰"].cmyk == (0.0, 0.0, 0.0, 0.4), "非法值污染了色票"
    win13._remove_selected_swatch(name="測試灰")  # 樣式引用中 → 守門
    assert "測試灰" in win13.template.colors and \
        "無法刪除" in win13.statusBar().currentMessage(), "引用中色票刪除未守門"
    assert win13._apply_style_definition(
        "para", "內文-改名測試", {"color": None}) is None  # 清引用
    win13._remove_selected_swatch(name="測試灰")
    assert "測試灰" not in win13.template.colors, "解引用後刪除色票未生效"
    assert win13._style_panel.swatch_list.count() == n_swatch, "面板色票清單未同步刪除"
    for _ in range(6):  # 刪色票→清引用→改值→掛色→新增色票→改名 依序回退
        win13._on_undo()
    assert BODY13 in win13.template.paragraph_styles, "undo 未回改名前"
    assert all(p.style != "內文-改名測試" for p in win13.doc.paragraphs), \
        "undo 後文件段落未回原樣式名"
    assert "測試灰" not in win13.template.colors, "undo 未回新增色票前"
    print(
        "C13 改名入口＋色票面板：選單改名全書同步（衝突守門）＋色票新增（K100）→"
        "樣式掛色→雙擊改值 0.4 全書變色（越界留警示）→引用中刪除守門→解引用刪除"
        "＋面板同步＋六步 undo 回原"
    )

    # C14 AI 指派校正 UI（Sprint 79）：逐段確認與批次改派、單一 undo 步、警告不沉默
    from cjkfolio.ai_style import SuggestResult

    win14 = EditorWindow(str(DOC))
    n14 = len(win14.doc.paragraphs)
    orig_styles = [p.style for p in win14.doc.paragraphs]

    def fake_suggest(texts, candidates):
        assert len(texts) == n14 and "內文-明體直排" in candidates
        assign = [None] * n14
        assign[2], assign[3] = "章節小標-黑體", "引文-仿宋語錄"  # 兩段建議、其餘降級 None
        return SuggestResult(assignments=tuple(assign),
                             warnings=("自擬警告：第 2 批降級",), batches=2)

    captured = {}
    from editor.ai_assign import AssignReviewDialog as _ARD

    def _capture_exec(dlg):  # 離屏不進事件圈：截取對話框供程式化操作
        captured["dlg"] = dlg
        return 0

    _orig_exec = _ARD.exec
    _ARD.exec = _capture_exec
    try:
        win14._run_ai_assign(suggest=fake_suggest)
        win14._ai_assign_wait()  # Sprint 104：建議改由背景執行緒回，等派送後才有對話框
    finally:
        _ARD.exec = _orig_exec
    dlg14 = captured["dlg"]
    assert dlg14._notice.text() == "自擬警告：第 2 批降級", "警告未顯示於對話框"
    assert dlg14.table.rowCount() == n14
    checked = [i for i in range(n14)
               if dlg14.table.item(i, 0).checkState() == Qt.CheckState.Checked]
    assert checked == [2, 3], f"預設勾選應為有建議且異於現行者，得到 {checked}"
    dlg14.table.item(3, 0).setCheckState(Qt.CheckState.Unchecked)  # 人工否決一段
    dlg14._combos[2].setCurrentText("引文-仿宋語錄")               # 人工改建議
    assert dlg14._assignments() == {2: "引文-仿宋語錄"}, "校正後載荷不符"
    dlg14._on_confirm()
    assert win14.doc.paragraphs[2].style == "引文-仿宋語錄", "批次改派未套用"
    assert win14.doc.paragraphs[3].style == orig_styles[3], "否決段被誤改"
    win14._on_undo()  # 單一 undo 步整批回退
    assert [p.style for p in win14.doc.paragraphs] == orig_styles, "undo 未整批回原"
    win14._apply_assignments({})  # 空載荷 no-op
    assert "未採用" in win14.statusBar().currentMessage()
    print(
        "C14 AI 指派校正 UI：注入建議 2 段（降級警告顯示）→ 預設勾選＝有建議且異於"
        "現行 → 人工否決一段＋改建議 → 批次改派 1 段（單一 undo 步整批回退）＋空載荷 no-op"
    )

    # C15 模版庫面板（Sprint 80）：草稿併入入口＋清單套用整份模版（壞檔守門）＋undo 回原
    from editor.library_panel import TemplateLibraryDialog

    win15 = EditorWindow(str(DOC))
    n15_styles = len(win15.template.paragraph_styles)
    with tempfile.TemporaryDirectory() as td15:
        draft15 = Path(td15) / "draft.json"
        draft15.write_text(json.dumps({
            "paragraph_styles": {
                "庫測-內文候選": {"font_family": "思源宋體 TC", "font_weight": "regular",
                                  "size_pt": 11.5},
                "庫測-標題候選": {"font_family": "思源黑體 TC", "font_weight": "bold",
                                  "size_pt": 21.9},
            }}, ensure_ascii=False), encoding="utf-8")
        win15._merge_draft_dialog(path=str(draft15))
        assert "已併入 2 個樣式" in win15.statusBar().currentMessage(), "草稿併入未生效"
        assert len(win15.template.paragraph_styles) == n15_styles + 2

        lib_dir = Path(td15) / "library"
        lib_dir.mkdir()
        win15._save_template_to(lib_dir / "演進模版.json")
        (lib_dir / "壞檔.json").write_text("{ 不是 JSON", encoding="utf-8")
        win15._on_undo()  # 回併入前（現行模版無庫測樣式）
        assert len(win15.template.paragraph_styles) == n15_styles

        cap15 = {}
        _orig15 = TemplateLibraryDialog.exec
        TemplateLibraryDialog.exec = lambda dlg: cap15.setdefault("dlg", dlg) or 0
        try:
            win15._open_library(directory=lib_dir)
        finally:
            TemplateLibraryDialog.exec = _orig15
        dlg15 = cap15["dlg"]
        assert dlg15.listing.count() == 2, "庫清單應含演進模版＋壞檔"
        dlg15.select_path("壞檔.json")
        dlg15._on_apply_clicked()
        assert "壞檔不可套用" in dlg15._notice.text(), "壞檔套用未守門"
        dlg15.select_path("演進模版.json")
        dlg15._on_apply_clicked()  # 套用整份模版（含庫測樣式）
        assert "庫測-內文候選" in win15.template.paragraph_styles, "套用模版未生效"
        win15._on_undo()
        assert "庫測-內文候選" not in win15.template.paragraph_styles, "undo 未回套用前"
    print(
        "C15 模版庫面板：草稿併入 2 樣式（statusBar 列報）→ 另存演進模版 → 庫清單 2 項"
        "（壞檔套用守門警示）→ 套用整份模版（樣式回來）→ 一步 undo 回原"
    )

    # C16〜C18 preflight 面板／背景執行緒／X-4、C23 字型授權分區
    # （抽於 editor/smoke_preflight.py）
    check_preflight(EditorWindow, DOC, ROOT)

    # C19 畫布置圖 UI、C20 文繞圖參數 UI（抽於 editor/smoke_images.py，同上行數紀律）
    check_images(EditorWindow, DOC, ROOT)
    check_wrap_ui(EditorWindow, ROOT)

    # C21 AI 指派背景執行緒（抽於 editor/smoke_ai.py，同上）
    check_ai_assign(EditorWindow, DOC)

    # C22 稿件匯入（抽於 editor/smoke_import.py，同上）
    check_import(EditorWindow, DOC, ROOT)

    # C24 行首擠壓的互動層字格（Sprint 117）：位移格矩形上緣跟著字形走、字格仍相連
    doc24 = load_document(str(ROOT / "samples" / "line-head-squeeze.doc.json"))
    tpl24 = load_template(str(ROOT / "samples" / "punct-squeeze.template.json"))
    layout24 = layout_document(doc24, tpl24)
    page24 = next(
        (p for p in layout24.pages
         if any(pl.line.cells and pl.line.cells[0].glyph_offset for pl in p.placed)),
        None,
    )
    assert page24 is not None, "行首擠壓樣張排不出命中行（畫布無從驗證）"
    scene24 = QGraphicsScene()
    build_page_scene(scene24, tpl24, doc24, layout24, page24, dpi=DPI)
    rects24 = list(
        iter_cell_rects(tpl24, tpl24.masters[doc24.master], page24, page24.number, scale)
    )
    by_line24: dict = {}
    for pi, ci, x, y, w, h, _kind in rects24:
        by_line24.setdefault(pi, []).append((ci, y, h))
        found = scene24.itemAt(QPointF(x + w / 2, y + h / 2), QTransform())
        assert found is not None and found.data(0) == (pi, ci), f"反查失準（{pi}, {ci}）"
    shifted24 = 0
    for pi, cells in by_line24.items():
        cells.sort()
        for (_ci, y, h), (_cj, y2, _h2) in zip(cells, cells[1:]):
            assert abs(y + h - y2) < 0.01, f"第 {pi} 行字格不相連（點選死區）"
        head = page24.placed[pi].line.cells[0]
        if not head.glyph_offset or len(cells) < 3:
            continue
        size = tpl24.paragraph_styles[page24.placed[pi].style].size_pt
        # 首格佔半槽＋讓出半個字級：與同行整格間距（cells[1]→cells[2]）互為印證
        expect = (cells[2][1] - cells[1][1]) * head.width - head.glyph_offset * size * scale
        assert abs((cells[1][1] - cells[0][1]) - expect) < 0.01, f"第 {pi} 行首格幾何不符"
        shifted24 += 1
    assert shifted24 >= 3, f"命中行僅 {shifted24} 行（樣張應 ≥ 3）"
    print(
        f"C24 行首擠壓互動層：命中 {shifted24} 行，首格上緣讓出半個字級、"
        f"字格相連無死區，hit-test {len(rects24)}/{len(rects24)} 全對"
    )

    # C25 空白起始（Sprint 123）：無參數＝未命名空白文件，從零開始匯入或打字
    win25 = EditorWindow(None)
    assert "未命名" in win25.windowTitle() and "骨架" not in win25.windowTitle(), \
        f"標題失準：{win25.windowTitle()}"
    assert win25.page is None, "空白文件應為空紙面（page None）"
    assert len(win25.scene.items()) > 0, "空紙面未畫出"
    assert "匯入稿件" in win25.statusBar().currentMessage(), "開場未引導匯入"
    win25._turn_page(1)  # 空白時翻頁不炸、據實提示
    assert "尚無頁面" in win25.statusBar().currentMessage()
    win25._ime.setText("測")
    win25._on_ime_commit()  # 第一字：空白直接落段 0 字位 0
    assert win25.doc.paragraphs[0].text == "測"
    assert win25.page is not None and win25.page.number == 1
    assert win25.cursor is not None, "第一字後游標未跟隨"
    win25._ime.setText("試")
    win25._on_ime_commit()  # 第二字：沿游標接續，不需再點字格
    assert win25.doc.paragraphs[0].text == "測試"
    win25._on_undo()
    win25._on_undo()
    assert win25.doc.paragraphs[0].text == "" and win25.page is None, "undo 未回到空紙面"
    win25._import_manuscript_dialog(str(ROOT / "samples" / "jiejiao-manxing-ch1.md"))
    assert win25.page is not None and "jiejiao-manxing-ch1" in win25.windowTitle(), \
        "匯入後標題未跟隨文件名"
    print(
        "C25 空白起始：未命名標題、空紙面、空白翻頁據實提示、輸入欄第一字即成頁"
        "＋第二字沿游標接續、兩步 undo 回空紙面、匯入後標題跟文件名"
    )

    # C26 畫布縮放平移（Sprint 124，抽於 editor/smoke_view.py，同行數紀律）
    check_view(EditorWindow, DOC)

    # C27 頁面導航與縮圖面板（Sprint 125，抽於 editor/smoke_nav.py）
    check_nav(EditorWindow, ROOT / "samples" / "chapter-opening.doc.json")

    # C28 檔案生命週期（Sprint 126，抽於 editor/smoke_file.py）
    check_file(EditorWindow, ROOT / "samples" / "chapter-opening.doc.json")

    # C29 轉存 PDF 介面（Sprint 127，抽於 editor/smoke_export.py）
    check_export(EditorWindow, DOC)

    # C30 尋找／取代（Sprint 128 丙1，抽於 editor/smoke_find.py）
    check_find(EditorWindow, DOC)

    # C31 文件資訊（Sprint 128 丙2，抽於 editor/smoke_info.py）
    check_info(EditorWindow, DOC)

    # C32 對頁檢視（Sprint 129 甲4，抽於 editor/smoke_spread.py）
    check_spread(EditorWindow, ROOT / "samples" / "paiban-xiaoji-ch1.doc.json")

    # C33 主版指派介面（Sprint 130 丁1，抽於 editor/smoke_master.py）
    check_master(
        EditorWindow,
        ROOT / "samples" / "chapter-opening.doc.json",
        ROOT / "samples" / "paiban-xiaoji-ch1.doc.json",
    )

    # 退出安全：各 C 建的視窗其縮圖執行緒可能仍在跑（QThread 運行中被銷毀
    # 會 abort），統一收攏後才收尾
    for widget in QApplication.instance().topLevelWidgets():
        shutdown = getattr(widget, "_shutdown_thumbnails", None)
        if shutdown is not None:
            shutdown()

    print(
        "SMOKE PASS：離屏可跑＋雙層建構＋hit-test 100%＋provenance 一致＋編輯回路 reflow"
        "＋框字格互動層＋app session 接線（IME 入框、undo／redo 統一歷史）＋AI 設定面板"
        "＋樣式面板＋拖曳範圍選取＋樣式管理＋改名與色票＋AI 指派校正＋模版庫面板"
        "＋preflight 面板＋背景執行緒與快取＋X-4 與 ICC 選取＋字型授權分區＋畫布置圖 UI"
        "＋文繞圖參數 UI（畫布所見即繞排所得）＋AI 指派背景執行緒（段序失效守門）"
        "＋稿件匯入（txt／md／docx 落到現行模版樣式，壞稿不進畫布）"
        "＋行首擠壓互動層字格（首格上緣跟著字形位移、字格相連無死區）"
        "＋空白起始（未命名空紙面、輸入欄第一字即成頁、undo 回空、標題跟文件名）"
        "＋畫布縮放平移（Ctrl+滾輪／Shift+滾輪／檢視選單／整頁 fit／重繪保留視角）"
        "＋頁面導航與縮圖面板（頁碼指示器／版面選單／面板點選跳頁／背景縮圖渲染）"
        "＋檔案生命週期（儲存另存開啟新建／髒標記／關閉確認／round-trip 守門）"
        "＋轉存 PDF 介面（檔案選單轉存項＋Ctrl+E＋空白守門＋背景 export_pdf 真產出"
        "成品／PyMuPDF 讀回驗／X-4 未選 ICC 擋 accept／取消與重入據實提示）"
        "＋尋找／取代（編輯選單 Ctrl+F／Ctrl+H＋純函式 find_matches＋真樣本命中頁定位"
        "高亮＋取代單一 undo 步＋全部取代 N 步復原）＋文件資訊（工具選單字數統計：總字數"
        "／段數／頁數／樣式用量）"
        "＋對頁檢視（檢視選單勾選項＋Ctrl+3＋右翻書偶右奇左併排＋目前頁偏移後全命中"
        "＋點對頁跳頁＋頁1 單邊＋純檢視不改版面頁數）"
        "＋主版指派介面（頁面面板右鍵七主版著作序＋勾選跟隨 page.master＋既有節首頁換節"
        "主版＋節內乾淨起頁升新節首延續至下一節首＋取消節首併回前節＋跨頁續段起頁停用提示）"
        "（IME 直排組字、視覺對位與拖曳手感待 Owner 真視窗）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
