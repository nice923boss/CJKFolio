"""三層樣式模型（cjkfolio.styles）：模版載入與驗證。"""
from pathlib import Path

import pytest

from cjkfolio.styles import TemplateError, load_template, template_from_dict

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
