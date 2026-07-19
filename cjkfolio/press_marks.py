"""印前標記的參數與繪製（Sprint 109，opt-in；GAPS #42 (b)、#56 乙(9)）。

四邊中點套準十字、下帶色條、上帶灰梯尺，全部落在 BleedBox 與 MediaBox 之間的
標記環內。幾何純函式在 primitives（同 crop_mark_lines 慣例），本模組只做兩件事：
持有參數常數，以及把幾何交給寫出層繪製（座標翻轉仍只發生在 pdf_writer）。

**定位（Owner 於 Gate 0 放行）：機制已驗、參數待印廠確認。** 本專案從未接觸過
印刷廠（GAPS #11／#18／#41），下列尺寸與色序皆為 D 級推導，非任何規格書；色條
**不宣稱相容於任何標準控制條**（Ugra／Fogra／Brunner）。日後取得印廠規格時只需
改這些常數，幾何與寫出結構不動。另有一項本專案自己就能看見的限制：§9 定案以
單頁完稿交付、拼版由印廠 RIP 處理，而印廠通常在大版層自加套準十字與色條，故
頁級標記的實際收益待真實印廠回報確認（GAPS #42）。

本模組獨立成檔而非併入 pdf_writer，是因後者已達單檔 800 行上限（同 Sprint 93
pdf_objects、Sprint 101 smoke_preflight 的處置）。
"""
from .primitives import (
    PT_PER_MM,
    color_bar_patches,
    crop_mark_lines,
    gray_ramp_patches,
    registration_cross_marks,
)

MARK_LENGTH_MM = 3.0         # 裁切角標長度（Sprint 83）
MARK_CMYK = (0.0, 0.0, 0.0, 1.0)
MARK_WIDTH_PT = 0.25

PRESS_MARK_MARGIN_MM = 8.0   # 印前標記帶寬（MediaBox 於 BleedBox 外擴此值）
PRESS_PATCH_MM = 6.0         # 色塊邊長
PRESS_GAP_MM = 1.0           # 帶內留白與塊間隙
PRESS_CROSS_ARM_MM = 3.0     # 十字臂半長（全長 6mm）
PRESS_CROSS_BOX_MM = 1.5     # 同心方框半邊（全邊 3mm）
PRESS_MARK_WIDTH_PT = 0.25   # 與 MARK_WIDTH_PT 同值，另立名以免兩者耦合

# 套準十字預設四版套準色（Owner 定案，推翻 GAPS #42 (c) 的單 K 預設）：套準十字
# 的功能是同時曬在四塊印版上供機長比對套印，單 K 只在黑版留痕、其餘三版無參照，
# 形態存在但功能不成立。標記在 TrimBox 外，裁切後不入成品。TAC 400% 由 §9 的油墨
# 檢查據實回報（不豁免、不改門檻），需要墨量全綠者走 registration_single_k。
REG_CMYK = (1.0, 1.0, 1.0, 1.0)
REG_SINGLE_K_CMYK = (0.0, 0.0, 0.0, 1.0)

# 色條 8 塊：四原色實地＋三塊二次色＋一塊三色疊（疊印診斷用，最高 TAC 300% 仍在
# §9 的 320% 之下）。四色實地不入色條：套準十字已提供 400% 的單一來源，重複無益。
COLOR_BAR_SWATCHES = (
    (1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 0.0, 0.0), (1.0, 0.0, 1.0, 0.0),
    (0.0, 1.0, 1.0, 0.0), (1.0, 1.0, 1.0, 0.0),
)
# 灰梯尺 9 階單 K：含 5% 與 10% 高光階（高光端的網點還原與平網掉點最需目視檢查，
# 10% 起跳會放掉最有診斷價值的一段）。0% 階不做（白紙上不可見）。
GRAY_RAMP_STEPS = (0.05, 0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 0.90, 1.00)


BLEED_MM = 3.0  # 四邊出血（§9）


def page_boxes_pt(template, bleed_mm: float = BLEED_MM,
                  mark_margin_mm: float = 0.0):
    """(MediaBox, TrimBox, BleedBox)，皆 pt。

    無標記（mark_margin_mm=0）時 BleedBox＝MediaBox（§9）；開啟標記時 MediaBox
    較 BleedBox 於四邊各外擴 mark_margin_mm（標記居於兩者之間），TrimBox 恆置中。
    """
    w = template.page_width_mm * PT_PER_MM
    h = template.page_height_mm * PT_PER_MM
    b = bleed_mm * PT_PER_MM
    mk = mark_margin_mm * PT_PER_MM
    o = b + mk  # MediaBox 左下 → TrimBox 左下偏移
    media = (0.0, 0.0, w + 2 * o, h + 2 * o)
    trim = (o, o, o + w, o + h)
    bleed = (mk, mk, mk + w + 2 * b, mk + h + 2 * b)
    return media, trim, bleed


def resolve_mark_margin_mm(crop_marks: bool, press_marks: bool) -> float:
    """兩個標記開關 → MediaBox 外擴量（mm）。兩者皆開時取較大者（帶寬相容）。

    語意布林只在此降解一次，之後全鏈只傳 mark_margin_pt（既有慣例）。
    """
    return max(MARK_LENGTH_MM if crop_marks else 0.0,
               PRESS_MARK_MARGIN_MM if press_marks else 0.0)


def press_mark_shapes(trim_w_pt: float, trim_h_pt: float, *, bleed_pt: float,
                      mm_to_pt, reg_cmyk=REG_CMYK):
    """一頁份的印前標記原件（top-down pt，trim 左上為原點）。

    回傳 (strokes, fills)：strokes＝套準十字的臂與方框（StrokeLine／StrokeRect），
    fills＝色條與灰梯尺色塊（FillRect）。mm_to_pt 由呼叫端傳入（底層各層自持
    換算免循環依賴，同 primitives.PT_PER_MM 慣例）。
    """
    band = mm_to_pt(PRESS_MARK_MARGIN_MM)
    patch = mm_to_pt(PRESS_PATCH_MM)
    gap = mm_to_pt(PRESS_GAP_MM)
    arm = mm_to_pt(PRESS_CROSS_ARM_MM)
    box = mm_to_pt(PRESS_CROSS_BOX_MM)
    strokes = registration_cross_marks(
        trim_w_pt, trim_h_pt, bleed_pt=bleed_pt, band_pt=band, arm_pt=arm,
        box_pt=box, cmyk=tuple(reg_cmyk), line_width_pt=PRESS_MARK_WIDTH_PT)
    fills = color_bar_patches(
        trim_w_pt, trim_h_pt, bleed_pt=bleed_pt, band_pt=band, patch_pt=patch,
        gap_pt=gap, arm_pt=arm, swatches=COLOR_BAR_SWATCHES)
    fills += gray_ramp_patches(
        trim_w_pt, trim_h_pt, bleed_pt=bleed_pt, band_pt=band, patch_pt=patch,
        gap_pt=gap, arm_pt=arm, steps=GRAY_RAMP_STEPS)
    return strokes, fills


def _emit_stroke(content, shape, *, origin_pt: float, page_h_pt: float) -> None:
    """標記原件（線或框）→ 內容流，套用唯一那條 top-down → y-up 翻轉公式。"""
    ox, top = origin_pt, page_h_pt + origin_pt
    if hasattr(shape, "dash_on_pt"):  # StrokeLine
        content.stroke_line(
            shape.cmyk, shape.line_width_pt,
            ox + shape.x0, top - shape.y0, ox + shape.x1, top - shape.y1,
            is_mark=True)
    else:  # StrokeRect：PDF re 取左下角＋寬高
        content.stroke_rect(
            shape.cmyk, shape.line_width_pt,
            ox + shape.x0, top - shape.y1,
            shape.x1 - shape.x0, shape.y1 - shape.y0, is_mark=True)


def emit_marks(content, *, trim_w_pt: float, trim_h_pt: float, bleed_pt: float,
               origin_pt: float, page_h_pt: float, mm_to_pt,
               crop: bool = False, press: bool = False, reg_cmyk=REG_CMYK) -> None:
    """把選用的標記畫進內容流（底層裝飾，恆在文字之下）。

    裁切角標（Sprint 83）內端距 trim＝出血、向外延伸 MARK_LENGTH_MM。**角標長度與
    MediaBox 外擴量自 Sprint 109 起解耦**：兩者原本同為 mark_margin_pt，但印前標記
    把外擴量加大到 8mm 後角標會跟著變長並吃掉色條空間。單開裁切標記時兩者仍恆等
    （3mm），故既有輸出位元不變。

    全部走 is_mark=True 記入標記帳本（來源標示用，不改任何墨量門檻）。
    """
    if crop:
        for line in crop_mark_lines(trim_w_pt, trim_h_pt, offset_pt=bleed_pt,
                                    length_pt=mm_to_pt(MARK_LENGTH_MM),
                                    cmyk=MARK_CMYK, line_width_pt=MARK_WIDTH_PT):
            _emit_stroke(content, line, origin_pt=origin_pt, page_h_pt=page_h_pt)
    if press:
        strokes, fills = press_mark_shapes(
            trim_w_pt, trim_h_pt, bleed_pt=bleed_pt, mm_to_pt=mm_to_pt,
            reg_cmyk=reg_cmyk)
        for shape in strokes:
            _emit_stroke(content, shape, origin_pt=origin_pt, page_h_pt=page_h_pt)
        ox, top = origin_pt, page_h_pt + origin_pt
        for rect in fills:
            content.fill_rect(
                rect.cmyk, ox + rect.x0, top - rect.y1,
                rect.x1 - rect.x0, rect.y1 - rect.y0, is_mark=True)
