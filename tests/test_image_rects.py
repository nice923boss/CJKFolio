"""多圖／任意矩形置入模型（Sprint 54）：PlacedImage.rect 任意圖框、每頁多張。

覆蓋：document rect 欄位驗證與序列化（槽式一頁一張守門保留、rect 多張放行）、
resolve 列表模型（rect 圖不需 figure 槽、去重、順序）、兩後端多圖幾何（PNG 像素
＋PDF XObject bbox＝rect＋出血）、溢出版心允許（真書照片略溢特徵）、G 佔位框只看
figure 槽。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest
from PIL import Image

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.images import ImageError, resolve_placed_images
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

TRIM_W_PT = 148 * 72.0 / 25.4
BLEED_PT = 3 * 72.0 / 25.4


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs, images, master="A-內文版"):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": master},
        "paragraphs": paragraphs,
        "images": images,
    })


def body_doc(images):
    return make_doc([{"text": "整理是一場與過去的對話。", "style": "內文-明體直排"}], images)


def gray_square(path, value=90, size=(40, 40)):
    Image.new("L", size, value).save(path)
    return path


# ---------- document：rect 欄位 ----------

def test_rect_parse_and_roundtrip():
    doc = body_doc([
        {"path": "a.png", "page": 1, "rect": [60.0, 100.0, 180.0, 260.0]},
        {"path": "b.png", "page": 1, "rect": [200, 300, 300, 420]},
    ])
    assert doc.images[0].rect == (60.0, 100.0, 180.0, 260.0)
    assert doc.images[1].rect == (200.0, 300.0, 300.0, 420.0)
    out = document_to_dict(doc)
    assert out["images"][0]["rect"] == [60.0, 100.0, 180.0, 260.0]
    again = document_from_dict(out)
    assert again.images[0].rect == (60.0, 100.0, 180.0, 260.0)
    # 槽式（無 rect）不序列化 rect 鍵
    slot = make_doc([{"text": "客廳一景", "style": "旁注-手札圖注"}],
                    [{"path": "g.png", "page": 1}], master="G-圖文版")
    assert slot.images[0].rect is None
    assert "rect" not in document_to_dict(slot)["images"][0]


def test_rect_shape_validation_fast_fail():
    for bad in ([1, 2, 3], "60,100,180,260", [60, 100, 180], [60, "a", 180, 260]):
        with pytest.raises(DocumentError, match="rect"):
            body_doc([{"path": "a.png", "page": 1, "rect": bad}])
    for degenerate in ([180, 100, 60, 260], [60, 260, 180, 100], [60, 100, 60, 260]):
        with pytest.raises(DocumentError, match="rect"):
            body_doc([{"path": "a.png", "page": 1, "rect": degenerate}])


def test_slot_based_still_one_per_page_but_rects_unlimited():
    with pytest.raises(DocumentError, match="figure"):  # 槽式一頁一張守門保留
        body_doc([{"path": "a.png", "page": 1}, {"path": "b.png", "page": 1}])
    doc = body_doc([  # rect 多張＋槽式一張同頁放行
        {"path": "a.png", "page": 1, "rect": [60, 100, 180, 260]},
        {"path": "b.png", "page": 1, "rect": [200, 300, 300, 420]},
        {"path": "c.png", "page": 1},
    ])
    assert len(doc.images) == 3


# ---------- resolve：列表模型 ----------

def test_resolve_rect_images_need_no_figure_slot(template, tmp_path):
    gray_square(tmp_path / "a.png")
    doc = body_doc([{"path": "a.png", "page": 1, "rect": [60, 100, 180, 260]}])
    a_master = template.masters["A-內文版"]  # A 無 figure 槽
    resolved = resolve_placed_images(doc, {1: a_master}, base_dir=tmp_path)
    assert len(resolved[1]) == 1
    _path, _img, rect = resolved[1][0]
    assert rect == (60.0, 100.0, 180.0, 260.0)


def test_resolve_slot_image_still_requires_figure(template, tmp_path):
    gray_square(tmp_path / "a.png")
    doc = body_doc([{"path": "a.png", "page": 1}])
    with pytest.raises(ImageError, match="figure"):
        resolve_placed_images(doc, {1: template.masters["A-內文版"]}, base_dir=tmp_path)


def test_resolve_preserves_order_and_dedups_cache(template, tmp_path):
    gray_square(tmp_path / "same.png")
    gray_square(tmp_path / "other.png", value=200)
    doc = body_doc([
        {"path": "same.png", "page": 1, "rect": [60, 100, 120, 160]},
        {"path": "other.png", "page": 1, "rect": [200, 100, 260, 160]},
        {"path": "same.png", "page": 1, "rect": [60, 300, 120, 360]},
    ])
    resolved = resolve_placed_images(doc, {1: template.masters["A-內文版"]},
                                     base_dir=tmp_path)
    entries = resolved[1]
    assert [Path(e[0]).name for e in entries] == ["same.png", "other.png", "same.png"]
    assert entries[0][1] is entries[2][1]  # 同路徑共用同一 PIL 物件（cache）


# ---------- 兩後端：多圖幾何（需字型） ----------

@needs_fonts
def test_export_multi_rect_images_geometry(template, tmp_path):
    """PDF：兩個 rect 圖框各自 contain 置中（bbox＝rect＋出血）、同路徑單一 XObject；
    溢出版心 rect 照置（真書照片略溢特徵、出血照片正當用法）。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    gray_square(tmp_path / "sq.png", size=(50, 50))
    over_x1 = TRIM_W_PT + 6.0  # 右緣溢出版心 6pt（跨入出血）
    doc = body_doc([
        {"path": "sq.png", "page": 1, "rect": [60, 100, 160, 200]},
        {"path": "sq.png", "page": 1, "rect": [200, 300, 260, 360]},
        {"path": "sq.png", "page": 1, "rect": [over_x1 - 40, 480, over_x1, 520]},
    ])
    out = tmp_path / "rects.pdf"
    result = export_pdf(doc, template, out, footer=False, image_base_dir=tmp_path)
    assert result.violations == []
    pdf = fitz.open(str(out))
    infos = pdf[0].get_images(full=True)
    assert len({i[0] for i in infos}) == 1  # 同路徑去重＝單一 XObject
    rects = sorted((pdf[0].get_image_rects(infos[0][0], transform=False)),
                   key=lambda r: (r.y0, r.x0))
    assert len(rects) == 3
    # 第一框 rect [60,100,160,200]（trim top-down）＋出血偏移；正方圖 contain 滿框
    # （fitz Rect 為 top-down 頁座標，與 trim rect 同向，僅差出血常數）
    r0 = rects[0]
    assert r0.x0 == pytest.approx(BLEED_PT + 60, abs=0.3)
    assert r0.x1 == pytest.approx(BLEED_PT + 160, abs=0.3)
    assert r0.y0 == pytest.approx(BLEED_PT + 100, abs=0.3)
    assert r0.y1 == pytest.approx(BLEED_PT + 200, abs=0.3)
    # 溢出框右緣超過 trim 右界（跨入出血）
    r2 = rects[-1]
    assert r2.x1 > BLEED_PT + TRIM_W_PT + 3.0


@needs_fonts
def test_render_multi_rect_images_pixels(template, tmp_path):
    from cjkfolio.render import render_document

    gray_square(tmp_path / "dark.png", value=30)
    gray_square(tmp_path / "light.png", value=220)
    doc = body_doc([
        {"path": "dark.png", "page": 1, "rect": [60, 100, 120, 160]},
        {"path": "light.png", "page": 1, "rect": [200, 300, 260, 360]},
    ])
    result = render_document(doc, template, tmp_path, dpi=150,
                             image_base_dir=tmp_path)
    assert result.images_placed == 2
    img = Image.open(result.paths[0])
    scale = 150 / 72.0
    assert img.getpixel((round(90 * scale), round(130 * scale))) < 80    # dark 中心
    assert img.getpixel((round(230 * scale), round(330 * scale))) > 180  # light 中心
    assert img.getpixel((round(160 * scale), round(500 * scale))) > 240  # 空白處仍紙白


@needs_fonts
def test_figure_skeleton_only_gated_by_slot_image(template, tmp_path):
    """G 頁只放 rect 圖：figure 槽仍空 → 佔位框照畫（InDesign 空框導引）；
    放槽式圖 → 佔位框消失（Sprint 50 既有語意）。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    gray_square(tmp_path / "p.png")
    caption = [{"text": "客廳一景", "style": "旁注-手札圖注"}]

    def dashes(images):
        doc = make_doc(caption, images, master="G-圖文版")
        out = tmp_path / f"g{len(images)}.pdf"
        export_pdf(doc, template, out, footer=False, image_base_dir=tmp_path)
        return [d for d in fitz.open(str(out))[0].get_drawings() if d.get("dashes") not in (None, "", "[] 0")]

    assert dashes([{"path": "p.png", "page": 1,
                    "rect": [60, 100, 120, 160]}])  # rect 圖不填槽 → 佔位虛線仍在
    assert not dashes([{"path": "p.png", "page": 1}])  # 槽式圖 → 佔位框消失


@needs_fonts
def test_layout_and_book_level_rect_images_flow(template, tmp_path):
    """rect 圖與節式主版共存：A 節頁 rect 圖 resolve 逐頁主版不需 figure。"""
    gray_square(tmp_path / "a.png")
    doc = make_doc(
        [
            {"text": "整理是一場與過去的對話。", "style": "內文-明體直排"},
            {"text": "客廳一景", "style": "旁注-手札圖注", "master": "G-圖文版"},
        ],
        [
            {"path": "a.png", "page": 1, "rect": [60, 100, 120, 160]},
            {"path": "a.png", "page": 2},
        ],
    )
    layout = layout_document(doc, template)
    masters_by_page = {p.number: template.masters[p.master] for p in layout.pages}
    resolved = resolve_placed_images(doc, masters_by_page, base_dir=tmp_path)
    assert set(resolved) == {1, 2}
    assert resolved[1][0][2] == (60.0, 100.0, 120.0, 160.0)
    assert resolved[2][0][2] is None  # G 頁槽式
