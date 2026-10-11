"""整版等比換開本（cjkfolio/page_scale.py，Sprint 157）。

Owner：「變更尺寸時，原本裡面的文字字級要等比例變大」，選定整版等比縮放：字級、字距、
行距、邊距、頁腳、圖框與文字框同乘一倍率，行列數與頁數不變；寬高比例不同時取較小倍率，
多出的空間平均補到邊距。本測試釘住：

1. 倍率與置中對應（同比例＝四邊邊距同乘 k；不同比例＝長軸多出的空間對半補）。
2. 真樣張重排後頁數不變、每頁行數不變、字身跟著乘 k。
3. 整頁蓋滿的置入圖換開本後仍蓋滿頁面＋四邊出血（不讓匯出白邊回來）。
4. session 單一 undo 步、尺寸不變 no-op。

素材用本專案自擬模版與樣張（版權紅線）。
"""
from dataclasses import replace
from pathlib import Path

import pytest

from cjkfolio.document import PlacedImage, TextFrame, load_document
from cjkfolio.page_scale import scale_factor, scale_page_size
from cjkfolio.press_marks import BLEED_MM
from cjkfolio.primitives import PT_PER_MM
from cjkfolio.session import EditSession
from cjkfolio.styles import TemplateError, load_template
from cjkfolio.wrap import layout_with_wrap

ROOT = Path(__file__).resolve().parents[1]
BODY = "A-內文版"
B = BLEED_MM * PT_PER_MM
W = 148.0 * PT_PER_MM
H = 210.0 * PT_PER_MM


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


@pytest.fixture(scope="module")
def doc():
    return load_document(ROOT / "samples" / "paiban-xiaoji-ch1.doc.json")


def test_factor_takes_smaller_axis(template):
    assert scale_factor(template, 296.0, 420.0) == pytest.approx(2.0)
    assert scale_factor(template, 170.0, 230.0) == pytest.approx(230.0 / 210.0)


def test_same_aspect_scales_every_length(template, doc):
    new_t, _ = scale_page_size(template, doc, 185.0, 262.5, bleed_pt=B)  # k＝1.25
    old, new = template.masters[BODY], new_t.masters[BODY]
    for f in ("top_mm", "bottom_mm", "outer_mm", "inner_mm"):
        assert getattr(new.margins, f) == pytest.approx(getattr(old.margins, f) * 1.25)
    assert new.grid.char_advance_pt == pytest.approx(old.grid.char_advance_pt * 1.25)
    assert new.grid.chars_per_line == old.grid.chars_per_line
    assert new.grid.lines_per_page == old.grid.lines_per_page
    for name, st in template.paragraph_styles.items():
        assert new_t.paragraph_styles[name].size_pt == pytest.approx(st.size_pt * 1.25)
    for name, item in old.footer.items():
        assert new.footer[name].baseline_from_top_pt == pytest.approx(
            item.baseline_from_top_pt * 1.25)


def test_extra_room_split_evenly_to_margins(template, doc):
    """18 開 170×230：高軸填滿（k＝230/210），寬軸多出的空間對半補到書口與訂口。"""
    new_t, _ = scale_page_size(template, doc, 170.0, 230.0, bleed_pt=B)
    k = 230.0 / 210.0
    half = (170.0 - 148.0 * k) / 2
    old, new = template.masters[BODY].margins, new_t.masters[BODY].margins
    assert new.outer_mm == pytest.approx(old.outer_mm * k + half)
    assert new.inner_mm == pytest.approx(old.inner_mm * k + half)
    assert new.top_mm == pytest.approx(old.top_mm * k)
    assert new.bottom_mm == pytest.approx(old.bottom_mm * k)


@pytest.mark.parametrize("size", [(170.0, 230.0), (130.0, 185.0), (210.0, 297.0)])
def test_real_sample_keeps_pages_and_lines(template, doc, size):
    before = layout_with_wrap(doc, template)
    new_t, new_doc = scale_page_size(template, doc, *size, bleed_pt=B)
    after = layout_with_wrap(new_doc, new_t)
    assert len(after.pages) == len(before.pages)
    for p0, p1 in zip(before.pages, after.pages):
        assert len(p0.placed) == len(p1.placed), p0.number


def test_text_frame_rect_maps_with_page(template, doc):
    tf = TextFrame(text="框", style=next(iter(template.paragraph_styles)), page=1,
                   rect=(10.0, 20.0, 50.0, 120.0))
    src = replace(doc, text_frames=(tf,))
    _, new_doc = scale_page_size(template, src, 296.0, 420.0, bleed_pt=B)
    assert new_doc.text_frames[0].rect == pytest.approx((20.0, 40.0, 100.0, 240.0))


@pytest.mark.parametrize("size", [(170.0, 230.0), (210.0, 285.0), (130.0, 185.0)])
def test_full_bleed_image_still_covers_bleed_box(template, doc, size):
    """滿版圖換到比例不同的開本：仍蓋滿四邊出血，匯出不露白邊。"""
    img = PlacedImage(path="a.png", page=1, rect=(-B, -B, W + B, H + B))
    small = PlacedImage(path="b.png", page=1, rect=(30.0, 40.0, 90.0, 100.0))
    src = replace(doc, images=(img, small))
    _, new_doc = scale_page_size(template, src, *size, bleed_pt=B)
    x0, y0, x1, y1 = new_doc.images[0].rect
    nw, nh = size[0] * PT_PER_MM, size[1] * PT_PER_MM
    assert x0 <= -B + 1e-6 and y0 <= -B + 1e-6 and x1 >= nw + B - 1e-6 and y1 >= nh + B - 1e-6
    assert (x1 - x0) / (y1 - y0) == pytest.approx((W + 2 * B) / (H + 2 * B))
    k = scale_factor(template, *size)
    sx0, sy0, sx1, sy1 = new_doc.images[1].rect
    assert (sx1 - sx0, sy1 - sy0) == pytest.approx((60.0 * k, 60.0 * k))


def test_same_size_is_noop_and_bad_size_fails(template, doc):
    assert scale_page_size(template, doc, 148.0, 210.0, bleed_pt=B) == (template, doc)
    with pytest.raises(TemplateError):
        scale_page_size(template, doc, 0, 210.0, bleed_pt=B)


def test_session_single_undo_step(template, doc):
    s = EditSession(doc, template)
    pages = len(s.layout.pages)
    assert s.scale_page_size(170.0, 230.0, bleed_pt=B) is not None
    assert s.template.page_width_mm == 170.0 and len(s.layout.pages) == pages
    assert s.scale_page_size(170.0, 230.0, bleed_pt=B) is None
    s.undo()
    assert s.template is template and s.document is doc
