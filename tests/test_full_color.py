"""全彩支援（Sprint 137）：螢幕保留原色，送印仍守 §9 兩種印前色彩空間。

起因是 Owner 真視窗回饋：置入的彩色封面圖在編輯器裡是黑白的（Sprint 92〜136 期間
open_placed 對非 CMYK 來源一律轉灰）。本檔驗的是「哪一條路留得住彩色」的分工：

- 讀取層：open_placed 保留 RGB（見 test_cmyk_image.py 的分流測試）
- 預覽層：PNG 畫布為 RGB，彩圖畫入後仍是彩的；單 K 文字維持中性灰不偏色
- 送印層（pdfx="x-1a"／"x-4"）：RGB 影像轉灰嵌入並記 image_color_warnings
- 一般 PDF（pdfx="none"）：不寫 OutputIntent 與 GTS 識別鍵，RGB 原樣 DeviceRGB

驗證一律走 PyMuPDF／PIL 獨立路徑（Gate 4）。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import fitz
import pytest
from PIL import Image

from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.images import EmbeddedImage
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import check_pdfx
from cjkfolio.render import render_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
G_MASTER = "G-圖文版"
ORANGE = (230, 120, 40)   # 三分量互異：轉灰會塌成同值，一眼可辨


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _color_image(path, size=(40, 30), color=ORANGE):
    Image.new("RGB", size, color).save(path)
    return path


def _figure_doc(name):
    return Document(title="樣張", template="x", master=G_MASTER,
                    paragraphs=(Paragraph(text="圖說", style="圖說-辰宇落雁"),),
                    images=(PlacedImage(path=name, page=1),))


def _text_doc(title="樣張"):
    """無置入圖的單頁內文文件（識別鍵與標題條款用，不牽扯影像）。"""
    return Document(title=title, template="x", master="A-內文版",
                    paragraphs=(Paragraph(text="留白是安放的開始。",
                                          style="內文-明體直排"),))


@pytest.fixture
def cmyk_icc(tmp_path):
    """最小可驗 CMYK 輸出 ICC（X-4 強制嵌；寫出層只驗長度／類別／色彩空間）。"""
    head = bytearray(132)
    head[0:4] = (132).to_bytes(4, "big")
    head[12:16] = b"prtr"
    head[16:20] = b"CMYK"
    path = tmp_path / "fake.icc"
    path.write_bytes(bytes(head))
    return path


def _first_image_colorspace(pdf_path):
    """獨立解析（PyMuPDF）取第 1 頁首張影像的色彩空間鍵。"""
    doc = fitz.open(pdf_path)
    xref = doc[0].get_images(full=True)[0][0]
    cs = doc.xref_get_key(xref, "ColorSpace")[1]
    doc.close()
    return cs


# ---------- 預覽層：PNG 畫布留得住彩色 ----------

def test_png_preview_keeps_image_color(tmp_path, template):
    """置入彩圖 → 預覽 PNG 為 RGB 且該處像素仍是彩的（不是灰）。"""
    _color_image(tmp_path / "c.png")
    result = render_document(_figure_doc("c.png"), template, tmp_path / "out",
                             footer=False, image_base_dir=tmp_path)
    assert result.images_placed == 1
    img = Image.open(result.paths[0])
    assert img.mode == "RGB"
    colors = {px for _, px in img.getcolors(maxcolors=65536)}
    assert ORANGE in colors          # 原色原樣落地（等比縮放不改純色區）
    assert any(r != g or g != b for r, g, b in colors)   # 全圖確實非中性灰


def test_png_preview_gray_source_stays_neutral(tmp_path, template):
    """灰階來源不因畫布轉 RGB 而偏色（三分量同值）。"""
    Image.new("L", (40, 30), 90).save(tmp_path / "g.png")
    result = render_document(_figure_doc("g.png"), template, tmp_path / "out",
                             footer=False, image_base_dir=tmp_path)
    img = Image.open(result.paths[0])
    assert (90, 90, 90) in {px for _, px in img.getcolors(maxcolors=65536)}


def test_png_preview_paper_white_and_text_ink(tmp_path, template):
    """紙白仍是純白、單 K92 文字仍是 (20,20,20)：既有輸出不因 RGB 畫布位移。"""
    result = render_document(_text_doc(), template, tmp_path / "out", footer=False)
    img = Image.open(result.paths[0])
    counts = {px: n for n, px in img.getcolors(maxcolors=65536)}
    assert img.getpixel((0, 0)) == (255, 255, 255)
    assert counts.get((20, 20, 20), 0) > 0        # K92 → 255×(1−0.92)＝20


# ---------- 送印層：PDF/X 轉灰並據實警告 ----------

@pytest.mark.parametrize("pdfx,icc_needed", [("x-1a", False), ("x-4", True)])
def test_pdfx_converts_rgb_image_to_gray_with_warning(tmp_path, template,
                                                      pdfx, icc_needed, cmyk_icc):
    _color_image(tmp_path / "c.png")
    out = tmp_path / "o.pdf"
    result = export_pdf(_figure_doc("c.png"), template, out, footer=False,
                        image_base_dir=tmp_path, pdfx=pdfx,
                        icc_profile=cmyk_icc if icc_needed else None)
    assert _first_image_colorspace(out) == "/DeviceGray"
    assert len(result.image_color_warnings) == 1
    msg = result.image_color_warnings[0]
    assert "c.png" in msg and "RGB" in msg
    assert "一般 PDF" in msg          # 訊息須給出可執行的解法
    assert dict(result.image_colorspaces) == {"/DeviceGray": 1}


def test_pdfx_rgb_image_still_passes_preflight(tmp_path, template):
    """轉灰後仍是合規 X-1a：色彩規則不因彩色來源而失敗。"""
    _color_image(tmp_path / "c.png")
    out = tmp_path / "o.pdf"
    export_pdf(_figure_doc("c.png"), template, out, footer=False,
               image_base_dir=tmp_path)
    report = check_pdfx(out)
    assert [f.rule for f in report.findings if not f.ok] == []


def test_pdfx_gray_and_cmyk_sources_warn_nothing(tmp_path, template):
    """§9 的兩種印前色彩空間原樣嵌入，不產生轉換警告（不誤報）。"""
    Image.new("L", (40, 30), 90).save(tmp_path / "g.png")
    result = export_pdf(_figure_doc("g.png"), template, tmp_path / "o.pdf",
                        footer=False, image_base_dir=tmp_path)
    assert result.image_color_warnings == ()


# ---------- 一般 PDF（pdfx="none"）：非 PDF/X，但留得住彩色 ----------

def test_none_profile_embeds_devicergb(tmp_path, template):
    _color_image(tmp_path / "c.png")
    out = tmp_path / "o.pdf"
    result = export_pdf(_figure_doc("c.png"), template, out, footer=False,
                        image_base_dir=tmp_path, pdfx="none")
    assert _first_image_colorspace(out) == "/DeviceRGB"
    assert dict(result.image_colorspaces) == {"/DeviceRGB": 1}
    assert result.image_color_warnings == ()     # 沒轉換就沒得警告


def test_none_profile_pixels_survive_roundtrip(tmp_path, template):
    """嵌入的位元組即原像素（未轉灰、未反相）：首像素三分量與來源相同。"""
    _color_image(tmp_path / "c.png", size=(4, 3))
    out = tmp_path / "o.pdf"
    export_pdf(_figure_doc("c.png"), template, out, footer=False,
               image_base_dir=tmp_path, pdfx="none")
    doc = fitz.open(out)
    raw = doc.xref_stream(doc[0].get_images(full=True)[0][0])
    doc.close()
    assert raw[:3] == bytes(ORANGE)


def test_none_profile_writes_no_pdfx_identification(tmp_path, template):
    """不是 PDF/X 就不宣稱是：無 OutputIntent、無 Info／XMP 的 GTS 鍵。"""
    out = tmp_path / "o.pdf"
    result = export_pdf(_text_doc(), template, out, footer=False, pdfx="none")
    raw = out.read_bytes()
    assert raw[:8] == b"%PDF-1.4"
    assert b"/OutputIntents" not in raw
    assert b"GTS_PDFX" not in raw            # Info 與 XMP 兩處皆無
    assert result.output_condition_identifier == ""   # 沒寫的鍵不對外宣稱
    assert result.icc_embedded is False
    assert result.pdfx_label == "一般 PDF（非 PDF/X，可含 RGB）"


def test_none_profile_fails_pdfx_preflight(tmp_path, template):
    """Gate 4 反向驗證：一般 PDF 拿去驗 X-1a 必然不過（不是偷偷的 PDF/X）。"""
    out = tmp_path / "o.pdf"
    export_pdf(_text_doc(), template, out, footer=False, pdfx="none")
    report = check_pdfx(out)
    assert not report.ok
    failed = {f.rule for f in report.findings if not f.ok}
    assert {"info-identification", "output-intent", "xmp-metadata",
            "header-version"} <= failed


def test_none_profile_rejects_icc_profile(tmp_path, template, cmyk_icc):
    """收下卻無處可嵌＝沉默丟棄，故快速失敗（不默默忽略使用者給的描述檔）。"""
    with pytest.raises(ValueError) as e:
        export_pdf(_text_doc(), template, tmp_path / "o.pdf", footer=False,
                   pdfx="none", icc_profile=cmyk_icc)
    assert "無處可嵌" in str(e.value)


def test_none_profile_allows_empty_title(tmp_path, template):
    """Info /Title 是 PDF/X 條款，非一般 PDF 條款：無標題不擋。"""
    out = tmp_path / "o.pdf"
    result = export_pdf(_text_doc(title=""), template, out, footer=False,
                        pdfx="none")
    assert result.page_count == 1
    assert out.exists()


def test_pdfx_still_requires_title(tmp_path, template):
    """送印形態的 /Title 條款不因新增形態而鬆動。"""
    with pytest.raises(ValueError) as e:
        export_pdf(_text_doc(title=""), template, tmp_path / "o.pdf",
                   footer=False)
    assert "Info /Title" in str(e.value)


def test_check_pdfx_rejects_none_profile(tmp_path, template):
    """preflight 只受理 PDF/X：拿非 PDF/X 形態當規則集是無意義的比對。"""
    out = tmp_path / "o.pdf"
    export_pdf(_text_doc(), template, out, footer=False)
    with pytest.raises(ValueError) as e:
        check_pdfx(out, profile="none")
    assert "非 PDF/X" in str(e.value)


def test_unknown_profile_still_rejected(tmp_path, template):
    with pytest.raises(ValueError) as e:
        export_pdf(_text_doc(), template, tmp_path / "o.pdf", footer=False,
                   pdfx="x-9")
    assert "未知 pdfx 形態" in str(e.value)


# ---------- 命令列：同一套說法 ----------

def _cli_doc(tmp_path, image="c.png"):
    """寫出 CLI 可讀的文件檔（含一張置入圖），回傳路徑。"""
    import json
    path = tmp_path / "d.doc.json"
    path.write_text(json.dumps({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "彩色樣張", "template": "neizai-zhengli",
                 "master": G_MASTER},
        "paragraphs": [{"text": "圖說", "style": "圖說-辰宇落雁"}],
        "images": [{"path": image, "page": 1}],
    }, ensure_ascii=False), encoding="utf-8")
    return path


def _cli_export(tmp_path, capsys, *extra):
    from cjkfolio.cli import main
    rc = main(["export-pdf", str(_cli_doc(tmp_path)),
               "-o", str(tmp_path / "cli.pdf"),
               "--template", str(ROOT / "templates" / "neizai-zhengli.json"),
               "--no-footer", *extra])
    return rc, capsys.readouterr().out


def test_cli_none_profile_reports_not_printable(tmp_path, capsys):
    """--pdfx none：據實說無 OutputIntent 不可送印，且置入圖列為 DeviceRGB。"""
    _color_image(tmp_path / "c.png")
    rc, out = _cli_export(tmp_path, capsys, "--pdfx", "none")
    assert rc == 0
    assert "無 OutputIntent、無 GTS 識別鍵，不可送印" in out
    assert "一般 PDF（非 PDF/X，可含 RGB）" in out
    assert "DeviceRGB 1 張" in out
    assert "影像色彩：" not in out          # 沒轉換就沒得警告


def test_cli_pdfx_reports_color_conversion(tmp_path, capsys):
    """預設 X-1a：轉灰一事寫在「影像色彩：」列，不靜默吞掉。"""
    _color_image(tmp_path / "c.png")
    rc, out = _cli_export(tmp_path, capsys)
    assert rc == 0
    assert "影像色彩：" in out and "c.png" in out
    assert "DeviceGray 1 張" in out
    assert "PDF/X-1a:2001 識別：OutputIntent" in out


# ---------- 影像領域層：RGB 的 PDF 形態 ----------

def test_embedded_image_emit_devicergb():
    emb = EmbeddedImage(Image.new("RGB", (3, 2), ORANGE), "Im1")
    assert emb.colorspace == "/DeviceRGB"
    assert len(emb.data) == 3 * 2 * 3        # 每像素三分量
    assert emb.data[:3] == bytes(ORANGE)
