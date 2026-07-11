"""向量原件層（pt 空間）：與 placement.py 同哲學，兩後端（render PIL／pdf path ops）同源。

座標約定同 placement：top-down pt（x 向右、y 向下）；render ×scale→px，
pdf 寫出時轉 y-up 並加出血偏移。描邊色一律 DeviceCMYK（維持 PLAN §9 全 CMYK；
preflight color-cmyk-only 檢查不退步，描邊走 `K` 算符不觸 `rg`／`RG`）。

v1 只有 CIP 細框（版權頁）一種原件，幾何由主版 grid 與內容行數確定性推導；
此層為後續部扉雙線菱形框（B 主版）與目錄水平虛線（D 主版）的地基（PLAN §1）。
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


def cip_frame_rect(master, left_x_pt: float, n_lines: int, frame) -> StrokeRect:
    """CIP 細框（top-down pt）：圍住橫排 CIP 內容網格盒，四周留 frame.pad_pt。

    網格盒＝[left, top]～[left＋滿行寬, top＋n_lines×行距]，其中滿行寬＝
    grid.chars_per_line×char_advance_pt；框在網格盒外擴 pad（四周等距）。
    left_x_pt 由呼叫端經 render.horizontal_left_x_pt 傳入（鏡像已判，兩後端同源）。
    """
    grid = master.grid
    top = master.margins.top_mm * PT_PER_MM
    content_w = grid.chars_per_line * grid.char_advance_pt
    pad = frame.pad_pt
    return StrokeRect(
        x0=left_x_pt - pad,
        y0=top - pad,
        x1=left_x_pt + content_w + pad,
        y1=top + n_lines * grid.line_pitch_pt + pad,
        cmyk=frame.cmyk,
        line_width_pt=frame.line_width_pt,
    )
