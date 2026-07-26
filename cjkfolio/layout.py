"""樣式驅動流排：文件＋模版 → 分頁的 PlacedLine（幾何一律確定性推導）。

樣式級數換算規則（v1，記入決議紀錄）：
- 字距 = 級數 × (網格字距 / 網格基準級數)，即與內文同比例（實測 12.08/11.5）。
- 行容量 = floor(欄高 / 該樣式字距)，欄高 = 網格滿行字數 × 網格字距。
- 行槽寬 = ceil(級數 / 行距)，級數不超過行距時仍佔 1 槽。
"""
from dataclasses import dataclass, field
from math import ceil, floor

from .engine import ParagraphSpec, check_kinsoku, check_overflow, flow_pages
from .primitives import PT_PER_MM
from .styles import Grid, ParagraphStyle, Template

_EPS = 1e-6

VERTICAL_MODE = "vertical-rl"
HORIZONTAL_MODE = "horizontal-tb"
WRITING_MODES = (VERTICAL_MODE, HORIZONTAL_MODE)


def _direction_modes(paragraphs, template: Template) -> list:
    """收集段落樣式的書寫方向（去重、保序）；未知 writing_mode 快速失敗。"""
    modes = []
    for p in paragraphs:
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
    return modes


def page_is_vertical(doc, template: Template) -> bool:
    """整份文件單一書寫方向判定（相容 util）：混向即快速失敗。

    節式逐頁方向（直排內文＋橫排版權頁同冊，Sprint 53）由 layout_document
    逐節判定並掛 LayoutPage.vertical，不經此函式。
    """
    modes = _direction_modes(doc.paragraphs, template)
    if len(modes) > 1:
        raise ValueError(
            f"v1 不支援單一文件混用書寫方向（本文件含 {modes}）；"
            "橫排頁（版權頁）與直排內文請分屬不同文件"
        )
    return modes[0] != HORIZONTAL_MODE if modes else True


def _section_is_vertical(paragraphs, template: Template, master_name: str) -> bool:
    """一節的書寫方向：同節混用（版面軸不同、slot 幾何不相容）快速失敗。"""
    modes = _direction_modes(paragraphs, template)
    if len(modes) > 1:
        raise ValueError(
            f"不支援同一節混用書寫方向（節「{master_name}」含 {modes}）；"
            "橫排頁（版權頁）與直排內文請以節首標記（Paragraph.master）分節"
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


def ruby_group_height(cells, index: int, advance_pt: float) -> float:
    """ruby 群組（自 cells[index] 起 ruby_span 個 cell）的總高（pt）。

    兩後端共用（Sprint 134 group ruby）：ruby 於此高度上垂直置中
    （placement.group_ruby_axis_and_top）。span 為 0 或 1 時退化為單一字槽高，
    即 v1 mono-ruby 的幾何。
    """
    span = cells[index].ruby_span or 1
    return sum(c.width for c in cells[index:index + span]) * advance_pt


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
    number: int  # 1 起算（版面頁號；書頁號另計）
    placed: tuple
    master: str = ""  # 本頁主版名（節式主版指派，Sprint 51；layout_document 必填）
    vertical: bool = True  # 本頁書寫方向（節式混向，Sprint 53；False＝橫排 horizontal-tb）
    # 裝訂補頁（Sprint 144）：為湊足 doc.sheet_pages 的倍數而補的空白頁。
    # 不編頁碼、不印書眉（同封面），主版裝飾亦因 placed 為空而不繪。
    blank: bool = False


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
    vertical: bool = True  # 首節方向（相容欄位）；逐頁方向以 LayoutPage.vertical 為準（Sprint 53）
    toc_marks: dict = field(default_factory=dict)  # page number → (TocEntryMark, ...)
    rule_breaks: dict = field(default_factory=dict)  # page number → (RuleBreak, ...)
    # 封面佔的版面頁數（Sprint 132）：0＝無封面。下游書頁號一律以此位移
    # （primitives.book_number_for），使頁碼自封面翻開後起算。
    cover_pages: int = 0


def _toc_marks(pages, template: Template) -> tuple:
    """依段末行的 page_no 產出 TocEntryMark（幾何確定性推導，逐頁主版）。

    回傳 ({page_number: (mark, ...)}, [違規訊息])；帶 page_no 但該頁主版無 toc
    配置時快速失敗（系統邊界）。
    """
    marks: dict = {}
    violations: list = []
    for page in pages:
        master = template.masters[page.master]
        grid = master.grid
        top_pt = master.margins.top_mm * PT_PER_MM
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
            # 標題末隨條目 body 的 lead_offset_pt 同步偏移（Sprint 30；body inline-start
            # 已含 lead_offset），引導線起點 leader_y0 因而跟隨；頁碼底錨 page_no_top 為
            # 頁面固定列（所有條目頁碼底對齊），不隨條目位置微調。
            title_end = top_pt + (pl.line.start_slot + used) * adv + pl.lead_offset_pt
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


def _rule_breaks(pages, template: Template) -> dict:
    """穿線行（行首字頂 y 高於虛線 y）→ RuleBreak（篇名嵌線斷開，Sprint 21）。

    行首字頂 y＝天頭＋start_slot×字距（縮排偏移維持網格字距，同 render 幾何）；
    head_offset 縮退已含在 start_slot 內。逐頁主版；無 rule 配置的頁回空。
    """
    breaks: dict = {}
    for page in pages:
        master = template.masters[page.master]
        if not page.vertical or master.rule is None:  # rule 為直排目錄原件
            continue
        grid = master.grid
        top_pt = master.margins.top_mm * PT_PER_MM
        for pl in page.placed:
            style = template.paragraph_styles[pl.style]
            # 穿線判定跟隨 body 實際位置：行首字頂含 lead_offset_pt（Sprint 30），
            # 條目下移／上移後穿線與否與 body inline-start 同步，不失步。
            line_top = top_pt + pl.line.start_slot * style_advance_pt(style, grid) + pl.lead_offset_pt
            if line_top < master.rule.y_from_top_pt - _EPS:
                breaks.setdefault(page.number, []).append(
                    RuleBreak(slot=pl.slot, line_slots=style_line_slots(style, grid))
                )
    return {n: tuple(bs) for n, bs in breaks.items()}


def _sections(doc) -> list:
    """依 Paragraph.master 節首標記切節：回傳 [(master_name, lo, hi), ...]（半開段區間）。

    節式主版指派（Sprint 51）：段帶 master＝自該段起新頁並改用該主版（同名亦分頁）；
    首節（無標記前的段落）用 doc.master。段 0 帶 master 時直接蓋過預設（無空首節）。
    """
    sections: list = []
    start, current = 0, doc.master
    for i, p in enumerate(doc.paragraphs):
        if p.master is None:
            continue
        if i > start:
            sections.append((current, start, i))
        start, current = i, p.master
    sections.append((current, start, len(doc.paragraphs)))
    return sections


def layout_document(doc, template: Template, first_para_continues: bool = False,
                    exclusions=None) -> LayoutResult:
    """流排文件為分頁 LayoutPage。

    exclusions＝{版面頁號: (engine.Exclusion, ...)} 圖文繞排排除區（Sprint 89，
    選配）：由 wrap.layout_with_wrap 於第二趟傳入（換算需先知逐頁主版），
    layout 只負責把節內頁序換算為版面頁號（page_offset）後轉交 flow_pages。
    """
    pages: list = []
    cover_pages = 0
    if doc.cover is not None:  # 封面＝版面頁 1 的空流排頁（Sprint 132）
        if doc.cover not in template.masters:
            raise KeyError(f"文件引用未知封面主版：{doc.cover}")
        # 方向取直排（本產品利基）：封面不吃內文流，兩後端 body 繪製對空 placed
        # 皆為空迴圈，故此欄位對封面頁的輸出無影響。
        pages.append(LayoutPage(1, (), master=doc.cover, vertical=True))
        cover_pages = 1
    for si, (master_name, lo, hi) in enumerate(_sections(doc)):
        if master_name not in template.masters:
            raise KeyError(f"文件引用未知主版：{master_name}")
        vertical = _section_is_vertical(doc.paragraphs[lo:hi], template, master_name)
        grid = template.masters[master_name].grid
        specs = []
        for i in range(lo, hi):
            p = doc.paragraphs[i]
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
                    runs=tuple((r.text, r.char_style, r.ruby) for r in p.runs),
                    page_no=p.page_no,
                    para_idx=i,
                    head_offset=st.head_offset_chars,
                    lead_offset_pt=st.lead_offset_pt,
                    advance_pt=style_advance_pt(st, grid),
                    punct_squeeze=st.punct_squeeze,
                    line_end_squeeze=st.line_end_squeeze,
                    line_head_squeeze=st.line_head_squeeze,
                )
            )
        # 每節獨立流排（節首＝強制起新頁）；頁號跨節連續。節間段後空槽自然歸零
        # （承「段後空槽跨頁歸零」慣例）；first_para_continues 僅首節有意義。
        raw_pages = flow_pages(
            specs, grid.chars_per_line, grid.lines_per_page,
            first_para_continues=first_para_continues and si == 0, vertical=vertical,
            exclusions=exclusions, page_offset=len(pages),
        )
        for page in raw_pages:
            pages.append(LayoutPage(len(pages) + 1, tuple(page), master=master_name,
                                    vertical=vertical))
    # 裝訂補頁（Sprint 144）：真實書冊以對折紙成帖，內文頁數非 doc.sheet_pages 的倍數
    # 就湊不成整數張紙，故於末尾補空白頁。封面不計（封面另計紙張，要成帖的是內文那疊）；
    # 補頁承末頁主版與方向，空 placed 使兩後端的主版裝飾（rule／frame／figure，皆帶
    # `and page.placed`）自然不繪，頁碼與書眉另由 blank 旗標抑制。
    unit = doc.sheet_pages or 0
    if unit > 1 and len(pages) > cover_pages:
        for _ in range(-(len(pages) - cover_pages) % unit):
            last = pages[-1]
            pages.append(LayoutPage(len(pages) + 1, (), master=last.master,
                                    vertical=last.vertical, blank=True))
    pages = tuple(pages)
    all_lines = [pl.line for page in pages for pl in page.placed]
    violations = check_kinsoku(all_lines)
    # 溢出偵測（Sprint 111）：超寬 cell 撐爆行時據實回報，不再沉默溢出版心
    violations += check_overflow(all_lines)
    toc_marks, toc_violations = _toc_marks(pages, template)
    violations += toc_violations
    rule_breaks = _rule_breaks(pages, template)
    stats = {"squeezed": 0, "stretched": 0, "beyond": 0}
    for page in pages:
        if not page.vertical:  # 齊行為直排內文特徵；橫排版權頁短行左齊、不字距縮放
            continue
        for pl in page.placed:
            _, status = line_justified_advance(pl.line, 1.0)
            if status in stats:
                stats[status] += 1
    body_pages = pages[cover_pages:]  # 首節方向取首個內文頁（封面無內文流不代表方向）
    return LayoutResult(pages=pages, violations=violations, justify_stats=stats,
                        vertical=body_pages[0].vertical if body_pages else True,
                        toc_marks=toc_marks, rule_breaks=rule_breaks,
                        cover_pages=cover_pages)
