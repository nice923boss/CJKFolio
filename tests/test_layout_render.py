"""樣式驅動流排（cjkfolio.layout）與單頁渲染（cjkfolio.render）。

幾何驗證以純數學測試為主（不需字型檔）；著墨測試需 assets/fonts 的思源宋體。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest
from PIL import Image, ImageOps

from cjkfolio.document import Document, Paragraph, document_from_dict
from cjkfolio.engine import Cell, Line
from cjkfolio.layout import (
    layout_document,
    line_justified_advance,
    page_is_vertical,
    style_advance_pt,
    style_line_capacity,
)
from cjkfolio.primitives import cip_frame_rect
from cjkfolio.render import (
    horizontal_baseline_y_pt,
    horizontal_left_x_pt,
    line_axis_x_pt,
    mm_to_pt,
    render_document,
)
from cjkfolio.styles import ParagraphStyle, Template, load_template

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
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


def make_cip_doc(lines):
    """自擬橫排版權頁文件（master F、樣式 版權頁-CIP橫排）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "橫排樣張", "template": "neizai-zhengli", "master": "F-版權頁"},
        "paragraphs": [{"text": t, "style": "版權頁-CIP橫排"} for t in lines],
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


def test_layout_unknown_char_style_raises(template):
    doc = make_doc([{
        "style": "內文-明體直排",
        "runs": [{"text": "字", "char_style": "不存在的字元樣式"}],
    }])
    with pytest.raises(KeyError, match="不存在的字元樣式"):
        layout_document(doc, template)


# ---------- 齊行（justification，Sprint 11） ----------

def _cjk_line(text, cap, para_end):
    return Line(tuple(Cell(c, "cjk", 1) for c in text), 0, cap=cap, para_end=para_end)


def test_line_justified_advance_statuses():
    full = _cjk_line("一二三四五", cap=5, para_end=False)
    assert line_justified_advance(full, 10.0) == (10.0, "grid")

    squeezed = _cjk_line("一二三四五。", cap=5, para_end=False)
    adv, status = line_justified_advance(squeezed, 10.0)
    assert status == "squeezed"
    assert adv == pytest.approx(50 / 6)
    assert 6 * adv == pytest.approx(5 * 10.0)  # 行尾錨定：內容總長＝欄容量

    stretched = _cjk_line("一二三四", cap=5, para_end=False)
    adv, status = line_justified_advance(stretched, 10.0)
    assert status == "stretched"
    assert adv == pytest.approx(12.5)

    last = _cjk_line("尾行", cap=5, para_end=True)
    assert line_justified_advance(last, 10.0) == (10.0, "grid")

    beyond = _cjk_line("孤", cap=5, para_end=False)
    assert line_justified_advance(beyond, 10.0) == (10.0, "beyond")


def test_layout_justify_stats(template):
    # 30 字滿行＋句號擠入 → 31 字入 30 槽（縮排 2 後容量 30）
    doc = make_doc([{"text": "字" * 30 + "。續行結束", "style": "內文-明體直排"}])
    result = layout_document(doc, template)
    assert result.violations == []
    assert result.justify_stats["squeezed"] == 1
    assert result.justify_stats["beyond"] == 0


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


@needs_fonts
def test_render_char_style_run_switches_font(template, tmp_path):
    doc = make_doc([{
        "style": "內文-明體直排",
        "runs": [{"text": "平文與"}, {"text": "重點", "char_style": "內文強調-明體W9"}],
    }])
    result = render_document(doc, template, tmp_path, dpi=150, footer=False)
    used = {Path(f).name for f in result.fonts_used}
    assert "SourceHanSerifTC-Regular.otf" in used
    assert "SourceHanSerifTC-Heavy.otf" in used  # 強調 run 用 W9→Heavy


# ---------- 頁腳三件組（主版層） ----------

def _footer_band(img, scale):
    """頁腳帶（基線 530.43pt 上下）的著墨 bbox。"""
    y0, y1 = round(516 * scale), round(538 * scale)
    band = img.crop((0, y0, img.width, y1))
    return ImageOps.invert(band.convert("L")).getbbox()


@needs_fonts
def test_footer_page_number_and_running_title(template, tmp_path):
    doc = make_doc([{"text": BODY_500, "style": "內文-明體直排"}])
    # first_page=30：頁 1＝書頁 30（偶數＝左頁）、頁 2＝書頁 31（奇數＝右頁），鏡像依書頁號（GAPS #16）
    result = render_document(doc, template, tmp_path, dpi=150, first_page=30)
    scale = 150 / 72.0
    page_w_px = mm_to_pt(148) * scale
    # 頁 1＝書頁 30（偶數＝左頁）：頁碼鏡像靠書口（左）緣、無書眉（書眉限奇數頁）
    ink1 = _footer_band(Image.open(result.paths[0]), scale)
    assert ink1 is not None, "偶數書頁頁腳帶無著墨"
    assert ink1[0] < page_w_px * 0.2, "偶數書頁頁腳應靠書口（左）側"
    # 頁 2＝書頁 31（奇數＝右頁）：頁碼靠右緣、書眉（書名）齊版心外緣
    ink2 = _footer_band(Image.open(result.paths[1]), scale)
    assert ink2 is not None, "奇數書頁頁腳帶無著墨"
    assert ink2[2] > page_w_px * 0.8, "奇數書頁頁腳應靠書口（右）側"
    used = {Path(f).name for f in result.fonts_used}
    assert "jf-openhuninn-2.1.ttf" in used       # 頁碼（全頁）
    assert "ChenYuluoyan-2.0-Thin.ttf" in used   # 書眉（書頁 31 奇數頁）


@needs_fonts
def test_footer_disabled_leaves_band_empty(template, tmp_path):
    doc = make_doc([{"text": "短段。", "style": "內文-明體直排"}])
    result = render_document(doc, template, tmp_path, dpi=150, footer=False)
    assert _footer_band(Image.open(result.paths[0]), 150 / 72.0) is None


# ---------- 鏡像依書頁號（GAPS #16） ----------

def _ink_cx(path):
    ink = ImageOps.invert(Image.open(path).convert("L")).getbbox()
    assert ink is not None, f"{path} 整頁空白"
    return (ink[0] + ink[2]) / 2


@needs_fonts
def test_body_axis_mirrors_by_book_page(template, tmp_path):
    """鏡像依書頁號：偶數起頁的首頁＝左頁（書口左）行軸偏左，奇數起頁偏右（GAPS #16）。"""
    doc = make_doc([{"text": "永", "style": "內文-明體直排"}])
    even = render_document(doc, template, tmp_path / "even", dpi=150, footer=False, first_page=20)
    odd = render_document(doc, template, tmp_path / "odd", dpi=150, footer=False, first_page=21)
    # 版面頁號同為 1；書頁號 20（偶＝左頁，訂口在右→行軸偏左）vs 21（奇＝右頁，書口在右→行軸偏右）
    assert _ink_cx(odd.paths[0]) > _ink_cx(even.paths[0])


# ---------- 橫排版面軸（Sprint 13：版權頁-CIP，GAPS #13） ----------

def test_page_is_vertical_detects_direction(template):
    assert page_is_vertical(make_doc([{"text": "直排內文。", "style": "內文-明體直排"}]), template)
    assert not page_is_vertical(make_cip_doc(["橫排版權頁資料"]), template)


def test_layout_rejects_mixed_direction(template):
    # v1 不支援單一文件混用直排與橫排（slot 幾何不相容）
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "混向", "master": "F-版權頁"},
        "paragraphs": [
            {"text": "橫排列", "style": "版權頁-CIP橫排"},
            {"text": "直排列", "style": "內文-明體直排"},
        ],
    })
    with pytest.raises(ValueError, match="混用書寫方向"):
        layout_document(doc, template)


def test_page_is_vertical_rejects_unknown_mode():
    tpl = Template(
        name="t", page_width_mm=148, page_height_mm=210,
        paragraph_styles={"壞樣式": ParagraphStyle(
            "壞樣式", "思源宋體 TC", "regular", 10.0, writing_mode="sideways-lr")},
    )
    doc = Document(title="", template="", master="A", paragraphs=(Paragraph("字", "壞樣式"),))
    with pytest.raises(ValueError, match="非法"):
        page_is_vertical(doc, tpl)


def test_layout_horizontal_no_justify_and_flags_direction(template):
    doc = make_cip_doc(["橫排一行短資料"])
    result = layout_document(doc, template)
    assert result.vertical is False
    assert result.violations == []
    # 橫排短行左齊、不字距縮放 → 齊行統計皆 0
    assert result.justify_stats == {"squeezed": 0, "stretched": 0, "beyond": 0}
    assert len(result.pages) == 1


def test_horizontal_geometry_left_and_baseline(template):
    master = template.masters["F-版權頁"]
    # 左起 x：mirror=false → 恆用訂口（inner）內推
    left = horizontal_left_x_pt(master, book_number=1)
    assert left == pytest.approx(mm_to_pt(master.margins.inner_mm))
    assert horizontal_left_x_pt(master, book_number=2) == pytest.approx(left)  # 無鏡像
    # 基線：行由上而下，每行 +line_pitch；首行含 ascent
    b0 = horizontal_baseline_y_pt(master, slot=0, size_pt=8.0)
    b1 = horizontal_baseline_y_pt(master, slot=1, size_pt=8.0)
    top = mm_to_pt(master.margins.top_mm)
    assert b0 == pytest.approx(top + 8.0 * 0.88)
    assert b1 - b0 == pytest.approx(master.grid.line_pitch_pt)


@needs_fonts
def test_render_horizontal_page_lands_top_left(template, tmp_path):
    doc = make_cip_doc([
        "自由排版工作室出版品預行編目資料",
        "ISBN 978-0-00-000000-0（平裝）",
    ])
    result = render_document(doc, template, tmp_path, dpi=200, footer=False)
    assert len(result.paths) == 1
    assert result.violations == []
    master = template.masters["F-版權頁"]
    scale = 200 / 72.0
    img = Image.open(result.paths[0]).convert("L")
    # F 版有 CIP 細框（Sprint 14）：量文字須排除框，裁掉框邊界內側再取 ink
    rect = cip_frame_rect(master, horizontal_left_x_pt(master, book_number=1),
                          n_lines=2, frame=master.frame)
    inset = round((master.frame.line_width_pt + 1) * scale)
    ox, oy = round(rect.x0 * scale) + inset, round(rect.y0 * scale) + inset
    crop = img.crop((ox, oy, round(rect.x1 * scale) - inset, round(rect.y1 * scale) - inset))
    ink = ImageOps.invert(crop).getbbox()
    assert ink is not None, "框內橫排文字無著墨"
    # 文字左緣貼訂口（inner）內推（頁面座標＝crop 原點＋crop 內 ink）
    left_px = mm_to_pt(master.margins.inner_mm) * scale
    assert abs((ox + ink[0]) - left_px) < 12, f"橫排文字左緣 {ox + ink[0]} vs {left_px}"
    # 由上而下兩行：文字頂緣接近天頭
    top_px = mm_to_pt(master.margins.top_mm) * scale
    assert (oy + ink[1]) < top_px + 8.0 * scale, "橫排首行應貼天頭"
    # 橫向鋪展：文字寬度遠大於高度（LTR 兩短行）
    assert (ink[2] - ink[0]) > (ink[3] - ink[1])
    assert "SourceHanSerifTC-Regular.otf" in {Path(f).name for f in result.fonts_used}


# ---------- PNG 缺字警告（GAPS #17） ----------

@needs_fonts
def test_render_missing_glyph_warns(template, tmp_path):
    # 私用區字元 U+E000 思源無字形 → 以 .notdef 輸出並警告（不沉默，與 PDF 後端一致）
    doc = make_doc([{"text": "字。", "style": "內文-明體直排"}])
    result = render_document(doc, template, tmp_path, dpi=150, footer=False)
    assert any("無字形" in w for w in result.font_warnings), result.font_warnings


# ---------- CIP 細框向量原件（Sprint 14） ----------

@needs_fonts
def test_render_cip_frame_is_outer_ink(template, tmp_path):
    """CIP 細框為最外層著墨：整頁 ink bbox ≈ cip_frame_rect 幾何（線寬容差）。"""
    doc = make_cip_doc([
        "自由排版工作室出版品預行編目資料",
        "ISBN 978-0-00-000000-0（平裝）",
    ])
    result = render_document(doc, template, tmp_path, dpi=200, footer=False)
    master = template.masters["F-版權頁"]
    scale = 200 / 72.0
    rect = cip_frame_rect(
        master, horizontal_left_x_pt(master, book_number=1), n_lines=2, frame=master.frame)
    ink = ImageOps.invert(Image.open(result.paths[0]).convert("L")).getbbox()
    assert ink is not None, "橫排框頁整頁空白"
    # 框寬＝版心滿行寬（遠大於兩短行文字），四緣皆由框決定
    assert abs(ink[0] - rect.x0 * scale) < 6, f"框左 {ink[0]} vs {rect.x0 * scale}"
    assert abs(ink[1] - rect.y0 * scale) < 6, f"框上 {ink[1]} vs {rect.y0 * scale}"
    assert abs(ink[2] - rect.x1 * scale) < 6, f"框右 {ink[2]} vs {rect.x1 * scale}"
    assert abs(ink[3] - rect.y1 * scale) < 6, f"框下 {ink[3]} vs {rect.y1 * scale}"


def test_no_frame_master_has_no_frame(template):
    """未配置 frame 的主版（直排 A、部扉 B）不畫框（render_page 依此 gate）。"""
    assert template.masters["A-內文版"].frame is None
    assert template.masters["B-部扉"].frame is None
