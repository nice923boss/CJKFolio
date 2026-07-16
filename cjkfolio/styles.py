"""三層樣式模型（PLAN §4.1）：段落樣式、字元樣式、主版，與模版載入。

模版是人類可讀 JSON（cjkfolio/template@1）。本層只承載參數，
幾何推導在 layout、字型解析在 fonts。系統邊界驗證，快速失敗。

樣式繼承（§4.3 基底＋覆寫，Sprint 68）：樣式宣告帶 based_on 即繼承基底有效欄位、
自身宣告欄位覆寫（鏈式）；效值於載入期扁平化（消費端讀平面欄位零變更），
based_on／declared 為簿記欄位（供編輯級聯 style_editing 與後續模版序列化）。
"""
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Mapping, Optional

SCHEMA_ID = "cjkfolio/template@1"


def _opt_str(value) -> Optional[str]:
    return None if value is None else str(value)


class TemplateError(ValueError):
    """模版 JSON 不合 schema。"""


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
    "source_font": _opt_str,
    "note": _opt_str,
}

CHARACTER_STYLE_FIELDS: Mapping[str, Callable] = {
    "font_family": str,
    "font_weight": str,
    "size_pt": float,
    "source_font": _opt_str,
    "note": _opt_str,
}


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
        colors=dict(data.get("colors", {})),
        paragraph_styles=_resolve_styles(
            data["paragraph_styles"], PARAGRAPH_STYLE_FIELDS,
            _paragraph_style, "paragraph_styles"),
        character_styles=_resolve_styles(
            data["character_styles"], CHARACTER_STYLE_FIELDS,
            _character_style, "character_styles"),
        masters={name: _master(name, d) for name, d in data["masters"].items()},
        md_mapping=dict(data.get("md_mapping", {})),
        md_inline_mapping=dict(data.get("md_inline_mapping", {})),
    )
    for mname, master in template.masters.items():
        if master.toc and master.toc.page_no_style not in template.character_styles:
            raise TemplateError(
                f"masters[{mname}].toc 引用的頁碼字元樣式"
                f"「{master.toc.page_no_style}」不存在於 character_styles"
            )
    return template


def load_template(path) -> Template:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise TemplateError(f"讀取模版失敗 {path}：{e}") from e
    return template_from_dict(data)
