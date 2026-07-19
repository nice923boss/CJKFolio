"""長書驗收工具的可用性與正確性（tools/measure_long_book.py，Sprint 110）。

**不驗時間與記憶體數字**：兩者隨機器而異，斷言任何毫秒或 MB 值都會變成跨機器的
假失敗（同 test_performance_tool.py 的立場）。本檔驗的是工具邏輯：預設值由模版
推導、章序不被猜測、清單結構正確、記憶體取數的語意（歷史最大值、不可得時據實回
None 而非以 tracemalloc 頂替），以及**工具不得內含任何書稿路徑**（GAPS #63 紅線：
未出版私人書稿不入 repo）。

長書驗收本身的數字記於 PLAN §6 Sprint 110 進度條與 GAPS #65，重跑指令見工具 docstring。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cjkfolio.book import load_book  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402

import measure_long_book as mlb  # noqa: E402

TEMPLATE_PATH = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"
needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE_PATH)


@pytest.fixture
def chapters(tmp_path):
    """兩章自撰 txt（章標題行在首段，其後兩段內文）。"""
    made = []
    for i, title in enumerate(("第一章　起點", "第二章　轉折"), start=1):
        p = tmp_path / f"ch{i}.txt"
        p.write_text(f"{title}\n\n第一段的內文。\n\n第二段的內文。\n", encoding="utf-8")
        made.append(p)
    return made


def _args(**over):
    base = dict(title="測試長書", template_id="neizai-zhengli",
                heading_style=None, toc_heading=None, toc_heading_style=None,
                toc_entry_style=None, toc_master=None, first_page=1, dpi=150,
                skip_render=True)
    base.update(over)
    return SimpleNamespace(**base)


# --- 紅線：工具不得內含書稿路徑 ---

def test_tool_contains_no_manuscript_path():
    """工具原始碼不得出現任何本機書稿路徑或書名（素材一律由呼叫端顯式指定）。

    GAPS #63：未出版私人書稿不入 repo、不進 git。工具若內建路徑，等於把它寫進版本
    控制。此測試釘死「素材外置」這件事，不是風格檢查。
    """
    src = (ROOT / "tools" / "measure_long_book.py").read_text(encoding="utf-8")
    assert "成名之路" not in src
    assert "Documents" not in src
    assert "C:\\Users" not in src and "C:/Users" not in src


# --- 記憶體取數的語意 ---

def test_peak_working_set_is_monotonic_or_none():
    """回正整數（Windows）或 None（取不到）；是歷史最大值故單調不減。"""
    first = mlb.peak_working_set()
    if first is None:
        assert not sys.platform.startswith("win")
        return
    assert isinstance(first, int) and first > 0
    blob = bytearray(64 * 1024 * 1024)  # 推高一次
    second = mlb.peak_working_set()
    del blob
    third = mlb.peak_working_set()
    assert second >= first
    assert third >= second, "peak 是歷史最大值，釋放記憶體後不得下降"


def test_fmt_mb_reports_unavailable_rather_than_substituting():
    """取不到時據實回「不可得」，不以其他來源的數字頂替。"""
    assert mlb._fmt_mb(None) == "不可得"
    assert mlb._fmt_mb(1024 * 1024) == "1.0MB"


# --- 兩趟量測的分工 ---

def test_timed_step_does_not_trace_memory():
    """純計時趟不開 tracemalloc（開了會讓耗時失真 5.8 倍）。"""
    out, rec = mlb.timed_step("測試", lambda: sum(range(1000)))
    assert out == sum(range(1000))
    assert rec["Python峰值"] is None, "計時趟不得回報記憶體（表示 tracemalloc 被開了）"
    assert rec["耗時"] >= 0 and rec["工序"] == "測試"


def test_traced_step_reports_python_peak():
    """記憶體趟回報該工序自己的 Python 端峰值（每道重新開停）。"""
    out, rec = mlb.traced_step("測試", lambda: bytearray(4 * 1024 * 1024))
    assert len(out) == 4 * 1024 * 1024
    assert rec["Python峰值"] >= 4 * 1024 * 1024


# --- 匯入與清單 ---

def test_chapter_documents_derives_defaults_from_template(template, chapters):
    """預設值全由模版推導（走 Sprint 107 的 import_manuscript，與編輯器同源）。"""
    docs = mlb.chapter_documents(chapters, template, "neizai-zhengli", None)
    assert len(docs) == 2
    for doc in docs:
        assert doc.master == template.default_master
        assert doc.template == "neizai-zhengli"
        assert {p.style for p in doc.paragraphs} == {template.md_mapping["paragraph"]}


def test_heading_style_applies_to_first_paragraph_only(template, chapters):
    docs = mlb.chapter_documents(chapters, template, "neizai-zhengli", "章名大標-明體W7")
    body = template.md_mapping["paragraph"]
    for doc in docs:
        assert doc.paragraphs[0].style == "章名大標-明體W7"
        assert {p.style for p in doc.paragraphs[1:]} == {body}


def test_empty_chapter_fails_fast(template, tmp_path):
    """空章檔快速失敗，不默默產出零段文件。"""
    empty = tmp_path / "空.txt"
    empty.write_text("\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="無任何段落"):
        mlb.chapter_documents([empty], template, "neizai-zhengli", None)


def test_manifest_order_follows_caller_not_filename(template, tmp_path):
    """章序取呼叫端給的順序，工具不依檔名排序（檔名排序會把「第十章」排到「第二章」前）。"""
    names = ["乙.txt", "甲.txt"]  # 刻意逆字典序
    paths = []
    for n in names:
        p = tmp_path / n
        p.write_text(f"{n} 的標題\n\n內文。\n", encoding="utf-8")
        paths.append(p)
    docs = mlb.chapter_documents(paths, template, "neizai-zhengli", None)
    out = tmp_path / "out"
    out.mkdir()
    manifest = mlb.write_manifest(docs, out, _args(toc_heading="目次",
                                                   toc_heading_style="目錄-部名",
                                                   toc_entry_style="目錄-篇章條目",
                                                   toc_master="D-目錄"))
    book = load_book(manifest)
    titles = [c.toc_title for c in book.chapters if c.toc_title]
    assert titles == ["乙.txt 的標題", "甲.txt 的標題"], "章序未依呼叫端給的順序"


def test_manifest_without_toc_has_no_generate_toc(template, chapters, tmp_path):
    """不給 --toc-heading 就不產目錄章（也不掛 toc_title）。"""
    docs = mlb.chapter_documents(chapters, template, "neizai-zhengli", None)
    out = tmp_path / "out"
    out.mkdir()
    book = load_book(mlb.write_manifest(docs, out, _args()))
    assert all(c.toc_spec is None for c in book.chapters)
    assert all(c.toc_title is None for c in book.chapters)
    assert len(book.chapters) == 2


# --- 端到端 ---

@needs_fonts
def test_pipeline_runs_end_to_end_and_passes_preflight(template, chapters, tmp_path):
    """完整鏈跑得完且 X-1a 通過（驗工具真的走完管線，不是印表格而已）。"""
    out = tmp_path / "out"
    out.mkdir()
    args = _args(heading_style="章名大標-明體W7", toc_heading="目次",
                 toc_heading_style="目錄-部名", toc_entry_style="目錄-篇章條目",
                 toc_master="D-目錄")
    steps, doc, result, reports, pdf = mlb.run_pipeline(
        chapters, template, args, out, mlb.timed_step)

    assert [s["工序"] for s in steps] == [
        "匯入（逐章）", "落檔＋清單", "組裝＋自動目錄", "排版", "匯出 PDF", "機械 preflight"]
    # 2 章各 3 段 ＋ 目錄標題 1 ＋ 目錄條目 2
    assert len(doc.paragraphs) == 2 * 3 + 1 + 2
    assert len(result.pages) >= 1
    assert result.violations == [], f"禁則違規：{result.violations}"
    assert reports[0].ok, "X-1a 機械檢查未通過"
    assert pdf.exists() and pdf.stat().st_size > 0


@needs_fonts
def test_render_step_included_when_not_skipped(template, chapters, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    steps = mlb.run_pipeline(chapters, template, _args(skip_render=False),
                             out, mlb.timed_step)[0]
    assert "渲染 PNG" in [s["工序"] for s in steps]
    assert list((out / "png").glob("*.png")), "渲染未產出 PNG"


@needs_fonts
def test_pipeline_without_toc_uses_plain_assembly(template, chapters, tmp_path):
    """不給 --toc-heading 時走純 path 組裝，不得因缺 generate_toc 章而失敗。

    `assemble_book_with_toc` 要求書冊含 generate_toc 章，故恆走該入口會讓「不產
    目錄」這個本就支援的形態直接炸掉（本測試在修正前確實 RED）。
    """
    out = tmp_path / "out"
    out.mkdir()
    steps, doc, result, reports, pdf = mlb.run_pipeline(
        chapters, template, _args(), out, mlb.timed_step)
    assert "組裝" in [s["工序"] for s in steps]
    assert "組裝＋自動目錄" not in [s["工序"] for s in steps]
    assert len(doc.paragraphs) == 2 * 3, "純組裝不應多出目錄段"
    assert result.violations == []
    assert reports[0].ok
