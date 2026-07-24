"""節式主版指派（Sprint 51）：Paragraph.master 節首標記＝起新頁換主版。

覆蓋四層：document 欄位驗證與序列化、layout 節式流排（逐頁主版、逐節網格容量、
頁號連續）、editing 七類操作保留 master、兩後端逐頁主版（頁腳 gate／幾何 parity／
G 節圖片置入）。測試素材一律自擬（版權紅線）。PDF 驗證走 PyMuPDF（Gate 4 獨立實作）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.editing import (
    DocCursor,
    DocRange,
    apply_char_style,
    change_paragraph_style,
    delete_range,
    insert_text,
    merge_paragraph,
    replace_range,
    set_section_master,
    split_paragraph,
)
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.render import line_axis_x_pt, mm_to_pt
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

BLEED_PT = mm_to_pt(3.0)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs, master="A-內文版", title="自擬樣張", images=None):
    data = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": title, "template": "neizai-zhengli", "master": master},
        "paragraphs": paragraphs,
    }
    if images is not None:
        data["images"] = images
    return document_from_dict(data)


def make_chapter_doc(title="整理練習"):
    """自擬「部扉＋內文」章首文件：頁 1＝B 部扉（無頁腳）、頁 2 起＝A 內文（頁腳）。"""
    return make_doc(
        [
            {"text": "第一部", "style": "標籤-篇序小標"},
            {"text": "把留下的東西安放好", "style": "部扉大標-明體W9"},
            {"text": "整" * 64, "style": "內文-明體直排", "master": "A-內文版"},
        ],
        master="B-部扉",
        title=title,
    )


# ---------- document 層：欄位驗證與序列化 ----------

def test_paragraph_master_parse_and_roundtrip():
    doc = make_chapter_doc()
    assert doc.paragraphs[0].master is None
    assert doc.paragraphs[1].master is None
    assert doc.paragraphs[2].master == "A-內文版"
    out = document_to_dict(doc)
    assert "master" not in out["paragraphs"][0]
    assert out["paragraphs"][2]["master"] == "A-內文版"
    again = document_from_dict(out)
    assert again.paragraphs[2].master == "A-內文版"


def test_paragraph_master_requires_nonempty_string():
    with pytest.raises(DocumentError, match="master"):
        make_doc([{"text": "字", "style": "內文-明體直排", "master": ""}])
    with pytest.raises(DocumentError, match="master"):
        make_doc([{"text": "字", "style": "內文-明體直排", "master": 3}])


def test_paragraph_master_rejected_on_v1_schema():
    with pytest.raises(DocumentError, match="document@2"):
        document_from_dict({
            "schema": "cjkfolio/document@1",
            "meta": {"title": "舊檔", "template": "neizai-zhengli", "master": "A-內文版"},
            "paragraphs": [{"text": "字", "style": "內文-明體直排", "master": "B-部扉"}],
        })


# ---------- layout 層：節式流排 ----------

def test_single_master_doc_pages_carry_doc_master(template):
    doc = make_doc([{"text": "整" * 64, "style": "內文-明體直排"}])
    layout = layout_document(doc, template)
    assert layout.violations == []
    assert [p.master for p in layout.pages] == ["A-內文版"]


def test_section_switch_starts_new_page_with_master(template):
    layout = layout_document(make_chapter_doc(), template)
    assert layout.violations == []
    assert [(p.number, p.master) for p in layout.pages] == [
        (1, "B-部扉"), (2, "A-內文版"),
    ]
    assert [pl.para_idx for pl in layout.pages[0].placed] == [0, 1]
    assert {pl.para_idx for pl in layout.pages[1].placed} == {2}


def test_section_capacity_uses_its_master_grid(template):
    """A 節容量依 A 網格（32 字/行、縮排 2 → 30＋32＋2＝3 行）；誤用 B 網格會成 4 行。"""
    layout = layout_document(make_chapter_doc(), template)
    assert len(layout.pages[1].placed) == 3
    assert layout.pages[1].placed[0].line.start_slot == 2  # 段首縮排 2 字（A 節首段）


def test_same_master_marker_forces_page_break(template):
    doc = make_doc([
        {"text": "整" * 10, "style": "內文-明體直排"},
        {"text": "理" * 10, "style": "內文-明體直排", "master": "A-內文版"},
    ])
    layout = layout_document(doc, template)
    assert [(p.number, p.master) for p in layout.pages] == [
        (1, "A-內文版"), (2, "A-內文版"),
    ]
    assert layout.pages[1].placed[0].slot == 0  # 節間段後空槽不帶進次頁


def test_para0_master_overrides_doc_default(template):
    doc = make_doc([
        {"text": "第一部", "style": "標籤-篇序小標", "master": "B-部扉"},
        {"text": "把留下的東西安放好", "style": "部扉大標-明體W9"},
    ])
    layout = layout_document(doc, template)
    assert [p.master for p in layout.pages] == ["B-部扉"]


def test_unknown_section_master_raises(template):
    doc = make_doc([
        {"text": "字", "style": "內文-明體直排", "master": "Z-不存在"},
    ])
    with pytest.raises(KeyError, match="Z-不存在"):
        layout_document(doc, template)


def test_first_para_continues_applies_to_first_section_only(template):
    doc = make_doc([
        {"text": "整" * 10, "style": "內文-明體直排"},
        {"text": "理" * 10, "style": "內文-明體直排", "master": "A-內文版"},
    ])
    layout = layout_document(doc, template, first_para_continues=True)
    assert layout.pages[0].placed[0].line.start_slot == 0  # 首節首段接排不縮排
    assert layout.pages[1].placed[0].line.start_slot == 2  # 次節首段維持縮排


def test_toc_marks_keyed_to_toc_section_page(template):
    doc = make_doc(
        [
            {"text": "安放與整理的十個提問", "style": "目錄-篇章條目", "page_no": "169"},
            {"text": "整" * 10, "style": "內文-明體直排", "master": "A-內文版"},
        ],
        master="D-目錄",
    )
    layout = layout_document(doc, template)
    assert layout.violations == []
    assert list(layout.toc_marks.keys()) == [1]  # 記號只在 D 節頁
    assert 1 in layout.rule_breaks or layout.rule_breaks == {}  # rule 僅 D 節頁計算


def test_page_no_on_section_without_toc_raises(template):
    doc = make_doc(
        [
            {"text": "安放與整理的十個提問", "style": "目錄-篇章條目", "page_no": "169"},
            {"text": "字。", "style": "內文-明體直排", "page_no": "5",
             "master": "A-內文版"},
        ],
        master="D-目錄",
    )
    with pytest.raises(ValueError, match="toc"):
        layout_document(doc, template)


# ---------- editing 層：七類操作保留 master ----------

def make_edit_doc():
    return make_doc([
        {"text": "整理是對話", "style": "內文-明體直排"},
        {"text": "安放好回憶", "style": "內文-明體直排", "master": "A-內文版"},
    ])


def test_insert_delete_replace_preserve_master():
    doc = make_edit_doc()
    d1 = insert_text(doc, DocCursor(1, 2), "與")
    assert d1.paragraphs[1].master == "A-內文版"
    d2 = delete_range(doc, DocRange(1, 0, 2))
    assert d2.paragraphs[1].master == "A-內文版"
    d3 = replace_range(doc, DocRange(1, 0, 2), "收拾")
    assert d3.paragraphs[1].master == "A-內文版"
    assert d1.paragraphs[0].master is None  # 無標記段落維持 None


def test_char_style_and_para_style_preserve_master():
    doc = make_edit_doc()
    d1 = apply_char_style(doc, DocRange(1, 0, 2), "內文強調-明體W9")
    assert d1.paragraphs[1].master == "A-內文版"
    d2 = change_paragraph_style(doc, 1, "引文-仿宋語錄")
    assert d2.paragraphs[1].master == "A-內文版"


def test_split_keeps_master_on_head_only():
    doc = make_edit_doc()
    d = split_paragraph(doc, DocCursor(1, 2))
    assert d.paragraphs[1].master == "A-內文版"  # head 承原段（節首身分同 page_no）
    assert d.paragraphs[2].master is None        # tail 不複製節首標記


def test_merge_dissolves_section_marker(template):
    doc = make_edit_doc()
    assert len(layout_document(doc, template).pages) == 2
    merged = merge_paragraph(doc, 1)
    assert merged.paragraphs[0].master is None  # 前段存活：併入後節首標記消失
    assert len(layout_document(merged, template).pages) == 1


# ---------- editing 層＋session：set_section_master 節式主版指派（Sprint 130） ----------

def test_set_section_master_para0_changes_doc_master():
    """段 0（無自帶 master）指派＝改首節預設主版 doc.master，不動段落標記。"""
    doc = make_edit_doc()  # doc.master="A-內文版"，段0 None、段1 "A-內文版"
    d = set_section_master(doc, 0, "E-序文版")
    assert d.master == "E-序文版"
    assert d.paragraphs[0].master is None       # 首節主版存 doc.master，非段落標記
    assert d.paragraphs[1].master == "A-內文版"  # 其餘節首標記不動


def test_set_section_master_marker_set_and_clear():
    """段 >0 指派＝設節首標記；清 None＝承前節（併回前節）。"""
    doc = make_edit_doc()
    assert set_section_master(doc, 1, "B-部扉").paragraphs[1].master == "B-部扉"
    assert set_section_master(doc, 1, None).paragraphs[1].master is None


def test_set_section_master_noop_returns_same_object():
    """等值指派 no-op 回原物件（段0 同 doc.master／段>0 同標記）。"""
    doc = make_edit_doc()
    assert set_section_master(doc, 0, "A-內文版") is doc
    assert set_section_master(doc, 1, "A-內文版") is doc


def test_set_section_master_out_of_range_raises():
    doc = make_edit_doc()
    with pytest.raises(IndexError):
        set_section_master(doc, 2, "B-部扉")
    with pytest.raises(IndexError):
        set_section_master(doc, -1, "B-部扉")


def test_set_section_master_first_section_clear_raises():
    """首節（段0 無自帶 master）不得清成 None（無前節可承）。"""
    doc = make_edit_doc()
    with pytest.raises(ValueError, match="首節"):
        set_section_master(doc, 0, None)


def test_set_section_master_para0_self_shadow_clear_reverts(template):
    """段0 自帶 master（自蓋首節）時，清 None＝退回 doc.master 預設，不 raise。"""
    doc = make_doc([
        {"text": "整" * 10, "style": "內文-明體直排", "master": "B-部扉"},
        {"text": "理" * 10, "style": "內文-明體直排"},
    ])  # doc.master="A-內文版"，段0 自蓋成 B
    assert layout_document(doc, template).pages[0].master == "B-部扉"
    d = set_section_master(doc, 0, None)
    assert d.paragraphs[0].master is None
    assert layout_document(d, template).pages[0].master == "A-內文版"  # 退回預設


def test_set_section_master_relayouts_sections(template):
    """指派後版面真的重新分節：段1 設 E-序文版 → 1 頁變 2 頁、頁2 主版＝E。"""
    doc = make_doc([
        {"text": "整" * 10, "style": "內文-明體直排"},
        {"text": "理" * 10, "style": "內文-明體直排"},
    ])
    assert [p.master for p in layout_document(doc, template).pages] == ["A-內文版"]
    d = set_section_master(doc, 1, "E-序文版")
    pages = layout_document(d, template).pages
    assert [(p.number, p.master) for p in pages] == [(1, "A-內文版"), (2, "E-序文版")]


def test_session_set_section_master_single_undo(template):
    """session 包裝：指派入單一 undo 步、等值 no-op 回 None、undo 回原。"""
    doc = make_doc([
        {"text": "整" * 10, "style": "內文-明體直排"},
        {"text": "理" * 10, "style": "內文-明體直排"},
    ])
    session = EditSession(doc, template)
    res = session.set_section_master(1, "E-序文版")
    assert res is not None
    assert session.document.paragraphs[1].master == "E-序文版"
    assert [p.master for p in session.layout.pages] == ["A-內文版", "E-序文版"]
    assert session.set_section_master(1, "E-序文版") is None  # 等值 no-op 不入歷史
    assert session.undo() is not None
    assert session.document.paragraphs[1].master is None
    assert not session.can_undo()


def test_session_set_section_master_unknown_master_fast_fail(template):
    """未知主版名於套用前的全文重排 KeyError 快速失敗，狀態不變不入歷史。"""
    doc = make_edit_doc()
    session = EditSession(doc, template)
    with pytest.raises(KeyError):
        session.set_section_master(1, "Z-不存在主版")
    assert session.document.paragraphs[1].master == "A-內文版"
    assert not session.can_undo()


# ---------- 兩後端：逐頁主版（需字型） ----------

@needs_fonts
def test_export_multimaster_footer_gates_per_page(template, tmp_path):
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    doc = make_chapter_doc()
    out = tmp_path / "chapter.pdf"
    result = export_pdf(doc, template, out)
    assert result.violations == []
    assert result.page_count == 2
    pdf = fitz.open(str(out))
    p1, p2 = pdf[0].get_text(), pdf[1].get_text()
    for ch in "第一部把留下的東西安放好":  # 直排逐字抽取，逐字檢查
        assert ch in p1
    assert "2" not in p1 and "練" not in p1  # B 部扉無頁腳（footer={} 真書一致）
    assert "2" in p2  # A 內文書頁 2：頁碼
    assert "練" in p2 and "習" in p2  # 書頁 2（偶＝右頁）：書名書眉「整理練習」


@needs_fonts
def test_export_multimaster_geometry_per_page(template, tmp_path):
    """頁 1 字墨對準 B 行軸（Sprint 20 一手量測 228.49／194.12），頁 2 對準 A 行軸。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.layout import style_line_slots
    from cjkfolio.pdf_writer import export_pdf

    doc = make_chapter_doc()
    out = tmp_path / "chapter.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))

    def span_cx(page_idx, pred, near=lambda cx: True):
        cxs = [
            cx
            for b in pdf[page_idx].get_text("rawdict")["blocks"]
            for ln in b.get("lines", []) for s in ln.get("spans", [])
            for c in s.get("chars", []) if pred(s["size"])
            for cx in [(c["bbox"][0] + c["bbox"][2]) / 2 - BLEED_PT] if near(cx)
        ]
        assert cxs, "無符合字級的字墨"
        return sum(cxs) / len(cxs)

    b_master = template.masters["B-部扉"]
    label = template.paragraph_styles["標籤-篇序小標"]
    title = template.paragraph_styles["部扉大標-明體W9"]
    axis_label = line_axis_x_pt(template, b_master, 0, 1,
                                line_slots=style_line_slots(label, b_master.grid))
    axis_title = line_axis_x_pt(
        template, b_master, style_line_slots(label, b_master.grid), 1,
        line_slots=style_line_slots(title, b_master.grid))
    assert axis_label == pytest.approx(228.49, abs=0.05)  # Sprint 20 A 級量測
    assert axis_title == pytest.approx(194.12, abs=0.05)
    assert span_cx(0, lambda sz: sz < 15) == pytest.approx(axis_label, abs=0.5)
    assert span_cx(0, lambda sz: sz > 15) == pytest.approx(axis_title, abs=0.5)

    a_master = template.masters["A-內文版"]
    for slot in (0, 1, 2):  # 64 字內文 3 行：逐槽近鄰分群比對 A 行軸（書頁 2 偶＝右頁）
        axis_body = line_axis_x_pt(template, a_master, slot, 2)
        assert span_cx(
            1, lambda sz: sz < 15,
            near=lambda cx, a=axis_body: abs(cx - a) < 10,
        ) == pytest.approx(axis_body, abs=0.5)


@needs_fonts
def test_render_multimaster_two_pages(template, tmp_path):
    from PIL import Image

    from cjkfolio.render import render_document

    doc = make_chapter_doc()
    result = render_document(doc, template, tmp_path, dpi=150)
    assert result.violations == []
    assert [p.name for p in result.paths] == ["page-001.png", "page-002.png"]
    for p in result.paths:
        assert Image.open(p).size == Image.open(result.paths[0]).size


@needs_fonts
def test_images_resolve_per_page_master(template, tmp_path):
    """G 節照片頁與 A 節內文同文件：圖落 G 頁可置入；落 A 頁（無 figure）快速失敗。"""
    from PIL import Image

    from cjkfolio.images import ImageError, resolve_placed_images

    Image.new("L", (40, 30), 128).save(tmp_path / "photo.png")
    paras = [
        {"text": "整" * 10, "style": "內文-明體直排"},
        {"text": "客廳一景", "style": "旁注-手札圖注", "master": "G-圖文版"},
    ]
    doc = make_doc(paras, images=[{"path": "photo.png", "page": 2}])
    layout = layout_document(doc, template)
    masters_by_page = {p.number: template.masters[p.master] for p in layout.pages}
    resolved = resolve_placed_images(doc, masters_by_page, base_dir=tmp_path)
    assert set(resolved) == {2}

    bad = make_doc(paras, images=[{"path": "photo.png", "page": 1}])
    with pytest.raises(ImageError, match="figure"):
        resolve_placed_images(bad, masters_by_page, base_dir=tmp_path)
    out_of_range = make_doc(paras, images=[{"path": "photo.png", "page": 9}])
    with pytest.raises(ImageError, match="頁"):
        resolve_placed_images(out_of_range, masters_by_page, base_dir=tmp_path)
