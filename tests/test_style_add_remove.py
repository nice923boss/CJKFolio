"""樣式新增／刪除（cjkfolio/style_editing.py＋session 整合，Sprint 69）。

§4.3「模版管理：新增」與 Phase 3 DoD「從零建立一套新書樣式模版」的資料面地基：
add_paragraph_style／add_character_style（宣告形同模版 JSON：選配 based_on 承基底、
根樣式必填守門、名稱衝突 TemplateError）、remove_paragraph_style／remove_character_style
（模版內參照守門：based_on 子孫、md_mapping／md_inline_mapping、主版 footer／toc 引用
即拒；文件仍用該樣式者由 session 全文重排 KeyError 快速失敗、狀態不變）。
session add_*／remove_* 入統一 undo 歷史。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.session import EditSession
from cjkfolio.style_editing import (
    add_character_style,
    add_paragraph_style,
    remove_character_style,
    remove_paragraph_style,
    set_paragraph_style,
)
from cjkfolio.styles import TemplateError, load_template

ROOT = Path(__file__).resolve().parents[1]

BODY = "內文-明體直排"
EMPH = "內文強調-明體W9"
NEW = "自擬-新樣式"


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _bodies(*texts: str, style: str = BODY):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": t, "style": style} for t in texts],
    })


# ---------- add：新增樣式（純模版層）----------

def test_add_root_paragraph_style(template):
    out = add_paragraph_style(template, NEW, {
        "font_family": "思源宋體 TC", "font_weight": "regular", "size_pt": 10.0})
    st = out.paragraph_styles[NEW]
    assert (st.font_family, st.size_pt) == ("思源宋體 TC", 10.0)
    assert st.based_on is None and "size_pt" in st.declared
    assert st.indent_chars == 2  # 未宣告欄位取 dataclass 預設
    assert NEW not in template.paragraph_styles  # 原模版不可變


def test_add_root_missing_required_raises(template):
    with pytest.raises(TemplateError):
        add_paragraph_style(template, NEW, {"size_pt": 10.0})  # 缺 font_family 等


def test_add_child_inherits_base(template):
    out = add_paragraph_style(template, NEW, {"based_on": BODY, "size_pt": 9.0})
    st = out.paragraph_styles[NEW]
    parent = template.paragraph_styles[BODY]
    assert st.size_pt == 9.0 and st.font_family == parent.font_family
    assert st.based_on == BODY and st.declared == ("size_pt",)


def test_add_child_unknown_base_raises(template):
    with pytest.raises(TemplateError):
        add_paragraph_style(template, NEW, {"based_on": "不存在"})


def test_add_name_collision_or_empty_raises(template):
    with pytest.raises(TemplateError):
        add_paragraph_style(template, BODY, {"based_on": BODY})
    with pytest.raises(TemplateError):
        add_paragraph_style(template, "", {"based_on": BODY})


def test_add_character_style(template):
    out = add_character_style(template, NEW, {"based_on": EMPH, "size_pt": 9.0})
    st = out.character_styles[NEW]
    assert st.size_pt == 9.0 and st.based_on == EMPH
    with pytest.raises(TemplateError):
        add_character_style(template, EMPH, {"based_on": EMPH})  # 名稱衝突


def test_added_child_joins_cascade(template):
    t = add_paragraph_style(template, NEW, {"based_on": BODY})
    out = set_paragraph_style(t, BODY, {"size_pt": 14.0})
    assert out.paragraph_styles[NEW].size_pt == 14.0  # 新增子樣式參與級聯


# ---------- remove：刪除樣式（模版內參照守門）----------

def test_remove_leaf_paragraph_style(template):
    t = add_paragraph_style(template, NEW, {"based_on": BODY})
    out = remove_paragraph_style(t, NEW)
    assert NEW not in out.paragraph_styles
    assert t.paragraph_styles[NEW].based_on == BODY  # 原模版不可變


def test_remove_unknown_raises_keyerror(template):
    with pytest.raises(KeyError):
        remove_paragraph_style(template, "不存在")


def test_remove_base_with_children_blocked(template):
    t = add_paragraph_style(template, NEW, {"based_on": BODY})
    with pytest.raises(TemplateError):
        remove_paragraph_style(t, BODY)  # 有子樣式承基底


def test_remove_md_mapping_referenced_blocked(template):
    assert BODY in template.md_mapping.values()  # 前提：內文為 md 對映目標
    with pytest.raises(TemplateError):
        remove_paragraph_style(template, BODY)


def test_remove_char_style_referenced_by_master_blocked(template):
    footer_styles = {item.style for m in template.masters.values()
                     for item in m.footer.values()}
    used = next(iter(footer_styles))  # 任一頁腳引用的字元樣式
    with pytest.raises(TemplateError):
        remove_character_style(template, used)


def test_remove_char_style_leaf_ok(template):
    t = add_character_style(template, NEW, {"based_on": EMPH})
    out = remove_character_style(t, NEW)
    assert NEW not in out.character_styles


# ---------- session 整合（統一 undo 歷史＋文件使用中快速失敗）----------

def test_session_add_use_and_undo(template):
    s = EditSession(_bodies("三房兩廳"), template)
    res = s.add_para_style(NEW, {"based_on": BODY, "size_pt": 9.0})
    assert res is not None and NEW in s.template.paragraph_styles
    s.apply_para_style(s.cursor, NEW)  # 新樣式立即可套用
    assert s.layout.pages[0].placed[0].style == NEW
    s.undo()  # 回套用
    s.undo()  # 回新增
    assert NEW not in s.template.paragraph_styles
    s.redo()
    assert NEW in s.template.paragraph_styles


def test_session_remove_style_in_use_fast_fails(template):
    t = add_paragraph_style(template, NEW, {"based_on": BODY})
    s = EditSession(_bodies("三房兩廳", style=NEW), t)
    with pytest.raises(KeyError):  # 文件仍用該樣式 → 全文重排快速失敗
        s.remove_para_style(NEW)
    assert NEW in s.template.paragraph_styles and not s.can_undo()  # 狀態不變


def test_session_remove_unused_style_and_undo(template):
    t = add_paragraph_style(template, NEW, {"based_on": BODY})
    s = EditSession(_bodies("三房兩廳"), t)
    s.remove_para_style(NEW)
    assert NEW not in s.template.paragraph_styles
    s.undo()
    assert NEW in s.template.paragraph_styles
