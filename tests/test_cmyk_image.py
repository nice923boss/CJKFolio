"""彩色 CMYK 影像置入（Sprint 92，PLAN §9「全文 CMYK 或 Grayscale」；關 GAPS #29 (c)）。

涵蓋：open_placed 依來源色彩空間分流（CMYK 保留／其餘轉灰階）、CMYK JPEG 快速失敗
（spike18 實測 PIL 對 Adobe YCCK JPEG 讀出反相值）、EmbeddedImage 的 DeviceCMYK
形態、兩後端置入（PDF 寫 DeviceCMYK／PNG 預覽轉灰階）、preflight 與 PPI 不退步。

真書素材為紅線不入 repo，本檔一律用程式合成的 CMYK 圖（極值可手算）。
"""
import re

import fitz
import pytest
from PIL import Image

from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.images import (
    EmbeddedImage,
    ImageError,
    open_grayscale,
    open_placed,
)
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import check_pdfx
from cjkfolio.render import render_document
from cjkfolio.styles import load_template

G_MASTER = "G-圖文版"


@pytest.fixture
def template():
    return load_template("templates/neizai-zhengli.json")


def _make_cmyk(path, size=(4, 1)):
    """合成 CMYK 圖：白（無墨）／單 K 黑／純青／純洋紅，分量值可手算。"""
    im = Image.new("CMYK", size)
    for x, px in enumerate(((0, 0, 0, 0), (0, 0, 0, 255), (255, 0, 0, 0), (0, 255, 0, 0))):
        if x < size[0]:
            im.putpixel((x, 0), px)
    im.save(path)
    return path


def _figure_doc(name):
    return Document(title="t", template="x", master=G_MASTER,
                    paragraphs=(Paragraph(text="圖說", style="圖說-辰宇落雁"),),
                    images=(PlacedImage(path=name, page=1),))


# ---------- open_placed：來源色彩空間分流 ----------

def test_open_placed_keeps_cmyk(tmp_path):
    im = open_placed(_make_cmyk(tmp_path / "c.tif"))
    assert im.mode == "CMYK"
    assert im.getpixel((0, 0)) == (0, 0, 0, 0)      # 白＝無墨，未反相
    assert im.getpixel((1, 0)) == (0, 0, 0, 255)    # 單 K 黑


def test_open_placed_converts_rgb_to_gray(tmp_path):
    p = tmp_path / "rgb.png"
    Image.new("RGB", (3, 2), (200, 100, 50)).save(p)
    assert open_placed(p).mode == "L"


def test_open_placed_converts_palette_to_gray(tmp_path):
    p = tmp_path / "pal.png"
    Image.new("P", (3, 2)).save(p)
    assert open_placed(p).mode == "L"


def test_open_placed_missing_file_raises(tmp_path):
    with pytest.raises(ImageError):
        open_placed(tmp_path / "nope.tif")


def test_open_grayscale_still_forces_gray_on_cmyk(tmp_path):
    """既有 open_grayscale 語意不變（恆轉灰階），彩色分流只在 open_placed。"""
    assert open_grayscale(_make_cmyk(tmp_path / "c.tif")).mode == "L"


# ---------- CMYK JPEG 快速失敗（spike18 反相風險） ----------

def test_open_placed_cmyk_jpeg_fast_fails(tmp_path):
    p = tmp_path / "c.jpg"
    Image.new("CMYK", (8, 8), (10, 20, 30, 40)).save(p, quality=95)
    with pytest.raises(ImageError) as e:
        open_placed(p)
    msg = str(e.value)
    assert "CMYK JPEG" in msg
    assert "TIFF" in msg          # 訊息須給出可執行的解法


def test_rgb_jpeg_still_accepted(tmp_path):
    """只擋 CMYK JPEG；一般 RGB JPEG 照舊走灰階，不誤傷。"""
    p = tmp_path / "rgb.jpg"
    Image.new("RGB", (8, 8), (120, 130, 140)).save(p)
    assert open_placed(p).mode == "L"


# ---------- EmbeddedImage：DeviceCMYK 形態 ----------

class _FakeBuilder:
    def __init__(self):
        self.calls = []

    def stream(self, extra_dict, data):
        self.calls.append((extra_dict, data))
        return 42


def test_embedded_image_emit_devicecmyk():
    emb = EmbeddedImage(Image.new("CMYK", (3, 2), (1, 2, 3, 4)), "Im1")
    assert emb.width == 3 and emb.height == 2
    assert len(emb.data) == 3 * 2 * 4        # 每像素四分量
    b = _FakeBuilder()
    assert emb.emit(b) == 42
    extra, data = b.calls[0]
    for token in ("/Subtype /Image", "/ColorSpace /DeviceCMYK",
                  "/Width 3", "/Height 2", "/BitsPerComponent 8"):
        assert token in extra
    assert "/SMask" not in extra              # X-1a 禁透明
    assert "/Decode" not in extra             # 真書 DeviceCMYK 亦無反相陣列
    assert data == emb.data


def test_embedded_image_rejects_unsupported_mode():
    with pytest.raises(ImageError):
        EmbeddedImage(Image.new("RGB", (2, 2)), "Im1")


def test_embedded_image_cmyk_bytes_are_not_inverted():
    """白（0,0,0,0）必須原值寫出：反相會使白區變成滿墨 255,255,255,255。"""
    emb = EmbeddedImage(Image.new("CMYK", (1, 1), (0, 0, 0, 0)), "Im1")
    assert emb.data == b"\x00\x00\x00\x00"


# ---------- 端到端：PDF 寫 DeviceCMYK、PNG 預覽轉灰階 ----------

def test_export_writes_devicecmyk_image(tmp_path, template):
    _make_cmyk(tmp_path / "c.tif")
    out = tmp_path / "o.pdf"
    export_pdf(_figure_doc("c.tif"), template, out, footer=False,
               image_base_dir=tmp_path)
    doc = fitz.open(out)
    xref = doc[0].get_images(full=True)[0][0]
    assert doc.xref_get_key(xref, "ColorSpace")[1] == "/DeviceCMYK"
    assert int(doc.xref_get_key(xref, "BitsPerComponent")[1]) == 8
    assert doc.xref_get_key(xref, "SMask")[0] == "null"
    raw = doc.xref_stream(xref)
    doc.close()
    assert raw[:4] == b"\x00\x00\x00\x00"     # 首像素白，往返未反相


def test_export_cmyk_image_passes_preflight(tmp_path, template):
    _make_cmyk(tmp_path / "c.tif")
    out = tmp_path / "o.pdf"
    export_pdf(_figure_doc("c.tif"), template, out, footer=False,
               image_base_dir=tmp_path)
    report = check_pdfx(out)
    failed = [f.rule for f in report.findings if not f.ok]
    assert failed == []                        # DeviceCMYK 不觸 color-cmyk-only
    assert len(report.findings) == 12


def test_export_gray_image_still_devicegray(tmp_path, template):
    """灰階來源不因本 Sprint 改走 CMYK（既有輸出形態不變）。"""
    Image.new("L", (4, 3), 128).save(tmp_path / "g.png")
    out = tmp_path / "o.pdf"
    export_pdf(_figure_doc("g.png"), template, out, footer=False,
               image_base_dir=tmp_path)
    doc = fitz.open(out)
    xref = doc[0].get_images(full=True)[0][0]
    cs = doc.xref_get_key(xref, "ColorSpace")[1]
    doc.close()
    assert cs == "/DeviceGray"


def test_render_png_preview_accepts_cmyk(tmp_path, template):
    """PNG 為灰階預覽畫布（Sprint 38 (c) 慣例）：CMYK 圖轉灰階畫入，不崩。"""
    _make_cmyk(tmp_path / "c.tif", size=(40, 30))
    result = render_document(_figure_doc("c.tif"), template, tmp_path / "out",
                             footer=False, image_base_dir=tmp_path)
    assert result.images_placed == 1
    assert result.violations == []
    png = sorted((tmp_path / "out").glob("*.png"))[0]
    assert Image.open(png).mode == "L"


def test_cmyk_image_ppi_recorded(tmp_path, template):
    """解析度檢核（Sprint 91）對 CMYK 影像同樣運作。"""
    _make_cmyk(tmp_path / "c.tif", size=(4, 1))
    out = tmp_path / "o.pdf"
    result = export_pdf(_figure_doc("c.tif"), template, out, footer=False,
                        image_base_dir=tmp_path)
    assert len(result.image_resolutions) == 1
    assert result.image_resolutions[0].px_w == 4
    assert result.ppi_warnings                 # 4px 置入必然遠低於 300ppi


def test_result_reports_image_colorspaces(tmp_path, template):
    """匯出結果據實回報各色彩空間張數（CLI 據此列印，不寫死 DeviceGray）。"""
    _make_cmyk(tmp_path / "c.tif")
    Image.new("L", (4, 3), 128).save(tmp_path / "g.png")
    doc = Document(title="t", template="x", master=G_MASTER,
                   paragraphs=(Paragraph(text="圖說", style="圖說-辰宇落雁"),),
                   images=(PlacedImage(path="c.tif", page=1),
                           PlacedImage(path="g.png", page=1,
                                       rect=(20.0, 20.0, 80.0, 60.0))))
    result = export_pdf(doc, template, tmp_path / "o.pdf", footer=False,
                        image_base_dir=tmp_path)
    assert result.images_placed == 2
    assert dict(result.image_colorspaces) == {"/DeviceCMYK": 1, "/DeviceGray": 1}


def test_result_image_colorspaces_empty_without_images(tmp_path, template):
    doc = Document(title="t", template="x", master="A-內文版",
                   paragraphs=(Paragraph(text="內文", style="內文-明體直排"),))
    result = export_pdf(doc, template, tmp_path / "o.pdf", footer=False)
    assert result.images_placed == 0
    assert dict(result.image_colorspaces) == {}


def test_cmyk_content_stream_has_no_rgb_operators(tmp_path, template):
    """置入 CMYK 影像不得在內容流引入 rg／RG（§9 無殘留 RGB）。"""
    _make_cmyk(tmp_path / "c.tif")
    out = tmp_path / "o.pdf"
    export_pdf(_figure_doc("c.tif"), template, out, footer=False,
               image_base_dir=tmp_path)
    doc = fitz.open(out)
    data = b"".join(doc.xref_stream(cx) or b"" for cx in doc[0].get_contents())
    doc.close()
    assert not re.search(rb"(?:^|[\s\]>])(rg|RG)(?:$|[\s/%])", data)
