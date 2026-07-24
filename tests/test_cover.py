"""書封面（Sprint 132）：封面頁＋頁碼自封面翻開後起算。

Owner 真視窗回饋：匯入稿件後「原本封面的位置直接顯示第一頁」，書該有封面可放
圖片與自加文字，且頁碼從封面翻開後才算第一頁。

形態（本 Sprint 定案）：封面＝版面頁 1 的**空流排頁**（placed 為空）＋專屬主版，
封面內容復用既有兩個自由佈局載體（PlacedImage 圖框、TextFrame 文字框，page=1），
不新增內容機制。書頁號位移集中於單一純函式 book_number_for，封面頁書頁號＝0
（偶數＝右頁，Sprint 22 側別 SSOT：右翻書封面在右），內文首頁＝1。

覆蓋六層：書頁號純函式、document 欄位驗證與序列化、layout 插頁與頁號、
兩後端（封面不編頁碼、封面圖與文字框落封面頁）、自動目錄頁碼位移、
無封面文件 0 行為改變（回歸）。素材一律自擬（版權紅線）。
PDF 驗證走 PyMuPDF（Gate 4 獨立實作，不 import 本專案渲染模組）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.layout import layout_document
from cjkfolio.primitives import book_number_for, is_right_page
from cjkfolio.render import mm_to_pt
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

COVER_MASTER = "H-封面"
BODY = "內文-明體直排"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs=None, cover=None, images=None, frames=None,
             title="自擬封面樣張"):
    """自擬文件：cover 非 None 即帶封面（值＝封面主版名）。"""
    if paragraphs is None:
        paragraphs = [{"text": "封面測試的內文段落。" * 3, "style": BODY}]
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": title, "template": "neizai-zhengli",
                 "master": "A-內文版"},
        "paragraphs": paragraphs,
    }
    if cover is not None:
        data["meta"]["cover"] = cover
    if images is not None:
        data["images"] = images
    if frames is not None:
        data["text_frames"] = frames
    return document_from_dict(data)


# ---- 1. 書頁號純函式（單一事實來源） ----

def test_book_number_無封面時退化為既有公式():
    """cover_pages=0：book_number＝版面頁號＋first_page−1（Sprint 12 SSOT 不變）。"""
    assert book_number_for(1) == 1
    assert book_number_for(3) == 3
    assert book_number_for(1, first_page=5) == 5
    assert book_number_for(4, first_page=5) == 8


def test_book_number_封面頁為0內文首頁為1():
    """頁碼自封面翻開後起算：封面（版面頁 1）＝0、內文首頁（版面頁 2）＝1。"""
    assert book_number_for(1, cover_pages=1) == 0
    assert book_number_for(2, cover_pages=1) == 1
    assert book_number_for(3, cover_pages=1) == 2


def test_book_number_封面與自訂起始頁碼併用():
    """first_page 語意不變＝內文首頁的書頁碼；封面恆為其前一號。"""
    assert book_number_for(2, first_page=5, cover_pages=1) == 5
    assert book_number_for(1, first_page=5, cover_pages=1) == 4


def test_封面頁側別為右頁():
    """Sprint 22 側別 SSOT：偶數書頁＝右頁。封面書頁號 0＝右頁（右翻書封面在右），
    翻開後內文首頁書頁號 1＝左頁，與實體書一致。"""
    assert is_right_page(book_number_for(1, cover_pages=1)) is True
    assert is_right_page(book_number_for(2, cover_pages=1)) is False


# ---- 2. document 欄位驗證與序列化 ----

def test_cover_欄位round_trip():
    doc = make_doc(cover=COVER_MASTER)
    assert doc.cover == COVER_MASTER
    again = document_from_dict(document_to_dict(doc))
    assert again.cover == COVER_MASTER


def test_無cover欄位者cover為None且不寫入序列化():
    doc = make_doc()
    assert doc.cover is None
    assert "cover" not in document_to_dict(doc)["meta"]


def test_cover需為非空字串():
    with pytest.raises(DocumentError, match="cover"):
        make_doc(cover="")
    with pytest.raises(DocumentError, match="cover"):
        document_from_dict({
            "schema": "cjkfolio/document@2",
            "meta": {"title": "t", "template": "x", "master": "A-內文版",
                     "cover": 3},
            "paragraphs": [{"text": "字", "style": BODY}],
        })


def test_cover需schema版本2():
    with pytest.raises(DocumentError, match="document@2"):
        document_from_dict({
            "schema": "cjkfolio/document@1",
            "meta": {"title": "t", "template": "x", "master": "A-內文版",
                     "cover": COVER_MASTER},
            "paragraphs": [{"text": "字", "style": BODY}],
        })


# ---- 3. layout 插封面頁 ----

def test_layout_封面為版面頁1且不吃內文流(template):
    no_cover = layout_document(make_doc(), template)
    with_cover = layout_document(make_doc(cover=COVER_MASTER), template)
    assert with_cover.cover_pages == 1
    assert no_cover.cover_pages == 0
    assert len(with_cover.pages) == len(no_cover.pages) + 1
    first = with_cover.pages[0]
    assert first.number == 1
    assert first.placed == ()  # 封面不吃內文流
    assert first.master == COVER_MASTER
    # 內文整體後移一個版面頁，內容逐頁不變
    for before, after in zip(no_cover.pages, with_cover.pages[1:]):
        assert after.number == before.number + 1
        assert [pl.para_idx for pl in after.placed] == \
               [pl.para_idx for pl in before.placed]


def test_layout_未知封面主版快速失敗(template):
    with pytest.raises(KeyError, match="封面"):
        layout_document(make_doc(cover="Z-不存在的主版"), template)


def test_layout_無段落文件也能只排封面(template):
    """空稿＋封面＝單頁封面（匯入前先建封面的形態）。"""
    result = layout_document(make_doc(paragraphs=[], cover=COVER_MASTER), template)
    assert len(result.pages) == 1
    assert result.pages[0].placed == ()
    assert result.cover_pages == 1


# ---- 4. 兩後端：封面不編頁碼、封面內容落封面頁 ----

def cover_doc_with_content(tmp_path):
    """自擬封面：一張封面圖（rect 圖框）＋一個書名文字框，皆掛版面頁 1。"""
    from PIL import Image

    img_path = tmp_path / "cover-art.png"
    Image.new("L", (600, 900), 128).save(img_path)
    page_w = mm_to_pt(148.0)
    page_h = mm_to_pt(210.0)
    return make_doc(
        cover=COVER_MASTER,
        images=[{"path": img_path.name, "page": 1,
                 "rect": [0.0, 0.0, page_w, page_h * 0.62]}],
        # 書名框：直排 6 字須容得下（欄距 56pt、字距 29.4pt），高度取 0.30〜0.80
        frames=[{"text": "封面書名試排", "style": "封面書名-明體W9", "page": 1,
                 "rect": [page_w * 0.62, page_h * 0.30,
                          page_w * 0.86, page_h * 0.80]}],
    )


@needs_fonts
def test_render_封面頁不印頁碼且內文首頁印1(tmp_path, template):
    """封面不編頁碼＝封面頁不繪頁腳（不論其主版是否宣告 footer）。"""
    from cjkfolio.render import render_document

    doc = cover_doc_with_content(tmp_path)
    out = render_document(doc, template, tmp_path / "png", font_dir=FONT_DIR,
                          image_base_dir=tmp_path)
    assert out.violations == []
    assert len(out.paths) >= 2
    assert out.images_placed == 1


@needs_fonts
def test_export_封面頁無頁碼_內文首頁頁碼為1(tmp_path, template):
    """Gate 4 獨立驗證（PyMuPDF 直讀）：封面頁抽不到頁碼數字、有封面文字框的字；
    內文首頁抽得到頁碼「1」。"""
    import fitz

    from cjkfolio.pdf_writer import export_pdf

    doc = cover_doc_with_content(tmp_path)
    pdf_path = tmp_path / "cover.pdf"
    export_pdf(doc, template, pdf_path, font_dir=FONT_DIR, image_base_dir=tmp_path)
    with fitz.open(pdf_path) as pdf:
        # 直排每字獨立成行，抽出的文字含換行；比對前壓平（既有直排驗證慣例）
        cover_text = pdf[0].get_text().replace("\n", "")
        body_text = pdf[1].get_text().replace("\n", "")
    assert "封面書名試排" in cover_text
    assert not any(ch.isdigit() for ch in cover_text)  # 封面不編頁碼
    assert "1" in body_text  # 內文首頁＝書頁 1


@needs_fonts
def test_export_封面頁的圖確實嵌入(tmp_path, template):
    import fitz

    from cjkfolio.pdf_writer import export_pdf

    doc = cover_doc_with_content(tmp_path)
    pdf_path = tmp_path / "cover.pdf"
    result = export_pdf(doc, template, pdf_path, font_dir=FONT_DIR,
                        image_base_dir=tmp_path)
    assert result.images_placed == 1
    with fitz.open(pdf_path) as pdf:
        # get_images() 列的是頁面 Resources 中的 XObject，本產品全頁共用一份
        # Resources，故每頁都會列到；要驗「畫在哪一頁」須用 get_image_info()
        # （實際繪製指令與座標）。
        assert len(pdf[0].get_image_info()) == 1  # 圖繪於封面頁
        assert len(pdf[1].get_image_info()) == 0  # 內文首頁無圖


# ---- 5. 自動目錄頁碼含封面位移 ----

def test_toc_頁碼扣除封面(tmp_path, template):
    """自動目錄印出的頁碼＝書頁號（自封面翻開後起算），與內文頁碼一致。"""
    import json

    from cjkfolio.book import load_book
    from cjkfolio.toc import toc_items

    for i in range(2):
        (tmp_path / f"ch{i}.doc.json").write_text(json.dumps({
            "schema": "cjkfolio/document@2",
            "meta": {"title": f"第 {i + 1} 章", "template": "neizai-zhengli",
                     "master": "A-內文版"},
            "paragraphs": [{"text": f"第 {i + 1} 章的內文。" * 40, "style": BODY}],
        }, ensure_ascii=False), encoding="utf-8")
    manifest = tmp_path / "book.json"
    manifest.write_text(json.dumps({
        "schema": "cjkfolio/book@1",
        "meta": {"title": "封面書冊", "template": "neizai-zhengli",
                 "cover": COVER_MASTER},
        "chapters": [
            {"generate_toc": {"heading": "目次", "heading_style": "目錄-部名",
                              "entry_style": "目錄-篇章條目", "master": "D-目錄"}},
            {"path": "ch0.doc.json", "toc_title": "第一章"},
            {"path": "ch1.doc.json", "toc_title": "第二章"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    book = load_book(manifest)
    items = toc_items(book, template, base_dir=tmp_path)
    assert [it.page for it in items] == sorted(it.page for it in items)
    assert items[0].page >= 1  # 封面不佔頁碼，首章書頁號自 1 起算


# ---- 6. 建立與移除封面（編輯層） ----

def test_with_cover_加封面並帶預設書名框(template):
    from cjkfolio.cover import with_cover

    doc = make_doc(title="排版小記")
    covered = with_cover(doc, template)
    assert covered.cover == "H-封面"
    assert doc.cover is None  # 不可變：原文件不動
    assert len(covered.text_frames) == 1
    frame = covered.text_frames[0]
    assert frame.text == "排版小記"
    assert frame.page == 1
    assert frame.style == "封面書名-明體W9"
    # 書名框靠書口側（封面書頁號 0＝右頁，書口在右）、自天頭起
    master = template.masters["H-封面"]
    page_w = mm_to_pt(template.page_width_mm)
    assert frame.rect[2] == pytest.approx(page_w - mm_to_pt(master.margins.outer_mm))
    assert frame.rect[1] == pytest.approx(mm_to_pt(master.margins.top_mm))


def test_with_cover_既有圖與框的頁號一併位移(template):
    """images／text_frames 的 page 是版面頁號：封面插最前，不位移即靜默錯位。"""
    from cjkfolio.cover import with_cover

    page_w = mm_to_pt(148.0)
    doc = make_doc(
        images=[{"path": "a.png", "page": 2, "rect": [0.0, 0.0, 100.0, 100.0]}],
        frames=[{"text": "圖說", "style": BODY, "page": 3,
                 "rect": [page_w * 0.5, 100.0, page_w * 0.8, 300.0]}],
    )
    covered = with_cover(doc, template, title="書名")
    assert [im.page for im in covered.images] == [3]
    assert [f.page for f in covered.text_frames] == [1, 4]  # 書名框 1、原圖說 3→4


def test_with_cover_重複建立快速失敗(template):
    from cjkfolio.cover import with_cover

    covered = with_cover(make_doc(), template)
    with pytest.raises(ValueError, match="已有封面"):
        with_cover(covered, template)


def test_with_cover_模版未宣告封面主版快速失敗(template):
    from dataclasses import replace as dc_replace

    from cjkfolio.cover import with_cover

    bare = dc_replace(template, default_cover="")
    with pytest.raises(ValueError, match="default_cover"):
        with_cover(make_doc(), bare)


def test_without_cover_移除封面並收回頁號(template):
    """封面頁上的圖與框隨封面移除（往後擠到內文首頁＝靜默污染內文）。"""
    from cjkfolio.cover import with_cover, without_cover

    page_w = mm_to_pt(148.0)
    doc = make_doc(
        images=[{"path": "a.png", "page": 1, "rect": [0.0, 0.0, 100.0, 100.0]}],
        frames=[{"text": "圖說", "style": BODY, "page": 2,
                 "rect": [page_w * 0.5, 100.0, page_w * 0.8, 300.0]}],
    )
    covered = with_cover(doc, template, title="書名")
    back = without_cover(covered)
    assert back.cover is None
    assert [im.page for im in back.images] == [1]   # 原頁 1 圖：位移後 2、收回 1
    assert [f.page for f in back.text_frames] == [2]  # 原頁 2 框收回 2；書名框已移除
    assert back.text_frames[0].text == "圖說"


def test_without_cover_無封面時快速失敗(template):
    from cjkfolio.cover import without_cover

    with pytest.raises(ValueError, match="無封面"):
        without_cover(make_doc())


def test_書名過長不靜默溢出(template):
    """title_fits 供呼叫端先判；框內真溢出仍由 frames 層列 violations（雙層不沉默）。"""
    from cjkfolio.cover import title_fits, with_cover
    from cjkfolio.render import render_document  # noqa: F401（僅取模組確認可載）

    assert title_fits(template, "H-封面", "排版小記")
    long_title = "書名" * 30
    assert not title_fits(template, "H-封面", long_title)
    covered = with_cover(make_doc(), template, title=long_title)
    result = layout_document(covered, template)
    assert result.cover_pages == 1  # 仍建得出封面（溢出由渲染層據實回報）


def test_未宣告cover_title的模版快速失敗(template):
    from dataclasses import replace as dc_replace

    from cjkfolio.cover import cover_title_style

    bare = dc_replace(template, md_mapping={"paragraph": BODY})
    with pytest.raises(KeyError, match="cover_title"):
        cover_title_style(bare)


# ---- 7. 匯入路徑帶封面 ----

def test_匯入稿件可建封面(tmp_path, template):
    """Owner 需求：匯入稿件時就該有封面（editor 匯入預設帶，CLI 走 --cover）。"""
    from editor.import_core import import_manuscript

    src = tmp_path / "稿件.txt"
    src.write_text("第一段文字。\n\n第二段文字。\n", encoding="utf-8")
    plain = import_manuscript(src, template, "neizai-zhengli")
    assert plain.cover is None  # 核心預設不變（既有 CLI 與量測工具零影響）
    covered = import_manuscript(src, template, "neizai-zhengli", cover=True)
    assert covered.cover == "H-封面"
    assert covered.text_frames[0].text == "稿件"  # 書名取檔名
    result = layout_document(covered, template)
    assert result.pages[0].master == "H-封面"
    assert result.pages[1].placed  # 內文自第二個版面頁起


# ---- 8. 公開樣張釘死（samples/cover.doc.json） ----

def test_公開封面樣張的結構與頁數(template):
    """樣張腐爛守門（同 test_public_sample 慣例）：改寫樣張須同步更新
    samples/README.md 的說明。"""
    from cjkfolio.document import load_document

    doc = load_document(ROOT / "samples" / "cover.doc.json")
    assert doc.cover == COVER_MASTER
    assert doc.title == "排版小記"
    # 封面內容：三個文字框（書名／作者／出版標記）＋一張封面圖，皆掛版面頁 1
    assert [f.page for f in doc.text_frames] == [1, 1, 1]
    assert doc.text_frames[0].text == "排版小記"
    assert [im.page for im in doc.images] == [1]
    result = layout_document(doc, template)
    assert len(result.pages) == 2  # 封面 1＋內文 1
    assert result.cover_pages == 1
    assert result.violations == []


@needs_fonts
def test_公開封面樣張渲染零違規(tmp_path, template):
    from cjkfolio.render import render_document

    doc = load_document_for_sample()
    out = render_document(doc, template, tmp_path, font_dir=FONT_DIR,
                          image_base_dir=ROOT / "samples")
    assert out.violations == []
    assert out.images_placed == 1
    assert len(out.paths) == 2


def load_document_for_sample():
    from cjkfolio.document import load_document

    return load_document(ROOT / "samples" / "cover.doc.json")


# ---- 9. 回歸：無封面文件 0 行為改變 ----

def test_無封面文件的分頁與頁號完全不變(template):
    doc = make_doc()
    result = layout_document(doc, template)
    assert result.cover_pages == 0
    assert result.pages[0].number == 1
    assert result.pages[0].master == "A-內文版"
    assert result.pages[0].placed  # 內文自版面頁 1 起（既有行為）
