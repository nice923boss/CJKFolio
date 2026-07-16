"""獨立文字框（Sprint 55 建立＋Sprint 57 串接）：任意矩形內的直排文字。

框內斷行與禁則復用 engine（正規化＋tokenize＋擠入追出），欄幾何依樣式級數
換算（§10 規則同構：字距＝級數×(網格字距/網格基準級數)、欄距＝級數×(網格
行距/網格基準級數)，grid＝框落點頁的主版網格）。
串接（thread）：同鏈框依文件序跨框續排，逐框以該框頁網格斷行取欄、以已消費
cell 數切出剩餘 cells 續排下一框（行邊界禁則已解消＝合法切點，engine.break_cells）；
鏈尾仍排不下列違規（不沉默）。兩後端共用本層產出的 FramePlacement（同源紀律）；
框可溢出版心（同 PlacedImage.rect：自由佈局層正當用法）。
"""
from dataclasses import dataclass
from math import floor

from .engine import break_cells, break_paragraph, normalize, tokenize
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


def _frame_style(frame, template):
    """框樣式解析（未知樣式／橫排樣式快速失敗；串接鏈取鏈首樣式，全鏈一致
    由 document 解析層守門）。"""
    if frame.style not in template.paragraph_styles:
        raise KeyError(f"文字框引用未知段落樣式：{frame.style}")
    st = template.paragraph_styles[frame.style]
    if st.writing_mode == HORIZONTAL_MODE:
        raise ValueError(
            f"文字框 v1 僅支援直排樣式；「{frame.style}」為橫排（horizontal-tb，待 v2）"
        )
    return st


def _frame_metrics(st, rect, grid):
    """框欄幾何：(字距, 欄距, 每欄容量, 欄數容量)。欄自框右緣起（直排右至左）。"""
    x0, y0, x1, y1 = rect
    advance = style_advance_pt(st, grid)
    pitch = frame_pitch_pt(st, grid)
    capacity = max(1, floor((y1 - y0) / advance + _EPS))
    max_cols = max(1, floor((x1 - x0) / pitch + _EPS))
    return advance, pitch, capacity, max_cols


def _place_lines(lines, rect, advance: float, pitch: float, size_pt: float) -> tuple:
    """欄序列 → FrameLine（欄 k 行軸＝x1 − (k＋0.5)×欄距）。"""
    x0, y0, x1, y1 = rect
    return tuple(
        FrameLine(
            line=ln,
            axis_x_pt=x1 - (k + 0.5) * pitch,
            top_pt=y0 + ln.start_slot * advance,
            advance_pt=advance,
            size_pt=size_pt,
        )
        for k, ln in enumerate(lines)
    )


def layout_text_frame(frame, template, grid) -> FramePlacement:
    """單一文字框 → FramePlacement（幾何確定性推導）。

    grid＝框落點頁的主版網格（度量換算比例來源）；每欄容量＝floor(框高／字距)。
    """
    st = _frame_style(frame, template)
    advance, pitch, capacity, max_cols = _frame_metrics(st, frame.rect, grid)
    lines = break_paragraph(frame.text, capacity, indent=0, vertical=True)
    violations: list = []
    if len(lines) > max_cols:
        dropped = sum(sum(c.width for c in ln.cells) for ln in lines[max_cols:])
        violations.append(
            f"文字框（頁 {frame.page}）溢出：{len(lines)} 欄超出框寬容量 "
            f"{max_cols} 欄，末 {dropped} 槽未繪"
        )
        lines = lines[:max_cols]
    return FramePlacement(style=frame.style, lines=_place_lines(
        lines, frame.rect, advance, pitch, st.size_pt), violations=violations)


def layout_thread(frames, template, grids) -> list:
    """串接鏈（同 thread 框依文件序）→ 逐框 FramePlacement（Sprint 57）。

    鏈文字（掛鏈首）一次 tokenize 成 cells；逐框以該框頁網格斷行剩餘 cells、
    取前「欄數容量」欄（行邊界禁則已解消＝合法切點），以已消費 cell 數切出
    剩餘續排下一框；中間框排滿即續流，鏈尾仍剩列違規（不沉默）。
    grids＝逐框落點頁的主版網格（跨頁串接各依其頁換算）。
    """
    head = frames[0]
    st = _frame_style(head, template)
    cells = tokenize(normalize(head.text), vertical=True)
    placements: list = []
    for tf, grid in zip(frames, grids):
        advance, pitch, capacity, max_cols = _frame_metrics(st, tf.rect, grid)
        taken = break_cells(cells, capacity, indent=0)[:max_cols]
        cells = cells[sum(len(ln.cells) for ln in taken):]
        placements.append(FramePlacement(style=head.style, lines=_place_lines(
            taken, tf.rect, advance, pitch, st.size_pt), violations=[]))
    if cells:
        dropped = sum(c.width for c in cells)
        tail = placements[-1]
        placements[-1] = FramePlacement(style=tail.style, lines=tail.lines, violations=[
            f"文字框串接（thread「{head.thread}」）溢出：末框（頁 {frames[-1].page}）"
            f"後剩 {dropped} 槽未繪"
        ])
    return placements


def resolve_text_frames(doc, template, masters_by_page: dict) -> dict:
    """把 doc.text_frames 解析為 {版面頁號: (FramePlacement, ...)}，供兩後端共用。

    框頁超出排版頁數（不在 masters_by_page）→ 快速失敗（同 images 規則，
    不為框造頁）；grid 取該頁主版網格（節式主版指派，Sprint 51）。
    thread 鏈框依鏈序統一佈局（layout_thread）後放回各自頁；頁內繪製序＝
    文件序（同 rect 圖慣例，Sprint 54）。
    """
    ordered: list = []   # (文件序, 頁, placement)
    chains: dict = {}    # thread → [(文件序, frame), ...]（dict 保插入序＝文件序）
    for i, tf in enumerate(doc.text_frames):
        if tf.page not in masters_by_page:
            raise ValueError(
                f"文字框 page {tf.page} 超出排版頁數（共 {len(masters_by_page)} 頁）"
            )
        if tf.thread is None:
            grid = masters_by_page[tf.page].grid
            ordered.append((i, tf.page, layout_text_frame(tf, template, grid)))
        else:
            chains.setdefault(tf.thread, []).append((i, tf))
    for members in chains.values():
        placements = layout_thread(
            [tf for _, tf in members], template,
            [masters_by_page[tf.page].grid for _, tf in members])
        ordered.extend(
            (i, tf.page, pl) for (i, tf), pl in zip(members, placements))
    out: dict = {}
    for _, page, pl in sorted(ordered, key=lambda t: t[0]):
        out.setdefault(page, []).append(pl)
    return {page: tuple(pls) for page, pls in out.items()}
