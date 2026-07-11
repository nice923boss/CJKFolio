"""直排版面引擎核心：正規化、斷行、禁則、頁面流排（Phase 1 產品層）。

自 Spike 1（spikes/spike1-vertical-core/vertical_engine.py）產品化：
斷行與禁則規則不變，flow_pages 改以 ParagraphSpec 承載樣式驅動的
每段行容量（大級數標題行高換算）、縮排、段後空槽與行槽寬。

純邏輯層，不碰字型與渲染。規則依據 W3C CLREQ（繁中）：
- 行首禁則：句逗號、閉引號括號等不得落行首。優先「擠入」本行行尾（行寬容忍
  溢出，Sprint 11 依參考書 −0.4pt 齊行實測）；連續句逗超過擠入上限時改「追出」
  （錨字連同整串句逗下移，本行由齊行撐開）。
- 行尾禁則：開引號括號不得懸行尾，退至下一行。
- 縱中橫：1〜2 位數字直立橫排（tcy）；3 位以上數字與拉丁串旋轉 90 度（latin），串不拆。
- Line 帶 cap（該行內容容量）與 para_end（段末行），供 layout 層齊行
  （非段末行行首行尾雙錨定，字距均勻縮放）。
"""
import unicodedata
from dataclasses import dataclass
from math import ceil
from typing import Optional

# CLREQ 繁中行首禁則（不得出現在行首）
LINE_START_FORBIDDEN = set("，。、：；！？」』）〕》〉｝〗…‥·．％")
# 行尾禁則（不得懸在行尾）
LINE_END_FORBIDDEN = set("「『（〔《〈｛〖")

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


@dataclass(frozen=True)
class PlacedLine:
    slot: int
    line: Line
    style: str
    page_no: Optional[str] = None  # 目錄條目頁碼（僅段末行帶值）
    para_idx: Optional[int] = None  # 文件段索引（provenance 載體）


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


def _flush_ascii(run: str, out: list, char_style=None, vertical: bool = True,
                 span=None) -> None:
    if not run:
        return
    # 直排：1〜2 位數字走縱中橫（tcy）；橫排數字/拉丁一律正常 LTR，不轉。
    if vertical and run.isdigit() and len(run) <= 2:
        out.append(Cell(run, "tcy", 1, char_style, span))
    else:
        out.append(Cell(run, "latin", max(1, ceil(len(run) * 0.5)), char_style, span))


def _is_run_char(ch: str, vertical: bool) -> bool:
    # 直排：只把英數收成串（拉丁串旋轉、短數字縱中橫）。
    # 橫排：整段連續 ascii（含空格、連字號、句點）收成一個 latin run，走自然寬。
    if vertical:
        return ch.isascii() and ch.isalnum()
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
        _flush_ascii(run, cells, char_style, vertical, _span(offsets, run_start, i))
        run = ""
        if ch in (" ", "　"):
            cells.append(Cell(ch, "space", 1, char_style, _span(offsets, i, i + 1)))
        else:
            cells.append(Cell(ch, "cjk", 1, char_style, _span(offsets, i, i + 1)))
    _flush_ascii(run, cells, char_style, vertical, _span(offsets, run_start, len(text)))
    return cells


def cells_from_runs(runs, vertical: bool = True) -> list:
    """run 序列 → cells（各 run 內部正規化＋標注字元樣式；拉丁串不跨 run 合併）。

    span 為文件段 text 座標：run k 的基底＝前 k−1 個 run 的 text 長度和
    （document@2 不變式：段 text＝runs 串接）。
    """
    cells: list = []
    base = 0
    for text, char_style in runs:
        norm, offs = normalize_with_offsets(text)
        cells.extend(tokenize(norm, char_style, vertical,
                              offsets=tuple(base + o for o in offs)))
        base += len(text)
    return cells


def break_paragraph(text: str, chars_per_line: int, indent: int = 2,
                    vertical: bool = True) -> list:
    return _break_cells(tokenize(normalize(text), vertical=vertical), chars_per_line, indent)


def _break_cells(cells: list, chars_per_line: int, indent: int = 2) -> list:
    lines: list = []
    idx = 0
    start = indent
    while idx < len(cells):
        cap = chars_per_line - start
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
        lines.append(Line(tuple(line), start, cap=cap, para_end=False))
        start = 0
    if lines:
        last = lines[-1]
        lines[-1] = Line(last.cells, last.start_slot, cap=last.cap, para_end=True)
    return lines


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
) -> list:
    """把 ParagraphSpec 序列流排成頁。

    回傳 pages，每頁為 [PlacedLine, ...]，行槽起算為 0（直排右起、橫排上起）。
    段後空槽跨頁時歸零（不帶進次頁），與參考書實測一致。
    斷行與禁則規則與方向無關；vertical 只決定 tokenize（橫排不轉縱中橫）。
    """
    pages: list = []
    cur: list = []
    slot = 0

    def emit(line: Line, style: str, line_slots: int, page_no=None, para_idx=None) -> None:
        nonlocal slot, cur
        if slot + line_slots > slots_per_page:
            pages.append(cur)
            cur = []
            slot = 0
        cur.append(PlacedLine(slot, line, style, page_no=page_no, para_idx=para_idx))
        slot += line_slots

    for pi, spec in enumerate(specs):
        indent = 0 if (pi == 0 and first_para_continues) else spec.indent
        cap = spec.chars_per_line if spec.chars_per_line else chars_per_line
        if spec.runs:
            cells = cells_from_runs(spec.runs, vertical)
        else:
            norm, offs = normalize_with_offsets(spec.text)
            cells = tokenize(norm, vertical=vertical, offsets=offs)
        for line in _break_cells(cells, cap, indent=indent):
            emit(line, spec.style, spec.line_slots,
                 page_no=spec.page_no if line.para_end else None,
                 para_idx=spec.para_idx)
        if pi < len(specs) - 1:
            slot += spec.gap_after
            if slot >= slots_per_page:
                pages.append(cur)
                cur = []
                slot = 0
    if cur:
        pages.append(cur)
    return pages
