"""Phase 1 直排引擎（cjkfolio.engine）單元測試。

自 Spike 1 測試移植，flow 測試改用 ParagraphSpec API。
測試素材一律自擬，不含《內在整理》文字（版權紅線）。
"""
from cjkfolio.engine import (
    Cell,
    Line,
    ParagraphSpec,
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


def test_tokenize_tags_char_style():
    cells = tokenize("重點2026", char_style="強調")
    assert all(c.char_style == "強調" for c in cells)
    assert tokenize("平文")[0].char_style is None


def test_flow_runs_carry_char_style_and_kinsoku():
    spec = ParagraphSpec(
        text="前段重點，後段。",
        runs=(("前段", None), ("重點，", "強調"), ("後段。", None)),
        indent=0, gap_after=0,
    )
    pages = flow_pages([spec], chars_per_line=8, slots_per_page=13)
    lines = [pl.line for pl in pages[0]]
    styles = [c.char_style for line in lines for c in line.cells]
    assert styles == [None, None, "強調", "強調", "強調", None, None, None]
    assert check_kinsoku(lines) == []


def test_normalize_strips_control_chars():
    # PDF 抽取素材殘留的控制字元（如 U+0007）不得進排版流
    assert normalize("發言\x07內容") == "發言內容"
    assert normalize("縮\t排\n") == "縮排"
    assert normalize("　全形空白保留") == "　全形空白保留"


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


# ---------- tokenize 橫排（Sprint 13：版權頁-CIP，不轉縱中橫） ----------

def test_tokenize_horizontal_digits_not_tcy():
    # 橫排：短數字走正常 latin LTR，不轉縱中橫
    cells = tokenize("第12章", vertical=False)
    assert [(c.text, c.kind) for c in cells] == [
        ("第", "cjk"), ("12", "latin"), ("章", "cjk"),
    ]


def test_tokenize_horizontal_groups_ascii_including_spaces_and_hyphens():
    # 橫排：整串 ascii（含空格、連字號、句點）成一個 latin run，走自然寬
    cells = tokenize("ISBN 978-0-00-0（平裝）", vertical=False)
    latin = [c for c in cells if c.kind == "latin"]
    assert len(latin) == 1
    assert latin[0].text == "ISBN 978-0-00-0"
    # 全形括號為非 ascii → cjk cell
    assert [c.text for c in cells if c.kind == "cjk"] == ["（", "平", "裝", "）"]


def test_tokenize_horizontal_fullwidth_space_is_space_cell():
    cells = tokenize("123.45　1140700", vertical=False)
    kinds = [(c.text, c.kind) for c in cells]
    assert kinds == [("123.45", "latin"), ("　", "space"), ("1140700", "latin")]


def test_break_paragraph_horizontal_direction_agnostic():
    # 斷行邏輯與方向無關（吃 cells＋容量）
    lines = break_paragraph("一二三四五六七八九十", 5, indent=0, vertical=False)
    assert ["".join(c.text for c in l.cells) for l in lines] == ["一二三四五", "六七八九十"]


# ---------- break_paragraph ----------

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

def test_line_start_kinsoku_pulls_punctuation_in():
    # 行首禁則優先擠入本行（Sprint 11：參考書 −0.4pt 齊行實測），行寬容忍溢出
    lines = break_paragraph("一二三四五。六七", 5, indent=0)
    texts = ["".join(c.text for c in l.cells) for l in lines]
    assert texts == ["一二三四五。", "六七"]
    assert lines[0].cap == 5 and not lines[0].para_end
    assert lines[1].para_end
    assert check_kinsoku(lines) == []


def test_line_start_kinsoku_run_over_limit_pushes_out_anchor():
    # 連續句逗超過擠入上限（2 槽）：錨字連同整串句逗追出，本行撐開齊行
    lines = break_paragraph("一二三四五。。。六", 5, indent=0)
    texts = ["".join(c.text for c in l.cells) for l in lines]
    assert texts == ["一二三四", "五。。。六"]
    assert check_kinsoku(lines) == []


def test_break_lines_carry_cap_and_para_end():
    lines = break_paragraph("一二三四五六七八", 5, indent=2)
    assert [(l.cap, l.para_end) for l in lines] == [(3, False), (5, True)]


def test_line_start_kinsoku_consecutive_pushed_together():
    lines = break_paragraph("一二三四「五。」六", 5, indent=0)
    for line in lines:
        assert line.cells[0].text not in set("。」，、")
    assert check_kinsoku(lines) == []


def test_line_end_kinsoku_open_bracket_pushed_down():
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


# ---------- flow_pages（ParagraphSpec API） ----------

def test_flow_pages_paragraph_gap_and_page_break():
    specs = [
        ParagraphSpec("一二三四五六七八九十", style="內文", indent=0, gap_after=1),
        ParagraphSpec("甲乙丙丁戊", style="內文", indent=0),
    ]
    # 每行 5 字、每頁 3 行槽：段 1 佔 2 槽、空 1 槽、段 2 首行進第 2 頁
    pages = flow_pages(specs, chars_per_line=5, slots_per_page=3)
    assert len(pages) == 2
    assert [p.slot for p in pages[0]] == [0, 1]
    assert [p.slot for p in pages[1]] == [0]
    first_page_text = "".join(c.text for p in pages[0] for c in p.line.cells)
    assert first_page_text == "一二三四五六七八九十"


def test_flow_pages_first_paragraph_continuation_no_indent():
    specs = [
        ParagraphSpec("接續前頁的段落文字", style="內文", indent=2, gap_after=1),
        ParagraphSpec("新段落開始", style="內文", indent=2),
    ]
    pages = flow_pages(specs, chars_per_line=6, slots_per_page=10, first_para_continues=True)
    slots = {p.slot: p for p in pages[0]}
    assert slots[0].line.start_slot == 0   # 續段不縮排
    assert 2 not in slots                   # 段間空 1 槽
    assert slots[3].line.start_slot == 2


def test_flow_pages_carries_style_name():
    specs = [
        ParagraphSpec("章名", style="章名大標-明體W7", indent=0, gap_after=1),
        ParagraphSpec("內文文字", style="內文-明體直排", indent=0),
    ]
    pages = flow_pages(specs, chars_per_line=10, slots_per_page=13)
    styles = [p.style for p in pages[0]]
    assert styles == ["章名大標-明體W7", "內文-明體直排"]


def test_flow_pages_per_spec_chars_per_line_override():
    # 標題行容量 3（大級數行高換算），內文行容量 6
    specs = [
        ParagraphSpec("大標題五字", style="標題", indent=0, gap_after=0, chars_per_line=3),
        ParagraphSpec("內文六字排滿", style="內文", indent=0),
    ]
    pages = flow_pages(specs, chars_per_line=6, slots_per_page=13)
    title_lines = [p for p in pages[0] if p.style == "標題"]
    assert ["".join(c.text for c in p.line.cells) for p in title_lines] == ["大標題", "五字"]
    body_lines = [p for p in pages[0] if p.style == "內文"]
    assert "".join(c.text for c in body_lines[0].line.cells) == "內文六字排滿"


def test_flow_pages_multi_slot_line_advances_slot():
    # line_slots=2 的標題每行佔 2 槽
    specs = [
        ParagraphSpec("標題", style="標題", indent=0, gap_after=1, line_slots=2),
        ParagraphSpec("內文", style="內文", indent=0),
    ]
    pages = flow_pages(specs, chars_per_line=10, slots_per_page=13)
    placed = pages[0]
    assert placed[0].slot == 0
    assert placed[1].slot == 3  # 標題佔槽 0-1、空 1 槽、內文在槽 3
