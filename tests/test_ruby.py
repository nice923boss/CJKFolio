"""注音 ruby（直排 mono-ruby 標注層，Sprint 86，Phase 4）測試。

覆蓋：ruby 幾何純函式（右側鄰欄置中）、document@2 相容擴充 Run.ruby 解析／序列化／
驗證（單字 base、非空字串）、engine cells_from_runs 掛 ruby 到 cell（相容 2 元組）、
ruby cell 流入 layout、兩後端端到端繪製（需字型）。base 字流與斷行不變。
真書《內在整理》無注音，R5 以自擬素材驗收（不宣稱真書驗證）。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.document import (
    DocumentError,
    Run,
    document_from_dict,
    load_document,
    save_document,
)
from cjkfolio.engine import cells_from_runs
from cjkfolio.layout import layout_document
from cjkfolio.placement import RUBY_SIZE_RATIO, ruby_axis_and_top
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
needs_fonts = pytest.mark.skipif(
    not (ROOT / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


def _doc(runs, style="內文-明體直排", master="A-內文版"):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "注音樣張", "template": "neizai-zhengli", "master": master},
        "paragraphs": [{"style": style, "runs": runs}],
    })


# ---------- 幾何純函式 ----------

def test_ruby_geometry_right_of_base_and_centered():
    rx, rtop, rsize = ruby_axis_and_top(100.0, 200.0, 24.0, 12.0, 2)
    assert rsize == 12.0 * RUBY_SIZE_RATIO          # 6.0
    assert rx == 100.0 + 6.0 + 3.0                  # base 右半 + ruby 左半 = 109
    assert rtop == (200.0 + 24.0 / 2) - 2 * 6.0 / 2  # 中心 212 − 串高半 6 = 206
    assert rtop == 206.0


def test_ruby_geometry_single_char_centered():
    rx, rtop, rsize = ruby_axis_and_top(50.0, 0.0, 20.0, 10.0, 1)
    assert rsize == 5.0
    assert rtop == 10.0 - 2.5  # 單字置中：中心 10 − 2.5


# ---------- 文件模型：解析／序列化／驗證 ----------

def test_run_ruby_parse_and_roundtrip(tmp_path):
    doc = _doc([
        {"text": "漢", "ruby": "ㄏㄢˋ"},
        {"text": "字", "ruby": "ㄗˋ"},
        {"text": "。"},
    ])
    p = doc.paragraphs[0]
    assert p.runs[0] == Run("漢", None, "ㄏㄢˋ")
    assert p.runs[1].ruby == "ㄗˋ"
    assert p.runs[2].ruby is None
    assert p.text == "漢字。"
    out = tmp_path / "r.doc.json"
    save_document(doc, out)
    again = load_document(out)
    assert again.paragraphs[0].runs[0].ruby == "ㄏㄢˋ"
    assert again.paragraphs[0].runs[2].ruby is None
    raw = json.loads(out.read_text(encoding="utf-8"))["paragraphs"][0]["runs"]
    assert raw[0]["ruby"] == "ㄏㄢˋ"
    assert "ruby" not in raw[2]


def test_run_ruby_validation_fast_fail():
    with pytest.raises(DocumentError, match="ruby"):
        _doc([{"text": "漢字", "ruby": "x"}])   # base 多字
    with pytest.raises(DocumentError, match="ruby"):
        _doc([{"text": "漢", "ruby": ""}])       # 空 ruby
    with pytest.raises(DocumentError, match="ruby"):
        _doc([{"text": "漢", "ruby": 123}])      # 非字串


def test_paragraph_text_shortcut_not_used_with_ruby(tmp_path):
    doc = _doc([{"text": "漢", "ruby": "ㄏㄢˋ"}])
    out = tmp_path / "s.doc.json"
    save_document(doc, out)
    raw = json.loads(out.read_text(encoding="utf-8"))["paragraphs"][0]
    assert "runs" in raw and "text" not in raw
    assert raw["runs"][0]["ruby"] == "ㄏㄢˋ"


# ---------- engine：ruby 掛到 cell（相容 2/3 元組） ----------

def test_cells_from_runs_carries_ruby():
    cells = cells_from_runs((("漢", None, "ㄏㄢˋ"), ("字", None, None)))
    assert cells[0].text == "漢" and cells[0].ruby == "ㄏㄢˋ"
    assert cells[1].text == "字" and cells[1].ruby is None
    cells2 = cells_from_runs((("測", None),))  # 2 元組相容
    assert cells2[0].ruby is None


def test_ruby_cell_flows_to_layout_unchanged_break():
    template = load_template(TEMPLATE)
    doc = _doc([{"text": "漢", "ruby": "ㄏㄢˋ"}, {"text": "字", "ruby": "ㄗˋ"}])
    layout = layout_document(doc, template)
    ruby_cells = [c for pg in layout.pages for pl in pg.placed
                  for c in pl.line.cells if c.ruby]
    assert [c.text for c in ruby_cells] == ["漢", "字"]
    assert [c.ruby for c in ruby_cells] == ["ㄏㄢˋ", "ㄗˋ"]
    assert layout.violations == []
    # base 字流不變：帶 ruby 與不帶 ruby 的斷行分頁相同
    plain = _doc([{"text": "漢"}, {"text": "字"}])
    lp = layout_document(plain, template)
    assert [len(pg.placed) for pg in layout.pages] == [len(pg.placed) for pg in lp.pages]


# ---------- 端到端（需字型）：兩後端繪 ruby ----------

@needs_fonts
def test_ruby_pdf_end_to_end(tmp_path):
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    template = load_template(TEMPLATE)
    doc = _doc([
        {"text": "漢", "ruby": "ㄏㄢˋ"}, {"text": "字", "ruby": "ㄗˋ"},
        {"text": "注", "ruby": "ㄓㄨˋ"}, {"text": "音", "ruby": "ㄧㄣ"},
    ])
    out = tmp_path / "ruby.pdf"
    result = export_pdf(doc, template, out)
    assert result.violations == []
    assert result.font_warnings == []  # ruby 注音字元皆有字形（無 .notdef）
    txt = fitz.open(str(out))[0].get_text()
    for ch in "漢字注音":       # base
        assert ch in txt
    for ch in "ㄏㄢㄗㄓㄨㄧㄣ":  # ruby 注音符號進 PDF
        assert ch in txt


@needs_fonts
def test_ruby_png_renders(tmp_path):
    from cjkfolio.render import render_document

    template = load_template(TEMPLATE)
    doc = _doc([{"text": "漢", "ruby": "ㄏㄢˋ"}, {"text": "字", "ruby": "ㄗˋ"}])
    result = render_document(doc, template, tmp_path, dpi=100)
    assert result.font_warnings == []
    assert list(tmp_path.glob("*.png"))  # 有輸出頁
