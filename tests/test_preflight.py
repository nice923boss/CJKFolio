"""PDF/X-1a 機械 preflight（cjkfolio.preflight）。

檢查器與寫出層不同實作（PyMuPDF 解析，Gate 4 獨立驗證）；
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import RULE_IDS, check_pdfx1a
from cjkfolio.styles import load_template

fitz = pytest.importorskip("fitz")


def fake_icc(space: bytes = b"CMYK", klass: bytes = b"prtr") -> bytes:
    """最小可驗 ICC（與 test_pdf_writer.fake_icc 同構，避免跨測試檔匯入）。"""
    head = bytearray(132)
    head[0:4] = (132).to_bytes(4, "big")
    head[12:16] = klass
    head[16:20] = space
    return bytes(head)

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


def make_doc():
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "檢查器樣張：整理與安放。", "style": "內文-明體直排"}],
    })


def _failed_rules(report):
    return {f.rule for f in report.findings if not f.ok}


@needs_fonts
def test_preflight_passes_on_exported_pdf(template, tmp_path):
    out = tmp_path / "ok.pdf"
    export_pdf(make_doc(), template, out)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]
    assert {f.rule for f in report.findings} == set(RULE_IDS), "規則清單須全數執行"
    assert report.not_covered, "未涵蓋項須誠實列出"


@needs_fonts
def test_preflight_passes_with_custom_icc(template, tmp_path):
    icc = tmp_path / "fake.icc"
    icc.write_bytes(fake_icc())
    out = tmp_path / "icc.pdf"
    export_pdf(make_doc(), template, out,
               output_condition_identifier="ShopX Custom",
               output_condition="測試條件", icc_profile=icc)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


def test_preflight_fails_on_plain_pdf(tmp_path):
    """一般 PDF（無 X 識別、無 TrimBox、RGB 內容）逐條落網。"""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(20, 20, 80, 80), color=(1, 0, 0), fill=(1, 0, 0))
    path = tmp_path / "plain.pdf"
    doc.save(str(path))

    report = check_pdfx1a(path)
    assert not report.ok
    bad = _failed_rules(report)
    assert "header-version" in bad       # PyMuPDF 預設寫 1.7
    assert "info-identification" in bad  # 無 GTS 鍵、無 Trapped
    assert "output-intent" in bad        # 無 OutputIntent
    assert "page-boxes" in bad           # 無 TrimBox
    assert "color-cmyk-only" in bad      # rg/RG RGB 著色
    assert "xmp-metadata" in bad         # 無 XMP


def _minimal_pdf(objects) -> bytes:
    """與寫出層無關的測試用最小 PDF 組裝（負向案例夾具）。"""
    out = bytearray(b"%PDF-1.3\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1")
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF"
    ).encode("latin-1")
    return bytes(out)


def test_preflight_flags_lzw_and_rgb_tokens(tmp_path):
    """人造最小 PDF：資源掛 /DeviceRGB、串流宣告 LZWDecode → 兩規則落網。"""
    path = tmp_path / "hand.pdf"
    path.write_bytes(_minimal_pdf([
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
        "/Resources << /ColorSpace << /CS0 /DeviceRGB >> >> /Contents 4 0 R >>",
        "<< /Length 0 /Filter /LZWDecode >>\nstream\n\nendstream",
    ]))
    report = check_pdfx1a(path)
    bad = _failed_rules(report)
    assert "color-cmyk-only" in bad
    assert "no-lzw" in bad
