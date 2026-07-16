"""獨立文字框（Sprint 55）：任意矩形內的直排文字（v1 單一樣式、不串接、不繞排）。

框內斷行與禁則復用 engine（break_paragraph：正規化＋tokenize＋擠入追出），
欄幾何依樣式級數換算（§10 規則同構：字距＝級數×(網格字距/網格基準級數)、
欄距＝級數×(網格行距/網格基準級數)，grid＝框落點頁的主版網格）。
兩後端共用本層產出的 FramePlacement（同源紀律）；溢出框寬的欄不繪並列違規
（不沉默）。框可溢出版心（同 PlacedImage.rect：自由佈局層正當用法）。
"""
from dataclasses import dataclass
from math import floor

from .engine import break_paragraph
from .layout import HORIZONTAL_MODE, style_advance_pt

_EPS = 1e-6


@dataclass(frozen=True)
class FrameLine:
    line: object        # engine.Line（cells＋start_slot，禁則已解消）
    axis_x_pt: float    # 欄行軸（水平中心，trim pt；直排右起）
    top_pt: float       # 首字頂（trim pt）
    advance_pt: float   # 字距（框內不齊行，等距）
    size_pt: float


@dataclass(frozen=True)
class FramePlacement:
    style: str          # 段落樣式名（後端據此取字型）
    lines: tuple        # FrameLine 序列
    violations: list    # 溢出等違規訊息（應為空）


def frame_pitch_pt(style, grid) -> float:
    """欄距＝級數×(網格行距/網格基準級數)（§10 換算規則同構）。"""
    return style.size_pt * (grid.line_pitch_pt / grid.base_size_pt)


def layout_text_frame(frame, template, grid) -> FramePlacement:
    """文字框 → FramePlacement（幾何確定性推導；未知樣式／橫排樣式快速失敗）。

    grid＝框落點頁的主版網格（度量換算比例來源）。欄自框右緣起（直排右至左），
    欄 k 行軸＝x1 − (k＋0.5)×欄距；每欄容量＝floor(框高／字距)。
    """
    if frame.style not in template.paragraph_styles:
        raise KeyError(f"文字框引用未知段落樣式：{frame.style}")
    st = template.paragraph_styles[frame.style]
    if st.writing_mode == HORIZONTAL_MODE:
        raise ValueError(
            f"文字框 v1 僅支援直排樣式；「{frame.style}」為橫排（horizontal-tb，待 v2）"
        )
    x0, y0, x1, y1 = frame.rect
    advance = style_advance_pt(st, grid)
    pitch = frame_pitch_pt(st, grid)
    capacity = max(1, floor((y1 - y0) / advance + _EPS))
    max_cols = max(1, floor((x1 - x0) / pitch + _EPS))
    lines = break_paragraph(frame.text, capacity, indent=0, vertical=True)
    violations: list = []
    if len(lines) > max_cols:
        dropped = sum(sum(c.width for c in ln.cells) for ln in lines[max_cols:])
        violations.append(
            f"文字框（頁 {frame.page}）溢出：{len(lines)} 欄超出框寬容量 "
            f"{max_cols} 欄，末 {dropped} 槽未繪"
        )
        lines = lines[:max_cols]
    placed = tuple(
        FrameLine(
            line=ln,
            axis_x_pt=x1 - (k + 0.5) * pitch,
            top_pt=y0 + ln.start_slot * advance,
            advance_pt=advance,
            size_pt=st.size_pt,
        )
        for k, ln in enumerate(lines)
    )
    return FramePlacement(style=frame.style, lines=placed, violations=violations)


def resolve_text_frames(doc, template, masters_by_page: dict) -> dict:
    """把 doc.text_frames 解析為 {版面頁號: (FramePlacement, ...)}，供兩後端共用。

    框頁超出排版頁數（不在 masters_by_page）→ 快速失敗（同 images 規則，
    v1 不為框造頁）；grid 取該頁主版網格（節式主版指派，Sprint 51）。
    """
    out: dict = {}
    for tf in doc.text_frames:
        master = masters_by_page.get(tf.page)
        if master is None:
            raise ValueError(
                f"文字框 page {tf.page} 超出排版頁數（共 {len(masters_by_page)} 頁）"
            )
        out.setdefault(tf.page, []).append(layout_text_frame(tf, template, master.grid))
    return {page: tuple(pls) for page, pls in out.items()}
