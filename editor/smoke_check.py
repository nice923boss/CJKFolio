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

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QTransform  # noqa: E402
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

    print(
        "SMOKE PASS：離屏可跑＋雙層建構＋hit-test 100%＋provenance 一致＋編輯回路 reflow"
        "＋框字格互動層＋app session 接線（IME 入框、undo／redo 統一歷史）"
        "（IME 直排組字與視覺對位待 Owner 真視窗）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
