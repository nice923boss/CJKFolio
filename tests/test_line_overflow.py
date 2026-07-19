"""行內容溢出行容量的偵測（Sprint 111，關 GAPS #66 的正確性子項）。

**這條缺陷不是 URL 專屬的**：任何寬於整行容量的單一 cell 都會觸發。斷行的病理
防護（`engine.py` `_break_one_line` 末段「強制收一字避免死循環」）在貪婪迴圈收不到
任何 cell 時強制收一枚並**立即 return**，故：

  1. 該枚可能寬於 cap，行內容因此溢出版心，而在此之前**沒有任何機制回報它**；
  2. 強制收字產生的行邊界不再經禁則解消迴圈。

一手實測（Sprint 111）：80 字元拉丁串（width=40）排進 cap=30 的欄，得 used=40 的行，
超出 10 槽＝**120.8pt**（以內文字距 12.08pt 計，約 42.6mm），且 `check_kinsoku` 只
驗行首行尾字元、不驗寬度，故整份 layout 的 violations 對此完全沉默。

本次處置是**不沉默**（同 Sprint 109 對 TAC 400% 的立場：據實回報、不擋流程），
不改斷行行為：斷行策略的改動需要 R1 證據，而溢出的「回報」不需要。
"""
import pytest

from cjkfolio.engine import Cell, break_cells, check_overflow
from cjkfolio.layout import layout_document
from cjkfolio.document import Document, Paragraph
from cjkfolio.styles import load_template

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


# --- 純函式 ---

def test_overflow_reported_with_used_cap_and_excess():
    """超寬 cell 撐爆行時據實回報，訊息含行號、最寬 cell、容量、超出量。"""
    lines = break_cells([Cell("x" * 80, "latin", 40), Cell("。", "cjk", 1)], 30, indent=0)
    violations = check_overflow(lines)
    assert violations, "超寬 cell 撐爆行卻未回報（沉默溢出版心）"
    msg = violations[0]
    assert "溢出" in msg
    assert "40" in msg and "30" in msg, f"訊息未含最寬 cell 與容量：{msg}"


def test_kinsoku_squeeze_is_not_reported_as_overflow():
    """行首禁則的擠入（GAPS #9 設計行為）使 used > cap，但不是溢出，不得回報。

    判準若寫成 used > cap，這條會 RED：擠入本就刻意讓句逗掛出行尾。實測初版判準在
    samples/paiban-xiaoji-ch1.md 上產生 11 筆此類假違規。
    """
    # 末尾連續句逗會被擠入前一行，使該行 used 超過 cap 而最寬 cell 仍為 1 槽
    cells = [Cell(c, "cjk", 1) for c in "一二三四五六七八九十"] + [
        Cell("。", "cjk", 1), Cell("」", "cjk", 1)]
    lines = break_cells(cells, 10, indent=0)
    squeezed = [ln for ln in lines if sum(c.width for c in ln.cells) > ln.cap]
    assert squeezed, "測試前提不成立：未產生擠入行"
    assert all(max(c.width for c in ln.cells) <= ln.cap for ln in squeezed)
    assert check_overflow(lines) == [], "把合法的禁則擠入誤判為溢出"


def test_normal_lines_report_nothing():
    """正常斷行不得回報（避免假陽性淹沒真違規）。"""
    lines = break_cells([Cell(c, "cjk", 1) for c in "這是一段正常的中文內容用來確認不誤報"],
                        10, indent=2)
    assert check_overflow(lines) == []


def test_exactly_full_line_is_not_overflow():
    """used == cap 是滿行，合法，不得回報（邊界）。"""
    lines = break_cells([Cell(c, "cjk", 1) for c in "一二三四五"], 5, indent=0)
    assert all(sum(c.width for c in ln.cells) <= ln.cap for ln in lines)
    assert check_overflow(lines) == []


def test_unknown_capacity_is_not_reported():
    """cap <= 0＝容量未知（同 line_justified_advance 的立場），不得據此判溢出。"""
    lines = [type(break_cells([Cell("甲", "cjk", 1)], 5, indent=0)[0])(
        cells=(Cell("x" * 20, "latin", 10),), start_slot=0, cap=0, para_end=True)]
    assert check_overflow(lines) == []


def test_reports_every_overflowing_line_not_just_first():
    """多行溢出時逐行回報（只報第一行會讓後續問題隱形）。"""
    cells = [Cell("x" * 80, "latin", 40), Cell("y" * 80, "latin", 40)]
    lines = break_cells(cells, 30, indent=0)
    assert len(check_overflow(lines)) == 2


# --- 端到端：layout 的 violations 必須涵蓋 ---

def test_layout_surfaces_overflow_in_violations(template):
    """整份 layout 的 violations 要含溢出（此前完全沉默，是本次修正的核心）。"""
    long_latin = "x" * 200  # width=100，遠寬於內文欄容量
    doc = Document(title="溢出測試", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(f"前置文字{long_latin}後續文字。",
                                         "內文-明體直排"),))
    result = layout_document(doc, template)
    assert any("溢出" in v for v in result.violations), \
        f"layout 未回報溢出，violations={result.violations}"


def test_clean_document_has_no_violations(template):
    """一般內容零回歸：不得因新增檢查而冒出假違規。"""
    doc = Document(title="正常", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph("這是一段完全正常的中文內文，用來確認新增的"
                                         "溢出檢查不會產生假陽性違規。", "內文-明體直排"),))
    result = layout_document(doc, template)
    assert result.violations == []


def test_frame_path_also_reports_overflow(template):
    """文字框路徑同樣涵蓋（Gate 3 同類掃描：既有檢查只驗欄數，不驗單行寬度）。"""
    from cjkfolio.document import TextFrame
    from cjkfolio.frames import layout_text_frame

    frame = TextFrame(page=1, style="內文-明體直排", text="前置" + "x" * 200 + "後續",
                      rect=(100.0, 100.0, 60.0, 200.0))
    placed = layout_text_frame(frame, template, template.masters["A-內文版"].grid)
    assert any("溢出" in v for v in placed.violations), \
        f"文字框路徑未回報單行溢出，violations={placed.violations}"
    assert any("文字框" in v for v in placed.violations), "訊息未標明是文字框"


def test_public_sample_still_clean(template):
    """repo 內可散布素材（自撰原創）仍須零違規，這是跨機器可重現的回歸守門。"""
    from cjkfolio.md_import import import_markdown_file
    sample = ROOT / "samples" / "paiban-xiaoji-ch1.md"
    doc = import_markdown_file(sample, mapping=template.md_mapping,
                               inline_mapping=template.md_inline_mapping,
                               title="排版小記", template_id="neizai-zhengli",
                               master=template.default_master)
    result = layout_document(doc, template)
    assert result.violations == []
