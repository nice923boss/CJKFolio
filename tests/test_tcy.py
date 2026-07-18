"""縱中橫精修（Sprint 88，Phase 4）測試。

規則來源＝真書《內在整理》179 頁全掃（tools/measure_tcy_spans.py，A 級一手，
內文層 39 個西文 span 零反例）：
  正立（縱中橫）：單／雙位數字、數字帶尾點的列標記「1.」、全大寫縮寫逐字各一槽
    （'DM' 2 槽、'IKEA' 4 槽，縱向間距 12.07≈§1 字距 12.08）；級數不縮（'1.' 在
    11.5pt 內文中 span size＝11.5、墨寬 9.2 < 1em）。
  旋轉：含小寫的西文詞（podcast／Hermès／Céline／bye bye）、3 位以上數字（1966）、
    小數（2.0）。重音拉丁字母併入同一詞（真書整詞一個旋轉 span）。
"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.engine import tokenize
from cjkfolio.placement import tcy_placements
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
needs_fonts = pytest.mark.skipif(
    not (ROOT / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


def _kinds(text: str, vertical: bool = True):
    return [(c.text, c.kind, c.width) for c in tokenize(text, vertical=vertical)]


# ---------- tokenize：正立（縱中橫） ----------

def test_single_upper_letter_is_upright():
    # 真書 p40/p60/p91/p130：單一大寫字母正立各佔一槽（原走旋轉拉丁）
    assert _kinds("A型") == [("A", "tcy", 1), ("型", "cjk", 1)]


def test_upper_acronym_is_per_letter_upright():
    # 真書 p61 'IKEA' 4 槽、p40 'DM' 2 槽：全大寫縮寫逐字正立，一字一槽
    assert _kinds("去IKEA逛") == [
        ("去", "cjk", 1), ("I", "tcy", 1), ("K", "tcy", 1),
        ("E", "tcy", 1), ("A", "tcy", 1), ("逛", "cjk", 1),
    ]


def test_numbered_marker_is_one_tcy_cell():
    # 真書 p10 '1.' '2.' '3.'：數字帶尾點的列標記為單一正立格（原拆數字＋句點兩格）
    assert _kinds("1.整理") == [
        ("1.", "tcy", 1), ("整", "cjk", 1), ("理", "cjk", 1),
    ]
    assert _kinds("12.整理")[0] == ("12.", "tcy", 1)


def test_two_digit_run_still_tcy():
    assert _kinds("第12章") == [("第", "cjk", 1), ("12", "tcy", 1), ("章", "cjk", 1)]


# ---------- tokenize：旋轉 ----------

def test_lowercase_word_stays_rotated():
    # 真書 p7 'podcast'：含小寫的西文詞整串旋轉
    cells = [c for c in tokenize("聽podcast吧") if c.kind == "latin"]
    assert [c.text for c in cells] == ["podcast"]


def test_accented_latin_joins_one_run():
    # 真書 p23/p26 'Hermès' 為單一旋轉 span（3.2 槽）；重音字母不得拆斷西文詞
    cells = tokenize("買Hermès包")
    latin = [c for c in cells if c.kind == "latin"]
    assert [c.text for c in latin] == ["Hermès"]
    assert latin[0].width == 3          # ceil(6 × 0.5)，對表真書 38.64/12.08≈3.2
    assert [c.kind for c in cells] == ["cjk", "latin", "cjk"]


def test_decimal_number_is_rotated():
    # 真書 p172 '2.0' 旋轉：尾點併入 run 後，小數不再被拆成 tcy＋句點＋tcy
    cells = [c for c in tokenize("放大2.0倍") if c.kind == "latin"]
    assert [c.text for c in cells] == ["2.0"]


def test_long_digit_run_stays_rotated():
    # 真書 p172 '1966' 旋轉
    cells = [c for c in tokenize("西元2026年") if c.kind == "latin"]
    assert [c.text for c in cells] == ["2026"]


def test_mixed_case_word_rotated():
    cells = [c for c in tokenize("買Chanel包") if c.kind == "latin"]
    assert [c.text for c in cells] == ["Chanel"]


# ---------- provenance：逐字正立的 span ----------

def test_upper_acronym_spans_are_per_letter():
    cells = tokenize("去IKEA逛")
    assert [c.span for c in cells] == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]


def test_numbered_marker_span_covers_digit_and_dot():
    cells = tokenize("1.整理")
    assert cells[0].span == (0, 2)


# ---------- 橫排不受影響 ----------

def test_horizontal_unaffected():
    # 橫排（版權頁-CIP）：整串 ascii 一個 latin run，不逐字正立、不轉縱中橫
    assert _kinds("IKEA", vertical=False) == [("IKEA", "latin", 2)]
    assert _kinds("1.整理", vertical=False) == [
        ("1.", "latin", 1), ("整", "cjk", 1), ("理", "cjk", 1),
    ]


# ---------- 幾何：正立不縮字 ----------

@dataclass(frozen=True)
class _Info:
    codepoint: int
    cluster: int


@dataclass(frozen=True)
class _Pos:
    x_advance: float
    x_offset: float = 0.0
    y_offset: float = 0.0


class _StubShaper:
    """等寬假字型：每字 advance＝half em，供幾何純函式離字型驗證。"""
    upem = 1000

    def __init__(self, advance_units: float = 500.0):
        self.advance_units = advance_units

    def shape(self, text, direction):
        infos = [_Info(ord(ch), i) for i, ch in enumerate(text)]
        poss = [_Pos(self.advance_units) for _ in text]
        return infos, poss


def test_tcy_placement_uses_full_size():
    # 真書 '1.' 在 11.5pt 內文中 span size＝11.5（不縮字），墨寬 9.2 < 1em
    pls = tcy_placements(_StubShaper(), "1", axis_x_pt=100.0, cell_top_pt=0.0,
                         size_pt=12.0, advance_pt=12.0)
    assert [p.size_pt for p in pls] == [12.0]
    assert pls[0].x_pt == pytest.approx(100.0 - 6.0 / 2)   # 半形字寬 6 → 行軸置中


def test_tcy_placement_compresses_when_wider_than_em():
    # 三字（半形 ×3＝18 > em 12）：等比壓縮至 1em，仍行軸置中
    pls = tcy_placements(_StubShaper(), "123", axis_x_pt=100.0, cell_top_pt=0.0,
                         size_pt=12.0, advance_pt=12.0)
    assert pls[0].size_pt == pytest.approx(12.0 * 12.0 / 18.0)
    assert pls[0].x_pt == pytest.approx(100.0 - 12.0 / 2)  # 壓後總寬 1em


# ---------- 端到端（需字型）：兩後端 ----------

def _doc(text: str):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "縱中橫樣張", "template": "neizai-zhengli",
                 "master": "A-內文版"},
        "paragraphs": [{"style": "內文-明體直排", "text": text}],
    })


@needs_fonts
def test_tcy_pdf_per_letter_upright_on_line_axis(tmp_path):
    """PDF 側：全大寫逐字正立，同欄（行軸）逐槽下行，間距＝字距。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    template = load_template(TEMPLATE)
    out = tmp_path / "tcy.pdf"
    result = export_pdf(_doc("去IKEA逛街買東西，1.整理，2.0倍。"), template, out)
    assert result.violations == []
    assert result.font_warnings == []

    page = fitz.open(str(out))[0]
    txt = page.get_text()
    for ch in "IKEA":
        assert ch in txt
    assert "2.0" in txt.replace("\n", "")

    letters = [sp for block in page.get_text("dict")["blocks"]
               for line in block.get("lines", []) for sp in line["spans"]
               if sp["text"].strip() in tuple("IKEA")]
    assert len(letters) == 4
    centers = {round((sp["bbox"][0] + sp["bbox"][2]) / 2, 1) for sp in letters}
    assert len(centers) == 1          # 四字同欄＝同行軸
    tops = sorted(round(sp["bbox"][1], 2) for sp in letters)
    steps = [round(b - a, 2) for a, b in zip(tops, tops[1:])]
    assert all(s == pytest.approx(12.08, abs=0.05) for s in steps)  # §1 字距


@needs_fonts
def test_tcy_png_renders(tmp_path):
    from cjkfolio.render import render_document

    template = load_template(TEMPLATE)
    result = render_document(_doc("去IKEA逛，1.整理。"), template, tmp_path, dpi=100)
    assert result.font_warnings == []
    assert list(tmp_path.glob("*.png"))
