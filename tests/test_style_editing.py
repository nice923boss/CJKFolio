"""樣式定義編輯（cjkfolio/style_editing.py＋session 整合，Sprint 67）：改樣式即全書套用。

Phase 3 樣式系統第一片：set_paragraph_style／set_character_style 純模版層（不可變、
未知樣式 KeyError、不可編輯欄位 TemplateError、空與等值變更 no-op 回原物件、型別
轉換同載入層）；EditSession.update_para_style／update_char_style 走全書重排並與文件
編輯共用同一 undo／redo 歷史（快照三元組 (document, template, cursor)）。值語意
（writing_mode 合法性）由 layout_document 守門（既有慣例）。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.editing import DocCursor, DocRange
from cjkfolio.frame_editing import FrameCursor, FrameEditResult
from cjkfolio.session import EditSession
from cjkfolio.style_editing import set_character_style, set_paragraph_style
from cjkfolio.styles import TemplateError, load_template

ROOT = Path(__file__).resolve().parents[1]

BODY = "內文-明體直排"
EMPH = "內文強調-明體W9"
CAPTION = "旁注-手札圖注"


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _bodies(*texts: str):
    """A-內文版多段內文（自擬）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": t, "style": BODY} for t in texts],
    })


def _frame_doc():
    """含獨立文字框的自擬文件（框樣式＝旁注-手札圖注）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "留白是安放的開始。", "style": BODY}],
        "text_frames": [{"text": "安放選擇收納歸位", "style": CAPTION, "page": 1,
                         "rect": [300.0, 120.0, 340.0, 260.0]}],
    })


# ---------- set_paragraph_style／set_character_style（純模版層）----------

def test_set_para_style_returns_new_template_original_untouched(template):
    out = set_paragraph_style(template, BODY, {"size_pt": 14.0})
    assert out is not template
    assert out.paragraph_styles[BODY].size_pt == 14.0
    assert template.paragraph_styles[BODY].size_pt == 11.5  # 原模版不可變
    other = "引文-仿宋語錄"
    assert out.paragraph_styles[other] is template.paragraph_styles[other]  # 其他樣式共享
    assert out.character_styles is template.character_styles


def test_set_para_style_multi_fields(template):
    out = set_paragraph_style(
        template, BODY, {"indent_chars": 0, "para_gap_slots": 2, "note": "自擬測試"})
    st = out.paragraph_styles[BODY]
    assert (st.indent_chars, st.para_gap_slots, st.note) == (0, 2, "自擬測試")
    assert st.size_pt == 11.5  # 未列欄位保留


def test_set_para_style_unknown_style_keyerror(template):
    with pytest.raises(KeyError):
        set_paragraph_style(template, "不存在的樣式", {"size_pt": 12.0})


def test_set_para_style_uneditable_field_rejected(template):
    with pytest.raises(TemplateError):
        set_paragraph_style(template, BODY, {"name": "改名"})  # 改名不在 v1
    with pytest.raises(TemplateError):
        set_paragraph_style(template, BODY, {"bogus_field": 1})


def test_set_para_style_empty_and_equal_changes_are_noop(template):
    assert set_paragraph_style(template, BODY, {}) is template
    assert set_paragraph_style(template, BODY, {"size_pt": 11.5}) is template


def test_set_para_style_coerces_types_like_loader(template):
    out = set_paragraph_style(template, BODY, {"size_pt": "14", "indent_chars": "0"})
    assert out.paragraph_styles[BODY].size_pt == 14.0
    assert out.paragraph_styles[BODY].indent_chars == 0


def test_set_char_style_basic_and_guards(template):
    out = set_character_style(template, EMPH, {"size_pt": 12.5})
    assert out.character_styles[EMPH].size_pt == 12.5
    assert template.character_styles[EMPH].size_pt != 12.5
    assert out.paragraph_styles is template.paragraph_styles
    with pytest.raises(KeyError):
        set_character_style(template, "不存在", {"size_pt": 1.0})
    with pytest.raises(TemplateError):
        set_character_style(template, EMPH, {"indent_chars": 0})  # 字元樣式無此欄
    assert set_character_style(template, EMPH, {}) is template


# ---------- EditSession.update_para_style／update_char_style（reflow＋統一歷史）----------

def test_session_update_para_style_reflows_whole_document(template):
    s = EditSession(_bodies("安放選擇收納歸位定位取捨疊放展開整理收拾歸檔封存啟用留白呼吸沉澱清明"), template)
    lines_before = sum(len(p.placed) for p in s.layout.pages)
    res = s.update_para_style(BODY, {"size_pt": 23.0})
    assert s.template.paragraph_styles[BODY].size_pt == 23.0
    lines_after = sum(len(p.placed) for p in s.layout.pages)
    assert lines_after > lines_before  # 級數放大 → 行容量縮 → 行數增（全書重排）
    assert res.document is s.document  # 樣式編輯不改文件
    assert res.cursor == s.cursor and res.address is not None  # 游標保持並反查落點


def test_session_update_para_style_undo_redo_restores_template(template):
    s = EditSession(_bodies("安放選擇收納歸位定位取捨疊放展開整理收拾歸檔封存啟用留白呼吸沉澱清明"), template)
    lines_orig = sum(len(p.placed) for p in s.layout.pages)
    s.update_para_style(BODY, {"size_pt": 23.0})
    assert s.can_undo()
    s.undo()
    assert s.template.paragraph_styles[BODY].size_pt == 11.5
    assert sum(len(p.placed) for p in s.layout.pages) == lines_orig
    assert s.can_redo()
    s.redo()
    assert s.template.paragraph_styles[BODY].size_pt == 23.0


def test_session_update_unified_history_with_body_edits(template):
    s = EditSession(_bodies("三房兩廳"), template)
    s.insert(DocCursor(0, 4), "採光")            # 單元 1：插字
    s.update_para_style(BODY, {"indent_chars": 0})  # 單元 2：樣式編輯
    assert s.document.paragraphs[0].text == "三房兩廳採光"
    s.undo()  # 回樣式（文件不動）
    assert s.template.paragraph_styles[BODY].indent_chars == 2
    assert s.document.paragraphs[0].text == "三房兩廳採光"
    s.undo()  # 回插字
    assert s.document.paragraphs[0].text == "三房兩廳"
    assert not s.can_undo()


def test_session_update_char_style_records_template_history(template):
    s = EditSession(_bodies("三房兩廳"), template)
    s.apply_style(DocRange(0, 0, 2), EMPH)
    s.update_char_style(EMPH, {"size_pt": 12.5})
    assert s.template.character_styles[EMPH].size_pt == 12.5
    s.undo()
    assert s.template.character_styles[EMPH].size_pt == template.character_styles[EMPH].size_pt
    assert s.document.paragraphs[0].runs[0].char_style == EMPH  # 只回樣式定義，套用保留


def test_session_update_noop_returns_none_no_history(template):
    s = EditSession(_bodies("三房兩廳"), template)
    assert s.update_para_style(BODY, {"size_pt": 11.5}) is None  # 等值 no-op
    assert not s.can_undo()


def test_session_update_invalid_writing_mode_fast_fails_state_unchanged(template):
    s = EditSession(_bodies("三房兩廳"), template)
    layout_before = s.layout
    with pytest.raises(ValueError):
        s.update_para_style(BODY, {"writing_mode": "diagonal"})
    assert s.template is template and s.layout is layout_before  # 套用前快速失敗
    assert not s.can_undo()


def test_session_update_breaks_insert_coalescing(template):
    clock = _FakeClock()
    s = EditSession(_bodies("三房"), template, clock=clock)
    s.insert(DocCursor(0, 2), "兩")
    s.update_para_style(BODY, {"note": "自擬"})
    s.insert(DocCursor(0, 3), "廳")  # 樣式編輯介入 → 起新輸入單元
    assert s.document.paragraphs[0].text == "三房兩廳"
    s.undo()  # 回「廳」
    assert s.document.paragraphs[0].text == "三房兩"
    s.undo()  # 回樣式
    s.undo()  # 回「兩」
    assert s.document.paragraphs[0].text == "三房"
    assert not s.can_undo()


def test_session_update_with_frame_cursor_returns_frame_result(template):
    s = EditSession(_frame_doc(), template)
    s.insert_frame(FrameCursor(0, 4), "而")  # 現態游標成 FrameCursor
    res = s.update_para_style(CAPTION, {"size_pt": 10.0})
    assert isinstance(res, FrameEditResult)
    assert s.template.paragraph_styles[CAPTION].size_pt == 10.0
    undone = s.undo()  # 回樣式編輯前（該態游標仍為 FrameCursor）
    assert isinstance(undone, FrameEditResult)
    assert s.template.paragraph_styles[CAPTION].size_pt == 8.0


class _FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t
