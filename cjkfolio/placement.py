"""字形佈局層（pt 空間）：與 render.py 的 PNG 像素路徑同一套 pen 數學。

輸出 GlyphPlacement（top-down 頁面 pt 座標、字形「水平原點」），供 PDF 寫出層
以顯式 Tm 逐字定位。PNG 渲染維持既有像素路徑；兩後端幾何以同一組
行軸／字槽輸入對齊，PDF 端另以 PyMuPDF 渲染測試釘住（tests/test_pdf_writer.py）。

座標約定：x 向右、y 向下（與 PNG 同）；PDF 寫出時再轉 y-up 並加出血偏移。
"""
from dataclasses import dataclass

# 與 render._render_horizontal_strip 同源的基線比例（水平字條）
ASCENT_RATIO = 0.88
DESCENT_RATIO = 0.32
TCY_SIZE_RATIO = 0.92  # 縱中橫縮字比例（同 render._draw_tcy）
RUBY_SIZE_RATIO = 0.5  # 注音／ruby 相對 base 字級（CLREQ 慣例：約半形）


def ruby_axis_and_top(base_axis_x_pt: float, cell_top_pt: float,
                      base_advance_pt: float, base_size_pt: float, ruby_len: int,
                      ratio: float = RUBY_SIZE_RATIO):
    """直排 mono-ruby 幾何（純函式，兩後端共用）：ruby 置 base 右側鄰欄、垂直置中。

    回傳 (ruby_axis_x_pt, ruby_top_pt, ruby_size_pt)：
    - ruby_axis_x：base 行軸 ＋ base 字框右半 ＋ ruby 字框左半（緊鄰 base 右側，落欄間槽溝）。
    - ruby_top：base 字槽中心 − ruby 串總高一半（ruby 串以 ttb 自 top 起排，故垂直置中於 base）。
    - ruby_size：base 字級 × ratio。

    直排 vertical-rl 中 ＋x 為頁面右向（注音置字右側，CLREQ）；v1 不做 ruby 驅動的
    base 間距調整（ruby 較長時溢出欄溝，見 GAPS）。
    """
    ruby_size = base_size_pt * ratio
    ruby_axis_x = base_axis_x_pt + base_size_pt / 2 + ruby_size / 2
    ruby_top = cell_top_pt + base_advance_pt / 2 - ruby_len * ruby_size / 2
    return ruby_axis_x, ruby_top, ruby_size


@dataclass(frozen=True)
class GlyphPlacement:
    gid: int
    ch: str          # 來源字元（ToUnicode 用；查不到 cluster 時為空字串）
    x_pt: float      # 字形水平原點（top-down 頁面 pt）
    y_pt: float
    size_pt: float   # 有效字級（縱中橫縮字後）
    rotated: bool = False  # True＝順時針轉 90 度（直排中的長串拉丁）


def _cluster_char(text: str, cluster: int) -> str:
    return text[cluster] if 0 <= cluster < len(text) else ""


def ttb_char_placements(shaper, ch: str, axis_x_pt: float, cell_top_pt: float,
                        size_pt: float) -> list:
    """單一 CJK 字直排（vert）置於字槽：行軸置中、槽頂對齊（同 render._draw_ttb_char）。"""
    sf = size_pt / shaper.upem
    infos, poss = shaper.shape(ch, "ttb")
    out = []
    pen_x, pen_y = axis_x_pt, cell_top_pt
    for info, pos in zip(infos, poss):
        out.append(GlyphPlacement(
            info.codepoint, _cluster_char(ch, info.cluster),
            pen_x + pos.x_offset * sf, pen_y - pos.y_offset * sf, size_pt,
        ))
        pen_x += pos.x_advance * sf
        pen_y += -pos.y_advance * sf
    return out


def horizontal_run(shaper, text: str, size_pt: float):
    """LTR 塑形：回傳（[(gid, ch, x, dy), ...], 總寬 pt）。

    x 沿基線向右自 0 起；dy 為相對基線的 top-down 偏移（上負下正）。
    """
    sf = size_pt / shaper.upem
    infos, poss = shaper.shape(text, "ltr")
    glyphs = []
    pen = 0.0
    for info, pos in zip(infos, poss):
        glyphs.append((
            info.codepoint, _cluster_char(text, info.cluster),
            pen + pos.x_offset * sf, -pos.y_offset * sf,
        ))
        pen += pos.x_advance * sf
    return glyphs, pen


def run_width_pt(shaper, text: str, size_pt: float) -> float:
    return horizontal_run(shaper, text, size_pt)[1]


def horizontal_cell_advance_pt(shaper, cell, size_pt: float,
                               char_advance_pt: float) -> float:
    """橫排一個 cell 的水平推進量（render 與 pdf_writer 共用同一套 advance 數學）。

    latin（連續 ascii 串）走塑形自然寬；cjk 與全形空格走 em 格（char_advance）。
    橫排無縱中橫（tokenize 已不產 tcy），故不特判 tcy。
    """
    if cell.kind == "latin":
        return run_width_pt(shaper, cell.text, size_pt)
    return char_advance_pt


def horizontal_placements(shaper, text: str, pen_x_pt: float, baseline_y_pt: float,
                          size_pt: float) -> list:
    """水平字條（頁腳三件組）：自基線左端 pen 起排。"""
    glyphs, _ = horizontal_run(shaper, text, size_pt)
    return [
        GlyphPlacement(gid, ch, pen_x_pt + gx, baseline_y_pt + gdy, size_pt)
        for gid, ch, gx, gdy in glyphs
    ]


def tcy_placements(shaper, text: str, axis_x_pt: float, cell_top_pt: float,
                   size_pt: float, advance_pt: float) -> list:
    """縱中橫：短數字串橫排塞進一個字槽，行軸置中（同 render._draw_tcy）。"""
    eff = size_pt * TCY_SIZE_RATIO
    glyphs, width = horizontal_run(shaper, text, eff)
    strip_h = eff * (ASCENT_RATIO + DESCENT_RATIO)
    s = 1.0 if width <= size_pt or width <= 0 else size_pt / width
    baseline_y = cell_top_pt + (advance_pt - s * strip_h) / 2 + s * eff * ASCENT_RATIO
    start_x = axis_x_pt - s * width / 2
    return [
        GlyphPlacement(gid, ch, start_x + s * gx, baseline_y + s * gdy, eff * s)
        for gid, ch, gx, gdy in glyphs
    ]


def rotated_latin_placements(shaper, text: str, axis_x_pt: float, cell_top_pt: float,
                             size_pt: float) -> list:
    """長串拉丁／數字：橫排塑形後順時針轉 90 度沿行軸向下（同 render._draw_rotated_latin）。

    基線位置由字條旋轉幾何推得：baseline_x = 行軸 + (desc - asc) / 2。
    """
    glyphs, _ = horizontal_run(shaper, text, size_pt)
    baseline_x = axis_x_pt + size_pt * (DESCENT_RATIO - ASCENT_RATIO) / 2
    return [
        GlyphPlacement(gid, ch, baseline_x - gdy, cell_top_pt + gx, size_pt, rotated=True)
        for gid, ch, gx, gdy in glyphs
    ]
