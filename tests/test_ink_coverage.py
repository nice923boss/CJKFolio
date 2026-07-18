"""油墨總量 TAC 檢核（Sprint 93，Phase 4；PLAN §9「總墨量 ≤ 320〜340%」）。

兩側獨立路徑（Gate 4 紀律，同 Sprint 91 PPI 慣例）：
- 產出側（producer）：ink.tac_percent／image_max_tac 對本產品**即將寫出**的著色值
  與置入影像像素算 TAC，export_pdf 收於 PdfResult.ink_uses／tac_warnings。
- 驗證側（verifier）：preflight.check_ink_coverage 以 PyMuPDF 自**已寫出的 PDF**
  反算（內容流 k／K 算符＋影像 XObject 解碼），不看產出側任何中間值。

TAC 非 ISO 15930-1 條款（是紙張吸墨與乾燥的印廠條件），故不入 X-1a 規則集
（規則數維持 12，本檔釘死）。門檻取 §9 區間下限 320% 為預設，可調。

真書素材為紅線不入 repo，本檔一律用程式合成的圖與自擬色票（極值可手算）；
真書量測值（富黑 349.5%、影像最大 357%）只作為測試取值的依據，不含其內容。
"""
import json
from pathlib import Path

import fitz
import pytest
from PIL import Image

from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.ink import (
    MAX_TAC,
    TAC_TOLERANCE,
    InkUse,
    image_max_tac,
    meets_tac,
    tac_percent,
    tac_warnings,
)
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import (
    InkCoverageReport,
    check_ink_coverage,
    check_pdfx1a,
    ink_coverage_summary,
)
from cjkfolio.styles import load_template, template_from_dict, template_to_dict

ROOT = Path(__file__).resolve().parents[1]
G_MASTER = "G-圖文版"
BODY = "內文-明體直排"
# 真書送印稿實測的富黑（tools/measure_ink_coverage.py：8 頁手繪路徑用此值，
# TAC 349.5% 超 §9 上限）：只取色值作為超標樣本，不含真書任何內容
RICH_BLACK = (0.929, 0.878, 0.889, 0.799)


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


@pytest.fixture
def rich_black_template(template):
    """自擬模版：加富黑色票並讓內文樣式引用（走載入路徑，同 test_colors 慣例）。"""
    data = template_to_dict(template)
    data["colors"]["自擬富黑"] = {"cmyk": list(RICH_BLACK)}
    data["paragraph_styles"][BODY]["color"] = "自擬富黑"
    return template_from_dict(data)


def _text_doc():
    return Document(title="TAC 樣張", template="neizai-zhengli", master="A-內文版",
                    paragraphs=(Paragraph(text="整理與安放", style=BODY),))


def _figure_doc(image_name):
    return Document(
        title="TAC 圖樣張", template="neizai-zhengli", master=G_MASTER,
        paragraphs=(Paragraph(text="整理前後對照", style="圖說-辰宇落雁"),),
        images=(PlacedImage(path=image_name, page=1),),
    )


def _make_cmyk(path, heaviest):
    """合成 CMYK 圖：一枚最重墨像素＋其餘留白（最大值可手算，非平均）。"""
    im = Image.new("CMYK", (4, 4), (0, 0, 0, 0))
    im.putpixel((2, 3), heaviest)
    im.save(path)
    return path


def _make_gray(path, darkest=0):
    im = Image.new("L", (4, 4), 255)
    im.putpixel((1, 1), darkest)
    im.save(path)
    return path


# ---------- tac_percent 純函式 ----------

def test_tac_percent_single_k92():
    """本產品預設內文暖黑 K92（§9 內文轉單 K90-92）＝TAC 92%。"""
    assert tac_percent((0.0, 0.0, 0.0, 0.92)) == pytest.approx(92.0)


def test_tac_percent_rich_black_matches_reference_measurement():
    """真書手繪路徑富黑實測 TAC 349.5%（tools/measure_ink_coverage.py）。"""
    assert tac_percent(RICH_BLACK) == pytest.approx(349.5)


def test_tac_percent_paper_white_is_zero():
    assert tac_percent((0.0, 0.0, 0.0, 0.0)) == 0.0


def test_tac_percent_four_full_plates_is_400():
    assert tac_percent((1.0, 1.0, 1.0, 1.0)) == pytest.approx(400.0)


def test_tac_percent_rejects_out_of_range():
    with pytest.raises(ValueError):
        tac_percent((0.0, 0.0, 0.0, 1.5))


def test_tac_percent_rejects_wrong_component_count():
    with pytest.raises(ValueError):
        tac_percent((0.0, 0.0, 0.0))


# ---------- meets_tac 門檻 ----------

def test_max_tac_default_is_plan_lower_bound():
    assert MAX_TAC == 320.0  # §9「總墨量 ≤ 320〜340%」取保守下限為預設


def test_meets_tac_at_threshold_passes():
    assert meets_tac(320.0) is True


def test_meets_tac_over_threshold_fails():
    assert meets_tac(349.5) is False


def test_meets_tac_tolerance_never_contradicts_display():
    """報告顯示四捨五入至整數 %：判超標者顯示值必嚴格大於門檻。"""
    assert TAC_TOLERANCE == 0.5
    assert meets_tac(MAX_TAC + TAC_TOLERANCE * 0.8) is True
    assert meets_tac(MAX_TAC + TAC_TOLERANCE * 1.2) is False
    assert round(MAX_TAC + TAC_TOLERANCE * 1.2) > MAX_TAC


def test_meets_tac_custom_threshold():
    assert meets_tac(338.0, max_tac=340.0) is True   # §9 區間上限放寬後達標
    assert meets_tac(338.0, max_tac=320.0) is False


# ---------- image_max_tac 純函式 ----------

def test_image_max_tac_grayscale_black_is_100():
    """DeviceGray：0＝全黑＝單 K 100%（灰階照片走單 K，§9）。"""
    assert image_max_tac(Image.new("L", (2, 2), 0)) == pytest.approx(100.0)


def test_image_max_tac_grayscale_white_is_zero():
    assert image_max_tac(Image.new("L", (2, 2), 255)) == pytest.approx(0.0)


def test_image_max_tac_takes_max_pixel_not_mean():
    """一枚重墨像素即超標：取最大值，不因大面積留白被平均稀釋。"""
    im = Image.new("CMYK", (10, 10), (0, 0, 0, 0))
    im.putpixel((5, 5), (255, 255, 255, 255))
    assert image_max_tac(im) == pytest.approx(400.0)


def test_image_max_tac_cmyk_sums_four_plates():
    im = Image.new("CMYK", (2, 2), (255, 0, 0, 128))
    assert image_max_tac(im) == pytest.approx((255 + 128) / 2.55)


def test_image_max_tac_rejects_unsupported_mode():
    with pytest.raises(ValueError):
        image_max_tac(Image.new("RGB", (2, 2), (10, 20, 30)))


# ---------- tac_warnings 彙整 ----------

def _use(tac, kind="著色", label="k 0 0 0 0.92"):
    return InkUse(kind=kind, label=label, tac=tac)


def test_warnings_empty_when_within_limit():
    assert tac_warnings([_use(92.0), _use(100.0)]) == []


def test_warnings_list_over_limit_with_numbers():
    w = tac_warnings([_use(349.5, label="自擬富黑")])
    assert len(w) == 1
    assert "自擬富黑" in w[0] and "350" in w[0] and "320" in w[0]


def test_warnings_respects_custom_threshold():
    assert tac_warnings([_use(338.0)], max_tac=340.0) == []
    assert tac_warnings([_use(338.0)], max_tac=320.0) != []


def test_warnings_empty_input():
    assert tac_warnings([]) == []


# ---------- 匯出整合（producer 側） ----------

def test_export_default_output_within_limit(tmp_path, template):
    """預設輸出（內文單 K92）零 TAC 警告，且確實記錄了用到的著色。"""
    result = export_pdf(_text_doc(), template, tmp_path / "plain.pdf", footer=False)
    assert list(result.tac_warnings) == []
    assert result.ink_uses
    assert max(u.tac for u in result.ink_uses) <= MAX_TAC


def test_export_flags_rich_black_swatch(tmp_path, rich_black_template):
    result = export_pdf(_text_doc(), rich_black_template, tmp_path / "rich.pdf",
                        footer=False)
    assert len(result.tac_warnings) == 1
    assert "350" in result.tac_warnings[0]
    assert max(u.tac for u in result.ink_uses) == pytest.approx(349.5)


def test_export_flags_cmyk_image_over_limit(tmp_path, template):
    _make_cmyk(tmp_path / "heavy.tif", (240, 230, 220, 210))  # TAC 352.9%
    result = export_pdf(_figure_doc("heavy.tif"), template, tmp_path / "heavy.pdf",
                        footer=False, image_base_dir=tmp_path)
    warnings = [w for w in result.tac_warnings if "heavy.tif" in w]
    assert len(warnings) == 1
    image_uses = [u for u in result.ink_uses if u.kind == "影像"]
    assert image_uses[0].tac == pytest.approx((240 + 230 + 220 + 210) / 2.55)


def test_export_grayscale_image_never_over_limit(tmp_path, template):
    _make_gray(tmp_path / "gray.png", darkest=0)
    result = export_pdf(_figure_doc("gray.png"), template, tmp_path / "gray.pdf",
                        footer=False, image_base_dir=tmp_path)
    image_uses = [u for u in result.ink_uses if u.kind == "影像"]
    assert image_uses[0].tac == pytest.approx(100.0)  # 單 K 上限
    assert list(result.tac_warnings) == []


def test_export_does_not_block_on_over_limit(tmp_path, template):
    """超標只警告不擋流程（同 Sprint 84 授權／91 解析度慣例）：PDF 仍寫出且合規。"""
    _make_cmyk(tmp_path / "heavy.tif", (255, 255, 255, 255))
    out = tmp_path / "heavy.pdf"
    result = export_pdf(_figure_doc("heavy.tif"), template, out, footer=False,
                        image_base_dir=tmp_path)
    assert out.exists() and result.page_count >= 1
    assert result.tac_warnings


# ---------- preflight 獨立檢查（verifier 側，PyMuPDF） ----------

def test_check_ink_coverage_passes_default_output(tmp_path, template):
    out = tmp_path / "plain.pdf"
    export_pdf(_text_doc(), template, out, footer=False)
    report = check_ink_coverage(out)
    assert isinstance(report, InkCoverageReport)
    assert report.ok is True
    assert report.findings                      # 至少驗到內文著色
    assert "皆在" in ink_coverage_summary(report)


def test_check_ink_coverage_flags_rich_black(tmp_path, rich_black_template):
    out = tmp_path / "rich.pdf"
    export_pdf(_text_doc(), rich_black_template, out, footer=False)
    report = check_ink_coverage(out)
    assert report.ok is False
    over = [f for f in report.findings if not f.ok]
    assert len(over) == 1 and over[0].kind == "著色"
    assert over[0].tac == pytest.approx(349.5, abs=0.05)
    assert "超標" in ink_coverage_summary(report)


def test_check_ink_coverage_flags_cmyk_image(tmp_path, template):
    _make_cmyk(tmp_path / "heavy.tif", (240, 230, 220, 210))
    out = tmp_path / "heavy.pdf"
    export_pdf(_figure_doc("heavy.tif"), template, out, footer=False,
               image_base_dir=tmp_path)
    report = check_ink_coverage(out)
    image_findings = [f for f in report.findings if f.kind == "影像"]
    assert len(image_findings) == 1
    assert image_findings[0].ok is False
    assert image_findings[0].tac == pytest.approx((240 + 230 + 220 + 210) / 2.55, abs=0.5)


def test_check_ink_coverage_custom_threshold(tmp_path, rich_black_template):
    out = tmp_path / "rich.pdf"
    export_pdf(_text_doc(), rich_black_template, out, footer=False)
    assert check_ink_coverage(out, max_tac=320.0).ok is False
    assert check_ink_coverage(out, max_tac=360.0).ok is True


def test_check_ink_coverage_reads_pdf_not_source(tmp_path, template):
    """驗證側只讀 PDF：來源圖檔刪除後仍可檢查（無隱性依賴產出側狀態）。"""
    img = _make_cmyk(tmp_path / "gone.tif", (255, 255, 255, 255))
    out = tmp_path / "gone.pdf"
    export_pdf(_figure_doc("gone.tif"), template, out, footer=False,
               image_base_dir=tmp_path)
    Path(img).unlink()
    report = check_ink_coverage(out)
    assert [f for f in report.findings if f.kind == "影像" and not f.ok]
    with fitz.open(out) as d:                   # 影像確實在 PDF 內（獨立確認）
        assert len(d.get_page_images(0)) == 1


def test_check_ink_coverage_survives_malformed_numbers(tmp_path, template):
    """外來 PDF 為系統邊界：內容流出現非數值符記時跳過該處，不整份檢查崩潰。"""
    out = tmp_path / "plain.pdf"
    export_pdf(_text_doc(), template, out, footer=False)
    raw = out.read_bytes().replace(b"0 0 0 0.92 k", b"1.2.3 0 0 0.92 k", 1)
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(raw)
    report = check_ink_coverage(bad)          # 不拋例外
    assert all(f.tac <= 400.0 for f in report.findings)


def test_producer_and_verifier_agree(tmp_path, template):
    """Gate 4：產出側（來源像素／色值）與驗證側（PDF 反算）最大 TAC 同值。"""
    _make_cmyk(tmp_path / "x.tif", (200, 180, 160, 140))
    out = tmp_path / "x.pdf"
    result = export_pdf(_figure_doc("x.tif"), template, out, footer=False,
                        image_base_dir=tmp_path)
    report = check_ink_coverage(out)
    assert max(u.tac for u in result.ink_uses) == pytest.approx(
        max(f.tac for f in report.findings), abs=0.5)


# ---------- 規則集分離與誠實聲明 ----------

def test_xpdfx_rule_set_unchanged_by_high_tac(tmp_path, rich_black_template):
    """TAC 非 ISO 15930-1 條款：超墨量不使 X-1a 規則集不過，規則數維持 12。"""
    out = tmp_path / "rich.pdf"
    export_pdf(_text_doc(), rich_black_template, out, footer=False)
    report = check_pdfx1a(out)
    assert len(report.findings) == 12
    assert report.ok is True


def test_not_covered_points_to_ink_checker(tmp_path, template):
    out = tmp_path / "plain.pdf"
    export_pdf(_text_doc(), template, out, footer=False)
    entries = [e for e in check_pdfx1a(out).not_covered if "TAC" in e]
    assert len(entries) == 1
    assert "check_ink_coverage" in entries[0]


def test_cli_export_prints_tac_warning(tmp_path, capsys):
    from cjkfolio.cli import main
    _make_cmyk(tmp_path / "heavy.tif", (255, 255, 255, 255))
    docp = tmp_path / "d.json"
    docp.write_text(json.dumps({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "CLI 墨量", "template": "neizai-zhengli", "master": G_MASTER},
        "paragraphs": [{"text": "整理前後對照", "style": "圖說-辰宇落雁"}],
        "images": [{"path": "heavy.tif", "page": 1}],
    }, ensure_ascii=False), encoding="utf-8")
    rc = main(["export-pdf", str(docp), "-o", str(tmp_path / "cli.pdf"),
               "--template", str(ROOT / "templates" / "neizai-zhengli.json"),
               "--no-footer"])
    assert rc == 0                                    # 不擋流程
    out = capsys.readouterr().out
    assert "油墨總量" in out and "heavy.tif" in out and "320" in out


def test_cli_preflight_prints_ink_section(tmp_path, template, capsys):
    from cjkfolio.cli import main
    out_pdf = tmp_path / "plain.pdf"
    export_pdf(_text_doc(), template, out_pdf, footer=False)
    assert main(["preflight", str(out_pdf)]) == 0
    printed = capsys.readouterr().out
    assert "油墨總量（§9，非 X-1a 條款）" in printed
    capsys.readouterr()
    # 門檻壓到內文 K92 以下：墨量區報超標，X-1a 結論仍通過（退出碼依 X-1a）
    assert main(["preflight", str(out_pdf), "--max-tac", "50"]) == 0
    printed = capsys.readouterr().out
    assert "超標" in printed and "全數通過（12/12）" in printed
