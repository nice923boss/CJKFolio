"""整版等比縮放換開本（Sprint 157）：字級、字距、行距、邊距與自由佈局層一起乘同一倍率。

Owner：「變更尺寸時，原本裡面的文字字級要等比例變大」，並選定「整版等比縮放」：
行列數與頁數不變，整頁像放大縮小影印一樣換到新紙張上。

倍率 k＝min(新寬／舊寬, 新高／舊高)。寬高比例不同時，短的那一軸剛好填滿，長的那一軸
多出的空間平均補到兩側邊距（等同把縮放後的舊頁面置中擺上新紙）。故任一點的對應為
x' = k·x + dx/2、y' = k·y + dy/2（dx、dy＝新紙減縮放後舊紙），長度只乘 k。

整頁蓋滿的置入圖（舊框四邊都到成品邊以外，即滿版與出血圖）不走點對應：兩軸比例不同時
置中後會在長軸兩側露出白邊，正是 Owner 抓過的匯出白邊問題。這類圖改以原框寬高比重算
「鋪滿頁面＋四邊出血」（同一鍵滿版 fill），換開本後仍無白邊。

出血寬度（RuleSpec.bleed_extend_pt）是印刷規格 3mm，與開本無關，不縮放。
本層為純函式（同 page_size 慣例）：回傳新 Template 與新 Document，入 undo 歷史與重排由
session.scale_page_size 負責；換算後版心兩軸恰好等於縮放後的值，行列數不變。
"""
from dataclasses import replace

from .image_editing import full_page_rect
from .page_size import FIT_TOLERANCE_PT, _check_mm
from .primitives import PT_PER_MM
from .styles import Template


def scale_factor(template: Template, width_mm: float, height_mm: float) -> float:
    """新舊開本的整版倍率：兩軸取小（大的那軸多出的空間補到邊距）。"""
    return min(width_mm / template.page_width_mm, height_mm / template.page_height_mm)


def _scale_master(master, k: float, dx: float, dy: float):
    """主版：長度乘 k，自頁緣量起的錨點再加該軸補邊量的一半。dx、dy 單位 pt。"""
    m = master.margins
    half_x_mm, half_y_mm = dx / 2 / PT_PER_MM, dy / 2 / PT_PER_MM
    margins = replace(m, top_mm=m.top_mm * k + half_y_mm,
                      bottom_mm=m.bottom_mm * k + half_y_mm,
                      outer_mm=m.outer_mm * k + half_x_mm,
                      inner_mm=m.inner_mm * k + half_x_mm)
    g = master.grid
    grid = replace(g, char_advance_pt=g.char_advance_pt * k,
                   line_pitch_pt=g.line_pitch_pt * k, base_size_pt=g.base_size_pt * k)
    footer = {name: replace(item, baseline_from_top_pt=item.baseline_from_top_pt * k + dy / 2,
                            outer_offset_pt=item.outer_offset_pt * k + dx / 2)
              for name, item in master.footer.items()}
    frame = master.frame and replace(
        master.frame, line_width_pt=master.frame.line_width_pt * k,
        pad_pt=master.frame.pad_pt * k,
        pad_v_pt=None if master.frame.pad_v_pt is None else master.frame.pad_v_pt * k)
    figure = master.figure and replace(
        master.figure, top_from_top_pt=master.figure.top_from_top_pt * k + dy / 2,
        bottom_from_top_pt=master.figure.bottom_from_top_pt * k + dy / 2,
        line_width_pt=master.figure.line_width_pt * k,
        dash_on_pt=master.figure.dash_on_pt * k, dash_off_pt=master.figure.dash_off_pt * k)
    rule = master.rule and replace(
        master.rule, y_from_top_pt=master.rule.y_from_top_pt * k + dy / 2,
        line_width_pt=master.rule.line_width_pt * k,
        dash_on_pt=master.rule.dash_on_pt * k, dash_off_pt=master.rule.dash_off_pt * k,
        break_before_pt=master.rule.break_before_pt * k,
        break_after_pt=master.rule.break_after_pt * k)
    toc = master.toc and replace(
        master.toc, page_no_bottom_pt=master.toc.page_no_bottom_pt * k + dy / 2,
        leader_width_pt=master.toc.leader_width_pt * k,
        leader_gap_pt=master.toc.leader_gap_pt * k)
    return replace(master, margins=margins, grid=grid, footer=footer,
                   frame=frame, figure=figure, rule=rule, toc=toc)


def _covers_page(rect, page_w: float, page_h: float) -> bool:
    x0, y0, x1, y1 = rect
    tol = FIT_TOLERANCE_PT
    return x0 <= tol and y0 <= tol and x1 >= page_w - tol and y1 >= page_h - tol


def _map_rect(rect, k: float, dx: float, dy: float) -> tuple:
    x0, y0, x1, y1 = rect
    return (x0 * k + dx / 2, y0 * k + dy / 2, x1 * k + dx / 2, y1 * k + dy / 2)


def scale_page_size(template: Template, doc, width_mm, height_mm, *, bleed_pt: float):
    """整版等比換開本：回 (新模版, 新文件)；尺寸不變時原物件原樣回（no-op）。

    bleed_pt 為整頁蓋滿圖重算鋪滿時的四邊出血（呼叫端傳 press_marks.BLEED_MM 換算值）。
    """
    w_mm = _check_mm(width_mm, "寬")
    h_mm = _check_mm(height_mm, "高")
    if (w_mm, h_mm) == (template.page_width_mm, template.page_height_mm):
        return template, doc
    k = scale_factor(template, w_mm, h_mm)
    old_w = template.page_width_mm * PT_PER_MM
    old_h = template.page_height_mm * PT_PER_MM
    new_w, new_h = w_mm * PT_PER_MM, h_mm * PT_PER_MM
    dx, dy = new_w - old_w * k, new_h - old_h * k

    paragraph_styles = {
        name: replace(st, size_pt=st.size_pt * k, lead_offset_pt=st.lead_offset_pt * k)
        for name, st in template.paragraph_styles.items()}
    character_styles = {name: replace(st, size_pt=st.size_pt * k)
                        for name, st in template.character_styles.items()}
    masters = {name: _scale_master(mp, k, dx, dy) for name, mp in template.masters.items()}
    new_template = replace(template, page_width_mm=w_mm, page_height_mm=h_mm,
                           paragraph_styles=paragraph_styles,
                           character_styles=character_styles, masters=masters)

    def scale_image(im):
        if im.rect is None:  # 槽式圖跟著主版 figure 保留區走
            return replace(im, wrap_margin_mm=im.wrap_margin_mm * k)
        x0, y0, x1, y1 = im.rect
        if _covers_page(im.rect, old_w, old_h):
            rect = full_page_rect((x1 - x0) / (y1 - y0), new_w, new_h,
                                  mode="fill", bleed_pt=bleed_pt)
        else:
            rect = _map_rect(im.rect, k, dx, dy)
        return replace(im, rect=rect, wrap_margin_mm=im.wrap_margin_mm * k)

    new_doc = replace(
        doc, images=tuple(scale_image(im) for im in doc.images),
        text_frames=tuple(replace(tf, rect=_map_rect(tf.rect, k, dx, dy))
                          for tf in doc.text_frames))
    return new_template, new_doc
