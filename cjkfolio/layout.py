"""樣式驅動流排：文件＋模版 → 分頁的 PlacedLine（幾何一律確定性推導）。

樣式級數換算規則（v1，記入決議紀錄）：
- 字距 = 級數 × (網格字距 / 網格基準級數)，即與內文同比例（實測 12.08/11.5）。
- 行容量 = floor(欄高 / 該樣式字距)，欄高 = 網格滿行字數 × 網格字距。
- 行槽寬 = ceil(級數 / 行距)，級數不超過行距時仍佔 1 槽。
"""
from dataclasses import dataclass, field
from math import ceil, floor

from .engine import ParagraphSpec, check_kinsoku, flow_pages
from .primitives import PT_PER_MM
from .styles import Grid, ParagraphStyle, Template

_EPS = 1e-6

VERTICAL_MODE = "vertical-rl"
HORIZONTAL_MODE = "horizontal-tb"
WRITING_MODES = (VERTICAL_MODE, HORIZONTAL_MODE)


def page_is_vertical(doc, template: Template) -> bool:
    """由文件實際引用的段落樣式判定頁面書寫方向（v1：全文件單一方向）。

    混用 vertical-rl 與 horizontal-tb（版面軸不同、slot 幾何不相容）快速失敗；
    未知 writing_mode 亦快速失敗（系統邊界驗證）。
    """
    modes = []
    for p in doc.paragraphs:
        st = template.paragraph_styles.get(p.style)
        if st is None:
            continue  # 未知樣式由 layout_document 另行 raise
        if st.writing_mode not in WRITING_MODES:
            raise ValueError(
                f"樣式「{st.name}」writing_mode={st.writing_mode!r} 非法，"
                f"支援 {WRITING_MODES}"
            )
        if st.writing_mode not in modes:
            modes.append(st.writing_mode)
    if len(modes) > 1:
        raise ValueError(
            f"v1 不支援單一文件混用書寫方向（本文件含 {modes}）；"
            "橫排頁（版權頁）與直排內文請分屬不同文件"
        )
    return modes[0] != HORIZONTAL_MODE if modes else True


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
class TocEntryMark:
    """目錄條目記號（頁碼＋引導線，top-down pt；x＝行軸由後端以 slot 求）。

    幾何（PLAN §1、p003 一手量測）：頁碼直排逐位直立、底錨 toc.page_no_bottom_pt；
    引導線為行軸垂直實線，自標題末＋gap 至頁碼頂−gap。leader_y1 ≤ leader_y0 時
    後端不畫線（重疊守護，違規訊息由 layout 列入 violations 不沉默）。
    """
    slot: int              # 段末行行槽（行軸鍵）
    line_slots: int        # 該行佔的行槽數（行軸置中用，同 body）
    digits: str
    digit_size_pt: float
    digit_advance_pt: float
    page_no_top_pt: float  # 首位數字槽頂
    leader_y0_pt: float    # 引導線起（標題末＋gap）
    leader_y1_pt: float    # 引導線終（頁碼頂−gap）
    char_style: str        # 頁碼字元樣式名


@dataclass(frozen=True)
class RuleBreak:
    """穿線行（行首字頂高於主版虛線 y）＝虛線斷開處（Sprint 21，篇名嵌線）。

    x 由後端以 slot 求（render.rule_break_ranges，同 TocEntryMark 的行軸模式）；
    判定純幾何（非樣式白名單）：「嵌線」本義即字穿線。
    """
    slot: int        # 穿線行行槽（行軸鍵）
    line_slots: int  # 該行佔的行槽數（行槽範圍推導用）


@dataclass(frozen=True)
class LayoutResult:
    pages: tuple
    violations: list  # 禁則違規訊息（runtime 檢查，應為空）
    justify_stats: dict  # {"squeezed": n, "stretched": n, "beyond": n}
    vertical: bool = True  # 頁面書寫方向（False＝橫排 horizontal-tb）
    toc_marks: dict = field(default_factory=dict)  # page number → (TocEntryMark, ...)
    rule_breaks: dict = field(default_factory=dict)  # page number → (RuleBreak, ...)


def _toc_marks(pages, template: Template, master) -> tuple:
    """依段末行的 page_no 產出 TocEntryMark（幾何確定性推導）。

    回傳 ({page_number: (mark, ...)}, [違規訊息])；帶 page_no 但主版無 toc 配置
    時快速失敗（系統邊界）。
    """
    marks: dict = {}
    violations: list = []
    grid = master.grid
    top_pt = master.margins.top_mm * PT_PER_MM
    for page in pages:
        for pl in page.placed:
            if not pl.page_no:
                continue
            toc = master.toc
            if toc is None:
                raise ValueError(
                    f"段落帶 page_no（{pl.page_no}）但主版「{master.name}」無 toc 配置"
                )
            entry_style = template.paragraph_styles[pl.style]
            cstyle = template.character_styles[toc.page_no_style]
            adv = style_advance_pt(entry_style, grid)
            digit_adv = style_advance_pt(cstyle, grid)
            used = sum(c.width for c in pl.line.cells)
            title_end = top_pt + (pl.line.start_slot + used) * adv
            page_no_top = toc.page_no_bottom_pt - len(pl.page_no) * digit_adv
            mark = TocEntryMark(
                slot=pl.slot,
                line_slots=style_line_slots(entry_style, grid),
                digits=pl.page_no,
                digit_size_pt=cstyle.size_pt,
                digit_advance_pt=digit_adv,
                page_no_top_pt=page_no_top,
                leader_y0_pt=title_end + toc.leader_gap_pt,
                leader_y1_pt=page_no_top - toc.leader_gap_pt,
                char_style=toc.page_no_style,
            )
            if mark.leader_y1_pt <= mark.leader_y0_pt:
                violations.append(
                    f"目錄頁碼：頁 {page.number} 條目（…{pl.line.cells[-1].text}）標題"
                    f"與頁碼區重疊（引導線長 ≤0，不畫線）"
                )
            marks.setdefault(page.number, []).append(mark)
    return {n: tuple(ms) for n, ms in marks.items()}, violations


def _rule_breaks(pages, template: Template, master) -> dict:
    """穿線行（行首字頂 y 高於虛線 y）→ RuleBreak（篇名嵌線斷開，Sprint 21）。

    行首字頂 y＝天頭＋start_slot×字距（縮排偏移維持網格字距，同 render 幾何）；
    head_offset 縮退已含在 start_slot 內。無 rule 配置的主版回空。
    """
    if master.rule is None:
        return {}
    grid = master.grid
    top_pt = master.margins.top_mm * PT_PER_MM
    breaks: dict = {}
    for page in pages:
        for pl in page.placed:
            style = template.paragraph_styles[pl.style]
            line_top = top_pt + pl.line.start_slot * style_advance_pt(style, grid)
            if line_top < master.rule.y_from_top_pt - _EPS:
                breaks.setdefault(page.number, []).append(
                    RuleBreak(slot=pl.slot, line_slots=style_line_slots(style, grid))
                )
    return {n: tuple(bs) for n, bs in breaks.items()}


def layout_document(doc, template: Template, first_para_continues: bool = False) -> LayoutResult:
    master = template.masters[doc.master]
    grid = master.grid
    vertical = page_is_vertical(doc, template)
    specs = []
    for i, p in enumerate(doc.paragraphs):
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
                page_no=p.page_no,
                para_idx=i,
                head_offset=st.head_offset_chars,
                lead_offset_pt=st.lead_offset_pt,
            )
        )
    raw_pages = flow_pages(
        specs, grid.chars_per_line, grid.lines_per_page,
        first_para_continues=first_para_continues, vertical=vertical,
    )
    pages = tuple(LayoutPage(i + 1, tuple(page)) for i, page in enumerate(raw_pages))
    violations = check_kinsoku([pl.line for page in pages for pl in page.placed])
    toc_marks, toc_violations = _toc_marks(pages, template, master)
    violations += toc_violations
    rule_breaks = _rule_breaks(pages, template, master) if vertical else {}
    stats = {"squeezed": 0, "stretched": 0, "beyond": 0}
    if vertical:  # 齊行為直排內文特徵；橫排版權頁短行左齊、不字距縮放
        for page in pages:
            for pl in page.placed:
                _, status = line_justified_advance(pl.line, 1.0)
                if status in stats:
                    stats[status] += 1
    return LayoutResult(pages=pages, violations=violations, justify_stats=stats,
                        vertical=vertical, toc_marks=toc_marks,
                        rule_breaks=rule_breaks)
