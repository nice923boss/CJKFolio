"""目錄自動生成（cjkfolio/book@1 auto-TOC，Sprint 85）測試。

覆蓋：book@1 相容擴充（chapters[].toc_title、generate_toc 章）解析與快速失敗、
兩趟穩定分頁計算各章起始書頁號、page_no 填入不改分頁、first_page 位移、
heading 選配、無目錄章／空目錄章快速失敗、CLI assemble 自動目錄路徑。
測試素材一律自擬（版權紅線）。
"""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from cjkfolio.book import BookError, TocSpec, assemble_book, book_from_dict
from cjkfolio.document import load_document
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template
from cjkfolio.toc import TocItem, assemble_book_with_toc, toc_items

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def write_chapter(dirpath, name, master, paragraphs, template_id="neizai-zhengli"):
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": name, "template": template_id, "master": master},
        "paragraphs": paragraphs,
    }
    path = Path(dirpath) / f"{name}.doc.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return f"{name}.doc.json"


def toc_chapter(entry_style="目錄-篇章條目", master="D-目錄",
                heading="目錄", heading_style="目錄-部名"):
    gen = {"entry_style": entry_style, "master": master}
    if heading is not None:
        gen["heading"] = heading
        gen["heading_style"] = heading_style
    return {"generate_toc": gen}


def book_dict(chapters, title="自動目錄書"):
    return {
        "schema": "cjkfolio/book@1",
        "meta": {"title": title, "template": "neizai-zhengli"},
        "chapters": chapters,
    }


def first_page_with_master(layout, master_name):
    return next(p.number for p in layout.pages if p.master == master_name)


def make_content(tmp_path):
    """兩個自擬內容章：A 內文（多頁）、B 部扉。回傳 (a_file, b_file)。"""
    a = write_chapter(tmp_path, "a", "A-內文版",
                      [{"text": "整" * 40, "style": "內文-明體直排"}] * 3)
    b = write_chapter(tmp_path, "b", "B-部扉", [
        {"text": "第二部", "style": "標籤-篇序小標"},
        {"text": "安放與整理", "style": "部扉大標-明體W9"},
    ])
    return a, b


# ---------- 解析與快速失敗 ----------

def test_parse_toc_title_and_spec():
    b = book_from_dict(book_dict([
        toc_chapter(),
        {"path": "a.doc.json", "toc_title": "第一章"},
    ]))
    assert b.chapters[0].path is None
    assert b.chapters[0].toc_spec == TocSpec("目錄-篇章條目", "D-目錄", "目錄", "目錄-部名")
    assert b.chapters[1].toc_title == "第一章"
    assert b.chapters[1].toc_spec is None


def test_parse_toc_spec_without_heading():
    b = book_from_dict(book_dict([toc_chapter(heading=None), {"path": "a.doc.json"}]))
    assert b.chapters[0].toc_spec == TocSpec("目錄-篇章條目", "D-目錄", None, None)


def test_parse_fast_fail():
    with pytest.raises(BookError, match="path 與 generate_toc"):
        book_from_dict(book_dict([
            {"path": "a.doc.json", "generate_toc": {"entry_style": "e", "master": "m"}}]))
    with pytest.raises(BookError, match="entry_style"):
        book_from_dict(book_dict([{"generate_toc": {"master": "D-目錄"}}]))
    with pytest.raises(BookError, match="master"):
        book_from_dict(book_dict([{"generate_toc": {"entry_style": "目錄-篇章條目"}}]))
    with pytest.raises(BookError, match="heading_style"):
        book_from_dict(book_dict([
            {"generate_toc": {"entry_style": "e", "master": "m", "heading": "目錄"}}]))
    with pytest.raises(BookError, match="toc_title"):
        book_from_dict(book_dict([toc_chapter(), {"path": "a.doc.json", "toc_title": 123}]))
    with pytest.raises(BookError, match="至多一個"):
        book_from_dict(book_dict([toc_chapter(), toc_chapter(), {"path": "a.doc.json"}]))
    with pytest.raises(BookError, match="自動目錄章不可有 toc_title"):
        book_from_dict(book_dict([
            {"generate_toc": {"entry_style": "e", "master": "m"}, "toc_title": "x"}]))


def test_assemble_plain_rejects_toc_chapter(tmp_path):
    a, _ = make_content(tmp_path)
    book = book_from_dict(book_dict([toc_chapter(), {"path": a, "toc_title": "第一章"}]))
    with pytest.raises(BookError, match="自動目錄章"):
        assemble_book(book, base_dir=tmp_path)


# ---------- 頁碼計算：兩趟穩定分頁 ----------

def test_toc_items_match_layout(template, tmp_path):
    a, b = make_content(tmp_path)
    book = book_from_dict(book_dict([
        toc_chapter(),
        {"path": a, "toc_title": "第一章　安放"},
        {"path": b, "toc_title": "第二部"},
    ]))
    items = toc_items(book, template, base_dir=tmp_path)
    assert [it.title for it in items] == ["第一章　安放", "第二部"]
    # 獨立驗證：各章起始書頁號＝組裝後 layout 首個該主版頁（節式主版指派）
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    layout = layout_document(doc, template)
    assert items[0].page == first_page_with_master(layout, "A-內文版")
    assert items[1].page == first_page_with_master(layout, "B-部扉")
    # 目錄章本身為首節（D-目錄，頁 1）
    assert layout.pages[0].master == "D-目錄"


def test_toc_stamps_page_no_and_stable(template, tmp_path):
    a, b = make_content(tmp_path)
    book = book_from_dict(book_dict([
        toc_chapter(),
        {"path": a, "toc_title": "第一章"},
        {"path": b, "toc_title": "第二部"},
    ]))
    items = toc_items(book, template, base_dir=tmp_path)
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    entries = [p for p in doc.paragraphs if p.style == "目錄-篇章條目"]
    assert [p.page_no for p in entries] == [str(items[0].page), str(items[1].page)]
    assert [p.text for p in entries] == ["第一章", "第二部"]
    heading = doc.paragraphs[0]
    assert heading.style == "目錄-部名" and heading.page_no is None
    # 穩定性：填入 page_no（純載體）不改分頁，與剝除 page_no 版本頁數相同
    stripped = replace(doc, paragraphs=tuple(
        replace(p, page_no=None) for p in doc.paragraphs))
    assert len(layout_document(stripped, template).pages) == \
        len(layout_document(doc, template).pages)
    # 且目錄頁碼記號有被 layout 認出（非空）
    assert layout_document(doc, template).toc_marks


def test_toc_first_page_offset(template, tmp_path):
    a, b = make_content(tmp_path)
    book = book_from_dict(book_dict([
        toc_chapter(), {"path": a, "toc_title": "一"}, {"path": b, "toc_title": "二"}]))
    base = toc_items(book, template, base_dir=tmp_path, first_page=1)
    shifted = toc_items(book, template, base_dir=tmp_path, first_page=30)
    assert [it.page for it in shifted] == [it.page + 29 for it in base]


def test_toc_heading_optional_first_entry_marks_section(template, tmp_path):
    a, _ = make_content(tmp_path)
    book = book_from_dict(book_dict([
        toc_chapter(heading=None), {"path": a, "toc_title": "第一章"}]))
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    assert doc.paragraphs[0].style == "目錄-篇章條目"
    assert doc.paragraphs[0].master == "D-目錄"
    layout = layout_document(doc, template)
    assert layout.pages[0].master == "D-目錄"


# ---------- 快速失敗 ----------

def test_no_toc_chapter_raises(template, tmp_path):
    a, _ = make_content(tmp_path)
    book = book_from_dict(book_dict([{"path": a, "toc_title": "第一章"}]))
    with pytest.raises(BookError, match="generate_toc"):
        toc_items(book, template, base_dir=tmp_path)
    with pytest.raises(BookError, match="generate_toc"):
        assemble_book_with_toc(book, template, base_dir=tmp_path)


def test_empty_toc_no_heading_raises(template, tmp_path):
    a, _ = make_content(tmp_path)
    book = book_from_dict(book_dict([toc_chapter(heading=None), {"path": a}]))
    with pytest.raises(BookError, match="無 heading"):
        assemble_book_with_toc(book, template, base_dir=tmp_path)


def test_toc_heading_only_when_no_listed(template, tmp_path):
    a, _ = make_content(tmp_path)
    book = book_from_dict(book_dict([toc_chapter(), {"path": a}]))  # a 無 toc_title
    items = toc_items(book, template, base_dir=tmp_path)
    assert items == ()
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    assert [p for p in doc.paragraphs if p.style == "目錄-篇章條目"] == []
    assert doc.paragraphs[0].style == "目錄-部名"


# ---------- CLI ----------

def test_cli_assemble_auto_toc(tmp_path):
    from cjkfolio.cli import main

    a, b = make_content(tmp_path)
    bd = book_dict([
        toc_chapter(), {"path": a, "toc_title": "第一章"}, {"path": b, "toc_title": "第二部"}])
    bp = tmp_path / "book.json"
    bp.write_text(json.dumps(bd, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "asm.doc.json"
    assert main(["assemble", str(bp), "-o", str(out), "--template", str(TEMPLATE)]) == 0
    doc = load_document(out)
    entries = [p for p in doc.paragraphs if p.style == "目錄-篇章條目"]
    assert len(entries) == 2
    assert all(p.page_no is not None for p in entries)
    # 缺 --template：含自動目錄章須報錯（非 0）
    assert main(["assemble", str(bp), "-o", str(out)]) == 2


def test_cli_assemble_plain_unchanged(tmp_path):
    """無自動目錄章的書冊：assemble 行為與 Sprint 52 一致（不需 --template）。"""
    from cjkfolio.cli import main

    a, b = make_content(tmp_path)
    bd = book_dict([{"path": a}, {"path": b}])
    bp = tmp_path / "plain.json"
    bp.write_text(json.dumps(bd, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "plain.doc.json"
    assert main(["assemble", str(bp), "-o", str(out)]) == 0
    doc = load_document(out)
    assert [p.master for p in doc.paragraphs][:1] == ["A-內文版"]


# ---------- 端到端（需字型）：自動頁碼烘焙進 PDF ----------

@pytest.mark.skipif(
    not (ROOT / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)
def test_auto_toc_export_end_to_end(template, tmp_path):
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    a, b = make_content(tmp_path)
    book = book_from_dict(book_dict([
        toc_chapter(),
        {"path": a, "toc_title": "第一章　安放"},
        {"path": b, "toc_title": "第二部"},
    ]))
    items = toc_items(book, template, base_dir=tmp_path)
    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    out = tmp_path / "auto-toc.pdf"
    result = export_pdf(doc, template, out, image_base_dir=tmp_path)
    assert result.violations == []
    pdf = fitz.open(str(out))
    # 目錄頁（頁 1）應含各章自動計算頁碼數字
    toc_text = pdf[0].get_text()
    for it in items:
        assert str(it.page) in toc_text


def test_auto_toc_page_numbers_account_for_wrap(template, tmp_path):
    """帶 wrap 圖的書冊：條目頁碼須依繞排後的分頁（Sprint 103）。

    目錄兩趟分頁原走 layout_document，與兩渲染後端的 layout_with_wrap 不同源，
    故繞排把內文往後推時會印出比實際早的頁（實測差 1 頁）。
    """
    from PIL import Image

    from cjkfolio.wrap import layout_with_wrap

    photo = tmp_path / "photo.png"
    Image.new("L", (360, 270), 128).save(photo)
    body = [{"text": "整理一個房間先要決定的不是收納盒。" * 60,
             "style": "內文-明體直排"}]
    a = write_chapter(tmp_path, "wa", "A-內文版", body)
    b = write_chapter(tmp_path, "wb", "A-內文版", body)
    spec = book_dict([toc_chapter(), {"path": a, "toc_title": "第一章"},
                      {"path": b, "toc_title": "第二章"}])
    # 書冊層 wrap 圖：落在第二頁內文，繞排後把其後的內文往後推
    spec["images"] = [{"path": "photo.png", "page": 2,
                       "rect": [76.64, 180.0, 320.0, 540.0],
                       "wrap": True, "wrap_margin_mm": 4.0}]
    book = book_from_dict(spec)

    doc = assemble_book_with_toc(book, template, base_dir=tmp_path)
    printed = [int(p.page_no) for p in doc.paragraphs if p.page_no]

    layout = layout_with_wrap(doc, template)
    first_page_of = {}
    for page in layout.pages:
        for placed in page.placed:
            first_page_of.setdefault(placed.para_idx, page.number)
    body_starts = [first_page_of[i] for i in sorted(first_page_of) if i >= 3]

    assert printed == body_starts, (
        f"目錄印出 {printed}，繞排後實際章首頁 {body_starts}")
