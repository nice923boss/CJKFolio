"""節式混向文件（Sprint 53）：書寫方向降到節層級，直排內文與橫排版權頁同冊。

覆蓋：LayoutPage.vertical 逐頁方向、首節方向＝LayoutResult.vertical、同節混向仍
快速失敗、齊行統計只計直排頁、兩後端混向幾何（頁 1 直排行軸、頁 2 橫排基線與
CIP 細框）、book 組裝含 F 章端到端。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs, master="A-內文版", title="自擬樣張"):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": title, "template": "neizai-zhengli", "master": master},
        "paragraphs": paragraphs,
    })


def make_mixed_doc(title="整理練習"):
    """直排內文節＋橫排版權頁節（F 入冊的最小混向文件，全自擬）。"""
    return make_doc(
        [
            {"text": "搬進老公寓的第一天，我先替物品找位置。", "style": "內文-明體直排"},
            {"text": "整理練習（自擬書目）", "style": "版權頁-CIP橫排",
             "master": "F-版權頁"},
            {"text": "作者：某某某", "style": "版權頁-CIP橫排"},
            {"text": "ISBN 978-000-0000-00-0", "style": "版權頁-CIP橫排"},
        ],
        title=title,
    )


# ---------- layout：逐頁方向 ----------

def test_mixed_sections_flag_direction_per_page(template):
    layout = layout_document(make_mixed_doc(), template)
    assert layout.violations == []
    assert [(p.number, p.master, p.vertical) for p in layout.pages] == [
        (1, "A-內文版", True), (2, "F-版權頁", False),
    ]
    assert layout.vertical is True  # 首節方向（逐頁以 LayoutPage.vertical 為準）


def test_horizontal_first_section_flags_result(template):
    doc = make_doc(
        [
            {"text": "整理練習（自擬書目）", "style": "版權頁-CIP橫排"},
            {"text": "直排跋文自此起。", "style": "內文-明體直排", "master": "A-內文版"},
        ],
        master="F-版權頁",
    )
    layout = layout_document(doc, template)
    assert layout.vertical is False  # 首節橫排
    assert [p.vertical for p in layout.pages] == [False, True]


def test_single_direction_docs_unchanged(template):
    v = layout_document(make_doc(
        [{"text": "直排內文。", "style": "內文-明體直排"}]), template)
    assert v.vertical is True and [p.vertical for p in v.pages] == [True]
    h = layout_document(make_doc(
        [{"text": "橫排資料", "style": "版權頁-CIP橫排"}], master="F-版權頁"), template)
    assert h.vertical is False and [p.vertical for p in h.pages] == [False]


def test_mixed_within_one_section_still_raises(template):
    doc = make_doc([
        {"text": "橫排列", "style": "版權頁-CIP橫排"},
        {"text": "直排列", "style": "內文-明體直排"},  # 無節首標記＝同節
    ], master="F-版權頁")
    with pytest.raises(ValueError, match="混用書寫方向"):
        layout_document(doc, template)


def test_justify_stats_count_vertical_pages_only(template):
    body = {"text": "搬進這間老公寓的第一天，我把行李箱立在玄關，先替每一件物品找位置。",
            "style": "內文-明體直排"}
    base = layout_document(make_doc([body]), template)
    mixed = layout_document(make_doc([
        dict(body),
        {"text": "整理練習（自擬書目）", "style": "版權頁-CIP橫排", "master": "F-版權頁"},
        {"text": "作者：某某某", "style": "版權頁-CIP橫排"},
    ]), template)
    assert mixed.justify_stats == base.justify_stats  # 橫排節不入齊行統計


# ---------- 兩後端：混向幾何（需字型） ----------

@needs_fonts
def test_export_mixed_direction_geometry(template, tmp_path):
    """頁 1 直排（同欄字墨 cx 一致、y 遞增）、頁 2 橫排（同行基線 y 一致、x 遞增）
    ＋CIP 細框（橫排原件）只在 F 頁出現。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    out = tmp_path / "mixed.pdf"
    result = export_pdf(make_mixed_doc(), template, out, footer=False)
    assert result.violations == []
    assert result.page_count == 2
    pdf = fitz.open(str(out))

    def chars_of(page_idx):
        return [
            c for b in pdf[page_idx].get_text("rawdict")["blocks"]
            for ln in b.get("lines", []) for s in ln.get("spans", [])
            for c in s.get("chars", [])
        ]

    p1 = chars_of(0)[:6]  # 頁 1 首欄前幾字：直排＝cx 一致、y 遞增
    cxs = [(c["bbox"][0] + c["bbox"][2]) / 2 for c in p1]
    ys = [c["bbox"][1] for c in p1]
    assert max(cxs) - min(cxs) < 2.0
    assert all(a < b for a, b in zip(ys, ys[1:]))

    p2 = chars_of(1)[:6]  # 頁 2 首行前幾字：橫排＝基線 y 一致、x 遞增
    y1s = [c["bbox"][3] for c in p2]
    xs = [c["bbox"][0] for c in p2]
    assert max(y1s) - min(y1s) < 2.0
    assert all(a < b for a, b in zip(xs, xs[1:]))

    # CIP 細框（re 描邊向量）只在 F 頁
    assert not [d for d in pdf[0].get_drawings() if d["items"] and d["items"][0][0] == "re"]
    assert [d for d in pdf[1].get_drawings() if d["items"] and d["items"][0][0] == "re"]


@needs_fonts
def test_render_mixed_direction_two_pages(template, tmp_path):
    from cjkfolio.render import render_document

    result = render_document(make_mixed_doc(), template, tmp_path, dpi=150)
    assert result.violations == []
    assert [p.name for p in result.paths] == ["page-001.png", "page-002.png"]


# ---------- book 組裝含 F 章 ----------

@needs_fonts
def test_book_with_cip_chapter_end_to_end(template, tmp_path):
    import json

    from cjkfolio.book import assemble_book, book_from_dict
    from cjkfolio.pdf_writer import export_pdf

    body = tmp_path / "body.doc.json"
    body.write_text(json.dumps({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "章", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "直排內文一段。", "style": "內文-明體直排"}],
    }, ensure_ascii=False), encoding="utf-8")
    cip = tmp_path / "cip.doc.json"
    cip.write_text(json.dumps({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "版權頁", "template": "neizai-zhengli", "master": "F-版權頁"},
        "paragraphs": [{"text": "整理練習（自擬書目）", "style": "版權頁-CIP橫排"}],
    }, ensure_ascii=False), encoding="utf-8")
    book = book_from_dict({
        "schema": "cjkfolio/book@1",
        "meta": {"title": "整理練習（全書）", "template": "neizai-zhengli"},
        "chapters": [{"path": "body.doc.json"}, {"path": "cip.doc.json"}],
    })
    doc = assemble_book(book, base_dir=tmp_path)
    layout = layout_document(doc, template)
    assert [(p.master, p.vertical) for p in layout.pages] == [
        ("A-內文版", True), ("F-版權頁", False),
    ]
    result = export_pdf(doc, template, tmp_path / "book.pdf")
    assert result.violations == [] and result.page_count == 2
