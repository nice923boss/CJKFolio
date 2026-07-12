"""editor 畫布骨架的離屏煙霧驗證（Gate 5：可跑＋建構＋幾何同源反查）。

不入 pytest 基線（Sprint 17：GUI 套件不綁核心基線）；獨立跑：
  python editor/smoke_check.py
驗證項（皆離屏可自主驗證，不含視覺與 IME）：
  C1 QApplication＋scene 可建、雙層畫布建構無誤
  C2 互動層字格數 > 0、底圖 pixmap 存在
  C3 hit-test 反查 100%（每字格中心 itemAt → (placed_idx, cell_idx) 全對）
  C4 resolve_hit 反查文件游標與文件段 text 一致（cjk 字格 span 切片＝cell.text）
視覺對位與 IME 直排輸入需真視窗與 Owner 鍵盤實測（GAPS #19），非本驗證範圍。
"""
import os
import sys
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

from cjkfolio.document import load_document  # noqa: E402
from cjkfolio.layout import layout_document  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from editor.app import EditorWindow  # noqa: E402
from editor.canvas import build_page_scene, iter_cell_rects, resolve_hit  # noqa: E402

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

    print(
        "SMOKE PASS：離屏可跑＋雙層建構＋hit-test 100%＋provenance 一致＋編輯回路 reflow"
        "（IME 直排組字與視覺對位待 Owner 真視窗）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
