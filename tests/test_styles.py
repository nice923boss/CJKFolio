"""三層樣式模型（cjkfolio.styles）：模版載入與驗證。"""
import json
from pathlib import Path

import pytest

from cjkfolio.styles import (
    FrameSpec,
    RuleSpec,
    TemplateError,
    TocSpec,
    load_template,
    template_from_dict,
)

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def test_template_three_layers_complete(template):
    # §4.2：15 段落樣式、9 字元樣式、7 主版
    assert len(template.paragraph_styles) == 15
    assert len(template.character_styles) == 9
    assert len(template.masters) == 7


def test_body_style_matches_measured_values(template):
    body = template.paragraph_styles["內文-明體直排"]
    assert body.size_pt == 11.5
    assert body.font_family == "思源宋體 TC"
    assert body.font_weight == "regular"
    assert body.indent_chars == 2
    assert body.para_gap_slots == 1
    assert body.source_font == "DFMingStd-W3"


def test_master_a_geometry_from_measurements(template):
    a = template.masters["A-內文版"]
    assert a.grid.chars_per_line == 32
    assert a.grid.lines_per_page == 13
    assert a.grid.char_advance_pt == 12.08
    assert a.grid.line_pitch_pt == 23.0
    assert a.grid.base_size_pt == 11.5
    assert a.margins.top_mm == 32.49
    assert a.margins.outer_mm == 21.0
    assert a.mirror is True


def test_template_page_size_and_colors(template):
    assert template.page_width_mm == 148.0
    assert template.page_height_mm == 210.0
    assert template.colors["暖黑"] == "#231f20"


def test_template_md_mapping_present(template):
    m = template.md_mapping
    assert m["h1"] == "章名大標-明體W7"
    assert m["h2"] == "個案大標-NotoSans"
    assert m["h3"] == "章節小標-黑體"
    assert m["blockquote"] == "引文-仿宋語錄"
    assert m["paragraph"] == "內文-明體直排"


def test_master_a_footer_spec(template):
    footer = template.masters["A-內文版"].footer
    num = footer["page_number"]
    assert num.style == "頁碼數字-GillSans"
    assert num.source == "number"
    assert num.pages == "all"
    assert num.baseline_from_top_pt == 530.43
    title = footer["running_title"]
    assert title.source == "title"
    assert title.pages == "odd"
    assert template.masters["B-部扉"].footer == {}


def test_template_missing_masters_rejected():
    with pytest.raises(TemplateError, match="masters"):
        template_from_dict({
            "schema": "cjkfolio/template@1",
            "name": "壞模版",
            "page": {"width_mm": 148, "height_mm": 210},
            "paragraph_styles": {},
            "character_styles": {},
        })


# ---------- 向量裝飾框（Sprint 14：CIP 細框） ----------

def test_master_frame_parsing(template):
    f = template.masters["F-版權頁"].frame
    assert isinstance(f, FrameSpec)
    assert f.kind == "cip-box"
    assert f.cmyk == (0.0, 0.0, 0.0, 1.0)
    assert f.line_width_pt == 0.5
    assert f.pad_pt == 6.0
    # 非版權頁主版無框（None）
    assert template.masters["A-內文版"].frame is None
    assert template.masters["B-部扉"].frame is None


def _template_with_frame(frame_dict):
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["F-版權頁"]["frame"] = frame_dict
    return data


def test_frame_unknown_kind_rejected():
    with pytest.raises(TemplateError, match="框類型"):
        template_from_dict(_template_with_frame({"kind": "菱形雙線"}))


def test_frame_bad_cmyk_rejected():
    with pytest.raises(TemplateError, match="cmyk"):
        template_from_dict(_template_with_frame({"kind": "cip-box", "cmyk": [0, 0, 0]}))


def test_frame_defaults_when_optional_omitted():
    tpl = template_from_dict(_template_with_frame({"kind": "cip-box"}))
    f = tpl.masters["F-版權頁"].frame
    assert f.cmyk == (0.0, 0.0, 0.0, 1.0)  # 預設純黑
    assert f.line_width_pt == 0.5
    assert f.pad_pt == 6.0


# ---------- 向量裝飾線（Sprint 15：目錄水平虛線） ----------

def test_master_rule_parsing(template):
    r = template.masters["D-目錄"].rule
    assert isinstance(r, RuleSpec)
    assert r.kind == "toc-rule"
    assert r.cmyk == (0.0, 0.0, 0.0, 0.57)  # 灰 K57（參考書 p003 實測 RGB 0.427 推導）
    assert r.line_width_pt == 1.0
    assert r.dash_on_pt == 3.0 and r.dash_off_pt == 2.0  # 實測 dash pattern [3 2]
    assert r.y_from_top_pt == pytest.approx(122.46)  # 實測天頭下位置
    # 非目錄主版無虛線（None）
    assert template.masters["A-內文版"].rule is None
    assert template.masters["F-版權頁"].rule is None


def _template_with_rule(rule_dict):
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["D-目錄"]["rule"] = rule_dict
    return data


def test_rule_unknown_kind_rejected():
    with pytest.raises(TemplateError, match="線類型"):
        template_from_dict(_template_with_rule({"kind": "波浪線", "y_from_top_pt": 100}))


def test_rule_bad_cmyk_rejected():
    with pytest.raises(TemplateError, match="cmyk"):
        template_from_dict(_template_with_rule(
            {"kind": "toc-rule", "y_from_top_pt": 100, "cmyk": [0, 0]}))


def test_rule_missing_y_rejected():
    with pytest.raises(TemplateError, match="y_from_top_pt"):
        template_from_dict(_template_with_rule({"kind": "toc-rule"}))


def test_rule_defaults_when_optional_omitted():
    tpl = template_from_dict(_template_with_rule({"kind": "toc-rule", "y_from_top_pt": 100.0}))
    r = tpl.masters["D-目錄"].rule
    assert r.cmyk == (0.0, 0.0, 0.0, 1.0)  # 預設純黑
    assert r.line_width_pt == 1.0
    assert r.dash_on_pt == 3.0 and r.dash_off_pt == 2.0
    assert r.bleed_extend_pt == pytest.approx(3.0 * 72.0 / 25.4)  # 預設出血 3mm


# ---------- 目錄條目頁碼配置（Sprint 16） ----------

def test_master_toc_parsing(template):
    t = template.masters["D-目錄"].toc
    assert isinstance(t, TocSpec)
    assert t.page_no_style == "頁碼數字-GillSans"
    assert t.page_no_bottom_pt == pytest.approx(490.0)  # p003 頁碼末位底實測
    assert t.leader_width_pt == pytest.approx(0.1)      # 引導線寬實測
    assert t.leader_gap_pt == pytest.approx(2.0)
    assert t.leader_cmyk == (0.0, 0.0, 0.0, 0.92)       # 引導線同文字單 K92
    # 非目錄主版無 toc 配置
    assert template.masters["A-內文版"].toc is None


def _template_with_toc(toc_dict):
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["D-目錄"]["toc"] = toc_dict
    return data


def test_toc_missing_required_rejected():
    with pytest.raises(TemplateError, match="page_no_style"):
        template_from_dict(_template_with_toc({"page_no_bottom_pt": 490}))
    with pytest.raises(TemplateError, match="page_no_bottom_pt"):
        template_from_dict(_template_with_toc({"page_no_style": "頁碼數字-GillSans"}))


def test_toc_unknown_page_no_style_rejected():
    with pytest.raises(TemplateError, match="頁碼字元樣式"):
        template_from_dict(_template_with_toc(
            {"page_no_style": "不存在的樣式", "page_no_bottom_pt": 490}))
