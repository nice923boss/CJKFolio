"""圖片置入（Sprint 50，Phase 2）：灰階影像置入 G 圖文版 figure 保留區。

涵蓋：fit_image_rect 純幾何（contain 等比置中）、open_grayscale 色彩空間、
document PlacedImage round-trip 與守門、resolve_placed_images 驗證與去重、
PNG 後端置入與方向、PDF DeviceGray XObject／去重／preflight 12/12／bbox 幾何
（PyMuPDF 獨立解析，Gate 4）／pixmap 方向（獨立渲染）。

循 tests/ 分檔慣例（各檔自帶 fixture／helper，不建共享 conftest）。
"""
from pathlib import Path

import fitz
import pytest
from PIL import Image

from cjkfolio.document import (
    Document,
    DocumentError,
    Paragraph,
    PlacedImage,
    document_from_dict,
    document_to_dict,
)
from cjkfolio.images import (
    EmbeddedImage,
    ImageError,
    open_grayscale,
    resolve_placed_images,
)
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import check_pdfx1a
from cjkfolio.primitives import ImageBox, figure_slot_rect, fit_image_rect
from cjkfolio.render import is_right_page, mm_to_pt, render_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
G_MASTER = "G-圖文版"


@pytest.fixture
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _make_image(path, w=400, h=600, top=(40, 40, 40), bottom=(200, 200, 200)):
    """自擬測試圖（RGB）：上半 dark、下半 light，供方向驗證；save 後回傳路徑。"""
    im = Image.new("RGB", (w, h), bottom)
    im.paste(Image.new("RGB", (w, h // 2), top), (0, 0))
    im.save(path)
    return path


def _figure_doc(image_name, page=1, text="整理前後對照"):
    """單頁 G 圖文版文件：一段圖說＋一張置入圖（相對路徑，配合 image_base_dir）。"""
    return Document(
        title="圖文版置入測試", template="neizai-zhengli", master=G_MASTER,
        paragraphs=(Paragraph(text=text, style="圖說-辰宇落雁"),),
        images=(PlacedImage(path=image_name, page=page),),
    )


def _g_slot(template, is_right=False):
    master = template.masters[G_MASTER]
    return figure_slot_rect(mm_to_pt(template.page_width_mm), master, is_right, master.figure)


# ---------- fit_image_rect 純幾何 ----------

def test_fit_portrait_fits_height_letterbox_sides():
    box = fit_image_rect(0, 0, 100, 100, 50, 100)  # 影像比 0.5 < slot 1.0 → 貼高
    assert isinstance(box, ImageBox)
    assert box.y0 == 0 and box.y1 == 100  # 滿高
    assert box.x0 == 25 and box.x1 == 75  # 兩側置中留白


def test_fit_landscape_fits_width_letterbox_topbottom():
    box = fit_image_rect(0, 0, 100, 100, 200, 100)  # 比 2.0 > slot 1.0 → 貼寬
    assert box.x0 == 0 and box.x1 == 100  # 滿寬
    assert box.y0 == 25 and box.y1 == 75  # 上下置中留白


def test_fit_square_exact():
    box = fit_image_rect(0, 0, 100, 100, 300, 300)
    assert (box.x0, box.y0, box.x1, box.y1) == (0, 0, 100, 100)


def test_fit_preserves_aspect_ratio():
    box = fit_image_rect(10, 20, 210, 120, 400, 300)  # slot 200×100、比 2.0；img 比 1.333
    draw_w, draw_h = box.x1 - box.x0, box.y1 - box.y0
    assert abs(draw_w / draw_h - 400 / 300) < 1e-9  # 不變形
    assert draw_h == 100  # slot 較矮 → 貼高（img 比 < slot 比）


def test_fit_within_slot_and_centered():
    sx0, sy0, sx1, sy1 = 60.0, 107.0, 347.0, 467.0
    box = fit_image_rect(sx0, sy0, sx1, sy1, 400, 600)
    assert sx0 - 1e-9 <= box.x0 and box.x1 <= sx1 + 1e-9
    assert sy0 - 1e-9 <= box.y0 and box.y1 <= sy1 + 1e-9
    # 置中：兩側留白相等
    assert abs((box.x0 - sx0) - (sx1 - box.x1)) < 1e-9
    assert abs((box.y0 - sy0) - (sy1 - box.y1)) < 1e-9


def test_fit_zero_pixels_raises():
    with pytest.raises(ValueError):
        fit_image_rect(0, 0, 100, 100, 0, 600)
    with pytest.raises(ValueError):
        fit_image_rect(0, 0, 100, 100, 400, 0)


# ---------- open_grayscale ----------

def test_open_grayscale_converts_rgb_to_L(tmp_path):
    p = _make_image(tmp_path / "rgb.png")
    im = open_grayscale(p)
    assert im.mode == "L"
    assert im.size == (400, 600)


def test_open_grayscale_missing_file_raises(tmp_path):
    with pytest.raises(ImageError):
        open_grayscale(tmp_path / "nope.png")


def test_open_grayscale_non_image_raises(tmp_path):
    bad = tmp_path / "notimg.png"
    bad.write_text("這不是圖檔", encoding="utf-8")
    with pytest.raises(ImageError):
        open_grayscale(bad)


# ---------- document PlacedImage round-trip 與守門 ----------

def test_document_images_roundtrip():
    doc = Document(title="t", template="x", master=G_MASTER,
                   paragraphs=(Paragraph(text="圖說", style="圖說-辰宇落雁"),),
                   images=(PlacedImage(path="a.png", page=1), PlacedImage(path="b.png", page=3)))
    d = document_to_dict(doc)
    assert d["images"] == [{"path": "a.png", "page": 1}, {"path": "b.png", "page": 3}]
    back = document_from_dict(d)
    assert back.images == doc.images


def test_document_no_images_key_when_empty():
    doc = Document(title="t", template="x", master="A-內文版",
                   paragraphs=(Paragraph(text="內文", style="內文-明體直排"),))
    assert "images" not in document_to_dict(doc)
    assert doc.images == ()


def test_document_backcompat_doc_without_images():
    data = {"schema": "cjkfolio/document@2", "meta": {"title": "t"},
            "paragraphs": [{"text": "內文", "style": "內文-明體直排"}]}
    assert document_from_dict(data).images == ()


def test_document_image_missing_path_raises():
    data = {"schema": "cjkfolio/document@2", "meta": {},
            "paragraphs": [{"text": "x", "style": "s"}],
            "images": [{"page": 1}]}
    with pytest.raises(DocumentError):
        document_from_dict(data)


@pytest.mark.parametrize("bad_page", [0, -1, "1", 1.5, True])
def test_document_image_bad_page_raises(bad_page):
    data = {"schema": "cjkfolio/document@2", "meta": {},
            "paragraphs": [{"text": "x", "style": "s"}],
            "images": [{"path": "a.png", "page": bad_page}]}
    with pytest.raises(DocumentError):
        document_from_dict(data)


def test_document_duplicate_image_page_raises():
    data = {"schema": "cjkfolio/document@2", "meta": {},
            "paragraphs": [{"text": "x", "style": "s"}],
            "images": [{"path": "a.png", "page": 2}, {"path": "b.png", "page": 2}]}
    with pytest.raises(DocumentError):
        document_from_dict(data)


# ---------- resolve_placed_images ----------

def test_resolve_no_figure_master_raises(tmp_path, template):
    _make_image(tmp_path / "g.png")
    doc = Document(title="t", template="x", master="A-內文版",
                   paragraphs=(Paragraph(text="內文", style="內文-明體直排"),),
                   images=(PlacedImage(path="g.png", page=1),))
    with pytest.raises(ImageError):
        resolve_placed_images(doc, {1: template.masters["A-內文版"]}, base_dir=tmp_path)


def test_resolve_page_out_of_range_raises(tmp_path, template):
    _make_image(tmp_path / "g.png")
    doc = _figure_doc("g.png", page=5)
    with pytest.raises(ImageError):
        resolve_placed_images(doc, {1: template.masters[G_MASTER]}, base_dir=tmp_path)


def test_resolve_dedup_same_path_shared_object(tmp_path, template):
    _make_image(tmp_path / "same.png")
    doc = Document(title="t", template="x", master=G_MASTER,
                   paragraphs=(Paragraph(text="圖說", style="圖說-辰宇落雁"),),
                   images=(PlacedImage(path="same.png", page=1), PlacedImage(path="same.png", page=2)))
    g = template.masters[G_MASTER]
    resolved = resolve_placed_images(doc, {1: g, 2: g}, base_dir=tmp_path)
    assert resolved[1][0] == resolved[2][0]  # 同解析路徑
    assert resolved[1][1] is resolved[2][1]  # 同 PIL 物件（cache）


def test_resolve_empty_when_no_images(template):
    doc = Document(title="t", template="x", master=G_MASTER, paragraphs=())
    assert resolve_placed_images(doc, {}) == {}


# ---------- EmbeddedImage（PDF XObject 形態單元） ----------

class _FakeBuilder:
    def __init__(self):
        self.calls = []

    def stream(self, extra_dict, data):
        self.calls.append((extra_dict, data))
        return 77


def test_embedded_image_emit_devicegray():
    emb = EmbeddedImage(Image.new("L", (3, 2), 128), "Im1")
    assert emb.width == 3 and emb.height == 2
    assert len(emb.data) == 6  # 3×2 個 8-bit 灰階 byte
    b = _FakeBuilder()
    assert emb.emit(b) == 77
    extra, data = b.calls[0]
    for token in ("/Subtype /Image", "/ColorSpace /DeviceGray",
                  "/Width 3", "/Height 2", "/BitsPerComponent 8"):
        assert token in extra
    assert "/SMask" not in extra  # 灰階無 alpha（preflight no-transparency）
    assert data == emb.data


# ---------- PNG 後端置入與方向 ----------

def test_render_places_image_result_count(tmp_path, template):
    _make_image(tmp_path / "g.png")
    doc = _figure_doc("g.png")
    result = render_document(doc, template, tmp_path / "out", footer=False,
                             image_base_dir=tmp_path)
    assert result.images_placed == 1
    assert result.violations == []


def test_render_image_pixels_and_orientation(tmp_path, template):
    _make_image(tmp_path / "g.png")  # 上 dark(40)、下 light(200)
    doc = _figure_doc("g.png")
    dpi = 150
    result = render_document(doc, template, tmp_path / "out", dpi=dpi, footer=False,
                             image_base_dir=tmp_path)
    img = Image.open(result.paths[0])
    scale = dpi / 72.0
    slot = _g_slot(template, is_right=is_right_page(1))  # 書頁 1＝左頁
    box = fit_image_rect(slot.x0, slot.y0, slot.x1, slot.y1, 400, 600)
    cx = round((box.x0 + box.x1) / 2 * scale)
    top_y = round((box.y0 + (box.y1 - box.y0) * 0.25) * scale)
    bot_y = round((box.y0 + (box.y1 - box.y0) * 0.75) * scale)
    top_val, bot_val = img.getpixel((cx, top_y)), img.getpixel((cx, bot_y))
    assert top_val < 128 < bot_val  # 上暗下亮（未上下翻轉）
    # 貼高置中 → 左側留白為背景白（無佔位框、無影像）
    lb_x = round((slot.x0 + 3) * scale)
    lb_y = round((slot.y0 + slot.y1) / 2 * scale)
    assert img.getpixel((lb_x, lb_y)) > 250


def test_render_no_images_placed_zero(tmp_path, template):
    doc = Document(title="t", template="x", master=G_MASTER,
                   paragraphs=(Paragraph(text="只有圖說沒有圖", style="圖說-辰宇落雁"),))
    result = render_document(doc, template, tmp_path / "out", footer=False,
                             image_base_dir=tmp_path)
    assert result.images_placed == 0


# ---------- PDF 後端 XObject／去重／preflight／幾何 ----------

def _export(tmp_path, template, doc, name="out.pdf"):
    out = tmp_path / name
    return export_pdf(doc, template, out, footer=False, image_base_dir=tmp_path), out


def test_export_embeds_devicegray_xobject(tmp_path, template):
    _make_image(tmp_path / "g.png")
    result, out = _export(tmp_path, template, _figure_doc("g.png"))
    assert result.images_placed == 1
    d = fitz.open(str(out))
    try:
        imgs = d[0].get_images(full=True)
        assert len(imgs) == 1
        obj = d.xref_object(imgs[0][0])
        assert "/Subtype /Image" in obj
        assert "/DeviceGray" in obj
        assert "/Width 400" in obj and "/Height 600" in obj
    finally:
        d.close()


def test_export_xobject_in_resources(tmp_path, template):
    _make_image(tmp_path / "g.png")
    _result, out = _export(tmp_path, template, _figure_doc("g.png"))
    raw = out.read_bytes()
    assert b"/XObject" in raw


def test_export_preflight_all_pass_with_image(tmp_path, template):
    _make_image(tmp_path / "g.png")
    _result, out = _export(tmp_path, template, _figure_doc("g.png"))
    report = check_pdfx1a(out)
    assert report.ok, [f.detail for f in report.findings if not f.ok]
    assert len(report.findings) == 12
    # DeviceGray 影像不觸 color-cmyk-only、no-transparency
    by_rule = {f.rule: f for f in report.findings}
    assert by_rule["color-cmyk-only"].ok
    assert by_rule["no-transparency"].ok


def test_export_image_bbox_matches_fit_rect(tmp_path, template):
    _make_image(tmp_path / "g.png")
    _result, out = _export(tmp_path, template, _figure_doc("g.png"))
    slot = _g_slot(template, is_right=is_right_page(1))
    box = fit_image_rect(slot.x0, slot.y0, slot.x1, slot.y1, 400, 600)
    d = fitz.open(str(out))
    try:
        page = d[0]
        bbox = page.get_image_bbox(page.get_images(full=True)[0])
        assert abs(bbox.width - (box.x1 - box.x0)) < 0.6
        assert abs(bbox.height - (box.y1 - box.y0)) < 0.6
    finally:
        d.close()


def test_export_pdf_orientation_upright(tmp_path, template):
    _make_image(tmp_path / "g.png")  # 上 dark、下 light
    _result, out = _export(tmp_path, template, _figure_doc("g.png"))
    slot = _g_slot(template, is_right=is_right_page(1))
    box = fit_image_rect(slot.x0, slot.y0, slot.x1, slot.y1, 400, 600)
    bleed = mm_to_pt(3.0)
    sc = 100 / 72.0
    d = fitz.open(str(out))
    try:
        pix = d[0].get_pixmap(matrix=fitz.Matrix(sc, sc))
        cx = round((bleed + (box.x0 + box.x1) / 2) * sc)
        top_y = round((bleed + box.y0 + (box.y1 - box.y0) * 0.25) * sc)
        bot_y = round((bleed + box.y0 + (box.y1 - box.y0) * 0.75) * sc)
        top_lum = sum(pix.pixel(cx, top_y)) / 3
        bot_lum = sum(pix.pixel(cx, bot_y)) / 3
    finally:
        d.close()
    assert top_lum < 128 < bot_lum  # 上暗下亮（cm/Do 未翻轉）


def test_export_dedup_repeated_image_single_xobject(tmp_path, template):
    _make_image(tmp_path / "same.png")
    long_text = "文" * 500  # G 32×13≈416 字/頁 → 跨 2 頁
    doc = Document(title="兩頁同圖", template="neizai-zhengli", master=G_MASTER,
                   paragraphs=(Paragraph(text=long_text, style="內文-明體直排"),),
                   images=(PlacedImage(path="same.png", page=1),
                           PlacedImage(path="same.png", page=2)))
    result, out = _export(tmp_path, template, doc, name="two.pdf")
    assert result.page_count >= 2
    assert result.images_placed == 1  # 同路徑跨頁去重為單一 XObject
    d = fitz.open(str(out))
    try:
        xrefs = {im[0] for pno in range(d.page_count) for im in d[pno].get_images(full=True)}
        assert len(xrefs) == 1
    finally:
        d.close()


def test_export_no_images_placed_zero(tmp_path, template):
    doc = Document(title="無圖", template="x", master=G_MASTER,
                   paragraphs=(Paragraph(text="只有圖說", style="圖說-辰宇落雁"),))
    result, _out = _export(tmp_path, template, doc, name="noimg.pdf")
    assert result.images_placed == 0
