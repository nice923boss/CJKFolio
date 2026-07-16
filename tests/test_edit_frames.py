"""框內編輯核心（Sprint 59）：insert／delete 入框＋apply 回路＋框游標跟隨。

框編輯對象＝文字來源框（source_idx，串接鏈首；獨立框＝自身）的 text；
重佈局走 resolve_text_frames（body layout 不動）；游標落點以框 cells span 反查。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.editing import DocCursor
from cjkfolio.frame_editing import (
    FrameCursor,
    FrameEditResult,
    apply_frame_delete,
    apply_frame_insert,
    delete_frame_range,
    insert_frame_text,
    locate_frame_cell,
)
from cjkfolio.frames import masters_for_layout, resolve_text_frames
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


# 旁注 8pt 於 A 網格：字距 8.4035、欄距 16.0。
# 鏈首框 [300,120,340,200] 高 80 → 每欄 9 字、寬 40 → 2 欄＝18 字；續框同型接餘字。
def make_doc(head_text="安放選擇收納歸位" * 2, extra_frames=()):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "留白是安放的開始。", "style": "內文-明體直排"}],
        "text_frames": [
            {"text": head_text, "style": "旁注-手札圖注", "page": 1,
             "rect": [300.0, 120.0, 340.0, 200.0], "thread": "說"},
            {"style": "旁注-手札圖注", "page": 1,
             "rect": [200.0, 120.0, 240.0, 200.0], "thread": "說"},
            *extra_frames,
        ],
    })


def placements_of(doc, template):
    layout = layout_document(doc, template)
    return layout, resolve_text_frames(doc, template,
                                       masters_for_layout(template, doc, layout))


# ---------- 純文件層：insert_frame_text ----------

def test_insert_frame_text_middle_and_immutable(template):
    doc = make_doc()
    new = insert_frame_text(doc, FrameCursor(0, 2), "好物")
    assert new.text_frames[0].text == "安放好物選擇收納歸位安放選擇收納歸位"
    assert doc.text_frames[0].text == "安放選擇收納歸位" * 2  # 不可變
    assert new.text_frames[1] == doc.text_frames[1]  # 續框不動
    assert insert_frame_text(doc, FrameCursor(0, 0), "") is doc  # 空字串 no-op


def test_insert_frame_text_fast_fail(template):
    doc = make_doc()
    with pytest.raises(IndexError):
        insert_frame_text(doc, FrameCursor(9, 0), "字")
    with pytest.raises(ValueError, match="caret"):
        insert_frame_text(doc, FrameCursor(0, 99), "字")
    with pytest.raises(ValueError, match="鏈首"):  # 續框無文字，編輯對鏈首
        insert_frame_text(doc, FrameCursor(1, 0), "字")


# ---------- 純文件層：delete_frame_range ----------

def test_delete_frame_range_and_noop(template):
    doc = make_doc()
    new = delete_frame_range(doc, 0, 2, 4)
    assert new.text_frames[0].text == "安放收納歸位安放選擇收納歸位"
    assert delete_frame_range(doc, 0, 3, 3) is doc  # 空範圍 no-op


def test_delete_frame_range_fast_fail(template):
    doc = make_doc()
    with pytest.raises(ValueError):
        delete_frame_range(doc, 0, 4, 2)  # start > end
    with pytest.raises(ValueError):
        delete_frame_range(doc, 0, 0, 99)  # 越界
    with pytest.raises(ValueError, match="刪空"):  # 框 text 非空為 schema 不變式
        delete_frame_range(doc, 0, 0, 16)


# ---------- 回路：apply_frame_insert／apply_frame_delete ----------

def test_apply_frame_insert_reflows_and_follows_cursor(template):
    """鏈首插字 → 框重佈局（body layout 不動）→ 游標落點跟隨到最後插入字。"""
    doc = make_doc()
    layout = layout_document(doc, template)
    res = apply_frame_insert(doc, template, layout, FrameCursor(0, 4), "整理")
    assert res.document.text_frames[0].text == "安放選擇整理收納歸位安放選擇收納歸位"
    assert res.layout is layout  # body 不重排（框編輯不影響流排）
    assert res.cursor == FrameCursor(0, 6)
    addr = res.address
    assert addr is not None
    pl = next(p for p in res.placements_by_page[addr.page_number]
              if p.frame_idx == addr.frame_idx)
    cell = pl.lines[addr.line_idx].line.cells[addr.cell_idx]
    assert cell.text == "理"  # 最後插入字


def test_apply_frame_insert_overflow_into_next_frame(template):
    """插字使鏈首滿 18 格：第 19 字起流入續框，游標跨框跟隨（span 錨鏈首）。"""
    doc = make_doc(head_text="安放選擇收納歸位" * 2 + "留白")  # 18 字恰滿鏈首
    layout = layout_document(doc, template)
    res = apply_frame_insert(doc, template, layout, FrameCursor(0, 18), "生光")
    addr = res.address
    assert addr is not None and addr.frame_idx == 1  # 游標落續框
    pl = next(p for p in res.placements_by_page[addr.page_number]
              if p.frame_idx == 1)
    assert pl.lines[addr.line_idx].line.cells[addr.cell_idx].text == "光"


def test_apply_frame_delete_cursor_at_seam(template):
    doc = make_doc()
    layout = layout_document(doc, template)
    res = apply_frame_delete(doc, template, layout, 0, 2, 6)  # 刪「選擇收納」4 字
    assert res.document.text_frames[0].text == "安放歸位安放選擇收納歸位"
    assert res.cursor == FrameCursor(0, 2)
    pl = next(p for p in res.placements_by_page[res.address.page_number]
              if p.frame_idx == res.address.frame_idx)
    cell = pl.lines[res.address.line_idx].line.cells[res.address.cell_idx]
    assert cell.text == "放"  # 縫左鄰


# ---------- locate_frame_cell ----------

def test_locate_frame_cell_caret_zero_and_none(template):
    doc = make_doc()
    _, by_page = placements_of(doc, template)
    addr = locate_frame_cell(by_page, FrameCursor(0, 0))
    assert addr is not None and addr.frame_idx == 0
    pl = next(p for p in by_page[addr.page_number] if p.frame_idx == 0)
    assert pl.lines[addr.line_idx].line.cells[addr.cell_idx].text == "安"
    assert locate_frame_cell(by_page, FrameCursor(7, 0)) is None  # 查無來源框


# ---------- EditSession 框編輯整合（Sprint 60：與 body 統一 undo／redo 歷史） ----------

class _FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


ORIG_HEAD = "安放選擇收納歸位" * 2


def test_session_frame_insert_undo_redo(template):
    """框插字入 undo 歷史；undo 回編輯前（body 態）、redo 回框態（FrameEditResult）。"""
    s = EditSession(make_doc(), template)
    res = s.insert_frame(FrameCursor(0, 4), "整理")
    assert isinstance(res, FrameEditResult)
    assert s.document.text_frames[0].text == "安放選擇整理收納歸位安放選擇收納歸位"
    back = s.undo()
    assert back is not None
    assert s.document.text_frames[0].text == ORIG_HEAD
    assert s.can_redo()
    again = s.redo()
    assert isinstance(again, FrameEditResult)  # 還原態游標為 FrameCursor → 框結果
    assert s.document.text_frames[0].text == "安放選擇整理收納歸位安放選擇收納歸位"
    assert again.address is not None
    pl = next(p for p in again.placements_by_page[again.address.page_number]
              if p.frame_idx == again.address.frame_idx)
    cell = pl.lines[again.address.line_idx].line.cells[again.address.cell_idx]
    assert cell.text == "理"


def test_session_body_and_frame_history_interleave(template):
    """body 與框編輯交錯共用同一歷史：兩次 undo 依序回退框、body。"""
    doc = make_doc()
    s = EditSession(doc, template)
    s.insert(DocCursor(0, 2), "更")                 # body 編輯
    s.insert_frame(FrameCursor(0, 0), "先")         # 框編輯（新 undo 單元）
    assert s.document.paragraphs[0].text == "留白更是安放的開始。"
    assert s.document.text_frames[0].text == "先" + ORIG_HEAD
    s.undo()  # 回退框編輯
    assert s.document.text_frames[0].text == ORIG_HEAD
    assert s.document.paragraphs[0].text == "留白更是安放的開始。"
    s.undo()  # 回退 body 編輯
    assert s.document.paragraphs[0].text == "留白是安放的開始。"
    assert not s.can_undo()


def test_session_frame_insert_coalesces_single_undo_unit(template):
    """框連續前進打字併為單一 undo 單元；一步 undo 還原整串。"""
    clock = _FakeClock()
    s = EditSession(make_doc(), template, clock=clock)
    s.insert_frame(FrameCursor(0, 0), "一")
    clock.t += 1.0
    s.insert_frame(FrameCursor(0, 1), "二")  # caret 接續前一輸入尾 → 併入
    assert s.document.text_frames[0].text == "一二" + ORIG_HEAD
    s.undo()
    assert s.document.text_frames[0].text == ORIG_HEAD
    assert not s.can_undo()


def test_session_body_input_breaks_frame_sequence(template):
    """body 輸入打斷框輸入序列（鍵不同）：框、body、框＝三個 undo 單元。"""
    clock = _FakeClock()
    s = EditSession(make_doc(), template, clock=clock)
    s.insert_frame(FrameCursor(0, 0), "一")
    clock.t += 0.5
    s.insert(DocCursor(0, 0), "多")
    clock.t += 0.5
    s.insert_frame(FrameCursor(0, 1), "二")  # 序列已被 body 打斷 → 新單元
    s.undo()
    assert s.document.text_frames[0].text == "一" + ORIG_HEAD  # 只退「二」
    s.undo()
    assert s.document.paragraphs[0].text == "留白是安放的開始。"
    s.undo()
    assert s.document.text_frames[0].text == ORIG_HEAD
    assert not s.can_undo()


def test_session_delete_frame_undo(template):
    s = EditSession(make_doc(), template)
    res = s.delete_frame(0, 2, 6)
    assert isinstance(res, FrameEditResult)
    assert s.document.text_frames[0].text == "安放歸位安放選擇收納歸位"
    s.undo()
    assert s.document.text_frames[0].text == ORIG_HEAD
