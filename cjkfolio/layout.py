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


@dataclass(frozen=True)
class LayoutPage:
    number: int  # 1 起算；奇數＝右頁
    placed: tuple


@dataclass(frozen=True)
class LayoutResult:
    pages: tuple
    violations: list  # 禁則違規訊息（runtime 檢查，應為空）


def layout_document(doc, template: Template, first_para_continues: bool = False) -> LayoutResult:
    master = template.masters[doc.master]
    grid = master.grid
    specs = []
    for p in doc.paragraphs:
        if p.style not in template.paragraph_styles:
            raise KeyError(f"文件引用未知段落樣式：{p.style}")
        st = template.paragraph_styles[p.style]
        specs.append(
            ParagraphSpec(
                text=p.text,
                style=p.style,
                indent=st.indent_chars,
                gap_after=st.para_gap_slots,
                chars_per_line=style_line_capacity(st, grid),
                line_slots=style_line_slots(st, grid),
            )
        )
    raw_pages = flow_pages(
        specs, grid.chars_per_line, grid.lines_per_page,
        first_para_continues=first_para_continues,
    )
    pages = tuple(LayoutPage(i + 1, tuple(page)) for i, page in enumerate(raw_pages))
    violations = check_kinsoku([pl.line for page in pages for pl in page.placed])
    return LayoutResult(pages=pages, violations=violations)
