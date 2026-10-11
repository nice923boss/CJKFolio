"""畫布出血範圍（Sprint 156）。

Owner：「App畫布增加出血框範圍，用紅線框顯示」。先前畫布只畫成品範圍，滿版圖
沒拉進出血區時畫面看不出來，匯出 PDF 才見白邊。出血底圖外擴 3mm，畫出伸進出血
區的置入圖；成品範圍內逐像素等同原本的底圖（互動層幾何不動的前提）。
紅框與對頁行為走 smoke C46；本檔測 Qt 無關的渲染與幾何純函式。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from PySide6.QtGui import QImage

from cjkfolio.document import Document, Paragraph
from cjkfolio.press_marks import BLEED_MM
from cjkfolio.render import PageRenderer, mm_to_pt
from cjkfolio.styles import load_template
from cjkfolio.wrap import layout_with_wrap
from editor.canvas import bleed_base_pos, bleed_px_for, crop_spine_bleed

ROOT = Path(__file__).resolve().parents[1]
W = mm_to_pt(148.0)
H = mm_to_pt(210.0)
B = mm_to_pt(BLEED_MM)
DPI = 150


@pytest.fixture(scope="module")
def setup():
    template = load_template(ROOT / "templates" / "neizai-zhengli.json")
    doc = Document(title="出血畫布", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="出血畫布內文。", style="內文-明體直排"),))
    page = layout_with_wrap(doc, template).pages[0]
    return PageRenderer(template, doc.master, dpi=DPI), page


def render(setup, rect, size_px, bleed_pt):
    renderer, page = setup
    images = (("a.png", Image.new("L", size_px, 90), rect),)
    return renderer.render_page(page, images=images, bleed_pt=bleed_pt)


def test_trim_area_is_identical_to_plain_render(setup):
    rect = (-B, -B, W + B, H + B)
    plain = render(setup, rect, (154, 216), 0.0)
    bled = render(setup, rect, (154, 216), B)
    b = bleed_px_for(DPI)
    assert bled.size == (plain.width + 2 * b, plain.height + 2 * b)
    inner = bled.crop((b, b, b + plain.width, b + plain.height))
    assert ImageChops.difference(inner, plain).getbbox() is None


def test_full_bleed_image_shows_in_bleed_band(setup):
    bled = render(setup, (-B, -B, W + B, H + B), (154, 216), B)
    b = bleed_px_for(DPI)
    for xy in ((b // 2, bled.height // 2), (bled.width - b // 2 - 1, bled.height // 2),
               (bled.width // 2, b // 2), (bled.width // 2, bled.height - b // 2 - 1)):
        assert bled.getpixel(xy) == (90, 90, 90), f"出血帶 {xy} 應見圖"


def test_trim_only_image_leaves_bleed_band_white(setup):
    """圖只拉到成品邊：畫布出血帶白＝PDF 出血區露白，畫面與匯出一致。"""
    bled = render(setup, (0.0, 0.0, W, H), (148, 210), B)
    b = bleed_px_for(DPI)
    assert bled.getpixel((b // 2, bled.height // 2)) == (255, 255, 255)
    assert bled.getpixel((b + 2, bled.height // 2)) == (90, 90, 90)


def test_spine_side_bleed_is_cropped_for_facing_view():
    b = bleed_px_for(DPI)
    img = QImage(100 + 2 * b, 50, QImage.Format_RGB888)
    assert crop_spine_bleed(img, b, None).width() == 100 + 2 * b
    assert crop_spine_bleed(img, b, "left").width() == 100 + b
    assert crop_spine_bleed(img, b, "right").width() == 100 + b


def test_base_position_keeps_trim_origin():
    """trim 左上恆在 (x_offset, 0)：訂口在左的頁底圖不往左退。"""
    assert bleed_base_pos(0.0, 18.0, None) == (-18.0, -18.0)
    assert bleed_base_pos(500.0, 18.0, "left") == (500.0, -18.0)
    assert bleed_base_pos(0.0, 18.0, "right") == (-18.0, -18.0)
