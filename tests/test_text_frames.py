"""獨立文字框（Sprint 55 建立＋Sprint 57 串接）：任意矩形直排文字框。

覆蓋：document text_frames 欄位驗證與序列化（含 thread 串接鏈）、frames 框內
佈局（欄容量／斷行禁則／溢字違規不沉默／橫排樣式快速失敗）、串接跨框續排
（逐框幾何／框邊界禁則／鏈尾溢出／跨頁逐框主版網格）、兩後端框文字幾何 parity。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import DocumentError, document_from_dict, document_to_dict
from cjkfolio.engine import LINE_START_FORBIDDEN, check_kinsoku, normalize
from cjkfolio.frames import layout_text_frame, resolve_text_frames
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


# ---------- 串接（thread，Sprint 57） ----------
# 旁注-手札圖注 8pt 於 A 網格：字距 8.4035pt、欄距 16.0pt。
# 框高 140 → 每欄 16 字；框寬 40 → 2 欄。

CHAIN_TEXT = "安放選擇收納歸位" * 5  # 40 字純 CJK（與 body 段字集無交集）：框 A 32 字＋框 B 8 字
FRAME_A = {"text": CHAIN_TEXT, "style": "旁注-手札圖注", "page": 1,
           "rect": [300.0, 120.0, 340.0, 260.0], "thread": "圖說甲"}
FRAME_B = {"style": "旁注-手札圖注", "page": 1,
           "rect": [200.0, 120.0, 240.0, 260.0], "thread": "圖說甲"}


def masters_page1(template):
    return {1: template.masters["A-內文版"]}


def chain_placements(doc, template, masters=None):
    by_page = resolve_text_frames(doc, template,
                                  masters if masters is not None else masters_page1(template))
    return [pl for page in sorted(by_page) for pl in by_page[page]]


def joined_text(placements) -> str:
    return "".join(
        c.text for pl in placements for fl in pl.lines for c in fl.line.cells
    )


def test_thread_parse_and_roundtrip():
    doc = make_doc([FRAME_A, FRAME_B])
    a, b = doc.text_frames
    assert (a.thread, b.thread) == ("圖說甲", "圖說甲")
    assert a.text == CHAIN_TEXT and b.text == ""
    out = document_to_dict(doc)
    assert out["text_frames"][0]["thread"] == "圖說甲"
    assert "text" not in out["text_frames"][1]  # 續框不寫空 text
    again = document_from_dict(out)
    assert again.text_frames == doc.text_frames
    plain = make_doc([FRAME])  # 無 thread 框序列化不帶 thread 鍵
    assert "thread" not in document_to_dict(plain)["text_frames"][0]


def test_thread_validation_fast_fail():
    with pytest.raises(DocumentError, match="thread"):
        make_doc([{**FRAME_A, "thread": ""}])
    with pytest.raises(DocumentError, match="text"):  # 續框帶 text＝雙源
        make_doc([FRAME_A, {**FRAME_B, "text": "另一段"}])
    with pytest.raises(DocumentError, match="text"):  # 鏈首（首見）text 必非空
        make_doc([{k: v for k, v in FRAME_A.items() if k != "text"}, FRAME_B])
    with pytest.raises(DocumentError, match="style"):  # 續框樣式須與鏈首一致
        make_doc([FRAME_A, {**FRAME_B, "style": "內文-明體直排"}])


def test_thread_flows_across_frames(template):
    """文字流過框 A（2 欄×16 字排滿）續入框 B；內容跨框守恆無重複無遺漏。"""
    doc = make_doc([FRAME_A, FRAME_B])
    pl_a, pl_b = chain_placements(doc, template)
    assert pl_a.violations == [] and pl_b.violations == []
    assert [len(fl.line.cells) for fl in pl_a.lines] == [16, 16]
    assert len(pl_b.lines) == 1 and len(pl_b.lines[0].line.cells) == 8
    assert pl_b.lines[0].line.cells[0].text == normalize(CHAIN_TEXT)[32]
    assert joined_text([pl_a, pl_b]) == normalize(CHAIN_TEXT)
    # 框 B 首欄行軸在框 B 右緣內側半槽（幾何依各自 rect）
    assert pl_b.lines[0].axis_x_pt == pytest.approx(240.0 - 8.0)


def test_thread_kinsoku_at_frame_boundary(template):
    """框邊界禁則：第 33 字為句逗 → 擠入框 A 末欄行尾，框 B 首欄行首非禁則字。"""
    text = "安放選擇收納歸位" * 4 + "，把物件放回原位"  # 32 字＋句逗＋7 字
    doc = make_doc([{**FRAME_A, "text": text}, FRAME_B])
    pl_a, pl_b = chain_placements(doc, template)
    assert pl_a.lines[-1].line.cells[-1].text == "，"  # 句逗擠入前框行尾
    assert pl_b.lines[0].line.cells[0].text not in LINE_START_FORBIDDEN
    for pl in (pl_a, pl_b):
        assert check_kinsoku([fl.line for fl in pl.lines]) == []
    assert joined_text([pl_a, pl_b]) == normalize(text)


def test_thread_respects_each_frame_geometry(template):
    """各框依自身 rect 換算容量：框 B 高 60pt → 每欄 7 字（floor(60/8.4035)）。"""
    text = "安放選擇收納歸位" * 4 + "把時間留給重要的物件"  # 42 字
    doc = make_doc([{**FRAME_A, "text": text},
                    {**FRAME_B, "rect": [200.0, 120.0, 240.0, 180.0]}])
    pl_a, pl_b = chain_placements(doc, template)
    assert [len(fl.line.cells) for fl in pl_a.lines] == [16, 16]
    assert [len(fl.line.cells) for fl in pl_b.lines] == [7, 3]
    assert joined_text([pl_a, pl_b]) == normalize(text)


def test_thread_tail_overflow_reports_violation(template):
    """鏈尾仍排不下 → 違規掛鏈尾（不沉默）；中間框排滿續流不列違規。"""
    doc = make_doc([{**FRAME_A, "text": "把留下的東西安放好還給生活留白",
                     "rect": [300.0, 120.0, 320.0, 155.0]},   # 1 欄×4 字
                    {**FRAME_B, "rect": [200.0, 120.0, 220.0, 155.0]}])
    pl_a, pl_b = chain_placements(doc, template)
    assert pl_a.violations == []
    assert pl_b.violations and any("溢" in v for v in pl_b.violations)
    assert any("串接" in v for v in pl_b.violations)


def test_single_frame_thread_equivalent(template):
    """鏈長 1（帶 thread 單框）與無 thread 單框佈局完全等價。"""
    text = "抽屜留給信件，層架留給茶罐與杯子，窗邊的矮櫃留給還沒讀完的書。"
    doc = make_doc([{**FRAME, "text": text, "thread": "獨"}])
    threaded = chain_placements(doc, template)[0]
    plain = layout_text_frame(
        make_doc([{**FRAME, "text": text}]).text_frames[0], template, A_GRID(template))
    assert threaded.lines == plain.lines
    assert threaded.violations == plain.violations == []


def test_resolve_preserves_document_order(template):
    """同頁混合獨立框與鏈框：繪製序＝文件序（Sprint 54 rect 圖同慣例）。"""
    doc = make_doc([
        {**FRAME_A, "rect": [300.0, 120.0, 340.0, 260.0]},
        {**FRAME, "text": "獨立圖說", "rect": [260.0, 120.0, 290.0, 260.0]},
        FRAME_B,
    ])
    placements = resolve_text_frames(doc, template, masters_page1(template))[1]
    assert len(placements) == 3
    assert placements[0].lines[0].line.cells[0].text == normalize(CHAIN_TEXT)[0]
    assert joined_text([placements[1]]) == "獨立圖說"
    assert placements[2].lines[0].line.cells[0].text == normalize(CHAIN_TEXT)[32]


def test_thread_across_pages_uses_each_page_grid(template):
    """跨頁串接：各框字距依該頁主版網格換算（A 8.4035pt vs B-部扉 8.4384pt）。"""
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [
            {"text": "整理是一場與過去的對話。", "style": "內文-明體直排"},
            {"text": "第二部", "style": "標籤-篇序小標", "master": "B-部扉"},
        ],
        "text_frames": [FRAME_A, {**FRAME_B, "page": 2}],
    })
    masters = {1: template.masters["A-內文版"], 2: template.masters["B-部扉"]}
    by_page = resolve_text_frames(doc, template, masters)
    adv_a = by_page[1][0].lines[0].advance_pt
    adv_b = by_page[2][0].lines[0].advance_pt
    assert adv_a == pytest.approx(8.0 * 12.08 / 11.5)
    assert adv_b == pytest.approx(8.0 * 23.1 / 21.9)
    assert adv_a != pytest.approx(adv_b)


def test_thread_member_page_beyond_flow_fast_fail(template):
    """鏈成員框頁超出流排頁 → 快速失敗（沿用單框規則，不為框造頁）。"""
    doc = make_doc([FRAME_A, {**FRAME_B, "page": 9}])
    with pytest.raises(ValueError, match="頁"):
        resolve_text_frames(doc, template, masters_page1(template))


@needs_fonts
def test_export_thread_geometry(template, tmp_path):
    """PDF：串接雙框字元恰各一次、各落其框（±3pt bearing）、cx＝各框行軸。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    doc = make_doc([FRAME_A, FRAME_B])
    out = tmp_path / "thread.pdf"
    result = export_pdf(doc, template, out, footer=False)
    assert result.violations == []
    pl_a, pl_b = chain_placements(doc, template)
    pdf = fitz.open(str(out))
    boxes = {"A": (300.0, 340.0), "B": (200.0, 240.0)}
    counts = {"A": 0, "B": 0}
    for b in pdf[0].get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln.get("spans", []):
                for c in s.get("chars", []):
                    if c["c"] not in CHAIN_TEXT:
                        continue
                    cx = (c["bbox"][0] + c["bbox"][2]) / 2 - BLEED_PT
                    key = "A" if cx > 270.0 else "B"
                    counts[key] += 1
                    x0, x1 = boxes[key]
                    assert x0 - 3.0 <= c["bbox"][0] - BLEED_PT
                    assert c["bbox"][2] - BLEED_PT <= x1 + 3.0
                    axes = [fl.axis_x_pt for fl in (pl_a if key == "A" else pl_b).lines]
                    assert min(abs(cx - ax) for ax in axes) <= 1.2
    assert counts["A"] == 32 and counts["B"] == 8  # 40 字恰各一次、無跨框重複


@needs_fonts
def test_render_thread_ink_both_frames(template, tmp_path):
    """PNG：串接雙框皆有字墨（同源幾何，frames 層）。"""
    from PIL import Image, ImageOps

    from cjkfolio.render import render_document

    doc = make_doc([FRAME_A, FRAME_B])
    result = render_document(doc, template, tmp_path, dpi=150, footer=False)
    assert result.violations == []
    img = Image.open(result.paths[0])
    scale = 150 / 72.0
    for x0, x1 in ((300, 340), (200, 240)):
        region = img.crop((round(x0 * scale), round(120 * scale),
                           round(x1 * scale), round(260 * scale)))
        assert ImageOps.invert(region).getbbox() is not None
