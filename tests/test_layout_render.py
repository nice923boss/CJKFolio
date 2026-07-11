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


def make_part_doc():
    """自擬部扉文件（master B、兩段：篇序標籤＋部名）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "部扉樣張", "template": "neizai-zhengli", "master": "B-部扉"},
        "paragraphs": [
            {"text": "第一部", "style": "標籤-篇序小標"},
            {"text": "自擬的部名七個字", "style": "部扉大標-明體W9"},
        ],
    })


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
    """真書側別（Sprint 22 三向互證修正）：偶數書頁＝右頁（書口右）、
    奇數書頁＝左頁（書口左、slot 0 自訂口內推）。"""
    master = template.masters["A-內文版"]
    page_w = mm_to_pt(template.page_width_mm)
    odd0 = line_axis_x_pt(template, master, slot=0, page_number=1)
    even0 = line_axis_x_pt(template, master, slot=0, page_number=2)
    assert even0 == pytest.approx(page_w - mm_to_pt(master.margins.outer_mm) - 11.5 / 2)
    assert odd0 == pytest.approx(page_w - mm_to_pt(master.margins.inner_mm) - 11.5 / 2)
    assert even0 > odd0  # 偶數頁（右頁）書口在右，行軸更靠右
    assert line_axis_x_pt(template, master, slot=3, page_number=2) == pytest.approx(even0 - 3 * 23.0)


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
    # first_page=30：頁 1＝書頁 30（偶數＝右頁）、頁 2＝書頁 31（奇數＝左頁），
    # 側別依真書三向互證（Sprint 22）
    result = render_document(doc, template, tmp_path, dpi=150, first_page=30)
    scale = 150 / 72.0
    page_w_px = mm_to_pt(148) * scale
    # 頁 1＝書頁 30（偶數＝右頁）：頁碼靠書口（右）緣、書眉（書名）齊版心外緣
    ink1 = _footer_band(Image.open(result.paths[0]), scale)
    assert ink1 is not None, "偶數書頁頁腳帶無著墨"
    assert ink1[2] > page_w_px * 0.8, "偶數書頁頁腳應靠書口（右）側"
    # 頁 2＝書頁 31（奇數＝左頁）：頁碼鏡像靠書口（左）緣、無書眉（書名書眉限偶數頁）
    ink2 = _footer_band(Image.open(result.paths[1]), scale)
    assert ink2 is not None, "奇數書頁頁腳帶無著墨"
    assert ink2[0] < page_w_px * 0.2, "奇數書頁頁腳應靠書口（左）側"
    used = {Path(f).name for f in result.fonts_used}
    assert "jf-openhuninn-2.1.ttf" in used       # 頁碼（全頁）
    assert "ChenYuluoyan-2.0-Thin.ttf" in used   # 書眉（書頁 30 偶數頁）


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
    """鏡像依書頁號：偶數起頁的首頁＝右頁（書口右）行軸偏右，奇數起頁偏左（Sprint 22）。"""
    doc = make_doc([{"text": "永", "style": "內文-明體直排"}])
    even = render_document(doc, template, tmp_path / "even", dpi=150, footer=False, first_page=20)
    odd = render_document(doc, template, tmp_path / "odd", dpi=150, footer=False, first_page=21)
    # 版面頁號同為 1；書頁號 20（偶＝右頁，書口在右→行軸偏右）vs 21（奇＝左頁，訂口在右→行軸偏左）
    assert _ink_cx(even.paths[0]) > _ink_cx(odd.paths[0])


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
    # 左起 x：mirror=false → 恆以 outer 槽為起排側（p178 左頁書口 25.81mm，Sprint 22）
    left = horizontal_left_x_pt(master, book_number=1)
    assert left == pytest.approx(mm_to_pt(master.margins.outer_mm))
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
    # 文字左緣自起排側（outer，p178 左頁書口）內推（頁面座標＝crop 原點＋crop 內 ink）
    left_px = mm_to_pt(master.margins.outer_mm) * scale
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


# ---------- B 部扉頁型（Sprint 20：三部扉一手量測釘死） ----------

def test_part_divider_layout_geometry(template):
    """部序號 slot 0（右）、大標 slot 1；行軸與天頭＝三部扉量測值（A 級）。"""
    layout = layout_document(make_part_doc(), template)
    assert layout.vertical and len(layout.pages) == 1
    label, headline = layout.pages[0].placed
    assert (label.slot, label.style) == (0, "標籤-篇序小標")
    assert (headline.slot, headline.style) == (1, "部扉大標-明體W9")
    master = template.masters["B-部扉"]
    # 行軸（p018/068/114 三頁互證）：部序號 228.49、大標 194.12
    assert line_axis_x_pt(template, master, 0, 1) == pytest.approx(228.49, abs=0.05)
    assert line_axis_x_pt(template, master, 1, 1) == pytest.approx(194.12, abs=0.05)
    # 天頭＝部序號首字頂 176.84pt；大標字距 23.1（§10 換算規則）
    assert master.margins.top_mm * mm_to_pt(1.0) == pytest.approx(176.84, abs=0.05)
    adv = style_advance_pt(template.paragraph_styles["部扉大標-明體W9"], master.grid)
    assert adv == pytest.approx(23.1, abs=0.05)
    # 篇序標籤段後不空槽（間距已含於行距 34.37）
    assert template.paragraph_styles["標籤-篇序小標"].para_gap_slots == 0


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


# ---------- 目錄水平虛線向量原件（Sprint 15） ----------

def make_toc_doc(entries):
    """自擬直排目錄文件（master D、樣式 目錄-篇章條目）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄樣張", "template": "neizai-zhengli", "master": "D-目錄"},
        "paragraphs": [{"text": t, "style": "目錄-篇章條目"} for t in entries],
    })


@needs_fonts
def test_render_toc_rule_dashed_gray_full_width(template, tmp_path):
    """目錄天頭虛線：y 於實測 122.46pt、斷續（dash 生效）、灰值（K57 非純黑）、貫穿頁寬。"""
    doc = make_toc_doc(["安放與整理的十個提問", "把回憶放回原位的方法"])
    result = render_document(doc, template, tmp_path, dpi=200, footer=False)
    assert result.violations == []
    master = template.masters["D-目錄"]
    scale = 200 / 72.0
    img = Image.open(result.paths[0]).convert("L")
    y_px = round(master.rule.y_from_top_pt * scale)
    row = [img.getpixel((x, y_px)) for x in range(img.width)]
    ink = [v for v in row if v < 250]
    assert ink, "虛線列無著墨"
    # dash 生效：白→墨轉換多次（全寬 148mm ≈ 420pt／(3+2)pt ≈ 84 段，至少取 30）
    runs = sum(1 for a, b in zip(row, row[1:]) if a >= 250 and b < 250)
    assert runs >= 30, f"虛線未斷續（white→ink 轉換僅 {runs} 次）"
    # 灰 K57：中位 ink 值在灰域（PNG 灰階預覽以 255×(1−k) 近似）
    gray = sorted(ink)[len(ink) // 2]
    assert 80 <= gray <= 140, f"虛線灰值 {gray} 不在 K57 灰域（預期 ≈110）"
    # 貫穿頁寬：版心外的頁緣兩側也有墨（貼邊出血元素）
    left_band = [v for v in row[: round(10 * scale)] if v < 250]
    right_band = [v for v in row[-round(10 * scale):] if v < 250]
    assert left_band and right_band, "虛線未貫穿至頁緣（左右頁邊帶無墨）"
    # 虛線之下才是條目文字（D 主版天頭 47.63mm＝內容起點 135pt 實測，在虛線之下）
    body = ImageOps.invert(img.crop((0, y_px + 4, img.width, img.height))).getbbox()
    assert body is not None, "虛線下方無條目文字"
    above = ImageOps.invert(img.crop((0, 0, img.width, y_px - 4))).getbbox()
    assert above is None, f"虛線上方不應有文字墨（v1 部名嵌線未實作，GAPS #13）：{above}"


@needs_fonts
def test_render_no_rule_master_band_empty(template, tmp_path):
    """未配置 rule 的主版（A 內文版）在同一 y 列的頁邊帶不著墨（gate 守護）。"""
    doc = make_doc([{"text": "字。", "style": "內文-明體直排"}])
    result = render_document(doc, template, tmp_path, dpi=200, footer=False)
    scale = 200 / 72.0
    img = Image.open(result.paths[0]).convert("L")
    y_px = round(122.46 * scale)
    row = [img.getpixel((x, y_px)) for x in range(round(10 * scale))]
    assert all(v >= 250 for v in row), "無 rule 主版的頁邊帶不應有虛線墨"


# ---------- 目錄條目頁碼＋引導線（Sprint 16） ----------

PT = 72.0 / 25.4


def make_toc_doc_paged(entries_with_pages):
    """自擬目錄文件：entries_with_pages＝[(標題, 頁碼|None), ...]。"""
    paras = []
    for text, page_no in entries_with_pages:
        p = {"text": text, "style": "目錄-篇章條目"}
        if page_no is not None:
            p["page_no"] = page_no
        paras.append(p)
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄樣張", "template": "neizai-zhengli", "master": "D-目錄"},
        "paragraphs": paras,
    })


def test_engine_page_no_rides_paragraph_end_line(template):
    """ParagraphSpec.page_no 只掛到段末行的 PlacedLine（engine 純載體）。"""
    from cjkfolio.engine import ParagraphSpec, flow_pages
    long_title = "整" * 40  # 超過容量 34 → 折兩行
    specs = [ParagraphSpec(text=long_title, style="目錄-篇章條目", indent=0,
                           chars_per_line=34, page_no="169")]
    pages = flow_pages(specs, 34, 13)
    placed = [pl for page in pages for pl in page]
    assert len(placed) == 2
    assert placed[0].page_no is None       # 非段末行不帶
    assert placed[1].page_no == "169"      # 段末行帶頁碼


def test_layout_toc_marks_geometry(template):
    doc = make_toc_doc_paged([
        ("安放與整理的十個提問", "169"),
        ("無頁碼的條目不產記號", None),
    ])
    layout = layout_document(doc, template)
    assert layout.violations == []
    marks = layout.toc_marks[1]
    assert len(marks) == 1  # 只有帶 page_no 的條目
    m = marks[0]
    assert m.digits == "169"
    assert m.char_style == "頁碼數字-GillSans"

    master = template.masters["D-目錄"]
    grid = master.grid
    cstyle = template.character_styles["頁碼數字-GillSans"]
    digit_adv = style_advance_pt(cstyle, grid)
    assert m.digit_advance_pt == pytest.approx(digit_adv)
    assert m.digit_size_pt == pytest.approx(cstyle.size_pt)
    # 頁碼底錨實測 490pt：首位頂＝底−位數×字距
    assert m.page_no_top_pt == pytest.approx(490.0 - 3 * digit_adv)
    # 引導線：標題末＋gap 〜 頁碼頂−gap（標題 10 字、indent 0、slot 0；
    # 條目縮退 head_offset 槽下移，Sprint 21）
    entry_style = template.paragraph_styles["目錄-篇章條目"]
    adv = style_advance_pt(entry_style, grid)
    title_end = master.margins.top_mm * PT + (entry_style.head_offset_chars + 10) * adv
    assert m.slot == 0
    assert m.leader_y0_pt == pytest.approx(title_end + 2.0)
    assert m.leader_y1_pt == pytest.approx(m.page_no_top_pt - 2.0)
    assert m.leader_y0_pt < m.leader_y1_pt  # 正常條目線長為正


def test_layout_page_no_without_master_toc_raises(template):
    """帶 page_no 的段落落在無 toc 配置的主版 → 快速失敗。"""
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "誤用", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "字。", "style": "內文-明體直排", "page_no": "5"}],
    })
    with pytest.raises(ValueError, match="toc"):
        layout_document(doc, template)


@needs_fonts
def test_render_toc_page_no_and_leader(template, tmp_path):
    """條目頁碼（直排逐位、底錨）＋引導線（行軸垂直細線）著墨於推導幾何。"""
    doc = make_toc_doc_paged([("安放與整理的十個提問", "169")])
    result = render_document(doc, template, tmp_path, dpi=300, footer=False)
    assert result.violations == []
    master = template.masters["D-目錄"]
    layout = layout_document(doc, template)
    m = layout.toc_marks[1][0]
    scale = 300 / 72.0
    img = Image.open(result.paths[0]).convert("L")
    axis = line_axis_x_pt(template, master, m.slot, 1, line_slots=m.line_slots)
    ax_px = round(axis * scale)
    # 引導線：行軸 x 上、(leader_y0, leader_y1) 區間內有墨且細（左右 3px 外無墨）
    mid_y = round((m.leader_y0_pt + m.leader_y1_pt) / 2 * scale)
    band = [img.getpixel((x, mid_y)) for x in range(ax_px - 8, ax_px + 9)]
    assert min(band) < 200, "引導線中點無墨"
    assert img.getpixel((ax_px - 8, mid_y)) >= 250 and img.getpixel((ax_px + 8, mid_y)) >= 250, \
        "引導線過寬（應為 0.1pt 細線）"
    # 引導線起點之上一小段（標題末字與線之間的 gap）無墨
    assert img.getpixel((ax_px, round((m.leader_y0_pt - 1.0) * scale))) >= 250
    # 頁碼：三位數字著墨於 [page_no_top, bottom] 帶、行軸置中
    top_px = round(m.page_no_top_pt * scale)
    bot_px = round(master.toc.page_no_bottom_pt * scale)
    crop = img.crop((ax_px - round(m.digit_size_pt * scale), top_px,
                     ax_px + round(m.digit_size_pt * scale), bot_px))
    ink = ImageOps.invert(crop).getbbox()
    assert ink is not None, "頁碼區無數字著墨"
    # 頁碼底不越過底錨（bbox 底在 crop 內）
    assert ink[3] <= crop.height


# ---------- 目錄篇名嵌線斷開＋條目縮退（Sprint 21） ----------

def make_toc_doc_with_part(part, entries_with_pages):
    """自擬目錄文件：部名段（穿線）＋條目段（縮退）。"""
    paras = [{"text": part, "style": "目錄-部名"}]
    for text, page_no in entries_with_pages:
        p = {"text": text, "style": "目錄-篇章條目"}
        if page_no is not None:
            p["page_no"] = page_no
        paras.append(p)
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄樣張", "template": "neizai-zhengli", "master": "D-目錄"},
        "paragraphs": paras,
    })


def test_layout_rule_breaks_crossing_line_only(template):
    """穿線行（行首字頂高於虛線 y）產 RuleBreak：部名（不縮退）穿線、
    條目（head_offset 縮退）不穿（幾何判定，非樣式白名單）。"""
    doc = make_toc_doc_with_part("把日子放回原位", [("安放與整理的十個提問", "17")])
    layout = layout_document(doc, template)
    assert layout.violations == []
    master = template.masters["D-目錄"]
    grid = master.grid
    top_pt = master.margins.top_mm * PT
    # 幾何前提（p002/p003 一手量測）：部名天頭 107.96pt 在虛線 122.46 之上；
    # 條目縮退 3 槽後起點在虛線之下
    part_style = template.paragraph_styles["目錄-部名"]
    entry_style = template.paragraph_styles["目錄-篇章條目"]
    assert top_pt < master.rule.y_from_top_pt
    entry_top = top_pt + entry_style.head_offset_chars * style_advance_pt(entry_style, grid)
    assert entry_top > master.rule.y_from_top_pt
    breaks = layout.rule_breaks[1]
    assert len(breaks) == 1  # 只有部名行穿線
    b = breaks[0]
    assert b.slot == 0  # 部名為首段首行
    from cjkfolio.layout import style_line_slots
    assert b.line_slots == style_line_slots(part_style, grid)


def test_layout_rule_breaks_empty_without_crossing(template):
    """全條目（皆縮退）＝無穿線行＝無斷開（虛線維持全寬）。"""
    doc = make_toc_doc_paged([("安放與整理的十個提問", "17")])
    layout = layout_document(doc, template)
    assert layout.rule_breaks == {}


def test_layout_rule_breaks_empty_without_rule_master(template):
    """無 rule 配置的主版不產 rule_breaks（gate 守護）。"""
    doc = make_doc([{"text": "字。", "style": "內文-明體直排"}])
    layout = layout_document(doc, template)
    assert layout.rule_breaks == {}


@needs_fonts
def test_render_toc_rule_breaks_at_part_title(template, tmp_path):
    """篇名嵌線著墨驗證：虛線在部名行槽±斷開邊距內無線墨、兩側續畫；
    部名字墨存在於虛線之上（穿線視覺）。"""
    from cjkfolio.render import rule_break_ranges
    doc = make_toc_doc_with_part("把日子放回原位", [("安放與整理的十個提問", "17")])
    layout = layout_document(doc, template)
    result = render_document(doc, template, tmp_path, dpi=200, footer=False)
    assert result.violations == []
    master = template.masters["D-目錄"]
    (gap_lo, gap_hi), = rule_break_ranges(template, master, layout.rule_breaks[1], 1)
    scale = 200 / 72.0
    img = Image.open(result.paths[0]).convert("L")
    y_px = round(master.rule.y_from_top_pt * scale)
    row = [img.getpixel((x, y_px)) for x in range(img.width)]

    def band_has_ink(x0_pt, x1_pt):
        return any(v < 250 for v in row[max(0, round(x0_pt * scale)):round(x1_pt * scale)])

    # 斷開區間內、行槽外（無字無線）的兩側 gap 帶：無墨
    axis = line_axis_x_pt(template, master, 0, 1, line_slots=1)
    half = master.grid.line_pitch_pt / 2
    assert not band_has_ink(gap_lo + 0.5, axis - half - 0.5), "行後方斷開帶仍有線墨"
    assert not band_has_ink(axis + half + 0.5, gap_hi - 0.5), "行前方斷開帶仍有線墨"
    # 斷開區間外兩側：虛線續畫（dash 週期 5pt，取 8pt 帶必有 on 段）
    assert band_has_ink(gap_lo - 8.0, gap_lo - 0.5), "斷開左側虛線未續畫"
    assert band_has_ink(gap_hi + 0.5, gap_hi + 8.0), "斷開右側虛線未續畫"
    # 部名穿線：虛線 y 之上、部名行槽帶內有字墨（首字「把」起於天頭 107.97pt）
    above = img.crop((round((axis - half) * scale), 0,
                      round((axis + half) * scale), y_px - 2))
    assert ImageOps.invert(above).getbbox() is not None, "部名未穿線（虛線上方無字墨）"


@needs_fonts
def test_render_toc_entry_without_page_no_has_no_leader(template, tmp_path):
    """無 page_no 的條目不畫引導線與頁碼（標題以下至底錨帶無墨）。"""
    doc = make_toc_doc_paged([("無頁碼的條目", None)])
    result = render_document(doc, template, tmp_path, dpi=300, footer=False)
    master = template.masters["D-目錄"]
    scale = 300 / 72.0
    img = Image.open(result.paths[0]).convert("L")
    axis = line_axis_x_pt(template, master, 0, 1, line_slots=1)
    ax_px = round(axis * scale)
    entry_style = template.paragraph_styles["目錄-篇章條目"]
    adv = style_advance_pt(entry_style, master.grid)
    title_end_px = round(
        (master.margins.top_mm * PT + (entry_style.head_offset_chars + 6) * adv + 2)
        * scale)
    bot_px = round(master.toc.page_no_bottom_pt * scale)
    col = [img.getpixel((ax_px, y)) for y in range(title_end_px, bot_px)]
    assert all(v >= 250 for v in col), "無頁碼條目不應有引導線或頁碼墨"
