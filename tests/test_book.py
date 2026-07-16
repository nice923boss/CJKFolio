"""書冊組裝（cjkfolio/book@1，Sprint 52）：多章文件串接為單一多主版文件。

覆蓋：book@1 schema 驗證、assemble 章首節首標記與主版覆寫優先序、template 不一致
／空章／章級 images 快速失敗、書冊級 images 透傳、組裝後 layout 節序、CLI assemble。
測試素材一律自擬（版權紅線）。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.book import BookError, assemble_book, book_from_dict, load_book
from cjkfolio.document import load_document, save_document
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


def write_chapter(dirpath, name, master, paragraphs, template_id="neizai-zhengli",
                  images=None):
    """寫一個自擬章文件 JSON，回傳檔名（相對 dirpath）。"""
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": f"{name}（章題）", "template": template_id, "master": master},
        "paragraphs": paragraphs,
    }
    if images is not None:
        data["images"] = images
    path = Path(dirpath) / f"{name}.doc.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"{name}.doc.json"


def make_book_dict(chapters, title="整理練習（全書）", images=None):
    data = {
        "schema": "cjkfolio/book@1",
        "meta": {"title": title, "template": "neizai-zhengli"},
        "chapters": chapters,
    }
    if images is not None:
        data["images"] = images
    return data


def write_two_chapters(tmp_path):
    c1 = write_chapter(tmp_path, "part", "B-部扉", [
        {"text": "第一部", "style": "標籤-篇序小標"},
        {"text": "把留下的東西安放好", "style": "部扉大標-明體W9"},
    ])
    c2 = write_chapter(tmp_path, "body", "A-內文版", [
        {"text": "整" * 10, "style": "內文-明體直排"},
        {"text": "理" * 10, "style": "內文-明體直排"},
    ])
    return c1, c2


# ---------- book@1 schema 驗證 ----------

def test_book_schema_validation_fast_fail():
    with pytest.raises(BookError, match="schema"):
        book_from_dict({"schema": "cjkfolio/book@9", "meta": {}, "chapters": []})
    with pytest.raises(BookError, match="chapters"):
        book_from_dict(make_book_dict([]))
    with pytest.raises(BookError, match="path"):
        book_from_dict(make_book_dict([{"master": "A-內文版"}]))
    with pytest.raises(BookError, match="master"):
        book_from_dict(make_book_dict([{"path": "c.doc.json", "master": ""}]))
    with pytest.raises(BookError, match="title"):
        book_from_dict({
            "schema": "cjkfolio/book@1",
            "meta": {"title": "", "template": "neizai-zhengli"},
            "chapters": [{"path": "c.doc.json"}],
        })


def test_book_from_dict_and_load(tmp_path):
    c1, c2 = write_two_chapters(tmp_path)
    data = make_book_dict([{"path": c1}, {"path": c2, "master": "A-內文版"}])
    book = book_from_dict(data)
    assert book.title == "整理練習（全書）"
    assert [ch.path for ch in book.chapters] == [c1, c2]
    assert book.chapters[0].master is None
    assert book.chapters[1].master == "A-內文版"
    p = tmp_path / "book.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert load_book(p).title == book.title


# ---------- assemble：章首標記與優先序 ----------

def test_assemble_marks_chapter_heads(tmp_path):
    c1, c2 = write_two_chapters(tmp_path)
    book = book_from_dict(make_book_dict([{"path": c1}, {"path": c2}]))
    doc = assemble_book(book, base_dir=tmp_path)
    assert doc.title == "整理練習（全書）"
    assert doc.master == "B-部扉"  # 首章節首主版
    assert len(doc.paragraphs) == 4
    assert doc.paragraphs[0].master == "B-部扉"   # 章首標記＝章文件 meta.master
    assert doc.paragraphs[1].master is None
    assert doc.paragraphs[2].master == "A-內文版"
    assert doc.paragraphs[3].master is None
    assert doc.paragraphs[0].text == "第一部"
    assert doc.paragraphs[3].text == "理" * 10


def test_assemble_master_override_precedence(tmp_path):
    c1, _ = write_two_chapters(tmp_path)
    # 章文件首段已帶節首標記，且章文件 meta.master 為 B
    c3 = write_chapter(tmp_path, "marked", "B-部扉", [
        {"text": "整" * 4, "style": "內文-明體直排", "master": "A-內文版"},
    ])
    # 無覆寫：保留首段既有標記（A），不退回 meta.master（B）
    doc = assemble_book(book_from_dict(make_book_dict(
        [{"path": c1}, {"path": c3}])), base_dir=tmp_path)
    assert doc.paragraphs[2].master == "A-內文版"
    # 顯式覆寫：chapters[].master 蓋過既有標記與 meta.master
    doc2 = assemble_book(book_from_dict(make_book_dict(
        [{"path": c1}, {"path": c3, "master": "C-個案扉頁"}])), base_dir=tmp_path)
    assert doc2.paragraphs[2].master == "C-個案扉頁"


def test_assemble_preserves_interior_section_marks(tmp_path):
    ch = write_chapter(tmp_path, "chapter", "B-部扉", [
        {"text": "第一部", "style": "標籤-篇序小標"},
        {"text": "整" * 6, "style": "內文-明體直排", "master": "A-內文版"},
    ])
    doc = assemble_book(book_from_dict(make_book_dict([{"path": ch}])),
                        base_dir=tmp_path)
    assert doc.paragraphs[0].master == "B-部扉"
    assert doc.paragraphs[1].master == "A-內文版"  # 章內節照搬


def test_assemble_page_no_passthrough(tmp_path):
    ch = write_chapter(tmp_path, "toc", "D-目錄", [
        {"text": "安放與整理的十個提問", "style": "目錄-篇章條目", "page_no": "169"},
    ])
    doc = assemble_book(book_from_dict(make_book_dict([{"path": ch}])),
                        base_dir=tmp_path)
    assert doc.paragraphs[0].page_no == "169"


# ---------- assemble：快速失敗 ----------

def test_assemble_template_mismatch_raises(tmp_path):
    c1, _ = write_two_chapters(tmp_path)
    alien = write_chapter(tmp_path, "alien", "A-內文版",
                          [{"text": "字", "style": "內文-明體直排"}],
                          template_id="別的模版")
    book = book_from_dict(make_book_dict([{"path": c1}, {"path": alien}]))
    with pytest.raises(BookError, match="模版"):
        assemble_book(book, base_dir=tmp_path)


def test_assemble_empty_chapter_raises(tmp_path):
    empty = write_chapter(tmp_path, "empty", "A-內文版", [])
    book = book_from_dict(make_book_dict([{"path": empty}]))
    with pytest.raises(BookError, match="段落"):
        assemble_book(book, base_dir=tmp_path)


def test_assemble_missing_chapter_file_raises(tmp_path):
    book = book_from_dict(make_book_dict([{"path": "不存在.doc.json"}]))
    with pytest.raises(BookError, match="不存在"):
        assemble_book(book, base_dir=tmp_path)


def test_assemble_chapter_level_images_rejected(tmp_path):
    (tmp_path / "p.png").write_bytes(b"")  # 不會被開啟，僅測 schema 拒絕
    ch = write_chapter(tmp_path, "figs", "G-圖文版",
                       [{"text": "客廳一景", "style": "旁注-手札圖注"}],
                       images=[{"path": "p.png", "page": 1}])
    book = book_from_dict(make_book_dict([{"path": ch}]))
    with pytest.raises(BookError, match="images"):
        assemble_book(book, base_dir=tmp_path)


def test_book_level_images_passthrough(tmp_path):
    ch = write_chapter(tmp_path, "figs", "G-圖文版",
                       [{"text": "客廳一景", "style": "旁注-手札圖注"}])
    book = book_from_dict(make_book_dict(
        [{"path": ch}], images=[{"path": "photo.png", "page": 1}]))
    doc = assemble_book(book, base_dir=tmp_path)
    assert len(doc.images) == 1
    assert doc.images[0].path == "photo.png" and doc.images[0].page == 1


# ---------- 組裝後 layout：節序即章序 ----------

def test_assembled_layout_page_masters(template, tmp_path):
    c1, c2 = write_two_chapters(tmp_path)
    doc = assemble_book(book_from_dict(make_book_dict(
        [{"path": c1}, {"path": c2}])), base_dir=tmp_path)
    layout = layout_document(doc, template)
    assert layout.violations == []
    assert [(p.number, p.master) for p in layout.pages] == [
        (1, "B-部扉"), (2, "A-內文版"),
    ]


def test_assembled_doc_roundtrips_via_save(template, tmp_path):
    c1, c2 = write_two_chapters(tmp_path)
    doc = assemble_book(book_from_dict(make_book_dict(
        [{"path": c1}, {"path": c2}])), base_dir=tmp_path)
    out = tmp_path / "assembled.doc.json"
    save_document(doc, out)
    again = load_document(out)
    assert [p.master for p in again.paragraphs] == [
        "B-部扉", None, "A-內文版", None,
    ]
    assert [p.master for p in layout_document(again, template).pages] == [
        "B-部扉", "A-內文版",
    ]


# ---------- CLI ----------

def test_cli_assemble(tmp_path):
    from cjkfolio.cli import main

    c1, c2 = write_two_chapters(tmp_path)
    book_path = tmp_path / "book.json"
    book_path.write_text(json.dumps(make_book_dict(
        [{"path": c1}, {"path": c2}]), ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "assembled.doc.json"
    assert main(["assemble", str(book_path), "-o", str(out)]) == 0
    doc = load_document(out)
    assert doc.title == "整理練習（全書）"
    assert [p.master for p in doc.paragraphs] == ["B-部扉", None, "A-內文版", None]


# ---------- 全書級端到端（需字型） ----------

@needs_fonts
def test_book_export_end_to_end(template, tmp_path):
    """五節全書（D 目錄＋B 部扉＋A 內文＋C 欄標頁＋G 圖文）單一 PDF/X，節序即頁序。"""
    fitz = pytest.importorskip("fitz")
    from PIL import Image

    from cjkfolio.pdf_writer import export_pdf

    Image.new("L", (60, 40), 120).save(tmp_path / "photo.png")
    toc = write_chapter(tmp_path, "toc", "D-目錄", [
        {"text": "把留下的東西安放好", "style": "目錄-篇章條目", "page_no": "3"},
    ])
    part = write_chapter(tmp_path, "part", "B-部扉", [
        {"text": "第一部", "style": "標籤-篇序小標"},
        {"text": "把留下的東西安放好", "style": "部扉大標-明體W9"},
    ])
    body = write_chapter(tmp_path, "body", "A-內文版", [
        {"text": "搬進老公寓的第一天，我先替物品找位置，再替自己找位置。",
         "style": "內文-明體直排"},
    ])
    case = write_chapter(tmp_path, "case", "C-個案扉頁", [
        {"text": "案例速寫", "style": "個案欄標-黑W7"},
        {"text": "把家還原成生活的樣子", "style": "個案扉頁大標-NotoSans"},
    ])
    figs = write_chapter(tmp_path, "figs", "G-圖文版", [
        {"text": "客廳一景", "style": "旁注-手札圖注"},
    ])
    book = book_from_dict(make_book_dict(
        [{"path": toc}, {"path": part}, {"path": body}, {"path": case},
         {"path": figs}],
        images=[{"path": "photo.png", "page": 5}],
    ))
    doc = assemble_book(book, base_dir=tmp_path)
    layout = layout_document(doc, template)
    assert [p.master for p in layout.pages] == [
        "D-目錄", "B-部扉", "A-內文版", "C-個案扉頁", "G-圖文版",
    ]
    out = tmp_path / "book.pdf"
    result = export_pdf(doc, template, out, image_base_dir=tmp_path)
    assert result.violations == []
    assert result.page_count == 5
    assert result.images_placed == 1
    pdf = fitz.open(str(out))
    assert pdf.page_count == 5
    for ch in "把留下的東西安放好":  # 部扉大標（頁 2，直排逐字抽取逐字檢查）
        assert ch in pdf[1].get_text()
    assert "3" in pdf[0].get_text()  # 目錄頁碼記號
    assert pdf[4].get_images(), "G 圖文頁應嵌入影像 XObject"
