"""置入圖編輯純函式與 session 接線（Sprint 102，畫布拖放與縮放置圖 UI 的判定層）。

本檔全數為 Qt 無關的離屏驗證：畫布只把滑鼠事件換算成 trim pt，圖框的建立、
平移、縮放、命中判定與 undo 歷史全在此層，故 UI 手感之外的行為皆可自動驗證。
"""
import pytest

from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.image_editing import (
    MIN_IMAGE_SIZE_PT,
    default_image_rect,
    handle_at_point,
    handle_rects,
    image_at_point,
    move_image,
    normalize_rect,
    place_image,
    remove_image,
    resize_image,
    resize_rect,
    set_image_wrap,
)
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

TEMPLATE_PATH = "templates/neizai-zhengli.json"


def _doc(images=()) -> Document:
    return Document(
        title="置圖測試",
        template="neizai-zhengli",
        master="A-內文版",
        paragraphs=(Paragraph(text="整理一個房間先要決定的不是收納盒。",
                              style="內文-明體直排"),),
        images=tuple(images),
    )


# --- 正規化與預設置入尺寸 -------------------------------------------------

def test_normalize_rect_sorts_corners():
    assert normalize_rect((120.0, 300.0, 40.0, 100.0)) == (40.0, 100.0, 120.0, 300.0)


def test_normalize_rect_rejects_degenerate():
    with pytest.raises(ValueError):
        normalize_rect((50.0, 100.0, 50.0, 260.0))


def test_default_image_rect_uses_300ppi_native_size():
    """§9 連續調影像下限 300ppi＝「符合規格前提下能放多大」，取為預設置入尺寸。"""
    rect = default_image_rect(600, 300, cx_pt=200.0, cy_pt=400.0,
                              page_w_pt=419.53, page_h_pt=595.28)
    x0, y0, x1, y1 = rect
    assert x1 - x0 == pytest.approx(600 * 72 / 300)  # 144pt
    assert y1 - y0 == pytest.approx(300 * 72 / 300)  # 72pt
    assert (x0 + x1) / 2 == pytest.approx(200.0)     # 落點置中
    assert (y0 + y1) / 2 == pytest.approx(400.0)


def test_default_image_rect_scales_down_to_fit_page():
    """原生尺寸超出頁面時等比縮到整頁可容（不裁切、不變形）。"""
    rect = default_image_rect(6000, 3000, cx_pt=200.0, cy_pt=300.0,
                              page_w_pt=419.53, page_h_pt=595.28)
    x0, y0, x1, y1 = rect
    assert x1 - x0 == pytest.approx(419.53)
    assert (y1 - y0) / (x1 - x0) == pytest.approx(0.5)  # 比例不變


def test_default_image_rect_rejects_non_positive_pixels():
    with pytest.raises(ValueError):
        default_image_rect(0, 300, cx_pt=100.0, cy_pt=100.0,
                           page_w_pt=419.53, page_h_pt=595.28)


# --- 文件層編輯（不可變，原文件不動） ------------------------------------

def test_place_image_appends_and_leaves_original_untouched():
    doc = _doc()
    out = place_image(doc, "photo.png", page=1, rect=(40.0, 100.0, 160.0, 220.0))
    assert len(doc.images) == 0
    assert len(out.images) == 1
    assert out.images[0] == PlacedImage(path="photo.png", page=1,
                                        rect=(40.0, 100.0, 160.0, 220.0))


def test_place_image_normalizes_reversed_rect():
    out = place_image(_doc(), "photo.png", page=1, rect=(160.0, 220.0, 40.0, 100.0))
    assert out.images[0].rect == (40.0, 100.0, 160.0, 220.0)


def test_place_image_rejects_bad_page():
    with pytest.raises(ValueError):
        place_image(_doc(), "photo.png", page=0, rect=(40.0, 100.0, 160.0, 220.0))


def test_move_image_shifts_rect_and_keeps_other_fields():
    doc = _doc([PlacedImage("a.png", 1, (40.0, 100.0, 160.0, 220.0),
                            wrap=True, wrap_margin_mm=4.26)])
    out = move_image(doc, 0, 10.0, -25.0)
    assert out.images[0].rect == (50.0, 75.0, 170.0, 195.0)
    assert out.images[0].wrap is True
    assert out.images[0].wrap_margin_mm == 4.26


def test_resize_image_replaces_rect():
    doc = _doc([PlacedImage("a.png", 1, (40.0, 100.0, 160.0, 220.0))])
    out = resize_image(doc, 0, (40.0, 100.0, 100.0, 160.0))
    assert out.images[0].rect == (40.0, 100.0, 100.0, 160.0)


def test_remove_image_drops_only_that_entry():
    doc = _doc([PlacedImage("a.png", 1, (0.0, 0.0, 10.0, 10.0)),
                PlacedImage("b.png", 1, (20.0, 20.0, 30.0, 30.0))])
    out = remove_image(doc, 0)
    assert [im.path for im in out.images] == ["b.png"]


def test_edit_functions_reject_out_of_range_index():
    doc = _doc([PlacedImage("a.png", 1, (0.0, 0.0, 10.0, 10.0))])
    for fn in (lambda: move_image(doc, 3, 1.0, 1.0),
               lambda: resize_image(doc, 3, (0.0, 0.0, 5.0, 5.0)),
               lambda: remove_image(doc, 3)):
        with pytest.raises(ValueError):
            fn()


def test_move_slot_image_rejected_because_it_has_no_coordinates():
    """槽式圖（rect None）由主版 figure 保留區定位，拖放語意不成立（不沉默改成 rect）。"""
    doc = _doc([PlacedImage("a.png", 1, None)])
    with pytest.raises(ValueError):
        move_image(doc, 0, 5.0, 5.0)


# --- 命中判定與控制點 ------------------------------------------------------

def test_image_at_point_returns_topmost_by_document_order():
    """文件序＝繪製序（Sprint 54），故重疊時後者在上、應優先命中。"""
    doc = _doc([PlacedImage("under.png", 1, (0.0, 0.0, 100.0, 100.0)),
                PlacedImage("over.png", 1, (50.0, 50.0, 150.0, 150.0))])
    assert image_at_point(doc, 1, 75.0, 75.0) == 1
    assert image_at_point(doc, 1, 10.0, 10.0) == 0
    assert image_at_point(doc, 1, 200.0, 200.0) is None


def test_image_at_point_ignores_other_pages_and_slot_images():
    doc = _doc([PlacedImage("other.png", 2, (0.0, 0.0, 100.0, 100.0)),
                PlacedImage("slot.png", 1, None)])
    assert image_at_point(doc, 1, 50.0, 50.0) is None


def test_handle_rects_are_four_corners_centred_on_them():
    rect = (40.0, 100.0, 160.0, 220.0)
    handles = handle_rects(rect, handle_pt=8.0)
    assert set(handles) == {"nw", "ne", "sw", "se"}
    hx0, hy0, hx1, hy1 = handles["se"]
    assert (hx0 + hx1) / 2 == pytest.approx(160.0)
    assert (hy0 + hy1) / 2 == pytest.approx(220.0)
    assert hx1 - hx0 == pytest.approx(8.0)


def test_handle_at_point_hits_corner_and_misses_centre():
    rect = (40.0, 100.0, 160.0, 220.0)
    assert handle_at_point(rect, 41.0, 101.0, handle_pt=8.0) == "nw"
    assert handle_at_point(rect, 100.0, 160.0, handle_pt=8.0) is None


# --- 縮放幾何 --------------------------------------------------------------

def test_resize_rect_free_moves_dragged_corner_only():
    rect = (40.0, 100.0, 160.0, 220.0)
    assert resize_rect(rect, "se", 200.0, 300.0) == (40.0, 100.0, 200.0, 300.0)
    assert resize_rect(rect, "nw", 60.0, 120.0) == (60.0, 120.0, 160.0, 220.0)


def test_resize_rect_free_clamps_to_minimum_side():
    """拖成零寬框後再也點不到，故夾最小邊長（方向維持拖曳側）。"""
    rect = (40.0, 100.0, 160.0, 220.0)
    out = resize_rect(rect, "se", 41.0, 300.0)
    assert out[2] - out[0] == pytest.approx(MIN_IMAGE_SIZE_PT)
    assert out[0] == pytest.approx(40.0)  # 對角固定


def test_resize_rect_aspect_keeps_image_ratio():
    """等比縮放（框恆貼合來源影像比例）：拖多少放大多少，不產生 contain 留白。"""
    rect = (40.0, 100.0, 160.0, 220.0)
    out = resize_rect(rect, "se", 280.0, 130.0, aspect=2.0)
    assert out[2] - out[0] == pytest.approx(240.0)      # 取較大的拖曳範圍
    assert (out[2] - out[0]) / (out[3] - out[1]) == pytest.approx(2.0)
    assert (out[0], out[1]) == (40.0, 100.0)            # 對角固定


def test_resize_rect_aspect_follows_vertical_drag():
    rect = (40.0, 100.0, 160.0, 220.0)
    out = resize_rect(rect, "se", 170.0, 400.0, aspect=2.0)
    assert out[3] - out[1] == pytest.approx(300.0)
    assert (out[2] - out[0]) / (out[3] - out[1]) == pytest.approx(2.0)


def test_resize_rect_aspect_clamps_minimum_on_both_axes():
    rect = (40.0, 100.0, 160.0, 220.0)
    out = resize_rect(rect, "se", 41.0, 101.0, aspect=2.0)
    assert out[2] - out[0] >= MIN_IMAGE_SIZE_PT
    assert out[3] - out[1] >= MIN_IMAGE_SIZE_PT
    assert (out[2] - out[0]) / (out[3] - out[1]) == pytest.approx(2.0)


def test_resize_rect_rejects_unknown_handle():
    with pytest.raises(ValueError):
        resize_rect((40.0, 100.0, 160.0, 220.0), "middle", 200.0, 300.0)


# --- session 接線（入統一 undo／redo 歷史） -------------------------------

def test_session_place_move_resize_remove_each_one_undo_step():
    template = load_template(TEMPLATE_PATH)
    session = EditSession(_doc(), template)

    session.place_image("photo.png", 1, (40.0, 100.0, 160.0, 220.0))
    assert len(session.document.images) == 1
    session.move_image(0, 10.0, 10.0)
    assert session.document.images[0].rect == (50.0, 110.0, 170.0, 230.0)
    session.resize_image(0, (50.0, 110.0, 110.0, 170.0))
    assert session.document.images[0].rect == (50.0, 110.0, 110.0, 170.0)
    session.remove_image(0)
    assert session.document.images == ()

    for expected in ((50.0, 110.0, 110.0, 170.0), (50.0, 110.0, 170.0, 230.0),
                     (40.0, 100.0, 160.0, 220.0)):
        session.undo()
        assert session.document.images[0].rect == expected
    session.undo()
    assert session.document.images == ()  # 回到置入前


def test_session_image_edits_are_redoable():
    session = EditSession(_doc(), load_template(TEMPLATE_PATH))
    session.place_image("photo.png", 1, (40.0, 100.0, 160.0, 220.0))
    session.undo()
    assert session.document.images == ()
    session.redo()
    assert session.document.images[0].path == "photo.png"


def test_session_image_edit_does_not_disturb_text_layout():
    """未開繞排的 rect 圖不改流排（wrap=False 為預設＝圖疊於文上，回歸鐵律）。"""
    session = EditSession(_doc(), load_template(TEMPLATE_PATH))
    before = len(session.layout.pages)
    session.place_image("photo.png", 1, (40.0, 100.0, 160.0, 220.0))
    assert len(session.layout.pages) == before


# --- 繞排參數（Sprint 103，GAPS #49 (e)） ---------------------------------

# 真書 PDF 53 R 半頁一手量測的圖框（tools/measure_wrap_pages.py，見 test_wrap.py）：
# 跨 A-內文版數欄，故開繞排後受影響欄的行長變化在版面上可觀測。
WRAP_RECT = (76.64, 289.01, 195.66, 467.54)


def _wrap_doc() -> Document:
    """長段落＋跨欄置入圖：繞排開關的效果可由逐欄行長觀測。"""
    return Document(
        title="繞排參數測試",
        template="neizai-zhengli",
        master="A-內文版",
        paragraphs=(Paragraph(text="整理一個房間先要決定的不是收納盒。" * 40,
                              style="內文-明體直排"),),
        images=(PlacedImage(path="photo.png", page=1, rect=WRAP_RECT),),
    )


def _caps(session) -> dict:
    """首頁逐欄行長 {slot: cap}（繞排把受影響欄的行裁短）。"""
    return {pl.slot: pl.line.cap for pl in session.layout.pages[0].placed}


def test_set_image_wrap_turns_wrap_on_with_margin():
    doc = set_image_wrap(_doc([PlacedImage(path="p.png", page=1,
                                           rect=(40.0, 100.0, 160.0, 220.0))]),
                         0, wrap=True, margin_mm=2.5)
    assert doc.images[0].wrap is True
    assert doc.images[0].wrap_margin_mm == 2.5
    assert doc.images[0].rect == (40.0, 100.0, 160.0, 220.0)  # 其餘欄位原樣


def test_set_image_wrap_omitted_fields_keep_current_value():
    """只改間隙不動開關（反之亦然）：未指定的欄位保持現值。"""
    base = _doc([PlacedImage(path="p.png", page=1, rect=(40.0, 100.0, 160.0, 220.0),
                             wrap=True, wrap_margin_mm=1.0)])
    assert set_image_wrap(base, 0, margin_mm=3.0).images[0].wrap is True
    assert set_image_wrap(base, 0, wrap=False).images[0].wrap_margin_mm == 1.0


def test_set_image_wrap_no_op_returns_same_document():
    """等值變更回原文件（session 據此判 no-op，不塞一步空 undo）。"""
    base = _doc([PlacedImage(path="p.png", page=1, rect=(40.0, 100.0, 160.0, 220.0),
                             wrap=True, wrap_margin_mm=2.0)])
    assert set_image_wrap(base, 0, wrap=True, margin_mm=2.0) is base


def test_set_image_wrap_rejects_slot_image():
    """槽式圖（主版 figure 保留區定位）無座標故無排除區，快速失敗不默默略過。"""
    with pytest.raises(ValueError, match="槽式"):
        set_image_wrap(_doc([PlacedImage(path="p.png", page=1)]), 0, wrap=True)


def test_set_image_wrap_rejects_negative_margin():
    with pytest.raises(ValueError, match="間隙"):
        set_image_wrap(_doc([PlacedImage(path="p.png", page=1,
                                         rect=(40.0, 100.0, 160.0, 220.0))]),
                       0, margin_mm=-0.5)


def test_set_image_wrap_rejects_out_of_range_index():
    with pytest.raises(ValueError, match="越界"):
        set_image_wrap(_doc(), 0, wrap=True)


def test_session_wrap_toggle_reflows_canvas_layout_and_undoes():
    """畫布所見即繞排所得：session 重排入口與兩渲染後端同為 layout_with_wrap。"""
    session = EditSession(_wrap_doc(), load_template(TEMPLATE_PATH))
    full = _caps(session)
    session.set_image_wrap(0, wrap=True)
    wrapped = _caps(session)
    shortened = [s for s, cap in wrapped.items() if cap < full.get(s, cap)]
    assert shortened, f"開繞排後應有欄被圖裁切（行長 {full} → {wrapped}）"
    session.undo()
    assert _caps(session) == full, "undo 應回到未繞排的版面"


def test_session_wrap_margin_widens_exclusion():
    """加大間隙＝排除區外擴，受影響欄的行再短一截（間隙由使用者表達，不硬編）。"""
    session = EditSession(_wrap_doc(), load_template(TEMPLATE_PATH))
    session.set_image_wrap(0, wrap=True)
    tight = _caps(session)
    session.set_image_wrap(0, margin_mm=6.0)
    loose = _caps(session)
    assert any(loose[s] < tight[s] for s in tight), f"{tight} → {loose}"


def test_session_wrap_no_op_does_not_add_undo_step():
    session = EditSession(_wrap_doc(), load_template(TEMPLATE_PATH))
    session.set_image_wrap(0, wrap=True)
    assert session.set_image_wrap(0, wrap=True) is None
    session.undo()
    assert session.document.images[0].wrap is False  # 只回退一步即回到未繞排
