"""頁面拖曳重排（Sprint 142）：搬節＝搬「自某頁起到下一節首前」的整塊內容。

本產品的頁面是段落流排的結果，不是投影片那樣的獨立物件，故沒有「把版面頁 4 搬到
版面頁 1」這個操作。可搬的最小完整單位是節（Paragraph.master 節首標記切出的段落
區塊，節首恆起新頁），搬完全書重排。三層驗收：文件層 move_section 的換序與節首
標記重寫、會談層 EditSession 的 undo／no-op、版面層重排後的逐頁主版與頁號。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.editing import move_section
from cjkfolio.layout import _sections
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from cjkfolio.wrap import layout_with_wrap

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs, master="A-內文版"):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli",
                 "master": master},
        "paragraphs": paragraphs,
    })


def three_sections():
    """自擬三節文件：H 封面版一段、B 部扉一段、A 內文兩段（首節主版存 doc.master）。"""
    return make_doc(
        [
            {"text": "封面：成名之路", "style": "封面書名-明體W9"},
            {"text": "第一部", "style": "部扉大標-明體W9", "master": "B-部扉"},
            {"text": "內文第一段。", "style": "內文-明體直排", "master": "A-內文版"},
            {"text": "內文第二段。", "style": "內文-明體直排"},
        ],
        master="H-封面",
    )


def section_shape(doc):
    """節結構的可比對形狀：[(主版名, 首段文字), …]。"""
    return [(m, doc.paragraphs[lo].text) for m, lo, _ in _sections(doc)]


# ---------- 文件層：換序與節首標記重寫 ----------

def test_move_last_section_to_front():
    """把第 3 節搬到最前：節序輪轉，內容整塊跟著走。"""
    doc = three_sections()
    assert section_shape(doc) == [
        ("H-封面", "封面：成名之路"), ("B-部扉", "第一部"),
        ("A-內文版", "內文第一段。"),
    ]
    moved = move_section(doc, 2, 0)
    assert section_shape(moved) == [
        ("A-內文版", "內文第一段。"), ("H-封面", "封面：成名之路"),
        ("B-部扉", "第一部"),
    ]
    # 整塊跟著走：A 節的第二段仍緊跟其後
    assert [p.text for p in moved.paragraphs] == [
        "內文第一段。", "內文第二段。", "封面：成名之路", "第一部",
    ]


def test_move_rewrites_head_markers_and_doc_master():
    """新首節清掉標記並把主版寫進 doc.master，其餘節在首段明寫自己的主版。"""
    moved = move_section(three_sections(), 2, 0)
    assert moved.master == "A-內文版"  # 新首節主版升格為 doc.master
    assert moved.paragraphs[0].master is None  # 首節無節首標記
    assert moved.paragraphs[2].master == "H-封面"  # 原首節降為一般節，補標記
    assert moved.paragraphs[3].master == "B-部扉"


def test_move_round_trip_restores_document_shape():
    """來回搬兩次還原原本的文件形狀（標記位置與 doc.master 都回到原值）。"""
    doc = three_sections()
    there = move_section(doc, 2, 0)
    back = move_section(there, 0, 3)
    assert back.master == doc.master
    assert [(p.text, p.master) for p in back.paragraphs] == \
           [(p.text, p.master) for p in doc.paragraphs]


def test_move_forward_uses_pre_move_insertion_index():
    """dst 是搬動前節序上的插入位（同一般清單拖放語意）：0→2 落在原第 2 節之後。"""
    moved = move_section(three_sections(), 0, 2)
    assert [m for m, _ in section_shape(moved)] == [
        "B-部扉", "H-封面", "A-內文版",
    ]


def test_move_to_same_position_is_noop_returning_same_object():
    """原位放下：回原物件（呼叫端據此不入 undo）。"""
    doc = three_sections()
    assert move_section(doc, 1, 1) is doc
    assert move_section(doc, 1, 2) is doc  # 搬到自己後面＝同一位


def test_single_section_document_is_always_noop():
    """單節文件無序可換（真稿《成名之路》匯入時即為此形）。"""
    doc = make_doc([{"text": "只有一節。", "style": "內文-明體直排"}])
    assert len(_sections(doc)) == 1
    assert move_section(doc, 0, 0) is doc
    assert move_section(doc, 0, 1) is doc


@pytest.mark.parametrize("src,dst", [(-1, 0), (3, 0), (0, -1), (0, 4)])
def test_out_of_range_indices_fail_fast(src, dst):
    """系統邊界快速失敗：節序越界 raise IndexError，不靜默夾住。"""
    with pytest.raises(IndexError):
        move_section(three_sections(), src, dst)


# ---------- 版面層：重排後的逐頁主版與頁號 ----------

def test_layout_reflows_with_new_master_order(template):
    """搬完重排：逐頁主版依新節序，頁號仍連續（頁面是流排結果）。"""
    doc = three_sections()
    before = layout_with_wrap(doc, template)
    assert [p.master for p in before.pages] == ["H-封面", "B-部扉", "A-內文版"]
    after = layout_with_wrap(move_section(doc, 2, 0), template)
    assert [p.master for p in after.pages] == ["A-內文版", "H-封面", "B-部扉"]
    assert [p.number for p in after.pages] == [1, 2, 3]


def test_moved_section_content_lands_on_its_new_head_page(template):
    """搬到最前的節，其首段落在新的第 1 頁（使用者要的「把封面搬到第一頁」的一般化）。"""
    moved = move_section(three_sections(), 2, 0)
    layout = layout_with_wrap(moved, template)
    first = layout.pages[0]
    assert first.placed[0].para_idx == 0
    assert first.placed[0].line.cells[0].text == "內"


# ---------- 會談層：undo 與 no-op ----------

def test_session_move_section_is_one_undo_step(template):
    """搬節入單一 undo 步：一次 Ctrl+Z 回到搬動前的節序。"""
    doc = three_sections()
    session = EditSession(doc, template)
    res = session.move_section(2, 0)
    assert res is not None
    assert [p.master for p in session.layout.pages] == \
           ["A-內文版", "H-封面", "B-部扉"]
    session.undo()
    assert [p.master for p in session.layout.pages] == \
           ["H-封面", "B-部扉", "A-內文版"]
    assert session.document.master == "H-封面"


def test_session_move_section_noop_returns_none(template):
    """原位放下不推 undo 步（避免一步看不出差別的復原）。"""
    session = EditSession(three_sections(), template)
    assert session.move_section(1, 1) is None
    assert not session.can_undo()
