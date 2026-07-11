"""三層樣式模型（PLAN §4.1）：段落樣式、字元樣式、主版，與模版載入。

模版是人類可讀 JSON（cjkfolio/template@1）。本層只承載參數，
幾何推導在 layout、字型解析在 fonts。系統邊界驗證，快速失敗。
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SCHEMA_ID = "cjkfolio/template@1"


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
    source_font: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class CharacterStyle:
    name: str
    font_family: str
    font_weight: str
    size_pt: float
    source_font: Optional[str] = None
    note: Optional[str] = None


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


@dataclass(frozen=True)
class MasterPage:
    name: str
    margins: Margins
    grid: Grid
    mirror: bool = True  # 對開鏡像（奇數書頁書口在右；奇偶依書頁號）
    footer: dict = field(default_factory=dict)  # name → FooterItem
    frame: Optional[FrameSpec] = None  # 向量裝飾框（v1：CIP 細框；None＝不畫框）
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
    return FrameSpec(
        kind=kind,
        cmyk=tuple(float(v) for v in cmyk),
        line_width_pt=float(d.get("line_width_pt", 0.5)),
        pad_pt=float(d.get("pad_pt", 6.0)),
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
        evidence=d.get("evidence"),
        note=d.get("note"),
    )


def template_from_dict(data) -> Template:
    if not isinstance(data, dict):
        raise TemplateError("模版必須是 JSON 物件")
    if data.get("schema") != SCHEMA_ID:
        raise TemplateError(f"schema 不符：需要 {SCHEMA_ID}，得到 {data.get('schema')!r}")
    for key in ("name", "page", "paragraph_styles", "character_styles", "masters"):
        if key not in data:
            raise TemplateError(f"模版缺 {key} 區塊")
    page = data["page"]
    return Template(
        name=str(data["name"]),
        page_width_mm=float(_require(page, "width_mm", "page")),
        page_height_mm=float(_require(page, "height_mm", "page")),
        colors=dict(data.get("colors", {})),
        paragraph_styles={
            name: _paragraph_style(name, d) for name, d in data["paragraph_styles"].items()
        },
        character_styles={
            name: _character_style(name, d) for name, d in data["character_styles"].items()
        },
        masters={name: _master(name, d) for name, d in data["masters"].items()},
        md_mapping=dict(data.get("md_mapping", {})),
        md_inline_mapping=dict(data.get("md_inline_mapping", {})),
    )


def load_template(path) -> Template:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise TemplateError(f"讀取模版失敗 {path}：{e}") from e
    return template_from_dict(data)
