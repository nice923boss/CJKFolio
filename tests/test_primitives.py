"""向量原件層（cjkfolio.primitives）：CIP 細框幾何純數學。素材自擬（版權紅線）。"""
from pathlib import Path

import pytest

from cjkfolio.primitives import PT_PER_MM, StrokeLine, StrokeRect, cip_frame_rect, toc_rule_line
from cjkfolio.styles import FrameSpec, RuleSpec, load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"


@pytest.fixture(scope="module")
def fmaster():
    return load_template(TEMPLATE).masters["F-版權頁"]


def test_cip_frame_rect_geometry(fmaster):
    frame = FrameSpec(kind="cip-box", cmyk=(0.0, 0.0, 0.0, 1.0), line_width_pt=0.5, pad_pt=6.0)
    left, n_lines = 72.51, 7
    rect = cip_frame_rect(fmaster, left, n_lines, frame)
    grid = fmaster.grid
    top = fmaster.margins.top_mm * PT_PER_MM
    content_w = grid.chars_per_line * grid.char_advance_pt
    assert isinstance(rect, StrokeRect)
    assert rect.x0 == pytest.approx(left - 6.0)
    assert rect.y0 == pytest.approx(top - 6.0)
    assert rect.x1 == pytest.approx(left + content_w + 6.0)
    assert rect.y1 == pytest.approx(top + n_lines * grid.line_pitch_pt + 6.0)
    assert rect.cmyk == (0.0, 0.0, 0.0, 1.0)
    assert rect.line_width_pt == pytest.approx(0.5)
    # top-down 不變式：x0<x1、y0（上緣）<y1（下緣）
    assert rect.x0 < rect.x1 and rect.y0 < rect.y1


def test_cip_frame_height_scales_with_line_count(fmaster):
    frame = FrameSpec(kind="cip-box")
    r5 = cip_frame_rect(fmaster, 72.0, 5, frame)
    r9 = cip_frame_rect(fmaster, 72.0, 9, frame)
    # 行數多 → 框更高（y1 增），左右與上緣不變
    assert r9.x0 == r5.x0 and r9.x1 == r5.x1 and r9.y0 == r5.y0
    assert r9.y1 - r5.y1 == pytest.approx(4 * fmaster.grid.line_pitch_pt)


def test_cip_frame_pad_widens_box(fmaster):
    tight = cip_frame_rect(fmaster, 72.0, 3, FrameSpec(kind="cip-box", pad_pt=0.0))
    padded = cip_frame_rect(fmaster, 72.0, 3, FrameSpec(kind="cip-box", pad_pt=10.0))
    assert padded.x0 == pytest.approx(tight.x0 - 10.0)
    assert padded.x1 == pytest.approx(tight.x1 + 10.0)
    assert padded.y0 == pytest.approx(tight.y0 - 10.0)
    assert padded.y1 == pytest.approx(tight.y1 + 10.0)


def test_cip_frame_asymmetric_vertical_pad(fmaster):
    # p178 實測 pad 不對稱（水平 5.05、垂直 4.94）：pad_v_pt 選配，None＝同 pad_pt
    frame = FrameSpec(kind="cip-box", pad_pt=5.05, pad_v_pt=4.94)
    base = cip_frame_rect(fmaster, 72.0, 3, FrameSpec(kind="cip-box", pad_pt=0.0))
    rect = cip_frame_rect(fmaster, 72.0, 3, frame)
    assert rect.x0 == pytest.approx(base.x0 - 5.05)
    assert rect.x1 == pytest.approx(base.x1 + 5.05)
    assert rect.y0 == pytest.approx(base.y0 - 4.94)
    assert rect.y1 == pytest.approx(base.y1 + 4.94)
    # 未給 pad_v_pt 時垂直沿用 pad_pt（既有行為不變）
    sym = cip_frame_rect(fmaster, 72.0, 3, FrameSpec(kind="cip-box", pad_pt=5.05))
    assert sym.y0 == pytest.approx(base.y0 - 5.05)


# ---------- 目錄水平虛線（Sprint 15） ----------

def test_toc_rule_line_geometry():
    rule = RuleSpec(kind="toc-rule", cmyk=(0.0, 0.0, 0.0, 0.57), line_width_pt=1.0,
                    dash_on_pt=3.0, dash_off_pt=2.0, y_from_top_pt=122.46)
    page_w = 148.0 * PT_PER_MM
    line = toc_rule_line(page_w, rule)
    assert isinstance(line, StrokeLine)
    # 水平線：y 固定於實測天頭下位置
    assert line.y0 == pytest.approx(122.46) and line.y1 == pytest.approx(122.46)
    # 貫穿頁寬並向兩側延伸出血（貼邊元素出血全出，§9）
    assert line.x0 == pytest.approx(-rule.bleed_extend_pt)
    assert line.x1 == pytest.approx(page_w + rule.bleed_extend_pt)
    assert line.x0 < line.x1
    # 樣式參數原樣傳遞
    assert line.cmyk == (0.0, 0.0, 0.0, 0.57)
    assert line.line_width_pt == pytest.approx(1.0)
    assert line.dash_on_pt == pytest.approx(3.0)
    assert line.dash_off_pt == pytest.approx(2.0)


def test_toc_rule_line_solid_when_dash_on_zero():
    # dash_on_pt=0 語意為實線（後端據此不分段）
    rule = RuleSpec(kind="toc-rule", y_from_top_pt=100.0, dash_on_pt=0.0, dash_off_pt=0.0)
    line = toc_rule_line(400.0, rule)
    assert line.dash_on_pt == 0.0


# ---------- 目錄虛線篇名斷開（Sprint 21） ----------

def test_toc_rule_segments_no_gap_single_full_span():
    """無斷開區間＝單段，幾何同原全寬線（向後相容）。"""
    from cjkfolio.primitives import toc_rule_segments
    rule = RuleSpec(kind="toc-rule", cmyk=(0.0, 0.0, 0.0, 0.57), y_from_top_pt=122.46)
    page_w = 148.0 * PT_PER_MM
    segs = toc_rule_segments(page_w, rule)
    assert len(segs) == 1
    assert segs[0].x0 == pytest.approx(-rule.bleed_extend_pt)
    assert segs[0].x1 == pytest.approx(page_w + rule.bleed_extend_pt)
    assert segs[0].y0 == pytest.approx(122.46) and segs[0].y1 == pytest.approx(122.46)


def test_toc_rule_segments_split_at_gaps():
    """斷開區間把線切段：段端點貼齊 gap 邊、樣式參數原樣傳遞每段。"""
    from cjkfolio.primitives import toc_rule_segments
    rule = RuleSpec(kind="toc-rule", cmyk=(0.0, 0.0, 0.0, 0.57), line_width_pt=1.0,
                    dash_on_pt=3.0, dash_off_pt=2.0, y_from_top_pt=122.46)
    page_w = 148.0 * PT_PER_MM
    segs = toc_rule_segments(page_w, rule, gaps=((100.0, 150.0),))
    assert len(segs) == 2
    assert segs[0].x0 == pytest.approx(-rule.bleed_extend_pt)
    assert segs[0].x1 == pytest.approx(100.0)
    assert segs[1].x0 == pytest.approx(150.0)
    assert segs[1].x1 == pytest.approx(page_w + rule.bleed_extend_pt)
    for s in segs:
        assert s.y0 == pytest.approx(122.46) and s.y1 == pytest.approx(122.46)
        assert s.cmyk == (0.0, 0.0, 0.0, 0.57)
        assert s.dash_on_pt == pytest.approx(3.0)


def test_toc_rule_segments_multiple_gaps_sorted_and_clipped():
    """多斷開：未排序輸入仍正確切段；越出線端的 gap 裁剪、零長段不產出。"""
    from cjkfolio.primitives import toc_rule_segments
    rule = RuleSpec(kind="toc-rule", y_from_top_pt=100.0, bleed_extend_pt=0.0)
    segs = toc_rule_segments(400.0, rule, gaps=((300.0, 350.0), (-20.0, 50.0)))
    # gap(-20,50) 蓋掉線頭（零長段不產出）→ 段：50〜300、350〜400
    assert [(s.x0, s.x1) for s in segs] == [
        pytest.approx((50.0, 300.0)), pytest.approx((350.0, 400.0))]


# ---------- G 圖文版圖框保留區（Sprint 27） ----------

@pytest.fixture(scope="module")
def gmaster():
    return load_template(TEMPLATE).masters["G-圖文版"]


def test_figure_slot_rect_right_page_geometry(gmaster):
    """右頁（書口右）：橫向左緣＝inner、右緣＝頁寬−outer，縱向取量測 top/bottom。"""
    from cjkfolio.primitives import figure_slot_rect
    fig = gmaster.figure
    page_w = 148.0 * PT_PER_MM
    rect = figure_slot_rect(page_w, gmaster, True, fig)
    assert isinstance(rect, StrokeRect)
    assert rect.x0 == pytest.approx(gmaster.margins.inner_mm * PT_PER_MM)
    assert rect.x1 == pytest.approx(page_w - gmaster.margins.outer_mm * PT_PER_MM)
    assert rect.y0 == pytest.approx(fig.top_from_top_pt)
    assert rect.y1 == pytest.approx(fig.bottom_from_top_pt)
    assert rect.x0 < rect.x1 and rect.y0 < rect.y1  # top-down 不變式
    assert rect.cmyk == fig.cmyk and rect.line_width_pt == pytest.approx(fig.line_width_pt)


def test_figure_slot_rect_mirror_left_page(gmaster):
    """左頁鏡像：書口在左，左右邊距對調（inner↔outer）；版心寬與縱向不變。"""
    from cjkfolio.primitives import figure_slot_rect
    fig = gmaster.figure
    page_w = 148.0 * PT_PER_MM
    r_right = figure_slot_rect(page_w, gmaster, True, fig)
    r_left = figure_slot_rect(page_w, gmaster, False, fig)
    assert r_left.x0 == pytest.approx(gmaster.margins.outer_mm * PT_PER_MM)
    assert r_left.x1 == pytest.approx(page_w - gmaster.margins.inner_mm * PT_PER_MM)
    assert (r_left.x1 - r_left.x0) == pytest.approx(r_right.x1 - r_right.x0)
    assert r_left.y0 == r_right.y0 and r_left.y1 == r_right.y1
    assert r_left.x0 != r_right.x0  # 鏡像確實位移


def test_figure_slot_rect_no_mirror_uses_outer_left(gmaster):
    """mirror=False 恆以 outer 為左緣（不受 is_right 影響）。"""
    from dataclasses import replace

    from cjkfolio.primitives import figure_slot_rect
    m = replace(gmaster, mirror=False)
    page_w = 148.0 * PT_PER_MM
    a = figure_slot_rect(page_w, m, True, m.figure)
    b = figure_slot_rect(page_w, m, False, m.figure)
    assert a.x0 == pytest.approx(m.margins.outer_mm * PT_PER_MM)
    assert a.x0 == pytest.approx(b.x0)


def test_figure_slot_edges_four_dashed(gmaster):
    """四邊虛線佔位框：4 條 dashed StrokeLine，貼齊矩形上下左右邊、原樣傳遞樣式。"""
    from cjkfolio.primitives import figure_slot_edges, figure_slot_rect
    fig = gmaster.figure
    rect = figure_slot_rect(148.0 * PT_PER_MM, gmaster, True, fig)
    edges = figure_slot_edges(rect, fig)
    assert len(edges) == 4
    assert fig.dash_on_pt > 0  # 虛線佔位語意
    for e in edges:
        assert isinstance(e, StrokeLine)
        assert e.dash_on_pt == pytest.approx(fig.dash_on_pt)
        assert e.dash_off_pt == pytest.approx(fig.dash_off_pt)
        assert e.cmyk == fig.cmyk
        assert e.line_width_pt == pytest.approx(fig.line_width_pt)
    seg = {(round(e.x0, 2), round(e.y0, 2), round(e.x1, 2), round(e.y1, 2)) for e in edges}
    assert (round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y0, 2)) in seg
    assert (round(rect.x0, 2), round(rect.y1, 2), round(rect.x1, 2), round(rect.y1, 2)) in seg
    assert (round(rect.x0, 2), round(rect.y0, 2), round(rect.x0, 2), round(rect.y1, 2)) in seg
    assert (round(rect.x1, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)) in seg
