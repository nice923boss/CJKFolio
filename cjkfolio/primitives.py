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
    「參數」入模版（Sprint 7 頁腳先例），「內容」不入 repo。篇名斷開與條目縮退
    屬目錄頁型工程（GAPS #13 剩項），v1 全寬貫穿。
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
