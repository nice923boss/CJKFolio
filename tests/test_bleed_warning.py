"""滿版圖出血不足警告（Sprint 156）。

Owner 回報：編輯器裡封面圖看起來滿版，匯出 PDF 卻左右有白邊。原因是 PDF 的
BleedBox 每邊比成品多 3mm，圖只拉到成品邊，出血區就是白的；畫布只畫成品範圍，
所以在編輯器看不出來。匯出時據實列出哪一頁哪張圖的哪幾邊缺出血。

兩側獨立（Gate 4）：產出側看 PdfResult.bleed_warnings，驗證側用 PyMuPDF 直接量
寫出 PDF 的影像 bbox 與 BleedBox，不採信產出側的判定。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import fitz
import pytest
from PIL import Image

from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.images import BLEED_NEAR_EDGE_PT, bleed_gap_warning
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.primitives import ImageBox
from cjkfolio.render import mm_to_pt
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
W = mm_to_pt(148.0)
H = mm_to_pt(210.0)
B = mm_to_pt(3.0)


def warn(x0, y0, x1, y1):
    return bleed_gap_warning("a.png", 1, ImageBox(x0, y0, x1, y1), W, H, B)


def test_image_stopping_at_trim_warns_all_four_edges():
    message = warn(0.0, 0.0, W, H)
    assert "頁 1 a.png 的上、下、左、右緣貼著成品邊" in message
    assert "3mm 出血線" in message


def test_image_reaching_bleed_line_is_fine():
    assert warn(-B, -B, W + B, H + B) is None
    assert warn(-B + 0.3, -B, W + B, H + B) is None, "0.5pt 內的捨入差視為已達出血線"


def test_only_short_edges_are_named():
    """Owner 原稿：上下已溢出、右緣拉過出血線，只有左緣停在成品邊。"""
    message = warn(0.0, -27.9, 431.95, 620.0)
    assert "的左緣貼著成品邊" in message


def test_image_kept_away_from_edges_is_a_design_choice():
    """離成品邊超過 1mm 的圖是刻意留白，不報。"""
    gap = BLEED_NEAR_EDGE_PT + 1.0
    assert warn(gap, gap, W - gap, H - gap) is None


def test_image_slightly_inside_trim_still_warns():
    """差 0.5pt 沒貼齊成品邊（拖曳誤差）：裁切後就是一條白線，照報。"""
    assert "右緣" in warn(-B, -B, W - 0.5, H + B)


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def export_with(tmp_path, template, rect, size_px):
    """size_px 取與 rect 同比例，contain 縮放後繪製框即 rect。"""
    Image.new("L", size_px, 90).save(tmp_path / "cover.png")
    doc = Document(title="出血樣張", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="出血測試內文。", style="內文-明體直排"),),
                   images=(PlacedImage(path="cover.png", page=1, rect=rect),))
    result = export_pdf(doc, template, tmp_path / "out.pdf", pdfx="none",
                        image_base_dir=tmp_path)
    page = fitz.open(result.path)[0]
    return result, page.get_image_info()[0]["bbox"], page.bleedbox


def test_export_reports_trim_only_image_and_pdf_shows_white_bleed(tmp_path, template):
    result, bbox, bleed = export_with(tmp_path, template, (0.0, 0.0, W, H), (148, 210))
    assert len(result.bleed_warnings) == 1
    assert "上、下、左、右緣" in result.bleed_warnings[0]
    assert bbox[0] - bleed.x0 == pytest.approx(B, abs=0.01), "PDF 左側出血區確實沒圖"


def test_export_full_bleed_image_has_no_warning(tmp_path, template):
    result, bbox, bleed = export_with(tmp_path, template, (-B, -B, W + B, H + B),
                                    (154, 216))
    assert result.bleed_warnings == ()
    assert bbox[0] <= bleed.x0 + 0.01 and bbox[2] >= bleed.x1 - 0.01


def export_trim_only(tmp_path, template, rect, size_px, **opts):
    Image.new("L", size_px, 90).save(tmp_path / "cover.png")
    doc = Document(title="成品範圍樣張", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="成品範圍內文。", style="內文-明體直排"),),
                   images=(PlacedImage(path="cover.png", page=1, rect=rect),))
    return export_pdf(doc, template, tmp_path / "trim.pdf", pdfx="none",
                      image_base_dir=tmp_path, trim_only=True, **opts)


def test_trim_only_boxes_equal_trim_and_image_covers_page(tmp_path, template):
    """Owner 要的「只輸出成品範圍、不要白邊」：三框＝成品，溢出的圖蓋滿整頁。"""
    result = export_trim_only(tmp_path, template, (-B, -B, W + B, H + B), (154, 216))
    page = fitz.open(result.path)[0]
    assert result.trim_only and result.bleed_warnings == ()
    for box in (page.mediabox, page.trimbox, page.bleedbox):
        assert (box.width, box.height) == pytest.approx((W, H), abs=0.01)
    bbox = page.get_image_info()[0]["bbox"]
    assert bbox[0] <= 0.01 and bbox[1] <= 0.01
    assert bbox[2] >= W - 0.01 and bbox[3] >= H - 0.01, "圖蓋滿成品頁面，四邊無白"


def test_trim_only_keeps_content_position_relative_to_trim(tmp_path, template):
    """成品內的內容相對成品邊不位移：與含出血版本相比，座標差恰為出血量。"""
    rect = (10.0, 10.0, 50.0, 50.0)
    trim = export_trim_only(tmp_path, template, rect, (40, 40))
    _, full, _ = export_with(tmp_path, template, rect, (40, 40))
    t = fitz.open(trim.path)[0].get_image_info()[0]["bbox"]
    assert t[0] == pytest.approx(10.0, abs=0.01) and t[1] == pytest.approx(10.0, abs=0.01)
    assert full[0] - t[0] == pytest.approx(B, abs=0.01)


def test_trim_only_rejects_crop_marks(tmp_path, template):
    with pytest.raises(ValueError, match="裁切標記、印前標記無處可放"):
        export_trim_only(tmp_path, template, (10.0, 10.0, 50.0, 50.0), (40, 40),
                         crop_marks=True)
