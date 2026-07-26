"""手動空行增刪（Sprint 141）：使用者自己推行，把卡在頁尾的行擠到下一頁。

starts_page 只認模版宣告的樣式；沒被宣告到的場合（自訂樣式、單次微調）仍要有
人工出口。空段是既有機制：不產 PlacedLine（畫布上看不到也點不到），但仍佔一個
para_gap_slots 槽，後續行整體下移一行。

畫布點不到＝刪不掉，故插入與移除成對提供，移除走「游標段前的空段」。
覆蓋 editing 純函式與 session 回路（含 undo）。素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.editing import (
    DocCursor,
    insert_blank_paragraph,
    remove_blank_paragraph,
)
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"

BODY = "內文-明體直排"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


def two_para_doc():
    return make_doc([
        {"text": "整" * 20, "style": BODY},
        {"text": "理" * 20, "style": BODY},
    ])


# ---------- editing 層：純函式 ----------

def test_insert_blank_before_target():
    """空段插在目標段之前，承目標段的樣式，原段內容不動。"""
    out = insert_blank_paragraph(two_para_doc(), 1)
    assert [p.text for p in out.paragraphs] == ["整" * 20, "", "理" * 20]
    assert out.paragraphs[1].style == BODY
    assert out.paragraphs[1].master is None
    assert out.paragraphs[1].page_no is None


def test_insert_blank_out_of_range_raises():
    """目標段必須存在（GUI 只從游標所在段呼叫；末段後無段可推，不另開語意）。"""
    with pytest.raises(IndexError):
        insert_blank_paragraph(two_para_doc(), 2)
    with pytest.raises(IndexError):
        insert_blank_paragraph(two_para_doc(), -1)


def test_remove_blank_only_accepts_empty_paragraph():
    """只吃空段：非空段 raise，不沉默刪掉整段內文。"""
    doc = insert_blank_paragraph(two_para_doc(), 1)
    out = remove_blank_paragraph(doc, 1)
    assert [p.text for p in out.paragraphs] == ["整" * 20, "理" * 20]
    with pytest.raises(ValueError, match="空段"):
        remove_blank_paragraph(doc, 0)


def test_blank_paragraph_shifts_lines_without_placing(template):
    """空段不產 PlacedLine（畫布上看不到），但後續行整體下移一槽。"""
    base = layout_document(two_para_doc(), template)
    pushed = layout_document(insert_blank_paragraph(two_para_doc(), 1), template)
    assert len(pushed.pages[0].placed) == len(base.pages[0].placed)  # 空段無行
    second_base = [ln for ln in base.pages[0].placed if ln.para_idx == 1][0]
    second_pushed = [ln for ln in pushed.pages[0].placed if ln.para_idx == 2][0]
    assert second_pushed.slot == second_base.slot + 1


# ---------- session 層：編輯回路與 undo ----------

def test_session_insert_blank_moves_cursor_to_target(template):
    """游標落在原目標段（插入後索引 +1）段首；空段無字格，游標不落在它上面。"""
    session = EditSession(two_para_doc(), template)
    result = session.insert_blank(1)
    assert result.cursor == DocCursor(2, 0)
    assert result.document.paragraphs[1].text == ""
    session.undo()
    assert len(session.document.paragraphs) == 2


def test_session_remove_blank_rejects_nonempty_without_changing_state(template):
    """非空段 ValueError，且文件與歷史都不動（失敗的操作不入 undo）。"""
    session = EditSession(two_para_doc(), template)
    before = session.document
    with pytest.raises(ValueError, match="空段"):
        session.remove_blank(0)
    assert session.document is before
    assert not session.can_undo()


def test_session_blank_pushes_last_line_to_next_page(template):
    """整頁滿版時插一空行＝末行被擠到下一頁（本功能的實際用途）。"""
    def one_line_paras(count):  # 每段 20 字＝一行（版心 30 格，不折行）
        return [{"text": "整" * 20, "style": BODY} for _ in range(count)]

    probe = layout_document(make_doc(one_line_paras(80)), template)
    capacity = len(probe.pages[0].placed)  # 首頁塞得下的段數
    assert 0 < capacity < 80, "探針未溢頁，量不到單頁容量"

    session = EditSession(make_doc(one_line_paras(capacity)), template)
    assert len(session.layout.pages) == 1
    result = session.insert_blank(0)
    assert len(result.layout.pages) == 2
    assert result.layout.pages[1].placed[0].para_idx == capacity  # 末段被推到次頁
