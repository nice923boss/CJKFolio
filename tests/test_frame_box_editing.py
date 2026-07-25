"""文字框的框級編輯純函式與 session 接線（Sprint 136：整框增刪移與縮放）。

本檔全數為 Qt 無關的離屏驗證：框的新增、平移、縮放、移除、命中判定與 undo 歷史
全在判定層，故 UI 手感之外的行為皆可自動驗證（同 test_image_editing.py 的分工）。

驗證重點在「刪得掉」這條使用者撞到的死結：封面書名框刪到最後一字時 document@2
的「框 text 非空」不變式擋下刪除，出路是整框移除，故本檔對移除路徑（含串接鏈首
的文字承接）驗得最密。
"""
import pytest

from cjkfolio.cover import with_cover
from cjkfolio.document import (
    Document,
    Paragraph,
    TextFrame,
    document_from_dict,
    document_to_dict,
)
from cjkfolio.frame_box_editing import (
    add_text_frame,
    default_frame_rect,
    move_text_frame,
    remove_text_frame,
    resize_text_frame,
    text_frame_at_point,
)
from cjkfolio.frame_editing import FrameCursor
from cjkfolio.image_editing import handle_at_point, handle_rects, resize_rect
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

TEMPLATE_PATH = "templates/neizai-zhengli.json"
BODY_STYLE = "內文-明體直排"


def _doc(frames=()) -> Document:
    return Document(
        title="文字框測試",
        template="neizai-zhengli",
        master="A-內文版",
        paragraphs=(Paragraph(text="整理一個房間先要決定的不是收納盒。",
                              style=BODY_STYLE),),
        text_frames=tuple(frames),
    )


def _frame(text="邊欄註記", page=1, rect=(60.0, 80.0, 100.0, 240.0), thread=None):
    return TextFrame(text=text, style=BODY_STYLE, page=page, rect=rect,
                     thread=thread)


# --- 新增 -----------------------------------------------------------------

def test_add_text_frame_appends_independent_frame():
    tpl = load_template(TEMPLATE_PATH)
    doc = add_text_frame(_doc(), tpl, "新的一段話", BODY_STYLE, 2,
                         (40.0, 50.0, 90.0, 300.0))
    assert len(doc.text_frames) == 1
    tf = doc.text_frames[0]
    assert (tf.text, tf.page, tf.thread) == ("新的一段話", 2, None)
    assert tf.rect == (40.0, 50.0, 90.0, 300.0)


def test_add_text_frame_normalizes_reversed_rect():
    """拖出來的框可能由右下往左上拉，正規化後才寫入（訊息要講「文字框」不是圖框）。"""
    tpl = load_template(TEMPLATE_PATH)
    doc = add_text_frame(_doc(), tpl, "字", BODY_STYLE, 1,
                         (90.0, 300.0, 40.0, 50.0))
    assert doc.text_frames[0].rect == (40.0, 50.0, 90.0, 300.0)


def test_add_text_frame_rejects_unknown_style():
    tpl = load_template(TEMPLATE_PATH)
    with pytest.raises(ValueError, match="不存在於模版"):
        add_text_frame(_doc(), tpl, "字", "沒有這個樣式", 1, (0.0, 0.0, 50.0, 100.0))


def test_add_text_frame_rejects_empty_text():
    """空框違反 document@2「框 text 非空」，在此擋而非存檔時才炸。"""
    tpl = load_template(TEMPLATE_PATH)
    with pytest.raises(ValueError, match="框 text 非空"):
        add_text_frame(_doc(), tpl, "", BODY_STYLE, 1, (0.0, 0.0, 50.0, 100.0))


def test_add_text_frame_rejects_degenerate_rect():
    tpl = load_template(TEMPLATE_PATH)
    with pytest.raises(ValueError, match="文字框須有正的寬與高"):
        add_text_frame(_doc(), tpl, "字", BODY_STYLE, 1, (40.0, 50.0, 40.0, 300.0))


def test_default_frame_rect_derives_from_style_and_grid():
    """框寬＝欄距×欄數、框高＝字距×字數，與 frames 佈局同源，非硬編座標。"""
    tpl = load_template(TEMPLATE_PATH)
    master = tpl.masters["A-內文版"]
    from cjkfolio.frames import frame_pitch_pt
    from cjkfolio.layout import style_advance_pt
    st = tpl.paragraph_styles[BODY_STYLE]
    pitch = frame_pitch_pt(st, master.grid)
    advance = style_advance_pt(st, master.grid)

    x0, y0, x1, y1 = default_frame_rect(tpl, master, "五個字喔", BODY_STYLE,
                                        cx_pt=200.0, cy_pt=400.0)
    assert x1 - x0 == pytest.approx(pitch)          # 4 字單欄放得下 → 1 欄
    assert y1 - y0 == pytest.approx(4 * advance)
    assert (x0 + x1) / 2 == pytest.approx(200.0)    # 以落點為中心
    assert (y0 + y1) / 2 == pytest.approx(400.0)


def test_default_frame_rect_wraps_to_extra_columns():
    """字多到單欄放不下時往左加欄，框高不超過頁高比例上限（不撐出頁面）。"""
    tpl = load_template(TEMPLATE_PATH)
    master = tpl.masters["A-內文版"]
    narrow = default_frame_rect(tpl, master, "短", BODY_STYLE, 200.0, 400.0)
    wide = default_frame_rect(tpl, master, "長" * 400, BODY_STYLE, 200.0, 400.0)
    assert wide[2] - wide[0] > narrow[2] - narrow[0]
    page_h = tpl.page_height_mm * 72.0 / 25.4
    assert wide[3] - wide[1] <= page_h * 0.6 + 1e-6


# --- 平移與縮放 -----------------------------------------------------------

def test_move_text_frame_shifts_rect_and_keeps_content():
    doc = move_text_frame(_doc([_frame()]), 0, dx_pt=12.0, dy_pt=-8.0)
    tf = doc.text_frames[0]
    assert tf.rect == (72.0, 72.0, 112.0, 232.0)
    assert (tf.text, tf.style, tf.page) == ("邊欄註記", BODY_STYLE, 1)


def test_resize_text_frame_replaces_rect():
    doc = resize_text_frame(_doc([_frame()]), 0, (60.0, 80.0, 140.0, 400.0))
    assert doc.text_frames[0].rect == (60.0, 80.0, 140.0, 400.0)
    assert doc.text_frames[0].text == "邊欄註記"


def test_resize_text_frame_allows_shrinking_below_text_capacity():
    """縮到裝不下＝溢出違規（frames 層記錄），不是例外：使用者可能先縮框再刪字。"""
    tpl = load_template(TEMPLATE_PATH)
    from cjkfolio.frames import masters_for_layout, resolve_text_frames
    from cjkfolio.wrap import layout_with_wrap
    doc = resize_text_frame(_doc([_frame(text="很長的一段邊欄註記文字" * 3)]), 0,
                            (60.0, 80.0, 74.0, 100.0))
    layout = layout_with_wrap(doc, tpl)
    placements = resolve_text_frames(
        doc, tpl, masters_for_layout(tpl, doc, layout))
    assert any(p.violations for page in placements.values() for p in page)


def test_frame_corner_handles_reuse_image_rect_math():
    """框的四角控制點與拖角縮放直接復用同一份純矩形數學，不另立第二套幾何。"""
    rect = (60.0, 80.0, 100.0, 240.0)
    assert set(handle_rects(rect, 8.0)) == {"nw", "ne", "sw", "se"}
    assert handle_at_point(rect, 100.0, 240.0, 8.0) == "se"
    assert resize_rect(rect, "se", 150.0, 300.0) == (60.0, 80.0, 150.0, 300.0)


def test_move_text_frame_rejects_out_of_range_index():
    with pytest.raises(ValueError, match="越界"):
        move_text_frame(_doc([_frame()]), 3, 1.0, 1.0)


# --- 移除（使用者撞到的死結） ---------------------------------------------

def test_remove_text_frame_drops_frame():
    doc = remove_text_frame(_doc([_frame(text="甲"), _frame(text="乙")]), 0)
    assert [tf.text for tf in doc.text_frames] == ["乙"]


def test_remove_thread_head_promotes_text_to_next_frame():
    """鏈首一走，文字要交給下一框：續框自身不帶 text，不承接就整段消失。"""
    doc = _doc([_frame(text="接續的長文", thread="邊欄"),
                _frame(text="", page=2, thread="邊欄")])
    out = remove_text_frame(doc, 0)
    assert len(out.text_frames) == 1
    assert (out.text_frames[0].text, out.text_frames[0].page) == ("接續的長文", 2)


def test_remove_thread_head_promotion_survives_reload():
    """承接後的文件要讀得回來：不承接會留下無 text 的鏈首＝存檔即壞。"""
    doc = _doc([_frame(text="接續的長文", thread="邊欄"),
                _frame(text="", page=2, thread="邊欄")])
    out = remove_text_frame(doc, 0)
    reloaded = document_from_dict(document_to_dict(out))
    assert reloaded.text_frames[0].text == "接續的長文"


def test_remove_last_frame_of_thread_drops_text_with_it():
    doc = remove_text_frame(_doc([_frame(text="只有這框", thread="邊欄")]), 0)
    assert doc.text_frames == ()


def test_remove_text_frame_rejects_out_of_range_index():
    with pytest.raises(ValueError, match="越界"):
        remove_text_frame(_doc([_frame()]), 1)


# --- 命中判定 -------------------------------------------------------------

def test_text_frame_at_point_returns_topmost():
    """文件序＝繪製序，後置者疊在上，故反序尋找與畫面所見一致。"""
    doc = _doc([_frame(text="下", rect=(60.0, 80.0, 100.0, 240.0)),
                _frame(text="上", rect=(80.0, 100.0, 140.0, 300.0))])
    assert text_frame_at_point(doc, 1, 90.0, 150.0) == 1   # 兩框重疊處取上層
    assert text_frame_at_point(doc, 1, 65.0, 150.0) == 0
    assert text_frame_at_point(doc, 1, 300.0, 150.0) is None


def test_text_frame_at_point_ignores_other_pages():
    doc = _doc([_frame(page=2)])
    assert text_frame_at_point(doc, 1, 80.0, 150.0) is None
    assert text_frame_at_point(doc, 2, 80.0, 150.0) == 0


# --- session 接線與 undo --------------------------------------------------

def test_session_add_move_remove_share_one_history():
    """框編輯與文字、圖片共用同一條歷史：Ctrl+Z 的順序＝使用者實際操作的順序。"""
    session = EditSession(_doc(), load_template(TEMPLATE_PATH))
    assert session.add_text_frame("邊欄", BODY_STYLE, 1, (60.0, 80.0, 100.0, 240.0))
    assert session.move_text_frame(0, 10.0, 0.0)
    assert session.document.text_frames[0].rect[0] == pytest.approx(70.0)

    session.undo()
    assert session.document.text_frames[0].rect[0] == pytest.approx(60.0)
    session.undo()
    assert session.document.text_frames == ()
    session.redo()
    assert len(session.document.text_frames) == 1


def test_session_remove_text_frame_undoes_in_one_step():
    doc = _doc([_frame(text="要刪的框")])
    session = EditSession(doc, load_template(TEMPLATE_PATH))
    assert session.remove_text_frame(0)
    assert session.document.text_frames == ()
    session.undo()
    assert session.document.text_frames[0].text == "要刪的框"


def test_session_remove_text_frame_clears_stale_frame_cursor():
    """移除後右側框左移一位，留著舊 source_idx 會靜默指到別的框，故歸零。"""
    doc = _doc([_frame(text="甲框"), _frame(text="乙框")])
    session = EditSession(doc, load_template(TEMPLATE_PATH))
    session.insert_frame(FrameCursor(source_idx=1, caret=1), "！")
    assert isinstance(session.cursor, FrameCursor)

    result = session.remove_text_frame(0)
    assert not isinstance(result.cursor, FrameCursor)
    session.undo()  # 回退連框游標一併回原（歷史快照含游標）
    assert isinstance(session.cursor, FrameCursor)


def test_session_removes_cover_title_frame():
    """Owner 真情境：封面放了圖之後要把預設書名框整個刪掉，刪完仍可存檔讀回。"""
    tpl = load_template(TEMPLATE_PATH)
    doc = with_cover(_doc(), tpl, title="成名之路")
    session = EditSession(doc, tpl)
    assert session.document.text_frames[0].text == "成名之路"

    assert session.remove_text_frame(0)
    assert session.document.text_frames == ()
    reloaded = document_from_dict(document_to_dict(session.document))
    assert reloaded.text_frames == ()
    assert reloaded.cover == tpl.default_cover  # 刪書名框不影響封面本身
