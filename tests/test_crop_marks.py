"""裁切標記（trim／crop marks）測試（Sprint 83，Phase 4 印前完稿）。

opt-in：crop_marks=False 為預設，輸出位元與 Sprint 82 前一致（零回歸）；開啟時
MediaBox 較 BleedBox 外擴（標記居於兩者之間）、BleedBox＝trim＋出血、8 條角標於
trim 外。驗證分兩軌：純函式 crop_mark_lines 幾何單測＋PyMuPDF 獨立解析內容流線段
（Gate 4，與寫出層不同實作）。素材一律自擬（版權紅線）。
"""
import json
import re
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.pdf_writer import MARK_LENGTH_MM, export_pdf, page_boxes_pt
from cjkfolio.primitives import crop_mark_lines
from cjkfolio.render import mm_to_pt
from cjkfolio.styles import load_template

fitz = pytest.importorskip("fitz")

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

BLEED_PT = mm_to_pt(3.0)
MARK_PT = mm_to_pt(MARK_LENGTH_MM)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(texts):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "裁切樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": t, "style": "內文-明體直排"} for t in texts],
    })


def _seg_re(content: str):
    """抽內容流所有 m/l/S 線段路徑 (x0,y0,x1,y1)。"""
    return [tuple(map(float, m)) for m in re.findall(
        r"([\d.\-]+) ([\d.\-]+) m\n([\d.\-]+) ([\d.\-]+) l\nS", content)]


def _contains(outer, inner, tol=0.1):
    return (outer[0] <= inner[0] + tol and outer[1] <= inner[1] + tol
            and outer[2] + tol >= inner[2] and outer[3] + tol >= inner[3])


# ---------- 純函式：crop_mark_lines 幾何 ----------

def test_crop_mark_lines_count_and_style():
    lines = crop_mark_lines(100.0, 200.0, offset_pt=8.5, length_pt=8.5,
                            cmyk=(0.0, 0.0, 0.0, 1.0), line_width_pt=0.25)
    assert len(lines) == 8
    assert all(ln.cmyk == (0.0, 0.0, 0.0, 1.0) for ln in lines)
    assert all(ln.line_width_pt == 0.25 for ln in lines)
    assert all(ln.dash_on_pt == 0.0 for ln in lines)  # 角標為實線
    # 每條線純水平或純垂直
    assert all((ln.x0 == ln.x1) or (ln.y0 == ln.y1) for ln in lines)


def test_crop_mark_lines_corner_geometry():
    W, H, o, L = 100.0, 200.0, 8.5, 3.0
    lines = crop_mark_lines(W, H, offset_pt=o, length_pt=L,
                            cmyk=(0.0, 0.0, 0.0, 1.0), line_width_pt=0.25)
    got = {(round(ln.x0, 3), round(ln.y0, 3), round(ln.x1, 3), round(ln.y1, 3))
           for ln in lines}
    want = {
        (-(o + L), 0.0, -o, 0.0),          # 左上 水平（延伸上邊向左）
        (0.0, -(o + L), 0.0, -o),          # 左上 垂直（延伸左邊向上）
        (W + o, 0.0, W + o + L, 0.0),      # 右上 水平
        (W, -(o + L), W, -o),              # 右上 垂直
        (-(o + L), H, -o, H),              # 左下 水平
        (0.0, H + o, 0.0, H + o + L),      # 左下 垂直
        (W + o, H, W + o + L, H),          # 右下 水平
        (W, H + o, W, H + o + L),          # 右下 垂直
    }
    want = {(round(a, 3), round(b, 3), round(c, 3), round(d, 3)) for a, b, c, d in want}
    assert got == want


def test_crop_marks_lie_outside_trim():
    W, H, o, L = 100.0, 200.0, 8.5, 3.0
    for ln in crop_mark_lines(W, H, offset_pt=o, length_pt=L,
                              cmyk=(0.0, 0.0, 0.0, 1.0), line_width_pt=0.25):
        xs = sorted((ln.x0, ln.x1))
        ys = sorted((ln.y0, ln.y1))
        # 整段不進入 trim 內部矩形 (0,0)-(W,H)
        outside = xs[1] <= 0 or xs[0] >= W or ys[1] <= 0 or ys[0] >= H
        assert outside, (ln.x0, ln.y0, ln.x1, ln.y1)


# ---------- page_boxes_pt ----------

def test_page_boxes_no_marks_bleed_equals_media(template):
    media, trim, bleed = page_boxes_pt(template)
    assert bleed == media  # §9 無標記：BleedBox＝MediaBox
    assert media == pytest.approx((0.0, 0.0, mm_to_pt(154), mm_to_pt(216)))
    assert trim == pytest.approx(
        (BLEED_PT, BLEED_PT, BLEED_PT + mm_to_pt(148), BLEED_PT + mm_to_pt(210)))


def test_page_boxes_with_marks_nested(template):
    media, trim, bleed = page_boxes_pt(template, mark_margin_mm=MARK_LENGTH_MM)
    # MediaBox 於 BleedBox 外再擴 mark 於四邊
    assert media[2] == pytest.approx(mm_to_pt(154) + 2 * MARK_PT)
    assert media[3] == pytest.approx(mm_to_pt(216) + 2 * MARK_PT)
    # BleedBox＝trim＋3mm 出血（148＋6＝154）
    assert bleed == pytest.approx(
        (MARK_PT, MARK_PT, MARK_PT + mm_to_pt(154), MARK_PT + mm_to_pt(216)))
    # trim 置中於 media（左右邊距皆＝出血＋mark）
    assert trim[0] == pytest.approx(BLEED_PT + MARK_PT)
    assert trim[0] == pytest.approx((media[2] - mm_to_pt(148)) / 2)
    # 巢狀：trim ⊂ bleed ⊂ media
    assert _contains(bleed, trim) and _contains(media, bleed)


# ---------- 匯出：預設無標記（零回歸） ----------

@needs_fonts
def test_export_default_no_crop_marks(template, tmp_path):
    out = tmp_path / "nomark.pdf"
    export_pdf(make_doc(["安靜的整理"]), template, out, footer=False)
    page = fitz.open(str(out))[0]
    assert page.mediabox.width == pytest.approx(mm_to_pt(154), abs=0.02)
    assert tuple(page.bleedbox) == pytest.approx(tuple(page.mediabox), abs=0.02)
    content = b"".join(page.parent.xref_stream(x) for x in page.get_contents()).decode("latin-1")
    assert not _seg_re(content), "純文字頁不應有角標線段"


# ---------- 匯出：開啟標記（PyMuPDF 獨立驗證） ----------

@needs_fonts
def test_export_crop_marks_boxes(template, tmp_path):
    out = tmp_path / "mark.pdf"
    export_pdf(make_doc(["安靜的整理", "把回憶放回原位"]), template, out,
               footer=False, crop_marks=True)
    page = fitz.open(str(out))[0]
    # MediaBox 外擴、BleedBox 縮回 trim＋3mm、TrimBox 不變
    assert page.mediabox.width == pytest.approx(mm_to_pt(154) + 2 * MARK_PT, abs=0.05)
    assert page.mediabox.height == pytest.approx(mm_to_pt(216) + 2 * MARK_PT, abs=0.05)
    assert page.bleedbox.width == pytest.approx(mm_to_pt(154), abs=0.05)
    assert page.trimbox.width == pytest.approx(mm_to_pt(148), abs=0.05)
    assert _contains(tuple(page.mediabox), tuple(page.bleedbox))
    assert _contains(tuple(page.bleedbox), tuple(page.trimbox))


@needs_fonts
def test_export_crop_marks_eight_segments_cmyk(template, tmp_path):
    out = tmp_path / "mark8.pdf"
    export_pdf(make_doc(["安靜的整理"]), template, out, footer=False, crop_marks=True)
    page = fitz.open(str(out))[0]
    content = b"".join(page.parent.xref_stream(x) for x in page.get_contents()).decode("latin-1")
    segs = _seg_re(content)
    assert len(segs) == 8, f"角標線段數＝{len(segs)}，應為 8"
    assert "0 0 0 1 K" in content, "角標非單 K registration 描邊"
    assert " rg" not in content and " RG" not in content, "角標殘留 RGB 描邊"
    # 角標在文字物件 BT 之前（獨立 q…Q，狀態隔離）
    assert content.index(" m\n") < content.index("BT")


@needs_fonts
def test_export_crop_marks_geometry_parity(template, tmp_path):
    """8 條角標內容流座標＝crop_mark_lines＋origin 偏移（獨立公式，Gate 4）。"""
    out = tmp_path / "markp.pdf"
    export_pdf(make_doc(["安靜的整理"]), template, out, footer=False, crop_marks=True)
    page = fitz.open(str(out))[0]
    content = b"".join(page.parent.xref_stream(x) for x in page.get_contents()).decode("latin-1")
    got = {tuple(round(v, 2) for v in s) for s in _seg_re(content)}

    trim_w, trim_h = mm_to_pt(148), mm_to_pt(210)
    origin = BLEED_PT + MARK_PT  # media 左下→trim 左下偏移
    page_h = mm_to_pt(template.page_height_mm)
    want = set()
    for ln in crop_mark_lines(trim_w, trim_h, offset_pt=BLEED_PT, length_pt=MARK_PT,
                              cmyk=(0.0, 0.0, 0.0, 1.0), line_width_pt=0.25):
        x0 = origin + ln.x0
        y0 = page_h + origin - ln.y0
        x1 = origin + ln.x1
        y1 = page_h + origin - ln.y1
        want.add((round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)))
    assert got == want


@needs_fonts
def test_crop_marks_do_not_shift_body_relative_to_trim(template, tmp_path):
    """外擴 MediaBox 不得位移內文相對 trim：marks off／on 首字 trim 空間位置相等。"""
    off, on = tmp_path / "off.pdf", tmp_path / "on.pdf"
    export_pdf(make_doc(["安靜的整理"]), template, off, footer=False)
    export_pdf(make_doc(["安靜的整理"]), template, on, footer=False, crop_marks=True)

    def first_word_trim_xy(path, origin):
        page = fitz.open(str(path))[0]
        w = page.get_text("words")[0]  # (x0,y0,x1,y1,word,...)；fitz media 左上為原點
        cx = (w[0] + w[2]) / 2 - origin
        cy = (w[1] + w[3]) / 2 - origin
        return cx, cy

    cx_off, cy_off = first_word_trim_xy(off, BLEED_PT)
    cx_on, cy_on = first_word_trim_xy(on, BLEED_PT + MARK_PT)
    assert cx_off == pytest.approx(cx_on, abs=0.3)
    assert cy_off == pytest.approx(cy_on, abs=0.3)


@needs_fonts
def test_crop_marks_preflight_green(template, tmp_path):
    from cjkfolio.preflight import check_pdfx
    out = tmp_path / "markx.pdf"
    export_pdf(make_doc(["安靜的整理", "整理的十個提問"]), template, out,
               footer=False, crop_marks=True)
    report = check_pdfx(out, profile="x-1a")
    assert report.ok, [f for f in report.findings if not f.ok]


@needs_fonts
def test_cli_crop_marks_flag(tmp_path):
    from cjkfolio.cli import main
    docp = tmp_path / "d.json"
    docp.write_text(json.dumps({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "CLI 裁切", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "安靜的整理", "style": "內文-明體直排"}],
    }, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "cli.pdf"
    rc = main(["export-pdf", str(docp), "-o", str(out),
               "--template", str(TEMPLATE), "--no-footer", "--crop-marks"])
    assert rc == 0
    page = fitz.open(str(out))[0]
    assert page.mediabox.width == pytest.approx(mm_to_pt(154) + 2 * MARK_PT, abs=0.05)
