"""模版序列化落檔（cjkfolio/styles.py template_to_dict／save_template，Sprint 70）。

§4.3「序列化格式：人類可讀 JSON」與 §6 Phase 3「書系模版另存」的另存半邊，關
GAPS #34 (c)（樣式編輯後可落檔）。round-trip 鐵律＝template_from_dict(template_to_dict(t))
與 t 完全相等（真實內建模版全 A〜G 主版〔footer／frame／rule／toc／figure〕覆蓋）；
樣式只寫 declared 欄位＋based_on（繼承宣告保真，不把承來的效值寫死成覆寫）。
測試素材：內建模版（量測參數，非參考書內容）＋自擬樣式。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.style_editing import add_paragraph_style, set_paragraph_style
from cjkfolio.styles import (
    load_template,
    save_template,
    template_from_dict,
    template_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"

BODY = "內文-明體直排"
CHILD = "內文-子樣式測試"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def test_builtin_roundtrip_equal(template):
    assert template_from_dict(template_to_dict(template)) == template


def test_to_dict_idempotent(template):
    d1 = template_to_dict(template)
    d2 = template_to_dict(template_from_dict(d1))
    assert d1 == d2


def test_to_dict_has_schema_and_page(template):
    d = template_to_dict(template)
    assert d["schema"] == "cjkfolio/template@1"
    assert d["page"] == {"width_mm": 148.0, "height_mm": 210.0}


def test_child_style_serializes_declared_only(template):
    t = add_paragraph_style(template, CHILD, {"based_on": BODY, "size_pt": 9.5})
    d = template_to_dict(t)
    assert d["paragraph_styles"][CHILD] == {"based_on": BODY, "size_pt": 9.5}


def test_edited_style_roundtrip_keeps_inheritance(template):
    t = add_paragraph_style(template, CHILD, {"based_on": BODY})
    t = set_paragraph_style(t, CHILD, {"indent_chars": 0})  # 編輯成覆寫
    t2 = template_from_dict(template_to_dict(t))
    assert t2 == t
    t3 = set_paragraph_style(t2, BODY, {"size_pt": 14.0})  # 重載後級聯仍活
    assert t3.paragraph_styles[CHILD].size_pt == 14.0
    assert t3.paragraph_styles[CHILD].indent_chars == 0


def test_save_and_load_file(tmp_path, template):
    path = tmp_path / "自擬模版.json"
    save_template(template, path)
    text = path.read_text(encoding="utf-8")
    assert "內文-明體直排" in text  # ensure_ascii=False 人類可讀
    assert json.loads(text)["schema"] == "cjkfolio/template@1"
    assert load_template(path) == template


def test_save_edited_template_roundtrip(tmp_path, template):
    t = add_paragraph_style(template, CHILD, {"based_on": BODY, "size_pt": 9.0})
    t = set_paragraph_style(t, BODY, {"note": "自擬編輯後另存"})
    path = tmp_path / "edited.json"
    save_template(t, path)
    assert load_template(path) == t
