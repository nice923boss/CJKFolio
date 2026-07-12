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


def build_page_scene(
    scene: QGraphicsScene,
    template: Template,
    doc: Document,
    layout: LayoutResult,
    page,
    dpi: int = 150,
) -> list:
    """在 scene 建雙層畫布（底圖 PNG z=0＋互動層透明字格 z=1）。回傳互動層 item list。

    互動層 item data(0)＝(placed_idx, cell_idx)，供 itemAt 反查 → resolve_hit。
    """
    scale = dpi / 72.0
    book_number = page.number
    renderer = PageRenderer(template, doc.master, dpi=dpi)
    footer = {"number": str(book_number), "title": doc.title or ""}
    pil_img = renderer.render_page(
        page, footer_texts=footer, book_number=book_number, vertical=layout.vertical
    )
    base = QGraphicsPixmapItem(QPixmap.fromImage(pil_to_qimage(pil_img)))
    base.setZValue(0)
    scene.addItem(base)

    master = template.masters[doc.master]
    items: list = []
    for pi, ci, x, y, w, h, _kind in iter_cell_rects(
        template, master, page, book_number, scale
    ):
        item = QGraphicsRectItem(x, y, w, h)
        item.setPen(Qt.NoPen)
        item.setBrush(QBrush(QColor(0, 0, 0, 0)))  # 全透明但保填充形狀（hit 區域）
        item.setZValue(1)
        item.setData(0, (pi, ci))
        scene.addItem(item)
        items.append(item)
    return items


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
