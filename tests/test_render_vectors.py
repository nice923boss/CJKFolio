"""目錄頁型（D 主版）與 CIP 細框向量原件的 layout／render 測試。

自 test_layout_render.py 分出（Sprint 32，替代軌 B：測試檔近 800 行上限分檔），涵蓋
CIP 細框（Sprint 14）、目錄天頭虛線（Sprint 15）、目錄條目頁碼＋引導線（Sprint 16）、
目錄篇名嵌線斷開＋條目縮退（Sprint 21）。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest
from PIL import Image, ImageOps

from cjkfolio.document import document_from_dict
from cjkfolio.layout import layout_document, style_advance_pt
from cjkfolio.primitives import cip_frame_rect
from cjkfolio.render import horizontal_left_x_pt, line_axis_x_pt, render_document
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
        master, horizontal_left_x_pt(master, sheet_face=1), n_lines=2, frame=master.frame)
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
def test_render_toc_rule_dashed_gray_full_width(toc_rule_template, tmp_path):
    """目錄天頭虛線：y 於實測 122.46pt、斷續（dash 生效）、灰值（K57 非純黑）、貫穿頁寬。

    吃回歸模版：產品模版自 Sprint 141 起不宣告 rule（見 tests/conftest.py）。"""
    template = toc_rule_template
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
    title_end = (master.margins.top_mm * PT + (entry_style.head_offset_chars + 10) * adv
                 + entry_style.lead_offset_pt)  # Sprint 30：標題末隨條目 lead_offset 偏移
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


def test_layout_rule_breaks_crossing_line_only(toc_rule_template):
    """穿線行（行首字頂高於虛線 y）產 RuleBreak：部名（不縮退）穿線、
    條目（head_offset 縮退）不穿（幾何判定，非樣式白名單）。

    吃回歸模版：產品模版自 Sprint 141 起不宣告 rule（見 tests/conftest.py）。"""
    template = toc_rule_template
    doc = make_toc_doc_with_part("把日子放回原位", [("安放與整理的十個提問", "17")])
    layout = layout_document(doc, template)
    assert layout.violations == []
    master = template.masters["D-目錄"]
    grid = master.grid
    top_pt = master.margins.top_mm * PT
    # 幾何前提（p002/p003 一手量測）：部名天頭 107.96pt 在虛線 122.46 之上；
    # 條目縮退 2 槽後起點在虛線之下（黑字距 12.08×2＝24.16pt，Sprint 24 勘誤）
    part_style = template.paragraph_styles["目錄-部名"]
    entry_style = template.paragraph_styles["目錄-篇章條目"]
    assert top_pt < master.rule.y_from_top_pt
    entry_top = (top_pt + entry_style.head_offset_chars * style_advance_pt(entry_style, grid)
                 + entry_style.lead_offset_pt)  # Sprint 30：條目起點含 lead_offset（下移更不穿線）
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
def test_render_toc_rule_breaks_at_part_title(toc_rule_template, tmp_path):
    """篇名嵌線著墨驗證：虛線在部名行槽±斷開邊距內無線墨、兩側續畫；
    部名字墨存在於虛線之上（穿線視覺）。

    吃回歸模版：產品模版自 Sprint 141 起不宣告 rule（見 tests/conftest.py）。"""
    template = toc_rule_template
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
        (master.margins.top_mm * PT + (entry_style.head_offset_chars + 6) * adv + 2
         + entry_style.lead_offset_pt)  # Sprint 30：條目下移，末字後起點跟隨
        * scale)
    bot_px = round(master.toc.page_no_bottom_pt * scale)
    col = [img.getpixel((ax_px, y)) for y in range(title_end_px, bot_px)]
    assert all(v >= 250 for v in col), "無頁碼條目不應有引導線或頁碼墨"
