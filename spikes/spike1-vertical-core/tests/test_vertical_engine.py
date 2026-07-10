"""Spike 1 直排引擎單元測試（TDD RED 先行）。

測試素材一律自擬，不含《內在整理》文字（版權紅線）。
規則依據：W3C CLREQ 繁中（句逗置中、行首行尾禁則、縱中橫）。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vertical_engine import (
    Cell,
    Line,
    break_paragraph,
    check_kinsoku,
    flow_pages,
    normalize,
    tokenize,
)


# ---------- normalize ----------

def test_normalize_vertical_presentation_forms():
    assert normalize("﹁縱書﹂") == "「縱書」"
    assert normalize("﹃引文﹄") == "『引文』"
    assert normalize("句讀﹐﹒") == "句讀，．"


# ---------- tokenize ----------

def test_tokenize_pure_cjk_one_cell_per_char():
    cells = tokenize("直排之美")
    assert [c.text for c in cells] == ["直", "排", "之", "美"]
    assert all(c.kind == "cjk" and c.width == 1 for c in cells)


def test_tokenize_two_digit_run_is_tcy():
    cells = tokenize("第12章")
    assert [(c.text, c.kind) for c in cells] == [
        ("第", "cjk"), ("12", "tcy"), ("章", "cjk"),
    ]
    assert cells[1].width == 1


def test_tokenize_long_digit_run_is_rotated_latin():
    cells = tokenize("西元2026年")
    latin = [c for c in cells if c.kind == "latin"]
    assert len(latin) == 1
    assert latin[0].text == "2026"
    assert latin[0].width == 2  # ceil(4 * 0.5)


def test_tokenize_latin_word_not_split():
    cells = tokenize("用HarfBuzz塑形")
    latin = [c for c in cells if c.kind == "latin"]
    assert len(latin) == 1
    assert latin[0].text == "HarfBuzz"
    assert latin[0].width == 4  # ceil(8 * 0.5)


def test_tokenize_space_occupies_one_slot():
    cells = tokenize("上 下")
    assert [(c.text, c.kind) for c in cells] == [
        ("上", "cjk"), (" ", "space"), ("下", "cjk"),
    ]


# ---------- break_paragraph 基本斷行 ----------

def test_break_even_lines_no_punctuation():
    lines = break_paragraph("一二三四五六七八九十", 5, indent=0)
    assert ["".join(c.text for c in l.cells) for l in lines] == ["一二三四五", "六七八九十"]


def test_break_first_line_indent_reduces_capacity():
    lines = break_paragraph("一二三四五六七八九十", 5, indent=2)
    assert lines[0].start_slot == 2
    assert "".join(c.text for c in lines[0].cells) == "一二三"
    assert lines[1].start_slot == 0
    assert "".join(c.text for c in lines[1].cells) == "四五六七八"


# ---------- 禁則 ----------

def test_line_start_kinsoku_pushes_previous_char_down():
    # 5 字滿行後第 6 字是「。」，不得落行首：前字「五」隨句號下移
    lines = break_paragraph("一二三四五。六七", 5, indent=0)
    texts = ["".join(c.text for c in l.cells) for l in lines]
    assert texts == ["一二三四", "五。六七"]
    assert check_kinsoku(lines) == []


def test_line_start_kinsoku_consecutive_pushed_together():
    # 行界後接連續禁則「。」」：一併處理，行首仍不得見禁則
    lines = break_paragraph("一二三四「五。」六", 5, indent=0)
    for line in lines:
        assert line.cells[0].text not in set("。」，、")
    assert check_kinsoku(lines) == []


def test_line_end_kinsoku_open_bracket_pushed_down():
    # 「 不得落行尾
    lines = break_paragraph("一二三四「五六七八", 5, indent=0)
    texts = ["".join(c.text for c in l.cells) for l in lines]
    assert texts == ["一二三四", "「五六七八"]
    assert check_kinsoku(lines) == []


def test_kinsoku_detector_flags_violation():
    bad = [Line(cells=(Cell("。", "cjk", 1), Cell("字", "cjk", 1)), start_slot=0)]
    assert check_kinsoku(bad) != []


def test_no_kinsoku_violations_on_mixed_synthetic_text():
    text = (
        "排版是一門手藝，也是一場對細節的凝視。「好的直排，讀者感覺不到它的存在。」"
        "第3章談禁則：句號、逗號不落行首；開引號不懸行尾。西元2026年，我們以12個"
        "測試句驗證，行行合格！（真的嗎？）真的。"
    )
    for width in (5, 7, 10, 22, 32):
        lines = break_paragraph(text, width, indent=2)
        assert check_kinsoku(lines) == [], f"width={width} 出現禁則違規"


# ---------- flow_pages 頁面流排 ----------

def test_flow_pages_paragraph_gap_and_page_break():
    paras = ["一二三四五六七八九十", "甲乙丙丁戊"]
    # 每行 5 字、每頁 3 行槽：段 1 佔 2 槽、空 1 槽、段 2 首行進第 2 頁
    pages = flow_pages(paras, chars_per_line=5, slots_per_page=3, indent=0, para_gap_slots=1)
    assert len(pages) == 2
    assert [slot for slot, _ in pages[0]] == [0, 1]
    assert [slot for slot, _ in pages[1]] == [0]
    first_page_text = "".join(c.text for _, l in pages[0] for c in l.cells)
    assert first_page_text == "一二三四五六七八九十"


def test_flow_pages_first_paragraph_continuation_no_indent():
    pages = flow_pages(
        ["接續前頁的段落文字", "新段落開始"],
        chars_per_line=6, slots_per_page=10, indent=2, para_gap_slots=1,
        first_para_continues=True,
    )
    slots = dict(pages[0])
    assert slots[0].start_slot == 0   # 續段不縮排
    # 段 1 佔槽 0、1，段間空 1 槽（槽 2），新段落在槽 3 且縮排 2
    assert 2 not in slots
    assert slots[3].start_slot == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
