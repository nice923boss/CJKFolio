"""文件 provenance 載體（Cell.span＋PlacedLine.para_idx，Sprint 18）。

Phase 2 首項工程（Spike 10 介面缺口）：畫布點選 → 文件游標映射的資料鏈。
span 座標系＝文件段 text 半開區間（normalize 前原字串）；layout 流排一律帶映射。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.engine import (
    ParagraphSpec,
    cells_from_runs,
    flow_pages,
    normalize,
    normalize_with_offsets,
    tokenize,
)
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


# ---------- normalize_with_offsets ----------

def test_normalize_with_offsets_identity_when_clean():
    norm, offs = normalize_with_offsets("直排之美")
    assert norm == "直排之美"
    assert offs == (0, 1, 2, 3)


def test_normalize_with_offsets_cc_strip_shifts():
    norm, offs = normalize_with_offsets("發\x07言﹁強﹂")
    assert norm == "發言「強」"
    assert offs == (0, 2, 3, 4, 5)  # \x07 剝除；表現形 1:1 保原索引
    assert normalize("發\x07言﹁強﹂") == norm  # normalize 與映射版單一事實來源


# ---------- tokenize span（輸入座標 identity）----------

def test_tokenize_span_covers_input():
    cells = tokenize("直排AB12，34格 尾")
    spans = [c.span for c in cells]
    # 直(0,1) 排(1,2) AB12(2,6) ，(6,7) 34(7,9) 格(9,10) 空(10,11) 尾(11,12)
    assert spans == [(0, 1), (1, 2), (2, 6), (6, 7), (7, 9), (9, 10), (10, 11), (11, 12)]
    text = "直排AB12，34格 尾"
    assert all(text[a:b] == c.text for c, (a, b) in zip(cells, spans))


def test_tokenize_span_with_offsets_maps_to_source():
    src = "發\x07言ab"   # 小寫＝旋轉拉丁整串一格（全大寫走逐字正立，見 test_tcy）
    norm, offs = normalize_with_offsets(src)
    cells = tokenize(norm, offsets=offs)
    assert [c.span for c in cells] == [(0, 1), (2, 3), (3, 5)]
    assert src[3:5] == "ab"


# ---------- cells_from_runs：文件座標基底 ----------

def test_cells_from_runs_span_uses_document_offsets():
    runs = (("前段", None), ("重\x07點", "強調"))
    doc_text = "前段重\x07點"
    cells = cells_from_runs(runs)
    assert [c.span for c in cells] == [(0, 1), (1, 2), (2, 3), (4, 5)]
    assert [doc_text[a:b] for a, b in (c.span for c in cells)] == ["前", "段", "重", "點"]
    assert cells[2].char_style == "強調"


# ---------- flow_pages：para_idx 載體 ----------

def test_flow_pages_placed_para_idx():
    specs = [
        ParagraphSpec(text="甲段甲段甲段甲段甲段", indent=0, gap_after=0, para_idx=0),
        ParagraphSpec(text="乙段乙段", indent=0, gap_after=0, para_idx=1),
    ]
    pages = flow_pages(specs, chars_per_line=4, slots_per_page=13)
    idx = [pl.para_idx for pl in pages[0]]
    assert idx == [0, 0, 0, 1]  # 甲段 3 行、乙段 1 行


def test_flow_pages_para_idx_default_none():
    pages = flow_pages([ParagraphSpec(text="無標段", indent=0)],
                       chars_per_line=8, slots_per_page=13)
    assert pages[0][0].para_idx is None


# ---------- layout_document：全文件 round-trip ----------

def _roundtrip_ok(doc, layout) -> tuple:
    """全 placed cells：doc 段 text[span] 正規化後應等於 cell.text。回傳 (檢查數, 錯數)。"""
    total = bad = 0
    for page in layout.pages:
        for pl in page.placed:
            para = doc.paragraphs[pl.para_idx]
            for c in pl.line.cells:
                total += 1
                if normalize(para.text[c.span[0]:c.span[1]]) != c.text:
                    bad += 1
    return total, bad


def test_layout_document_provenance_roundtrip(template):
    doc = make_doc([
        {"text": "整理之路2026年，由AB編號開始。", "style": "內文-明體直排"},
        {"runs": [{"text": "發言："}, {"text": "重點\x07句", "char_style": "內文強調-明體W9"}],
         "style": "訪談發言body"},
    ])
    layout = layout_document(doc, template)
    total, bad = _roundtrip_ok(doc, layout)
    assert total > 0 and bad == 0


def test_layout_document_horizontal_roundtrip(template):
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "橫排樣張", "template": "neizai-zhengli", "master": "F-版權頁"},
        "paragraphs": [{"text": "ISBN 978-000-0000-00-0（自擬）", "style": "版權頁-CIP橫排"}],
    })
    layout = layout_document(doc, template)
    total, bad = _roundtrip_ok(doc, layout)
    assert total > 0 and bad == 0
