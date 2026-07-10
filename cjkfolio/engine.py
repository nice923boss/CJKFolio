"""直排版面引擎核心：正規化、斷行、禁則、頁面流排（Phase 1 產品層）。

自 Spike 1（spikes/spike1-vertical-core/vertical_engine.py）產品化：
斷行與禁則規則不變，flow_pages 改以 ParagraphSpec 承載樣式驅動的
每段行容量（大級數標題行高換算）、縮排、段後空槽與行槽寬。

純邏輯層，不碰字型與渲染。規則依據 W3C CLREQ（繁中）：
- 行首禁則：句逗號、閉引號括號等不得落行首，以追出處理（前字隨之下移）。
- 行尾禁則：開引號括號不得懸行尾，退至下一行。
- 縱中橫：1〜2 位數字直立橫排（tcy）；3 位以上數字與拉丁串旋轉 90 度（latin），串不拆。
"""
import unicodedata
from dataclasses import dataclass
from math import ceil
from typing import Optional

# CLREQ 繁中行首禁則（不得出現在行首）
LINE_START_FORBIDDEN = set("，。、：；！？」』）〕》〉｝〗…‥·．％")
# 行尾禁則（不得懸在行尾）
LINE_END_FORBIDDEN = set("「『（〔《〈｛〖")

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


@dataclass(frozen=True)
class Line:
    cells: tuple
    start_slot: int = 0  # 段首縮排時 > 0


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


@dataclass(frozen=True)
class PlacedLine:
    slot: int
    line: Line
    style: str


def normalize(text: str) -> str:
    # 控制字元（Cc）非排版內容：PDF 抽取素材常殘留（如發言標籤後的 U+0007）
    return "".join(
        _PRESENTATION_FORMS.get(ch, ch)
        for ch in text
        if unicodedata.category(ch) != "Cc"
    )


def _flush_ascii(run: str, out: list, char_style=None) -> None:
    if not run:
        return
    if run.isdigit() and len(run) <= 2:
        out.append(Cell(run, "tcy", 1, char_style))
    else:
        out.append(Cell(run, "latin", max(1, ceil(len(run) * 0.5)), char_style))


def tokenize(text: str, char_style=None) -> list:
    cells: list = []
    run = ""
    for ch in text:
        if ch.isascii() and ch.isalnum():
            run += ch
            continue
        _flush_ascii(run, cells, char_style)
        run = ""
        if ch in (" ", "　"):
            cells.append(Cell(ch, "space", 1, char_style))
        else:
            cells.append(Cell(ch, "cjk", 1, char_style))
    _flush_ascii(run, cells, char_style)
    return cells


def cells_from_runs(runs) -> list:
    """run 序列 → cells（各 run 內部正規化＋標注字元樣式；拉丁串不跨 run 合併）。"""
    cells: list = []
    for text, char_style in runs:
        cells.extend(tokenize(normalize(text), char_style))
    return cells


def break_paragraph(text: str, chars_per_line: int, indent: int = 2) -> list:
    return _break_cells(tokenize(normalize(text)), chars_per_line, indent)


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
        # 行尾禁則：開括弧不懸行尾（後面還有字才需處理）
        while line and idx < len(cells) and line[-1].text in LINE_END_FORBIDDEN:
            idx -= 1
            line.pop()
        # 行首禁則：下一行首不得為禁則字，前字追出
        while line and idx < len(cells) and cells[idx].text in LINE_START_FORBIDDEN:
            if len(line) > 1:
                idx -= 1
                line.pop()
            else:  # 無字可追出：改為追入（禁則字掛入本行，允許溢出一格）
                line.append(cells[idx])
                idx += 1
        if not line:  # 病理情形防護：強制收一字避免死循環
            line.append(cells[idx])
            idx += 1
        lines.append(Line(tuple(line), start))
        start = 0
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
) -> list:
    """把 ParagraphSpec 序列流排成頁。

    回傳 pages，每頁為 [PlacedLine, ...]，行槽右起為 0。
    段後空槽跨頁時歸零（不帶進次頁），與參考書實測一致。
    """
    pages: list = []
    cur: list = []
    slot = 0

    def emit(line: Line, style: str, line_slots: int) -> None:
        nonlocal slot, cur
        if slot + line_slots > slots_per_page:
            pages.append(cur)
            cur = []
            slot = 0
        cur.append(PlacedLine(slot, line, style))
        slot += line_slots

    for pi, spec in enumerate(specs):
        indent = 0 if (pi == 0 and first_para_continues) else spec.indent
        cap = spec.chars_per_line if spec.chars_per_line else chars_per_line
        cells = cells_from_runs(spec.runs) if spec.runs else tokenize(normalize(spec.text))
        for line in _break_cells(cells, cap, indent=indent):
            emit(line, spec.style, spec.line_slots)
        if pi < len(specs) - 1:
            slot += spec.gap_after
            if slot >= slots_per_page:
                pages.append(cur)
                cur = []
                slot = 0
    if cur:
        pages.append(cur)
    return pages
