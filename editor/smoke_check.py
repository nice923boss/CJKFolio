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

    print(
        "SMOKE PASS：離屏可跑＋雙層建構＋hit-test 100%＋provenance 一致＋編輯回路 reflow"
        "＋框字格互動層＋app session 接線（IME 入框、undo／redo 統一歷史）＋AI 設定面板"
        "＋樣式面板＋拖曳範圍選取＋樣式管理（IME 直排組字、視覺對位與手感待 Owner 真視窗）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
