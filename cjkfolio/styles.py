"""三層樣式模型（PLAN §4.1）：段落樣式、字元樣式、主版，與模版載入。

模版是人類可讀 JSON（cjkfolio/template@1）。本層只承載參數，
幾何推導在 layout、字型解析在 fonts。系統邊界驗證，快速失敗。

樣式繼承（§4.3 基底＋覆寫，Sprint 68）：樣式宣告帶 based_on 即繼承基底有效欄位、
自身宣告欄位覆寫（鏈式）；效值於載入期扁平化（消費端讀平面欄位零變更），
based_on／declared 為簿記欄位（供編輯級聯 style_editing 與後續模版序列化）。
"""
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Mapping, Optional

from .auto_toc import AutoTocSpec, auto_toc_from_dict, check_auto_toc

SCHEMA_ID = "cjkfolio/template@1"

# 文字預設填色：暖黑單 K92（§9 內文 K90〜92 區間取 92，§10 Sprint 8 決議）
DEFAULT_TEXT_CMYK = (0.0, 0.0, 0.0, 0.92)

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\Z")


def _opt_str(value) -> Optional[str]:
    return None if value is None else str(value)


def _footer_text(value) -> Optional[str]:
    """書眉字面覆寫正規化：缺、null、空白字串一律回 None（＝照 source 取文件值）。

    單一「無覆寫」表示法，讓編輯層清空欄位與模版沒寫此鍵得到同一個模型。
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class TemplateError(ValueError):
    """模版 JSON 不合 schema。"""


_TRUE_TEXT = {"true", "1", "yes", "on"}
_FALSE_TEXT = {"false", "0", "no", "off", ""}


def _bool(value) -> bool:
    """布林欄位（模版 JSON 真布林／樣式面板 QLineEdit 字串皆可）。

    不用 Python 的真值判定：bool("False") 為 True，會把使用者的「關閉」讀成開啟。
    無法辨識者快速失敗，不沉默取預設。
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE_TEXT:
        return True
    if text in _FALSE_TEXT:
        return False
    raise TemplateError(f"布林欄位須為 true／false，得到 {value!r}")


@dataclass(frozen=True)
class ColorSwatch:
    """命名色票（§4.2／§4.3，Sprint 76）。

    cmyk 為印刷值 (c,m,y,k) 各 0〜1（§9 全 CMYK；文字填色引用取此值）；
    hex 為螢幕量測參考（如 §1 暖黑 #231f20），不參與印刷輸出。cmyk 為 None
    的色票（含舊形態 hex 字串照載）屬純記錄，不可被樣式 color 引用。
    """
    name: str
    cmyk: Optional[tuple] = None
    hex: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class ParagraphStyle:
    name: str
    font_family: str
    font_weight: str
    size_pt: float
    indent_chars: int = 2
    para_gap_slots: int = 1
    writing_mode: str = "vertical-rl"
    head_offset_chars: int = 0  # 段級天頭縮退（字格）：目錄條目相對篇名的縮退（Sprint 21）
    lead_offset_pt: float = 0.0  # 段級 inline 軸 sub-slot 偏移（pt）：首字起點微調（Sprint 29）
    punct_squeeze: bool = False  # 標點擠壓（Sprint 90）：相鄰約物讓出半形（CLREQ §3.1.6.1）
    line_end_squeeze: bool = False  # 行尾閉括號縮末側（Sprint 116；CLREQ §3.1.6.2 規則 2）
    line_head_squeeze: bool = False  # 行首開括號縮始側（Sprint 117；CLREQ §3.1.6.2 規則 1）
    starts_page: bool = False  # 此樣式的段一律起新頁（Sprint 141）：章名大標等章首樣式
    color: Optional[str] = None  # 文字色票名（Sprint 76）；None＝預設暖黑 K92
    source_font: Optional[str] = None
    note: Optional[str] = None
    based_on: Optional[str] = None  # 繼承基底樣式名（Sprint 68；效值已扁平化）
    declared: tuple = ()  # 自身宣告（覆寫）的欄位名，級聯與序列化簿記


@dataclass(frozen=True)
class CharacterStyle:
    name: str
    font_family: str
    font_weight: str
    size_pt: float
    color: Optional[str] = None  # 文字色票名（Sprint 76）；None＝承段落樣式解析鏈
    source_font: Optional[str] = None
    note: Optional[str] = None
    based_on: Optional[str] = None  # 繼承基底樣式名（Sprint 68；效值已扁平化）
    declared: tuple = ()  # 自身宣告（覆寫）的欄位名，級聯與序列化簿記


# 樣式參數欄位 → 型別轉換器（載入層語意單一來源；style_editing 編輯層同用。
# name／based_on／declared 為身分與簿記，不在參數欄位內）
PARAGRAPH_STYLE_FIELDS: Mapping[str, Callable] = {
    "font_family": str,
    "font_weight": str,
    "size_pt": float,
    "indent_chars": int,
    "para_gap_slots": int,
    "writing_mode": str,
    "head_offset_chars": int,
    "lead_offset_pt": float,
    "punct_squeeze": _bool,
    "line_end_squeeze": _bool,
    "line_head_squeeze": _bool,
    "starts_page": _bool,
    "color": _opt_str,
    "source_font": _opt_str,
    "note": _opt_str,
}

CHARACTER_STYLE_FIELDS: Mapping[str, Callable] = {
    "font_family": str,
    "font_weight": str,
    "size_pt": float,
    "color": _opt_str,
    "source_font": _opt_str,
    "note": _opt_str,
}


def _swatch_cmyk(value, ctx: str) -> tuple:
    """色票 cmyk 驗證（載入與編輯共用）：4 元素、各 0〜1。"""
    try:
        cmyk = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        raise TemplateError(f"{ctx}.cmyk 須為 4 元素 [c,m,y,k]，得到 {value!r}") from None
    if len(cmyk) != 4:
        raise TemplateError(f"{ctx}.cmyk 須為 4 元素 [c,m,y,k]，得到 {value!r}")
    if any(not 0.0 <= v <= 1.0 for v in cmyk):
        raise TemplateError(f"{ctx}.cmyk 各分量須在 0〜1，得到 {value!r}")
    return cmyk


def _swatch_hex(value, ctx: str) -> str:
    text = str(value)
    if not _HEX_RE.match(text):
        raise TemplateError(f"{ctx}.hex 須為 #RRGGBB，得到 {value!r}")
    return text


# 色票欄位 → 型別轉換器（style_editing.set_color 編輯層同用）
COLOR_FIELDS: Mapping[str, Callable] = {
    "cmyk": lambda v: None if v is None else _swatch_cmyk(v, "色票"),
    "hex": lambda v: None if v is None else _swatch_hex(v, "色票"),
    "note": _opt_str,
}


def check_color_ref(colors: Mapping, style, ctx: str) -> None:
    """樣式 color 引用守門（載入與編輯共用）：色票須存在且帶 cmyk 印刷值。"""
    if style.color is None:
        return
    swatch = colors.get(style.color)
    if swatch is None:
        raise TemplateError(f"{ctx}.color 引用不存在的色票「{style.color}」")
    if swatch.cmyk is None:
        raise TemplateError(
            f"{ctx}.color 色票「{style.color}」無 cmyk 印刷值，"
            "不可作文字色（§9 全 CMYK）")


def resolve_text_cmyk(template, *styles) -> tuple:
    """文字填色解析（兩後端單一事實來源，Sprint 76）。

    依序取第一個帶 color 的樣式（呼叫端以「字元樣式, 段落樣式」序傳入＝字元覆寫
    段落，同 run 覆寫字型慣例；None 項略過），查色票 cmyk；皆無 color 回預設暖黑
    K92。色票存在性與可印刷性由載入／編輯層守門，此處不再驗。
    """
    for style in styles:
        if style is not None and style.color is not None:
            return template.colors[style.color].cmyk
    return DEFAULT_TEXT_CMYK


@dataclass(frozen=True)
class Margins:
    top_mm: float
    bottom_mm: float
    outer_mm: float  # 書口
    inner_mm: float  # 訂口


@dataclass(frozen=True)
class Grid:
    chars_per_line: int
    lines_per_page: int
    char_advance_pt: float
    line_pitch_pt: float
    base_size_pt: float


@dataclass(frozen=True)
class FooterItem:
    """頁腳／書眉元素：水平文字，錨定書口（outer）側，奇偶頁鏡像。"""
    name: str
    style: str   # 字元樣式名
    source: str  # "number"（頁碼）| "title"（書名）
    baseline_from_top_pt: float
    outer_offset_pt: float  # 文字靠書口側的邊到頁面書口邊的距離
    pages: str = "all"      # "all" | "odd" | "even"
    text: Optional[str] = None  # 字面覆寫（Sprint 142）；None＝照 source 取文件值


# 書眉可編輯欄位（載入與 style_editing.set_footer_item 共用型別轉換，同上方樣式慣例）。
# style／source／pages 不在此：換字元樣式或改奇偶頁屬版型結構，非 Owner 的「改字、挪位置」。
FOOTER_ITEM_FIELDS: Mapping[str, Callable] = {
    "text": _footer_text,
    "baseline_from_top_pt": float,
    "outer_offset_pt": float,
}


KNOWN_FRAME_KINDS = frozenset({"cip-box"})  # v1 只有 CIP 細框
KNOWN_RULE_KINDS = frozenset({"toc-rule"})  # v1 只有目錄天頭虛線
KNOWN_FIGURE_KINDS = frozenset({"photo-slot"})  # v1 只有 G 圖文版前後對照照片保留區


@dataclass(frozen=True)
class FrameSpec:
    """主版向量裝飾框（v1：CIP 細框，PLAN §1 精緻設計細節）。

    cmyk 為描邊色 (c,m,y,k) 各 0〜1（一律 DeviceCMYK，維持 §9 全 CMYK）；
    幾何由 primitives.cip_frame_rect 依主版 grid 與內容行數推導。
    """
    kind: str
    cmyk: tuple = (0.0, 0.0, 0.0, 1.0)
    line_width_pt: float = 0.5
    pad_pt: float = 6.0
    pad_v_pt: Optional[float] = None  # 垂直 pad（p178 實測不對稱）；None＝同 pad_pt


@dataclass(frozen=True)
class FigureSpec:
    """主版圖框保留區（v1：G-圖文版前後對照照片區，PLAN §4.2）。

    記錄圖片置入的保留區：縱向 top_from_top_pt→bottom_from_top_pt（參考書典型
    雙照片全頁一手量測），橫向承主版版心（primitives.figure_slot_rect 鏡像推導）。
    Phase 1 以淡虛線佔位框標示保留區（版面骨架校對，InDesign 空框慣例）；Phase 2
    圖片置入後由實際照片取代、不留框線。此為代表性量測：實際照片逐頁變異（單/雙、
    高度不一），屬美術資產（§8 不生成）＋Phase 2 自由佈局。cmyk 一律 DeviceCMYK
    （維持 §9 全 CMYK，佔位框走 `K` 不觸 preflight rg/RG）；dash_on_pt>0 為虛線
    （佔位語意，與最終墨區隔）。
    """
    kind: str
    top_from_top_pt: float
    bottom_from_top_pt: float
    cmyk: tuple = (0.0, 0.0, 0.0, 0.3)
    line_width_pt: float = 0.5
    dash_on_pt: float = 4.0
    dash_off_pt: float = 3.0
    note: Optional[str] = None


@dataclass(frozen=True)
class RuleSpec:
    """主版向量裝飾線（v1：目錄天頭水平虛線，PLAN §1 精緻設計細節）。

    cmyk 一律 DeviceCMYK；y_from_top_pt 為線的天頭下位置（參考書 p003 實測
    122.46pt）；dash_on_pt/dash_off_pt 為虛線節奏（實測 [3 2]），on=0 為實線；
    bleed_extend_pt 為兩端越出頁邊的出血延伸（§9 貼邊元素出血全出）。
    幾何由 primitives.toc_rule_line 依頁寬推導。
    """
    kind: str
    y_from_top_pt: float
    cmyk: tuple = (0.0, 0.0, 0.0, 1.0)
    line_width_pt: float = 1.0
    dash_on_pt: float = 3.0
    dash_off_pt: float = 2.0
    bleed_extend_pt: float = 3.0 * 72.0 / 25.4
    # 篇名嵌線斷開邊距（Sprint 21，p002／p003 實測中值）：穿線行行槽緣到線端的
    # gap；before＝行前方（直排讀序 x 大側）、after＝行後方
    break_before_pt: float = 0.0
    break_after_pt: float = 0.0


@dataclass(frozen=True)
class TocSpec:
    """主版目錄條目配置（v1：直排數字頁碼底錨＋垂直引導線，PLAN §1）。

    page_no_style 為頁碼字元樣式名（須存在於模版 character_styles）；
    page_no_bottom_pt 為頁碼末位底錨（p003 實測 490pt，top-down）；引導線為
    行軸上的垂直實線（寬 0.1pt 實測），與文字同單 K92（§9）。幾何由
    layout.toc_marks 依段末行推導。
    """
    page_no_style: str
    page_no_bottom_pt: float
    leader_width_pt: float = 0.1
    leader_gap_pt: float = 2.0
    leader_cmyk: tuple = (0.0, 0.0, 0.0, 0.92)


@dataclass(frozen=True)
class MasterPage:
    name: str
    margins: Margins
    grid: Grid
    mirror: bool = True  # 對開鏡像（奇數書頁書口在右；奇偶依書頁號）
    footer: dict = field(default_factory=dict)  # name → FooterItem
    frame: Optional[FrameSpec] = None  # 向量裝飾框（v1：CIP 細框；None＝不畫框）
    rule: Optional[RuleSpec] = None  # 向量裝飾線（v1：目錄天頭虛線；None＝不畫線）
    toc: Optional[TocSpec] = None  # 目錄條目配置（頁碼底錨＋引導線；None＝非目錄頁）
    figure: Optional[FigureSpec] = None  # 圖框保留區（v1：G 圖文版照片區佔位；None＝非圖文頁）
    evidence: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class Template:
    name: str
    page_width_mm: float
    page_height_mm: float
    colors: dict = field(default_factory=dict)
    paragraph_styles: dict = field(default_factory=dict)
    character_styles: dict = field(default_factory=dict)
    masters: dict = field(default_factory=dict)
    md_mapping: dict = field(default_factory=dict)  # md block kind → 段落樣式名
    md_inline_mapping: dict = field(default_factory=dict)  # md 行內 kind（strong/em）→ 字元樣式名
    # 匯入新稿時掛哪張主版（Sprint 105）。原為寫死於各 import_* 的預設「A-內文版」，
    # 對第二本書即為錯的主版名，故搬進模版資料層由各模版自行宣告。
    default_master: str = ""
    # 新稿建封面時掛哪張主版（Sprint 132，同 default_master 的資料層慣例）：
    # 封面主版名逐模版而異（第一本 H-封面、第二本 丁-封面），寫死於匯入層即為
    # 對另一本書錯的名字（Sprint 107 已修過的同型缺陷）。""＝該模版不提供封面。
    default_cover: str = ""
    # 自動目錄生成規格（Sprint 135）；None＝該模版不支援自動目錄（AI 指派仍可標
    # 目錄條目，只是沒有可生成的目錄節，此時據實提示而非沉默略過）。
    auto_toc: Optional[AutoTocSpec] = None


def _require(data: dict, key: str, context: str):
    if key not in data:
        raise TemplateError(f"{context} 缺必要欄位 {key}")
    return data[key]


def _paragraph_style(name: str, d: dict) -> ParagraphStyle:
    ctx = f"paragraph_styles[{name}]"
    return ParagraphStyle(
        name=name,
        font_family=str(_require(d, "font_family", ctx)),
        font_weight=str(_require(d, "font_weight", ctx)),
        size_pt=float(_require(d, "size_pt", ctx)),
        indent_chars=int(d.get("indent_chars", 2)),
        para_gap_slots=int(d.get("para_gap_slots", 1)),
        writing_mode=str(d.get("writing_mode", "vertical-rl")),
        head_offset_chars=int(d.get("head_offset_chars", 0)),
        lead_offset_pt=float(d.get("lead_offset_pt", 0.0)),
        punct_squeeze=_bool(d.get("punct_squeeze", False)),
        line_end_squeeze=_bool(d.get("line_end_squeeze", False)),
        line_head_squeeze=_bool(d.get("line_head_squeeze", False)),
        starts_page=_bool(d.get("starts_page", False)),
        color=_opt_str(d.get("color")),
        source_font=d.get("source_font"),
        note=d.get("note"),
    )


def _character_style(name: str, d: dict) -> CharacterStyle:
    ctx = f"character_styles[{name}]"
    return CharacterStyle(
        name=name,
        font_family=str(_require(d, "font_family", ctx)),
        font_weight=str(_require(d, "font_weight", ctx)),
        size_pt=float(_require(d, "size_pt", ctx)),
        color=_opt_str(d.get("color")),
        source_font=d.get("source_font"),
        note=d.get("note"),
    )


def _footer_item(name: str, d: dict, ctx: str) -> FooterItem:
    return FooterItem(
        name=name,
        style=str(_require(d, "style", ctx)),
        source=str(_require(d, "source", ctx)),
        baseline_from_top_pt=float(_require(d, "baseline_from_top_pt", ctx)),
        outer_offset_pt=float(_require(d, "outer_offset_pt", ctx)),
        pages=str(d.get("pages", "all")),
        text=_footer_text(d.get("text")),
    )


def _frame_spec(d: dict, ctx: str) -> FrameSpec:
    kind = str(_require(d, "kind", ctx))
    if kind not in KNOWN_FRAME_KINDS:
        raise TemplateError(f"{ctx}.kind={kind!r} 非已知框類型 {sorted(KNOWN_FRAME_KINDS)}")
    cmyk = d.get("cmyk", [0.0, 0.0, 0.0, 1.0])
    if not (isinstance(cmyk, (list, tuple)) and len(cmyk) == 4):
        raise TemplateError(f"{ctx}.cmyk 須為 4 元素 [c,m,y,k]，得到 {cmyk!r}")
    pad_v = d.get("pad_v_pt")
    return FrameSpec(
        kind=kind,
        cmyk=tuple(float(v) for v in cmyk),
        line_width_pt=float(d.get("line_width_pt", 0.5)),
        pad_pt=float(d.get("pad_pt", 6.0)),
        pad_v_pt=None if pad_v is None else float(pad_v),
    )


def _rule_spec(d: dict, ctx: str) -> RuleSpec:
    kind = str(_require(d, "kind", ctx))
    if kind not in KNOWN_RULE_KINDS:
        raise TemplateError(f"{ctx}.kind={kind!r} 非已知線類型 {sorted(KNOWN_RULE_KINDS)}")
    y = _require(d, "y_from_top_pt", ctx)
    cmyk = d.get("cmyk", [0.0, 0.0, 0.0, 1.0])
    if not (isinstance(cmyk, (list, tuple)) and len(cmyk) == 4):
        raise TemplateError(f"{ctx}.cmyk 須為 4 元素 [c,m,y,k]，得到 {cmyk!r}")
    return RuleSpec(
        kind=kind,
        y_from_top_pt=float(y),
        cmyk=tuple(float(v) for v in cmyk),
        line_width_pt=float(d.get("line_width_pt", 1.0)),
        dash_on_pt=float(d.get("dash_on_pt", 3.0)),
        dash_off_pt=float(d.get("dash_off_pt", 2.0)),
        bleed_extend_pt=float(d.get("bleed_extend_pt", 3.0 * 72.0 / 25.4)),
        break_before_pt=float(d.get("break_before_pt", 0.0)),
        break_after_pt=float(d.get("break_after_pt", 0.0)),
    )


def _toc_spec(d: dict, ctx: str) -> TocSpec:
    style = str(_require(d, "page_no_style", ctx))
    bottom = _require(d, "page_no_bottom_pt", ctx)
    cmyk = d.get("leader_cmyk", [0.0, 0.0, 0.0, 0.92])
    if not (isinstance(cmyk, (list, tuple)) and len(cmyk) == 4):
        raise TemplateError(f"{ctx}.leader_cmyk 須為 4 元素 [c,m,y,k]，得到 {cmyk!r}")
    return TocSpec(
        page_no_style=style,
        page_no_bottom_pt=float(bottom),
        leader_width_pt=float(d.get("leader_width_pt", 0.1)),
        leader_gap_pt=float(d.get("leader_gap_pt", 2.0)),
        leader_cmyk=tuple(float(v) for v in cmyk),
    )


def _figure_spec(d: dict, ctx: str) -> FigureSpec:
    kind = str(_require(d, "kind", ctx))
    if kind not in KNOWN_FIGURE_KINDS:
        raise TemplateError(f"{ctx}.kind={kind!r} 非已知圖框類型 {sorted(KNOWN_FIGURE_KINDS)}")
    top = float(_require(d, "top_from_top_pt", ctx))
    bottom = float(_require(d, "bottom_from_top_pt", ctx))
    if not bottom > top:
        raise TemplateError(
            f"{ctx}.bottom_from_top_pt（{bottom}）須大於 top_from_top_pt（{top}）"
        )
    cmyk = d.get("cmyk", [0.0, 0.0, 0.0, 0.3])
    if not (isinstance(cmyk, (list, tuple)) and len(cmyk) == 4):
        raise TemplateError(f"{ctx}.cmyk 須為 4 元素 [c,m,y,k]，得到 {cmyk!r}")
    return FigureSpec(
        kind=kind,
        top_from_top_pt=top,
        bottom_from_top_pt=bottom,
        cmyk=tuple(float(v) for v in cmyk),
        line_width_pt=float(d.get("line_width_pt", 0.5)),
        dash_on_pt=float(d.get("dash_on_pt", 4.0)),
        dash_off_pt=float(d.get("dash_off_pt", 3.0)),
        note=d.get("note"),
    )


def _master(name: str, d: dict) -> MasterPage:
    ctx = f"masters[{name}]"
    m = _require(d, "margins_mm", ctx)
    g = _require(d, "grid", ctx)
    return MasterPage(
        name=name,
        margins=Margins(
            top_mm=float(_require(m, "top", f"{ctx}.margins_mm")),
            bottom_mm=float(_require(m, "bottom", f"{ctx}.margins_mm")),
            outer_mm=float(_require(m, "outer", f"{ctx}.margins_mm")),
            inner_mm=float(_require(m, "inner", f"{ctx}.margins_mm")),
        ),
        grid=Grid(
            chars_per_line=int(_require(g, "chars_per_line", f"{ctx}.grid")),
            lines_per_page=int(_require(g, "lines_per_page", f"{ctx}.grid")),
            char_advance_pt=float(_require(g, "char_advance_pt", f"{ctx}.grid")),
            line_pitch_pt=float(_require(g, "line_pitch_pt", f"{ctx}.grid")),
            base_size_pt=float(_require(g, "base_size_pt", f"{ctx}.grid")),
        ),
        mirror=bool(d.get("mirror", True)),
        footer={
            fname: _footer_item(fname, fd, f"{ctx}.footer[{fname}]")
            for fname, fd in d.get("footer", {}).items()
        },
        frame=_frame_spec(d["frame"], f"{ctx}.frame") if d.get("frame") else None,
        rule=_rule_spec(d["rule"], f"{ctx}.rule") if d.get("rule") else None,
        toc=_toc_spec(d["toc"], f"{ctx}.toc") if d.get("toc") else None,
        figure=_figure_spec(d["figure"], f"{ctx}.figure") if d.get("figure") else None,
        evidence=d.get("evidence"),
        note=d.get("note"),
    )


def _resolve_styles(raw: dict, fields: Mapping, build, kind: str) -> dict:
    """依 based_on 解析樣式宣告為扁平化樣式（Sprint 68 繼承）。

    子樣式繼承基底「有效欄位」再以自身宣告覆寫（鏈式）；循環（含自指）與
    未知基底 TemplateError；無 based_on 的根樣式必填欄位守門不變（由 build 執行）。
    declared＝自身宣告的參數欄位名（排序 tuple），based_on 原樣入簿記。
    """
    resolved: dict = {}
    resolving: list = []

    def resolve(name: str):
        if name in resolved:
            return resolved[name]
        if name in resolving:
            chain = "→".join((*resolving, name))
            raise TemplateError(f"{kind} based_on 循環：{chain}")
        decl = raw[name]
        base_name = decl.get("based_on")
        own = {k: v for k, v in decl.items() if k in fields}
        if base_name is None:
            effective = own
        else:
            if base_name not in raw:
                raise TemplateError(
                    f"{kind}[{name}] based_on 引用不存在的樣式「{base_name}」")
            resolving.append(name)
            base = resolve(base_name)
            resolving.pop()
            effective = {**{f: getattr(base, f) for f in fields}, **own}
        style = replace(build(name, effective),
                        based_on=base_name, declared=tuple(sorted(own)))
        resolved[name] = style
        return style

    for style_name in raw:
        resolve(style_name)
    return resolved


def _color_swatch(name: str, value) -> ColorSwatch:
    """色票載入：dict 形（cmyk／hex／note）；舊形態 hex 字串照載為純記錄色票。"""
    ctx = f"colors[{name}]"
    if isinstance(value, str):
        return ColorSwatch(name=name, hex=_swatch_hex(value, ctx))
    if not isinstance(value, dict):
        raise TemplateError(f"{ctx} 須為 hex 字串或色票物件，得到 {value!r}")
    cmyk = value.get("cmyk")
    hex_value = value.get("hex")
    return ColorSwatch(
        name=name,
        cmyk=None if cmyk is None else _swatch_cmyk(cmyk, ctx),
        hex=None if hex_value is None else _swatch_hex(hex_value, ctx),
        note=value.get("note"),
    )


def _parse_auto_toc(data) -> Optional[AutoTocSpec]:
    """auto_toc 區塊解析（缺即 None）；葉模組拋的 ValueError 改包成 TemplateError。"""
    return None if data is None else _check(auto_toc_from_dict, data)


def _check(fn, arg):
    """跑葉模組的守門，把其 ValueError 統一成模版錯誤型別（對外錯誤型別不變）。"""
    try:
        return fn(arg)
    except TemplateError:
        raise
    except ValueError as e:
        raise TemplateError(str(e)) from e


def template_from_dict(data) -> Template:
    if not isinstance(data, dict):
        raise TemplateError("模版必須是 JSON 物件")
    if data.get("schema") != SCHEMA_ID:
        raise TemplateError(f"schema 不符：需要 {SCHEMA_ID}，得到 {data.get('schema')!r}")
    for key in ("name", "page", "paragraph_styles", "character_styles", "masters"):
        if key not in data:
            raise TemplateError(f"模版缺 {key} 區塊")
    page = data["page"]
    template = Template(
        name=str(data["name"]),
        page_width_mm=float(_require(page, "width_mm", "page")),
        page_height_mm=float(_require(page, "height_mm", "page")),
        colors={name: _color_swatch(name, v)
                for name, v in data.get("colors", {}).items()},
        paragraph_styles=_resolve_styles(
            data["paragraph_styles"], PARAGRAPH_STYLE_FIELDS,
            _paragraph_style, "paragraph_styles"),
        character_styles=_resolve_styles(
            data["character_styles"], CHARACTER_STYLE_FIELDS,
            _character_style, "character_styles"),
        masters={name: _master(name, d) for name, d in data["masters"].items()},
        md_mapping=dict(data.get("md_mapping", {})),
        md_inline_mapping=dict(data.get("md_inline_mapping", {})),
        default_master=str(data.get("default_master", "")),
        default_cover=str(data.get("default_cover", "")),
        auto_toc=_parse_auto_toc(data.get("auto_toc")),
    )
    _check(check_auto_toc, template)
    if template.default_master and template.default_master not in template.masters:
        raise TemplateError(
            f"default_master「{template.default_master}」不存在於 masters")
    if template.default_cover and template.default_cover not in template.masters:
        raise TemplateError(
            f"default_cover「{template.default_cover}」不存在於 masters")
    for mname, master in template.masters.items():
        if master.toc and master.toc.page_no_style not in template.character_styles:
            raise TemplateError(
                f"masters[{mname}].toc 引用的頁碼字元樣式"
                f"「{master.toc.page_no_style}」不存在於 character_styles"
            )
    for kind, styles_map in (("paragraph_styles", template.paragraph_styles),
                             ("character_styles", template.character_styles)):
        for sname, style in styles_map.items():
            check_color_ref(template.colors, style, f"{kind}[{sname}]")
    return template


def load_template(path) -> Template:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise TemplateError(f"讀取模版失敗 {path}：{e}") from e
    return template_from_dict(data)


def _style_to_dict(style) -> dict:
    """樣式 → 宣告 dict：只寫 declared 欄位＋based_on（繼承宣告保真，Sprint 70）。"""
    out = {}
    if style.based_on is not None:
        out["based_on"] = style.based_on
    for f in style.declared:
        out[f] = getattr(style, f)
    return out


def _swatch_to_dict(swatch: ColorSwatch) -> dict:
    """色票 → dict（一律結構化形；舊字串形載入後另存即單向升級）。"""
    out = {}
    if swatch.cmyk is not None:
        out["cmyk"] = list(swatch.cmyk)
    if swatch.hex is not None:
        out["hex"] = swatch.hex
    if swatch.note is not None:
        out["note"] = swatch.note
    return out


def _footer_item_to_dict(item: FooterItem) -> dict:
    out = {
        "style": item.style,
        "source": item.source,
        "baseline_from_top_pt": item.baseline_from_top_pt,
        "outer_offset_pt": item.outer_offset_pt,
        "pages": item.pages,
    }
    if item.text is not None:  # 無覆寫時不寫此鍵（既有模版原樣往返）
        out["text"] = item.text
    return out


def _frame_to_dict(f: FrameSpec) -> dict:
    out = {"kind": f.kind, "cmyk": list(f.cmyk),
           "line_width_pt": f.line_width_pt, "pad_pt": f.pad_pt}
    if f.pad_v_pt is not None:
        out["pad_v_pt"] = f.pad_v_pt
    return out


def _rule_to_dict(r: RuleSpec) -> dict:
    return {"kind": r.kind, "y_from_top_pt": r.y_from_top_pt, "cmyk": list(r.cmyk),
            "line_width_pt": r.line_width_pt, "dash_on_pt": r.dash_on_pt,
            "dash_off_pt": r.dash_off_pt, "bleed_extend_pt": r.bleed_extend_pt,
            "break_before_pt": r.break_before_pt, "break_after_pt": r.break_after_pt}


def _toc_to_dict(t: TocSpec) -> dict:
    return {"page_no_style": t.page_no_style,
            "page_no_bottom_pt": t.page_no_bottom_pt,
            "leader_width_pt": t.leader_width_pt,
            "leader_gap_pt": t.leader_gap_pt,
            "leader_cmyk": list(t.leader_cmyk)}


def _figure_to_dict(f: FigureSpec) -> dict:
    out = {"kind": f.kind, "top_from_top_pt": f.top_from_top_pt,
           "bottom_from_top_pt": f.bottom_from_top_pt, "cmyk": list(f.cmyk),
           "line_width_pt": f.line_width_pt, "dash_on_pt": f.dash_on_pt,
           "dash_off_pt": f.dash_off_pt}
    if f.note is not None:
        out["note"] = f.note
    return out


def _master_to_dict(m: MasterPage) -> dict:
    out = {
        "margins_mm": {"top": m.margins.top_mm, "bottom": m.margins.bottom_mm,
                       "outer": m.margins.outer_mm, "inner": m.margins.inner_mm},
        "grid": {"chars_per_line": m.grid.chars_per_line,
                 "lines_per_page": m.grid.lines_per_page,
                 "char_advance_pt": m.grid.char_advance_pt,
                 "line_pitch_pt": m.grid.line_pitch_pt,
                 "base_size_pt": m.grid.base_size_pt},
        "mirror": m.mirror,
    }
    if m.footer:
        out["footer"] = {n: _footer_item_to_dict(it) for n, it in m.footer.items()}
    if m.frame:
        out["frame"] = _frame_to_dict(m.frame)
    if m.rule:
        out["rule"] = _rule_to_dict(m.rule)
    if m.toc:
        out["toc"] = _toc_to_dict(m.toc)
    if m.figure:
        out["figure"] = _figure_to_dict(m.figure)
    if m.evidence is not None:
        out["evidence"] = m.evidence
    if m.note is not None:
        out["note"] = m.note
    return out


def template_to_dict(template: Template) -> dict:
    """Template → 模版 JSON dict（template_from_dict 的逆，round-trip 相等；Sprint 70）。

    樣式只寫 declared 欄位＋based_on（不把繼承效值寫死成覆寫）；主版與 spec 全欄位
    鏡射載入層。供 save_template 落檔（§4.3 人類可讀序列化）。
    """
    out = {
        "schema": SCHEMA_ID,
        "name": template.name,
        "page": {"width_mm": template.page_width_mm,
                 "height_mm": template.page_height_mm},
        "colors": {n: _swatch_to_dict(sw) for n, sw in template.colors.items()},
        "paragraph_styles": {n: _style_to_dict(st)
                             for n, st in template.paragraph_styles.items()},
        "character_styles": {n: _style_to_dict(st)
                             for n, st in template.character_styles.items()},
        "masters": {n: _master_to_dict(m) for n, m in template.masters.items()},
        "md_mapping": dict(template.md_mapping),
        "md_inline_mapping": dict(template.md_inline_mapping),
    }
    if template.default_master:  # 未宣告者不寫出空鍵（round-trip 不變形）
        out["default_master"] = template.default_master
    if template.default_cover:
        out["default_cover"] = template.default_cover
    if template.auto_toc:
        out["auto_toc"] = _auto_toc_to_dict(template.auto_toc)
    return out


def _auto_toc_to_dict(spec) -> dict:
    """AutoTocSpec → JSON dict（層級鍵轉回字串；選配欄位空值不寫出）。"""
    out = {"master": spec.master,
           "entry_styles": {str(k): v for k, v in sorted(spec.entry_styles.items())}}
    if spec.heading:
        out["heading"] = spec.heading
        out["heading_style"] = spec.heading_style
    if spec.no_page_levels:
        out["no_page_levels"] = list(spec.no_page_levels)
    return out


def save_template(template: Template, path) -> None:
    """模版另存為人類可讀 JSON（utf-8、ensure_ascii=False、indent=1 承 Sprint 23 慣例）。"""
    Path(path).write_text(
        json.dumps(template_to_dict(template), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
