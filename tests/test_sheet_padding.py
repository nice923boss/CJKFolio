"""裝訂補頁（Sprint 144）：內文頁數補足一張紙對折的倍數。

Owner 需求：「假如最後一頁的頁碼並非 4 的倍數，也要增加空白頁使其成為 4 的倍數，
這樣才是正常的書冊印製紙張的數量。」實體書一張紙對折得 4 面，內文頁數非 4 的倍數
就湊不成整數張紙。

宣告在文件層（Document.sheet_pages，與 Document.cover 同層級：都宣告「這本書的
結構」、都增減版面頁、都不動網格幾何），不在模版層：兩份產品模版一宣告 4，41 個
單元測試的 1〜2 頁合成稿全被補成 4〜5 頁。程式庫預設不補（None），預設值 4 由編輯器
入口補上（editor.book_binding.with_binding），故使用者既有書檔開起來即生效。

覆蓋：補頁數學、補頁承末頁主版與方向、頁號連續、倍數含封面（Sprint 145）、欄位驗證與序列化、
兩後端補頁不編頁碼（PDF 走 PyMuPDF 獨立驗證＝Gate 4）、含補頁的 PDF 過 preflight、
編輯器層預設值、頁面面板縮圖頁腳、未宣告者 0 行為改變（回歸）。素材一律自擬。
"""
from pathlib import Path

import pytest

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

BODY = "內文-明體直排"
COVER_MASTER = "H-封面"
SHORT = [{"text": "裝訂補頁樣張：一段短文，只佔一頁。", "style": BODY}]
LONG = [{"text": "裝訂補頁樣張，長稿數頁，用來驗已是倍數者不補。" * 30,
         "style": BODY} for _ in range(4)]


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(sheet_pages=None, cover=None, paragraphs=None):
    """自擬文件；sheet_pages 非 None 即寫入 meta（0＝明說不補）。"""
    meta = {"title": "自擬裝訂樣張", "template": "neizai-zhengli",
            "master": "A-內文版"}
    if cover is not None:
        meta["cover"] = cover
    if sheet_pages is not None:
        meta["sheet_pages"] = sheet_pages
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": meta,
        "paragraphs": SHORT if paragraphs is None else paragraphs,
    })


# ---- 1. 補頁數學 ----

def test_未宣告者不補頁(template):
    """程式庫預設不補（CLI 與單元測試行為不變）。"""
    result = layout_document(make_doc(), template)
    assert not any(p.blank for p in result.pages)


def test_明說0者不補頁(template):
    """0 與 None 語意不同（明說不補 vs 未宣告），行為同為不補。"""
    assert not any(p.blank for p in layout_document(make_doc(0), template).pages)


@pytest.mark.parametrize("unit", [2, 3, 4, 8])
def test_補足至倍數且補的頁皆空白(template, unit):
    base = layout_document(make_doc(), template).pages
    result = layout_document(make_doc(unit), template)
    assert len(result.pages) % unit == 0
    assert len(result.pages) - len(base) == (-len(base)) % unit
    blanks = [p for p in result.pages if p.blank]
    assert len(blanks) == len(result.pages) - len(base)
    assert all(p.placed == () for p in blanks)
    # 補頁只加在末尾：既有內容頁逐頁不變（回歸）
    for before, after in zip(base, result.pages):
        assert after.number == before.number and not after.blank
        assert [pl.para_idx for pl in after.placed] == \
               [pl.para_idx for pl in before.placed]


def test_已是倍數者一頁不補(template):
    """內文頁數已是倍數＝補 0 頁，不整帖硬加。"""
    base = len(layout_document(make_doc(paragraphs=LONG), template).pages)
    assert base > 1, "夾具前提：長稿須多頁"
    result = layout_document(make_doc(base, paragraphs=LONG), template)
    assert len(result.pages) == base
    assert not any(p.blank for p in result.pages)


def test_補頁頁號連續且承末頁主版與方向(template):
    """補頁的主版取末頁主版（末節換過主版時跟著換），方向亦同。"""
    paragraphs = SHORT + [{"text": "換節：目錄主版起新節。", "style": BODY,
                           "master": "D-目錄"}]
    result = layout_document(make_doc(4, paragraphs=paragraphs), template)
    assert [p.number for p in result.pages] == \
           list(range(1, len(result.pages) + 1))
    content = [p for p in result.pages if not p.blank]
    assert content[-1].master == "D-目錄"
    for page in result.pages:
        if page.blank:
            assert page.master == content[-1].master
            assert page.vertical == content[-1].vertical


# ---- 2. 封面與空稿 ----

def test_倍數含封面(template):
    """Sprint 145（Owner 回饋修正 Sprint 144）：封面就是第一張紙的第一面
    （「封面為紙張的第一頁」「要確認每一張紙都會被印製到」），故 4 的倍數以
    「含封面的總頁數」計；總數湊成偶數＝末紙面恆偶＝翻完闔上書的單頁封底。"""
    result = layout_document(make_doc(4, cover=COVER_MASTER), template)
    assert result.cover_pages == 1
    assert len(result.pages) % 4 == 0
    assert not result.pages[0].blank, "封面不是補頁"
    # SHORT＝1 內文頁：1 封面＋1 內文＝2 → 補 2 至 4（舊制只湊內文＝補 3、總 5）
    assert len(result.pages) == 4
    assert [p.number for p in result.pages if p.blank] == [3, 4]


def test_只有封面的空稿不補頁(template):
    """無內文＝還沒有要成帖的那疊紙（匯入前先建封面的形態）。"""
    result = layout_document(
        make_doc(4, cover=COVER_MASTER, paragraphs=[]), template)
    assert len(result.pages) == 1


def test_空稿不補頁(template):
    assert layout_document(make_doc(4, paragraphs=[]), template).pages == ()


# ---- 3. 欄位驗證與序列化（document@2） ----

def test_sheet_pages_round_trip():
    doc = make_doc(4)
    assert doc.sheet_pages == 4
    assert document_from_dict(document_to_dict(doc)).sheet_pages == 4


def test_明說0與未宣告序列化可分辨():
    """0 須寫出（使用者明說不補，重開不該被預設值蓋回去），None 不寫出。"""
    assert document_to_dict(make_doc(0))["meta"]["sheet_pages"] == 0
    assert document_from_dict(document_to_dict(make_doc(0))).sheet_pages == 0
    assert "sheet_pages" not in document_to_dict(make_doc())["meta"]
    assert make_doc().sheet_pages is None


def test_sheet_pages_需schema版本2():
    with pytest.raises(DocumentError, match="document@2"):
        document_from_dict({
            "schema": "cjkfolio/document@1",
            "meta": {"title": "t", "template": "x", "master": "A-內文版",
                     "sheet_pages": 4},
            "paragraphs": [{"text": "字", "style": BODY}],
        })


@pytest.mark.parametrize("bad", [-1, True, 4.0, "4", []])
def test_sheet_pages_型別與範圍快速失敗(bad):
    """誤填不沉默取 0：布林、小數、字串、負數皆據實拒收。"""
    with pytest.raises(DocumentError, match="sheet_pages"):
        make_doc(bad)


# ---- 4. 兩後端：補頁不編頁碼、不繪任何裝飾 ----

@needs_fonts
def test_render_補頁為全白(tmp_path, template):
    """補頁不編頁碼、不印書眉、不繪天頭虛線＝該頁底圖全白（無一個非白像素）。"""
    from PIL import Image

    from cjkfolio.render import render_document

    doc = make_doc(4)
    out = render_document(doc, template, tmp_path / "png", font_dir=FONT_DIR)
    layout = layout_document(doc, template)
    assert out.violations == []
    assert len(out.paths) == len(layout.pages)
    for page, path in zip(layout.pages, out.paths):
        extrema = Image.open(path).convert("L").getextrema()
        if page.blank:
            assert extrema == (255, 255), f"補頁 {page.number} 有非白像素"
        else:
            assert extrema[0] < 255, f"內容頁 {page.number} 竟然全白"


@needs_fonts
def test_export_pdf_補頁抽不到任何字(tmp_path, template):
    """Gate 4 獨立驗證（PyMuPDF 直讀）：補頁確實成頁、且頁面上一個字都沒有。"""
    fitz = pytest.importorskip("fitz")

    from cjkfolio.pdf_writer import export_pdf

    doc = make_doc(4)
    layout = layout_document(doc, template)
    blanks = [p.number for p in layout.pages if p.blank]
    assert blanks, "夾具前提：本稿須有補頁"
    pdf_path = tmp_path / "padded.pdf"
    export_pdf(doc, template, pdf_path, font_dir=FONT_DIR)
    with fitz.open(pdf_path) as pdf:
        assert pdf.page_count == len(layout.pages)
        for page in layout.pages:
            text = pdf[page.number - 1].get_text().strip()
            if page.number in blanks:
                assert text == "", f"補頁 {page.number} 抽到字：{text!r}"
            else:
                assert text, f"內容頁 {page.number} 抽不到字"


@needs_fonts
def test_preflight_通過含補頁的pdf(tmp_path, template):
    """空白頁不破 PDF/X-1a（每頁 TrimBox 齊備、內容流可解碼）。"""
    pytest.importorskip("fitz")

    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.preflight import check_pdfx1a

    pdf_path = tmp_path / "padded-x1a.pdf"
    export_pdf(make_doc(4), template, pdf_path, font_dir=FONT_DIR)
    report = check_pdfx1a(pdf_path)
    assert report.ok, [f for f in report.findings if not f.ok]


# ---- 5. 編輯器層：預設值與縮圖頁腳 ----

def test_with_binding_未宣告者補預設值():
    """編輯器開的文件＝要裝訂的書：未宣告者視為 SHEET_PAGES，已宣告者原樣。"""
    from editor.book_binding import SHEET_PAGES, with_binding

    assert SHEET_PAGES == 4
    assert with_binding(make_doc()).sheet_pages == SHEET_PAGES
    assert with_binding(make_doc(0)).sheet_pages == 0, "明說不補須被尊重"
    assert with_binding(make_doc(8)).sheet_pages == 8
    doc = make_doc(4)
    assert with_binding(doc) is doc, "已宣告者不重建物件"


def test_thumbnail_footer_補頁不編頁碼():
    """縮圖頁腳：補頁同封面回 None（頁面面板不印補頁的頁碼）。"""
    from editor.page_panel import thumbnail_footer

    assert thumbnail_footer(5, cover_pages=1, title="書", blank=True) is None
    assert thumbnail_footer(5, cover_pages=1, title="書")["number"] == "4"
