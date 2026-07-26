"""段級 inline 軸 sub-slot pt 偏移（lead_offset_pt，Sprint 29 引擎 pt 精度模型）。

驗證 B-部扉大標「首字頂比部序號低 6.02pt」（Sprint 20 三頁互證 A 級量測，原
整數槽模型已知差異，GAPS #13）由 pt 偏移落地：兩後端 body 首字下移恰 6.02pt、
部序號標籤不動。兩渲染差分（offset 6.02 vs 0）令字型 ascent 度量抵消，只留偏移量。
測試素材自擬（版權紅線）。
"""
import dataclasses
import json
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.layout import layout_document
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.render import render_document
from cjkfolio.styles import load_template

fitz = pytest.importorskip("fitz")
from PIL import Image, ImageOps  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
SAMPLE = ROOT / "samples" / "part-divider.doc.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)

LEAD = 6.02          # 大標首字頂低於部序號的量測值（Sprint 20，pt）
DA_BIAO = "部扉大標-明體W9"
DA_AXIS = 194.12     # 大標行軸 x（slot 1，三頁互證）
LABEL_AXIS = 228.49  # 部序號行軸 x（slot 0）


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def _part_doc():
    return document_from_dict(json.loads(SAMPLE.read_text(encoding="utf-8")))


def _zero_lead(template):
    """大標 lead_offset_pt 歸零的模版副本（兩渲染差分的基準）。"""
    styles = dict(template.paragraph_styles)
    styles[DA_BIAO] = dataclasses.replace(styles[DA_BIAO], lead_offset_pt=0.0)
    return dataclasses.replace(template, paragraph_styles=styles)


def test_lead_offset_wired_to_placed_line(template):
    """styles → layout：大標 PlacedLine 帶 6.02、部序號帶 0（font-free 布線驗證）。"""
    layout = layout_document(_part_doc(), template)
    label, headline = layout.pages[0].placed
    assert headline.style == DA_BIAO
    assert headline.lead_offset_pt == pytest.approx(LEAD)
    assert label.lead_offset_pt == 0.0


def _pdf_tops(template, out):
    """export → 回傳 (大標首字墨頂 y, 部序號首字墨頂 y)；top-down、含出血（差分抵消）。"""
    export_pdf(_part_doc(), template, out, footer=False)
    da, label = [], []
    for blk in fitz.open(str(out))[0].get_text("rawdict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                bucket = da if sp["size"] > 18 else label
                bucket.extend(ch["bbox"][1] for ch in sp["chars"])
    return min(da), min(label)


def _png_tops(template, out_dir, scale):
    """render → 回傳 (大標欄墨頂 px, 部序號欄墨頂 px)；裁各自行軸欄隔離兩段。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    result = render_document(_part_doc(), template, out_dir, dpi=round(scale * 72),
                             footer=False)
    ink = ImageOps.invert(Image.open(result.paths[0]).convert("L"))

    def col_top(axis_pt, half_pt):
        crop = ink.crop((int((axis_pt - half_pt) * scale), 0,
                         int((axis_pt + half_pt) * scale), ink.height))
        bb = crop.getbbox()
        assert bb is not None, f"行軸 {axis_pt} 欄無墨"
        return bb[1]

    return col_top(DA_AXIS, 11.0), col_top(LABEL_AXIS, 9.0)


@needs_fonts
def test_lead_offset_shifts_pdf_glyph(template, tmp_path):
    """PDF 後端：大標首字墨頂下移恰 6.02pt、部序號不動（兩渲染差分）。"""
    da_on, label_on = _pdf_tops(template, tmp_path / "on.pdf")
    da_off, label_off = _pdf_tops(_zero_lead(template), tmp_path / "off.pdf")
    assert da_on - da_off == pytest.approx(LEAD, abs=0.05)
    assert label_on == pytest.approx(label_off, abs=0.05)


@needs_fonts
def test_lead_offset_shifts_png_glyph(template, tmp_path):
    """PNG 後端（render，與 pdf 同源）：大標欄墨頂下移恰 6.02pt、部序號不動。"""
    scale = 300 / 72.0
    da_on, label_on = _png_tops(template, tmp_path / "on", scale)
    da_off, label_off = _png_tops(_zero_lead(template), tmp_path / "off", scale)
    assert (da_on - da_off) / scale == pytest.approx(LEAD, abs=0.3)
    assert label_on == pytest.approx(label_off, abs=1)


# ---------- Sprint 30：目錄條目 lead_offset 接入 _toc_marks 與 _rule_breaks ----------
# Sprint 29 只套用直排 body；目錄條目 body 偏移須同步引導線起點（title_end→leader_y0）
# 與穿線判定（rule_break 的 line_top），否則條目下移但引導線／穿線不跟隨。機制與模版
# 真值解耦（此處施加合成 lead_offset），font-free 布線驗證。

ENTRY = "目錄-篇章條目"
TOC_MASTER = "D-目錄"


def _toc_doc(text="安放與整理的十個提問", page_no="169"):
    """自擬目錄條目文件（版權紅線：文字自擬）。"""
    para = {"text": text, "style": ENTRY}
    if page_no is not None:
        para["page_no"] = page_no
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄機制樣張", "template": "neizai-zhengli", "master": TOC_MASTER},
        "paragraphs": [para],
    })


def _entry_lead(template, value):
    """施加 lead_offset_pt 到目錄-篇章條目（機制驗證，與模版真值解耦）。"""
    styles = dict(template.paragraph_styles)
    styles[ENTRY] = dataclasses.replace(styles[ENTRY], lead_offset_pt=value)
    return dataclasses.replace(template, paragraph_styles=styles)


def test_toc_lead_offset_shifts_leader_start_not_page_anchor(template):
    """目錄條目 lead_offset：引導線起 leader_y0（標題末＋gap）同量偏移；頁碼底錨
    page_no_top 與線終 leader_y1（錨頁碼）不動（條目位置微調不牽動固定底錨）。"""
    off = layout_document(_toc_doc(), _entry_lead(template, 0.0)).toc_marks[1][0]
    on = layout_document(_toc_doc(), _entry_lead(template, 6.0)).toc_marks[1][0]
    assert on.leader_y0_pt - off.leader_y0_pt == pytest.approx(6.0)
    assert on.page_no_top_pt == pytest.approx(off.page_no_top_pt)  # 頁碼固定底錨不隨條目
    assert on.leader_y1_pt == pytest.approx(off.leader_y1_pt)      # 線終錨頁碼頂


def test_toc_lead_offset_syncs_rule_break_crossing(toc_rule_template):
    """穿線判定 line_top 同步 lead_offset：條目上移跨越虛線 y → 產 RuleBreak；
    下移維持不穿（判定跟隨 body 實際位置，Sprint 30 正題）。

    吃回歸模版：產品模版自 Sprint 141 起不宣告 rule（見 tests/conftest.py）。"""
    template = toc_rule_template
    base = layout_document(_toc_doc(), _entry_lead(template, 0.0))
    assert base.rule_breaks == {}  # 縮退條目（lead 歸零基準）在虛線下、不穿
    up = layout_document(_toc_doc(), _entry_lead(template, -12.0))  # 上移使框頂穿線
    assert len(up.rule_breaks[1]) == 1
    down = layout_document(_toc_doc(), _entry_lead(template, 6.0))  # 下移更不穿
    assert down.rule_breaks == {}


# ---------- Sprint 30：目錄章名條目墨頂貼真書（絕對值＋兩渲染差分，兩後端） ----------
# 交接目標 (b)＋Gate 4 勘正：Sprint 24「墨頂 137.42 vs 真書 135.15、+2.27」係拿 model 含
# 出血 media 座標比真書無出血 trim（真書 PDF 實測 media＝trim，無出血），未扣 3mm 出血
# 8.504pt，屬 GAPS #21 同型座標框錯配。扣出血後 model trim 墨頂 128.91 vs 真書 135.15，
# 正確 lead_offset_pt＝+6.24（下移）。絕對值用 PyMuPDF span top（同 measure_toc_page 口徑）
# 扣出血比對；PNG／PDF 差分抵消口徑與出血、僅留偏移量。

ENTRY_LEAD = 6.24            # 目錄-篇章條目 lead_offset_pt（模版值）
TRUE_ENTRY_INK_TOP = 135.15  # 真書章名首字墨頂（Sprint 24 A 級 p002/p003 六列平均）
BLEED_PT = 3 * 72.0 / 25.4   # 3mm 出血＝8.5039pt（media→trim 換算）


def _entry_pdf_ink_top(template, out, trim=True):
    """model PDF 條目 CJK 首字 span bbox top；trim=True 扣出血（貼真書無出血同空間）。"""
    export_pdf(_toc_doc(), template, out, footer=False)
    tops = [sp["bbox"][1]
            for blk in fitz.open(str(out))[0].get_text("dict")["blocks"]
            for ln in blk.get("lines", [])
            for sp in ln.get("spans", [])
            if sp["size"] > 10 and not sp["font"].startswith(("Times", "Gill", "Pepita"))]
    assert tops, "無條目 CJK span"
    return min(tops) - (BLEED_PT if trim else 0.0)


@needs_fonts
def test_toc_entry_ink_top_matches_reference_trim(template, tmp_path):
    """絕對值：條目墨頂（PyMuPDF span top 扣出血→trim）貼真書 135.15（Gate 4 勘正）。"""
    on = _entry_pdf_ink_top(template, tmp_path / "on.pdf")
    assert on == pytest.approx(TRUE_ENTRY_INK_TOP, abs=0.1)


@needs_fonts
def test_toc_entry_lead_offset_shifts_pdf_glyph(template, tmp_path):
    """PDF 兩渲染差分：條目墨頂下移恰 6.24pt（media 差分，出血抵消）。"""
    on = _entry_pdf_ink_top(template, tmp_path / "on.pdf", trim=False)
    off = _entry_pdf_ink_top(_entry_lead(template, 0.0), tmp_path / "off.pdf", trim=False)
    assert on - off == pytest.approx(ENTRY_LEAD, abs=0.05)


@needs_fonts
def test_toc_entry_lead_offset_shifts_png_glyph(template, tmp_path):
    """PNG 後端（與 pdf 同源）：條目首字墨頂下移恰 6.24pt（裁虛線下方排除 toc-rule）。"""
    scale = 300 / 72.0

    def entry_png_top(tpl, d):
        d.mkdir(parents=True, exist_ok=True)
        r = render_document(_toc_doc(), tpl, d, dpi=300, footer=False)
        ink = ImageOps.invert(Image.open(r.paths[0]).convert("L"))
        y0 = round(128 * scale)  # 排除 toc-rule 虛線（y=122.46）
        bb = ink.crop((0, y0, ink.width, ink.height)).getbbox()
        assert bb is not None, "條目區無墨"
        return (bb[1] + y0) / scale

    on = entry_png_top(template, tmp_path / "on")
    off = entry_png_top(_entry_lead(template, 0.0), tmp_path / "off")
    assert on - off == pytest.approx(ENTRY_LEAD, abs=0.3)
