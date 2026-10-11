"""刪除頁面與插入空白頁（Sprint 153）。

頁面是段落流排的結果：刪一頁＝刪掉排在那一頁的段，插一頁＝插入一個自成一節的空段。
三層驗收：文件層（段、節首標記、圖與文字框頁號）、版面層（空節撐出一頁、裝訂補頁
自動湊回 4 的倍數）、會談層（一步 undo、游標跟隨）。
"""
from dataclasses import replace
from pathlib import Path

import pytest

from cjkfolio.document import PlacedImage, TextFrame, document_from_dict
from cjkfolio.editing import DocCursor, delete_page, insert_blank_page
from cjkfolio.layout import _sections
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from cjkfolio.wrap import layout_with_wrap

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
BODY = "內文-明體直排"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs, sheet_pages=None):
    meta = {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"}
    if sheet_pages is not None:
        meta["sheet_pages"] = sheet_pages
    return document_from_dict({
        "schema": "cjkfolio/document@2", "meta": meta, "paragraphs": paragraphs,
    })


def four_pages():
    """自擬四節文件，每節一頁：書名頁、部扉（兩段）、內文、內文。"""
    return make_doc([
        {"text": "書名", "style": BODY},
        {"text": "第一部", "style": "部扉大標-明體W9", "master": "B-部扉"},
        {"text": "部扉說明。", "style": BODY},
        {"text": "內文第一段。", "style": BODY, "master": "A-內文版"},
        {"text": "內文第二段。", "style": BODY, "master": "A-內文版"},
    ])


def with_objects(doc):
    rect = (10.0, 10.0, 50.0, 50.0)
    return replace(
        doc,
        images=(PlacedImage("a.png", 1, rect), PlacedImage("b.png", 2, rect),
                PlacedImage("c.png", 3, rect)),
        text_frames=(TextFrame("框二", BODY, 2, rect), TextFrame("框三", BODY, 3, rect)),
    )


# ---------- 文件層：刪頁 ----------

def test_delete_page_drops_paragraphs_and_hands_head_marker_on():
    """刪掉部扉頁首段（節首）時，同節留下的段補上該節主版，仍從新頁開始。"""
    doc = delete_page(four_pages(), 2, 1, 2)
    assert [p.text for p in doc.paragraphs] == [
        "書名", "部扉說明。", "內文第一段。", "內文第二段。"]
    assert doc.paragraphs[1].master == "B-部扉"
    assert [m for m, _, _ in _sections(doc)] == [
        "A-內文版", "B-部扉", "A-內文版", "A-內文版"]


def test_delete_whole_section_keeps_next_head_untouched():
    doc = delete_page(four_pages(), 2, 1, 3)
    assert [p.text for p in doc.paragraphs] == ["書名", "內文第一段。", "內文第二段。"]
    assert doc.paragraphs[1].master == "A-內文版"


def test_delete_first_page_moves_marker_to_new_first_paragraph():
    doc = delete_page(four_pages(), 1, 0, 1)
    assert doc.paragraphs[0].text == "第一部"
    assert doc.paragraphs[0].master == "B-部扉"


def test_delete_page_removes_its_objects_and_shifts_later_pages():
    doc = delete_page(with_objects(four_pages()), 2, 1, 3)
    assert [(im.path, im.page) for im in doc.images] == [("a.png", 1), ("c.png", 2)]
    assert [(tf.text, tf.page) for tf in doc.text_frames] == [("框三", 2)]


@pytest.mark.parametrize("lo,hi", [(-1, 1), (2, 2), (3, 9), (0, 5)])
def test_delete_page_rejects_bad_range_or_whole_book(lo, hi):
    with pytest.raises(ValueError):
        delete_page(four_pages(), 1, lo, hi)


# ---------- 文件層：插頁 ----------

def test_insert_blank_page_adds_marked_empty_paragraph_in_common_style():
    doc = insert_blank_page(four_pages(), 1, 2, "A-內文版")
    blank = doc.paragraphs[1]
    assert (blank.text, blank.style, blank.master) == ("", BODY, "A-內文版")
    assert doc.paragraphs[2].master == "B-部扉"  # 原節首標記不動


def test_insert_marks_following_paragraph_so_it_keeps_its_page():
    """插在節中間（段 2 無標記）：段 2 補上所屬節主版，才不會黏到空白頁上。"""
    doc = insert_blank_page(four_pages(), 2, 3)
    assert doc.paragraphs[2].master == "B-部扉"  # 預設承插入處所在節
    assert doc.paragraphs[3].text == "部扉說明。"
    assert doc.paragraphs[3].master == "B-部扉"


def test_insert_at_end_and_object_pages_shift():
    doc = insert_blank_page(with_objects(four_pages()), 5, 3, "A-內文版")
    assert doc.paragraphs[-1].text == "" and doc.paragraphs[-1].master == "A-內文版"
    assert [im.page for im in doc.images] == [1, 2, 4]
    assert [tf.page for tf in doc.text_frames] == [2, 4]


def test_insert_out_of_range_fails_fast():
    with pytest.raises(IndexError):
        insert_blank_page(four_pages(), 6, 1)


# ---------- 版面層 ----------

def test_inserted_blank_page_lays_out_as_one_page_with_empty_line(template):
    base = layout_with_wrap(four_pages(), template)
    lay = layout_with_wrap(insert_blank_page(four_pages(), 1, 2, "A-內文版"), template)
    assert len(lay.pages) == len(base.pages) + 1
    page = lay.pages[1]
    assert [pl.para_idx for pl in page.placed] == [1]
    assert page.placed[0].line.cells == ()
    assert not page.blank, "插入的空白頁照常編頁碼，不是裝訂補頁"


def test_unmarked_empty_section_still_lays_out_to_zero_pages(template):
    """無節首標記的空節不補頁（空白起始文件要 0 頁空紙面，Sprint 123）。"""
    lay = layout_with_wrap(make_doc([{"text": "", "style": BODY}]), template)
    assert len(lay.pages) == 0


@pytest.mark.parametrize("edit", ["insert", "delete"])
def test_binding_padding_restores_multiple_of_four(template, edit):
    doc = replace(four_pages(), sheet_pages=4)
    assert len(layout_with_wrap(doc, template).pages) % 4 == 0
    doc = (insert_blank_page(doc, 3, 3, "A-內文版") if edit == "insert"
           else delete_page(doc, 1, 0, 1))
    lay = layout_with_wrap(doc, template)
    assert len(lay.pages) % 4 == 0
    assert sum(p.blank for p in lay.pages) == (3 if edit == "insert" else 1)


# ---------- 會談層 ----------

def test_session_delete_and_insert_are_single_undo_steps(template):
    ses = EditSession(four_pages(), template)
    original = ses.document
    ses.delete_page(2, 1, 3)
    assert len(ses.document.paragraphs) == 3
    ses.undo()
    assert ses.document == original
    ses.insert_blank_page(3, 3, "A-內文版")
    assert len(ses.document.paragraphs) == 6
    ses.undo()
    assert ses.document == original


def test_session_insert_shifts_cursor_after_insertion_point(template):
    ses = EditSession(four_pages(), template)
    ses._cursor = DocCursor(3, 2)
    ses.insert_blank_page(1, 2, "A-內文版")
    assert ses._cursor == DocCursor(4, 2)
    ses.delete_page(2, 1, 2)
    assert ses._cursor == DocCursor(1, 0)
