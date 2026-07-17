"""樣式改名（cjkfolio/style_editing.py 模版層＋editing.py 文件層＋session 整合，Sprint 75）。

§4.3 模版管理「可修改」的改名半邊（GAPS #34 (a) 改名子項）：
模版層同步所有名稱引用（樣式鍵、based_on、md_mapping／md_inline_mapping、
主版 footer／toc 頁碼樣式）；文件層同步段落 style／run char_style／文字框 style；
session 改名＝文件＋模版成對單一 undo 步。測試素材一律自擬（版權紅線）。
"""
from dataclasses import replace
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.editing import (
    DocCursor,
    rename_char_style_refs,
    rename_paragraph_style_refs,
)
from cjkfolio.session import EditSession
from cjkfolio.style_editing import (
    add_character_style,
    add_paragraph_style,
    rename_character_style,
    rename_paragraph_style,
)
from cjkfolio.styles import TemplateError, load_template

ROOT = Path(__file__).resolve().parents[1]

BODY = "內文-明體直排"
EMPH = "內文強調-明體W9"
PAGE_NO = "頁碼數字-GillSans"
NEW = "自擬-改名後"


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _doc(with_frame=False, run_style=None):
    paragraphs = [
        {"text": "第一段自擬內文。", "style": BODY},
        {"text": "引文自擬。", "style": "引文-仿宋語錄"},
    ]
    if run_style:
        paragraphs[0] = {"style": BODY, "runs": [
            {"text": "第一段"}, {"text": "強調", "char_style": run_style},
            {"text": "內文。"},
        ]}
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    }
    if with_frame:
        data["text_frames"] = [
            {"text": "框說明", "style": BODY, "page": 1, "rect": [50, 50, 120, 200]},
        ]
    return document_from_dict(data)


# ---------- 模版層：段落樣式改名 ----------

def test_rename_paragraph_updates_key_in_place(template):
    out = rename_paragraph_style(template, BODY, NEW)
    names = list(out.paragraph_styles)
    assert NEW in out.paragraph_styles and BODY not in out.paragraph_styles
    assert names.index(NEW) == list(template.paragraph_styles).index(BODY)  # 原位改名
    assert out.paragraph_styles[NEW] == replace(
        template.paragraph_styles[BODY], name=NEW)  # 僅 name 變，參數全同
    assert BODY in template.paragraph_styles  # 原模版不可變


def test_rename_paragraph_follows_based_on_and_md_mapping(template):
    with_child = add_paragraph_style(template, "自擬-子樣式",
                                     {"based_on": BODY, "size_pt": 9.0})
    out = rename_paragraph_style(with_child, BODY, NEW)
    assert out.paragraph_styles["自擬-子樣式"].based_on == NEW
    assert out.md_mapping["paragraph"] == NEW
    assert template.md_mapping["paragraph"] == BODY  # 原模版不可變


def test_rename_paragraph_same_name_noop(template):
    assert rename_paragraph_style(template, BODY, BODY) is template


def test_rename_paragraph_guards(template):
    with pytest.raises(KeyError):
        rename_paragraph_style(template, "不存在樣式", NEW)
    with pytest.raises(TemplateError):
        rename_paragraph_style(template, BODY, "引文-仿宋語錄")  # 名稱衝突
    with pytest.raises(TemplateError):
        rename_paragraph_style(template, BODY, " ")  # 空名


# ---------- 模版層：字元樣式改名 ----------

def test_rename_character_follows_all_refs(template):
    out = rename_character_style(template, PAGE_NO, NEW)
    assert NEW in out.character_styles and PAGE_NO not in out.character_styles
    for master in out.masters.values():
        for item in master.footer.values():
            assert item.style != PAGE_NO
        if master.toc is not None:
            assert master.toc.page_no_style != PAGE_NO
    toc_master = next(m for m in out.masters.values() if m.toc is not None)
    assert toc_master.toc.page_no_style == NEW
    assert any(item.style == NEW for m in out.masters.values()
               for item in m.footer.values())
    # 原模版不可變
    assert PAGE_NO in template.character_styles


def test_rename_character_follows_inline_mapping_and_based_on(template):
    with_child = add_character_style(template, "自擬-強調子",
                                     {"based_on": EMPH, "size_pt": 9.0})
    out = rename_character_style(with_child, EMPH, NEW)
    assert out.md_inline_mapping["strong"] == NEW
    assert out.md_inline_mapping["em"] == NEW
    assert out.character_styles["自擬-強調子"].based_on == NEW


def test_rename_character_guards(template):
    with pytest.raises(KeyError):
        rename_character_style(template, "不存在", NEW)
    with pytest.raises(TemplateError):
        rename_character_style(template, EMPH, PAGE_NO)  # 衝突


# ---------- 文件層：參照同步（editing.py 純函式） ----------

def test_rename_paragraph_refs_in_document_and_frames():
    doc = _doc(with_frame=True)
    out = rename_paragraph_style_refs(doc, BODY, NEW)
    assert out.paragraphs[0].style == NEW
    assert out.paragraphs[1].style == "引文-仿宋語錄"  # 非目標不動
    assert out.text_frames[0].style == NEW
    assert doc.paragraphs[0].style == BODY  # 原件不變


def test_rename_paragraph_refs_no_match_returns_original():
    doc = _doc()
    assert rename_paragraph_style_refs(doc, "未使用樣式", NEW) is doc


def test_rename_char_refs_in_runs():
    doc = _doc(run_style=EMPH)
    out = rename_char_style_refs(doc, EMPH, NEW)
    assert [r.char_style for r in out.paragraphs[0].runs] == [None, NEW, None]
    assert out.paragraphs[0].text == doc.paragraphs[0].text  # 文字不動
    assert doc.paragraphs[0].runs[1].char_style == EMPH  # 原件不變


def test_rename_char_refs_no_match_returns_original():
    doc = _doc(run_style=EMPH)
    assert rename_char_style_refs(doc, "未使用", NEW) is doc


# ---------- session：文件＋模版成對單一 undo 步 ----------

def test_session_rename_para_style_single_undo(template):
    session = EditSession(_doc(), template)
    result = session.rename_para_style(BODY, NEW)
    assert result is not None
    assert session.document.paragraphs[0].style == NEW
    assert NEW in session.template.paragraph_styles
    assert session.template.md_mapping["paragraph"] == NEW
    placed_styles = {line.style for page in session.layout.pages
                     for line in page.placed}
    assert NEW in placed_styles and BODY not in placed_styles
    assert session.can_undo()
    session.undo()
    assert session.document.paragraphs[0].style == BODY  # 一步回文件
    assert BODY in session.template.paragraph_styles      # 同步回模版
    assert not session.can_undo()  # 成對變更只佔一個 undo 單元


def test_session_rename_para_collision_state_unchanged(template):
    session = EditSession(_doc(), template)
    with pytest.raises(TemplateError):
        session.rename_para_style(BODY, "引文-仿宋語錄")
    assert session.document.paragraphs[0].style == BODY
    assert not session.can_undo()


def test_session_rename_char_style_single_undo(template):
    session = EditSession(_doc(run_style=EMPH), template)
    session.rename_char_style(EMPH, NEW)
    assert session.document.paragraphs[0].runs[1].char_style == NEW
    assert session.template.md_inline_mapping["strong"] == NEW
    session.undo()
    assert session.document.paragraphs[0].runs[1].char_style == EMPH
    assert session.template.md_inline_mapping["strong"] == EMPH
    assert not session.can_undo()


def test_session_rename_same_name_noop(template):
    session = EditSession(_doc(), template)
    assert session.rename_para_style(BODY, BODY) is None
    assert not session.can_undo()
