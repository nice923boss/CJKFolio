"""group／jukugo ruby（Sprint 134，GAPS #46 (a)）：多字 base 的 ruby 標注。

v1（Sprint 86）只做 mono-ruby 單字 base，因為當時**沒有帶 ruby 的真實稿件**
（Sprint 110 Gate 0 據此判定啟動條件不成立而順延）。本輪 Owner 授權上網搜尋，
素材缺口由**青空文庫**補上：日本公有領域文學電子圖書館，文本保留原書排印的
振り仮名，正是 jukugo ruby（熟語ルビ）的真實出版用例。繁中注音實務幾乎全是
mono-ruby（v1 已涵蓋），group ruby 的真實用例本就在日文，故取此素材。

三件 v1 沒有而 group ruby 必須有的事：
  1. 跨 cell 置中：ruby 在整個 base 群組範圍上置中，不是單字上。
  2. 群組不可拆行：base 被斷行切開時 ruby 無處可放，故整組退到下一行。
  3. ruby 驅動 base 間距：ruby 比 base 長時（「蟋蟀《きりぎりす》」2 字配 5 假名）
     若不加寬 base，ruby 會壓到相鄰欄的字（v1 GAPS #46 (c) 登記的溢出）。
"""
import pytest

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.engine import break_cells, cells_from_runs
from cjkfolio.placement import RUBY_SIZE_RATIO, group_ruby_axis_and_top

BODY = "內文-明體直排"


def runs_of(*items):
    """((text, char_style, ruby), ...) 便利建構。"""
    return tuple((t, None, r) for t, r in items)


# ---- 1. 模型：多字 base 的 ruby ----

def test_多字base的ruby可解析與序列化():
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "t", "template": "x", "master": "A-內文版"},
        "paragraphs": [{"style": BODY, "runs": [
            {"text": "羅生門", "ruby": "らしょうもん"},
            {"text": "の下で"},
        ]}],
    })
    run = doc.paragraphs[0].runs[0]
    assert run.text == "羅生門" and run.ruby == "らしょうもん"
    again = document_from_dict(document_to_dict(doc))
    assert again.paragraphs[0].runs[0].ruby == "らしょうもん"


def test_ruby仍須為非空字串():
    with pytest.raises(DocumentError, match="ruby"):
        document_from_dict({
            "schema": "cjkfolio/document@2",
            "meta": {"title": "t", "template": "x", "master": "A-內文版"},
            "paragraphs": [{"style": BODY, "runs": [
                {"text": "羅生門", "ruby": ""}]}],
        })


def test_ruby的base不得為空():
    """空 base 無處可掛 ruby（v1 的『須恰為單一字』放寬後仍要守住這條）。"""
    with pytest.raises(DocumentError, match="ruby"):
        document_from_dict({
            "schema": "cjkfolio/document@2",
            "meta": {"title": "t", "template": "x", "master": "A-內文版"},
            "paragraphs": [{"style": BODY, "runs": [
                {"text": "", "ruby": "らしょうもん"}]}],
        })


# ---- 2. engine：群組成形 ----

def test_多字base成為一個ruby群組():
    cells = cells_from_runs(runs_of(("羅生門", "らしょうもん"), ("の下", None)))
    assert cells[0].ruby == "らしょうもん"
    assert cells[0].ruby_span == 3      # 群組含 3 個 base cell
    assert [c.ruby for c in cells[1:3]] == [None, None]  # ruby 只掛群組首
    assert all(c.ruby_span == 0 for c in cells[1:])      # span 只掛群組首
    assert [c.text for c in cells[:3]] == ["羅", "生", "門"]


def test_單字base維持v1行為():
    """mono-ruby 是 group ruby 的特例（span=1），既有樣張與測試不得退步。"""
    cells = cells_from_runs(runs_of(("災", "わざわい"), ("がつづく", None)))
    assert cells[0].ruby == "わざわい" and cells[0].ruby_span == 1


# ---- 3. ruby 驅動 base 間距 ----

def test_ruby較短時base維持整數槽():
    """「羅生門」3 字配 6 假名：6×0.5＝3 單位 ≤ 3 字，base 不必加寬。"""
    cells = cells_from_runs(runs_of(("羅生門", "らしょうもん"), ))
    assert [c.width for c in cells[:3]] == [1, 1, 1]


def test_ruby較長時base等分加寬():
    """「蟋蟀」2 字配 5 假名：5×0.5＝2.5 單位 > 2 字，每字加寬到 1.25 槽，
    使 ruby 排得下而不壓到相鄰欄（v1 GAPS #46 (c) 的溢出即此處）。"""
    cells = cells_from_runs(runs_of(("蟋蟀", "きりぎりす"), ))
    need = len("きりぎりす") * RUBY_SIZE_RATIO
    assert need == pytest.approx(2.5)
    assert [c.width for c in cells[:2]] == [pytest.approx(1.25)] * 2
    assert sum(c.width for c in cells[:2]) == pytest.approx(need)


def test_加寬只影響群組不外溢():
    cells = cells_from_runs(runs_of(("蟋蟀", "きりぎりす"), ("が一匹", None)))
    assert [c.width for c in cells[2:]] == [1, 1, 1]


# ---- 4. 群組不可拆行 ----

def test_群組不被斷行切開():
    """行尾容不下整組時整組退到下一行（切開則 ruby 無處可放）。"""
    cells = cells_from_runs(runs_of(
        ("あ" * 8, None), ("羅生門", "らしょうもん"), ("の下", None)))
    lines = break_cells(cells, chars_per_line=10, indent=0)
    first = "".join(c.text for c in lines[0].cells)
    assert first == "あ" * 8, f"群組被切開：{first!r}"
    second = "".join(c.text for c in lines[1].cells)
    assert second.startswith("羅生門"), second


def test_群組整組放得下就不退行():
    cells = cells_from_runs(runs_of(
        ("あ" * 7, None), ("羅生門", "らしょうもん"), ("の下", None)))
    lines = break_cells(cells, chars_per_line=10, indent=0)
    assert "".join(c.text for c in lines[0].cells) == "あ" * 7 + "羅生門"


def test_群組比整行還長時不無限退行():
    """病理情形（群組寬於行容量）：容許溢出並由既有 check_overflow 回報，
    不可陷入退行死循環。"""
    cells = cells_from_runs(runs_of(("羅生門大改造", "らしょうもんだいかいぞう"), ))
    lines = break_cells(cells, chars_per_line=4, indent=0)
    assert lines and "".join(c.text for c in lines[0].cells).startswith("羅")


# ---- 5. 幾何：跨 cell 置中 ----

def test_group_ruby在群組範圍置中():
    """ruby 串以群組整體高度置中；單字群組即退化為 v1 的 mono 幾何。"""
    axis, top, size = group_ruby_axis_and_top(
        base_axis_x_pt=100.0, group_top_pt=200.0, group_height_pt=36.0,
        base_size_pt=12.0, ruby_len=6)
    assert size == pytest.approx(6.0)                    # 12 × 0.5
    assert axis == pytest.approx(100.0 + 6.0 + 3.0)      # base 右半＋ruby 左半
    # 群組中心 218；ruby 串總高 6×6＝36 → 自 218−18＝200 起
    assert top == pytest.approx(200.0)


def test_單字群組幾何與v1一致():
    from cjkfolio.placement import ruby_axis_and_top

    v1 = ruby_axis_and_top(base_axis_x_pt=100.0, cell_top_pt=200.0,
                           base_advance_pt=12.08, base_size_pt=11.5, ruby_len=4)
    v2 = group_ruby_axis_and_top(base_axis_x_pt=100.0, group_top_pt=200.0,
                                 group_height_pt=12.08, base_size_pt=11.5,
                                 ruby_len=4)
    assert v2 == pytest.approx(v1)


# ---- 6. R5 真實素材：青空文庫《羅生門》開頭（公有領域） ----

def _sample_doc():
    from pathlib import Path

    from cjkfolio.document import load_document

    root = Path(__file__).resolve().parents[1]
    return load_document(root / "samples" / "rashomon-opening.doc.json")


def test_真實素材含足量的多字base用例():
    """素材腐爛守門：改寫樣張須同步更新 samples/README.md 的說明。"""
    doc = _sample_doc()
    assert len(doc.paragraphs) == 12
    groups = [(r.text, r.ruby) for p in doc.paragraphs for r in p.runs if r.ruby]
    multi = [g for g in groups if len(g[0]) > 1]
    assert len(groups) == 68 and len(multi) == 40
    assert ("朱雀大路", "すざくおおじ") in multi   # 4 字 base
    assert ("蟋蟀", "きりぎりす") in multi         # ruby 長於 base（觸發加寬）


def test_真實素材排版零違規():
    from pathlib import Path

    from cjkfolio.layout import layout_document
    from cjkfolio.styles import load_template

    root = Path(__file__).resolve().parents[1]
    template = load_template(root / "templates" / "neizai-zhengli.json")
    result = layout_document(_sample_doc(), template)
    assert result.violations == []
    assert len(result.pages) == 8
    # 每個群組都完整落在同一行（不被斷行切開）
    for page in result.pages:
        for placed in page.placed:
            cells = placed.line.cells
            for i, c in enumerate(cells):
                if c.ruby_span:
                    assert i + c.ruby_span <= len(cells), \
                        f"群組被切開：{c.text}《{c.ruby}》"
