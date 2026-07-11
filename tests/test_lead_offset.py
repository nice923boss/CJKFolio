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
