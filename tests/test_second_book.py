"""多書專案驗證（Sprint 105，GAPS #56 丙(11)）：第二本非參考書跑完整管線。

本檔的用途不是再驗一次排版規則，而是驗**管線是否只對單一書目可用**。素材為
自擬設計的第二套模版 `templates/jiejiao-manxing.json`（開本 130×190mm、版心、
字級、行距、主版名、樣式名、色票名與參考書零共用）＋自撰原創散文《街角慢行》
三章（版權紅線：不用參考書任何文字）。

釘死的是**參數化**：頁面盒框、版心幾何、頁腳側別、目錄頁碼、PDF/X 合規都須
由模版推導而得，不得依賴任何「A-內文版」「neizai-zhengli」148×210 之類的預設。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.book import load_book
from cjkfolio.document import load_document
from cjkfolio.layout import layout_document
from cjkfolio.md_import import import_markdown_file
from cjkfolio.styles import load_template
from cjkfolio.toc import assemble_book_with_toc, toc_items

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "templates" / "jiejiao-manxing.json"
SAMPLES = ROOT / "samples"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE_PATH)


def test_template_shares_nothing_with_reference(template):
    """第二套模版與參考書模版零共用（否則驗不出過擬合）。"""
    ref = load_template(ROOT / "templates" / "neizai-zhengli.json")
    assert (template.page_width_mm, template.page_height_mm) != \
           (ref.page_width_mm, ref.page_height_mm)
    assert not set(template.masters) & set(ref.masters)
    assert not set(template.paragraph_styles) & set(ref.paragraph_styles)
    assert not set(template.character_styles) & set(ref.character_styles)
    assert not set(template.colors) & set(ref.colors)


def test_template_declares_default_master(template):
    """模版自行宣告預設主版（原先寫死於程式的 A-內文版 搬進資料層）。"""
    assert template.default_master == "甲-內文"
    assert template.default_master in template.masters


def test_reference_template_still_declares_its_default():
    """參考書模版補宣告原本的程式預設，行為不變（向後相容）。"""
    ref = load_template(ROOT / "templates" / "neizai-zhengli.json")
    assert ref.default_master == "A-內文版"


def test_toc_master_without_rule_is_valid(template):
    """丙-目錄 刻意不設 rule：水平虛線為選配而非必填。"""
    toc_master = template.masters["丙-目錄"]
    assert toc_master.rule is None
    assert toc_master.toc is not None


@pytest.mark.parametrize("n", [1, 2, 3])
def test_chapter_import_uses_second_template(template, n):
    """md 匯入須把第二套模版的 id 與預設主版寫進文件（非參考書預設）。"""
    doc = import_markdown_file(
        SAMPLES / f"jiejiao-manxing-ch{n}.md",
        mapping=template.md_mapping,
        inline_mapping=template.md_inline_mapping,
        title="街角慢行",
        template_id="jiejiao-manxing",
        master=template.default_master,
    )
    assert doc.template == "jiejiao-manxing"
    assert doc.master == "甲-內文"
    assert doc.paragraphs
    for para in doc.paragraphs:
        assert para.style in template.paragraph_styles, \
            f"第 {n} 章出現模版未定義的樣式 {para.style}"


def test_chapter_docs_on_disk_match_second_template(template):
    """落檔的三章 doc.json 亦指向第二套模版（供 CLI 與書冊組裝取用）。"""
    for n in (1, 2, 3):
        doc = load_document(SAMPLES / f"jiejiao-manxing-ch{n}.doc.json")
        assert doc.template == "jiejiao-manxing"
        assert doc.master == "甲-內文"


def test_book_manifest_names_second_template():
    book = load_book(SAMPLES / "book-jiejiao-manxing.json")
    assert book.template == "jiejiao-manxing"
    assert len(book.chapters) == 7  # 自動目錄 + 三組（章扉 + 內文）


def test_chapter_openers_switch_master(template):
    """章扉走 乙-章扉（mirror=false、無頁腳），內文走 甲-內文：節式主版切換。"""
    doc = assemble_book_with_toc(
        load_book(SAMPLES / "book-jiejiao-manxing.json"), template,
        base_dir=SAMPLES, first_page=1)
    section_masters = [p.master for p in doc.paragraphs if p.master]
    assert section_masters == ["丙-目錄", "乙-章扉", "甲-內文",
                               "乙-章扉", "甲-內文", "乙-章扉", "甲-內文"]
    assert template.masters["乙-章扉"].mirror is False
    assert not template.masters["乙-章扉"].footer  # 章扉不排頁腳三件組
    assert template.masters["甲-內文"].mirror is True


@needs_fonts
def test_full_book_layout_geometry_comes_from_template(template):
    """整本組裝後排版：頁面幾何逐項由第二套模版推導，非參考書常數。"""
    from cjkfolio.primitives import PT_PER_MM, line_axis_x_pt

    doc = assemble_book_with_toc(
        load_book(SAMPLES / "book-jiejiao-manxing.json"), template,
        base_dir=SAMPLES, first_page=1)
    result = layout_document(doc, template)
    assert result.pages, "整本排不出任何頁"

    body = template.masters["甲-內文"]
    # 首行行軸＝頁寬 − 書口 − 半字身（右頁）；用第二套模版的數字獨立算一次
    page_w_pt = 130.0 * PT_PER_MM
    want = page_w_pt - 16.0 * PT_PER_MM - body.grid.base_size_pt / 2
    assert line_axis_x_pt(template, body, 0, 2) == pytest.approx(want, abs=1e-9)
    # 版心不得溢出訂口（版心寬＝base + (n-1)×pitch）
    content_w = body.grid.base_size_pt + (body.grid.lines_per_page - 1) * \
        body.grid.line_pitch_pt
    assert 16.0 * PT_PER_MM + content_w + body.margins.inner_mm * PT_PER_MM == \
        pytest.approx(page_w_pt, abs=0.05)


@needs_fonts
def test_full_book_flows_without_violation(template):
    """整本流排：無禁則違規、無溢出頁面，且目錄頁碼指到實際章首頁。"""
    book = load_book(SAMPLES / "book-jiejiao-manxing.json")
    doc = assemble_book_with_toc(book, template, base_dir=SAMPLES, first_page=1)
    items = toc_items(book, template, base_dir=SAMPLES, first_page=1)
    result = layout_document(doc, template)
    assert not result.violations, f"整本排版有違規：{result.violations[:3]}"
    # 兩層目錄（Sprint 108）：三章各列一條，章內小節各列兩條
    chapters = [item for item in items if item.level == 1]
    sections = [item for item in items if item.level == 2]
    assert len(chapters) == 3, "三章都應列入目錄"
    assert len(sections) == 6, "三章各兩個小節都應列入目錄"
    assert len(items) == len(chapters) + len(sections), "不應出現第三層條目"
    # 目錄頁碼須遞增（書序即頁序），且不超過整本頁數
    numbers = [item.page for item in items]
    assert numbers == sorted(numbers)
    assert [c.page for c in chapters] == sorted(set(c.page for c in chapters))
    assert max(numbers) <= len(result.pages), \
        f"目錄頁碼 {max(numbers)} 超出整本 {len(result.pages)} 頁"


@needs_fonts
def test_export_pdf_boxes_and_preflight(tmp_path, template):
    """匯出 PDF：盒框依第二套開本、PDF/X-1a 機械檢查全過。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import BLEED_MM, export_pdf
    from cjkfolio.preflight import check_pdfx
    from cjkfolio.primitives import PT_PER_MM

    doc = assemble_book_with_toc(
        load_book(SAMPLES / "book-jiejiao-manxing.json"), template,
        base_dir=SAMPLES, first_page=1)
    out = tmp_path / "jiejiao-manxing.pdf"
    export_pdf(doc, template, out)

    # Gate 4：不用本產品的幾何助手，直接讀 PDF 盒框
    with fitz.open(out) as pdf:
        page = pdf[0]
        trim = page.trimbox
        media = page.mediabox
    assert trim.width == pytest.approx(130.0 * PT_PER_MM, abs=0.01)
    assert trim.height == pytest.approx(190.0 * PT_PER_MM, abs=0.01)
    assert media.width == pytest.approx(
        (130.0 + 2 * BLEED_MM) * PT_PER_MM, abs=0.01)

    report = check_pdfx(str(out))
    assert report.ok, [f for f in report.findings if not f.ok]


def test_samples_are_original_not_reference(template):
    """版權紅線：三章素材為自撰原創，且不含破折號（全域中文標點規範）。"""
    for n in (1, 2, 3):
        text = (SAMPLES / f"jiejiao-manxing-ch{n}.md").read_text(encoding="utf-8")
        assert "—" not in text, f"第 {n} 章含破折號"
        assert len(text) > 400, f"第 {n} 章規模過小，排不出多頁"


@needs_fonts
def test_page_count_and_footer_sides(template):
    """整本頁數與側別：偶數書頁＝右頁有書眉，奇數＝左頁無書眉；章扉整頁無頁腳。"""
    doc = assemble_book_with_toc(
        load_book(SAMPLES / "book-jiejiao-manxing.json"), template,
        base_dir=SAMPLES, first_page=1)
    result = layout_document(doc, template)
    assert len(result.pages) == 13, f"整本頁數 {len(result.pages)}（預期 13）"
    openers = [i for i, p in enumerate(result.pages, 1)
               if p.master == "乙-章扉"]
    assert openers == [2, 6, 10], f"章扉落點 {openers}（預期 2／6／10）"


def test_book_manifest_is_valid_json():
    data = json.loads(
        (SAMPLES / "book-jiejiao-manxing.json").read_text(encoding="utf-8"))
    assert data["schema"] == "cjkfolio/book@1"
