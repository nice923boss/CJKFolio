"""多層目錄階層與章內小節（Sprint 108，GAPS #44 (c)(e)、#56 乙(6)）測試。

Sprint 85 的自動目錄只有一層：條目樣式單一（entry_style），且只列 path 章的
章首頁，章內小節無從列入。本檔釘死的是**層級的宣告與對映**：

- 層級一律由使用者顯式宣告（manifest `chapters[].toc_level`、章文件段落
  `toc_title`／`toc_level`），引擎不從字型、字級或樣式名反推標題階層
  （§4.4 分工鐵律：標題語意屬使用者、幾何屬引擎）。
- 每一層各有自己的條目樣式（`generate_toc.entry_styles`），縮排階層由該層
  樣式的 `head_offset_chars` 表達，不新增任何幾何機制。
- 用到未宣告樣式的層級＝快速失敗，不沉默落回第一層樣式。

測試素材一律自擬（版權紅線）。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.book import BookError, book_from_dict
from cjkfolio.document import (
    DocumentError, Paragraph, document_from_dict, document_to_dict)
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template
from cjkfolio.toc import assemble_book_with_toc, toc_items

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"

L1_STYLE = "目錄-篇章條目"
L2_STYLE = "目錄-部名"  # 借既有樣式當第二層（本檔只驗層級對映，不驗字形）


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def write_chapter(dirpath, name, master, paragraphs):
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": name, "template": "neizai-zhengli", "master": master},
        "paragraphs": paragraphs,
    }
    (Path(dirpath) / f"{name}.doc.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return f"{name}.doc.json"


def toc_chapter(entry_styles=None, heading="目錄"):
    gen = {"entry_style": L1_STYLE, "master": "D-目錄",
           "heading": heading, "heading_style": "目錄-部名"}
    if heading is None:
        del gen["heading"], gen["heading_style"]
    if entry_styles is not None:
        gen["entry_styles"] = entry_styles
    return {"generate_toc": gen}


def book_dict(chapters):
    return {
        "schema": "cjkfolio/book@1",
        "meta": {"title": "多層目錄書", "template": "neizai-zhengli"},
        "chapters": chapters,
    }


def body(text="整" * 40):
    return {"text": text, "style": "內文-明體直排"}


def section(text, toc_title, toc_level=None):
    """章內小節首段：宣告 toc_title 即列入目錄。"""
    p = {"text": text, "style": "內文-明體直排", "toc_title": toc_title}
    if toc_level is not None:
        p["toc_level"] = toc_level
    return p


def two_chapter_book(tmp_path, entry_styles=None):
    """兩章，各一個宣告小節：章＝第一層、小節＝第二層（預設承章 +1）。"""
    a = write_chapter(tmp_path, "a", "A-內文版", [
        body(), section("整" * 40, "第一節　安放"), body()])
    b = write_chapter(tmp_path, "b", "A-內文版", [
        body(), section("整" * 40, "第二節　留白")])
    return book_from_dict(book_dict([
        toc_chapter(entry_styles=entry_styles),
        {"path": a, "toc_title": "第一章"},
        {"path": b, "toc_title": "第二章"},
    ]))


# ---------- 解析：document@2 段落層級宣告 ----------

def test_paragraph_toc_title_parsed_and_round_trips():
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": "t", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [
            {"text": "一", "style": "內文-明體直排"},
            {"text": "二", "style": "內文-明體直排", "toc_title": "小節", "toc_level": 3},
        ],
    }
    doc = document_from_dict(data)
    assert doc.paragraphs[0].toc_title is None and doc.paragraphs[0].toc_level is None
    assert doc.paragraphs[1].toc_title == "小節" and doc.paragraphs[1].toc_level == 3
    out = document_to_dict(doc)
    assert out["paragraphs"][0] == {"text": "一", "style": "內文-明體直排"}
    assert out["paragraphs"][1]["toc_title"] == "小節"
    assert out["paragraphs"][1]["toc_level"] == 3
    assert document_from_dict(out).paragraphs == doc.paragraphs


def test_paragraph_toc_fast_fail():
    def doc_with(para):
        return {
            "schema": "cjkfolio/document@2",
            "meta": {"title": "t", "template": "x", "master": "A-內文版"},
            "paragraphs": [para],
        }

    with pytest.raises(DocumentError, match="toc_title 需為非空字串"):
        document_from_dict(doc_with({"text": "一", "style": "s", "toc_title": ""}))
    with pytest.raises(DocumentError, match="toc_level 需為 ≥1 的整數"):
        document_from_dict(doc_with(
            {"text": "一", "style": "s", "toc_title": "節", "toc_level": 0}))
    with pytest.raises(DocumentError, match="toc_level 需搭 toc_title"):
        document_from_dict(doc_with({"text": "一", "style": "s", "toc_level": 2}))
    with pytest.raises(DocumentError, match="需 schema document@2"):
        v1 = doc_with({"text": "一", "style": "s", "toc_title": "節"})
        v1["schema"] = "cjkfolio/document@1"
        document_from_dict(v1)


# ---------- 解析：book@1 章層級與逐層樣式 ----------

def test_chapter_toc_level_defaults_to_one():
    b = book_from_dict(book_dict([
        toc_chapter(), {"path": "a.doc.json", "toc_title": "第一章"},
        {"path": "b.doc.json", "toc_title": "第一節", "toc_level": 2}]))
    assert b.chapters[1].toc_level == 1
    assert b.chapters[2].toc_level == 2


def test_entry_styles_parsed():
    b = book_from_dict(book_dict([
        toc_chapter(entry_styles={"2": L2_STYLE}), {"path": "a.doc.json"}]))
    assert b.chapters[0].toc_spec.entry_style == L1_STYLE
    assert b.chapters[0].toc_spec.entry_styles == {2: L2_STYLE}


def test_book_toc_level_fast_fail():
    with pytest.raises(BookError, match="toc_level 需為 ≥1 的整數"):
        book_from_dict(book_dict([
            toc_chapter(), {"path": "a.doc.json", "toc_title": "第一章", "toc_level": 0}]))
    with pytest.raises(BookError, match="toc_level 需搭 toc_title"):
        book_from_dict(book_dict([
            toc_chapter(), {"path": "a.doc.json", "toc_level": 2}]))
    with pytest.raises(BookError, match="entry_styles 的鍵需為 ≥2 的層級整數字串"):
        book_from_dict(book_dict([toc_chapter(entry_styles={"1": L2_STYLE})]))
    with pytest.raises(BookError, match="entry_styles 的鍵需為 ≥2 的層級整數字串"):
        book_from_dict(book_dict([toc_chapter(entry_styles={"二": L2_STYLE})]))
    with pytest.raises(BookError, match="entry_styles 的值需為非空字串"):
        book_from_dict(book_dict([toc_chapter(entry_styles={"2": ""})]))
    with pytest.raises(BookError, match="entry_styles 需為物件"):
        book_from_dict(book_dict([toc_chapter(entry_styles=[L2_STYLE])]))


# ---------- 層級對映：條目樣式與序 ----------

def test_sections_listed_after_their_chapter_in_document_order(template, tmp_path):
    book = two_chapter_book(tmp_path, entry_styles={"2": L2_STYLE})
    items = toc_items(book, template, base_dir=tmp_path)
    assert [(it.title, it.level) for it in items] == [
        ("第一章", 1), ("第一節　安放", 2), ("第二章", 1), ("第二節　留白", 2)]


def test_entry_style_per_level(template, tmp_path):
    book = two_chapter_book(tmp_path, entry_styles={"2": L2_STYLE})
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    entries = [p for p in doc.paragraphs[:5] if p.page_no is not None]
    assert [p.style for p in entries] == [L1_STYLE, L2_STYLE, L1_STYLE, L2_STYLE]


def test_section_level_defaults_to_chapter_level_plus_one(template, tmp_path):
    """章宣告第二層時，其小節預設落第三層（承所屬章 +1，非固定 2）。"""
    a = write_chapter(tmp_path, "a", "A-內文版", [body(), section("整" * 40, "小節")])
    book = book_from_dict(book_dict([
        toc_chapter(entry_styles={"2": L2_STYLE, "3": L2_STYLE}),
        {"path": a, "toc_title": "第一節", "toc_level": 2}]))
    assert [it.level for it in toc_items(book, template, base_dir=tmp_path)] == [2, 3]


def test_explicit_paragraph_toc_level_overrides_default(template, tmp_path):
    a = write_chapter(tmp_path, "a", "A-內文版", [
        body(), section("整" * 40, "小節", toc_level=4)])
    book = book_from_dict(book_dict([
        toc_chapter(entry_styles={"4": L2_STYLE}), {"path": a, "toc_title": "第一章"}]))
    assert [it.level for it in toc_items(book, template, base_dir=tmp_path)] == [1, 4]


def test_section_in_unlisted_chapter_still_listed(template, tmp_path):
    """章本身不列入（無 toc_title）不影響其小節列入：宣告是逐項顯式的。"""
    a = write_chapter(tmp_path, "a", "A-內文版", [body(), section("整" * 40, "小節")])
    book = book_from_dict(book_dict([
        toc_chapter(entry_styles={"2": L2_STYLE}), {"path": a}]))
    assert [(it.title, it.level)
            for it in toc_items(book, template, base_dir=tmp_path)] == [("小節", 2)]


def test_missing_level_style_fast_fails(template, tmp_path):
    """用到未宣告樣式的層級即快速失敗，不沉默落回第一層樣式。"""
    book = two_chapter_book(tmp_path)  # 有第二層條目卻未宣告 entry_styles
    with pytest.raises(BookError, match="第 2 層無條目樣式"):
        toc_items(book, template, base_dir=tmp_path)
    with pytest.raises(BookError, match="第 2 層無條目樣式"):
        assemble_book_with_toc(book, template, base_dir=tmp_path)


# ---------- 頁碼：小節頁碼＝該小節首次出現的書頁 ----------

def test_section_page_is_its_own_page_not_chapter_head(template, tmp_path):
    """小節條目的頁碼指到小節本身所在頁，不是章首頁（跨頁章才驗得出）。"""
    long_body = body("整" * 40)
    paras = [long_body] * 14 + [section("整" * 40, "後段小節")] + [long_body]
    a = write_chapter(tmp_path, "a", "A-內文版", paras)
    book = book_from_dict(book_dict([
        toc_chapter(entry_styles={"2": L2_STYLE}), {"path": a, "toc_title": "第一章"}]))
    items = toc_items(book, template, base_dir=tmp_path)
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    layout = layout_document(doc, template)

    # 獨立算一次：小節首段在組裝後段落列的索引 → 其首次出現的版面頁
    section_idx = next(i for i, p in enumerate(doc.paragraphs)
                       if p.toc_title == "後段小節")
    want = next(page.number for page in layout.pages
                for pl in page.placed if pl.para_idx == section_idx)
    assert items[1].page == want
    assert items[1].page > items[0].page, "後段小節須落在章首頁之後"


def test_section_page_no_stamped_and_pagination_stable(template, tmp_path):
    book = two_chapter_book(tmp_path, entry_styles={"2": L2_STYLE})
    items = toc_items(book, template, base_dir=tmp_path)
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    stamped = [p for p in doc.paragraphs if p.page_no is not None]
    assert len(stamped) == 4, "兩章各含一小節＝四條目"
    assert [p.page_no for p in stamped] == [str(it.page) for it in items]
    # 條目數為先驗定值（宣告數，非分頁推導），故兩趟穩定：條目段的 page_no
    # 為非流排載體，剝除後頁數不變
    from dataclasses import replace
    stripped = replace(doc, paragraphs=tuple(
        replace(p, page_no=None) for p in doc.paragraphs))
    assert len(layout_document(stripped, template).pages) == \
        len(layout_document(doc, template).pages)


def test_first_page_offset_applies_to_sections(template, tmp_path):
    book = two_chapter_book(tmp_path, entry_styles={"2": L2_STYLE})
    base = toc_items(book, template, base_dir=tmp_path, first_page=1)
    shifted = toc_items(book, template, base_dir=tmp_path, first_page=30)
    assert [it.page for it in shifted] == [it.page + 29 for it in base]


# ---------- 縮排階層走既有 head_offset_chars（零新幾何機制） ----------

def test_level_indent_comes_from_style_head_offset(tmp_path):
    """第二層條目較第一層縮退，且縮退量恰為兩樣式 head_offset_chars 之差。

    用第二本書的模版（其 目錄-小節條目 為本 Sprint 為多層目錄新增的第二層樣式），
    因為階層縮排是資料層的事：引擎不認識「層級」，只認識該層條目掛的樣式。
    """
    template = load_template(ROOT / "templates" / "jiejiao-manxing.json")
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": "c", "template": "jiejiao-manxing", "master": "甲-內文"},
        "paragraphs": [
            {"text": "走" * 30, "style": "內文-宋體直排"},
            {"text": "走" * 30, "style": "內文-宋體直排", "toc_title": "小節"},
        ],
    }
    (tmp_path / "c.doc.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    book = book_from_dict({
        "schema": "cjkfolio/book@1",
        "meta": {"title": "階層目錄書", "template": "jiejiao-manxing"},
        "chapters": [
            {"generate_toc": {
                "heading": "目次", "heading_style": "目錄-標題",
                "entry_style": "目錄-條目", "master": "丙-目錄",
                "entry_styles": {"2": "目錄-小節條目"}}},
            {"path": "c.doc.json", "toc_title": "第一章"},
        ],
    })
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    layout = layout_document(doc, template)
    slots = {}
    for pl in layout.pages[0].placed:
        para = doc.paragraphs[pl.para_idx]
        if para.page_no is not None and para.style not in slots:
            slots[para.style] = pl.line.start_slot

    l1 = template.paragraph_styles["目錄-條目"]
    l2 = template.paragraph_styles["目錄-小節條目"]
    assert slots["目錄-小節條目"] - slots["目錄-條目"] == \
        (l2.head_offset_chars + l2.indent_chars) - (l1.head_offset_chars + l1.indent_chars)
    assert slots["目錄-小節條目"] > slots["目錄-條目"], "第二層條目須較第一層縮退"


# ---------- 編輯不得讓小節從目錄消失 ----------

def test_editing_preserves_paragraph_toc_declaration(template):
    """在編輯器裡改小節標題的字，目錄宣告須跟著留下（同 page_no／master 慣例）。

    Gate 3 同類掃描：editing 的段落重建原以列舉欄位建新 Paragraph，新增欄位會被
    靜默丟掉＝改一個字就把該小節移出目錄；改以 replace 保欄位，日後加欄位亦不重演。
    """
    from cjkfolio.document import Document
    from cjkfolio.editing import (
        DocCursor, DocRange, change_paragraph_style, delete_range, insert_text,
        merge_paragraph, split_paragraph,
    )

    para = Paragraph("把速度調慢", "內文-明體直排", toc_title="小節", toc_level=2)
    doc = Document(title="t", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(para, Paragraph("後段", "內文-明體直排")))

    for edited in (
        insert_text(doc, DocCursor(0, 5), "一點"),
        delete_range(doc, DocRange(0, 0, 2)),
        change_paragraph_style(doc, 0, "章節小標-黑體"),
        split_paragraph(doc, DocCursor(0, 2)),
        merge_paragraph(doc, 1),
    ):
        assert edited.paragraphs[0].toc_title == "小節"
        assert edited.paragraphs[0].toc_level == 2
    # 分段：新生的後半段不繼承目錄身分（同 page_no 慣例，身分留前段）
    assert split_paragraph(doc, DocCursor(0, 2)).paragraphs[1].toc_title is None


# ---------- 真實樣本：第二本書《街角慢行》的兩層目錄 ----------

@pytest.mark.skipif(
    not (ROOT / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)
def test_second_book_sample_two_level_toc():
    """樣本書冊的兩層目錄：小節條目掛第二層樣式，頁碼指到小節自身所在頁。"""
    from cjkfolio.book import load_book

    samples = ROOT / "samples"
    template = load_template(ROOT / "templates" / "jiejiao-manxing.json")
    book = load_book(samples / "book-jiejiao-manxing.json")
    items = toc_items(book, template, base_dir=samples, first_page=1)
    doc = assemble_book_with_toc(book, template, base_dir=samples, first_page=1)
    layout = layout_document(doc, template)

    entries = [p for p in doc.paragraphs if p.page_no is not None]
    assert [p.style for p in entries] == [
        "目錄-條目" if it.level == 1 else "目錄-小節條目" for it in items]

    # 獨立算一次：每條小節條目的頁碼＝該小節首段首次出現的版面頁
    first_page_of = {}
    for page in layout.pages:
        for placed in page.placed:
            first_page_of.setdefault(placed.para_idx, page.number)
    for item in (it for it in items if it.level == 2):
        idx = next(i for i, p in enumerate(doc.paragraphs)
                   if p.toc_title == item.title)
        assert item.page == first_page_of[idx], f"小節「{item.title}」頁碼不符"
