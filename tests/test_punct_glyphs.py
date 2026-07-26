"""標點字形三修（Sprint 142）：破折號成對連字、省略號置中、半形括號轉全形。

三者共用同一條路：engine.tokenize 產出的 Cell 決定兩後端（render PNG／pdf_writer
PDF）怎麼塑形。故單元驗收落在 tokenize，字形層再以 HarfBuzz 塑形結果佐證
（成對破折號確實取到連字、省略號與全形括號確實有 vert 直排字形）。
"""
import json
from pathlib import Path

import pytest
import uharfbuzz as hb

from cjkfolio.engine import normalize_with_offsets, tokenize
from cjkfolio.placement import _cluster_text

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf"
MANUSCRIPT = ROOT / "local" / "manual-test" / "chengming.doc.json"


def cells(text: str, vertical: bool = True):
    norm, offs = normalize_with_offsets(text)
    return tokenize(norm, None, vertical, offsets=offs)


def shape_ttb(text: str):
    face = hb.Face(hb.Blob.from_file_path(str(FONT)), 0)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.direction = "ttb"
    buf.script = "Hani"
    buf.language = "zh-tw"
    hb.shape(font, buf, {})
    return [(i.codepoint, i.cluster, p.y_advance)
            for i, p in zip(buf.glyph_infos, buf.glyph_positions)]


# ---------- 破折號成對 ----------

def test_dash_pair_is_one_cell_of_two_slots():
    """連續兩枚破折號合成一個字格、佔兩個字槽（使用者要求：連起來佔兩格）。"""
    out = cells("第一章——金絲雀")
    dash = [c for c in out if "—" in c.text]
    assert len(dash) == 1
    assert dash[0].text == "——"
    assert dash[0].width == 2
    assert dash[0].kind == "cjk"


def test_dash_pair_shapes_to_a_single_two_em_ligature():
    """成對塑形取得連字（一枚字形、縱推進兩個 em）＝一條連續的長線。

    逐字塑形則是兩枚各推進一個 em，字槽上下各留 0.071 em，接縫處空 0.142 em
    ＝使用者看到的斷線。
    """
    pair = shape_ttb("——")
    single = shape_ttb("—")
    assert len(pair) == 1, "成對須併為一枚連字"
    assert pair[0][2] == -2000, "連字縱推進須為兩個 em"
    assert len(single) == 1 and single[0][2] == -1000
    assert pair[0][0] != single[0][0], "連字與單枚須為不同字形"


def test_dash_single_unchanged():
    """單枚破折號維持一格：真稿 13 處單枚，不得被本次修正改寬。"""
    out = cells("第一章—金絲雀")
    dash = [c for c in out if "—" in c.text]
    assert len(dash) == 1 and dash[0].text == "—" and dash[0].width == 1


def test_dash_triple_pairs_then_single_keeping_total_width():
    """三枚：前兩枚成對、餘一枚單獨，總字槽數與逐字時相同（不改斷行容量）。"""
    out = cells("枚———測")
    dash = [c for c in out if "—" in c.text]
    assert [c.text for c in dash] == ["——", "—"]
    assert sum(c.width for c in dash) == 3


def test_dash_pair_span_covers_both_source_chars():
    """provenance：合併後的字格 span 須涵蓋兩枚來源字元（游標反查不失步）。"""
    out = cells("章——金")
    dash = [c for c in out if "—" in c.text][0]
    assert dash.span == (1, 3)


def test_dash_cluster_text_maps_whole_ligature_for_tounicode():
    """PDF 抽字：連字須對回兩枚破折號，否則抽出來少一枚。"""
    class _Info:
        def __init__(self, cluster):
            self.cluster = cluster

    assert _cluster_text("——", [_Info(0)], 0) == "——"
    assert _cluster_text("「完", [_Info(0), _Info(1)], 0) == "「"
    assert _cluster_text("「完", [_Info(0), _Info(1)], 1) == "完"


def test_dash_pair_not_merged_in_horizontal():
    """橫排（版權頁-CIP）不合併：連字是直排 vert 字形，橫排走另一條路。"""
    out = cells("章——金", vertical=False)
    assert [c.text for c in out if "—" in c.text] == ["—", "—"]


# ---------- 省略號置中 ----------

def test_ascii_dots_become_centred_ellipsis_cells():
    """ASCII 句點串（鍵盤代打的省略號）轉 U+2026 走 cjk 字格。

    走 latin 的話由 _draw_rotated_latin 以 asc+desc 字條置中，句點墨跡貼基線，
    旋轉後偏向行軸左側＝使用者回報的偏左。
    """
    out = cells("我...我")
    ell = [c for c in out if c.text == "…"]
    assert len(ell) == 1
    assert ell[0].kind == "cjk" and ell[0].width == 1
    assert ell[0].span == (1, 4)


def test_six_dots_become_two_ellipsis_cells():
    """六點＝中文省略號「……」兩格（三點一枚，不改變作者寫的點數）。"""
    out = cells("名......燈")
    assert [c.text for c in out] == ["名", "…", "…", "燈"]
    assert [c.span for c in out if c.text == "…"] == [(1, 4), (4, 7)]


def test_two_dots_round_up_to_one_ellipsis():
    """不足三點進位為一枚（真稿 2 處「妳..我」，屬作者少打）。"""
    out = cells("妳..我")
    assert [c.text for c in out] == ["妳", "…", "我"]


def test_ellipsis_has_centred_vertical_glyph():
    """U+2026 的 vert 字形一枚一個 em，供 _draw_ttb_char 依字槽置中。"""
    got = shape_ttb("…")
    assert len(got) == 1 and got[0][2] == -1000


def test_list_marker_and_decimal_unaffected():
    """列標記「1.」走縱中橫、小數「2.0」走旋轉拉丁：兩者含數字，非純句點串。"""
    out = cells("記 1. 與 2.0 完")
    kinds = {c.text: (c.kind, c.width) for c in out}
    assert kinds["1."] == ("tcy", 1)
    assert kinds["2.0"] == ("latin", 2)


def test_single_period_unchanged():
    """單枚句點不轉：可能是縮寫點或被切掉數字的小數，轉省略號會誤判。"""
    out = cells("甲.乙")
    assert [c.text for c in out] == ["甲", ".", "乙"]


def test_dots_not_converted_in_horizontal():
    out = cells("我...我", vertical=False)
    assert [c.text for c in out] == ["我", "...", "我"]


# ---------- 半形括號轉全形 ----------

@pytest.mark.parametrize("half,full", [
    ("(", "（"), (")", "）"), ("[", "〔"), ("]", "〕"), ("{", "｛"), ("}", "｝"),
])
def test_halfwidth_brackets_become_fullwidth_in_vertical(half, full):
    """半形括號在字型裡沒有 vert 直排字形，直排會維持半形直立（真稿「(完)」）。"""
    out = cells(f"甲{half}乙")
    assert [c.text for c in out] == ["甲", full, "乙"]
    assert out[1].kind == "cjk" and out[1].width == 1


def test_fullwidth_bracket_has_vertical_glyph():
    """轉全形後才有 vert 字形（半形括號無，故維持直立半形）。"""
    for ch in "（）":
        got = shape_ttb(ch)
        assert len(got) == 1 and got[0][2] == -1000


def test_bracket_conversion_keeps_span():
    out = cells("(完)")
    assert [c.span for c in out] == [(0, 1), (1, 2), (2, 3)]


def test_converted_bracket_obeys_kinsoku_sets():
    """轉全形的附帶效益：進入禁則字集，開括號不懸行尾、閉括號不落行首。"""
    from cjkfolio.engine import LINE_END_FORBIDDEN, LINE_START_FORBIDDEN

    assert cells("甲(")[1].text in LINE_END_FORBIDDEN
    assert cells("甲)")[1].text in LINE_START_FORBIDDEN


def test_brackets_not_converted_in_horizontal():
    """橫排的 ascii 括號屬 latin run（走塑形自然寬），不得轉全形。"""
    out = cells("甲(乙)", vertical=False)
    assert any(c.kind == "latin" and "(" in c.text for c in out)


# ---------- 真素材驗收（R5）----------

@pytest.mark.skipif(not MANUSCRIPT.exists(), reason="真稿為本機素材，未納版控")
def test_real_manuscript_punctuation_all_routed_to_cjk_cells():
    """真稿《成名之路》407 段全掃：三類標點都走 cjk 字格，無殘留 latin 句點串。"""
    data = json.loads(MANUSCRIPT.read_text(encoding="utf-8"))
    pairs = dots = brackets = 0
    for para in data["paragraphs"]:
        for c in cells(para["text"]):
            assert not (c.kind == "latin" and set(c.text) == {"."}), \
                f"仍有句點串走旋轉拉丁：{c.text!r}"
            assert not (c.kind == "cjk" and c.text in "()[]{}"), \
                f"仍有半形括號走直排字格：{c.text!r}"
            if c.text == "——":
                pairs += 1
            elif c.text == "…":
                dots += 1
            elif c.text in "（）":
                brackets += 1
    # 130＝ASCII 句點串換算（2 點×2＋3 點×52＋4 點×1 進位 2＋6 點×37 各兩格），
    # ＋1＝真稿原有的一枚 U+2026。
    assert pairs == 32, f"真稿成對破折號 32 處，實得 {pairs}"
    assert dots == 131, f"真稿省略號字格 131 格，實得 {dots}"
    assert brackets == 8, f"真稿全形括號 8 枚（原有 6 ＋「(完)」轉來 2），實得 {brackets}"
