"""PDF 寫出層（cjkfolio.pdf_writer）：盒框、子集嵌入、幾何、頁腳、單 K。

驗證一律走 PyMuPDF（與寫出層不同實作，Gate 4 獨立驗證）。
測試素材一律自擬（版權紅線）。
"""
import re
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.pdf_writer import export_pdf, page_boxes_pt, subset_tag
from cjkfolio.render import line_axis_x_pt, mm_to_pt
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
    # 全頁匯出：520 字 → 2 頁
    out_all = tmp_path / "all.pdf"
    r_all = export_pdf(doc, template, out_all, first_page=30)
    assert r_all.page_count == 2
    pdf_all = fitz.open(str(out_all))
    assert pdf_all.page_count == 2
    p1 = pdf_all[0].get_text()
    assert "30" in p1 and "自擬樣張" in p1  # 頁碼＋書眉（奇數頁）
    p2 = pdf_all[1].get_text()
    assert "31" in p2 and "自擬樣張" not in p2  # 偶數頁無書眉

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
def test_export_text_is_single_k(template, tmp_path):
    doc = make_doc([{"text": "單色檢查。", "style": "內文-明體直排"}])
    out = tmp_path / "k.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents())
    assert b"0 0 0 0.92 k" in content, "內文未用單 K92（DeviceCMYK）"
    assert b" rg" not in content and b" RG" not in content, "內容流殘留 RGB 色彩"


@needs_fonts
def test_export_rejects_horizontal_style(template, tmp_path):
    doc = make_doc([{"text": "橫排未支援", "style": "版權頁-CIP橫排"}])
    with pytest.raises(ValueError, match="vertical-rl"):
        export_pdf(doc, template, tmp_path / "h.pdf")


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
