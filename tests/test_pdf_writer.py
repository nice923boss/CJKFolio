"""PDF 寫出層（cjkfolio.pdf_writer）：盒框、子集嵌入、幾何、頁腳、單 K。

驗證一律走 PyMuPDF（與寫出層不同實作，Gate 4 獨立驗證）。
測試素材一律自擬（版權紅線）。
"""
import re
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.pdf_writer import export_pdf, page_boxes_pt, subset_tag
from cjkfolio.primitives import cip_frame_rect, toc_rule_line
from cjkfolio.render import (
    horizontal_baseline_y_pt,
    horizontal_left_x_pt,
    line_axis_x_pt,
    mm_to_pt,
)
from cjkfolio.styles import load_template

fitz = pytest.importorskip("fitz")

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

BLEED_PT = mm_to_pt(3.0)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


BODY_500 = (
    "整理是一場與過去的對話，我們把留下的物件一件件安放，也把回憶安放。"
    "直排的世界裡，文字由上而下、由右而左，讀者的視線像水流一樣落下。"
) * 8  # 520 字，自擬


# ---------- 純數學 ----------

def test_page_boxes_pt(template):
    media, trim = page_boxes_pt(template)
    assert media == pytest.approx((0.0, 0.0, mm_to_pt(154), mm_to_pt(216)))
    assert trim == pytest.approx(
        (BLEED_PT, BLEED_PT, BLEED_PT + mm_to_pt(148), BLEED_PT + mm_to_pt(210))
    )


def test_subset_tag_deterministic():
    a = subset_tag("SourceHanSerifTC-Regular", [3, 1, 2])
    b = subset_tag("SourceHanSerifTC-Regular", [1, 2, 3])
    c = subset_tag("SourceHanSerifTC-Regular", [1, 2, 4])
    assert re.fullmatch(r"[A-Z]{6}", a)
    assert a == b  # 與順序無關
    assert a != c


# ---------- 整合（需字型；PyMuPDF 獨立驗證） ----------

@needs_fonts
def test_export_single_page_structure_and_fonts(template, tmp_path):
    doc = make_doc([{"text": "整理2026年的抽屜，留下30件衣物。", "style": "內文-明體直排"}])
    out = tmp_path / "single.pdf"
    result = export_pdf(doc, template, out)
    assert result.violations == []
    assert result.page_count == 1

    pdf = fitz.open(str(out))
    assert pdf.page_count == 1
    page = pdf[0]
    assert page.mediabox.width == pytest.approx(mm_to_pt(154), abs=0.02)
    assert page.mediabox.height == pytest.approx(mm_to_pt(216), abs=0.02)
    assert tuple(page.trimbox) == pytest.approx(
        (BLEED_PT, BLEED_PT, BLEED_PT + mm_to_pt(148), BLEED_PT + mm_to_pt(210)), abs=0.02
    )
    fonts = page.get_fonts(full=True)
    assert fonts, "頁面無字型資源"
    for f in fonts:
        assert f[2] == "Type0", f"非 CID 字型：{f}"
        assert re.match(r"^[A-Z]{6}\+", f[3]), f"BaseFont 無子集前綴：{f[3]}"
        buf = pdf.extract_font(f[0])[3]
        assert 0 < len(buf) < 5_000_000, "字型未嵌入或未子集化"
    extracted = page.get_text()
    for ch in "整理年的抽屜留下件衣物20263。，":
        assert ch in extracted, f"ToUnicode 抽取缺字：{ch}"


@needs_fonts
def test_export_glyph_geometry_on_grid(template, tmp_path):
    """單字著墨落在首字槽（與 test_render_single_char_lands_in_first_cell 同準線＋出血偏移）。"""
    from PIL import Image, ImageOps

    doc = make_doc([{"text": "永", "style": "內文-明體直排"}])
    out = tmp_path / "one.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    raw = pdf[0].get_text("rawdict")
    chars = [
        c for b in raw["blocks"] for l in b.get("lines", [])
        for s in l.get("spans", []) for c in s.get("chars", [])
    ]
    assert [c["c"] for c in chars] == ["永"]

    scale = 150 / 72.0
    pix = pdf[0].get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    ink = ImageOps.invert(img).getbbox()
    assert ink is not None, "整頁空白"
    master = template.masters["A-內文版"]
    axis_px = (BLEED_PT + line_axis_x_pt(template, master, 0, 1)) * scale
    cell_top_px = (BLEED_PT + mm_to_pt(master.margins.top_mm) + 2 * 12.08) * scale  # 縮排 2 字
    cx = (ink[0] + ink[2]) / 2
    assert abs(cx - axis_px) < 5, f"行軸偏移 {cx} vs {axis_px}"
    assert cell_top_px - 3 <= ink[1] <= cell_top_px + 12.08 * scale
    assert ink[3] <= cell_top_px + 2 * 12.08 * scale, "著墨超出一個字槽太多"


@needs_fonts
def test_export_page_selection_and_footer(template, tmp_path):
    doc = make_doc([{"text": BODY_500, "style": "內文-明體直排"}])
    # 全頁匯出：520 字 → 2 頁；first_page=30 → 頁 1＝書頁 30（偶）、頁 2＝書頁 31（奇），鏡像依書頁號（GAPS #16）
    out_all = tmp_path / "all.pdf"
    r_all = export_pdf(doc, template, out_all, first_page=30)
    assert r_all.page_count == 2
    pdf_all = fitz.open(str(out_all))
    assert pdf_all.page_count == 2
    p1 = pdf_all[0].get_text()
    assert "30" in p1 and "自擬樣張" not in p1  # 書頁 30 偶數（左頁）：頁碼有、書眉無
    p2 = pdf_all[1].get_text()
    assert "31" in p2 and "自擬樣張" in p2  # 書頁 31 奇數（右頁）：頁碼＋書眉

    # 單頁選擇：只匯第 2 版面頁
    out_one = tmp_path / "p2.pdf"
    r_one = export_pdf(doc, template, out_one, pages=[2], first_page=30)
    assert r_one.page_count == 1
    only = fitz.open(str(out_one))[0].get_text()
    assert "31" in only

    # 頁腳關閉：無頁碼數字
    out_off = tmp_path / "off.pdf"
    export_pdf(doc, template, out_off, footer=False, first_page=30)
    assert "30" not in fitz.open(str(out_off))[0].get_text()


@needs_fonts
def test_export_body_axis_mirrors_by_book_page(template, tmp_path):
    """PDF 內容流行軸依書頁號鏡像：偶數起頁行軸偏左，奇數起頁偏右（GAPS #16）。"""
    doc = make_doc([{"text": "永", "style": "內文-明體直排"}])

    def axis_x(first_page):
        out = tmp_path / f"fp{first_page}.pdf"
        export_pdf(doc, template, out, footer=False, first_page=first_page)
        pdf = fitz.open(str(out))
        content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
        m = re.search(r"1 0 0 1 ([\d.\-]+) [\d.\-]+ Tm", content)
        assert m, content
        return float(m.group(1))

    assert axis_x(21) > axis_x(20)  # 書頁 21（奇＝右頁）行軸較 20（偶＝左頁）右


@needs_fonts
def test_export_text_is_single_k(template, tmp_path):
    doc = make_doc([{"text": "單色檢查。", "style": "內文-明體直排"}])
    out = tmp_path / "k.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents())
    assert b"0 0 0 0.92 k" in content, "內文未用單 K92（DeviceCMYK）"
    assert b" rg" not in content and b" RG" not in content, "內容流殘留 RGB 色彩"


def make_cip_doc(lines):
    """自擬橫排版權頁文件（master F、樣式 版權頁-CIP橫排）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "橫排樣張", "template": "neizai-zhengli", "master": "F-版權頁"},
        "paragraphs": [{"text": t, "style": "版權頁-CIP橫排"} for t in lines],
    })


@needs_fonts
def test_export_horizontal_cip_matrix_and_reading_order(template, tmp_path):
    """橫排 CIP：內容流用水平 Tm（非旋轉）、抽字為 LTR 由上而下閱讀序。"""
    doc = make_cip_doc([
        "自由排版工作室出版品預行編目資料",
        "ISBN 978-0-00-000000-0（平裝）",
    ])
    out = tmp_path / "cip.pdf"
    result = export_pdf(doc, template, out, footer=False)
    assert result.violations == []
    assert result.page_count == 1

    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert re.search(r"1 0 0 1 [\d.\-]+ [\d.\-]+ Tm", content), "橫排須用水平文字矩陣"
    assert "0 -1 1 0" not in content, "橫排不得有旋轉矩陣（縱中橫／旋轉拉丁）"
    # 抽字：LTR 閱讀序，latin 串連續
    text = pdf[0].get_text()
    assert "自由排版工作室出版品預行編目資料" in text
    assert "ISBN 978-0-00-000000-0" in text


@needs_fonts
def test_export_horizontal_two_backend_position_parity(template, tmp_path):
    """兩後端同源：PDF 抽字座標＝render 幾何助手（left_x／baseline_y）＋出血偏移。"""
    doc = make_cip_doc(["自由排版工作室", "臺北市出版"])
    out = tmp_path / "parity.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    raw = pdf[0].get_text("rawdict")
    lines = [
        (l["spans"][0]["chars"][0]["c"], l["spans"][0]["chars"][0]["origin"])
        for b in raw["blocks"] for l in b.get("lines", []) if l.get("spans")
    ]
    assert [c for c, _ in lines] == ["自", "臺"]  # 兩行首字（由上而下）

    master = template.masters["F-版權頁"]
    expect_x = BLEED_PT + horizontal_left_x_pt(master, book_number=1)
    for i, (_, (ox, oy)) in enumerate(lines):
        expect_y = BLEED_PT + horizontal_baseline_y_pt(master, slot=i, size_pt=8.0)
        assert ox == pytest.approx(expect_x, abs=0.3), f"行 {i} 左緣 {ox} vs {expect_x}"
        assert oy == pytest.approx(expect_y, abs=0.3), f"行 {i} 基線 {oy} vs {expect_y}"


@needs_fonts
def test_export_horizontal_preflight_green(template, tmp_path):
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "cipx.pdf"
    export_pdf(make_cip_doc(["ISBN 978-0-00-000000-0（平裝）"]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


@needs_fonts
def test_export_char_style_run_embeds_style_font(template, tmp_path):
    doc = make_doc([{
        "style": "內文-明體直排",
        "runs": [{"text": "平文與"}, {"text": "重點強調", "char_style": "內文強調-明體W9"}],
    }])
    out = tmp_path / "run.pdf"
    result = export_pdf(doc, template, out, footer=False)
    bases = {e["base"].split("+", 1)[1] for e in result.embedded_fonts}
    assert {"SourceHanSerifTC-Regular", "SourceHanSerifTC-Heavy"} <= bases
    extracted = fitz.open(str(out))[0].get_text()
    for ch in "平文與重點強調":
        assert ch in extracted


@needs_fonts
def test_export_missing_glyph_warns_not_crash(template, tmp_path):
    # 私用區字元思源無字形 → 以 .notdef 輸出並警告（不沉默、不中斷）
    doc = make_doc([{"text": "缺字測試。", "style": "內文-明體直排"}])
    result = export_pdf(doc, template, tmp_path / "m.pdf", footer=False)
    assert result.page_count == 1
    assert any("無字形" in w for w in result.font_warnings), result.font_warnings


# ---------- 齊行（Sprint 11） ----------

@needs_fonts
def test_export_justified_line_anchors_column_ends(template, tmp_path):
    # 擠入行（31 字入 30 槽）行首行尾雙錨定：內容字距 = 12.08 × 30/31
    doc = make_doc([{"text": "字" * 30 + "。續行結束", "style": "內文-明體直排"}])
    out = tmp_path / "just.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    ys = [float(m.group(2)) for m in re.finditer(
        r"1 0 0 1 ([\d.\-]+) ([\d.\-]+) Tm", content)]
    assert len(ys) >= 31
    adv = 12.08 * 30 / 31
    for i in range(30):
        d = ys[i] - ys[i + 1]
        assert d == pytest.approx(adv, abs=0.02), f"第 {i} 格字距 {d}，齊行應為 {adv}"


# ---------- PDF/X-1a:2001 識別（Sprint 10） ----------

def fake_icc(space: bytes = b"CMYK", klass: bytes = b"prtr") -> bytes:
    """最小可驗 ICC：128 byte header＋tag 數 0；寫出層只驗長度／類別／色彩空間。"""
    head = bytearray(132)
    head[0:4] = (132).to_bytes(4, "big")
    head[12:16] = klass
    head[16:20] = space
    return bytes(head)


def _info_dict(pdf):
    trailer = pdf.xref_object(-1, compressed=True)
    m = re.search(r"/Info\s+(\d+)\s+0\s+R", trailer)
    assert m, f"trailer 無 /Info：{trailer}"
    return trailer, pdf.xref_object(int(m.group(1)), compressed=True)


def _output_intent(pdf):
    cat = pdf.xref_object(pdf.pdf_catalog(), compressed=True)
    m = re.search(r"/OutputIntents\s*\[\s*(\d+)\s+0\s+R\s*\]", cat)
    assert m, f"Catalog 無 OutputIntents 陣列：{cat}"
    return cat, pdf.xref_object(int(m.group(1)), compressed=True)


@needs_fonts
def test_export_pdfx_header_info_and_id(template, tmp_path):
    doc = make_doc([{"text": "識別檢查。", "style": "內文-明體直排"}])
    out = tmp_path / "x.pdf"
    export_pdf(doc, template, out, footer=False)
    assert out.read_bytes().startswith(b"%PDF-1.3"), "X-1a:2001 須為 PDF 1.3"

    pdf = fitz.open(str(out))
    trailer, info = _info_dict(pdf)
    assert re.search(r"/ID\s*\[", trailer)
    assert "/Encrypt" not in trailer
    assert re.search(r"/Title\s*[<(]", info)
    assert re.search(r"/CreationDate\s*\(D:\d{14}[+\-Z]", info), "日期須帶時區"
    assert re.search(r"/ModDate\s*\(D:", info)
    assert re.search(r"/Trapped\s*/False", info)
    assert re.search(r"/GTS_PDFXVersion\s*\(PDF/X-1:2001\)", info)
    assert re.search(r"/GTS_PDFXConformance\s*\(PDF/X-1a:2001\)", info)


@needs_fonts
def test_export_pdfx_output_intent_default_registry(template, tmp_path):
    doc = make_doc([{"text": "輸出意圖。", "style": "內文-明體直排"}])
    out = tmp_path / "oi.pdf"
    result = export_pdf(doc, template, out, footer=False)
    assert result.output_condition_identifier == "JC200103"
    assert result.icc_embedded is False

    pdf = fitz.open(str(out))
    _, oi = _output_intent(pdf)
    assert re.search(r"/S\s*/GTS_PDFX(?![A-Za-z])", oi)
    assert re.search(r"/OutputConditionIdentifier\s*\(JC200103\)", oi)
    assert re.search(r"/RegistryName\s*\(http://www\.color\.org\)", oi)
    assert re.search(r"/OutputCondition\s*[<(]", oi)
    assert "/DestOutputProfile" not in oi, "registry 識別預設不嵌 ICC"


@needs_fonts
def test_export_pdfx_xmp_metadata(template, tmp_path):
    doc = make_doc([{"text": "中繼資料。", "style": "內文-明體直排"}])
    out = tmp_path / "xmp.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    cat = pdf.xref_object(pdf.pdf_catalog(), compressed=True)
    m = re.search(r"/Metadata\s+(\d+)\s+0\s+R", cat)
    assert m, f"Catalog 無 /Metadata：{cat}"
    meta_dict = pdf.xref_object(int(m.group(1)), compressed=True)
    assert "/Filter" not in meta_dict, "XMP metadata stream 不壓縮"
    xmp = pdf.get_xml_metadata()
    assert "PDF/X-1:2001" in xmp and "PDF/X-1a:2001" in xmp
    assert "自擬樣張" in xmp  # dc:title 與 Info 一致
    assert "GTS_PDFXVersion" in xmp
    assert ">False<" in xmp  # pdf:Trapped


@needs_fonts
def test_export_pdfx_custom_condition_requires_icc(template, tmp_path):
    doc = make_doc([{"text": "自訂條件。", "style": "內文-明體直排"}])
    with pytest.raises(ValueError, match="ICC"):
        export_pdf(doc, template, tmp_path / "c.pdf", footer=False,
                   output_condition_identifier="ShopX Custom")


@needs_fonts
def test_export_pdfx_custom_condition_embeds_icc(template, tmp_path):
    icc_path = tmp_path / "fake.icc"
    icc_path.write_bytes(fake_icc())
    doc = make_doc([{"text": "嵌入描述檔。", "style": "內文-明體直排"}])
    out = tmp_path / "icc.pdf"
    result = export_pdf(doc, template, out, footer=False,
                        output_condition_identifier="ShopX Custom",
                        output_condition="測試條件", icc_profile=icc_path)
    assert result.icc_embedded is True

    pdf = fitz.open(str(out))
    _, oi = _output_intent(pdf)
    assert re.search(r"/OutputConditionIdentifier\s*\(ShopX Custom\)", oi)
    assert "/RegistryName" not in oi, "自訂識別不得掛 color.org registry"
    m = re.search(r"/DestOutputProfile\s+(\d+)\s+0\s+R", oi)
    assert m, f"自訂識別須嵌 DestOutputProfile：{oi}"
    icc_x = int(m.group(1))
    assert re.search(r"/N\s*4", pdf.xref_object(icc_x, compressed=True))
    assert pdf.xref_stream(icc_x) == fake_icc()


@needs_fonts
def test_export_pdfx_icc_rejects_wrong_profile(template, tmp_path):
    doc = make_doc([{"text": "描述檔驗證。", "style": "內文-明體直排"}])
    rgb = tmp_path / "rgb.icc"
    rgb.write_bytes(fake_icc(space=b"RGB "))
    with pytest.raises(ValueError, match="CMYK"):
        export_pdf(doc, template, tmp_path / "r.pdf", footer=False,
                   output_condition_identifier="ShopX", icc_profile=rgb)
    mntr = tmp_path / "mntr.icc"
    mntr.write_bytes(fake_icc(klass=b"mntr"))
    with pytest.raises(ValueError, match="prtr"):
        export_pdf(doc, template, tmp_path / "m.pdf", footer=False,
                   output_condition_identifier="ShopX", icc_profile=mntr)


@needs_fonts
def test_export_pdfx_requires_title(template, tmp_path):
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "無題測試。", "style": "內文-明體直排"}],
    })
    with pytest.raises(ValueError, match="Title"):
        export_pdf(doc, template, tmp_path / "t.pdf", footer=False)


# ---------- CIP 細框向量原件（Sprint 14） ----------

def _frame_re(content: str):
    """抽內容流第一個矩形路徑 (x_ll, y_ll, w, h)。"""
    m = re.search(r"([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) re", content)
    return tuple(map(float, m.groups())) if m else None


@needs_fonts
def test_export_cip_frame_cmyk_stroke_before_text(template, tmp_path):
    """CIP 細框：CMYK 描邊矩形（re/S/K）在 BT 之前、無 rg/RG（preflight color 不退步）。"""
    doc = make_cip_doc(["自由排版工作室出版品預行編目資料"])
    out = tmp_path / "framed.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert _frame_re(content) is not None, "缺矩形路徑 re"
    assert "\nS\n" in content, "缺描邊算符 S"
    assert "0 0 0 1 K" in content, "框描邊非 DeviceCMYK 純黑 K"
    assert content.index(" re") < content.index("BT"), "path 須在文字物件 BT 之前"
    assert " rg" not in content and " RG" not in content, "框殘留 RGB 描邊"


@needs_fonts
def test_export_cip_frame_two_backend_parity(template, tmp_path):
    """框 re 座標＝render 幾何助手（cip_frame_rect）＋出血偏移，兩後端同源。"""
    lines = ["自由排版工作室", "臺北市出版", "ISBN 978-0-00-000000-0"]
    out = tmp_path / "parity.pdf"
    export_pdf(make_cip_doc(lines), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    x_ll, y_ll, w, h = _frame_re(content)

    master = template.masters["F-版權頁"]
    rect = cip_frame_rect(master, horizontal_left_x_pt(master, book_number=1),
                          n_lines=len(lines), frame=master.frame)
    page_h = mm_to_pt(template.page_height_mm)
    assert x_ll == pytest.approx(BLEED_PT + rect.x0, abs=0.3)
    assert y_ll == pytest.approx(page_h + BLEED_PT - rect.y1, abs=0.3)  # y-up 左下角
    assert w == pytest.approx(rect.x1 - rect.x0, abs=0.3)
    assert h == pytest.approx(rect.y1 - rect.y0, abs=0.3)


@needs_fonts
def test_export_cip_frame_preflight_green(template, tmp_path):
    """加框後 CIP PDF 仍過全部 X-1a 機械規則（color-cmyk-only 不退步）。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "framedx.pdf"
    export_pdf(make_cip_doc([
        "自由排版工作室出版品預行編目資料",
        "ISBN 978-0-00-000000-0（平裝）",
    ]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


# ---------- 目錄水平虛線向量原件（Sprint 15） ----------

def make_toc_doc(entries):
    """自擬直排目錄文件（master D、樣式 目錄-篇章條目）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄樣張", "template": "neizai-zhengli", "master": "D-目錄"},
        "paragraphs": [{"text": t, "style": "目錄-篇章條目"} for t in entries],
    })


@needs_fonts
def test_export_toc_rule_dash_stroke_before_text(template, tmp_path):
    """目錄虛線：dash 算符＋灰 K 描邊（d/m/l/S/K）在 BT 之前、q…Q 隔離、無 rg/RG。"""
    out = tmp_path / "toc.pdf"
    export_pdf(make_toc_doc(["安放與整理的十個提問"]), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert "[ 3 2 ] 0 d" in content, "缺 dash 算符 [ 3 2 ] 0 d"
    assert re.search(r"[\d.\-]+ [\d.\-]+ m\n[\d.\-]+ [\d.\-]+ l\nS", content), "缺 m/l/S 線段路徑"
    assert "0 0 0 0.57 K" in content, "虛線描邊非灰 K57"
    assert content.index(" d\n") < content.index("BT"), "dash 須在文字物件 BT 之前"
    assert " rg" not in content and " RG" not in content, "虛線殘留 RGB 描邊"
    # dash 狀態隔離（q…Q 內）：PyMuPDF 獨立解析回報 dashes
    draws = pdf[0].get_drawings()
    dash_lines = [d for d in draws if d.get("dashes") and "3" in d["dashes"]]
    assert dash_lines, f"PyMuPDF 未解析出 dash 線：{[d.get('dashes') for d in draws]}"


@needs_fonts
def test_export_toc_rule_two_backend_parity(template, tmp_path):
    """虛線 m/l 座標＝render 幾何助手（toc_rule_line）＋出血偏移，兩後端同源。"""
    out = tmp_path / "toc-parity.pdf"
    export_pdf(make_toc_doc(["把回憶放回原位的方法"]), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    m = re.search(r"([\d.\-]+) ([\d.\-]+) m\n([\d.\-]+) ([\d.\-]+) l", content)
    assert m, "缺 m/l 線段路徑"
    x0, y0, x1, y1 = map(float, m.groups())

    master = template.masters["D-目錄"]
    line = toc_rule_line(mm_to_pt(template.page_width_mm), master.rule)
    page_h = mm_to_pt(template.page_height_mm)
    assert x0 == pytest.approx(BLEED_PT + line.x0, abs=0.3)
    assert x1 == pytest.approx(BLEED_PT + line.x1, abs=0.3)
    y_up = page_h + BLEED_PT - line.y0  # top-down → y-up
    assert y0 == pytest.approx(y_up, abs=0.3) and y1 == pytest.approx(y_up, abs=0.3)
    # 貼邊出血：線兩端正好落在出血邊（x0=0、x1=頁寬＋2×出血）
    assert x0 == pytest.approx(0.0, abs=0.3)
    assert x1 == pytest.approx(mm_to_pt(template.page_width_mm) + 2 * BLEED_PT, abs=0.3)


@needs_fonts
def test_export_toc_rule_preflight_green(template, tmp_path):
    """加虛線後目錄 PDF 仍過全部 X-1a 機械規則（color-cmyk-only 不退步）。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "tocx.pdf"
    export_pdf(make_toc_doc([
        "安放與整理的十個提問",
        "把回憶放回原位的方法",
    ]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


# ---------- 目錄條目頁碼＋引導線（Sprint 16） ----------

def make_toc_doc_paged(entries_with_pages):
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


@needs_fonts
def test_export_toc_leader_line_solid_k92_parity(template, tmp_path):
    """引導線：垂直實線（該狀態塊無 d）、K92 描邊、座標＝mark 幾何＋行軸＋出血。"""
    from cjkfolio.layout import layout_document
    doc = make_toc_doc_paged([("安放與整理的十個提問", "169")])
    out = tmp_path / "toc-entry.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert "0 0 0 0.92 K" in content, "引導線描邊非單 K92"
    # 引導線的 q…Q 塊：0.1 w、無 d、垂直 m/l
    blocks = re.findall(r"q\n(.*?)\nQ", content, re.S)
    leader = [b for b in blocks if "0.1 w" in b]
    assert leader, "缺引導線狀態塊（0.1 w）"
    assert " d" not in leader[0], "引導線不應掛 dash"
    lm = re.search(r"([\d.\-]+) ([\d.\-]+) m\n([\d.\-]+) ([\d.\-]+) l", leader[0])
    x0, y0, x1, y1 = map(float, lm.groups())
    assert x0 == pytest.approx(x1, abs=0.01), "引導線應為垂直線"

    master = template.masters["D-目錄"]
    m = layout_document(doc, template).toc_marks[1][0]
    axis = line_axis_x_pt(template, master, m.slot, 1, line_slots=m.line_slots)
    page_h = mm_to_pt(template.page_height_mm)
    assert x0 == pytest.approx(BLEED_PT + axis, abs=0.3)
    # top-down → y-up：兩端點集合比對（emit 順序不拘）
    got = sorted([y0, y1])
    want = sorted([page_h + BLEED_PT - m.leader_y0_pt, page_h + BLEED_PT - m.leader_y1_pt])
    assert got[0] == pytest.approx(want[0], abs=0.3)
    assert got[1] == pytest.approx(want[1], abs=0.3)


@needs_fonts
def test_export_toc_page_no_digits_positions(template, tmp_path):
    """頁碼三位直排逐位：PyMuPDF 抽字座標與 mark 幾何一致（底錨 490pt）。"""
    from cjkfolio.layout import layout_document
    doc = make_toc_doc_paged([("安放與整理的十個提問", "169")])
    out = tmp_path / "toc-digits.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    words = [w for w in pdf[0].get_text("words") if w[4] in ("1", "6", "9")]
    assert len(words) == 3, f"頁碼應為 3 個獨立直立數字，得到 {words}"

    master = template.masters["D-目錄"]
    m = layout_document(doc, template).toc_marks[1][0]
    axis = line_axis_x_pt(template, master, m.slot, 1, line_slots=m.line_slots)
    # 直排由上而下 1→6→9；PyMuPDF top-down 座標含出血（PDF 頁面原點含 bleed）
    words.sort(key=lambda w: w[1])
    assert [w[4] for w in words] == ["1", "6", "9"]
    for i, w in enumerate(words):
        cx = (w[0] + w[2]) / 2
        assert cx == pytest.approx(BLEED_PT + axis, abs=1.5), f"第 {i} 位未行軸置中"
        cell_top = m.page_no_top_pt + i * m.digit_advance_pt
        assert w[1] >= BLEED_PT + cell_top - 1.5, f"第 {i} 位高於字槽頂"
    # 末位底不越過底錨
    assert words[-1][3] <= BLEED_PT + master.toc.page_no_bottom_pt + 1.5


@needs_fonts
def test_export_toc_entry_preflight_green(template, tmp_path):
    """加頁碼與引導線後目錄 PDF 仍過全部 X-1a 機械規則。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "toc-entryx.pdf"
    export_pdf(make_toc_doc_paged([
        ("安放與整理的十個提問", "169"),
        ("把回憶放回原位的方法", "197"),
    ]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]
