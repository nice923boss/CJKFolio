"""直排版面引擎核心：正規化、斷行、禁則、頁面流排（Phase 1 產品層）。

自 Spike 1（spikes/spike1-vertical-core/vertical_engine.py）產品化：
斷行與禁則規則不變，flow_pages 改以 ParagraphSpec 承載樣式驅動的
每段行容量（大級數標題行高換算）、縮排、段後空槽與行槽寬。

純邏輯層，不碰字型與渲染。規則依據 W3C CLREQ（繁中）：
- 行首禁則：句逗號、閉引號括號等不得落行首。優先「擠入」本行行尾（行寬容忍
  溢出，Sprint 11 依參考書 −0.4pt 齊行實測）；連續句逗超過擠入上限時改「追出」
  （錨字連同整串句逗下移，本行由齊行撐開）。
- 行尾禁則：開引號括號不得懸行尾，退至下一行。
- 縱中橫：1〜2 位數字（可帶列標記尾點「1.」）與全大寫縮寫逐字直立橫排（tcy）；
  含小寫的西文詞、3 位以上數字、小數旋轉 90 度（latin），串不拆（Sprint 88 精修，
  規則對表真書 179 頁全掃）。
- Line 帶 cap（該行內容容量）與 para_end（段末行），供 layout 層齊行
  （非段末行行首行尾雙錨定，字距均勻縮放）。
"""
import re
import unicodedata
from dataclasses import dataclass, replace
from math import ceil, floor
from typing import Optional

_EPS = 1e-6

# CLREQ 繁中行首禁則（不得出現在行首）
LINE_START_FORBIDDEN = set("，。、：；！？」』）〕》〉｝〗…‥·．％")
# 行尾禁則（不得懸在行尾）
LINE_END_FORBIDDEN = set("「『（〔《〈｛〖")

# 走縱中橫的數字串：1〜2 位數字，可帶列標記尾點（真書 p10「1.」「2.」「3.」）
_TCY_NUMERIC = re.compile(r"\d{1,2}\.?")

# 行首禁則擠入上限（槽）：整串句逗溢出超過此值改追出（參考書實測 ±0.4pt
# 對應 ±1 槽；連續兩句逗跨行為罕見情形，容忍至 2）
MAX_SQUEEZE_SLOTS = 2

# 直排／相容表現形 → 標準形（PDF 抽取常見）
_PRESENTATION_FORMS = {
    "﹁": "「", "﹂": "」", "﹃": "『", "﹄": "』",
    "﹐": "，", "﹑": "、", "﹒": "．", "﹔": "；", "﹕": "：",
    "﹖": "？", "﹗": "！", "﹙": "（", "﹚": "）", "﹛": "｛",
    "﹜": "｝", "﹝": "〔", "﹞": "〕",
    "︐": "，", "︑": "、", "︒": "。", "︓": "：", "︔": "；",
    "︕": "！", "︖": "？", "︙": "…",
    "︵": "（", "︶": "）", "︷": "｛", "︸": "｝",
    "︹": "〔", "︺": "〕", "︽": "《", "︾": "》",
    "︿": "〈", "﹀": "〉", "︻": "【", "︼": "】",
}


@dataclass(frozen=True)
class Cell:
    text: str
    kind: str  # "cjk" | "tcy" | "latin" | "space"
    width: int = 1  # 佔用的直排字槽數
    char_style: Optional[str] = None  # 字元樣式名（run 模型；None＝依段落樣式）
    span: Optional[tuple] = None  # 文件 provenance：來源 text 半開區間 (start, end)。
    # 座標系＝tokenize 輸入 text；經 offsets 映射後＝文件段 text（normalize 前）座標。
    ruby: Optional[str] = None  # 注音／ruby 標注（Sprint 86）：直排繪於字右側置中；
    # 僅單字 base run 的 cjk cell 帶值（不影響 width／斷行禁則）。


@dataclass(frozen=True)
class Line:
    cells: tuple
    start_slot: int = 0  # 段首縮排時 > 0
    cap: int = 0         # 本行內容容量（槽；0＝未知，不齊行）
    para_end: bool = True  # 段末行不齊行


@dataclass(frozen=True)
class ParagraphSpec:
    """一段的流排參數（由樣式層推導，engine 不認識樣式本身）。"""
    text: str
    style: str = "內文"
    indent: int = 2
    gap_after: int = 1  # 段後空槽（最後一段不留）
    chars_per_line: Optional[int] = None  # None → 用頁面預設
    line_slots: int = 1  # 每行佔的行槽數（特大級數標題 > 1）
    runs: Optional[tuple] = None  # ((text, char_style|None), ...)；None → 全段無字元樣式
    page_no: Optional[str] = None  # 目錄條目頁碼（純載體，掛到段末行，不影響斷行禁則）
    para_idx: Optional[int] = None  # 文件段索引（純載體，供畫布反查文件游標）
    head_offset: int = 0  # 段級天頭縮退（槽）：整段每行起始槽位下移（目錄條目縮退）
    lead_offset_pt: float = 0.0  # 段級 inline 軸 sub-slot 偏移（pt）：首字起點微調，不改斷行容量（Sprint 29）
    advance_pt: float = 0.0  # 該樣式字距（pt）：繞排排除區的 pt 區間換算字格用（0＝不繞排）


@dataclass(frozen=True)
class Exclusion:
    """繞排排除區（頁級，已換算為版面座標；Sprint 89）。

    slot_lo／slot_hi：受影響行槽半開區間（行軸）；
    span_lo_pt／span_hi_pt：字軸排除區間（相對天頭 pt，半開）。
    幾何換算（rect → 本結構）在 wrap.py，engine 只做字格裁切（不認識主版與鏡像）。
    """
    slot_lo: int
    slot_hi: int
    span_lo_pt: float
    span_hi_pt: float


def line_window(exclusions, slot: int, line_slots: int, advance_pt: float,
                chars_per_line: int):
    """該行的可用字格半開區間 [start, end)（繞排排除區裁切後）。

    行佔 slot〜slot+line_slots−1，任一行槽與排除區行軸區間重疊即整行受裁切（保守，
    大級數跨槽行不做部分裁切）。排除區把可用區間切成前後兩段，v1 取較長的一段
    （同欄不跨圖續排＝真書 179 頁全掃 8 個繞排樣本的一致形態，Sprint 89 R1）。
    end ≤ start＝該行槽被圖佔滿，呼叫端不於此槽排字。
    """
    start, end = 0, chars_per_line
    if not exclusions or advance_pt <= 0:
        return start, end
    for ex in exclusions:
        if ex.slot_hi <= slot or ex.slot_lo >= slot + line_slots:
            continue
        lo = int(floor(ex.span_lo_pt / advance_pt + _EPS))
        hi = int(ceil(ex.span_hi_pt / advance_pt - _EPS))
        before = (start, min(end, lo))
        after = (max(start, hi), end)
        start, end = (before if max(0, before[1] - before[0])
                      >= max(0, after[1] - after[0]) else after)
        if end < start:
            end = start
    return start, end


@dataclass(frozen=True)
class PlacedLine:
    slot: int
    line: Line
    style: str
    page_no: Optional[str] = None  # 目錄條目頁碼（僅段末行帶值）
    para_idx: Optional[int] = None  # 文件段索引（provenance 載體）
    lead_offset_pt: float = 0.0  # 段級 inline 軸 sub-slot 偏移（pt，純載體，body 定位用）


def normalize_with_offsets(text: str):
    """正規化＋原索引映射：回傳 (normalized, offsets)，offsets[i]＝normalized[i] 的原索引。

    控制字元（Cc）剝除會位移索引，畫布游標映射需要此表；表現形替換為 1:1 不動索引。
    """
    chars: list = []
    offsets: list = []
    for i, ch in enumerate(text):
        # 控制字元（Cc）非排版內容：PDF 抽取素材常殘留（如發言標籤後的 U+0007）
        if unicodedata.category(ch) == "Cc":
            continue
        chars.append(_PRESENTATION_FORMS.get(ch, ch))
        offsets.append(i)
    return "".join(chars), tuple(offsets)


def normalize(text: str) -> str:
    return normalize_with_offsets(text)[0]


def _flush_latin(run: str, out: list, char_style, vertical: bool, offsets,
                 start: int) -> None:
    """西文 run → cells（直排分正立與旋轉；橫排一律 LTR 不轉）。

    直排排法依真書 179 頁全掃（Sprint 88，tools/measure_tcy_spans.py）：
    正立（縱中橫，一枚一槽）＝1〜2 位數字，可帶列標記尾點（「1.」）；全大寫縮寫
    逐字正立（'IKEA' 4 槽、'DM' 2 槽）。其餘旋轉（含小寫的西文詞、3 位以上數字、
    小數「2.0」）。
    """
    if not run:
        return
    end = start + len(run)
    if vertical and _TCY_NUMERIC.fullmatch(run):
        out.append(Cell(run, "tcy", 1, char_style, _span(offsets, start, end)))
    elif vertical and run.isalpha() and run.isupper():
        out.extend(Cell(ch, "tcy", 1, char_style, _span(offsets, i, i + 1))
                   for i, ch in enumerate(run, start))
    else:
        out.append(Cell(run, "latin", max(1, ceil(len(run) * 0.5)), char_style,
                        _span(offsets, start, end)))


def _is_latin_letter(ch: str) -> bool:
    """拉丁字母（含重音變體）：真書把整個西文詞當一串旋轉，重音不得斷詞
    （'Hermès'／'Céline' 各為單一旋轉 span）。全形拉丁不算（維持全形字槽）。"""
    return ch.isalpha() and unicodedata.name(ch, "").startswith("LATIN ")


def _is_run_char(ch: str, vertical: bool) -> bool:
    # 直排：拉丁字母（含重音）、半形數字與句點收成一串（句點須併入才分得出
    # 列標記「1.」與小數「2.0」）。
    # 橫排：整段連續 ascii（含空格、連字號、句點）收成一個 latin run，走自然寬。
    if vertical:
        return _is_latin_letter(ch) or ch == "." or (ch.isascii() and ch.isdigit())
    return ch.isascii()


def _span(offsets, i0: int, i1: int):
    """輸入座標 [i0, i1) → 來源座標半開區間（offsets＝原索引表）。"""
    if i1 <= i0:
        return None
    return (offsets[i0], offsets[i1 - 1] + 1)


def tokenize(text: str, char_style=None, vertical: bool = True, offsets=None) -> list:
    """text → cells，各 cell 帶 span。offsets＝normalize_with_offsets 的原索引表；
    None 時 span 為輸入 text 自身座標（identity）。"""
    if offsets is None:
        offsets = range(len(text))
    cells: list = []
    run = ""
    run_start = 0
    for i, ch in enumerate(text):
        if _is_run_char(ch, vertical):
            if not run:
                run_start = i
            run += ch
            continue
        _flush_latin(run, cells, char_style, vertical, offsets, run_start)
        run = ""
        if ch in (" ", "　"):
            cells.append(Cell(ch, "space", 1, char_style, _span(offsets, i, i + 1)))
        else:
            cells.append(Cell(ch, "cjk", 1, char_style, _span(offsets, i, i + 1)))
    _flush_latin(run, cells, char_style, vertical, offsets, run_start)
    return cells


def cells_from_runs(runs, vertical: bool = True) -> list:
    """run 序列 → cells（各 run 內部正規化＋標注字元樣式；拉丁串不跨 run 合併）。

    span 為文件段 text 座標：run k 的基底＝前 k−1 個 run 的 text 長度和
    （document@2 不變式：段 text＝runs 串接）。
    """
    cells: list = []
    base = 0
    for run in runs:  # run 為 (text, char_style) 或 (text, char_style, ruby)（相容）
        text, char_style = run[0], run[1]
        ruby = run[2] if len(run) > 2 else None
        norm, offs = normalize_with_offsets(text)
        produced = tokenize(norm, char_style, vertical,
                            offsets=tuple(base + o for o in offs))
        if ruby and produced:  # 單字 base（document 已守門）→ ruby 掛該 cell
            produced = [replace(produced[0], ruby=ruby), *produced[1:]]
        cells.extend(produced)
        base += len(text)
    return cells


def break_paragraph(text: str, chars_per_line: int, indent: int = 2,
                    vertical: bool = True) -> list:
    return break_cells(tokenize(normalize(text), vertical=vertical), chars_per_line, indent)


def break_cells(cells: list, chars_per_line: int, indent: int = 2) -> list:
    """cells 級斷行（break_paragraph 的 cells 入口）。

    行序列的 cells 連續無增刪（擠入追出只移動行邊界），且每行行首行尾禁則已
    解消，故任一行邊界皆為合法切點：文字框串接（Sprint 57）據此逐框取欄、
    以已消費 cell 數切出剩餘 cells 續排下一框。
    """
    return _break_cells(cells, chars_per_line, indent)


def _break_cells(cells: list, chars_per_line: int, indent: int = 2,
                 head: int = 0) -> list:
    lines: list = []
    idx = 0
    start = head + indent  # head＝段級天頭縮退（每行）；indent 只疊段首行
    while idx < len(cells):
        cap = chars_per_line - start
        line, idx = _break_one_line(cells, idx, cap)
        lines.append(Line(tuple(line), start, cap=cap, para_end=False))
        start = head
    if lines:
        last = lines[-1]
        lines[-1] = Line(last.cells, last.start_slot, cap=last.cap, para_end=True)
    return lines


def _break_one_line(cells: list, idx: int, cap: int):
    """自 idx 起斷出一行（禁則解消後），回傳 (line_cells, new_idx)。

    斷行與流排共用（繞排逐行流排每行容量不同，Sprint 89）：任一行邊界皆為合法
    切點，故逐行取用與整段一次斷行等價。
    """
    line: list = []
    used = 0
    while idx < len(cells) and used + cells[idx].width <= cap:
        line.append(cells[idx])
        used += cells[idx].width
        idx += 1
    # 禁則解消（迭代至穩定；每輪或推進 idx、或縮短 line，必然終止）
    while True:
        # 行尾禁則：開括弧不懸行尾（後面還有字才需處理）
        if line and idx < len(cells) and line[-1].text in LINE_END_FORBIDDEN:
            idx -= 1
            used -= line[-1].width
            line.pop()
            continue
        # 行首禁則：整串句逗一次決策，擠入或追出
        if line and idx < len(cells) and cells[idx].text in LINE_START_FORBIDDEN:
            run_w, j = 0, idx
            while j < len(cells) and cells[j].text in LINE_START_FORBIDDEN:
                run_w += cells[j].width
                j += 1
            if used + run_w - cap <= MAX_SQUEEZE_SLOTS or len(line) <= 1:
                while idx < j:  # 擠入：句逗掛本行行尾，齊行負調整
                    line.append(cells[idx])
                    used += cells[idx].width
                    idx += 1
            else:  # 追出：退到非禁則錨字，錨字連同整串句逗下移
                while len(line) > 1 and line[-1].text in LINE_START_FORBIDDEN:
                    idx -= 1
                    used -= line[-1].width
                    line.pop()
                if len(line) > 1:
                    idx -= 1
                    used -= line[-1].width
                    line.pop()
            continue
        break
    if not line:  # 病理情形防護：強制收一字避免死循環
        line.append(cells[idx])
        idx += 1
    return line, idx


def check_kinsoku(lines) -> list:
    violations = []
    for i, line in enumerate(lines):
        if not line.cells:
            continue
        head, tail = line.cells[0], line.cells[-1]
        if head.text in LINE_START_FORBIDDEN:
            violations.append(f"行 {i + 1} 行首禁則違規：{head.text!r}")
        if tail.text in LINE_END_FORBIDDEN:
            violations.append(f"行 {i + 1} 行尾禁則違規：{tail.text!r}")
    return violations


def flow_pages(
    specs,
    chars_per_line: int,
    slots_per_page: int,
    first_para_continues: bool = False,
    vertical: bool = True,
    exclusions=None,
    page_offset: int = 0,
) -> list:
    """把 ParagraphSpec 序列流排成頁。

    回傳 pages，每頁為 [PlacedLine, ...]，行槽起算為 0（直排右起、橫排上起）。
    段後空槽跨頁時歸零（不帶進次頁），與參考書實測一致。
    斷行與禁則規則與方向無關；vertical 只決定 tokenize（橫排不轉縱中橫）。

    繞排（Sprint 89）：exclusions＝{版面頁號: (Exclusion, ...)}，逐行以 line_window
    取該行槽的可用字格區間（行首推移或行尾縮短），故斷行改逐行取用（行邊界皆為
    合法切點，與整段一次斷行等價）。page_offset＝本次流排前已產生的頁數（節式
    多節流排時把節內頁序換算為版面頁號）。無 exclusions 時行為與既有一致。
    """
    pages: list = []
    cur: list = []
    slot = 0

    def page_exclusions():
        return exclusions.get(page_offset + len(pages) + 1, ()) if exclusions else ()

    for pi, spec in enumerate(specs):
        indent = 0 if (pi == 0 and first_para_continues) else spec.indent
        cap = spec.chars_per_line if spec.chars_per_line else chars_per_line
        if spec.runs:
            cells = cells_from_runs(spec.runs, vertical)
        else:
            norm, offs = normalize_with_offsets(spec.text)
            cells = tokenize(norm, vertical=vertical, offsets=offs)
        idx = 0
        start = spec.head_offset + indent  # head＝段級天頭縮退（每行）；indent 只疊段首行
        blocked = 0  # 本頁因繞排跳過的行槽數（整頁排不下任何行＝配置錯誤，快速失敗）
        while idx < len(cells):
            if slot + spec.line_slots > slots_per_page:
                if blocked and not cur:
                    raise ValueError(
                        f"繞排排除區覆蓋版面頁 {page_offset + len(pages) + 1} 全部行槽，"
                        "無處排字（請縮小圖框或 wrap_margin）"
                    )
                pages.append(cur)
                cur = []
                slot = 0
                blocked = 0
            win_lo, win_hi = line_window(page_exclusions(), slot, spec.line_slots,
                                         spec.advance_pt, cap)
            line_start = max(start, win_lo)
            line_cap = win_hi - line_start
            if line_cap <= 0:  # 本行槽被排除區佔滿：留白，續下一行槽
                slot += spec.line_slots
                blocked += spec.line_slots
                continue
            line_cells, idx = _break_one_line(cells, idx, line_cap)
            line = Line(tuple(line_cells), line_start, cap=line_cap,
                        para_end=idx >= len(cells))
            cur.append(PlacedLine(slot, line, spec.style,
                                  page_no=spec.page_no if line.para_end else None,
                                  para_idx=spec.para_idx,
                                  lead_offset_pt=spec.lead_offset_pt))
            slot += spec.line_slots
            start = spec.head_offset
        if pi < len(specs) - 1:
            slot += spec.gap_after
            if slot >= slots_per_page:
                pages.append(cur)
                cur = []
                slot = 0
    if cur:
        pages.append(cur)
    return pages
