"""Spike 10 探針：WYSIWYG 畫布（QGraphicsScene）與排版核心同步契約。

驗證 premortem.md 的 S1〜S5：
  S1 offscreen 環境可跑、scene 可渲染成 PNG
  S2 互動層字格高亮框與底圖字形對位（輸出 overlay PNG 供 Read 目檢）
  S3 全頁字格中心 itemAt 反查 100% 正確
  S4 編輯回路端到端延遲（重排＋單頁渲染＋底圖更新＋互動層重建）
  S5 全章互動層規模（item 數、建立時間、hit-test 延遲）

架構：底圖層（既有 PNG 渲染後端）＋互動層（layout 幾何直接生成透明字格 item）。
互動層座標復用 render 同一組幾何函式，不另立幾何（兩層同源）。

執行（自 repo 根）：python spikes/spike10-canvas-sync/probe_canvas_sync.py
輸出：spikes/spike10-canvas-sync/out/（不入 repo）
"""
import json
import os
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # 必須在 Qt import 前

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QTransform  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from cjkfolio.document import load_document  # noqa: E402
from cjkfolio.layout import (  # noqa: E402
    layout_document,
    line_justified_advance,
    style_advance_pt,
    style_line_slots,
)
from cjkfolio.render import PageRenderer, line_axis_x_pt, mm_to_pt  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
DOC_PATH = ROOT / "assets" / "reference" / "chapter1md.doc.json"
TEMPLATE_PATH = ROOT / "templates" / "neizai-zhengli.json"


def pil_to_qimage(img) -> QImage:
    """PIL "L" 灰階 → QImage（stride＝寬，PIL tobytes 無 padding；copy 保活）。"""
    return QImage(img.tobytes(), img.width, img.height, img.width,
                  QImage.Format_Grayscale8).copy()


def cell_rects(template, master, page, book_number: int, scale: float):
    """互動層字格矩形（px）：與 render._draw_vertical_body 同一組幾何函式推導。

    yield (placed_idx, cell_idx, x, y, w, h, kind)。space 格也含（選取需要）。
    """
    top_pt = mm_to_pt(master.margins.top_mm)
    for pi, placed in enumerate(page.placed):
        style = template.paragraph_styles[placed.style]
        advance = style_advance_pt(style, master.grid)
        axis = line_axis_x_pt(template, master, placed.slot, book_number,
                              line_slots=style_line_slots(style, master.grid))
        adv, _ = line_justified_advance(placed.line, advance)
        line_top = top_pt + placed.line.start_slot * advance
        content_i = 0
        for ci, cell in enumerate(placed.line.cells):
            cell_top = line_top + content_i * adv
            size = style.size_pt
            if cell.char_style:
                size = template.character_styles[cell.char_style].size_pt
            x = (axis - size / 2) * scale
            y = cell_top * scale
            w = size * scale
            h = adv * cell.width * scale
            yield pi, ci, x, y, w, h, cell.kind
            content_i += cell.width


def build_interactive_layer(scene, template, master, page, book_number, scale):
    """建互動層：每字格一個透明 QGraphicsRectItem，data=(placed_idx, cell_idx)。"""
    items = []
    for pi, ci, x, y, w, h, kind in cell_rects(template, master, page, book_number, scale):
        item = QGraphicsRectItem(x, y, w, h)
        item.setPen(Qt.NoPen)
        item.setBrush(QBrush(QColor(0, 0, 0, 0)))  # 全透明但保有填充形狀（hit 區域）
        item.setZValue(1)
        item.setData(0, (pi, ci))
        scene.addItem(item)
        items.append(item)
    return items


def render_scene_png(scene, path: Path) -> None:
    rect = scene.sceneRect()
    out_img = QImage(int(rect.width()), int(rect.height()), QImage.Format_RGB32)
    out_img.fill(Qt.white)
    painter = QPainter(out_img)
    scene.render(painter)
    painter.end()
    out_img.save(str(path))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    metrics: dict = {}

    doc = load_document(DOC_PATH)
    template = load_template(TEMPLATE_PATH)
    master = template.masters[doc.master]

    # ---- S1：offscreen 環境 ----
    t0 = time.perf_counter()
    app = QApplication([])
    view = QGraphicsView()  # 驗證 View 可實例化（互動容器）；渲染走 scene.render
    metrics["s1_qapp_ms"] = (time.perf_counter() - t0) * 1000
    print(f"S1 offscreen QApplication＋QGraphicsView 建立 {metrics['s1_qapp_ms']:.1f}ms（platform={app.platformName()}）")

    dpi = 150
    scale = dpi / 72.0
    layout = layout_document(doc, template)
    renderer = PageRenderer(template, doc.master, dpi=dpi)
    page = layout.pages[0]
    book_number = page.number  # first_page=1
    footer = {"number": str(book_number), "title": doc.title}

    t0 = time.perf_counter()
    pil_img = renderer.render_page(page, footer_texts=footer, book_number=book_number,
                                   vertical=layout.vertical)
    t_render = (time.perf_counter() - t0) * 1000

    scene = QGraphicsScene()
    t0 = time.perf_counter()
    qimg = pil_to_qimage(pil_img)
    base_item = QGraphicsPixmapItem(QPixmap.fromImage(qimg))
    base_item.setZValue(0)
    scene.addItem(base_item)
    t_pixmap = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    items = build_interactive_layer(scene, template, master, page, book_number, scale)
    t_layer = (time.perf_counter() - t0) * 1000
    metrics["page1_render_ms"] = t_render
    metrics["page1_pixmap_ms"] = t_pixmap
    metrics["page1_layer_ms"] = t_layer
    metrics["page1_cells"] = len(items)
    print(f"頁 1：渲染 {t_render:.1f}ms、pixmap {t_pixmap:.1f}ms、互動層 {len(items)} 格 {t_layer:.1f}ms")

    render_scene_png(scene, OUT / "page1_base.png")

    # ---- S3：全頁字格中心 itemAt 反查 ----
    total = hit = 0
    for pi, ci, x, y, w, h, kind in cell_rects(template, master, page, book_number, scale):
        total += 1
        found = scene.itemAt(QPointF(x + w / 2, y + h / 2), QTransform())
        if found is not None and found.data(0) == (pi, ci):
            hit += 1
    metrics["s3_total"] = total
    metrics["s3_hit"] = hit
    print(f"S3 hit-test：{hit}/{total} 反查正確")

    # ---- S2：對位高亮（散布多行的字格＋char_style 覆寫格，Read 目檢框住字形）----
    all_rects = [r for r in cell_rects(template, master, page, book_number, scale)
                 if r[6] != "space"]
    picks = [all_rects[j][:6] for j in (0, len(all_rects) // 3,
                                        2 * len(all_rects) // 3, len(all_rects) - 1)]
    styled = {(pi, ci) for pi, placed in enumerate(page.placed)
              for ci, c in enumerate(placed.line.cells) if c.char_style}
    picks += [r[:6] for r in all_rects if (r[0], r[1]) in styled][:1]
    for pi, ci, x, y, w, h in picks:
        hl = QGraphicsRectItem(x, y, w, h)
        hl.setPen(QPen(QColor(220, 30, 30), 1.5))
        hl.setBrush(QBrush(QColor(255, 220, 0, 70)))
        hl.setZValue(2)
        scene.addItem(hl)
    metrics["s2_highlights"] = [(pi, ci) for pi, ci, *_ in picks]
    render_scene_png(scene, OUT / "page1_overlay.png")
    print(f"S2 高亮 {len(picks)} 格 → out/page1_overlay.png（Read 目檢對位）")

    # ---- S4：編輯回路（改頁 1 上的段，重排＋重渲染頁 1＋更新底圖＋重建互動層）----
    def append_text(para, suffix: str):
        """模擬打字：段末加字，維持 document@2 正規化不變式（text＝runs 串接）。"""
        if para.runs:
            last = para.runs[-1]
            new_runs = para.runs[:-1] + (replace(last, text=last.text + suffix),)
            return replace(para, text=para.text + suffix, runs=new_runs)
        return replace(para, text=para.text + suffix)

    target_idx = next(i for i, p in enumerate(doc.paragraphs) if p.text)
    for probe_dpi in (150, 96):
        r = PageRenderer(template, doc.master, dpi=probe_dpi)
        s = probe_dpi / 72.0
        sc = QGraphicsScene()
        base = QGraphicsPixmapItem()
        sc.addItem(base)
        layer: list = []
        laps = {"flow": [], "render": [], "pixmap": [], "layer": [], "total": []}
        for i in range(10):
            edited = append_text(doc.paragraphs[target_idx], "測" * (i + 1))
            doc2 = replace(doc, paragraphs=doc.paragraphs[:target_idx] + (edited,)
                           + doc.paragraphs[target_idx + 1:])
            t_all = time.perf_counter()
            t0 = time.perf_counter()
            lay2 = layout_document(doc2, template)
            laps["flow"].append((time.perf_counter() - t0) * 1000)
            pg = lay2.pages[0]
            t0 = time.perf_counter()
            img2 = r.render_page(pg, footer_texts=footer, book_number=pg.number,
                                 vertical=lay2.vertical)
            laps["render"].append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            base.setPixmap(QPixmap.fromImage(pil_to_qimage(img2)))
            laps["pixmap"].append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            for it in layer:
                sc.removeItem(it)
            layer = build_interactive_layer(sc, template, master, pg, pg.number, s)
            laps["layer"].append((time.perf_counter() - t0) * 1000)
            laps["total"].append((time.perf_counter() - t_all) * 1000)
        med = {k: statistics.median(v) for k, v in laps.items()}
        metrics[f"s4_dpi{probe_dpi}"] = med
        print(f"S4 編輯回路 @{probe_dpi}dpi 中位：總 {med['total']:.1f}ms"
              f"（重排 {med['flow']:.1f}／渲染 {med['render']:.1f}"
              f"／pixmap {med['pixmap']:.1f}／互動層 {med['layer']:.1f}）")

    # ---- S5：全章互動層規模（22 頁級，單一 scene 頁面橫向平鋪）----
    big = QGraphicsScene()
    page_w_px = mm_to_pt(template.page_width_mm) * scale
    t0 = time.perf_counter()
    n_items = 0
    for page_i, pg in enumerate(layout.pages):
        offset = page_i * (page_w_px + 20)
        bn = pg.number
        for pi, ci, x, y, w, h, kind in cell_rects(template, master, pg, bn, scale):
            item = QGraphicsRectItem(x + offset, y, w, h)
            item.setPen(Qt.NoPen)
            item.setBrush(QBrush(QColor(0, 0, 0, 0)))
            item.setData(0, (pg.number, pi, ci))
            big.addItem(item)
            n_items += 1
    t_build = (time.perf_counter() - t0) * 1000
    samples = []
    probe_targets = []
    for page_i, pg in enumerate(layout.pages):
        offset = page_i * (page_w_px + 20)
        for j, (pi, ci, x, y, w, h, kind) in enumerate(cell_rects(template, master, pg, pg.number, scale)):
            if j % 97 == 0:
                probe_targets.append((pg.number, pi, ci, x + offset + w / 2, y + h / 2))
    s5_hit = 0
    for num, pi, ci, cx, cy in probe_targets:
        t0 = time.perf_counter()
        found = big.itemAt(QPointF(cx, cy), QTransform())
        samples.append((time.perf_counter() - t0) * 1000)
        if found is not None and found.data(0) == (num, pi, ci):
            s5_hit += 1
    metrics["s5_pages"] = len(layout.pages)
    metrics["s5_items"] = n_items
    metrics["s5_build_ms"] = t_build
    metrics["s5_hittest_median_ms"] = statistics.median(samples)
    metrics["s5_hittest_max_ms"] = max(samples)
    metrics["s5_hit"] = s5_hit
    metrics["s5_probes"] = len(probe_targets)
    print(f"S5 規模：{len(layout.pages)} 頁 {n_items} 格建立 {t_build:.0f}ms、"
          f"hit-test 中位 {statistics.median(samples):.3f}ms（max {max(samples):.3f}）、"
          f"反查 {s5_hit}/{len(probe_targets)}")

    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(f"指標 → {OUT / 'metrics.json'}")
    del view
    return 0


if __name__ == "__main__":
    sys.exit(main())
