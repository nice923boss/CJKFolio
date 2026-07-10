"""樣式驅動流排（cjkfolio.layout）與單頁渲染（cjkfolio.render）。

幾何驗證以純數學測試為主（不需字型檔）；著墨測試需 assets/fonts 的思源宋體。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest
from PIL import Image, ImageOps

from cjkfolio.document import document_from_dict
from cjkfolio.layout import layout_document, style_advance_pt, style_line_capacity
from cjkfolio.render import line_axis_x_pt, mm_to_pt, render_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@1",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


BODY_500 = (
    "整理是一場與過去的對話，我們把留下的物件一件件安放，也把回憶安放。"
    "直排的世界裡，文字由上而下、由右而左，讀者的視線像水流一樣落下。"
) * 8  # 65 字 × 8 = 520 字，自擬


# ---------- layout ----------

def test_style_geometry_derivation(template):
    grid = template.masters["A-內文版"].grid
    body = template.paragraph_styles["內文-明體直排"]
    title = template.paragraph_styles["章名大標-明體W7"]
    assert style_line_capacity(body, grid) == 32
    assert style_advance_pt(body, grid) == pytest.approx(12.08)
    # 21.9pt 標題：字距 21.9×(12.08/11.5)=23.0，欄高 386.56 → 16 字
    assert style_line_capacity(title, grid) == 16


def test_layout_body_fills_master_grid(template):
    doc = make_doc([{"text": BODY_500, "style": "內文-明體直排"}])
    result = layout_document(doc, template)
    assert result.violations == []
    # 520 字、首行縮 2 → 17 行；每頁 13 槽 → 2 頁
    assert len(result.pages) == 2
    assert [p.slot for p in result.pages[0].placed] == list(range(13))
    assert result.pages[0].number == 1
    assert result.pages[1].number == 2


def test_layout_title_style_uses_own_capacity_and_indent(template):
    doc = make_doc([
        {"text": "這是一個超過十六個字的自擬章名標題範例文字", "style": "章名大標-明體W7"},  # 21 字
        {"text": "內文接續。", "style": "內文-明體直排"},
    ])
    result = layout_document(doc, template)
    title_lines = [p for p in result.pages[0].placed if p.style == "章名大標-明體W7"]
    assert title_lines[0].line.start_slot == 0  # 大標不縮排
    assert len("".join(c.text for c in title_lines[0].line.cells)) == 16
    assert len(title_lines) == 2


def test_layout_unknown_style_raises(template):
    doc = make_doc([{"text": "壞段", "style": "不存在的樣式"}])
    with pytest.raises(KeyError, match="不存在的樣式"):
        layout_document(doc, template)


# ---------- render 幾何（純數學） ----------

def test_line_axis_positions_odd_even_mirror(template):
    master = template.masters["A-內文版"]
    page_w = mm_to_pt(template.page_width_mm)
    odd0 = line_axis_x_pt(template, master, slot=0, page_number=1)
    even0 = line_axis_x_pt(template, master, slot=0, page_number=2)
    assert odd0 == pytest.approx(page_w - mm_to_pt(master.margins.outer_mm) - 11.5 / 2)
    assert even0 == pytest.approx(page_w - mm_to_pt(master.margins.inner_mm) - 11.5 / 2)
    assert odd0 > even0  # 奇數頁（右頁）書口在右，行軸更靠右
    assert line_axis_x_pt(template, master, slot=3, page_number=1) == pytest.approx(odd0 - 3 * 23.0)


# ---------- render 著墨（需字型） ----------

@needs_fonts
def test_render_single_char_lands_in_first_cell(template, tmp_path):
    doc = make_doc([{"text": "永", "style": "內文-明體直排"}])
    result = render_document(doc, template, tmp_path, dpi=150, footer=False)
    assert len(result.paths) == 1
    img = Image.open(result.paths[0])
    scale = 150 / 72.0
    assert img.size == (round(mm_to_pt(148) * scale), round(mm_to_pt(210) * scale))
    ink = ImageOps.invert(img.convert("L")).getbbox()
    assert ink is not None
    master = template.masters["A-內文版"]
    # 首字槽：縮排 2 字 → 槽頂 = 天頭 + 2×12.08
    axis_px = line_axis_x_pt(template, master, 0, 1) * scale
    cell_top_px = (mm_to_pt(master.margins.top_mm) + 2 * 12.08) * scale
    cx = (ink[0] + ink[2]) / 2
    assert abs(cx - axis_px) < 5, f"行軸偏移 {cx} vs {axis_px}"
    assert cell_top_px - 3 <= ink[1] <= cell_top_px + 12.08 * scale
    assert ink[3] <= cell_top_px + 2 * 12.08 * scale  # 著墨不超出一個字槽太多


@needs_fonts
def test_render_multipage_and_style_fonts(template, tmp_path):
    doc = make_doc([
        {"text": "自擬章名十字整整齊齊", "style": "章名大標-明體W7"},
        {"text": BODY_500, "style": "內文-明體直排"},
    ])
    result = render_document(doc, template, tmp_path, dpi=150)
    assert len(result.paths) >= 2
    for p in result.paths:
        assert Path(p).exists()
        ink = ImageOps.invert(Image.open(p).convert("L")).getbbox()
        assert ink is not None, f"{p} 整頁空白"
    assert result.violations == []
    used = {Path(f).name for f in result.fonts_used}
    assert "SourceHanSerifTC-Regular.otf" in used
    assert "SourceHanSerifTC-Heavy.otf" in used  # 章名 W7→Heavy（字重 fallback）


# ---------- 頁腳三件組（主版層） ----------

def _footer_band(img, scale):
    """頁腳帶（基線 530.43pt 上下）的著墨 bbox。"""
    y0, y1 = round(516 * scale), round(538 * scale)
    band = img.crop((0, y0, img.width, y1))
    return ImageOps.invert(band.convert("L")).getbbox()


@needs_fonts
def test_footer_page_number_and_running_title(template, tmp_path):
    doc = make_doc([{"text": BODY_500, "style": "內文-明體直排"}])
    result = render_document(doc, template, tmp_path, dpi=150, first_page=30)
    scale = 150 / 72.0
    page_w_px = mm_to_pt(148) * scale
    # 頁 1（奇數＝右頁）：頁碼靠右緣、書眉（書名）齊版心外緣
    ink1 = _footer_band(Image.open(result.paths[0]), scale)
    assert ink1 is not None, "奇數頁頁腳帶無著墨"
    assert ink1[2] > page_w_px * 0.8, "奇數頁頁腳應靠書口（右）側"
    # 頁 2（偶數＝左頁）：鏡像靠左緣
    ink2 = _footer_band(Image.open(result.paths[1]), scale)
    assert ink2 is not None, "偶數頁頁腳帶無著墨"
    assert ink2[0] < page_w_px * 0.2, "偶數頁頁腳應靠書口（左）側"
    used = {Path(f).name for f in result.fonts_used}
    assert "jf-openhuninn-2.1.ttf" in used       # 頁碼
    assert "ChenYuluoyan-2.0-Thin.ttf" in used   # 書眉


@needs_fonts
def test_footer_disabled_leaves_band_empty(template, tmp_path):
    doc = make_doc([{"text": "短段。", "style": "內文-明體直排"}])
    result = render_document(doc, template, tmp_path, dpi=150, footer=False)
    assert _footer_band(Image.open(result.paths[0]), 150 / 72.0) is None
