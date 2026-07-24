"""向量原件層（pt 空間）：與 placement.py 同哲學，兩後端（render PIL／pdf path ops）同源。

座標約定同 placement：top-down pt（x 向右、y 向下）；render ×scale→px，
pdf 寫出時轉 y-up 並加出血偏移。描邊色一律 DeviceCMYK（維持 PLAN §9 全 CMYK；
preflight color-cmyk-only 檢查不退步，描邊走 `K` 算符不觸 `rg`／`RG`）。

原件：CIP 細框（F 版權頁，Sprint 14）、目錄水平虛線（D 主版，Sprint 15），
幾何由主版 grid／樣式參數確定性推導；此層為後續部扉雙線菱形框（B 主版）
等向量裝飾的地基（PLAN §1）。
"""
from dataclasses import dataclass

PT_PER_MM = 72.0 / 25.4  # 物理常數（同 render.PT_PER_MM，底層層各自持有免循環依賴）


def is_right_page(book_number: int) -> bool:
    """右頁（書口在右）＝偶數書頁。

    真書《內在整理》三向互證（Sprint 22，A 級）：頁碼側（偶頁頁碼書口右）、
    書眉側（書名書眉皆偶頁）、版心側（偶頁右邊距 21mm＝outer 精確）。
    右翻直排書 spread＝（偶右、奇左），讀序右→左＝頁碼小→大。
    """
    return book_number % 2 == 0


def book_number_for(page_number: int, first_page: int = 1,
                    cover_pages: int = 0) -> int:
    """版面頁號 → 書頁號（鏡像、頁腳奇偶與目錄頁碼一律依此，Sprint 12 SSOT）。

    cover_pages＝封面佔的版面頁數（Sprint 132）：頁碼自封面翻開後起算，故內文
    首頁的書頁號恆為 first_page，封面依序往前推（單頁封面＝first_page−1，預設
    即 0）。封面書頁號 0 為偶數＝右頁（is_right_page），與右翻書封面在右一致。
    cover_pages=0 時退化為既有公式（版面頁號＋first_page−1），無封面文件零變更。
    """
    return page_number - cover_pages + first_page - 1


def line_axis_x_pt(template, master, slot: int, page_number: int,
                   line_slots: int = 1) -> float:
    """第 slot 行槽的行軸（欄中心）x 座標，pt。傳入書頁號，偶數＝右頁書口在右；
    mirror=false 恆以 outer 槽為起排側（B 部扉先例）。

    兩後端與繞排排除區換算（wrap.py，Sprint 89）的行軸單一事實來源；render 與
    pdf_writer 自此 re-export（既有呼叫端不變）。
    """
    page_w = template.page_width_mm * PT_PER_MM
    outer_side = is_right_page(page_number) or not master.mirror
    margin_mm = master.margins.outer_mm if outer_side else master.margins.inner_mm
    axis0 = page_w - margin_mm * PT_PER_MM - master.grid.base_size_pt / 2
    return axis0 - (slot + (line_slots - 1) / 2) * master.grid.line_pitch_pt


@dataclass(frozen=True)
class StrokeRect:
    """描邊矩形（top-down pt）：x0<x1、y0<y1（y0＝上緣）。cmyk 為描邊色 (c,m,y,k)。"""
    x0: float
    y0: float
    x1: float
    y1: float
    cmyk: tuple
    line_width_pt: float


@dataclass(frozen=True)
class FillRect:
    """填色矩形（top-down pt）：x0<x1、y0<y1（y0＝上緣）。cmyk 為填色 (c,m,y,k)。

    印前標記的色條與灰梯尺載體（Sprint 109）。刻意不帶 line_width_pt：填色語意
    無線寬，需要框線者用 StrokeRect。
    """
    x0: float
    y0: float
    x1: float
    y1: float
    cmyk: tuple


@dataclass(frozen=True)
class StrokeLine:
    """描邊線段（top-down pt）。dash_on_pt>0 時為虛線（畫 on 空 off），=0 為實線。"""
    x0: float
    y0: float
    x1: float
    y1: float
    cmyk: tuple
    line_width_pt: float
    dash_on_pt: float = 0.0
    dash_off_pt: float = 0.0


def toc_rule_line(page_width_pt: float, rule) -> StrokeLine:
    """目錄天頭水平虛線（top-down pt）：y 取實測 rule.y_from_top_pt，貫穿頁寬並向
    兩側延伸 rule.bleed_extend_pt（貼邊元素出血全出，PLAN §9）。

    參考書 p003 一手量測（A 級）：y=122.46pt、1.0pt、dash [3 2]、灰 K57；量測
    「參數」入模版（Sprint 7 頁腳先例），「內容」不入 repo。篇名斷開見
    toc_rule_segments（Sprint 21）。
    """
    return StrokeLine(
        x0=-rule.bleed_extend_pt,
        y0=rule.y_from_top_pt,
        x1=page_width_pt + rule.bleed_extend_pt,
        y1=rule.y_from_top_pt,
        cmyk=rule.cmyk,
        line_width_pt=rule.line_width_pt,
        dash_on_pt=rule.dash_on_pt,
        dash_off_pt=rule.dash_off_pt,
    )


def toc_rule_segments(page_width_pt: float, rule, gaps=()) -> tuple:
    """目錄天頭虛線的分段形（篇名嵌線斷開，Sprint 21）：在 gaps 各 (x_lo, x_hi)
    區間斷開（穿線行的行槽範圍±斷開邊距，由 layout／後端幾何推導），其餘
    與全寬線同幾何。gaps 空＝單段（同 toc_rule_line）。

    參考書 p002／p003 一手量測（A 級）：虛線在「第N篇」行處斷開；越出線端的
    gap 裁剪、零長段不產出。
    """
    full = toc_rule_line(page_width_pt, rule)
    segs: list = []
    cursor = full.x0
    for lo, hi in sorted(gaps):
        if hi <= cursor or lo >= full.x1:  # gap 在線外
            cursor = max(cursor, hi)
            continue
        if lo > cursor:  # 零長段不產出
            segs.append((cursor, min(lo, full.x1)))
        cursor = max(cursor, hi)
    if cursor < full.x1:
        segs.append((cursor, full.x1))
    return tuple(
        StrokeLine(x0=x0, y0=full.y0, x1=x1, y1=full.y1, cmyk=full.cmyk,
                   line_width_pt=full.line_width_pt,
                   dash_on_pt=full.dash_on_pt, dash_off_pt=full.dash_off_pt)
        for x0, x1 in segs
    )


def crop_mark_lines(trim_w_pt: float, trim_h_pt: float, *, offset_pt: float,
                    length_pt: float, cmyk: tuple, line_width_pt: float) -> tuple:
    """裁切標記（trim marks）：8 條角標（top-down pt，trim 左上＝原點）。

    每個 trim 角產出 2 條角標，各延伸該角相交的一條裁切邊（上／下邊向左右、左／右邊
    向上下）：內端距 trim 邊 offset_pt（取＝出血，落在 BleedBox 邊、不侵入活區），向外
    延伸 length_pt。標記落在 trim 外（座標可為負或超出 trim_w/h），由 pdf_writer 加
    origin 偏移後落入外擴 MediaBox（BleedBox 與 MediaBox 之間）。標記色一律單 K
    （registration，PLAN §9 全 CMYK、避高 TAC；trim 外於裁切後不入成品）。
    """
    w, h, o, ell = trim_w_pt, trim_h_pt, offset_pt, length_pt

    def ln(x0: float, y0: float, x1: float, y1: float) -> StrokeLine:
        return StrokeLine(x0=x0, y0=y0, x1=x1, y1=y1, cmyk=cmyk,
                          line_width_pt=line_width_pt)

    return (
        ln(-(o + ell), 0.0, -o, 0.0),        # 左上 水平（延伸上邊向左）
        ln(0.0, -(o + ell), 0.0, -o),        # 左上 垂直（延伸左邊向上）
        ln(w + o, 0.0, w + o + ell, 0.0),    # 右上 水平
        ln(w, -(o + ell), w, -o),            # 右上 垂直
        ln(-(o + ell), h, -o, h),            # 左下 水平
        ln(0.0, h + o, 0.0, h + o + ell),    # 左下 垂直
        ln(w + o, h, w + o + ell, h),        # 右下 水平
        ln(w, h + o, w, h + o + ell),        # 右下 垂直
    )


def _check_band(band_pt: float, patch_pt: float, gap_pt: float) -> None:
    """標記帶內的共用守門：不合即快速失敗，不靜默夾住或縮排（Sprint 109）。"""
    if gap_pt <= 0:
        raise ValueError(f"標記帶內間隙須大於 0，得到 {gap_pt:.3f}pt")
    if patch_pt > band_pt - 2 * gap_pt + 1e-9:
        raise ValueError(
            f"色塊邊長 {patch_pt:.3f}pt 超過標記帶可容（帶寬 {band_pt:.3f} 減兩側間隙 "
            f"{2 * gap_pt:.3f}）；請縮小色塊或加寬標記帶"
        )


def _check_cmyk(values, ctx: str) -> tuple:
    values = tuple(float(v) for v in values)
    if len(values) != 4:
        raise ValueError(f"{ctx} 須為四分量 CMYK，得到 {len(values)} 個")
    for v in values:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"{ctx} 的分量須落在 0 至 1，得到 {v}")
    return values


def _band_patches(trim_w_pt: float, trim_h_pt: float, *, bleed_pt: float,
                  band_pt: float, patch_pt: float, gap_pt: float,
                  colors, top_band: bool, arm_pt: float) -> tuple:
    """標記帶內自左起排的等距色塊列（top-down pt，trim 左上為原點）。

    色條與灰梯尺唯一的差異是所在帶（上或下）與色序來源，故共用本函式。
    色塊列右緣須留在中央套準十字的保留跨距之外，否則快速失敗（不靜默省略色塊）。
    """
    _check_band(band_pt, patch_pt, gap_pt)
    colors = tuple(_check_cmyk(c, "色塊") for c in colors)
    if not colors:
        raise ValueError("色塊清單不得為空")
    pitch = patch_pt + gap_pt
    right_edge = gap_pt + (len(colors) - 1) * pitch + patch_pt
    reserved_left = trim_w_pt / 2 - arm_pt - gap_pt
    if right_edge + gap_pt > reserved_left + 1e-9:
        raise ValueError(
            f"色塊列右緣 {right_edge:.3f}pt 會撞進中央套準十字的保留跨距"
            f"（左緣 {reserved_left:.3f}pt）；請減少色塊數、縮小色塊或加大開本"
        )
    inset = (band_pt - patch_pt) / 2  # 色塊在帶內垂直置中
    if top_band:
        y0 = -(bleed_pt + inset + patch_pt)
    else:
        y0 = trim_h_pt + bleed_pt + inset
    y1 = y0 + patch_pt
    out = []
    for i, cmyk in enumerate(colors):
        x0 = gap_pt + i * pitch
        out.append(FillRect(x0=x0, y0=y0, x1=x0 + patch_pt, y1=y1, cmyk=cmyk))
    return tuple(out)


def color_bar_patches(trim_w_pt: float, trim_h_pt: float, *, bleed_pt: float,
                      band_pt: float, patch_pt: float, gap_pt: float,
                      swatches, arm_pt: float) -> tuple:
    """色條（下標記帶，自左起排；Sprint 109）：每個 swatch 一塊實地色。

    本色條為自擬配置，**不宣稱相容於任何標準控制條**（Ugra／Fogra／Brunner）；
    塊數、色序、尺寸皆為 D 級推導（本專案無印廠一手需求，GAPS #42）。
    """
    return _band_patches(trim_w_pt, trim_h_pt, bleed_pt=bleed_pt, band_pt=band_pt,
                         patch_pt=patch_pt, gap_pt=gap_pt, colors=swatches,
                         top_band=False, arm_pt=arm_pt)


def gray_ramp_patches(trim_w_pt: float, trim_h_pt: float, *, bleed_pt: float,
                      band_pt: float, patch_pt: float, gap_pt: float,
                      steps, arm_pt: float) -> tuple:
    """灰梯尺（上標記帶，自左起排；Sprint 109）：每階一塊單 K 網點。

    steps 須嚴格遞增且各落於 [0,1]（不遞增視為資料錯誤，不自行排序）。單 K 取向
    承 §9「灰階照片走單 K」，階數與百分比為 D 級推導。
    """
    values = tuple(float(s) for s in steps)
    if not values:
        raise ValueError("灰梯尺階數清單不得為空")
    for v in values:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"灰梯尺階值須落在 0 至 1，得到 {v}")
    if any(b <= a for a, b in zip(values, values[1:])):
        raise ValueError(f"灰梯尺階值須嚴格遞增，得到 {values}")
    return _band_patches(trim_w_pt, trim_h_pt, bleed_pt=bleed_pt, band_pt=band_pt,
                         patch_pt=patch_pt, gap_pt=gap_pt,
                         colors=tuple((0.0, 0.0, 0.0, v) for v in values),
                         top_band=True, arm_pt=arm_pt)


def registration_cross_marks(trim_w_pt: float, trim_h_pt: float, *, bleed_pt: float,
                             band_pt: float, arm_pt: float, box_pt: float,
                             cmyk: tuple, line_width_pt: float) -> tuple:
    """套準十字（四邊中點各一組；Sprint 109）：十字臂＋同心方框。

    中心落在標記帶正中（距 trim 邊 bleed_pt + band_pt/2），臂半長 arm_pt、方框半邊
    box_pt。回傳 8 條 StrokeLine（每組水平與垂直各一）＋4 個 StrokeRect。

    **非傳統圓形套準環**：寫出層無曲線算符（`c`／`v`／`y`），本 v1 以同心方框代替
    圓環，不假裝是圓（GAPS #42）。色由呼叫端給定：套準十字的功能是同時曬在四塊
    印版上供比對套印，故預設為四版套準色（單 K 只在黑版留痕，其餘三版無參照）。
    """
    _check_cmyk(cmyk, "套準十字色")
    if arm_pt + 0.0 <= 0 or box_pt <= 0:
        raise ValueError("套準十字的臂長與方框邊長須大於 0")
    if arm_pt * 2 > band_pt:
        raise ValueError(
            f"套準十字臂全長 {2 * arm_pt:.3f}pt 超過標記帶寬 {band_pt:.3f}pt"
        )
    if box_pt >= arm_pt:
        raise ValueError(
            f"同心方框半邊 {box_pt:.3f}pt 須小於臂半長 {arm_pt:.3f}pt（方框須在臂內）"
        )
    d = bleed_pt + band_pt / 2
    centers = (
        (trim_w_pt / 2, -d),              # 上
        (trim_w_pt / 2, trim_h_pt + d),   # 下
        (-d, trim_h_pt / 2),              # 左
        (trim_w_pt + d, trim_h_pt / 2),   # 右
    )
    out: list = []
    for cx, cy in centers:
        out.append(StrokeLine(x0=cx - arm_pt, y0=cy, x1=cx + arm_pt, y1=cy,
                              cmyk=cmyk, line_width_pt=line_width_pt))
        out.append(StrokeLine(x0=cx, y0=cy - arm_pt, x1=cx, y1=cy + arm_pt,
                              cmyk=cmyk, line_width_pt=line_width_pt))
        out.append(StrokeRect(x0=cx - box_pt, y0=cy - box_pt,
                              x1=cx + box_pt, y1=cy + box_pt,
                              cmyk=cmyk, line_width_pt=line_width_pt))
    return tuple(out)


def cip_frame_rect(master, left_x_pt: float, n_lines: int, frame) -> StrokeRect:
    """CIP 細框（top-down pt）：圍住橫排 CIP 內容網格盒，外留 pad。

    網格盒＝[left, top]～[left＋滿行寬, top＋n_lines×行距]，其中滿行寬＝
    grid.chars_per_line×char_advance_pt；框在網格盒外擴 pad（水平 pad_pt、垂直
    pad_v_pt，None 時沿用 pad_pt；p178 實測水平 5.05／垂直 4.94 不對稱）。
    left_x_pt 由呼叫端經 render.horizontal_left_x_pt 傳入（鏡像已判，兩後端同源）。
    """
    grid = master.grid
    top = master.margins.top_mm * PT_PER_MM
    content_w = grid.chars_per_line * grid.char_advance_pt
    pad_h = frame.pad_pt
    pad_v = frame.pad_v_pt if frame.pad_v_pt is not None else frame.pad_pt
    return StrokeRect(
        x0=left_x_pt - pad_h,
        y0=top - pad_v,
        x1=left_x_pt + content_w + pad_h,
        y1=top + n_lines * grid.line_pitch_pt + pad_v,
        cmyk=frame.cmyk,
        line_width_pt=frame.line_width_pt,
    )


def figure_slot_rect(page_w_pt: float, master, is_right: bool, figure) -> StrokeRect:
    """G-圖文版圖框保留區（top-down pt，x0<x1、y0<y1）：橫向承主版版心（鏡像感知），
    縱向取 figure 量測 top/bottom。回傳 StrokeRect（幾何＋佔位框描邊參數）。

    版心橫向鏡像與 render.horizontal_left_x_pt 同規則（書口＝outer）：右頁（書口右）
    左緣＝inner、右緣＝頁寬−outer；左頁反之；mirror=false 恆以 outer 為左緣。
    參考書典型雙照片全頁一手量測（Sprint 27，tools/measure_figure_page.py）：R 頁
    版心 x0=72.51／x1=360.0、L 頁 59.53／347.02，真書照片略溢版心 1〜4pt（美術自由
    佈局，入 GAPS）。Phase 1 以 figure_slot_edges 描淡虛線佔位框；Phase 2 圖片置入
    消費此保留區、由實際照片取代。
    """
    mirror_right = master.mirror and is_right
    left_mm = master.margins.inner_mm if mirror_right else master.margins.outer_mm
    right_mm = master.margins.outer_mm if mirror_right else master.margins.inner_mm
    return StrokeRect(
        x0=left_mm * PT_PER_MM,
        y0=figure.top_from_top_pt,
        x1=page_w_pt - right_mm * PT_PER_MM,
        y1=figure.bottom_from_top_pt,
        cmyk=figure.cmyk,
        line_width_pt=figure.line_width_pt,
    )


def figure_slot_edges(rect: StrokeRect, figure) -> tuple:
    """圖框保留區四邊虛線（佔位語意）：把 StrokeRect 拆成上下左右四條 dashed
    StrokeLine，兩後端各以既有 dashed-line 路徑繪出（render 灰值分段／pdf `d` 算符），
    不新增低階描邊碼。dash 節奏取 figure.dash_on_pt／dash_off_pt。
    """
    edges = (
        (rect.x0, rect.y0, rect.x1, rect.y0),  # 上緣
        (rect.x0, rect.y1, rect.x1, rect.y1),  # 下緣
        (rect.x0, rect.y0, rect.x0, rect.y1),  # 左緣
        (rect.x1, rect.y0, rect.x1, rect.y1),  # 右緣
    )
    return tuple(
        StrokeLine(x0=x0, y0=y0, x1=x1, y1=y1, cmyk=rect.cmyk,
                   line_width_pt=rect.line_width_pt,
                   dash_on_pt=figure.dash_on_pt, dash_off_pt=figure.dash_off_pt)
        for x0, y0, x1, y1 in edges
    )


@dataclass(frozen=True)
class ImageBox:
    """圖片實繪矩形（top-down pt，x0<x1、y0<y1）：contain-fit 後的置入座標。

    非描邊原件（無 cmyk／line_width）；兩後端（render PIL paste／pdf `cm`＋`Do`）
    以此同一矩形放置影像，構成兩後端幾何同源。
    """
    x0: float
    y0: float
    x1: float
    y1: float


def fit_image_rect(slot_x0: float, slot_y0: float, slot_x1: float, slot_y1: float,
                   img_w_px: int, img_h_px: int) -> ImageBox:
    """把 img_w_px×img_h_px 的影像等比縮放（contain）置入保留區並置中（top-down pt）。

    contain＝縮放係數取兩軸較小者（min(sw/w, sh/h)），影像完整落入保留區內、不裁切、
    不變形，四周留白置中（InDesign「按比例調整內容」預設）。真書照片略溢版心屬美術
    自由佈局（§8，GAPS #13），v1 不做溢出。像素尺寸非正快速失敗（系統邊界）。
    """
    if img_w_px <= 0 or img_h_px <= 0:
        raise ValueError(f"影像像素尺寸須為正，得到 {img_w_px}×{img_h_px}")
    sw = slot_x1 - slot_x0
    sh = slot_y1 - slot_y0
    scale = min(sw / img_w_px, sh / img_h_px)
    draw_w = img_w_px * scale
    draw_h = img_h_px * scale
    x0 = slot_x0 + (sw - draw_w) / 2
    y0 = slot_y0 + (sh - draw_h) / 2
    return ImageBox(x0=x0, y0=y0, x1=x0 + draw_w, y1=y0 + draw_h)
