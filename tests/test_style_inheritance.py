"""樣式繼承（§4.3 基底樣式＋子樣式覆寫，Sprint 68）：based_on 載入解析＋編輯級聯。

載入期：樣式宣告帶 based_on 即繼承基底的有效欄位、自身宣告的欄位覆寫（鏈式傳遞）；
效值於 template_from_dict 扁平化（消費端 layout／render／pdf 讀平面欄位零變更），
declared 記錄自身宣告欄位、based_on 記基底名（供編輯級聯與後續 save 序列化）。
循環（含自指）與未知基底 TemplateError 快速失敗；無 based_on 的根樣式必填欄位守門不變。

編輯期：set_paragraph_style／set_character_style 改樣式後，未宣告（未覆寫）該欄位的
傳遞子孫同步刷新（改樣式即全書套用的繼承半邊）；子樣式一經編輯某欄位即成 declared
覆寫，其後基底該欄位變更不再流入。based_on 不可經 set_* 編輯（結構變更屬後續片）。
測試素材一律自擬（版權紅線）。
"""
import copy
import json
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.session import EditSession
from cjkfolio.style_editing import set_character_style, set_paragraph_style
from cjkfolio.styles import TemplateError, load_template, template_from_dict

ROOT = Path(__file__).resolve().parents[1]

BODY = "內文-明體直排"
EMPH = "內文強調-明體W9"
CHILD = "內文-子樣式測試"
GRAND = "內文-孫樣式測試"


@pytest.fixture(scope="module")
def raw_template():
    return json.loads(
        (ROOT / "templates" / "neizai-zhengli.json").read_text(encoding="utf-8"))


def _with_styles(raw_template, para=None, char=None):
    raw = copy.deepcopy(raw_template)
    raw["paragraph_styles"].update(para or {})
    raw["character_styles"].update(char or {})
    return template_from_dict(raw)


# ---------- 載入期解析 ----------

def test_load_child_inherits_and_overrides(raw_template):
    t = _with_styles(raw_template, para={
        CHILD: {"based_on": BODY, "size_pt": 9.5}})
    parent = t.paragraph_styles[BODY]
    child = t.paragraph_styles[CHILD]
    assert child.size_pt == 9.5                       # 自身宣告覆寫
    assert child.font_family == parent.font_family   # 未宣告承基底
    assert child.indent_chars == parent.indent_chars
    assert child.based_on == BODY
    assert child.declared == ("size_pt",)
    assert parent.based_on is None                    # 根樣式不受影響


def test_load_chain_grandparent(raw_template):
    t = _with_styles(raw_template, para={
        CHILD: {"based_on": BODY, "size_pt": 9.5},
        GRAND: {"based_on": CHILD, "note": "孫層自擬"}})
    grand = t.paragraph_styles[GRAND]
    assert grand.size_pt == 9.5                       # 承中層覆寫
    assert grand.font_family == t.paragraph_styles[BODY].font_family  # 承根
    assert grand.note == "孫層自擬"


def test_load_cycle_and_self_reference_raise(raw_template):
    with pytest.raises(TemplateError):
        _with_styles(raw_template, para={
            "甲": {"based_on": "乙", "size_pt": 10},
            "乙": {"based_on": "甲", "size_pt": 11}})
    with pytest.raises(TemplateError):
        _with_styles(raw_template, para={"丙": {"based_on": "丙", "size_pt": 10}})


def test_load_unknown_base_raises(raw_template):
    with pytest.raises(TemplateError):
        _with_styles(raw_template, para={CHILD: {"based_on": "不存在的基底"}})


def test_load_root_missing_required_still_raises(raw_template):
    with pytest.raises(TemplateError):
        _with_styles(raw_template, para={"殘缺根樣式": {"size_pt": 10}})


def test_load_child_may_declare_nothing(raw_template):
    t = _with_styles(raw_template, para={CHILD: {"based_on": BODY}})
    child = t.paragraph_styles[CHILD]
    parent = t.paragraph_styles[BODY]
    assert (child.font_family, child.size_pt) == (parent.font_family, parent.size_pt)
    assert child.declared == ()


def test_load_char_style_inheritance(raw_template):
    t = _with_styles(raw_template, char={
        "強調-子測試": {"based_on": EMPH, "size_pt": 10.0}})
    child = t.character_styles["強調-子測試"]
    assert child.size_pt == 10.0
    assert child.font_family == t.character_styles[EMPH].font_family
    assert child.based_on == EMPH and child.declared == ("size_pt",)


# ---------- 編輯期級聯 ----------

def test_edit_parent_cascades_to_undeclared_child_field(raw_template):
    t = _with_styles(raw_template, para={CHILD: {"based_on": BODY, "size_pt": 9.5}})
    before_weight = t.paragraph_styles[BODY].font_weight
    assert before_weight != "heavy"  # 前提：測試變更值確實不同於現值
    out = set_paragraph_style(t, BODY, {"font_weight": "heavy"})
    assert out.paragraph_styles[CHILD].font_weight == "heavy"  # 未覆寫欄位流入
    assert out.paragraph_styles[CHILD].size_pt == 9.5          # 覆寫欄位不動
    assert t.paragraph_styles[BODY].font_weight == before_weight  # 原模版不可變
    assert t.paragraph_styles[CHILD].font_weight == before_weight


def test_edit_parent_does_not_touch_child_declared_field(raw_template):
    t = _with_styles(raw_template, para={CHILD: {"based_on": BODY, "size_pt": 9.5}})
    out = set_paragraph_style(t, BODY, {"size_pt": 14.0})
    assert out.paragraph_styles[BODY].size_pt == 14.0
    assert out.paragraph_styles[CHILD].size_pt == 9.5  # declared 覆寫擋住級聯


def test_edit_child_marks_field_declared_blocking_future_cascade(raw_template):
    t = _with_styles(raw_template, para={CHILD: {"based_on": BODY}})
    t2 = set_paragraph_style(t, CHILD, {"size_pt": 9.0})
    assert "size_pt" in t2.paragraph_styles[CHILD].declared
    t3 = set_paragraph_style(t2, BODY, {"size_pt": 14.0})
    assert t3.paragraph_styles[CHILD].size_pt == 9.0  # 已成覆寫，不再流入


def test_edit_grandparent_cascades_through_chain(raw_template):
    t = _with_styles(raw_template, para={
        CHILD: {"based_on": BODY, "size_pt": 9.5},
        GRAND: {"based_on": CHILD}})
    out = set_paragraph_style(t, BODY, {"font_weight": "heavy"})
    assert out.paragraph_styles[CHILD].font_weight == "heavy"
    assert out.paragraph_styles[GRAND].font_weight == "heavy"  # 傳遞至孫層
    assert out.paragraph_styles[GRAND].size_pt == 9.5          # 中層覆寫仍承


def test_edit_char_style_cascades(raw_template):
    t = _with_styles(raw_template, char={
        "強調-子測試": {"based_on": EMPH}})
    out = set_character_style(t, EMPH, {"size_pt": 12.5})
    assert out.character_styles["強調-子測試"].size_pt == 12.5


def test_based_on_not_editable(raw_template):
    t = _with_styles(raw_template, para={CHILD: {"based_on": BODY}})
    with pytest.raises(TemplateError):
        set_paragraph_style(t, CHILD, {"based_on": "題詞-楷書"})
    with pytest.raises(TemplateError):
        set_paragraph_style(t, CHILD, {"declared": ("size_pt",)})


# ---------- session 端到端（改基底 → 子樣式段落全書重排）----------

def test_session_update_parent_reflows_child_paragraphs(raw_template):
    t = _with_styles(raw_template, para={CHILD: {"based_on": BODY}})
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "安放選擇收納歸位定位取捨疊放展開整理收拾歸檔封存啟用留白呼吸沉澱清明",
                        "style": CHILD}],
    })
    s = EditSession(doc, t)
    lines_before = sum(len(p.placed) for p in s.layout.pages)
    s.update_para_style(BODY, {"size_pt": 23.0})  # 改基底，段落用子樣式
    assert s.template.paragraph_styles[CHILD].size_pt == 23.0
    assert sum(len(p.placed) for p in s.layout.pages) > lines_before
    s.undo()
    assert s.template.paragraph_styles[CHILD].size_pt == 11.5
    assert sum(len(p.placed) for p in s.layout.pages) == lines_before


def test_loaded_builtin_template_unchanged(raw_template):
    """內建模版無 based_on：載入行為與既有完全一致（回歸守門）。"""
    t = load_template(ROOT / "templates" / "neizai-zhengli.json")
    assert all(st.based_on is None for st in t.paragraph_styles.values())
    body = t.paragraph_styles[BODY]
    assert body.size_pt == 11.5 and "size_pt" in body.declared
