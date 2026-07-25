"""成品尺寸（cjkfolio/page_size.py，Sprint 140）：換開本與版心重算兩種語意。

trim size 只存在模版一處（Template.page_width_mm／page_height_mm），PDF 的 TrimBox
與兩後端的頁面座標系皆自此推導。本測試釘住三件事：

1. refit_grid=False 只換紙張，一個網格參數都不動（頁數不變）。
2. refit_grid=True 邊距原封不動，把紙張增減換算成行列增減；尺寸沒變時對每個主版
   恰為零變更（no-op 回原物件，session 不推空 undo）。
3. page_fit_warnings 量的是紙邊而非名目邊距框，且據實列出不自動搬絕對 pt 錨點。

素材用本專案自擬模版 templates/neizai-zhengli.json（版權紅線：不引用參考書內容）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph, PlacedImage, TextFrame
from cjkfolio.page_size import (
    FIT_TOLERANCE_PT,
    MAX_PAGE_MM,
    new_fit_warnings,
    page_fit_warnings,
    set_page_size,
)
from cjkfolio.primitives import PT_PER_MM
from cjkfolio.session import EditSession
from cjkfolio.styles import TemplateError, load_template

ROOT = Path(__file__).resolve().parents[1]

BODY = "A-內文版"      # 版心齊自己的名目邊距（32 字 × 13 行）
PART = "B-部扉"        # 宣告 8 行、末行外緣本來就越過紙邊（模版既有狀態）
COLOPHON = "F-版權頁"  # 45 行小字，版心刻意跨過名目訂口


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _grid(t, master: str):
    return t.masters[master].grid


# --- 只換紙張（refit_grid=False） ---------------------------------------


def test_plain_resize_changes_paper_only(template):
    """換紙張不動任何網格參數：一個字都不重排，頁數不變。"""
    out = set_page_size(template, 128.0, 188.0)
    assert (out.page_width_mm, out.page_height_mm) == (128.0, 188.0)
    assert out.masters == template.masters


def test_plain_resize_keeps_other_template_parts(template):
    """版面尺寸之外的模版內容（色彩、段落樣式、預設主版）原樣不動。"""
    out = set_page_size(template, 128.0, 188.0)
    assert out.colors == template.colors
    assert out.paragraph_styles == template.paragraph_styles
    assert out.default_master == template.default_master


def test_same_size_is_noop_object(template):
    """等值變更回原物件：session 的 `template is self._template` 判定成立、不推空 undo。"""
    assert set_page_size(template, 148.0, 210.0) is template
    assert set_page_size(template, 148.0, 210.0, refit_grid=True) is template


def test_int_dimensions_accepted(template):
    """整數 mm 收得下並存成 float（Qt 的 spin box 可能給 int）。"""
    out = set_page_size(template, 128, 188)
    assert (out.page_width_mm, out.page_height_mm) == (128.0, 188.0)


@pytest.mark.parametrize("bad", [0, -1.0, MAX_PAGE_MM + 1, "a5", None, True])
def test_invalid_dimensions_rejected(template, bad):
    """成品尺寸在邊界快速失敗，不讓 0／負值／超 PDF 盒框上限的紙張進到排版層。"""
    with pytest.raises(TemplateError):
        set_page_size(template, bad, 210.0)
    with pytest.raises(TemplateError):
        set_page_size(template, 148.0, bad)


# --- 重算版心行列（refit_grid=True） ------------------------------------


def test_refit_adds_exactly_the_rows_the_paper_gained(template):
    """加高剛好三個字身 → 每行恰多三字；加寬兩個行距 → 每頁恰多兩行。"""
    g = _grid(template, BODY)
    out = set_page_size(
        template,
        148.0 + 2 * g.line_pitch_pt / PT_PER_MM,
        210.0 + 3 * g.char_advance_pt / PT_PER_MM,
        refit_grid=True)
    assert _grid(out, BODY).chars_per_line == g.chars_per_line + 3
    assert _grid(out, BODY).lines_per_page == g.lines_per_page + 2


def test_refit_removes_rows_when_paper_shrinks(template):
    """縮紙張 → 行列數減少（換小開本時內文重排、頁數會變）。"""
    g = _grid(template, BODY)
    out = set_page_size(template, 128.0, 188.0, refit_grid=True)
    assert _grid(out, BODY).chars_per_line < g.chars_per_line
    assert _grid(out, BODY).lines_per_page < g.lines_per_page


def test_refit_keeps_margins_and_pitches(template):
    """重算的只有行列「數」：邊距、字距、行距、基準級數全部原封不動。"""
    out = set_page_size(template, 128.0, 188.0, refit_grid=True)
    for name, master in template.masters.items():
        got = out.masters[name]
        assert got.margins == master.margins
        assert got.grid.char_advance_pt == master.grid.char_advance_pt
        assert got.grid.line_pitch_pt == master.grid.line_pitch_pt
        assert got.grid.base_size_pt == master.grid.base_size_pt


def test_refit_preserves_deliberate_overhang(template):
    """版心不齊名目邊距的主版（部扉、版權頁），與自身邊距的既有關係原樣保留。

    採「增減量」而非「拿邊距框重算」的理由就在這：換開本不該順手把這些主版重新設計。
    """
    grow_mm = 5 * _grid(template, COLOPHON).line_pitch_pt / PT_PER_MM
    out = set_page_size(template, 148.0 + grow_mm, 210.0, refit_grid=True)
    assert (_grid(out, COLOPHON).lines_per_page
            == _grid(template, COLOPHON).lines_per_page + 5)
    assert (_grid(out, PART).chars_per_line
            == _grid(template, PART).chars_per_line)


def test_refit_clamps_to_one(template):
    """紙張小到放不下一行時夾到 1，不產生 0 或負的網格（溢出交給警告據實回報）。"""
    out = set_page_size(template, 1.0, 1.0, refit_grid=True)
    for master in out.masters.values():
        assert master.grid.chars_per_line >= 1
        assert master.grid.lines_per_page >= 1


def test_refit_tolerates_mm_rounding(template):
    """邊距以 mm 記兩位小數必有 pt 捨入差，容差內不誤加減行。

    A-內文版的 inner 25.58mm 即由 13 行網格反推後四捨五入，實算差 0.03pt。
    """
    epsilon_mm = 0.4 * FIT_TOLERANCE_PT / PT_PER_MM
    out = set_page_size(template, 148.0 + epsilon_mm, 210.0, refit_grid=True)
    assert _grid(out, BODY).lines_per_page == _grid(template, BODY).lines_per_page


# --- 溢出回報 -----------------------------------------------------------


def test_shipped_template_body_master_fits(template):
    """出貨模版的內文版在自家尺寸內齊邊：捨入差不該被報成溢出。"""
    keys = {w.key for w in page_fit_warnings(template)}
    assert not [k for k in keys if k.startswith(BODY)]


def test_warning_measures_paper_not_nominal_margin_box(template):
    """量的是紙邊：版權頁 45 行跨過名目訂口不報，跨過紙邊才報。"""
    assert f"{COLOPHON}/版心寬" not in {w.key for w in page_fit_warnings(template)}
    shrunk = set_page_size(template, 128.0, 188.0)
    assert f"{COLOPHON}/版心寬" in {w.key for w in page_fit_warnings(shrunk)}


def test_warning_reports_body_height_overflow(template):
    """紙張矮到版心下緣越過紙邊時據實回報高度溢出（含實際 pt 座標）。"""
    shrunk = set_page_size(template, 148.0, 120.0)
    hits = [w for w in page_fit_warnings(shrunk) if w.key == f"{BODY}/版心高"]
    assert len(hits) == 1
    assert "版心高" in hits[0].message and "超出成品高" in hits[0].message


def test_warning_reports_absolute_pt_anchors(template):
    """頁腳基線等絕對 pt 錨點不隨紙張縮放，落在紙外要據實列出。"""
    shrunk = set_page_size(template, 148.0, 120.0)
    keys = {w.key for w in page_fit_warnings(shrunk)}
    assert f"{BODY}/頁腳「page_number」基線" in keys
    assert f"D-目錄/目錄頁碼底錨" in keys
    assert f"G-圖文版/圖框保留區下緣" in keys


def test_new_fit_warnings_hides_pre_existing(template):
    """改尺寸前就溢出的項不重複列出，免得淹掉這次真正造成的溢出。"""
    assert f"{PART}/版心寬" in {w.key for w in page_fit_warnings(template)}
    shrunk = set_page_size(template, 128.0, 188.0)
    news = new_fit_warnings(template, shrunk)
    assert not [m for m in news if PART in m]
    assert [m for m in news if COLOPHON in m]


def test_refit_path_reports_no_new_body_overflow(template):
    """勾了重算版心，版心本身就不冒出新的溢出（換小開本是內文重排，不是把字擠出紙外）。"""
    for w_mm, h_mm in ((128.0, 188.0), (182.0, 257.0), (105.0, 148.0)):
        out = set_page_size(template, w_mm, h_mm, refit_grid=True)
        assert [m for m in new_fit_warnings(template, out) if "版心" in m] == []


def test_refit_does_not_rescue_absolute_anchors(template):
    """重算版心救不了絕對 pt 錨點：頁腳基線是一手量測值，紙張矮過它就照報不誤。

    這是本模組明講的界線（不機械縮放一手量測的座標），不是漏做；A6 這種大幅縮
    開本仍須人工調頁腳。
    """
    out = set_page_size(template, 105.0, 148.0, refit_grid=True)
    assert [m for m in new_fit_warnings(template, out) if "頁腳" in m]


# --- 文件層置入圖與文字框 -----------------------------------------------


def _doc_with(images=(), frames=()) -> Document:
    return Document(title="t", template="neizai-zhengli", master=BODY,
                    paragraphs=(Paragraph(text="測試", style="內文-明體直排"),),
                    images=tuple(images), text_frames=tuple(frames))


def test_placed_image_outside_new_trim_reported(template):
    """置入圖的 rect 是絕對 pt，不隨紙張縮放；落到新成品外要點名。"""
    doc = _doc_with(images=[PlacedImage(path="art/x.png", page=1,
                                        rect=(300.0, 400.0, 400.0, 560.0))])
    shrunk = set_page_size(template, 105.0, 148.0)
    assert [m for m in new_fit_warnings(template, shrunk, doc)
            if m.startswith("置入圖 1（x.png，頁 1）")]


def test_slot_image_without_rect_skipped(template):
    """槽式置入圖依主版圖框保留區推導、無自身座標，不該被當成溢出。"""
    doc = _doc_with(images=[PlacedImage(path="art/x.png", page=1)])
    shrunk = set_page_size(template, 105.0, 148.0)
    assert not [m for m in new_fit_warnings(template, shrunk, doc) if "置入圖" in m]


def test_text_frame_outside_new_trim_reported(template):
    """文字框同理：座標一手指定，換小紙就要據實說它跑到成品外。"""
    doc = _doc_with(frames=[TextFrame(text="框", style="內文-明體直排", page=1,
                                      rect=(200.0, 300.0, 380.0, 500.0))])
    shrunk = set_page_size(template, 105.0, 148.0)
    assert [m for m in new_fit_warnings(template, shrunk, doc) if m.startswith("文字框 1")]


def test_session_page_size_undo_restores_paper_and_grid(template):
    """改成品尺寸入統一 undo 歷史：一步還原紙張與版心，頁數回原值。"""
    session = EditSession(_doc_with(), template)
    pages_before = len(session.layout.pages)
    assert session.update_page_size(105.0, 148.0, refit_grid=True) is not None
    assert session.template.page_width_mm == 105.0
    assert _grid(session.template, BODY).chars_per_line < _grid(template, BODY).chars_per_line
    session.undo()
    assert session.template is template
    assert len(session.layout.pages) == pages_before


def test_session_same_size_not_in_history(template):
    """等值變更 no-op 回 None，不推一步看不出差別的 undo。"""
    session = EditSession(_doc_with(), template)
    assert session.update_page_size(148.0, 210.0) is None
    assert session.update_page_size(148.0, 210.0, refit_grid=True) is None


def test_session_rejects_bad_size_without_changing_state(template):
    """非法尺寸於套用前快速失敗：模版與版面狀態不變。"""
    session = EditSession(_doc_with(), template)
    with pytest.raises(TemplateError):
        session.update_page_size(0.0, 210.0)
    assert session.template is template


def test_session_refit_reflows_body(template):
    """縮開本並勾重算 → 內文真的重排（同一份文件的頁數變多）。"""
    long_doc = Document(title="t", template="neizai-zhengli", master=BODY,
                        paragraphs=tuple(
                            Paragraph(text="測試字句" * 20, style="內文-明體直排")
                            for _ in range(6)))
    session = EditSession(long_doc, template)
    before = len(session.layout.pages)
    session.update_page_size(105.0, 148.0, refit_grid=True)
    assert len(session.layout.pages) > before


def test_in_range_placements_silent(template):
    """落在成品內的置入圖與文字框不出聲（不製造要使用者忽略的雜訊）。"""
    doc = _doc_with(images=[PlacedImage(path="art/x.png", page=1,
                                        rect=(20.0, 20.0, 120.0, 160.0))],
                    frames=[TextFrame(text="框", style="內文-明體直排", page=1,
                                      rect=(20.0, 200.0, 120.0, 300.0))])
    bigger = set_page_size(template, 182.0, 257.0)
    assert new_fit_warnings(template, bigger, doc) == []
