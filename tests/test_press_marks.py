"""印前標記（Sprint 109，GAPS #42 (b)、#56 乙(9)）測試。

Sprint 83 只做了 trim 角標。本檔涵蓋三類印前標記：四邊中點套準十字、下標記帶
色條、上標記帶灰梯尺，以及它們共同需要的第一個填色路徑（`re` + `f`）。

**定位（Owner 於 Gate 0 放行）**：機制已驗、參數待印廠確認。本專案從未接觸過
印刷廠（GAPS #11／#18／#41），故所有尺寸為 D 級推導，色條**不宣稱相容於任何
標準控制條**。可機械驗證的是機制：幾何落點、盒框巢狀、算符落地、互不碰撞、
TAC 據實回報。

**期望值一律以 mm 字面值寫在本檔內並自行換算**，不 import 產出端常數、不呼叫
產出端幾何函式，否則測試只是把實作抄一遍（自我背書）。
"""
import re
from pathlib import Path

import pytest

from cjkfolio.primitives import PT_PER_MM

W_MM, H_MM = 148.0, 210.0          # trim 開本（參考書模版）
BLEED_MM = 3.0                     # 出血
BAND_MM = 8.0                      # 印前標記帶寬
PATCH_MM = 6.0                     # 色塊邊長
GAP_MM = 1.0                       # 帶內留白與塊間隙
ARM_MM = 3.0                       # 十字臂半長
BOX_MM = 1.5                       # 同心方框半邊
PITCH_MM = PATCH_MM + GAP_MM       # 7.0

BAR_SWATCHES = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1),
                (1, 1, 0, 0), (1, 0, 1, 0), (0, 1, 1, 0), (1, 1, 1, 0))
RAMP_STEPS = (0.05, 0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 0.90, 1.00)


def mm(v: float) -> float:
    """本檔自行換算，不用產出端的換算函式。"""
    return v * PT_PER_MM


def patch_x_mm(i: int):
    """第 i 塊色塊的 x 區間（mm），色條與灰梯尺共用同一排法。"""
    x0 = GAP_MM + i * PITCH_MM
    return x0, x0 + PATCH_MM


def envelope(shape):
    """任一原件的包絡盒 (x0, y0, x1, y1)，座標排序後回傳。"""
    xs = sorted((shape.x0, shape.x1))
    ys = sorted((shape.y0, shape.y1))
    return (xs[0], ys[0], xs[1], ys[1])


def boxes_overlap(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


# ---------- 甲、純函式幾何（不需 PyMuPDF 與字型） ----------

def test_fill_rect_invariants():
    from dataclasses import FrozenInstanceError

    from cjkfolio.primitives import FillRect

    r = FillRect(x0=1.0, y0=2.0, x1=3.0, y1=4.0, cmyk=(0.0, 0.0, 0.0, 1.0))
    assert (r.x0, r.y0, r.x1, r.y1) == (1.0, 2.0, 3.0, 4.0)
    assert len(r.cmyk) == 4
    with pytest.raises(FrozenInstanceError):
        r.x0 = 9.0
    assert not hasattr(r, "line_width_pt"), "填色語意不帶線寬"


def cross_shapes():
    from cjkfolio.primitives import registration_cross_marks

    return registration_cross_marks(
        mm(W_MM), mm(H_MM), bleed_pt=mm(BLEED_MM), band_pt=mm(BAND_MM),
        arm_pt=mm(ARM_MM), box_pt=mm(BOX_MM), cmyk=(1.0, 1.0, 1.0, 1.0),
        line_width_pt=0.25)


def test_registration_cross_count_and_style():
    from cjkfolio.primitives import StrokeLine, StrokeRect

    lines = [s for s in cross_shapes() if isinstance(s, StrokeLine)]
    rects = [s for s in cross_shapes() if isinstance(s, StrokeRect)]
    assert len(lines) == 8 and len(rects) == 4
    for ln in lines:
        assert ln.x0 == ln.x1 or ln.y0 == ln.y1, "臂須純水平或純垂直"
        assert ln.line_width_pt == 0.25 and ln.dash_on_pt == 0.0
    for rc in rects:
        assert (rc.x1 - rc.x0) == pytest.approx(mm(2 * BOX_MM), abs=1e-9)
        assert (rc.y1 - rc.y0) == pytest.approx(mm(2 * BOX_MM), abs=1e-9)


def test_registration_cross_centers():
    from cjkfolio.primitives import StrokeRect

    d = BLEED_MM + BAND_MM / 2  # 7mm
    want = {(round(mm(W_MM / 2), 3), round(mm(-d), 3)),
            (round(mm(W_MM / 2), 3), round(mm(H_MM + d), 3)),
            (round(mm(-d), 3), round(mm(H_MM / 2), 3)),
            (round(mm(W_MM + d), 3), round(mm(H_MM / 2), 3))}
    got = {(round((rc.x0 + rc.x1) / 2, 3), round((rc.y0 + rc.y1) / 2, 3))
           for rc in cross_shapes() if isinstance(rc, StrokeRect)}
    assert got == want


def outward_span_mm(shape):
    """原件離開 trim 那個軸上的距離區間（mm，皆為正值：距最近的 trim 邊多遠）。"""
    x0, y0, x1, y1 = envelope(shape)
    if x1 <= 0:
        return (-x1 / PT_PER_MM, -x0 / PT_PER_MM)
    if x0 >= mm(W_MM):
        return ((x0 - mm(W_MM)) / PT_PER_MM, (x1 - mm(W_MM)) / PT_PER_MM)
    if y1 <= 0:
        return (-y1 / PT_PER_MM, -y0 / PT_PER_MM)
    return ((y0 - mm(H_MM)) / PT_PER_MM, (y1 - mm(H_MM)) / PT_PER_MM)


def test_registration_cross_arm_clearance():
    """十字全部落在距 trim 邊 4mm 至 10mm 之間，即距 BleedBox 與 MediaBox 各留 1mm。"""
    for s in cross_shapes():
        lo, hi = outward_span_mm(s)
        assert lo >= BLEED_MM + GAP_MM - 1e-9, f"距 BleedBox 邊不足 1mm：{s}"
        assert hi <= BLEED_MM + BAND_MM - GAP_MM + 1e-9, f"距 MediaBox 邊不足 1mm：{s}"
    # 且外向臂確實用滿臂長：最遠端恰為 7mm ＋ 3mm
    assert max(outward_span_mm(s)[1] for s in cross_shapes()) == \
        pytest.approx(BLEED_MM + BAND_MM / 2 + ARM_MM, abs=1e-9)


def bar_patches():
    from cjkfolio.primitives import color_bar_patches

    return color_bar_patches(
        mm(W_MM), mm(H_MM), bleed_pt=mm(BLEED_MM), band_pt=mm(BAND_MM),
        patch_pt=mm(PATCH_MM), gap_pt=mm(GAP_MM), arm_pt=mm(ARM_MM),
        swatches=tuple(tuple(float(v) for v in s) for s in BAR_SWATCHES))


def ramp_patches():
    from cjkfolio.primitives import gray_ramp_patches

    return gray_ramp_patches(
        mm(W_MM), mm(H_MM), bleed_pt=mm(BLEED_MM), band_pt=mm(BAND_MM),
        patch_pt=mm(PATCH_MM), gap_pt=mm(GAP_MM), arm_pt=mm(ARM_MM),
        steps=RAMP_STEPS)


def test_color_bar_geometry():
    patches = bar_patches()
    assert len(patches) == 8
    y_top, y_bot = mm(H_MM + 4.0), mm(H_MM + 10.0)
    want = {(round(mm(patch_x_mm(i)[0]), 3), round(y_top, 3),
             round(mm(patch_x_mm(i)[1]), 3), round(y_bot, 3)) for i in range(8)}
    got = {(round(p.x0, 3), round(p.y0, 3), round(p.x1, 3), round(p.y1, 3))
           for p in patches}
    assert got == want
    ordered = sorted(patches, key=lambda p: p.x0)
    for a, b in zip(ordered, ordered[1:]):
        assert b.x0 - a.x1 == pytest.approx(mm(GAP_MM), abs=1e-6)


def test_color_bar_swatches():
    from cjkfolio.ink import tac_percent

    ordered = sorted(bar_patches(), key=lambda p: p.x0)
    assert [tuple(p.cmyk) for p in ordered] == \
        [tuple(float(v) for v in s) for s in BAR_SWATCHES]
    assert max(tac_percent(p.cmyk) for p in ordered) == pytest.approx(300.0)


def test_gray_ramp_geometry():
    patches = ramp_patches()
    assert len(patches) == 9
    y_top, y_bot = mm(-10.0), mm(-4.0)
    want = {(round(mm(patch_x_mm(j)[0]), 3), round(y_top, 3),
             round(mm(patch_x_mm(j)[1]), 3), round(y_bot, 3)) for j in range(9)}
    got = {(round(p.x0, 3), round(p.y0, 3), round(p.x1, 3), round(p.y1, 3))
           for p in patches}
    assert got == want


def test_gray_ramp_steps():
    from cjkfolio.ink import tac_percent

    ordered = sorted(ramp_patches(), key=lambda p: p.x0)
    assert [tuple(p.cmyk) for p in ordered] == \
        [(0.0, 0.0, 0.0, k) for k in RAMP_STEPS]
    ks = [p.cmyk[3] for p in ordered]
    assert ks == sorted(ks) and len(set(ks)) == len(ks), "K 值須嚴格遞增"
    assert max(tac_percent(p.cmyk) for p in ordered) == pytest.approx(100.0)


def all_press_shapes():
    return list(cross_shapes()) + list(bar_patches()) + list(ramp_patches())


def test_press_marks_lie_outside_trim():
    for s in all_press_shapes():
        x0, y0, x1, y1 = envelope(s)
        assert x1 <= 0 or x0 >= mm(W_MM) or y1 <= 0 or y0 >= mm(H_MM), \
            f"標記侵入活區：{s}"


def test_press_marks_inside_band():
    """每個原件完全落在標記環內：不侵入 BleedBox、不越出 MediaBox。"""
    inner_l, inner_t = -mm(BLEED_MM), -mm(BLEED_MM)
    inner_r, inner_b = mm(W_MM + BLEED_MM), mm(H_MM + BLEED_MM)
    outer_l, outer_t = -mm(BLEED_MM + BAND_MM), -mm(BLEED_MM + BAND_MM)
    outer_r, outer_b = mm(W_MM + BLEED_MM + BAND_MM), mm(H_MM + BLEED_MM + BAND_MM)
    for s in all_press_shapes():
        x0, y0, x1, y1 = envelope(s)
        assert outer_l - 1e-6 <= x0 and x1 <= outer_r + 1e-6
        assert outer_t - 1e-6 <= y0 and y1 <= outer_b + 1e-6
        in_band = (x1 <= inner_l + 1e-6 or x0 >= inner_r - 1e-6
                   or y1 <= inner_t + 1e-6 or y0 >= inner_b - 1e-6)
        assert in_band, f"原件侵入 BleedBox：{s}"


def crop_shapes():
    from cjkfolio.primitives import crop_mark_lines

    return crop_mark_lines(mm(W_MM), mm(H_MM), offset_pt=mm(BLEED_MM),
                           length_pt=mm(3.0), cmyk=(0.0, 0.0, 0.0, 1.0),
                           line_width_pt=0.25)


def inflated(shape):
    """線與框以線寬的一半外擴，使零面積的線段也能參與相交判定。"""
    x0, y0, x1, y1 = envelope(shape)
    half = getattr(shape, "line_width_pt", 0.0) / 2
    return (x0 - half, y0 - half, x1 + half, y1 + half)


def merge(boxes):
    xs0, ys0, xs1, ys1 = zip(*boxes)
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def test_press_marks_no_overlap_with_crop_marks():
    """21 個標記群組（4 個十字＋8 色塊＋9 階＋8 角標）兩兩零相交，不靠目視。

    一個十字內的兩條臂本來就相交，故十字以「整組包絡盒」參與判定；線段以線寬
    一半外擴，零面積線段才不會白白通過。
    """
    crosses = list(cross_shapes())
    assert len(crosses) == 12, "每個十字 3 個原件，共四組"
    groups = [merge([inflated(s) for s in crosses[i:i + 3]]) for i in range(0, 12, 3)]
    groups += [inflated(s) for s in bar_patches()]
    groups += [inflated(s) for s in ramp_patches()]
    groups += [inflated(s) for s in crop_shapes()]
    assert len(groups) == 4 + 8 + 9 + 8
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            assert not boxes_overlap(a, b), f"標記相碰：{a} 與 {b}"


def test_press_marks_guard_narrow_page():
    """開本窄到色塊列會撞進中央十字保留跨距時，快速失敗而非靜默截短。"""
    from cjkfolio.primitives import color_bar_patches

    with pytest.raises(ValueError, match="色塊列"):
        color_bar_patches(mm(60.0), mm(H_MM), bleed_pt=mm(BLEED_MM),
                          band_pt=mm(BAND_MM), patch_pt=mm(PATCH_MM),
                          gap_pt=mm(GAP_MM), arm_pt=mm(ARM_MM),
                          swatches=tuple(tuple(float(v) for v in s)
                                         for s in BAR_SWATCHES))


def test_press_marks_guard_invalid_params():
    from cjkfolio.primitives import (
        color_bar_patches, gray_ramp_patches, registration_cross_marks)

    swatches = tuple(tuple(float(v) for v in s) for s in BAR_SWATCHES)
    base = dict(bleed_pt=mm(BLEED_MM), band_pt=mm(BAND_MM),
                patch_pt=mm(PATCH_MM), gap_pt=mm(GAP_MM), arm_pt=mm(ARM_MM))
    with pytest.raises(ValueError, match="色塊邊長"):  # patch > band − 2×gap
        color_bar_patches(mm(W_MM), mm(H_MM), **{**base, "patch_pt": mm(7.0)},
                          swatches=swatches)
    with pytest.raises(ValueError, match="間隙"):  # gap ≤ 0
        color_bar_patches(mm(W_MM), mm(H_MM), **{**base, "gap_pt": 0.0},
                          swatches=swatches)
    with pytest.raises(ValueError, match="遞增"):  # steps 非嚴格遞增
        gray_ramp_patches(mm(W_MM), mm(H_MM), **base, steps=(0.5, 0.5, 1.0))
    with pytest.raises(ValueError, match="0 至 1"):  # 分量越界
        gray_ramp_patches(mm(W_MM), mm(H_MM), **base, steps=(0.5, 1.5))
    with pytest.raises(ValueError, match="0 至 1"):
        color_bar_patches(mm(W_MM), mm(H_MM), **base,
                          swatches=((1.0, 0.0, 0.0, 2.0),))
    with pytest.raises(ValueError, match="臂"):  # arm + gap > band/2
        registration_cross_marks(mm(W_MM), mm(H_MM), bleed_pt=mm(BLEED_MM),
                                 band_pt=mm(BAND_MM), arm_pt=mm(5.0),
                                 box_pt=mm(BOX_MM), cmyk=(1.0, 1.0, 1.0, 1.0),
                                 line_width_pt=0.25)


# ---------- 乙、盒框 ----------

@pytest.fixture(scope="module")
def template():
    from pathlib import Path

    from cjkfolio.styles import load_template

    return load_template(Path(__file__).resolve().parents[1] / "templates"
                         / "neizai-zhengli.json")


@pytest.mark.parametrize("crop,press,want_margin_mm", [
    (False, False, 0.0), (True, False, 3.0), (False, True, 8.0), (True, True, 8.0)])
def test_mark_margin_four_states(crop, press, want_margin_mm):
    from cjkfolio.pdf_writer import resolve_mark_margin_mm

    assert resolve_mark_margin_mm(crop, press) == pytest.approx(want_margin_mm)


def test_page_boxes_press_nested(template):
    from cjkfolio.pdf_writer import page_boxes_pt

    media, trim, bleed = page_boxes_pt(template, mark_margin_mm=BAND_MM)
    assert media[2] - media[0] == pytest.approx(mm(170.0), abs=0.01)
    assert media[3] - media[1] == pytest.approx(mm(232.0), abs=0.01)
    assert bleed[2] - bleed[0] == pytest.approx(mm(154.0), abs=0.01)
    assert trim[2] - trim[0] == pytest.approx(mm(W_MM), abs=0.01)
    # 第二條獨立算式：trim 左緣＝(MediaBox 寬 − trim 寬)/2
    assert trim[0] == pytest.approx((media[2] - mm(W_MM)) / 2, abs=0.01)
    for inner, outer in ((trim, bleed), (bleed, media)):
        assert outer[0] <= inner[0] and outer[1] <= inner[1]
        assert inner[2] <= outer[2] and inner[3] <= outer[3]


# ---------- 丙、零回歸 ----------

@pytest.fixture(scope="module")
def sample_doc():
    from cjkfolio.document import Document, Paragraph

    return Document(title="印前標記樣張", template="neizai-zhengli", master="A-內文版",
                    paragraphs=tuple(
                        Paragraph("整理一個房間先要決定的不是收納盒。" * 3,
                                  "內文-明體直排") for _ in range(4)))


needs_fonts = pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1]
         / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）")


def export(tmp_path, doc, template, name, **kw):
    from cjkfolio.pdf_writer import export_pdf

    out = tmp_path / f"{name}.pdf"
    export_pdf(doc, template, out, **kw)
    return out


def contents_of(path):
    fitz = pytest.importorskip("fitz")
    with fitz.open(path) as pdf:
        return pdf[0].read_contents().decode("latin-1")


@needs_fonts
def test_export_default_unchanged(tmp_path, sample_doc, template):
    """不給任何標記旗標：盒框與內容流維持既有形態，且零填色終結子。"""
    fitz = pytest.importorskip("fitz")

    out = export(tmp_path, sample_doc, template, "plain")
    with fitz.open(out) as pdf:
        media, bleed = pdf[0].mediabox, pdf[0].bleedbox
    assert media.width == pytest.approx(mm(154.0), abs=0.01)
    assert (bleed.x0, bleed.y0, bleed.x1, bleed.y1) == \
        pytest.approx((media.x0, media.y0, media.x1, media.y1), abs=0.01)
    body = contents_of(out)
    assert "\nf\n" not in body, "預設輸出不得出現填色終結子"
    assert "\nS\n" not in body, "預設輸出不得有描邊路徑"


@needs_fonts
def test_export_crop_only_unchanged(tmp_path, sample_doc, template):
    """只開裁切標記：仍為 160×222mm、恰 8 條線段、零填色。"""
    fitz = pytest.importorskip("fitz")

    out = export(tmp_path, sample_doc, template, "crop", crop_marks=True)
    with fitz.open(out) as pdf:
        media = pdf[0].mediabox
    assert media.width == pytest.approx(mm(160.0), abs=0.01)
    body = contents_of(out)
    assert body.count("\nS\n") == 8
    assert "\nf\n" not in body


@needs_fonts
def test_crop_mark_length_decoupled(tmp_path, sample_doc, template):
    """開印前標記時角標仍長 3mm（不隨 MediaBox 外擴變長吃掉色條空間）。"""
    out = export(tmp_path, sample_doc, template, "both",
                 crop_marks=True, press_marks=True)
    body = contents_of(out)
    segs = re.findall(r"([-\d.]+) ([-\d.]+) m\n([-\d.]+) ([-\d.]+) l", body)
    lengths = sorted({round(max(abs(float(x1) - float(x0)),
                                abs(float(y1) - float(y0))), 3)
                      for x0, y0, x1, y1 in segs})
    assert len(lengths) == 2, f"線段長度應只有兩種（角標與十字臂），得到 {lengths}"
    assert lengths[0] == pytest.approx(mm(3.0), abs=0.01)
    assert lengths[1] == pytest.approx(mm(6.0), abs=0.01)


@needs_fonts
def test_body_not_shifted_by_press_marks(tmp_path, sample_doc, template):
    """origin 由 3mm 位移到 11mm，內文在 trim 空間的落點須逐字不變。"""
    fitz = pytest.importorskip("fitz")

    def spans_in_trim(path, origin_mm):
        with fitz.open(path) as pdf:
            page = pdf[0]
            out = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        out.append((span["text"],
                                    round(span["origin"][0] - mm(origin_mm), 2),
                                    round(span["origin"][1] - mm(origin_mm), 2)))
        return out

    plain = export(tmp_path, sample_doc, template, "shift-off")
    pressed = export(tmp_path, sample_doc, template, "shift-on", press_marks=True)
    a = spans_in_trim(plain, BLEED_MM)
    b = spans_in_trim(pressed, BLEED_MM + BAND_MM)
    assert a and a == b, "內文相對 trim 的落點被標記位移了"


# ---------- 丁、Gate 4 獨立複驗（PyMuPDF，本檔自寫轉換式與期望值） ----------

def local_to_pdf(x_topdown, y_topdown, *, origin_mm, page_h_mm):
    """本檔自寫的 top-down → PDF y-up 轉換，不呼叫產出端任何函式。"""
    o = mm(origin_mm)
    return (o + x_topdown, mm(page_h_mm) + o - y_topdown)


@needs_fonts
def test_content_fill_blocks_parity(tmp_path, sample_doc, template):
    """17 個填色色塊的四座標與 CMYK，與本檔寫死的 mm 期望值完整相等。"""
    out = export(tmp_path, sample_doc, template, "fills", press_marks=True)
    body = contents_of(out)
    found = re.findall(
        r"q\n([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) k\n"
        r"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) re\nf\nQ", body)
    assert len(found) == 17, f"應有 8 色塊＋9 階＝17 個填色塊，得到 {len(found)}"

    origin = BLEED_MM + BAND_MM
    side = mm(PATCH_MM)
    want = []
    for i, sw in enumerate(BAR_SWATCHES):  # 色條在下帶
        x0m, _ = patch_x_mm(i)
        llx, lly = local_to_pdf(mm(x0m), mm(H_MM + 10.0),
                                origin_mm=origin, page_h_mm=H_MM)
        want.append((tuple(float(v) for v in sw), llx, lly, side, side))
    for j, k in enumerate(RAMP_STEPS):    # 灰梯尺在上帶
        x0m, _ = patch_x_mm(j)
        llx, lly = local_to_pdf(mm(x0m), mm(-4.0),
                                origin_mm=origin, page_h_mm=H_MM)
        want.append(((0.0, 0.0, 0.0, k), llx, lly, side, side))

    got = [(tuple(float(v) for v in g[:4]), *(float(v) for v in g[4:]))
           for g in found]
    key = (lambda t: (t[0], round(t[1], 1)))
    for g, w in zip(sorted(got, key=key), sorted(want, key=key)):
        assert g[0] == pytest.approx(w[0]), f"色值不符：{g} vs {w}"
        assert g[1:] == pytest.approx(w[1:], abs=0.01), f"座標不符：{g} vs {w}"


@needs_fonts
def test_press_marks_pixel_values(tmp_path, sample_doc, template):
    """第二種方法：光柵化取樣，證明 f 真的填出面而非只有 token。"""
    fitz = pytest.importorskip("fitz")

    out = export(tmp_path, sample_doc, template, "pixels", press_marks=True)
    with fitz.open(out) as pdf:
        page = pdf[0]
        pix = page.get_pixmap(dpi=72)
        greys = []
        for j in range(len(RAMP_STEPS)):
            x0m, x1m = patch_x_mm(j)
            cx, cy = local_to_pdf(mm((x0m + x1m) / 2), mm(-7.0),
                                  origin_mm=BLEED_MM + BAND_MM, page_h_mm=H_MM)
            px, py = int(cx - page.rect.x0), int(page.rect.y1 - cy)
            greys.append(sum(pix.pixel(px, py)[:3]) / 3)
    assert greys == sorted(greys, reverse=True), f"灰梯尺應由淺至深單調：{greys}"
    assert greys[0] > 200 and greys[-1] < 60, f"高光端與實地端灰值不合理：{greys}"


@needs_fonts
def test_boxes_via_pymupdf(tmp_path, sample_doc, template):
    fitz = pytest.importorskip("fitz")

    out = export(tmp_path, sample_doc, template, "boxes", press_marks=True)
    with fitz.open(out) as pdf:
        page = pdf[0]
        media, bleed, trim = page.mediabox, page.bleedbox, page.trimbox
    assert media.width == pytest.approx(mm(170.0), abs=0.05)
    assert media.height == pytest.approx(mm(232.0), abs=0.05)
    assert bleed.width == pytest.approx(mm(154.0), abs=0.05)
    assert trim.width == pytest.approx(mm(W_MM), abs=0.05)
    assert trim.height == pytest.approx(mm(H_MM), abs=0.05)


@needs_fonts
def test_color_discipline_not_regressed(tmp_path, sample_doc, template):
    """標記全走 DeviceCMYK：內容流見四原色字面，且無 rg／RG。"""
    out = export(tmp_path, sample_doc, template, "colors", press_marks=True)
    body = contents_of(out)
    for literal in ("1 0 0 0 k", "0 1 0 0 k", "0 0 1 0 k", "1 1 1 1 K"):
        assert literal in body, f"內容流缺 {literal}"
    assert " rg" not in body and " RG" not in body


@needs_fonts
def test_marks_below_text(tmp_path, sample_doc, template):
    out = export(tmp_path, sample_doc, template, "order", press_marks=True)
    body = contents_of(out)
    assert body.index(" re\nf") < body.index("BT")


# ---------- 戊、preflight 與 TAC ----------

@needs_fonts
def test_press_marks_pdfx_green(tmp_path, sample_doc, template):
    """填色色塊不使 X-1a 退步：仍 12 條規則全過。"""
    from cjkfolio.preflight import check_pdfx

    out = export(tmp_path, sample_doc, template, "pdfx", press_marks=True)
    report = check_pdfx(str(out))
    assert len(report.findings) == 12, "規則集不得因新功能擴張"
    assert report.ok, [f.rule for f in report.findings if not f.ok]


@needs_fonts
def test_registration_400_reported_not_exempted(tmp_path, sample_doc, template):
    """套準十字的 400% 據實回報。這條測試的存在本身就是沒有偷偷豁免的機械證據。"""
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.preflight import check_ink_coverage

    out = tmp_path / "tac400.pdf"
    result = export_pdf(sample_doc, template, out, press_marks=True)
    report = check_ink_coverage(str(out))
    assert any(f.tac == pytest.approx(400.0) for f in report.findings)
    assert report.ok is False, "超標須照報，不得因位於 trim 外而豁免"
    assert result.tac_warnings, "產出側同樣須發警告"


@needs_fonts
def test_single_k_option_tac_green(tmp_path, sample_doc, template):
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.preflight import check_ink_coverage

    out = tmp_path / "singlek.pdf"
    result = export_pdf(sample_doc, template, out, press_marks=True,
                        registration_single_k=True)
    report = check_ink_coverage(str(out))
    assert report.ok, [f for f in report.findings if not f.ok]
    assert max(f.tac for f in report.findings) == pytest.approx(300.0)
    assert not result.tac_warnings


@needs_fonts
def test_ink_use_kind_labels(tmp_path, sample_doc, template):
    """標記色標明來源；內文 K92 仍為著色（分帳只是判讀依據，不改門檻）。"""
    from cjkfolio.pdf_writer import export_pdf

    out = tmp_path / "kinds.pdf"
    result = export_pdf(sample_doc, template, out, press_marks=True)
    kinds = {u.label: u.kind for u in result.ink_uses}
    assert kinds["1 1 1 1"] == "印前標記"
    assert kinds["0 0 0 0.92"] == "著色"


def test_single_k_requires_press_marks(tmp_path, sample_doc, template):
    from cjkfolio.pdf_writer import export_pdf

    with pytest.raises(ValueError, match="需搭 press_marks"):
        export_pdf(sample_doc, template, tmp_path / "x.pdf",
                   registration_single_k=True)


# ---------- 己、CLI ----------

def write_doc_json(tmp_path, doc):
    import json

    from cjkfolio.document import document_to_dict

    src = tmp_path / "doc.json"
    src.write_text(json.dumps(document_to_dict(doc), ensure_ascii=False),
                   encoding="utf-8")
    return src


@needs_fonts
def test_cli_press_marks_flag(tmp_path, sample_doc, capsys):
    from cjkfolio.cli import main

    fitz = pytest.importorskip("fitz")
    src = write_doc_json(tmp_path, sample_doc)
    out = tmp_path / "cli.pdf"
    rc = main(["export-pdf", str(src), "-o", str(out), "--press-marks"])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "印前標記" in printed and "非任何標準控制條" in printed
    with fitz.open(out) as pdf:
        assert pdf[0].mediabox.width == pytest.approx(mm(170.0), abs=0.05)


def test_cli_single_k_requires_press_marks(tmp_path, sample_doc, capsys):
    from cjkfolio.cli import main

    src = write_doc_json(tmp_path, sample_doc)
    rc = main(["export-pdf", str(src), "-o", str(tmp_path / "x.pdf"),
               "--registration-single-k"])
    assert rc == 2
    assert "需搭 --press-marks" in capsys.readouterr().err
