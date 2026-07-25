"""色票管理（Sprint 76，§4.3／§6 Phase 3「色票管理」）。

ColorSwatch 結構化色票（名稱→CMYK 印刷值＋hex 螢幕參考）＋樣式選配 color 引用
（字元樣式 > 段落樣式 > 預設暖黑 K92）＋style_editing 色票 CRUD＋session 統一
undo＋兩後端文字色同源（PDF fill 算符切色、PNG 灰值 255×(1−k) 只取 k）。
驗證一律走 PyMuPDF／PIL 獨立路徑（Gate 4）。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.session import EditSession
from cjkfolio.style_editing import (
    add_color,
    add_paragraph_style,
    remove_color,
    set_color,
    set_character_style,
    set_paragraph_style,
)
from cjkfolio.styles import (
    DEFAULT_TEXT_CMYK,
    ColorSwatch,
    TemplateError,
    load_template,
    resolve_text_cmyk,
    template_from_dict,
    template_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

BODY = "內文-明體直排"
EMPH = "內文強調-明體W9"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def _template_dict(template) -> dict:
    """以內建模版為底的可改寫 dict（走載入路徑驗證）。"""
    return template_to_dict(template)


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


# ---------- 載入層（styles）----------

def test_load_structured_swatch(template):
    """內建模版 colors 升級結構化：暖黑帶 CMYK 印刷值＋hex 量測參考（§1／§9）。"""
    sw = template.colors["暖黑"]
    assert isinstance(sw, ColorSwatch)
    assert sw.name == "暖黑"
    assert sw.cmyk == (0.0, 0.0, 0.0, 0.92)
    assert sw.hex == "#231f20"


def test_load_legacy_hex_string_compat(template):
    """舊形態 colors 值為 hex 字串：照載為 hex-only 色票（cmyk None＝不可印刷引用）。"""
    data = _template_dict(template)
    data["colors"] = {"舊紙白": "#ffffff"}
    t = template_from_dict(data)
    sw = t.colors["舊紙白"]
    assert sw.hex == "#ffffff" and sw.cmyk is None


@pytest.mark.parametrize("bad", [
    [0.0, 0.0, 0.92],          # 長度不足
    [0.0, 0.0, 0.0, 1.2],      # 越界
    [0.0, 0.0, 0.0, -0.1],     # 負值
    ["x", 0.0, 0.0, 0.9],      # 非數
])
def test_bad_cmyk_rejected(template, bad):
    data = _template_dict(template)
    data["colors"] = {"壞色": {"cmyk": bad}}
    with pytest.raises(TemplateError):
        template_from_dict(data)


def test_bad_hex_rejected(template):
    data = _template_dict(template)
    data["colors"] = {"壞色": {"hex": "231f20"}}  # 缺 #
    with pytest.raises(TemplateError):
        template_from_dict(data)


def test_style_color_unknown_swatch_rejected(template):
    data = _template_dict(template)
    data["paragraph_styles"][BODY]["color"] = "不存在的色票"
    with pytest.raises(TemplateError):
        template_from_dict(data)


def test_style_color_needs_cmyk(template):
    """樣式引用 hex-only 色票（無印刷值）快速失敗（§9 全 CMYK）。"""
    data = _template_dict(template)
    data["colors"]["螢幕灰"] = {"hex": "#888888"}
    data["character_styles"][EMPH]["color"] = "螢幕灰"
    with pytest.raises(TemplateError):
        template_from_dict(data)


def test_color_field_loads_and_inherits(template):
    """樣式 color 載入為平面欄位；子樣式 based_on 自動承 color（欄位表繼承）。"""
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57]}
    data["paragraph_styles"][BODY]["color"] = "淡墨"
    data["paragraph_styles"]["內文-子樣式"] = {"based_on": BODY, "indent_chars": 0}
    t = template_from_dict(data)
    assert t.paragraph_styles[BODY].color == "淡墨"
    assert t.paragraph_styles["內文-子樣式"].color == "淡墨"  # 繼承
    assert "color" not in t.paragraph_styles["內文-子樣式"].declared


# ---------- 文字色解析（單一事實來源）----------

def test_resolve_text_cmyk_priority(template):
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57]}
    data["colors"]["點灰"] = {"cmyk": [0.0, 0.0, 0.0, 0.3]}
    data["paragraph_styles"][BODY]["color"] = "淡墨"
    data["character_styles"][EMPH]["color"] = "點灰"
    t = template_from_dict(data)
    para, char = t.paragraph_styles[BODY], t.character_styles[EMPH]
    plain = t.paragraph_styles["引文-仿宋語錄"]
    assert resolve_text_cmyk(t, plain) == DEFAULT_TEXT_CMYK          # 無 color → 預設 K92
    assert resolve_text_cmyk(t, para) == (0.0, 0.0, 0.0, 0.57)       # 段落色
    assert resolve_text_cmyk(t, char, para) == (0.0, 0.0, 0.0, 0.3)  # 字元 > 段落
    assert resolve_text_cmyk(t, None, para) == (0.0, 0.0, 0.0, 0.57)  # None 略過


# ---------- 序列化（round-trip 鐵律）----------

def test_roundtrip_structured_colors(template):
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57], "note": "自擬"}
    data["paragraph_styles"][BODY]["color"] = "淡墨"
    t = template_from_dict(data)
    d = template_to_dict(t)
    assert template_from_dict(d) == t                     # round-trip 相等
    assert template_to_dict(template_from_dict(d)) == d   # 冪等
    assert d["paragraph_styles"][BODY]["color"] == "淡墨"  # declared 序列化


def test_legacy_string_upgrades_to_dict_form(template):
    """舊字串形載入後 to_dict 一律寫結構化 dict 形（單向升級），重載相等。"""
    data = _template_dict(template)
    data["colors"] = {"舊紙白": "#ffffff"}
    t = template_from_dict(data)
    d = template_to_dict(t)
    assert d["colors"]["舊紙白"] == {"hex": "#ffffff"}
    assert template_from_dict(d) == t


# ---------- style_editing：樣式 color 欄位 ----------

def test_set_para_style_color_takes_effect(template):
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57]}
    t = template_from_dict(data)
    out = set_paragraph_style(t, BODY, {"color": "淡墨"})
    assert out.paragraph_styles[BODY].color == "淡墨"
    assert "color" in out.paragraph_styles[BODY].declared
    assert set_paragraph_style(out, BODY, {"color": "淡墨"}) is out  # 等值 no-op
    cleared = set_paragraph_style(out, BODY, {"color": None})       # 清除回預設
    assert cleared.paragraph_styles[BODY].color is None


def test_set_style_color_ref_validated(template):
    with pytest.raises(TemplateError):
        set_paragraph_style(template, BODY, {"color": "不存在的色票"})
    data = _template_dict(template)
    data["colors"]["螢幕灰"] = {"hex": "#888888"}
    t = template_from_dict(data)
    with pytest.raises(TemplateError):
        set_character_style(t, EMPH, {"color": "螢幕灰"})  # hex-only 不可印刷引用


def test_add_style_with_color_validated(template):
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57]}
    t = template_from_dict(data)
    out = add_paragraph_style(t, "註記-淡墨", {"based_on": BODY, "color": "淡墨"})
    assert out.paragraph_styles["註記-淡墨"].color == "淡墨"
    with pytest.raises(TemplateError):
        add_paragraph_style(t, "壞註記", {"based_on": BODY, "color": "不存在的色票"})


def test_cascade_on_base_color_change(template):
    """改基底 color 級聯至未覆寫子孫（Sprint 68 級聯，欄位表自動涵蓋 color）。"""
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57]}
    data["paragraph_styles"]["內文-子樣式"] = {"based_on": BODY, "indent_chars": 0}
    t = template_from_dict(data)
    out = set_paragraph_style(t, BODY, {"color": "淡墨"})
    assert out.paragraph_styles["內文-子樣式"].color == "淡墨"


# ---------- style_editing：色票 CRUD ----------

def test_add_color_and_guards(template):
    out = add_color(template, "淡墨", cmyk=(0.0, 0.0, 0.0, 0.57), note="自擬")
    sw = out.colors["淡墨"]
    assert sw.cmyk == (0.0, 0.0, 0.0, 0.57) and sw.note == "自擬"
    assert template.colors.get("淡墨") is None  # 原模版不可變
    with pytest.raises(TemplateError):
        add_color(template, "暖黑", cmyk=(0.0, 0.0, 0.0, 0.5))  # 同名衝突
    with pytest.raises(TemplateError):
        add_color(template, "", cmyk=(0.0, 0.0, 0.0, 0.5))      # 空名
    with pytest.raises(TemplateError):
        add_color(template, "空值色")                             # cmyk 與 hex 全缺


def test_set_color_and_guards(template):
    out = set_color(template, "暖黑", {"cmyk": (0.0, 0.0, 0.0, 0.9)})
    assert out.colors["暖黑"].cmyk == (0.0, 0.0, 0.0, 0.9)
    assert out.colors["暖黑"].hex == "#231f20"  # 未列欄位保留
    assert set_color(template, "暖黑", {}) is template                          # 空變更 no-op
    assert set_color(template, "暖黑", {"cmyk": (0.0, 0.0, 0.0, 0.92)}) is template  # 等值 no-op
    with pytest.raises(KeyError):
        set_color(template, "不存在的色票", {"cmyk": (0.0, 0.0, 0.0, 0.5)})
    with pytest.raises(TemplateError):
        set_color(template, "暖黑", {"cmyk": (0.0, 0.0, 0.0, 1.5)})  # 越界


def test_remove_color_guards(template):
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57]}
    data["paragraph_styles"][BODY]["color"] = "淡墨"
    t = template_from_dict(data)
    with pytest.raises(TemplateError):
        remove_color(t, "淡墨")  # 樣式引用中
    with pytest.raises(KeyError):
        remove_color(t, "不存在的色票")
    out = remove_color(t, "紙白")  # 未被引用可刪
    assert "紙白" not in out.colors


# ---------- session：色票編輯入統一 undo ----------

def test_session_update_color_undo_redo(template):
    doc = make_doc([{"text": "留白是安放的開始。", "style": BODY}])
    session = EditSession(doc, template)
    result = session.update_color("暖黑", {"cmyk": (0.0, 0.0, 0.0, 0.9)})
    assert result is not None
    assert session.template.colors["暖黑"].cmyk == (0.0, 0.0, 0.0, 0.9)
    assert session.update_color("暖黑", {"cmyk": (0.0, 0.0, 0.0, 0.9)}) is None  # no-op 不入歷史
    assert session.undo() is not None
    assert session.template.colors["暖黑"].cmyk == (0.0, 0.0, 0.0, 0.92)
    assert session.redo() is not None
    assert session.template.colors["暖黑"].cmyk == (0.0, 0.0, 0.0, 0.9)


def test_session_add_color_then_style_color(template):
    doc = make_doc([{"text": "留白是安放的開始。", "style": BODY}])
    session = EditSession(doc, template)
    assert session.add_color("淡墨", cmyk=(0.0, 0.0, 0.0, 0.57)) is not None
    assert session.update_para_style(BODY, {"color": "淡墨"}) is not None
    assert session.template.paragraph_styles[BODY].color == "淡墨"
    with pytest.raises(TemplateError):
        session.remove_color("淡墨")  # 樣式引用中，狀態不變
    assert session.template.colors["淡墨"].cmyk == (0.0, 0.0, 0.0, 0.57)
    session.undo()  # 回未掛 color
    assert session.template.paragraph_styles[BODY].color is None
    assert session.remove_color("淡墨") is not None  # 已無引用可刪，入歷史
    assert "淡墨" not in session.template.colors
    session.undo()
    assert session.template.colors["淡墨"].cmyk == (0.0, 0.0, 0.0, 0.57)


# ---------- 兩後端（PyMuPDF／PIL 獨立驗證，Gate 4）----------

def _colored_template(template):
    """自擬雙色票模版：段落色 淡墨 K57＋字元色 點灰 K30。"""
    data = _template_dict(template)
    data["colors"]["淡墨"] = {"cmyk": [0.0, 0.0, 0.0, 0.57]}
    data["colors"]["點灰"] = {"cmyk": [0.0, 0.0, 0.0, 0.3]}
    data["paragraph_styles"]["註記-淡墨"] = {"based_on": BODY, "color": "淡墨"}
    data["character_styles"][EMPH]["color"] = "點灰"
    return template_from_dict(data)


@needs_fonts
def test_pdf_text_fill_color_ops(template, tmp_path):
    from cjkfolio.pdf_writer import export_pdf
    fitz = pytest.importorskip("fitz")

    t = _colored_template(template)
    doc = make_doc([
        {"text": "留白是安放的開始。", "style": BODY},
        {"text": "整理是一場對話。", "style": "註記-淡墨"},
        {"text": "安放", "style": BODY,
         "runs": [{"text": "安", "char_style": EMPH}, {"text": "放"}]},
    ])
    out = tmp_path / "colored.pdf"
    result = export_pdf(doc, t, out, footer=False)
    assert result.violations == []
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert "0 0 0 0.92 k" in content  # 預設 K92（prologue）
    assert "0 0 0 0.57 k" in content  # 段落色票
    assert "0 0 0 0.3 k" in content   # 字元色票（覆寫段落）
    # Gate 4 第二路：PyMuPDF texttrace 獨立回報 fill 色（fitz 自帶 CMYK→sRGB
    # 色彩管理轉換，數值非 1−k 直換）：恰三種填色、灰值嚴格遞增＝K92 最暗 →
    # K57 → K30 最亮（暗序與 K 遞減一致）
    fills = sorted({round(s["color"][0], 2)
                    for s in pdf[0].get_texttrace() if s["type"] == 0})
    assert len(fills) == 3


@needs_fonts
def test_pdf_no_extra_fill_ops_without_colors(template, tmp_path):
    """無 color 樣式的文件：內容流僅 prologue 一個 fill 算符（既有輸出形態不變）。"""
    from cjkfolio.pdf_writer import export_pdf
    fitz = pytest.importorskip("fitz")

    doc = make_doc([{"text": "留白是安放的開始。", "style": BODY}])
    out = tmp_path / "plain.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert content.count(" k\n") + content.count(" k ") == 1  # 只有 prologue K92


@needs_fonts
def test_png_text_ink_levels(template, tmp_path):
    from PIL import Image

    from cjkfolio.layout import layout_document
    from cjkfolio.render import line_axis_x_pt, render_document

    t = _colored_template(template)
    doc = make_doc([
        {"text": "留白是安放的開始。", "style": BODY},
        {"text": "整理是一場對話。", "style": "註記-淡墨"},
    ])
    result = render_document(doc, t, tmp_path, footer=False)
    layout = layout_document(doc, t)
    img = Image.open(result.paths[0])
    scale = 150 / 72.0
    master = t.masters["A-內文版"]

    def deepest_ink(placed):
        axis = line_axis_x_pt(t, master, placed.slot, 1)
        x0 = round((axis - 5.0) * scale)
        x1 = round((axis + 5.0) * scale)
        band = img.crop((x0, 0, x1, img.height))
        return tuple(lo for lo, _ in band.getextrema())  # 帶內各分量最深墨值

    # 畫布自 Sprint 137 為 RGB：單 K 著色三分量同值（＝維持中性灰，不偏色）
    body_line, note_line = layout.pages[0].placed[0], layout.pages[0].placed[1]
    assert deepest_ink(body_line) == (round(255 * (1 - 0.92)),) * 3  # 預設 K92 → 20
    assert deepest_ink(note_line) == (round(255 * (1 - 0.57)),) * 3  # 淡墨 K57 → 110
