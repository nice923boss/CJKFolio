"""樣式驅動流排：文件＋模版 → 分頁的 PlacedLine（幾何一律確定性推導）。

樣式級數換算規則（v1，記入決議紀錄）：
- 字距 = 級數 × (網格字距 / 網格基準級數)，即與內文同比例（實測 12.08/11.5）。
- 行容量 = floor(欄高 / 該樣式字距)，欄高 = 網格滿行字數 × 網格字距。
- 行槽寬 = ceil(級數 / 行距)，級數不超過行距時仍佔 1 槽。
"""
from dataclasses import dataclass
from math import ceil, floor

from .engine import ParagraphSpec, check_kinsoku, flow_pages
from .styles import Grid, ParagraphStyle, Template

_EPS = 1e-6


def style_advance_pt(style: ParagraphStyle, grid: Grid) -> float:
    return style.size_pt * (grid.char_advance_pt / grid.base_size_pt)


def style_line_capacity(style: ParagraphStyle, grid: Grid) -> int:
    column_height = grid.chars_per_line * grid.char_advance_pt
    return max(1, floor(column_height / style_advance_pt(style, grid) + _EPS))


def style_line_slots(style: ParagraphStyle, grid: Grid) -> int:
    return max(1, ceil(style.size_pt / grid.line_pitch_pt - _EPS))


JUSTIFY_TOLERANCE_SLOTS = 2  # 齊行容忍（槽）：偏差超過維持等距網格（列入統計不沉默）


def line_justified_advance(line, advance_pt: float):
    """非段末行的齊行實效字距（行首行尾雙錨定，字距均勻縮放）。

    回傳 (advance_pt', status)，status ∈ {"grid","squeezed","stretched","beyond"}；
    grid＝不調整（滿行、段末行或無容量資訊），beyond＝偏差超容忍維持網格。
    """
    used = sum(c.width for c in line.cells)
    if line.para_end or line.cap <= 0 or used <= 0 or used == line.cap:
        return advance_pt, "grid"
    if abs(used - line.cap) > JUSTIFY_TOLERANCE_SLOTS:
        return advance_pt, "beyond"
    status = "squeezed" if used > line.cap else "stretched"
    return advance_pt * line.cap / used, status


@dataclass(frozen=True)
class LayoutPage:
    number: int  # 1 起算；奇數＝右頁
    placed: tuple


@dataclass(frozen=True)
class LayoutResult:
    pages: tuple
    violations: list  # 禁則違規訊息（runtime 檢查，應為空）
    justify_stats: dict  # {"squeezed": n, "stretched": n, "beyond": n}


def layout_document(doc, template: Template, first_para_continues: bool = False) -> LayoutResult:
    master = template.masters[doc.master]
    grid = master.grid
    specs = []
    for p in doc.paragraphs:
        if p.style not in template.paragraph_styles:
            raise KeyError(f"文件引用未知段落樣式：{p.style}")
        for r in p.runs:
            if r.char_style and r.char_style not in template.character_styles:
                raise KeyError(f"文件引用未知字元樣式：{r.char_style}")
        st = template.paragraph_styles[p.style]
        specs.append(
            ParagraphSpec(
                text=p.text,
                style=p.style,
                indent=st.indent_chars,
                gap_after=st.para_gap_slots,
                chars_per_line=style_line_capacity(st, grid),
                line_slots=style_line_slots(st, grid),
                runs=tuple((r.text, r.char_style) for r in p.runs),
            )
        )
    raw_pages = flow_pages(
        specs, grid.chars_per_line, grid.lines_per_page,
        first_para_continues=first_para_continues,
    )
    pages = tuple(LayoutPage(i + 1, tuple(page)) for i, page in enumerate(raw_pages))
    violations = check_kinsoku([pl.line for page in pages for pl in page.placed])
    stats = {"squeezed": 0, "stretched": 0, "beyond": 0}
    for page in pages:
        for pl in page.placed:
            _, status = line_justified_advance(pl.line, 1.0)
            if status in stats:
                stats[status] += 1
    return LayoutResult(pages=pages, violations=violations, justify_stats=stats)
