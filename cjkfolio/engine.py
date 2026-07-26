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

# 標點擠壓（約物詰め）字集（Sprint 90，CLREQ WD-20150723 §3.1.6.1）：
# 條文列舉的「頓號、逗號、句號」與括號類。括號沿用既有禁則字集不另立新集。
SQUEEZE_STOPS = frozenset("、，。")
SQUEEZE_OPENERS = frozenset(LINE_END_FORBIDDEN)
SQUEEZE_CLOSERS = frozenset("」』）〕》〉｝〗")
SQUEEZE_WIDTH = 0.5  # 讓出半形後的字身框（條文：可減少半個字寬）
# 行首開括號的字形位移（Sprint 117，§3.1.6.2 規則 1）：單位為 em（字級倍數），
# 負值＝往行首（直排的上方）。取 em 而非字槽是量出來的：位移綁字距（0.5252 em）
# 或綁齊行後字距（cap 愈小愈大）會在《〈上切墨，見 spikes/spike20-line-head-squeeze。
SQUEEZE_HEAD_OFFSET = -0.5

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

# 破折號（Sprint 142）：U+2014 EM DASH／U+2015 HORIZONTAL BAR。連續兩枚須**一起
# 塑形**才連得起來，單枚逐格塑形會在接縫留缺口（量測 spikes 見 devlog：內建
# Source Han Serif TC 的 vert 單枚 gid 58918 墨高 858/1000，字槽上下各留 0.071 em，
# 兩格相鄰即中間空 0.142 em）。兩枚一起塑形取得連字 gid 65053，yadv −2000、
# 墨高 1858/2000＝一條連續的兩格長線，正是 CLREQ 破折號佔兩格的形態。
_DASHES = frozenset("—―")

# 直排半形括號 → 全形（Sprint 142）：ASCII 括號在字型裡沒有 vert 直排字形，
# 直排會維持半形直立（真稿末段「(完)」即此形態），且不在禁則字集內＝不吃行首
# 行尾規則。轉全形後走與其他全形約物同一條路（vert 字形、禁則、擠壓）。
# 只在直排轉；橫排的 ascii 括號屬 latin run（_is_run_char 收走），不經此表。
_VERTICAL_BRACKETS = {
    "(": "（", ")": "）", "[": "〔", "]": "〕", "{": "｛", "}": "｝",
}


@dataclass(frozen=True)
class Cell:
    text: str
    kind: str  # "cjk" | "tcy" | "latin" | "space"
    width: float = 1  # 佔用的直排字槽數（標點擠壓後可為 0.5，Sprint 90）
    char_style: Optional[str] = None  # 字元樣式名（run 模型；None＝依段落樣式）
    span: Optional[tuple] = None  # 文件 provenance：來源 text 半開區間 (start, end)。
    # 座標系＝tokenize 輸入 text；經 offsets 映射後＝文件段 text（normalize 前）座標。
    ruby: Optional[str] = None  # 注音／ruby 標注（Sprint 86）：直排繪於字右側置中；
    # 掛 base 群組的**首** cell（單字 base＝v1 mono-ruby，即 span=1 的特例）。
    ruby_span: int = 0  # 本 cell 起算的 base 群組 cell 數（Sprint 134 group ruby）；
    # 0＝非群組首。群組不被斷行切開（切開則 ruby 無處可放），ruby 於群組範圍置中。
    glyph_offset: float = 0.0  # 字形位移（em；Sprint 117）：字軸方向，負值＝往行首。
    # 純載體，不影響 width／斷行／禁則；三處渲染一律乘字級（非乘齊行字距）。


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
    punct_squeeze: bool = False  # 標點擠壓（Sprint 90）：相鄰約物讓出半形（opt-in）
    line_end_squeeze: bool = False  # 行尾閉括號縮末側（Sprint 116，CLREQ §3.1.6.2 規則 2；opt-in）
    line_head_squeeze: bool = False  # 行首開括號縮始側（Sprint 117，CLREQ §3.1.6.2 規則 1；opt-in）


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
    if vertical and len(run) >= 2 and set(run) == {"."}:
        # 純句點串＝省略號的鍵盤代打（真稿 92 處，如「我...我想跟」）。列標記
        # 「1.」與小數「2.0」含數字，不落此分支。走 latin 的話會被 _draw_rotated_latin
        # 以 asc+desc 字條置中，句點墨跡貼基線＝旋轉後偏左（使用者回報的病灶）；
        # 轉標準省略號 U+2026 走 cjk 字槽，vert 字形墨跡 ink_x=[−56,56] 自然置中。
        # 三點一枚（U+2026 本身即三點），不足三點者進位為一枚。
        for k in range(ceil(len(run) / 3)):
            lo, hi = start + k * 3, min(start + (k + 1) * 3, end)
            out.append(Cell("…", "cjk", 1, char_style, _span(offsets, lo, hi)))
        return
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
    skip_next = False  # 破折號成對時吃掉下一枚
    for i, ch in enumerate(text):
        if skip_next:
            skip_next = False
            continue
        if _is_run_char(ch, vertical):
            if not run:
                run_start = i
            run += ch
            continue
        _flush_latin(run, cells, char_style, vertical, offsets, run_start)
        run = ""
        if ch in (" ", "　"):
            cells.append(Cell(ch, "space", 1, char_style, _span(offsets, i, i + 1)))
        elif (vertical and ch in _DASHES and i + 1 < len(text)
                and text[i + 1] in _DASHES):
            # 成對破折號＝一格兩枚一起塑形（連字），佔兩個字槽（見 _DASHES 註）。
            # 只吃兩枚：三枚以上時前兩枚成對、餘下者續判，字格總寬與逐字時相同，
            # 故斷行容量與頁數不因本合併而變。
            cells.append(Cell(text[i:i + 2], "cjk", 2, char_style,
                              _span(offsets, i, i + 2)))
            skip_next = True
        else:
            cells.append(Cell(_VERTICAL_BRACKETS.get(ch, ch) if vertical else ch,
                              "cjk", 1, char_style, _span(offsets, i, i + 1)))
    _flush_latin(run, cells, char_style, vertical, offsets, run_start)
    return cells


def _ruby_group(cells: list, ruby: str) -> list:
    """把一個 run 產出的 cells 標成一個 ruby 群組，並依 ruby 長度加寬 base。

    ruby 驅動 base 間距（Sprint 134）：ruby 串佔的槽數＝字數×RUBY_SIZE_RATIO，
    超過 base 群組原寬時把差額**等分**攤回各 base cell。不加寬的話 ruby 會排到
    群組範圍外、壓上相鄰欄的字（v1 GAPS #46 (c) 登記的溢出，日文「蟋蟀
    《きりぎりす》」這類 2 字配 5 假名的詞即會踩到）。ruby 較短時不縮排
    （base 維持整數槽，版心網格不因注音而鬆動）。
    """
    from .placement import RUBY_SIZE_RATIO

    span = len(cells)
    base_width = sum(c.width for c in cells)
    need = len(ruby) * RUBY_SIZE_RATIO
    if need > base_width:  # 等分加寬（保持群組內各字等距）
        per = need / span
        cells = [replace(c, width=per) for c in cells]
    return [replace(cells[0], ruby=ruby, ruby_span=span), *cells[1:]]


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
        if ruby and produced:  # base 群組（單字＝mono-ruby 的特例，Sprint 134）
            produced = _ruby_group(produced, ruby)
        cells.extend(produced)
        base += len(text)
    return cells


def _squeezes(left: str, right: str) -> bool:
    """左枚約物是否讓出半形（CLREQ WD-20150723 §3.1.6.1 規則 2〜6）。

    規則 2／4／6＝閉括號後接句逗、開括號、閉括號；規則 3＝句逗後接開括號；
    規則 5＝連續開括號。**規則 1（句逗後接閉括號）不實作**：條文明文括註
    「繁體中文標點不適用此規則」，且內建繁體字型墨跡量測顯示該情境擠壓後
    墨距為負（相碰，spikes/spike17-mojikumi）。規則 7／8（solidus 減 1/4 形）
    無素材可驗，未實作（見 GAPS）。
    """
    if left in SQUEEZE_CLOSERS:
        return (right in SQUEEZE_STOPS or right in SQUEEZE_OPENERS
                or right in SQUEEZE_CLOSERS)
    if left in SQUEEZE_STOPS:
        return right in SQUEEZE_OPENERS
    if left in SQUEEZE_OPENERS:
        return right in SQUEEZE_OPENERS
    return False


def _squeezable(cell) -> bool:
    """單一全形約物字格才參與擠壓（縱中橫、旋轉拉丁、空白與已擠壓者除外）。"""
    return cell.kind == "cjk" and len(cell.text) == 1 and cell.width == 1


def squeeze_punctuation(cells: list) -> list:
    """相鄰約物擠壓（純函式）：讓出半形者字身框 1 → 0.5 em，字形位置不變。

    CLREQ §3.1.6.1 調整的是「符號間相鄰的空隙」而非字面位置，故只縮推進量、
    不位移字形：兩後端既有的 `content_i += cell.width` 累加即得正確落點，
    渲染層零改動（Spike 17 已推導此模型與「壓後枚＋字形上移」等價）。
    逐對套用（三枚以上連續約物各對獨立判定）。
    """
    out = list(cells)
    for i in range(len(out) - 1):
        left, right = out[i], out[i + 1]
        if not (_squeezable(left) and _squeezable(right)):
            continue
        if _squeezes(left.text, right.text):
            out[i] = replace(left, width=SQUEEZE_WIDTH)
    return out


def squeeze_line_end(line: Line) -> Line:
    """行尾閉括號縮末側（純函式，CLREQ §3.1.6.2 規則 2）：末枚字身框 1 → 0.5 em。

    條文：「當行尾出現結束括注符號時，可以縮減其末側二分之一個漢字大小的空白。」
    同 §3.1.6.1 取 advance-only 模型（只縮推進量、不位移字形），故兩後端與畫布零
    改動。**斷行已定案後才套用**（模型 A）：省下的半格不回饋容量，行邊界與關閉時
    完全相同，保住 Sprint 90 起守住的斷行確定性（模型 B 迭代求不動點見 GAPS #69）。

    幾何實效：末枚之後無內容，故單看該行不動字形；非段末行經齊行 `cap / used`
    重算後字距均勻放大，末枚的墨跡因而抵住行尾。段末行不齊行，本規則對其無視覺
    效果（誠實記錄，見 GAPS #72）。同小節規則 1（行首開括號）需字形偏移欄位，另案。
    """
    if not line.cells:
        return line
    last = line.cells[-1]
    if not (_squeezable(last) and last.text in SQUEEZE_CLOSERS):
        return line  # 已由 §3.1.6.1 壓過者 width 非 1，`_squeezable` 即擋住重複扣
    return replace(line, cells=(*line.cells[:-1], replace(last, width=SQUEEZE_WIDTH)))


def squeeze_line_head(line: Line) -> Line:
    """行首開括號縮始側（純函式，CLREQ §3.1.6.2 規則 1）：首枚字身框 1 → 0.5 em，
    並把字形往行首移 0.5 em。

    條文：「當行首出現開始括注符號，可以縮減該符號始側二分之一個漢字大小的空白。」
    與同小節規則 2 的差別在**始側之前沒有推進量可縮**：只縮 width 會讓後續字格上移
    而括號自己不動，等於把空白留在行首。故本條除縮 width 外另設 `glyph_offset`
    （em，`SQUEEZE_HEAD_OFFSET`），由兩後端與畫布乘字級還原。

    位移單位取字級不取字槽：Spike 20 量得 0.5 em 位移在兩款內建字型 16 枚開括號上
    切墨 0 筆（最小餘裕 0.020 em），而 0.5 字槽（0.5252 em）與齊行放大後的 0.5 字距
    會在《〈上切墨，且欄愈窄切愈深。

    **斷行已定案後才套用**（模型 A，同 Sprint 116）：省下的半格不回饋容量，行邊界與
    關閉時完全相同。已由 §3.1.6.1 壓過的行首括號（width 非 1）不重複套用。
    """
    if not line.cells:
        return line
    first = line.cells[0]
    if not (_squeezable(first) and first.text in SQUEEZE_OPENERS):
        return line
    squeezed = replace(first, width=SQUEEZE_WIDTH, glyph_offset=SQUEEZE_HEAD_OFFSET)
    return replace(line, cells=(squeezed, *line.cells[1:]))


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
    # ruby 群組不可拆行（Sprint 134）：行尾落在群組中間就整組退到下一行
    # （切開則 ruby 無處可放）。群組本身寬於整行時不退（退了行會空，且無解），
    # 容許溢出並由 check_overflow 據實回報，同單枚超寬 cell 的處置。
    cut = _ruby_group_cut(line)
    if cut is not None and cut > 0:
        idx -= len(line) - cut
        del line[cut:]
    if not line:  # 病理情形防護：強制收一字避免死循環
        line.append(cells[idx])
        idx += 1
    return line, idx


def _ruby_group_cut(line: list):
    """行尾若切在 ruby 群組中間，回傳該群組在 line 中的起始索引；否則 None。"""
    for i in range(len(line) - 1, -1, -1):
        span = line[i].ruby_span
        if span:
            return i if i + span > len(line) else None
    return None


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


def check_overflow(lines) -> list:
    """行內容寬於行容量者逐行回報（Sprint 111）。

    觸發來源是 `_break_one_line` 末段的病理防護：貪婪迴圈收不到任何 cell 時
    （＝單一 cell 寬於整行容量）強制收一枚，該枚遂溢出版心。此前**沒有任何機制
    回報它**：`check_kinsoku` 只驗行首行尾字元、不驗寬度。一手實測（Sprint 111）：
    80 字元拉丁串（width=40）排進 cap=30 的欄，溢出 10 槽＝120.8pt（約 42.6mm）。

    本函式只回報、不改斷行行為（斷行策略的改動需 R1 證據，回報不需要；同 Sprint 109
    對 TAC 400% 的立場：據實回報、不擋流程）。cap <= 0＝容量未知，不據以判定
    （同 `line_justified_advance` 對未知容量的處置）。

    **判準是「單一 cell 寬於行容量」，不是「行用量超過容量」**：後者會把行首禁則的
    擠入（GAPS #9 定案的設計行為，句逗整串擠入行尾、溢出 ≤ MAX_SQUEEZE_SLOTS）誤判
    為違規。實測初版以 used > cap 為判準，在 `samples/paiban-xiaoji-ch1.md` 這份正常
    素材上就冒出 11 筆假違規（皆為 used=31／cap=30 而最寬 cell 僅 1 槽的擠入行）。
    單一 cell 寬於容量則無論如何切行都塞不下，齊行也無從補救，那才是病理情形。
    """
    violations = []
    for i, line in enumerate(lines):
        if not line.cells or line.cap <= 0:
            continue
        widest = max(c.width for c in line.cells)
        if widest > line.cap:
            violations.append(
                f"行 {i + 1} 內容溢出行容量：最寬 cell {widest:g} 槽 > 容量 "
                f"{line.cap:g} 槽（超出 {widest - line.cap:g} 槽），"
                f"本行共用 {sum(c.width for c in line.cells):g} 槽"
            )
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
        if spec.punct_squeeze and vertical:  # 擠壓量測依直排 vert 形墨跡（Sprint 90）
            cells = squeeze_punctuation(cells)
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
            if spec.line_end_squeeze and vertical:  # 斷行定案後才套用（模型 A）
                line = squeeze_line_end(line)
            if spec.line_head_squeeze and vertical:  # 同上（Sprint 117，規則 1）
                line = squeeze_line_head(line)
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
