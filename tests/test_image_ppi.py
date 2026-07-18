"""影像解析度 PPI 檢核測試（Sprint 91，Phase 4；GAPS #29 (b)）。

兩側獨立路徑（Gate 4 紀律）：
- 產出側（producer）：images.effective_ppi／resolution_warnings 以來源像素數與
  fit_image_rect 繪製尺寸算實效 PPI，export_pdf 收於 PdfResult.ppi_warnings。
- 驗證側（verifier）：preflight.check_image_resolution 以 PyMuPDF 獨立解析已寫出
  PDF 的影像 XObject 與繪製 bbox 反算 PPI，不看產出側任何中間值。

PPI 非 ISO 15930-1 條款，故不入 X-1a 規則集（規則數維持 12，本檔釘死）。
門檻 §9「連續調影像 300〜350ppi」取 300 為下限。

循 tests/ 分檔慣例（各檔自帶 fixture／helper，不建共享 conftest）。
"""
import json
from pathlib import Path

import fitz
import pytest
from PIL import Image

from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.images import (
    MIN_IMAGE_PPI,
    PPI_TOLERANCE,
    ImageResolution,
    effective_ppi,
    meets_ppi,
    resolution_warnings,
)
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import (
    ImageResolutionReport,
    check_image_resolution,
    check_pdfx1a,
    image_resolution_summary,
)
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
G_MASTER = "G-圖文版"


@pytest.fixture
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _make_image(path, w, h):
    """自擬灰階測試圖：尺寸即解析度變因（內容不影響 PPI 判定）。"""
    Image.new("L", (w, h), 160).save(path)
    return path


def _figure_doc(image_name):
    """單頁 G 圖文版文件：一段圖說＋一張槽式置入圖（落 photo-slot 保留區）。"""
    return Document(
        title="解析度檢核樣張", template="neizai-zhengli", master=G_MASTER,
        paragraphs=(Paragraph(text="整理前後對照", style="圖說-辰宇落雁"),),
        images=(PlacedImage(path=image_name, page=1),),
    )


def _res(px_w, px_h, draw_w, draw_h, page=1, path="a.png"):
    return ImageResolution(path=path, page=page, px_w=px_w, px_h=px_h,
                           draw_w_pt=draw_w, draw_h_pt=draw_h)


# ---------- effective_ppi 純函式 ----------

def test_effective_ppi_one_inch():
    # 72pt＝1 英吋：300 像素繪成 1 英吋恰 300ppi
    assert effective_ppi(300, 72.0) == pytest.approx(300.0)


def test_effective_ppi_half_inch_doubles():
    assert effective_ppi(300, 36.0) == pytest.approx(600.0)


def test_effective_ppi_rejects_non_positive_draw():
    with pytest.raises(ValueError):
        effective_ppi(300, 0.0)


def test_effective_ppi_rejects_non_positive_pixels():
    with pytest.raises(ValueError):
        effective_ppi(0, 72.0)


# ---------- ImageResolution.ppi 取兩軸較小 ----------

def test_resolution_ppi_takes_worse_axis():
    r = _res(300, 300, 72.0, 144.0)  # 橫 300ppi、縱 150ppi
    assert r.ppi == pytest.approx(150.0)


def test_resolution_uniform_scale_axes_agree():
    r = _res(400, 600, 96.0, 144.0)  # 等比縮放（contain）兩軸同值
    assert r.ppi == pytest.approx(300.0)


# ---------- resolution_warnings 彙整 ----------

def test_warnings_empty_when_above_threshold():
    assert resolution_warnings([_res(1600, 2400, 240.0, 360.0)]) == []


def test_warnings_list_low_resolution_with_numbers():
    w = resolution_warnings([_res(400, 600, 240.0, 360.0, path="low.png")])
    assert len(w) == 1
    assert "low.png" in w[0] and "頁 1" in w[0]
    assert "120" in w[0] and "300" in w[0]  # 實效 ppi 與門檻皆列出


def test_warnings_respects_custom_threshold():
    r = _res(1600, 2400, 240.0, 360.0)  # 480ppi
    assert resolution_warnings([r], min_ppi=600.0) != []
    assert resolution_warnings([r], min_ppi=300.0) == []


def test_warnings_default_threshold_is_plan_spec():
    assert MIN_IMAGE_PPI == 300.0  # §9 連續調影像 300〜350ppi 的下限


def test_warnings_empty_input():
    assert resolution_warnings([]) == []


# ---------- 浮點容差（參考書 p138 實測 299.999996ppi 假陽性的回歸守門） ----------

def test_exactly_at_threshold_passes():
    # 756px 繪 181.44pt＝299.999996ppi（參考書 p138 實測值，浮點誤差 4e-6）
    r = _res(756, 1008, 181.44000244140625, 241.91998291015625)
    assert r.ppi < MIN_IMAGE_PPI          # 數學上確實低於門檻
    assert meets_ppi(r.ppi) is True       # 但在容差內判達標
    assert resolution_warnings([r]) == []


def test_tolerance_boundary_both_sides():
    assert PPI_TOLERANCE == 0.5  # 報告顯示精度（四捨五入至整數 ppi）
    assert meets_ppi(MIN_IMAGE_PPI - PPI_TOLERANCE * 0.8) is True
    assert meets_ppi(MIN_IMAGE_PPI - PPI_TOLERANCE * 1.2) is False


def test_clearly_low_still_flagged_with_tolerance():
    assert meets_ppi(254.5) is False      # 參考書 p146 標章實測值
    assert resolution_warnings([_res(186, 71, 52.62, 20.09)]) != []


def test_tolerance_never_contradicts_displayed_ppi():
    """報告顯示四捨五入至整數 ppi：判不足者顯示值必嚴格小於門檻（不自相矛盾）。"""
    for ppi in (250.0, 299.4, 299.49):
        assert not meets_ppi(ppi)
        assert round(ppi) < MIN_IMAGE_PPI


# ---------- 匯出整合（producer 側） ----------

def test_export_reports_low_resolution(tmp_path, template):
    _make_image(tmp_path / "low.png", 400, 600)
    result = export_pdf(_figure_doc("low.png"), template, tmp_path / "low.pdf",
                        footer=False, image_base_dir=tmp_path)
    assert len(result.image_resolutions) == 1
    assert result.image_resolutions[0].ppi < MIN_IMAGE_PPI
    assert len(result.ppi_warnings) == 1
    assert "low.png" in result.ppi_warnings[0]


def test_export_silent_when_resolution_sufficient(tmp_path, template):
    _make_image(tmp_path / "hi.png", 1600, 2400)
    result = export_pdf(_figure_doc("hi.png"), template, tmp_path / "hi.pdf",
                        footer=False, image_base_dir=tmp_path)
    assert result.image_resolutions[0].ppi >= MIN_IMAGE_PPI
    assert list(result.ppi_warnings) == []


def test_export_without_images_has_no_resolutions(tmp_path, template):
    doc = Document(title="無圖", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="整理與安放", style="內文-明體直排"),))
    result = export_pdf(doc, template, tmp_path / "plain.pdf", footer=False)
    assert list(result.image_resolutions) == []
    assert list(result.ppi_warnings) == []


# ---------- preflight 獨立檢查（verifier 側，PyMuPDF） ----------

def test_check_image_resolution_flags_low(tmp_path, template):
    _make_image(tmp_path / "low.png", 400, 600)
    out = tmp_path / "low.pdf"
    export_pdf(_figure_doc("low.png"), template, out, footer=False,
               image_base_dir=tmp_path)
    report = check_image_resolution(out)
    assert isinstance(report, ImageResolutionReport)
    assert len(report.findings) == 1
    assert report.findings[0].ok is False
    assert report.ok is False
    assert "不足" in image_resolution_summary(report)


def test_check_image_resolution_passes_sufficient(tmp_path, template):
    _make_image(tmp_path / "hi.png", 1600, 2400)
    out = tmp_path / "hi.pdf"
    export_pdf(_figure_doc("hi.png"), template, out, footer=False,
               image_base_dir=tmp_path)
    report = check_image_resolution(out)
    assert report.ok is True
    assert report.findings[0].ppi >= MIN_IMAGE_PPI
    assert "全數達標" in image_resolution_summary(report)


def test_check_image_resolution_no_images_is_ok(tmp_path, template):
    doc = Document(title="無圖", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="整理與安放", style="內文-明體直排"),))
    out = tmp_path / "plain.pdf"
    export_pdf(doc, template, out, footer=False)
    report = check_image_resolution(out)
    assert report.findings == ()
    assert report.ok is True
    assert "無置入影像" in image_resolution_summary(report)


def test_check_image_resolution_custom_threshold(tmp_path, template):
    _make_image(tmp_path / "hi.png", 1600, 2400)
    out = tmp_path / "hi.pdf"
    export_pdf(_figure_doc("hi.png"), template, out, footer=False,
               image_base_dir=tmp_path)
    assert check_image_resolution(out, min_ppi=600.0).ok is False
    assert check_image_resolution(out, min_ppi=300.0).ok is True


# ---------- 兩側交叉驗證與 X-1a 規則集不受影響 ----------

def test_producer_and_verifier_agree(tmp_path, template):
    """Gate 4：產出側（來源像素＋fit_image_rect）與驗證側（PyMuPDF bbox 反算）同值。"""
    _make_image(tmp_path / "x.png", 900, 1400)
    out = tmp_path / "x.pdf"
    result = export_pdf(_figure_doc("x.png"), template, out, footer=False,
                        image_base_dir=tmp_path)
    report = check_image_resolution(out)
    assert len(report.findings) == len(result.image_resolutions) == 1
    assert report.findings[0].ppi == pytest.approx(
        result.image_resolutions[0].ppi, abs=0.5)


def test_xpdfx_rule_set_unchanged_by_low_resolution(tmp_path, template):
    """PPI 非 ISO 15930-1 條款：低解析度不使 X-1a 規則集不過，規則數維持 12。"""
    _make_image(tmp_path / "low.png", 400, 600)
    out = tmp_path / "low.pdf"
    export_pdf(_figure_doc("low.png"), template, out, footer=False,
               image_base_dir=tmp_path)
    report = check_pdfx1a(out)
    assert len(report.findings) == 12
    assert report.ok is True


def test_not_covered_points_to_separate_checker(tmp_path, template):
    """NOT_COVERED 的 PPI 條目須指向獨立檢查器（誠實聲明不失效）。"""
    doc = Document(title="無圖", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="整理與安放", style="內文-明體直排"),))
    out = tmp_path / "plain.pdf"
    export_pdf(doc, template, out, footer=False)
    ppi_entries = [e for e in check_pdfx1a(out).not_covered if "PPI" in e]
    assert len(ppi_entries) == 1
    assert "check_image_resolution" in ppi_entries[0]


def test_cli_export_prints_low_resolution_warning(tmp_path, capsys):
    from cjkfolio.cli import main
    _make_image(tmp_path / "low.png", 400, 600)
    docp = tmp_path / "d.json"
    docp.write_text(json.dumps({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "CLI 解析度", "template": "neizai-zhengli", "master": G_MASTER},
        "paragraphs": [{"text": "整理前後對照", "style": "圖說-辰宇落雁"}],
        "images": [{"path": "low.png", "page": 1}],
    }, ensure_ascii=False), encoding="utf-8")
    rc = main(["export-pdf", str(docp), "-o", str(tmp_path / "cli.pdf"),
               "--template", str(ROOT / "templates" / "neizai-zhengli.json"),
               "--no-footer"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "影像解析度" in out and "low.png" in out and "300ppi" in out


def test_cli_preflight_prints_image_section(tmp_path, template, capsys):
    from cjkfolio.cli import main
    _make_image(tmp_path / "hi.png", 1600, 2400)
    out_pdf = tmp_path / "hi.pdf"
    export_pdf(_figure_doc("hi.png"), template, out_pdf, footer=False,
               image_base_dir=tmp_path)
    assert main(["preflight", str(out_pdf)]) == 0  # X-1a 仍通過（PPI 不影響合規）
    out = capsys.readouterr().out
    assert "影像解析度（§9，非 X-1a 條款）：全數達標" in out
    capsys.readouterr()
    # 門檻拉高後影像區報不足，X-1a 結論仍為通過（退出碼依 X-1a）
    assert main(["preflight", str(out_pdf), "--min-ppi", "600"]) == 0
    out = capsys.readouterr().out
    assert "解析度不足" in out and "全數通過（12/12）" in out


def test_verifier_reads_pdf_not_source(tmp_path, template):
    """驗證側只讀 PDF：來源圖檔刪除後仍可檢查（證明無隱性依賴產出側狀態）。"""
    img = _make_image(tmp_path / "gone.png", 400, 600)
    out = tmp_path / "gone.pdf"
    export_pdf(_figure_doc("gone.png"), template, out, footer=False,
               image_base_dir=tmp_path)
    Path(img).unlink()
    report = check_image_resolution(out)
    assert len(report.findings) == 1 and report.findings[0].ok is False
    with fitz.open(out) as d:  # 影像確實在 PDF 內（獨立確認）
        assert len(d.get_page_images(0)) == 1
