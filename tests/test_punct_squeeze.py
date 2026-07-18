"""標點擠壓（約物詰め，Sprint 90）：CLREQ §3.1.6.1 規則 2〜6 相鄰約物減半形。

證據：W3C CLREQ WD-20150723 §3.1.6.1（B 級，條文原文）＋內建思源宋體 TC 約物
墨跡量測（A 級，spikes/spike17-mojikumi）。規則 1（句逗後接閉括號）條文明文
「繁體中文標點不適用」，量測亦顯示該情境擠壓後墨跡相碰，故不實作。
"""
from pathlib import Path

import pytest

from cjkfolio.engine import (
    SQUEEZE_WIDTH,
    ParagraphSpec,
    flow_pages,
    squeeze_punctuation,
    tokenize,
)
from cjkfolio.styles import TemplateError, load_template

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"


def widths(text: str):
    return [c.width for c in squeeze_punctuation(tokenize(text))]


# --- CLREQ 規則逐條（實作範圍：2〜6） ---

@pytest.mark.parametrize("pair", ["」，", "』。", "）、"])
def test_rule2_closer_then_stop_squeezes(pair):
    """規則 2：閉括號後接頓號／逗號／句號，減半形。"""
    assert widths(pair) == [SQUEEZE_WIDTH, 1]


@pytest.mark.parametrize("pair", ["，「", "。『", "、（"])
def test_rule3_stop_then_opener_squeezes(pair):
    """規則 3：頓號／逗號／句號後接開括號，減半形。"""
    assert widths(pair) == [SQUEEZE_WIDTH, 1]


@pytest.mark.parametrize("pair", ["」「", "』（", "）《"])
def test_rule4_closer_then_opener_squeezes(pair):
    """規則 4：閉括號後接開括號，減半形。"""
    assert widths(pair) == [SQUEEZE_WIDTH, 1]


@pytest.mark.parametrize("pair", ["「『", "（〈", "《「"])
def test_rule5_consecutive_openers_squeeze(pair):
    """規則 5：連續開括號，減半形。"""
    assert widths(pair) == [SQUEEZE_WIDTH, 1]


@pytest.mark.parametrize("pair", ["」』", "）〉", "》」"])
def test_rule6_consecutive_closers_squeeze(pair):
    """規則 6：連續閉括號，減半形。"""
    assert widths(pair) == [SQUEEZE_WIDTH, 1]


@pytest.mark.parametrize("pair", ["，」", "。』", "、）"])
def test_rule1_stop_then_closer_not_squeezed_for_traditional(pair):
    """規則 1（句逗後接閉括號）不實作：CLREQ 明文繁體不適用，且本產品內建繁體
    字型量測顯示擠壓後墨距為負（相碰，Spike 17 probe_squeeze_pairs）。"""
    assert widths(pair) == [1, 1]


# --- 邊界 ---

def test_hanzi_and_lone_punctuation_not_squeezed():
    """非相鄰約物對不擠壓：漢字之間、漢字與約物之間皆維持全形。"""
    assert widths("整理書") == [1, 1, 1]
    assert widths("書。整") == [1, 1, 1]


def test_last_cell_never_squeezed():
    """末枚無後續字，無「符號間空隙」可調，維持全形。"""
    assert widths("書」") == [1, 1]
    assert widths("」") == [1]


def test_three_consecutive_openers_squeeze_pairwise():
    """三枚以上連續約物逐對套用：前兩枚各讓半形，末枚維持全形。"""
    assert widths("「『〈") == [SQUEEZE_WIDTH, SQUEEZE_WIDTH, 1]


def test_squeeze_is_pure_and_preserves_cell_identity():
    """純函式：原 cells 不被修改，且除 width 外欄位（text／kind／span）不變。"""
    cells = tokenize("」「書")
    before = [(c.text, c.kind, c.span) for c in cells]
    out = squeeze_punctuation(cells)
    assert [(c.text, c.kind, c.span) for c in cells] == before
    assert [(c.text, c.kind, c.span) for c in out] == before
    assert [c.width for c in cells] == [1, 1, 1]


def test_latin_and_tcy_cells_not_squeezed():
    """西文旋轉串與縱中橫非約物，不參與擠壓（寬度維持既有推導）。"""
    assert [c.width for c in squeeze_punctuation(tokenize("」abc"))] == [1, 2]
    assert [c.width for c in squeeze_punctuation(tokenize("」12"))] == [1, 1]


# --- 流排整合（opt-in） ---

def _spec(text: str, squeeze: bool):
    return ParagraphSpec(text=text, indent=0, punct_squeeze=squeeze)


def test_flow_pages_opt_in_default_off():
    """預設 punct_squeeze=False：字寬與既有一致（既有輸出零變更的鐵律）。"""
    text = "書」「整"
    off = flow_pages([_spec(text, False)], 10, 10)[0][0].line
    assert [c.width for c in off.cells] == [1, 1, 1, 1]


def test_flow_pages_squeeze_on_frees_slots():
    """開啟後相鄰約物讓出半形，同一行槽容得下更多字。"""
    text = "書」「整"
    on = flow_pages([_spec(text, True)], 10, 10)[0][0].line
    assert [c.width for c in on.cells] == [1, SQUEEZE_WIDTH, 1, 1]
    assert sum(c.width for c in on.cells) == 3.5


def test_flow_pages_squeeze_changes_line_breaking():
    """兩處擠壓共讓出一整格，行容量 4 槽時多排入一字（首尾皆不觸禁則）。"""
    text = "整」」，理書"  # 」」＝規則 6、」，＝規則 2
    off = flow_pages([_spec(text, False)], 4, 10)[0]
    on = flow_pages([_spec(text, True)], 4, 10)[0]
    assert "".join(c.text for c in off[0].line.cells) == "整」」，"
    assert "".join(c.text for c in on[0].line.cells) == "整」」，理"
    assert sum(c.width for c in on[0].line.cells) == 4.0


def test_squeezed_cells_keep_provenance_span():
    """擠壓不動 span：畫布反查與編輯游標映射不受影響。"""
    line = flow_pages([_spec("書」「整", True)], 10, 10)[0][0].line
    assert [c.span for c in line.cells] == [(0, 1), (1, 2), (2, 3), (3, 4)]


# --- 樣式層 ---

def test_template_paragraph_style_punct_squeeze_defaults_false():
    """模版未宣告時預設關閉（既有模版行為不變）。"""
    template = load_template(TEMPLATE)
    assert template.paragraph_styles["內文-明體直排"].punct_squeeze is False
    assert all(st.punct_squeeze is False
               for st in template.paragraph_styles.values())


@pytest.mark.parametrize("value,expected", [(True, True), (False, False),
                                            ("true", True), ("False", False)])
def test_template_punct_squeeze_accepts_bool_and_text(value, expected):
    """模版 JSON 布林與樣式面板文字輸入（QLineEdit 送字串）皆可解析。"""
    from cjkfolio.styles import PARAGRAPH_STYLE_FIELDS
    assert PARAGRAPH_STYLE_FIELDS["punct_squeeze"](value) is expected


def test_template_punct_squeeze_rejects_garbage():
    """非布林值快速失敗（不沉默當 True）。"""
    from cjkfolio.styles import PARAGRAPH_STYLE_FIELDS
    with pytest.raises(TemplateError):
        PARAGRAPH_STYLE_FIELDS["punct_squeeze"]("maybe")


def test_punct_squeeze_survives_template_round_trip(tmp_path):
    """另存重載保真：declared 只記宣告欄位，子樣式其餘參數承基底（Sprint 68／70）。"""
    from cjkfolio.style_editing import add_paragraph_style
    from cjkfolio.styles import save_template

    template = add_paragraph_style(
        load_template(TEMPLATE), "內文-標點擠壓",
        {"based_on": "內文-明體直排", "punct_squeeze": True})
    path = tmp_path / "roundtrip.json"
    save_template(template, path)
    back = load_template(path)
    child = back.paragraph_styles["內文-標點擠壓"]
    base = back.paragraph_styles["內文-明體直排"]
    assert child.punct_squeeze is True and base.punct_squeeze is False
    assert "punct_squeeze" in child.declared
    assert (child.size_pt, child.font_family) == (base.size_pt, base.font_family)


# --- 兩後端同源 ---

@pytest.mark.skipif(
    not (TEMPLATE.parents[1] / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）")
def test_two_backend_parity_on_squeezed_cells(tmp_path):
    """擠壓後 PDF 實際字距＝半個字距（Gate 4：PyMuPDF 獨立解析，與寫出層不同實作）。

    擠壓只改 cell.width，兩後端皆以 `content_i += cell.width` 定位，故同源；
    本測試釘住 PDF 側的實際落點，PNG 側由既有字槽測試涵蓋。
    """
    fitz = pytest.importorskip("fitz")
    from cjkfolio.document import document_from_dict
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.style_editing import add_paragraph_style

    template = add_paragraph_style(
        load_template(TEMPLATE), "內文-標點擠壓",
        {"based_on": "內文-明體直排", "punct_squeeze": True})
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"style": "內文-標點擠壓", "text": "整」「理"}],
    })
    out = tmp_path / "squeeze.pdf"
    export_pdf(doc, template, out, footer=False)
    chars = [(c["bbox"][1], c["c"])
             for b in fitz.open(str(out))[0].get_text("rawdict")["blocks"]
             for line in b.get("lines", []) for s in line["spans"] for c in s["chars"]]
    tops = {c: y for y, c in chars}
    grid_advance = 12.08  # A-內文版網格字距（PLAN §1 實測）
    assert tops["「"] - tops["」"] == pytest.approx(grid_advance / 2, abs=0.05)
    assert tops["理"] - tops["「"] == pytest.approx(grid_advance, abs=0.05)
