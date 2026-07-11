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
