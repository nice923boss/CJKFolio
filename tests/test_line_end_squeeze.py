"""行尾閉括號縮末側（CLREQ WD-20150723 §3.1.6.2 規則 2，Sprint 116）。

證據：條文逐字（B 級）＝「當行尾出現結束括注符號時，可以縮減其末側二分之一個
漢字大小的空白」＋內建思源宋體 TC 與思源黑體 TC 各 8 枚閉括號的一手墨跡量測
（A 級，spikes/spike19-mojikumi-rest：縮 0.5 em 後切墨 0 筆、最小留白 0.520 em）。

同小節的規則 1（行首開括號縮始側）不在本 Sprint：現行擠壓模型只縮推進量、不位移
字形，規則 1 要縮的是字形之前的空白，需 `Cell` 新增字形偏移欄位並在兩後端加畫布
三處同步，成本不同級，另案（GAPS #69 (a)）。規則 3 條文明文限簡體中文，繁中排除。

本檔釘死的核心保證是**模型 A：行邊界完全不變**（省下的半格不回饋斷行容量），
以及開關兩版的斷行逐行相同，這是不取模型 B（迭代求不動點）換來的斷行確定性。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.engine import (
    SQUEEZE_CLOSERS,
    SQUEEZE_WIDTH,
    Cell,
    Line,
    ParagraphSpec,
    flow_pages,
    squeeze_line_end,
    tokenize,
)
from cjkfolio.layout import layout_document, line_justified_advance
from cjkfolio.styles import TemplateError, load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
SAMPLE_DOC = ROOT / "samples" / "line-end-squeeze.doc.json"
SAMPLE_TEMPLATE = ROOT / "samples" / "punct-squeeze.template.json"


def line_of(text: str, **kw) -> Line:
    cells = tokenize(text)
    return Line(tuple(cells), cap=kw.get("cap", len(cells)),
                para_end=kw.get("para_end", False))


def widths(line: Line):
    return [c.width for c in line.cells]


# --- 純函式：條文規則 ---

@pytest.mark.parametrize("closer", sorted(SQUEEZE_CLOSERS))
def test_line_ending_with_closer_squeezes_its_tail(closer):
    """規則 2：行尾閉括號讓出末側半形（字身框 1 → 0.5），其餘字格不動。"""
    out = squeeze_line_end(line_of("整理" + closer))
    assert widths(out) == [1, 1, SQUEEZE_WIDTH]


@pytest.mark.parametrize("tail", ["書", "。", "、", "「", "《"])
def test_line_ending_with_non_closer_untouched(tail):
    """條文只給行尾的「結束括注符號」，漢字、句逗、開括號皆不適用。"""
    assert widths(squeeze_line_end(line_of("整理" + tail))) == [1, 1, 1]


def test_already_squeezed_closer_not_squeezed_twice():
    """行尾閉括號若已由 §3.1.6.1（Sprint 90）讓出半形，不重複扣。"""
    cells = (Cell("書", "cjk"), Cell("」", "cjk", width=SQUEEZE_WIDTH))
    out = squeeze_line_end(Line(cells, cap=2))
    assert widths(out) == [1, SQUEEZE_WIDTH]


def test_latin_and_tcy_line_ends_not_squeezed():
    """西文旋轉串與縱中橫非閉括號，不參與（寬度維持既有推導）。"""
    assert widths(squeeze_line_end(line_of("書abc"))) == [1, 2]
    assert widths(squeeze_line_end(line_of("書12"))) == [1, 1]


def test_empty_line_is_returned_unchanged():
    """空行無末枚可縮（繞排全排除行槽會產生此形態）。"""
    line = Line((), cap=0)
    assert squeeze_line_end(line) is line


def test_squeeze_line_end_is_pure_and_preserves_everything_else():
    """純函式：原 Line 不被修改，且除末枚 width 外欄位全保真。"""
    line = Line(tuple(tokenize("整理」")), start_slot=2, cap=8, para_end=True)
    before = [(c.text, c.kind, c.span, c.width) for c in line.cells]
    out = squeeze_line_end(line)
    assert [(c.text, c.kind, c.span, c.width) for c in line.cells] == before
    assert (out.start_slot, out.cap, out.para_end) == (2, 8, True)
    assert [(c.text, c.kind, c.span) for c in out.cells] == [b[:3] for b in before]


# --- 流排整合（opt-in，模型 A） ---

def _spec(text: str, line_end: bool = False, punct: bool = False):
    return ParagraphSpec(text=text, indent=0, line_end_squeeze=line_end,
                         punct_squeeze=punct)


TWO_CLOSER_LINES = "他說「好」再看《書》結束"  # cap=5：前兩行行尾各一枚閉括號


def test_flow_pages_opt_in_default_off():
    """預設 line_end_squeeze=False：字寬與既有一致（既有輸出零變更的鐵律）。"""
    lines = [pl.line for pl in flow_pages([_spec(TWO_CLOSER_LINES)], 5, 10)[0]]
    assert [widths(ln) for ln in lines] == [[1] * 5, [1] * 5, [1, 1]]


def test_flow_pages_squeezes_only_the_closer_at_each_line_end():
    """開啟後每行末枚閉括號讓半形，行內其他閉括號不受本規則影響。"""
    lines = [pl.line for pl in
             flow_pages([_spec(TWO_CLOSER_LINES, line_end=True)], 5, 10)[0]]
    assert [widths(ln) for ln in lines] == [
        [1, 1, 1, 1, SQUEEZE_WIDTH], [1, 1, 1, 1, SQUEEZE_WIDTH], [1, 1]]


def test_line_breaking_is_identical_with_and_without_the_rule():
    """模型 A 核心保證：省下的半格不回饋容量，開關兩版斷行逐行完全相同。"""
    text = "她說「這是《內在整理》」而後停頓（很久）再開口說下去直到天亮"
    for cap in (4, 5, 7, 11, 16):
        off = flow_pages([_spec(text)], cap, 20)[0]
        on = flow_pages([_spec(text, line_end=True)], cap, 20)[0]
        assert ["".join(c.text for c in pl.line.cells) for pl in off] == \
               ["".join(c.text for c in pl.line.cells) for pl in on], f"cap={cap}"


def test_rule_applies_only_to_vertical():
    """量測依直排 vert 形墨跡（同 Sprint 90）：橫排字形位置不同，不套用。"""
    lines = flow_pages([_spec(TWO_CLOSER_LINES, line_end=True)], 5, 10,
                       vertical=False)[0]
    assert all(c.width == 1 for pl in lines for c in pl.line.cells)


def test_orthogonal_to_adjacent_punctuation_squeeze():
    """只開行尾規則時，行內相鄰約物（§3.1.6.1）維持全形，兩開關互不代理。"""
    lines = [pl.line for pl in
             flow_pages([_spec("「『書』」是", line_end=True)], 10, 10)[0]]
    assert widths(lines[0]) == [1, 1, 1, 1, 1, 1]


def test_both_rules_on_does_not_double_squeeze_the_same_cell():
    """兩規則同開：行尾閉括號若已被 §3.1.6.1 壓過，維持 0.5 不再扣。"""
    on_both = flow_pages([_spec("書」「整理", line_end=True, punct=True)], 3, 10)[0]
    first = on_both[0].line
    assert "".join(c.text for c in first.cells) == "書」"
    assert widths(first) == [1, SQUEEZE_WIDTH]


# --- 與齊行的互動（誠實面：命中行有一部分會被齊行分回） ---

def test_full_line_becomes_stretched_after_squeeze():
    """滿行讓出半形後由 grid 轉 stretched：省下的空白由齊行均分回字距。"""
    on = flow_pages([_spec(TWO_CLOSER_LINES, line_end=True)], 5, 10)[0][0].line
    adv, status = line_justified_advance(on, 12.0)
    assert status == "stretched"
    assert adv == pytest.approx(12.0 * 5 / 4.5)


def test_para_end_line_has_no_geometric_effect():
    """段末行不齊行，末枚之後也無內容：本規則對段末行無視覺效果（誠實記錄）。"""
    line = squeeze_line_end(line_of("整理」", cap=5, para_end=True))
    assert line_justified_advance(line, 12.0) == (12.0, "grid")


# --- 樣式層 ---

def test_template_paragraph_style_line_end_squeeze_defaults_false():
    """模版未宣告時預設關閉（既有模版行為不變）。"""
    template = load_template(TEMPLATE)
    assert all(st.line_end_squeeze is False
               for st in template.paragraph_styles.values())


@pytest.mark.parametrize("value,expected", [(True, True), (False, False),
                                            ("true", True), ("False", False)])
def test_template_line_end_squeeze_accepts_bool_and_text(value, expected):
    """模版 JSON 布林與樣式面板文字輸入（QLineEdit 送字串）皆可解析。"""
    from cjkfolio.styles import PARAGRAPH_STYLE_FIELDS
    assert PARAGRAPH_STYLE_FIELDS["line_end_squeeze"](value) is expected


def test_template_line_end_squeeze_rejects_garbage():
    """非布林值快速失敗（不沉默當 True）。"""
    from cjkfolio.styles import PARAGRAPH_STYLE_FIELDS
    with pytest.raises(TemplateError):
        PARAGRAPH_STYLE_FIELDS["line_end_squeeze"]("maybe")


def test_line_end_squeeze_survives_template_round_trip(tmp_path):
    """另存重載保真：declared 只記宣告欄位，子樣式其餘參數承基底（Sprint 68／70）。"""
    from cjkfolio.style_editing import add_paragraph_style
    from cjkfolio.styles import save_template

    template = add_paragraph_style(
        load_template(TEMPLATE), "內文-行尾擠壓",
        {"based_on": "內文-明體直排", "line_end_squeeze": True})
    path = tmp_path / "roundtrip.json"
    save_template(template, path)
    back = load_template(path)
    child = back.paragraph_styles["內文-行尾擠壓"]
    base = back.paragraph_styles["內文-明體直排"]
    assert child.line_end_squeeze is True and base.line_end_squeeze is False
    assert "line_end_squeeze" in child.declared
    assert (child.size_pt, child.font_family) == (base.size_pt, base.font_family)


# --- R5 樣張（repo 內原本一枚括號都沒有，GAPS #69 (b)） ---

@pytest.fixture(scope="module")
def sample_layout():
    from cjkfolio.document import document_from_dict
    doc = document_from_dict(json.loads(SAMPLE_DOC.read_text(encoding="utf-8")))
    return layout_document(doc, load_template(SAMPLE_TEMPLATE))


def test_sample_exists_and_has_no_em_dash():
    """繁中標點紅線：破折號一律不用（逗號、冒號、括號替代）。"""
    assert SAMPLE_DOC.exists(), "R5 素材缺檔（GAPS #69 (b) 要求自擬含括號樣張）"
    assert "—" not in SAMPLE_DOC.read_text(encoding="utf-8")


def test_sample_actually_hits_the_rule_and_stays_clean(sample_layout):
    """樣張確實命中規則（不是排出來一次都沒觸發的假驗收），且禁則與溢出 0。"""
    hits = [pl for page in sample_layout.pages for pl in page.placed
            if pl.line.cells and pl.line.cells[-1].width == SQUEEZE_WIDTH]
    assert len(hits) >= 3, f"樣張只命中 {len(hits)} 行，不足以支撐 R5 驗收"
    assert all(pl.line.cells[-1].text in SQUEEZE_CLOSERS for pl in hits)
    assert sample_layout.violations == []


def test_sample_has_an_unsqueezed_control_paragraph(sample_layout):
    """樣張含未開啟的對照段：同一段文字排兩次，比對才看得出差別。"""
    styles = {pl.style for page in sample_layout.pages for pl in page.placed}
    assert {"內文-明體直排", "內文-行尾擠壓"} <= styles
