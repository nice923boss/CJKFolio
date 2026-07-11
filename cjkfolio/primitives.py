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
