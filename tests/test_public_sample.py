"""公開章節素材（samples/paiban-xiaoji-ch1.md，Sprint 96）端到端測試。

GAPS #1 的「公開測試素材須另備自由散布文本」：真書《內在整理》為版權物僅限
本機，本素材為自撰原創（可隨 repo 散布），作為公開的章節級端到端驗證來源。

覆蓋：md 匯入樣式對映、排版頁數與禁則 0 違規、匯出 PDF/X-1a 機械檢查全過、
繁中標點紅線（無破折號）、素材確實涵蓋縱中橫兩形態（逐字正立與整串旋轉）。
頁數與段數為現況釘死值：素材若改寫，本檔會失敗以提醒同步更新 samples/README。
"""
from pathlib import Path

import pytest

from cjkfolio.engine import Cell
from cjkfolio.layout import layout_document
from cjkfolio.md_import import import_markdown_file
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import check_pdfx
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "paiban-xiaoji-ch1.md"
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


@pytest.fixture(scope="module")
def document(template):
    return import_markdown_file(SAMPLE, template.md_mapping,
                                inline_mapping=template.md_inline_mapping,
                                title="排版小記")


@pytest.fixture(scope="module")
def layout(document, template):
    return layout_document(document, template)


def test_sample_file_is_tracked_and_non_empty():
    assert SAMPLE.exists(), "公開素材缺檔（GAPS #1 的替代文本）"
    assert len(SAMPLE.read_text(encoding="utf-8")) > 2000


def test_sample_has_no_em_dash():
    """繁中標點紅線：破折號一律不用（逗號、冒號、括號替代）。"""
    assert "—" not in SAMPLE.read_text(encoding="utf-8")


def test_import_maps_headings_to_template_styles(document, template):
    assert len(document.paragraphs) == 41
    assert document.paragraphs[0].style == "章名大標-明體W7"
    used = {p.style for p in document.paragraphs}
    assert used == {"章名大標-明體W7", "章節小標-黑體", "引文-仿宋語錄", "內文-明體直排"}
    assert used <= set(template.paragraph_styles), "素材用到模版沒有的段落樣式"


def test_layout_pages_and_no_prohibition_violations(layout):
    assert len(layout.pages) == 11
    assert layout.violations == []
    assert layout.justify_stats["beyond"] == 0


def test_sample_covers_both_tcy_forms(layout):
    """素材須同時涵蓋逐字正立（全大寫縮寫）與整串旋轉（含小寫西文）。

    兩形態為 Sprint 88 縱中橫的兩條規則，公開素材若失去任一形態，
    端到端驗證就不再涵蓋該路徑，故在此釘死。
    """
    cells = [c for page in layout.pages for pl in page.placed
             for c in pl.line.cells if isinstance(c, Cell)]
    upright = {c.text for c in cells if c.kind == "tcy"}
    rotated = {c.text for c in cells if c.kind == "latin"}
    assert {"C", "M", "Y", "K"} <= upright, "缺全大寫縮寫的逐字正立樣本"
    assert any(any(ch.islower() for ch in t) for t in rotated), "缺含小寫西文的旋轉樣本"


def test_export_passes_pdfx1a_mechanical_preflight(document, template, tmp_path):
    out = tmp_path / "public-chapter.pdf"
    result = export_pdf(document, template, out)
    assert out.exists()
    assert result.page_count == 11
    report = check_pdfx(out)
    failed = [f.rule for f in report.findings if not f.ok]
    assert failed == [], f"preflight 不過：{failed}"
    assert len(report.findings) == 12
    assert report.ok
