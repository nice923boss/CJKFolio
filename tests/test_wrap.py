"""圖文繞排（Sprint 89，Phase 4）測試。

覆蓋：排除區幾何純函式（rect → 行槽區間＋字軸 pt 區間，對表真書 PDF 53 R 半頁
一手量測）、line_window 字格裁切（圖在字軸後段→行縮短、前段→行首推移、整欄被
擋→空窗）、document@2 相容擴充 PlacedImage.wrap／wrap_margin_mm 解析驗證與序列化、
flow_pages 逐行排除區流排、layout_with_wrap 兩趟（逐頁主版取得→帶排除區重排）、
兩後端端到端（字形不落入圖框）。wrap=False 為預設＝既有輸出零變更（回歸鐵律）。

繞排規則以真書《內在整理》179 頁全掃為據（tools/measure_wrap_pages.py，8 個
wrap-partial 樣本）：圖矩形跨數欄，受影響欄文字避開圖的縱向範圍且同欄不跨圖續排。
真書圖文間隙 1〜3 字格不等（作者自由放置），本產品以 wrap_margin_mm 表達，不硬編。
測試素材一律自擬（版權紅線），真書僅用於幾何對表數值。
"""
from pathlib import Path

import pytest
from PIL import Image

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.engine import Exclusion, ParagraphSpec, flow_pages, line_window
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template
from cjkfolio.wrap import image_exclusion, layout_with_wrap, page_exclusions

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

# 真書 PDF 53 R 半頁（右頁）一手量測：內嵌小圖 rect 與受影響欄
# （tools/measure_wrap_pages.py；圖 x 76.64〜195.66／y 289.01〜467.54，
# 受影響欄行軸 193.25／170.25／147.25／124.25／101.25／78.25＝A-內文版 slot 7〜12）
REF_RECT = (76.64, 289.01, 195.66, 467.54)
REF_SLOTS = (7, 13)          # 半開區間
ADVANCE_PT = 12.08           # A-內文版字距（§1 實測）
CHARS_PER_LINE = 32


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


@pytest.fixture(scope="module")
def master_a(template):
    return template.masters["A-內文版"]


def make_doc(paragraphs, images=None, master="A-內文版"):
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": "繞排樣張", "template": "neizai-zhengli", "master": master},
        "paragraphs": paragraphs,
    }
    if images is not None:
        data["images"] = images
    return document_from_dict(data)


def long_body(chars: int = 600):
    return [{"text": "整理是一場與過去的對話" * (chars // 11 + 1),
             "style": "內文-明體直排"}]


# ── 排除區幾何純函式（對表真書一手量測） ──────────────────────────────


def test_exclusion_slots_match_reference_page(template, master_a):
    """真書 PDF 53 R 半頁的圖 rect → A-內文版 slot 7〜12（量測 6 欄逐欄吻合）。"""
    ex = image_exclusion(REF_RECT, template, master_a, book_number=2)
    assert (ex.slot_lo, ex.slot_hi) == REF_SLOTS


def test_exclusion_span_is_relative_to_top_margin(template, master_a):
    """字軸區間相對天頭（32.49mm＝92.09pt）。"""
    ex = image_exclusion(REF_RECT, template, master_a, book_number=2)
    assert ex.span_lo_pt == pytest.approx(289.01 - 92.0975, abs=0.01)
    assert ex.span_hi_pt == pytest.approx(467.54 - 92.0975, abs=0.01)


def test_window_shortens_line_before_image(template, master_a):
    """圖佔字軸後段 → 受影響行可用字格自天頭起縮短（真書：滿行 32 → 16 格）。"""
    ex = image_exclusion(REF_RECT, template, master_a, book_number=2)
    assert line_window((ex,), 7, 1, ADVANCE_PT, CHARS_PER_LINE) == (0, 16)


def test_window_margin_matches_reference_gap(template, master_a):
    """wrap_margin 一字格時與真書逐格吻合（真書該 6 欄末字落 cell 14，end＝15）。"""
    ex = image_exclusion(REF_RECT, template, master_a, book_number=2,
                         margin_pt=ADVANCE_PT)
    assert line_window((ex,), 7, 1, ADVANCE_PT, CHARS_PER_LINE) == (0, 15)


def test_window_shifts_line_start_after_image(template, master_a):
    """圖佔字軸前段（天頭側）→ 行首推移到圖之後（真書 PDF 60 形態）。"""
    rect = (77.63, 92.58, 271.52, 229.05)
    ex = image_exclusion(rect, template, master_a, book_number=2)
    start, end = line_window((ex,), ex.slot_lo, 1, ADVANCE_PT, CHARS_PER_LINE)
    assert (start, end) == (12, 32)   # (229.05−92.0975)/12.08＝11.34 → ceil 12


def test_window_untouched_slot_is_full(template, master_a):
    ex = image_exclusion(REF_RECT, template, master_a, book_number=2)
    assert line_window((ex,), 0, 1, ADVANCE_PT, CHARS_PER_LINE) == (0, CHARS_PER_LINE)


def test_window_full_column_blocked_is_empty(template, master_a):
    """圖覆蓋整欄字軸 → 空窗（該行槽不排字）。"""
    rect = (76.64, 80.0, 195.66, 490.0)
    ex = image_exclusion(rect, template, master_a, book_number=2)
    start, end = line_window((ex,), 8, 1, ADVANCE_PT, CHARS_PER_LINE)
    assert start == end


def test_window_takes_larger_side(template, master_a):
    """圖落字軸中段 → v1 取較大的一段（另一段不排字，GAPS 誠實登記）。"""
    rect = (76.64, 92.0975 + 5 * ADVANCE_PT, 195.66, 92.0975 + 9 * ADVANCE_PT)
    ex = image_exclusion(rect, template, master_a, book_number=2)
    assert line_window((ex,), 8, 1, ADVANCE_PT, CHARS_PER_LINE) == (9, 32)


def test_exclusion_slots_mirror_on_left_page(template, master_a):
    """鏡像主版：同一 rect 在左頁（奇數書頁）對到不同行槽（版心左右互換）。"""
    right = image_exclusion(REF_RECT, template, master_a, book_number=2)
    left = image_exclusion(REF_RECT, template, master_a, book_number=3)
    assert (left.slot_lo, left.slot_hi) != (right.slot_lo, right.slot_hi)


def test_exclusion_outside_body_is_none(template, master_a):
    """圖完全落在版心行軸範圍外（書口外側）→ 無排除區。"""
    assert image_exclusion((380.0, 100.0, 410.0, 200.0), template, master_a,
                           book_number=2) is None


def test_line_window_multi_slot_line_uses_any_overlap(template, master_a):
    """跨多行槽的大級數行：任一行槽與圖重疊即受裁切（保守）。"""
    ex = image_exclusion(REF_RECT, template, master_a, book_number=2)
    assert line_window((ex,), 6, 2, ADVANCE_PT, CHARS_PER_LINE) == (0, 16)


# ── document@2 相容擴充：wrap 欄位 ───────────────────────────────────


def test_wrap_defaults_false_and_not_serialized():
    doc = make_doc(long_body(), [{"path": "a.png", "page": 1,
                                  "rect": [76.6, 289.0, 195.7, 467.5]}])
    assert doc.images[0].wrap is False
    assert doc.images[0].wrap_margin_mm == 0.0
    assert "wrap" not in document_to_dict(doc)["images"][0]


def test_wrap_roundtrip():
    raw = {"path": "a.png", "page": 1, "rect": [76.6, 289.0, 195.7, 467.5],
           "wrap": True, "wrap_margin_mm": 4.26}
    doc = make_doc(long_body(), [raw])
    assert doc.images[0].wrap is True
    assert doc.images[0].wrap_margin_mm == pytest.approx(4.26)
    out = document_to_dict(doc)["images"][0]
    assert out["wrap"] is True and out["wrap_margin_mm"] == pytest.approx(4.26)


def test_wrap_requires_rect():
    """槽式圖（figure 保留區）不支援繞排 → 快速失敗（v1 限 rect 圖框）。"""
    with pytest.raises(DocumentError, match="wrap"):
        make_doc(long_body(), [{"path": "a.png", "page": 1, "wrap": True}])


def test_wrap_type_guard():
    with pytest.raises(DocumentError, match="wrap"):
        make_doc(long_body(), [{"path": "a.png", "page": 1,
                                "rect": [10.0, 10.0, 20.0, 20.0], "wrap": "yes"}])


def test_wrap_margin_non_negative():
    with pytest.raises(DocumentError, match="wrap_margin_mm"):
        make_doc(long_body(), [{"path": "a.png", "page": 1,
                                "rect": [10.0, 10.0, 20.0, 20.0],
                                "wrap": True, "wrap_margin_mm": -1.0}])


# ── flow_pages 逐行排除區流排 ────────────────────────────────────────


def test_flow_pages_without_exclusions_is_unchanged():
    """無排除區＝既有流排行為（逐行改寫的等價守門）。"""
    specs = [ParagraphSpec(text="整理" * 200, style="內文", advance_pt=ADVANCE_PT)]
    plain = flow_pages(specs, CHARS_PER_LINE, 13)
    with_arg = flow_pages(specs, CHARS_PER_LINE, 13, exclusions={})
    assert [[(pl.slot, pl.line.start_slot, pl.line.cap, len(pl.line.cells))
             for pl in page] for page in plain] == \
           [[(pl.slot, pl.line.start_slot, pl.line.cap, len(pl.line.cells))
             for pl in page] for page in with_arg]


def test_flow_pages_applies_exclusion_to_page():
    specs = [ParagraphSpec(text="整理" * 300, style="內文", advance_pt=ADVANCE_PT)]
    ex = Exclusion(slot_lo=2, slot_hi=4, span_lo_pt=16 * ADVANCE_PT,
                   span_hi_pt=32 * ADVANCE_PT)
    pages = flow_pages(specs, CHARS_PER_LINE, 13, exclusions={1: (ex,)})
    caps = {pl.slot: pl.line.cap for pl in pages[0]}
    assert caps[2] == 16 and caps[3] == 16
    assert caps[0] == CHARS_PER_LINE - 2   # 段首縮排 2
    assert caps[4] == CHARS_PER_LINE
    assert all(pl.line.cap == CHARS_PER_LINE for pl in pages[1] if pl.slot not in (0,))


def test_flow_pages_skips_fully_blocked_slot():
    specs = [ParagraphSpec(text="整理" * 300, style="內文", advance_pt=ADVANCE_PT)]
    ex = Exclusion(slot_lo=1, slot_hi=3, span_lo_pt=0.0,
                   span_hi_pt=CHARS_PER_LINE * ADVANCE_PT)
    pages = flow_pages(specs, CHARS_PER_LINE, 13, exclusions={1: (ex,)})
    assert {pl.slot for pl in pages[0]}.isdisjoint({1, 2})


def test_flow_pages_all_slots_blocked_fails_fast():
    specs = [ParagraphSpec(text="整理" * 50, style="內文", advance_pt=ADVANCE_PT)]
    ex = Exclusion(slot_lo=0, slot_hi=13, span_lo_pt=0.0,
                   span_hi_pt=CHARS_PER_LINE * ADVANCE_PT)
    with pytest.raises(ValueError, match="繞排"):
        flow_pages(specs, CHARS_PER_LINE, 13, exclusions={1: (ex,), 2: (ex,)})


# ── layout_with_wrap 端到端 ─────────────────────────────────────────


def test_layout_with_wrap_shortens_affected_lines(template):
    doc = make_doc(long_body(700), [{"path": "a.png", "page": 1,
                                     "rect": list(REF_RECT), "wrap": True}])
    result = layout_with_wrap(doc, template, first_page=2)
    caps = {pl.slot: pl.line.cap for pl in result.pages[0].placed}
    for slot in range(*REF_SLOTS):
        assert caps[slot] == 16, f"slot {slot} 未被繞排裁切"
    assert caps[6] == CHARS_PER_LINE
    assert not result.violations


def test_layout_without_wrap_flag_is_identical(template):
    """wrap=False（預設）→ 與無圖 layout 逐行相同（既有輸出零變更）。"""
    body = long_body(700)
    plain = layout_document(make_doc(body), template)
    with_img = layout_with_wrap(
        make_doc(body, [{"path": "a.png", "page": 1, "rect": list(REF_RECT)}]),
        template, first_page=2)
    assert _fingerprint(plain) == _fingerprint(with_img)


def test_layout_with_wrap_reflows_more_pages(template):
    """繞排吃掉字格 → 同樣內容佔更多頁（不沉默丟字）。"""
    body = long_body(700)
    plain = layout_document(make_doc(body), template)
    wrapped = layout_with_wrap(
        make_doc(body, [{"path": "a.png", "page": 1, "rect": list(REF_RECT),
                         "wrap": True}]), template, first_page=2)
    assert _cell_count(wrapped) == _cell_count(plain)
    assert len(wrapped.pages) >= len(plain.pages)


def test_layout_with_wrap_horizontal_master_unaffected(template):
    """橫排頁 v1 不繞排（GAPS 誠實登記）：wrap 圖不改變橫排流排。"""
    body = [{"text": "版權頁測試文字" * 20, "style": "版權頁-CIP橫排"}]
    plain = layout_document(make_doc(body, master="F-版權頁"), template)
    wrapped = layout_with_wrap(
        make_doc(body, [{"path": "a.png", "page": 1, "rect": list(REF_RECT),
                         "wrap": True}], master="F-版權頁"), template)
    assert _fingerprint(plain) == _fingerprint(wrapped)


def test_page_exclusions_keyed_by_layout_page(template):
    doc = make_doc(long_body(700), [{"path": "a.png", "page": 2,
                                     "rect": list(REF_RECT), "wrap": True}])
    layout = layout_document(doc, template)
    ex = page_exclusions(doc, layout.pages, template, first_page=1)
    assert set(ex) == {2}


def _fingerprint(result):
    return [[(pl.slot, pl.line.start_slot, pl.line.cap,
              "".join(c.text for c in pl.line.cells)) for pl in page.placed]
            for page in result.pages]


def _cell_count(result):
    return sum(len(pl.line.cells) for page in result.pages for pl in page.placed)


# ── 兩後端端到端 ────────────────────────────────────────────────────


@needs_fonts
def test_export_wrapped_text_avoids_image_rect(tmp_path):
    """PDF 端到端：受繞排頁的字形無一落入圖框（＋出血偏移）。"""
    import fitz

    from cjkfolio.pdf_writer import export_pdf

    img = tmp_path / "photo.png"
    Image.new("L", (60, 40), 120).save(img)
    doc_path = tmp_path / "doc.json"
    doc = make_doc(long_body(700), [{"path": "photo.png", "page": 1,
                                     "rect": list(REF_RECT), "wrap": True}])
    out = tmp_path / "out.pdf"
    export_pdf(doc, load_template(TEMPLATE), out, font_dir=FONT_DIR,
               image_base_dir=tmp_path, first_page=2)
    assert doc_path or True
    bleed = 3 * 72.0 / 25.4
    page = fitz.open(out)[0]
    box = fitz.Rect(REF_RECT[0] + bleed, REF_RECT[1] + bleed,
                    REF_RECT[2] + bleed, REF_RECT[3] + bleed)
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for sp in line["spans"]:
                r = fitz.Rect(sp["bbox"])
                assert not r.intersects(box), f"字形落入圖框：{sp['bbox']}"
