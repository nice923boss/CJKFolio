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
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QPixmap
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
from cjkfolio.primitives import book_number_for, sheet_face_for
from cjkfolio.render import PageRenderer, line_axis_x_pt, mm_to_pt
from cjkfolio.styles import Template


# Owner 需求（Sprint 147）：「滑鼠移動到圖片右下角，滑鼠也要改成可拖拉的圖示來示意
# 可以放大」。控制點本身全透明看不見，故游標形狀就是它唯一的存在提示；取作業系統的
# 對角縮放游標（↖↘／↗↙）＝與各繪圖軟體一致，且方向對得上該角能拖的走向。
# QGraphicsItem.setCursor 由 Qt 於 hover 時自動套用（不需選取、不需自寫 hover 事件）。
# 存 CursorShape 而非 QCursor 實例：QCursor 屬 GUI 資源，模組載入時（QApplication
# 之前）不建構，交由 setCursor 當場轉換。
HANDLE_CURSOR_SHAPES = {
    "nw": Qt.CursorShape.SizeFDiagCursor,  # ↖↘
    "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor,  # ↗↙
    "sw": Qt.CursorShape.SizeBDiagCursor,
}


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
    """PIL 影像 → QImage（stride＝寬×分量數，PIL tobytes 無 padding；copy 保活）。

    "RGB"（Sprint 137 起的預設畫布）走 Format_RGB888、"L" 走 Format_Grayscale8。
    其餘模式先轉 RGB：QImage 沒有對應格式，硬套 stride 會讀出雜訊而非報錯。
    """
    if img.mode == "L":
        fmt, stride = QImage.Format_Grayscale8, img.width
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
        fmt, stride = QImage.Format_RGB888, img.width * 3
    return QImage(img.tobytes(), img.width, img.height, stride, fmt).copy()


def iter_cell_rects(
    template: Template, master, page, sheet_face: int, scale: float
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
            sheet_face,
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
            # 字形位移（em×字級，Sprint 117）：矩形上緣跟著位移、高度補回，
            # 使墨跡落在自己的字格內，且與次枚字格仍相連（不產生點不到的死區）。
            offset = cell.glyph_offset * size
            y = (cell_top + offset) * scale
            w = size * scale
            h = (adv * cell.width - offset) * scale
            yield pi, ci, x, y, w, h, cell.kind
            content_i += cell.width
        if not placed.line.cells and placed.para_idx is not None:
            # 空白頁的空行（Sprint 153 插頁）：行首給一格落點槽位，點得到才能打字（Sprint 154）
            yield (pi, 0, (axis - style.size_pt / 2) * scale, line_top * scale,
                   style.size_pt * scale, advance * scale, "empty")


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


def spread_pages(page_number: int, total: int):
    """右翻書對開配對（紙面奇偶，Sprint 145）：回傳 (left_page, right_page)，
    None＝該側空白。頁號皆版面頁號（編輯器 first_page=1，版面頁號＝紙面號）。

    側別由紙張的面決定（primitives.is_right_page，Owner 實體書模型）：封面＝紙面 1，
    每翻一張即見其背面在右、下一面在左，故偶數紙面＝右頁、奇數紙面＝左頁。一組
    spread＝(右 偶 E, 左 奇 E+1)，讀序右→左＝頁號小→大。紙面 1（含封面）的右夥伴
    紙面 0 不存在＝單邊（闔上的書）；末偶紙面的左夥伴不存在＝單邊（翻完闔上書的
    封底畫面）。導航到 spread 內任一頁都得同一組。帶不帶封面配對公式相同：封面
    只是紙面 1 的內容，不再特例單邊在右（Sprint 132 的書頁號配對已廢，Owner：
    「第二頁應該是要在翻開後的右邊才正確」）。
    """
    if page_number % 2 == 0:  # 偶數紙面＝右頁
        right = page_number
        left = page_number + 1 if page_number + 1 <= total else None
    else:  # 奇數紙面＝左頁
        left = page_number
        right = page_number - 1 if page_number - 1 >= 1 else None
    return left, right


def build_page_scene(
    scene: QGraphicsScene,
    template: Template,
    doc: Document,
    layout: LayoutResult,
    page,
    dpi: int = 150,
    images=(),
    x_offset: float = 0.0,
    first_page: int = 1,
    base_dpi: int = 0,
) -> list:
    """在 scene 建雙層畫布（底圖 PNG z=0＋互動層透明字格 z=1）。回傳互動層 item list。

    互動層 item data(0)：body 字格＝(placed_idx, cell_idx) → resolve_hit；
    文字框字格＝("frame", frame_idx, line_idx, cell_idx) → resolve_frame_hit（Sprint 58）；
    置入圖框＝("image", image_idx) z=2、角控制點＝("image-handle", image_idx, 角名)
    z=5（Sprint 102）。圖層 z 高於字格，故圖上按下取到的是圖不是其下的字。
    整框拖曳區＝("frame-box", frame_idx) z=0.5（Sprint 136），低於字格：框內點在
    字上得字游標，點在空白處才搬整個框；框的角控制點由選取後的 UI 層另加（z=5）。

    images＝該頁已解析的置入圖（page_images 產出），底圖據此繪製；呼叫端自行解析
    是為了讓「圖檔讀不到」的提示留在 UI 層（畫布不代為決定要不要吞錯）。

    x_offset＝底圖與互動層一併水平平移的像素量（對頁檢視右頁置於 x=頁寬，Sprint 129）。
    預設 0.0＝與單頁完全等價（byte-identical），既有單頁路徑不受影響。
    """
    scale = dpi / 72.0  # 互動層字格幾何一律依 dpi（scene 座標系），不隨底圖畫質變
    base_dpi = base_dpi or dpi  # 底圖渲染解析度（Sprint 133，畫質用；預設同 scene）
    # 頁碼數字＝書頁號（封面翻開後起算，Sprint 132）；側別與鏡像＝紙面號
    # （Sprint 145 SSOT），與兩後端同源。
    book_number = book_number_for(page.number, first_page, layout.cover_pages)
    sheet_face = sheet_face_for(page.number, first_page)
    renderer = PageRenderer(template, doc.master, dpi=base_dpi)
    no_folio = page.number <= layout.cover_pages or page.blank  # 封面與補頁不編頁碼
    footer = None if no_folio else {
        "number": str(book_number), "title": doc.title or ""}
    vertical = getattr(page, "vertical", layout.vertical)  # 逐頁方向（Sprint 53）
    frames = page_frame_placements(template, doc, layout, page)
    pil_img = renderer.render_page(
        page, footer_texts=footer, sheet_face=sheet_face, vertical=vertical,
        frames=frames,  # 底圖含獨立文字框（Sprint 55）；互動層字格見下（Sprint 58）
        images=images,  # 底圖含置入圖（Sprint 102）；互動層圖框見下
    )
    base = QGraphicsPixmapItem(QPixmap.fromImage(pil_to_qimage(pil_img)))
    base.setZValue(0)
    # 高 dpi 底圖縮回 scene 尺寸（Sprint 133）：畫面上像素更密而 scene 座標不變，
    # 故互動層字格幾何零改動。平滑轉換讓非整數倍縮放不出硬鋸齒。
    base.setTransformationMode(Qt.SmoothTransformation)
    if base_dpi != dpi:
        base.setScale(dpi / base_dpi)
    # data(1)＝底圖標記（畫質升級時據此找回該頁底圖）。**刻意不用 data(0)**：
    # 那是互動層的字格鍵，底圖帶了就會被 _cell_item_at 當成字格命中。
    base.setData(1, page.number)
    base.setPos(x_offset, 0.0)  # 對頁右頁整頁右移（Sprint 129）；預設 0.0＝不動
    scene.addItem(base)
    items: list = []

    def add_item(x: float, y: float, w: float, h: float, key: tuple,
                 z: float = 1, cursor=None) -> None:
        item = QGraphicsRectItem(x + x_offset, y, w, h)
        item.setPen(Qt.NoPen)
        item.setBrush(QBrush(QColor(0, 0, 0, 0)))  # 全透明但保填充形狀（hit 區域）
        item.setZValue(z)
        item.setData(0, key)
        if cursor is not None:  # 滑到此區的游標形狀（Sprint 147，只有圖角控制點用）
            item.setCursor(QCursor(cursor))
        scene.addItem(item)
        items.append(item)

    # 置入圖框與角控制點（Sprint 102）：直排橫排皆建（rect 圖不依行軸語意）
    for idx, x, y, w, h in iter_image_rects(doc, page.number, scale):
        add_item(x, y, w, h, ("image", idx), z=2)
        rect = doc.images[idx].rect
        for name, (hx0, hy0, hx1, hy1) in handle_rects(rect).items():
            add_item(hx0 * scale, hy0 * scale, (hx1 - hx0) * scale,
                     (hy1 - hy0) * scale, ("image-handle", idx, name), z=5,
                     cursor=HANDLE_CURSOR_SHAPES[name])
    # 整框拖曳的命中區（Sprint 136）：**z=0.5 刻意低於字格**，故框內點在字上仍
    # 得字游標（打字為主要操作，不可被搬框攔胡），點在框內空白處才選中整個框。
    for placement in frames:
        fx0, fy0, fx1, fy1 = doc.text_frames[placement.frame_idx].rect
        add_item(fx0 * scale, fy0 * scale, (fx1 - fx0) * scale,
                 (fy1 - fy0) * scale, ("frame-box", placement.frame_idx), z=0.5)
    if not vertical:
        # 橫排頁字格互動層未建（iter_cell_rects 為直排 body 幾何）：GAPS #30 (b) 註記
        return items

    # 逐頁主版（節式主版指派，Sprint 51）：互動層幾何依該頁主版，與 render 同源
    master = template.masters[getattr(page, "master", "") or doc.master]
    for pi, ci, x, y, w, h, _kind in iter_cell_rects(
        template, master, page, sheet_face, scale
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
    """互動層字格 (placed_idx, cell_idx) → 文件游標（para_idx, span, text）。

    空行的落點槽位（Sprint 154）回 span (0, 0)、kind "empty"：插入落在段首。"""
    placed = page.placed[placed_idx]
    if not placed.line.cells:
        return CellHit(page_number=page.number, placed_idx=placed_idx, cell_idx=cell_idx,
                       para_idx=placed.para_idx, span=(0, 0), text="",
                       style=placed.style, kind="empty")
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
