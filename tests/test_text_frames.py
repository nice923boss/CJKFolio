"""獨立文字框 v1（Sprint 55）：任意矩形文字框（直排、單一樣式、框內斷行禁則）。

覆蓋：document text_frames 欄位驗證與序列化、frames 框內佈局（欄容量／斷行禁則
／溢字違規不沉默／橫排樣式快速失敗）、兩後端框文字幾何 parity。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.frames import layout_text_frame
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

BLEED_PT = 3 * 72.0 / 25.4


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def A_GRID(template):
    return template.masters["A-內文版"].grid


def make_doc(text_frames, paragraphs=None, master="A-內文版"):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": master},
        "paragraphs": paragraphs if paragraphs is not None else [
            {"text": "整理是一場與過去的對話。", "style": "內文-明體直排"},
        ],
        "text_frames": text_frames,
    })


FRAME = {"text": "客廳側寫", "style": "旁注-手札圖注", "page": 1,
         "rect": [300.0, 120.0, 340.0, 260.0]}


# ---------- document：text_frames 欄位 ----------

def test_text_frame_parse_and_roundtrip():
    doc = make_doc([FRAME])
    tf = doc.text_frames[0]
    assert (tf.text, tf.style, tf.page) == ("客廳側寫", "旁注-手札圖注", 1)
    assert tf.rect == (300.0, 120.0, 340.0, 260.0)
    out = document_to_dict(doc)
    assert out["text_frames"][0]["rect"] == [300.0, 120.0, 340.0, 260.0]
    again = document_from_dict(out)
    assert again.text_frames[0].text == "客廳側寫"
    plain = make_doc([])
    assert plain.text_frames == ()
    assert "text_frames" not in document_to_dict(plain)


def test_text_frame_validation_fast_fail():
    with pytest.raises(DocumentError, match="text"):
        make_doc([{**FRAME, "text": ""}])
    with pytest.raises(DocumentError, match="style"):
        make_doc([{**FRAME, "style": ""}])
    with pytest.raises(DocumentError, match="page"):
        make_doc([{**FRAME, "page": 0}])
    with pytest.raises(DocumentError, match="rect"):
        make_doc([{**FRAME, "rect": [300, 120, 300, 260]}])
    with pytest.raises(DocumentError, match="rect"):
        make_doc([{"text": "無框", "style": "旁注-手札圖注", "page": 1}])


def test_text_frame_rejected_on_v1_schema():
    with pytest.raises(DocumentError, match="document@2"):
        document_from_dict({
            "schema": "cjkfolio/document@1",
            "meta": {"title": "舊", "template": "neizai-zhengli", "master": "A-內文版"},
            "paragraphs": [{"text": "字", "style": "內文-明體直排"}],
            "text_frames": [FRAME],
        })


# ---------- frames：框內直排佈局 ----------

def test_frame_layout_columns_and_capacity(template):
    """框高 140pt、旁注 9pt（advance 9×12.08/11.5≈9.454）→ 每欄 14 字；
    12 字單欄；框寬 40pt、行距槽寬依樣式。"""
    doc = make_doc([{**FRAME, "text": "窗邊的矮櫃留給還沒讀完書"}])  # 12 字
    placed = layout_text_frame(doc.text_frames[0], template, A_GRID(template))
    assert placed.violations == []
    assert len(placed.lines) == 1
    line = placed.lines[0]
    assert sum(c.width for c in line.line.cells) == 12
    # 首欄行軸在框右緣內側半槽（直排右起）
    assert placed.lines[0].axis_x_pt < 340.0
    assert placed.lines[0].axis_x_pt > 300.0


def test_frame_layout_wraps_and_kinsoku(template):
    """超過欄容量折欄；行首禁則（句號）擠入不落欄首。"""
    text = "抽屜留給信件，層架留給茶罐與杯子，窗邊的矮櫃留給還沒讀完的書。"  # 30 字含標點
    doc = make_doc([{**FRAME, "text": text}])
    placed = layout_text_frame(doc.text_frames[0], template, A_GRID(template))
    assert placed.violations == []
    assert len(placed.lines) >= 2
    for pl in placed.lines:
        first = pl.line.cells[0].text
        assert first not in "，。」"  # 禁則不落欄首


def test_frame_overflow_reports_violation(template):
    doc = make_doc([{**FRAME, "rect": [300, 120, 320, 160],  # 窄框：每欄約 4 字、約 1 欄
                     "text": "把留下的東西安放好把留下的東西安放好"}])
    placed = layout_text_frame(doc.text_frames[0], template, A_GRID(template))
    assert placed.violations, "溢字必須列違規（不沉默）"
    assert any("溢" in v for v in placed.violations)


def test_frame_horizontal_style_fast_fail(template):
    doc = make_doc([{**FRAME, "style": "版權頁-CIP橫排"}])
    with pytest.raises(ValueError, match="橫排"):
        layout_text_frame(doc.text_frames[0], template, A_GRID(template))


def test_frame_unknown_style_fast_fail(template):
    doc = make_doc([{**FRAME, "style": "不存在樣式"}])
    with pytest.raises(KeyError, match="不存在樣式"):
        layout_text_frame(doc.text_frames[0], template, A_GRID(template))


# ---------- 兩後端（需字型） ----------

@needs_fonts
def test_export_text_frame_geometry(template, tmp_path):
    """PDF：框文字字墨落框內、首欄 cx＝frames 幾何（＋出血）；body 照排不受影響。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    doc = make_doc([FRAME])
    out = tmp_path / "frame.pdf"
    result = export_pdf(doc, template, out, footer=False)
    assert result.violations == []
    pdf = fitz.open(str(out))
    chars = [
        c for b in pdf[0].get_text("rawdict")["blocks"]
        for ln in b.get("lines", []) for s in ln.get("spans", [])
        for c in s.get("chars", []) if c["c"] in "客廳側寫"
    ]
    assert len(chars) == 4
    placed = layout_text_frame(doc.text_frames[0], template, A_GRID(template))
    axis = placed.lines[0].axis_x_pt
    for c in chars:
        cx = (c["bbox"][0] + c["bbox"][2]) / 2 - BLEED_PT
        assert cx == pytest.approx(axis, abs=1.2)
        # 框緣容忍 3pt＝字型 bearing（字墨可略超字框，Sprint 37 同性質度量差）
        assert 300.0 - 3.0 <= c["bbox"][0] - BLEED_PT and c["bbox"][2] - BLEED_PT <= 340.0 + 3.0
        assert 120.0 - 3.0 <= c["bbox"][1] - BLEED_PT and c["bbox"][3] - BLEED_PT <= 260.0 + 3.0


@needs_fonts
def test_render_text_frame_ink_parity(template, tmp_path):
    """PNG：框區域出現字墨、框外（其下方）紙白；與 PDF 同源幾何（frames 層）。"""
    from PIL import Image, ImageOps

    from cjkfolio.render import render_document

    doc = make_doc([FRAME])
    result = render_document(doc, template, tmp_path, dpi=150, footer=False)
    assert result.violations == []
    img = Image.open(result.paths[0])
    scale = 150 / 72.0
    region = img.crop((round(300 * scale), round(120 * scale),
                       round(340 * scale), round(260 * scale)))
    assert ImageOps.invert(region).getbbox() is not None  # 框內有字墨
    below = img.crop((round(300 * scale), round(300 * scale),
                      round(340 * scale), round(400 * scale)))
    assert ImageOps.invert(below).getbbox() is None  # 框下方紙白


@needs_fonts
def test_frame_page_beyond_flow_fast_fail(template, tmp_path):
    """框頁超出流排頁數 → 快速失敗（同 images 規則；v1 不為框造頁）。"""
    from cjkfolio.render import render_document

    doc = make_doc([{**FRAME, "page": 9}])
    with pytest.raises(ValueError, match="頁"):
        render_document(doc, template, tmp_path, dpi=150)
