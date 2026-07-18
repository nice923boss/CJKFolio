"""CJKFolio 編輯器畫布核心（Phase 2）：雙層畫布與點字格反查文件游標。

承 Spike 10（spikes/spike10-canvas-sync/）離屏驗證的雙層架構，落為產品碼：
  底圖層＝既有 PNG 渲染後端輸出（QGraphicsPixmapItem，z=0）
  互動層＝layout 幾何直接生成的透明字格（QGraphicsRectItem，z=1，data=(placed_idx, cell_idx)）

互動層座標復用 render 直排 body 同一組幾何函式（line_axis_x_pt／style_advance_pt／
line_justified_advance／lead_offset_pt），與雙後端同源紀律一致，不另立幾何（公式與
cjkfolio/render.py::PageRenderer._draw_vertical_body 逐項對齊）。

紅線：本模組不綁任何素材路徑，demo 文件由呼叫端指定（samples/ 自擬文件，非參考書）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene

from cjkfolio.document import Document
from cjkfolio.frames import masters_for_layout, resolve_text_frames
from cjkfolio.image_editing import handle_rects
from cjkfolio.images import resolve_placed_images
from cjkfolio.layout import (
    LayoutResult,
    line_justified_advance,
    style_advance_pt,
    style_line_slots,
)
from cjkfolio.render import PageRenderer, line_axis_x_pt, mm_to_pt
from cjkfolio.styles import Template


@dataclass(frozen=True)
class CellHit:
    """點字格反查到的文件游標（Sprint 18 provenance 的畫布落地）。"""

    page_number: int
    placed_idx: int
    cell_idx: int
    para_idx: Optional[int]
    span: Optional[tuple]
    text: str
    style: str
    kind: str


@dataclass(frozen=True)
class FrameCellHit:
    """點文字框字格反查到的框游標（Sprint 58 框 provenance 的畫布落地）。

    span 座標系＝文字來源框（source_idx，串接鏈首）的 text 半開區間；
    doc.text_frames[source_idx].text[s:e] 即來源字元。"""

    page_number: int
    frame_idx: int
    source_idx: int
    line_idx: int
    cell_idx: int
    span: Optional[tuple]
    text: str
    style: str
    kind: str


def pil_to_qimage(img) -> QImage:
    """PIL "L" 灰階 → QImage（stride＝寬，PIL tobytes 無 padding；copy 保活）。"""
    return QImage(
        img.tobytes(), img.width, img.height, img.width, QImage.Format_Grayscale8
    ).copy()


def iter_cell_rects(
    template: Template, master, page, book_number: int, scale: float
) -> Iterator[tuple]:
    """互動層字格矩形（px），與 render 直排 body 逐項同源。

    yield (placed_idx, cell_idx, x, y, w, h, kind)；space 格亦含（選取需要）。
    幾何：axis＝欄行軸（水平中心）、cell_top＝字格頂；矩形以 axis 為水平中心、
    寬＝級數、高＝實效字距×width。
    """
    top_pt = mm_to_pt(master.margins.top_mm)
    for pi, placed in enumerate(page.placed):
        style = template.paragraph_styles[placed.style]
        advance = style_advance_pt(style, master.grid)
        axis = line_axis_x_pt(
            template,
            master,
            placed.slot,
            book_number,
            line_slots=style_line_slots(style, master.grid),
        )
        adv, _status = line_justified_advance(placed.line, advance)
        line_top = top_pt + placed.line.start_slot * advance + placed.lead_offset_pt
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


def page_frame_placements(
    template: Template, doc: Document, layout: LayoutResult, page
) -> tuple:
    """該頁的文字框 placements（含 frame_idx／source_idx，Sprint 58）。

    封裝逐頁主版解析＋resolve_text_frames，供 build_page_scene 與呼叫端
    （app／smoke 反查 FrameCellHit 來源文字）共用單一事實來源。"""
    masters = masters_for_layout(template, doc, layout)
    return resolve_text_frames(doc, template, masters).get(page.number, ())


def iter_frame_cell_rects(placements, scale: float) -> Iterator[tuple]:
    """文字框互動層字格矩形（px），與 render._draw_text_frame 逐項同源。

    yield (frame_idx, line_idx, cell_idx, x, y, w, h, kind)。幾何：欄行軸＝
    FrameLine.axis_x_pt（水平中心）、字格頂＝top_pt＋content_i×advance_pt
    （框內不齊行、等距、無字元樣式覆寫）。"""
    for pl in placements:
        for li, fl in enumerate(pl.lines):
            content_i = 0
            for ci, cell in enumerate(fl.line.cells):
                x = (fl.axis_x_pt - fl.size_pt / 2) * scale
                y = (fl.top_pt + content_i * fl.advance_pt) * scale
                w = fl.size_pt * scale
                h = fl.advance_pt * cell.width * scale
                yield pl.frame_idx, li, ci, x, y, w, h, cell.kind
                content_i += cell.width


def page_images(template: Template, doc: Document, layout: LayoutResult, page,
                base_dir=None) -> tuple:
    """該頁的置入圖 ((路徑, PIL 影像, rect|None), ...)（Sprint 102）。

    封裝逐頁主版解析＋resolve_placed_images，供 build_page_scene 與呼叫端共用
    單一事實來源（同 page_frame_placements 慣例）。圖檔缺失或不可讀由
    resolve_placed_images 拋 ImageError，呼叫端負責提示（畫布不吞錯）。"""
    masters = masters_for_layout(template, doc, layout)
    return resolve_placed_images(doc, masters, base_dir=base_dir).get(page.number, ())


def iter_image_rects(doc: Document, page_number: int, scale: float) -> Iterator[tuple]:
    """該頁 rect 置入圖的互動層矩形（px）。yield (image_idx, x, y, w, h)。

    幾何直接取 PlacedImage.rect（trim pt、top-down），與底圖 render._draw_image
    同一組座標；槽式圖（rect None）無座標故不建互動層（不可拖放，見
    image_editing 模組說明）。文件序＝繪製序，故後 yield 者應疊在上層。"""
    for idx, placed in enumerate(doc.images):
        if placed.page != page_number or placed.rect is None:
            continue
        x0, y0, x1, y1 = placed.rect
        yield idx, x0 * scale, y0 * scale, (x1 - x0) * scale, (y1 - y0) * scale


def build_page_scene(
    scene: QGraphicsScene,
    template: Template,
    doc: Document,
    layout: LayoutResult,
    page,
    dpi: int = 150,
    images=(),
) -> list:
    """在 scene 建雙層畫布（底圖 PNG z=0＋互動層透明字格 z=1）。回傳互動層 item list。

    互動層 item data(0)：body 字格＝(placed_idx, cell_idx) → resolve_hit；
    文字框字格＝("frame", frame_idx, line_idx, cell_idx) → resolve_frame_hit（Sprint 58）；
    置入圖框＝("image", image_idx) z=2、角控制點＝("image-handle", image_idx, 角名)
    z=5（Sprint 102）。圖層 z 高於字格，故圖上按下取到的是圖不是其下的字。

    images＝該頁已解析的置入圖（page_images 產出），底圖據此繪製；呼叫端自行解析
    是為了讓「圖檔讀不到」的提示留在 UI 層（畫布不代為決定要不要吞錯）。
    """
    scale = dpi / 72.0
    book_number = page.number
    renderer = PageRenderer(template, doc.master, dpi=dpi)
    footer = {"number": str(book_number), "title": doc.title or ""}
    vertical = getattr(page, "vertical", layout.vertical)  # 逐頁方向（Sprint 53）
    frames = page_frame_placements(template, doc, layout, page)
    pil_img = renderer.render_page(
        page, footer_texts=footer, book_number=book_number, vertical=vertical,
        frames=frames,  # 底圖含獨立文字框（Sprint 55）；互動層字格見下（Sprint 58）
        images=images,  # 底圖含置入圖（Sprint 102）；互動層圖框見下
    )
    base = QGraphicsPixmapItem(QPixmap.fromImage(pil_to_qimage(pil_img)))
    base.setZValue(0)
    scene.addItem(base)
    items: list = []

    def add_item(x: float, y: float, w: float, h: float, key: tuple,
                 z: float = 1) -> None:
        item = QGraphicsRectItem(x, y, w, h)
        item.setPen(Qt.NoPen)
        item.setBrush(QBrush(QColor(0, 0, 0, 0)))  # 全透明但保填充形狀（hit 區域）
        item.setZValue(z)
        item.setData(0, key)
        scene.addItem(item)
        items.append(item)

    # 置入圖框與角控制點（Sprint 102）：直排橫排皆建（rect 圖不依行軸語意）
    for idx, x, y, w, h in iter_image_rects(doc, page.number, scale):
        add_item(x, y, w, h, ("image", idx), z=2)
        rect = doc.images[idx].rect
        for name, (hx0, hy0, hx1, hy1) in handle_rects(rect).items():
            add_item(hx0 * scale, hy0 * scale, (hx1 - hx0) * scale,
                     (hy1 - hy0) * scale, ("image-handle", idx, name), z=5)
    if not vertical:
        # 橫排頁字格互動層未建（iter_cell_rects 為直排 body 幾何）：GAPS #30 (b) 註記
        return items

    # 逐頁主版（節式主版指派，Sprint 51）：互動層幾何依該頁主版，與 render 同源
    master = template.masters[getattr(page, "master", "") or doc.master]
    for pi, ci, x, y, w, h, _kind in iter_cell_rects(
        template, master, page, book_number, scale
    ):
        add_item(x, y, w, h, (pi, ci))
    for fi, li, ci, x, y, w, h, _kind in iter_frame_cell_rects(frames, scale):
        add_item(x, y, w, h, ("frame", fi, li, ci))
    return items


def resolve_frame_hit(page_number: int, placement, line_idx: int,
                      cell_idx: int) -> FrameCellHit:
    """框互動層字格 ("frame", frame_idx, line_idx, cell_idx) → 框游標。

    placement＝該頁 page_frame_placements 中 frame_idx 對應者；span 座標系＝
    doc.text_frames[placement.source_idx].text（串接鏈首）半開區間。"""
    cell = placement.lines[line_idx].line.cells[cell_idx]
    return FrameCellHit(
        page_number=page_number,
        frame_idx=placement.frame_idx,
        source_idx=placement.source_idx,
        line_idx=line_idx,
        cell_idx=cell_idx,
        span=cell.span,
        text=cell.text,
        style=placement.style,
        kind=cell.kind,
    )


def resolve_hit(doc: Document, page, placed_idx: int, cell_idx: int) -> CellHit:
    """互動層字格 (placed_idx, cell_idx) → 文件游標（para_idx, span, text）。"""
    placed = page.placed[placed_idx]
    cell = placed.line.cells[cell_idx]
    return CellHit(
        page_number=page.number,
        placed_idx=placed_idx,
        cell_idx=cell_idx,
        para_idx=placed.para_idx,
        span=cell.span,
        text=cell.text,
        style=placed.style,
        kind=cell.kind,
    )
