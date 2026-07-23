"""行首開括號縮始側（CLREQ WD-20150723 §3.1.6.2 規則 1，Sprint 117）。

證據：條文逐字（B 級）＝「當行首出現開始括注符號，可以縮減該符號始側二分之一個
漢字大小的空白」＋內建思源宋體 TC 與思源黑體 TC 各 8 枚開括號的一手墨跡量測
（A 級，spikes/spike20-line-head-squeeze：位移 0.5 em 後切墨 0 筆、最小餘裕 0.020 em）。

與同小節規則 2（Sprint 116）的關鍵差別在**位移單位**：規則 2 只縮推進量，規則 1 要縮
的是字形之前的空白，必須位移字形。Spike 20 量出位移若取字槽（0.5 × 字距，且齊行後
更大）會在《與〈上切墨，故 `Cell.glyph_offset` 存 **em**（字級倍數），三處渲染一律
乘字級而非乘齊行字距。本檔釘死這條界線，以及模型 A（行邊界完全不變）。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.engine import (
    SQUEEZE_HEAD_OFFSET,
    SQUEEZE_OPENERS,
    SQUEEZE_WIDTH,
    Cell,
    Line,
    ParagraphSpec,
    flow_pages,
    squeeze_line_head,
    tokenize,
)
from cjkfolio.layout import layout_document, line_justified_advance
from cjkfolio.style_editing import add_paragraph_style
from cjkfolio.styles import TemplateError, load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"
SAMPLE_DOC = ROOT / "samples" / "line-head-squeeze.doc.json"
SAMPLE_TEMPLATE = ROOT / "samples" / "punct-squeeze.template.json"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）")


def line_of(text: str, **kw) -> Line:
    cells = tokenize(text)
    return Line(tuple(cells), kw.get("start_slot", 0), cap=kw.get("cap", len(cells)),
                para_end=kw.get("para_end", False))


def widths(line: Line):
    return [c.width for c in line.cells]


def offsets(line: Line):
    return [c.glyph_offset for c in line.cells]


# --- 純函式：條文規則 ---

@pytest.mark.parametrize("opener", sorted(SQUEEZE_OPENERS))
def test_line_starting_with_opener_squeezes_its_head(opener):
    """規則 1：行首開括號讓出始側半形（字身框 1 → 0.5）並把字形往行首移 0.5 em。"""
    out = squeeze_line_head(line_of(opener + "整理"))
    assert widths(out) == [SQUEEZE_WIDTH, 1, 1]
    assert offsets(out) == [SQUEEZE_HEAD_OFFSET, 0.0, 0.0]


@pytest.mark.parametrize("head", ["書", "。", "、", "」", "》"])
def test_line_starting_with_non_opener_untouched(head):
    """條文只給行首的「開始括注符號」，漢字、句逗、閉括號皆不適用。"""
    out = squeeze_line_head(line_of(head + "整理"))
    assert widths(out) == [1, 1, 1] and offsets(out) == [0.0, 0.0, 0.0]


def test_already_squeezed_opener_not_squeezed_twice():
    """行首開括號若已由 §3.1.6.1（Sprint 90）讓出半形，不重複扣也不位移。"""
    cells = (Cell("「", "cjk", width=SQUEEZE_WIDTH), Cell("『", "cjk"), Cell("書", "cjk"))
    out = squeeze_line_head(Line(cells, cap=3))
    assert widths(out) == [SQUEEZE_WIDTH, 1, 1] and offsets(out) == [0.0, 0.0, 0.0]


def test_latin_and_tcy_line_heads_not_squeezed():
    """西文旋轉串與縱中橫非開括號，不參與。"""
    assert offsets(squeeze_line_head(line_of("abc書"))) == [0.0, 0.0]
    assert offsets(squeeze_line_head(line_of("12書"))) == [0.0, 0.0]


def test_empty_line_is_returned_unchanged():
    """空行無首枚可縮（繞排全排除行槽會產生此形態）。"""
    line = Line((), cap=0)
    assert squeeze_line_head(line) is line


def test_squeeze_line_head_is_pure_and_preserves_everything_else():
    """純函式：原 Line 不被修改，且除首枚 width／glyph_offset 外欄位全保真。"""
    line = line_of("「整理", start_slot=2, cap=8, para_end=True)
    before = [(c.text, c.kind, c.span, c.width, c.glyph_offset) for c in line.cells]
    out = squeeze_line_head(line)
    assert [(c.text, c.kind, c.span, c.width, c.glyph_offset)
            for c in line.cells] == before
    assert (out.start_slot, out.cap, out.para_end) == (2, 8, True)
    assert [(c.text, c.kind, c.span) for c in out.cells] == [b[:3] for b in before]


# --- 流排整合（opt-in，模型 A） ---

def _spec(text: str, head: bool = False, end: bool = False, punct: bool = False,
          indent: int = 0):
    return ParagraphSpec(text=text, indent=indent, line_head_squeeze=head,
                         line_end_squeeze=end, punct_squeeze=punct)


TWO_OPENER_LINES = "「整理」他說。《書》好"  # cap=4：第一、三行行首各一枚開括號


def test_flow_pages_opt_in_default_off():
    """預設 line_head_squeeze=False：字寬與位移皆維持既有（既有輸出零變更）。"""
    lines = [pl.line for pl in flow_pages([_spec(TWO_OPENER_LINES)], 4, 10)[0]]
    assert [widths(ln) for ln in lines] == [[1] * 4, [1] * 3, [1] * 4]
    assert all(c.glyph_offset == 0.0 for ln in lines for c in ln.cells)


def test_flow_pages_squeezes_only_the_opener_at_each_line_head():
    """開啟後每行首枚開括號讓半形，行內其他開括號不受本規則影響。"""
    lines = [pl.line for pl in
             flow_pages([_spec(TWO_OPENER_LINES, head=True)], 4, 10)[0]]
    assert [widths(ln) for ln in lines] == [
        [SQUEEZE_WIDTH, 1, 1, 1], [1] * 3, [SQUEEZE_WIDTH, 1, 1, 1]]
    assert [offsets(ln)[0] for ln in lines] == [
        SQUEEZE_HEAD_OFFSET, 0.0, SQUEEZE_HEAD_OFFSET]


def test_line_breaking_is_identical_with_and_without_the_rule():
    """模型 A 核心保證：省下的半格不回饋容量，開關兩版斷行逐行完全相同。"""
    text = "「整理」是《內在整理》裡的一句話（她說）而後停頓「很久」再開口說下去"
    for cap in (4, 5, 7, 11, 16):
        off = flow_pages([_spec(text)], cap, 20)[0]
        on = flow_pages([_spec(text, head=True)], cap, 20)[0]
        assert ["".join(c.text for c in pl.line.cells) for pl in off] == \
               ["".join(c.text for c in pl.line.cells) for pl in on], f"cap={cap}"


def test_rule_applies_only_to_vertical():
    """量測依直排 vert 形墨跡（同 Sprint 90／116）：橫排字形位置不同，不套用。"""
    lines = flow_pages([_spec(TWO_OPENER_LINES, head=True)], 4, 10,
                       vertical=False)[0]
    assert all(c.width == 1 and c.glyph_offset == 0.0
               for pl in lines for c in pl.line.cells)


def test_indented_first_line_still_hits_and_keeps_its_indent():
    """段首縮排行命中：縮的是符號自己的始側空白，縮排槽數不變（Spike 20 定案三）。"""
    first = flow_pages([_spec("「整理」是一句話", head=True, indent=2)], 8, 10)[0][0].line
    assert first.start_slot == 2
    assert widths(first)[0] == SQUEEZE_WIDTH
    assert offsets(first)[0] == SQUEEZE_HEAD_OFFSET


def test_head_and_end_rules_are_independent_on_the_same_line():
    """同一行行首開括號與行尾閉括號可各自命中，兩規則互不代理。"""
    line = flow_pages([_spec("「整理」他說", head=True, end=True)], 4, 10)[0][0].line
    assert "".join(c.text for c in line.cells) == "「整理」"
    assert widths(line) == [SQUEEZE_WIDTH, 1, 1, SQUEEZE_WIDTH]
    assert offsets(line) == [SQUEEZE_HEAD_OFFSET, 0.0, 0.0, 0.0]


def test_para_end_line_still_has_visual_effect():
    """與規則 2 相反：位移是固定量，不靠齊行分回，故段末行同樣看得到效果。"""
    line = squeeze_line_head(line_of("「書", cap=5, para_end=True))
    assert line_justified_advance(line, 12.0) == (12.0, "grid")  # 段末行不齊行
    assert line.cells[0].glyph_offset == SQUEEZE_HEAD_OFFSET     # 位移仍在


# --- 幾何：位移單位是字級不是字槽（Spike 20 定案一） ---

def test_offset_is_em_based_so_it_never_grows_with_justification():
    """釘死位移單位：0.5 em ＝ 5.75pt（字級 11.5），與齊行放大後的字距無關。

    若位移誤綁字槽，cap 愈小位移愈大（12.08×cap/(cap−0.5)×0.5），Spike 20 量到
    《在 0.5252 em 起即切墨。本測試讓 cap 由寬到窄，位移量必須一動不動。
    """
    size_pt = 11.5
    text = "「整理是一場與過去的對話，我們把留下的物件一件件安放，也把回憶安放。" * 3
    for cap in (32, 16, 10, 4):
        line = flow_pages([_spec(text, head=True)], cap, 30)[0][0].line
        adv, _ = line_justified_advance(line, 12.08)
        assert adv > 12.08  # 讓出半格後齊行確實放大字距
        assert line.cells[0].glyph_offset * size_pt == pytest.approx(-5.75)


@needs_fonts
def test_png_backend_moves_the_glyph_by_half_em(tmp_path):
    """PNG 後端（render.py）：同一枚括號開關兩版的墨跡實測位移＝0.5 字級。"""
    from PIL import Image, ImageOps

    from cjkfolio.document import document_from_dict
    from cjkfolio.render import render_document

    base = load_template(TEMPLATE)
    tpl = add_paragraph_style(base, "內文-行首擠壓",
                              {"based_on": "內文-明體直排", "line_head_squeeze": True})

    def ink_top(style: str, out: Path) -> float:
        doc = document_from_dict({
            "schema": "cjkfolio/document@2",
            "meta": {"title": "自擬樣張", "template": "neizai-zhengli",
                     "master": "A-內文版"},
            "paragraphs": [{"text": "「", "style": style}]})
        out.mkdir()
        result = render_document(doc, tpl, out, dpi=150, footer=False)
        img = Image.open(result.paths[0])
        box = ImageOps.invert(img.convert("L")).getbbox()
        assert box is not None, "整頁空白"
        return box[1]

    off = ink_top("內文-明體直排", tmp_path / "off")
    on = ink_top("內文-行首擠壓", tmp_path / "on")
    expect_px = 0.5 * 11.5 * (150 / 72.0)
    assert off - on == pytest.approx(expect_px, abs=2), f"位移 {off - on} vs {expect_px}"


@needs_fonts
def test_pdf_backend_glyph_origin_matches_png_and_breaks_stay_identical(tmp_path):
    """PDF 後端（pdf_writer.py）：以 PyMuPDF 抽字座標獨立驗證（Gate 4）。

    首枚括號往行首移 0.5 字級（5.75pt），次枚字則往行首移「一字距減半個齊行字距」
    ＝兩個不同量值，正是本規則與只縮推進量的規則 2 的差別所在。
    """
    fitz = pytest.importorskip("fitz")

    from cjkfolio.document import document_from_dict
    from cjkfolio.pdf_writer import export_pdf

    base = load_template(TEMPLATE)
    tpl = add_paragraph_style(base, "內文-行首擠壓",
                              {"based_on": "內文-明體直排", "line_head_squeeze": True})
    text = "「整理是一場與過去的對話，我們把留下的物件一件件安放，也把回憶安放。"

    def chars(style: str, name: str):
        doc = document_from_dict({
            "schema": "cjkfolio/document@2",
            "meta": {"title": "自擬樣張", "template": "neizai-zhengli",
                     "master": "A-內文版"},
            "paragraphs": [{"text": text, "style": style}]})
        out = tmp_path / name
        export_pdf(doc, tpl, out, footer=False)
        raw = fitz.open(str(out))[0].get_text("rawdict")
        return [(c["c"], c["origin"]) for b in raw["blocks"]
                for l in b.get("lines", []) for s in l.get("spans", [])
                for c in s.get("chars", [])]

    off = chars("內文-明體直排", "off.pdf")
    on = chars("內文-行首擠壓", "on.pdf")
    assert [c for c, _ in off] == [c for c, _ in on], "模型 A：斷行與字序完全不變"
    assert off[0][0] == "「"

    layout = layout_document(document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli",
                 "master": "A-內文版"},
        "paragraphs": [{"text": text, "style": "內文-行首擠壓"}]}), tpl)
    cap = layout.pages[0].placed[0].line.cap
    adv = 12.08 * cap / (cap - 0.5)  # 獨立重算齊行字距（不引 layout 的實作）

    assert off[0][1][1] - on[0][1][1] == pytest.approx(0.5 * 11.5, abs=0.05)
    assert off[1][1][1] - on[1][1][1] == pytest.approx(12.08 - 0.5 * adv, abs=0.05)


# --- 樣式層 ---

def test_template_paragraph_style_line_head_squeeze_defaults_false():
    """模版未宣告時預設關閉（既有模版行為不變）。"""
    template = load_template(TEMPLATE)
    assert all(st.line_head_squeeze is False
               for st in template.paragraph_styles.values())


@pytest.mark.parametrize("value,expected", [(True, True), (False, False),
                                            ("true", True), ("False", False)])
def test_template_line_head_squeeze_accepts_bool_and_text(value, expected):
    """模版 JSON 布林與樣式面板文字輸入（QLineEdit 送字串）皆可解析。"""
    from cjkfolio.styles import PARAGRAPH_STYLE_FIELDS
    assert PARAGRAPH_STYLE_FIELDS["line_head_squeeze"](value) is expected


def test_template_line_head_squeeze_rejects_garbage():
    """非布林值快速失敗（不沉默當 True）。"""
    from cjkfolio.styles import PARAGRAPH_STYLE_FIELDS
    with pytest.raises(TemplateError):
        PARAGRAPH_STYLE_FIELDS["line_head_squeeze"]("maybe")


def test_line_head_squeeze_survives_template_round_trip(tmp_path):
    """另存重載保真：declared 只記宣告欄位，子樣式其餘參數承基底（Sprint 68／70）。"""
    from cjkfolio.styles import save_template

    template = add_paragraph_style(
        load_template(TEMPLATE), "內文-行首擠壓",
        {"based_on": "內文-明體直排", "line_head_squeeze": True})
    path = tmp_path / "roundtrip.json"
    save_template(template, path)
    back = load_template(path)
    child = back.paragraph_styles["內文-行首擠壓"]
    base = back.paragraph_styles["內文-明體直排"]
    assert child.line_head_squeeze is True and base.line_head_squeeze is False
    assert "line_head_squeeze" in child.declared
    assert (child.size_pt, child.font_family) == (base.size_pt, base.font_family)


# --- R5 樣張 ---

@pytest.fixture(scope="module")
def sample_layout():
    from cjkfolio.document import document_from_dict
    doc = document_from_dict(json.loads(SAMPLE_DOC.read_text(encoding="utf-8")))
    return layout_document(doc, load_template(SAMPLE_TEMPLATE))


def test_sample_exists_and_has_no_em_dash():
    """繁中標點紅線：破折號一律不用（逗號、冒號、括號替代）。"""
    assert SAMPLE_DOC.exists(), "R5 素材缺檔（自擬含行首開括號樣張）"
    assert "—" not in SAMPLE_DOC.read_text(encoding="utf-8")


def test_sample_actually_hits_the_rule_and_stays_clean(sample_layout):
    """樣張確實命中規則（不是排出來一次都沒觸發的假驗收），且禁則與溢出 0。"""
    hits = [pl for page in sample_layout.pages for pl in page.placed
            if pl.line.cells and pl.line.cells[0].glyph_offset == SQUEEZE_HEAD_OFFSET]
    assert len(hits) >= 3, f"樣張只命中 {len(hits)} 行，不足以支撐 R5 驗收"
    assert all(pl.line.cells[0].text in SQUEEZE_OPENERS for pl in hits)
    assert all(pl.line.cells[0].width == SQUEEZE_WIDTH for pl in hits)
    assert sample_layout.violations == []


def test_sample_has_an_unsqueezed_control_paragraph(sample_layout):
    """樣張含未開啟的對照段：同一段文字排兩次，比對才看得出差別。"""
    styles = {pl.style for page in sample_layout.pages for pl in page.placed}
    assert {"內文-明體直排", "內文-行首擠壓"} <= styles
