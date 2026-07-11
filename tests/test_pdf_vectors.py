"""PDF 寫出層的向量原件與目錄／圖文頁型測試（cjkfolio.pdf_writer）。

自 test_pdf_writer.py 分出（Sprint 32，替代軌 B：測試檔近 800 行上限分檔），涵蓋
CIP 細框（Sprint 14）、目錄天頭虛線（Sprint 15）、目錄條目頁碼＋引導線（Sprint 16）、
目錄篇名嵌線斷開（Sprint 21）、G 圖文版圖框佔位框（Sprint 27）。驗證一律走 PyMuPDF
（與寫出層不同實作，Gate 4 獨立驗證）。測試素材一律自擬（版權紅線）。
"""
import re
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.primitives import cip_frame_rect, toc_rule_line
from cjkfolio.render import horizontal_left_x_pt, line_axis_x_pt, mm_to_pt
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


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_cip_doc(lines):
    """自擬橫排版權頁文件（master F、樣式 版權頁-CIP橫排）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "橫排樣張", "template": "neizai-zhengli", "master": "F-版權頁"},
        "paragraphs": [{"text": t, "style": "版權頁-CIP橫排"} for t in lines],
    })


# ---------- CIP 細框向量原件（Sprint 14） ----------

def _frame_re(content: str):
    """抽內容流第一個矩形路徑 (x_ll, y_ll, w, h)。"""
    m = re.search(r"([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) re", content)
    return tuple(map(float, m.groups())) if m else None


@needs_fonts
def test_export_cip_frame_cmyk_stroke_before_text(template, tmp_path):
    """CIP 細框：CMYK 描邊矩形（re/S/K）在 BT 之前、無 rg/RG（preflight color 不退步）。"""
    doc = make_cip_doc(["自由排版工作室出版品預行編目資料"])
    out = tmp_path / "framed.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert _frame_re(content) is not None, "缺矩形路徑 re"
    assert "\nS\n" in content, "缺描邊算符 S"
    assert "0 0 0 0.92 K" in content, "框描邊非 DeviceCMYK 暖黑 K92（p178 量測：框色同內文）"
    assert content.index(" re") < content.index("BT"), "path 須在文字物件 BT 之前"
    assert " rg" not in content and " RG" not in content, "框殘留 RGB 描邊"


@needs_fonts
def test_export_cip_frame_two_backend_parity(template, tmp_path):
    """框 re 座標＝render 幾何助手（cip_frame_rect）＋出血偏移，兩後端同源。"""
    lines = ["自由排版工作室", "臺北市出版", "ISBN 978-0-00-000000-0"]
    out = tmp_path / "parity.pdf"
    export_pdf(make_cip_doc(lines), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    x_ll, y_ll, w, h = _frame_re(content)

    master = template.masters["F-版權頁"]
    rect = cip_frame_rect(master, horizontal_left_x_pt(master, book_number=1),
                          n_lines=len(lines), frame=master.frame)
    page_h = mm_to_pt(template.page_height_mm)
    assert x_ll == pytest.approx(BLEED_PT + rect.x0, abs=0.3)
    assert y_ll == pytest.approx(page_h + BLEED_PT - rect.y1, abs=0.3)  # y-up 左下角
    assert w == pytest.approx(rect.x1 - rect.x0, abs=0.3)
    assert h == pytest.approx(rect.y1 - rect.y0, abs=0.3)


@needs_fonts
def test_export_cip_frame_preflight_green(template, tmp_path):
    """加框後 CIP PDF 仍過全部 X-1a 機械規則（color-cmyk-only 不退步）。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "framedx.pdf"
    export_pdf(make_cip_doc([
        "自由排版工作室出版品預行編目資料",
        "ISBN 978-0-00-000000-0（平裝）",
    ]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


# ---------- 目錄水平虛線向量原件（Sprint 15） ----------

def make_toc_doc(entries):
    """自擬直排目錄文件（master D、樣式 目錄-篇章條目）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄樣張", "template": "neizai-zhengli", "master": "D-目錄"},
        "paragraphs": [{"text": t, "style": "目錄-篇章條目"} for t in entries],
    })


@needs_fonts
def test_export_toc_rule_dash_stroke_before_text(template, tmp_path):
    """目錄虛線：dash 算符＋灰 K 描邊（d/m/l/S/K）在 BT 之前、q…Q 隔離、無 rg/RG。"""
    out = tmp_path / "toc.pdf"
    export_pdf(make_toc_doc(["安放與整理的十個提問"]), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert "[ 3 2 ] 0 d" in content, "缺 dash 算符 [ 3 2 ] 0 d"
    assert re.search(r"[\d.\-]+ [\d.\-]+ m\n[\d.\-]+ [\d.\-]+ l\nS", content), "缺 m/l/S 線段路徑"
    assert "0 0 0 0.57 K" in content, "虛線描邊非灰 K57"
    assert content.index(" d\n") < content.index("BT"), "dash 須在文字物件 BT 之前"
    assert " rg" not in content and " RG" not in content, "虛線殘留 RGB 描邊"
    # dash 狀態隔離（q…Q 內）：PyMuPDF 獨立解析回報 dashes
    draws = pdf[0].get_drawings()
    dash_lines = [d for d in draws if d.get("dashes") and "3" in d["dashes"]]
    assert dash_lines, f"PyMuPDF 未解析出 dash 線：{[d.get('dashes') for d in draws]}"


@needs_fonts
def test_export_toc_rule_two_backend_parity(template, tmp_path):
    """虛線 m/l 座標＝render 幾何助手（toc_rule_line）＋出血偏移，兩後端同源。"""
    out = tmp_path / "toc-parity.pdf"
    export_pdf(make_toc_doc(["把回憶放回原位的方法"]), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    m = re.search(r"([\d.\-]+) ([\d.\-]+) m\n([\d.\-]+) ([\d.\-]+) l", content)
    assert m, "缺 m/l 線段路徑"
    x0, y0, x1, y1 = map(float, m.groups())

    master = template.masters["D-目錄"]
    line = toc_rule_line(mm_to_pt(template.page_width_mm), master.rule)
    page_h = mm_to_pt(template.page_height_mm)
    assert x0 == pytest.approx(BLEED_PT + line.x0, abs=0.3)
    assert x1 == pytest.approx(BLEED_PT + line.x1, abs=0.3)
    y_up = page_h + BLEED_PT - line.y0  # top-down → y-up
    assert y0 == pytest.approx(y_up, abs=0.3) and y1 == pytest.approx(y_up, abs=0.3)
    # 貼邊出血：線兩端正好落在出血邊（x0=0、x1=頁寬＋2×出血）
    assert x0 == pytest.approx(0.0, abs=0.3)
    assert x1 == pytest.approx(mm_to_pt(template.page_width_mm) + 2 * BLEED_PT, abs=0.3)


@needs_fonts
def test_export_toc_rule_preflight_green(template, tmp_path):
    """加虛線後目錄 PDF 仍過全部 X-1a 機械規則（color-cmyk-only 不退步）。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "tocx.pdf"
    export_pdf(make_toc_doc([
        "安放與整理的十個提問",
        "把回憶放回原位的方法",
    ]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


# ---------- 目錄條目頁碼＋引導線（Sprint 16） ----------

def make_toc_doc_paged(entries_with_pages):
    paras = []
    for text, page_no in entries_with_pages:
        p = {"text": text, "style": "目錄-篇章條目"}
        if page_no is not None:
            p["page_no"] = page_no
        paras.append(p)
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄樣張", "template": "neizai-zhengli", "master": "D-目錄"},
        "paragraphs": paras,
    })


@needs_fonts
def test_export_toc_leader_line_solid_k92_parity(template, tmp_path):
    """引導線：垂直實線（該狀態塊無 d）、K92 描邊、座標＝mark 幾何＋行軸＋出血。"""
    from cjkfolio.layout import layout_document
    doc = make_toc_doc_paged([("安放與整理的十個提問", "169")])
    out = tmp_path / "toc-entry.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert "0 0 0 0.92 K" in content, "引導線描邊非單 K92"
    # 引導線的 q…Q 塊：0.1 w、無 d、垂直 m/l
    blocks = re.findall(r"q\n(.*?)\nQ", content, re.S)
    leader = [b for b in blocks if "0.1 w" in b]
    assert leader, "缺引導線狀態塊（0.1 w）"
    assert " d" not in leader[0], "引導線不應掛 dash"
    lm = re.search(r"([\d.\-]+) ([\d.\-]+) m\n([\d.\-]+) ([\d.\-]+) l", leader[0])
    x0, y0, x1, y1 = map(float, lm.groups())
    assert x0 == pytest.approx(x1, abs=0.01), "引導線應為垂直線"

    master = template.masters["D-目錄"]
    m = layout_document(doc, template).toc_marks[1][0]
    axis = line_axis_x_pt(template, master, m.slot, 1, line_slots=m.line_slots)
    page_h = mm_to_pt(template.page_height_mm)
    assert x0 == pytest.approx(BLEED_PT + axis, abs=0.3)
    # top-down → y-up：兩端點集合比對（emit 順序不拘）
    got = sorted([y0, y1])
    want = sorted([page_h + BLEED_PT - m.leader_y0_pt, page_h + BLEED_PT - m.leader_y1_pt])
    assert got[0] == pytest.approx(want[0], abs=0.3)
    assert got[1] == pytest.approx(want[1], abs=0.3)


@needs_fonts
def test_export_toc_page_no_digits_positions(template, tmp_path):
    """頁碼三位直排逐位：PyMuPDF 抽字座標與 mark 幾何一致（底錨 490pt）。"""
    from cjkfolio.layout import layout_document
    doc = make_toc_doc_paged([("安放與整理的十個提問", "169")])
    out = tmp_path / "toc-digits.pdf"
    export_pdf(doc, template, out, footer=False)
    pdf = fitz.open(str(out))
    words = [w for w in pdf[0].get_text("words") if w[4] in ("1", "6", "9")]
    assert len(words) == 3, f"頁碼應為 3 個獨立直立數字，得到 {words}"

    master = template.masters["D-目錄"]
    m = layout_document(doc, template).toc_marks[1][0]
    axis = line_axis_x_pt(template, master, m.slot, 1, line_slots=m.line_slots)
    # 直排由上而下 1→6→9；PyMuPDF top-down 座標含出血（PDF 頁面原點含 bleed）
    words.sort(key=lambda w: w[1])
    assert [w[4] for w in words] == ["1", "6", "9"]
    for i, w in enumerate(words):
        cx = (w[0] + w[2]) / 2
        assert cx == pytest.approx(BLEED_PT + axis, abs=1.5), f"第 {i} 位未行軸置中"
        cell_top = m.page_no_top_pt + i * m.digit_advance_pt
        assert w[1] >= BLEED_PT + cell_top - 1.5, f"第 {i} 位高於字槽頂"
    # 末位底不越過底錨
    assert words[-1][3] <= BLEED_PT + master.toc.page_no_bottom_pt + 1.5


@needs_fonts
def test_export_toc_entry_preflight_green(template, tmp_path):
    """加頁碼與引導線後目錄 PDF 仍過全部 X-1a 機械規則。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "toc-entryx.pdf"
    export_pdf(make_toc_doc_paged([
        ("安放與整理的十個提問", "169"),
        ("把回憶放回原位的方法", "197"),
    ]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


# ---------- 目錄篇名嵌線斷開（Sprint 21） ----------

def make_toc_doc_with_part(part, entries_with_pages):
    paras = [{"text": part, "style": "目錄-部名"}]
    for text, page_no in entries_with_pages:
        paras.append({"text": text, "style": "目錄-篇章條目", "page_no": page_no})
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "目錄樣張", "template": "neizai-zhengli", "master": "D-目錄"},
        "paragraphs": paras,
    })


@needs_fonts
def test_export_toc_rule_break_two_backend_parity(template, tmp_path):
    """篇名嵌線斷開：PDF 虛線分兩段，端點＝rule_break_ranges＋toc_rule_segments
    手推＋出血偏移（兩後端同源）。"""
    from cjkfolio.layout import layout_document
    from cjkfolio.primitives import toc_rule_segments
    from cjkfolio.render import rule_break_ranges
    doc = make_toc_doc_with_part("把日子放回原位", [("安放與整理的十個提問", "17")])
    out = tmp_path / "toc-break.pdf"
    export_pdf(doc, template, out, footer=False)

    master = template.masters["D-目錄"]
    layout = layout_document(doc, template)
    gaps = rule_break_ranges(template, master, layout.rule_breaks[1], 1)
    segs = toc_rule_segments(mm_to_pt(template.page_width_mm), master.rule, gaps)
    assert len(segs) == 2  # 部名一行 → 斷成兩段

    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    page_h = mm_to_pt(template.page_height_mm)
    y_up = page_h + BLEED_PT - master.rule.y_from_top_pt
    found = [
        (float(m.group(1)), float(m.group(3)))
        for m in re.finditer(r"([\d.\-]+) ([\d.\-]+) m\n([\d.\-]+) ([\d.\-]+) l\nS", content)
        if abs(float(m.group(2)) - y_up) < 0.3 and abs(float(m.group(4)) - y_up) < 0.3
    ]
    assert len(found) == 2, f"虛線 y 列應有兩段線，得到 {found}"
    for (px0, px1), seg in zip(sorted(found), segs):
        assert px0 == pytest.approx(BLEED_PT + seg.x0, abs=0.3)
        assert px1 == pytest.approx(BLEED_PT + seg.x1, abs=0.3)


@needs_fonts
def test_export_toc_rule_break_preflight_green(template, tmp_path):
    """篇名嵌線斷開後目錄 PDF 仍過全部 X-1a 機械規則。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "toc-breakx.pdf"
    export_pdf(make_toc_doc_with_part("把日子放回原位", [
        ("安放與整理的十個提問", "17"),
        ("把回憶放回原位的方法", "63"),
    ]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]


# ---------- G 圖文版圖框保留區佔位框（Sprint 27） ----------

def make_figure_doc(captions):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "圖文版樣張", "template": "neizai-zhengli", "master": "G-圖文版"},
        "paragraphs": [{"text": c, "style": "圖說-辰宇落雁"} for c in captions],
    })


@needs_fonts
def test_export_figure_slot_dash_stroke_before_text(template, tmp_path):
    """圖框保留區佔位框：4 邊 dash 描邊（d/m/l/S/淡灰 K30）在 BT 前、q…Q 隔離、無 rg/RG。"""
    out = tmp_path / "fig.pdf"
    export_pdf(make_figure_doc(["改造前", "改造後"]), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    assert "[ 4 3 ] 0 d" in content, "缺 dash 算符 [ 4 3 ] 0 d"
    assert "0 0 0 0.3 K" in content, "佔位框描邊非淡灰 K30"
    assert content.index(" d\n") < content.index("BT"), "dash 須在文字 BT 之前"
    assert " rg" not in content and " RG" not in content, "佔位框殘留 RGB 描邊"
    dashed = [d for d in pdf[0].get_drawings() if d.get("dashes") and "4" in d["dashes"]]
    assert dashed, "PyMuPDF 未解析出佔位框 dash 線"


@needs_fonts
def test_export_figure_slot_two_backend_parity(template, tmp_path):
    """佔位框四邊 m/l 座標＝figure_slot_rect（承版心鏡像）＋出血偏移，與 render 同源。"""
    from cjkfolio.primitives import figure_slot_edges, figure_slot_rect
    from cjkfolio.render import is_right_page
    out = tmp_path / "fig-parity.pdf"
    export_pdf(make_figure_doc(["改造前"]), template, out, footer=False)
    pdf = fitz.open(str(out))
    content = b"".join(pdf.xref_stream(x) for x in pdf[0].get_contents()).decode("latin-1")
    segs = [tuple(map(float, g)) for g in
            re.findall(r"([\d.\-]+) ([\d.\-]+) m\n([\d.\-]+) ([\d.\-]+) l", content)]
    master = template.masters["G-圖文版"]
    page_h = mm_to_pt(template.page_height_mm)
    rect = figure_slot_rect(mm_to_pt(template.page_width_mm), master,
                            is_right_page(1), master.figure)
    for edge in figure_slot_edges(rect, master.figure):
        want = (BLEED_PT + edge.x0, page_h + BLEED_PT - edge.y0,
                BLEED_PT + edge.x1, page_h + BLEED_PT - edge.y1)
        assert any(all(a == pytest.approx(b, abs=0.3) for a, b in zip(seg, want))
                   for seg in segs), f"缺與 render 同源的邊 {want}"


@needs_fonts
def test_export_figure_preflight_green(template, tmp_path):
    """加圖框保留區佔位框後 G 頁 PDF 仍過全部 X-1a 機械規則（color-cmyk-only 不退步）。"""
    from cjkfolio.preflight import check_pdfx1a
    out = tmp_path / "figx.pdf"
    export_pdf(make_figure_doc(["改造前", "改造後"]), template, out, footer=False)
    report = check_pdfx1a(out)
    assert report.ok, [f for f in report.findings if not f.ok]
