"""從參考 PDF 萃取起始樣式（cjkfolio.reference_extract，PLAN §4.3「從參考萃取」）。

純邏輯層（map_font／propose_styles）全合成資料；整合層以 PyMuPDF 造測試 PDF
（Gate 4 獨立路徑：fitz 寫、本模組掃）。草稿紅線：不含書中文句。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.reference_extract import (
    extract_draft,
    map_font,
    propose_styles,
    scan_pdf,
)


# ---------- 字型對映（§8 可散布字型組） ----------

@pytest.mark.parametrize("source,family,weight", [
    ("DFMingStd-W3", "思源宋體 TC", "regular"),
    ("DFMingStd-W7", "思源宋體 TC", "bold"),
    ("DFMingStd-W9", "思源宋體 TC", "heavy"),
    ("DFHeiStd-W5", "思源黑體 TC", "medium"),
    ("DFHeiStd-W7", "思源黑體 TC", "bold"),
    ("DFHeiStd-W9", "思源黑體 TC", "bold"),      # 黑無 heavy，就近 bold
    ("SourceHanSansTC-Medium", "思源黑體 TC", "medium"),
    ("DFFangSongStd-W4", "全字庫正宋體", "regular"),
    ("DFKaiShuStd-W5", "全字庫正楷體 TW-Kai", "regular"),
    ("HanziPenTC-W5", "辰宇落雁體", "regular"),
    ("GillSans-Light", "思源黑體 TC", "medium"),
    ("TimesNewRomanPSMT", "思源宋體 TC", "regular"),
])
def test_map_font_known_families(source, family, weight):
    got_family, got_weight, warn = map_font(source)
    assert (got_family, got_weight) == (family, weight)
    assert warn is False


def test_map_font_unknown_falls_back_with_warn():
    family, weight, warn = map_font("PepitaMT")
    assert family == "思源宋體 TC"
    assert warn is True


def test_map_font_fangsong_not_mistaken_as_song():
    family, _, _ = map_font("DFFangSongStd-W4")  # 名含 song，須先判仿宋
    assert family == "全字庫正宋體"


# ---------- 提案（純邏輯） ----------

def row(font, size, chars, pages=3):
    return {"font": font, "size": size, "chars": chars, "pages": pages}


STATS = [
    row("DFMingStd-W3", 11.5, 57000, 170),   # 主力 → 內文候選
    row("DFMingStd-W7", 21.9, 300, 12),      # 1.9 倍 → 標題候選
    row("DFHeiStd-W5", 13.0, 800, 40),       # 1.13 倍 → 標題候選
    row("DFHeiStd-W7", 11.5, 400, 30),       # 同級候選
    row("HanziPenTC-W5", 8.0, 900, 170),     # 0.70 倍 → 小字候選
]


def test_propose_roles_and_fields():
    styles, skipped = propose_styles(STATS, min_chars=60, max_styles=20)
    names = list(styles)
    assert names[0].startswith("內文候選-宋11.5pt")
    body = styles[names[0]]
    assert body == {
        "font_family": "思源宋體 TC", "font_weight": "regular", "size_pt": 11.5,
        "source_font": "DFMingStd-W3 11.5pt",
        "note": body["note"],  # note 逐欄驗於下
    }
    assert "57,000 字" in body["note"] and "170 頁" in body["note"]
    assert any(n.startswith("標題候選-宋21.9pt") for n in names)
    assert any(n.startswith("標題候選-黑13pt") for n in names)
    assert any(n.startswith("同級候選-黑11.5pt") for n in names)
    assert any(n.startswith("小字候選-手寫8pt") for n in names)
    assert skipped == []


def test_propose_min_chars_filters_noise_not_silent():
    stats = [row("DFMingStd-W3", 11.5, 5000), row("GillSans-Light", 8.0, 12)]
    styles, skipped = propose_styles(stats, min_chars=60, max_styles=20)
    assert len(styles) == 1
    assert skipped and skipped[0]["chars"] == 12  # 濾掉的列出，不沉默


def test_propose_max_styles_caps_and_reports():
    stats = [row("DFMingStd-W3", 10.0 + i, 1000 - i) for i in range(6)]
    styles, skipped = propose_styles(stats, min_chars=1, max_styles=3)
    assert len(styles) == 3
    assert len(skipped) == 3


def test_propose_name_collision_gets_suffix():
    stats = [
        row("DFMingStd-W3", 11.5, 9000),
        row("TimesNewRomanPSMT", 11.5, 500),   # 同映 宋 11.5 同級 → 名稱衝突
        row("PMingLiU", 11.5, 400),
    ]
    styles, _ = propose_styles(stats, min_chars=1, max_styles=9)
    assert len(styles) == 3  # 唯一鍵，不互相覆蓋
    assert len({n for n in styles}) == 3


def test_propose_unknown_font_notes_fallback():
    stats = [row("DFMingStd-W3", 11.5, 9000), row("PepitaMT", 9.0, 200)]
    styles, _ = propose_styles(stats, min_chars=1, max_styles=9)
    pepita = next(v for v in styles.values() if v["source_font"].startswith("PepitaMT"))
    assert "未識別" in pepita["note"]  # fallback 警告不沉默


# ---------- 掃描整合（fitz 造 PDF，Gate 4 獨立路徑） ----------

@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    import fitz

    path = tmp_path_factory.mktemp("refpdf") / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((30, 60), "Heading Line", fontname="hebo", fontsize=18)
    for i in range(8):
        page.insert_text((30, 100 + 14 * i), "body text row " * 4,
                         fontname="helv", fontsize=11)
    page.insert_text((30, 360), "tiny footnote", fontname="tiro", fontsize=8)
    doc.save(str(path))
    doc.close()
    return path


def test_scan_pdf_aggregates_spans(sample_pdf):
    result = scan_pdf(sample_pdf)
    assert result.page_count == 1
    fonts = {(r["font"], r["size"]) for r in result.stats}
    assert ("Helvetica", 11.0) in fonts
    assert ("Helvetica-Bold", 18.0) in fonts
    assert result.stats[0]["font"] == "Helvetica"  # chars 最多排最前
    assert result.colors[0]["hex"] == "#000000"


def test_extract_draft_no_book_text(sample_pdf):
    draft = extract_draft(sample_pdf, min_chars=5, max_styles=10)
    assert draft["pages"] == 1
    assert any(n.startswith("內文候選") for n in draft["paragraph_styles"])
    dumped = json.dumps(draft, ensure_ascii=False)
    assert "body text row" not in dumped  # 紅線：草稿不含 PDF 內文句
    assert "Heading Line" not in dumped


def test_cli_extract_styles(sample_pdf, tmp_path):
    from cjkfolio.cli import main

    out = tmp_path / "draft.json"
    assert main(["extract-styles", str(sample_pdf), "-o", str(out),
                 "--min-chars", "5"]) == 0
    draft = json.loads(out.read_text(encoding="utf-8"))
    assert draft["source_pdf"].endswith("sample.pdf")
    styles = draft["paragraph_styles"]
    assert all(set(v) == {"font_family", "font_weight", "size_pt", "source_font", "note"}
               for v in styles.values())
