"""效能量測工具的可用性（tools/measure_performance.py，Sprint 106）。

**不驗時間數字**：耗時隨機器而異，斷言任何毫秒值都會變成跨機器的假失敗。本檔
驗的是工具本身可跑、放大邏輯正確、量到的是真東西（頁數確實隨倍數成長）。

基線數字記於 PLAN §6 Sprint 106 進度條與 GAPS #60，重跑指令見工具 docstring。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cjkfolio.md_import import import_markdown_file  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402

import measure_performance as mp  # noqa: E402

FONT_DIR = ROOT / "assets" / "fonts"
needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


@pytest.fixture(scope="module")
def base_doc():
    template = load_template(mp.TEMPLATE)
    doc = import_markdown_file(mp.SAMPLE, mapping=template.md_mapping,
                               inline_mapping=template.md_inline_mapping,
                               title="排版小記",
                               template_id="neizai-zhengli",
                               master=template.default_master)
    return doc, template


def test_sample_and_template_are_repo_local():
    """素材與模版都在 repo 內（任何人可原樣重現，不需參考書）。"""
    assert mp.SAMPLE.exists() and mp.SAMPLE.parent.name == "samples"
    assert mp.TEMPLATE.exists() and mp.TEMPLATE.parent.name == "templates"


def test_scaled_document_repeats_paragraphs(base_doc):
    """放大＝段落序列整數倍重複，內容與順序皆保留（非隨機生成）。"""
    doc, _ = base_doc
    n = len(doc.paragraphs)
    scaled = mp.scaled_document(doc, 4)
    assert len(scaled.paragraphs) == 4 * n
    assert scaled.paragraphs[:n] == doc.paragraphs
    assert scaled.paragraphs[n:2 * n] == doc.paragraphs
    assert scaled.title == doc.title and scaled.template == doc.template


def test_scaled_document_identity_at_one(base_doc):
    doc, _ = base_doc
    assert mp.scaled_document(doc, 1).paragraphs == doc.paragraphs


def test_timed_returns_median_and_last_value():
    """timed 取中位數（不受單次離群值左右），並回傳最後一次的結果。"""
    calls = []

    def work():
        calls.append(len(calls))
        return calls[-1]

    seconds, value = mp.timed(work, repeats=5)
    assert len(calls) == 5 and value == 4
    assert seconds >= 0


def test_fmt_switches_unit_at_one_second():
    assert mp._fmt(None) == "略過"
    assert mp._fmt(0.006).endswith("ms")
    assert mp._fmt(1.7).endswith("s") and "ms" not in mp._fmt(1.7)


@needs_fonts
def test_measure_scale_layout_only_grows_with_scale(base_doc):
    """量到的是真東西：頁數隨倍數成長，且 layout_only 不跑後三道工序。"""
    doc, template = base_doc
    small = mp.measure_scale(doc, template, 1, skip_render=True, repeats=1,
                             layout_only=True)
    big = mp.measure_scale(doc, template, 4, skip_render=True, repeats=1,
                           layout_only=True)
    assert small["頁數"] >= 1
    assert big["頁數"] > small["頁數"]
    assert big["段數"] == 4 * small["段數"]
    assert small["排版"] > 0
    for key in ("渲染", "匯出", "preflight"):
        assert small[key] is None, f"layout_only 不應跑 {key}"
    assert small["X-1a"] == "未跑"


@needs_fonts
def test_measure_scale_full_pass_runs_preflight(base_doc):
    """完整一輪會真的匯出 PDF 並跑 preflight，且結論為通過。"""
    doc, template = base_doc
    row = mp.measure_scale(doc, template, 1, skip_render=True, repeats=1)
    assert row["渲染"] is None       # skip_render
    assert row["匯出"] > 0 and row["preflight"] > 0
    assert row["PDF大小"] > 0
    assert row["X-1a"] == "通過"
