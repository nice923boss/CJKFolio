"""圖文繞排（Sprint 89，Phase 4）：置入圖框 → 排除區 → 帶排除區重排。

規則以真書《內在整理》179 頁全掃為據（tools/measure_wrap_pages.py，8 個
wrap-partial 樣本，A 級）：圖矩形跨數欄，受影響欄的內文避開圖的字軸範圍，且
同欄不跨圖續排（無「圖上下同欄皆有字」樣本）。真書圖文間隙 1〜3 字格不等
（＝作者自由放置圖框的設計選擇，非排版規則），本產品由 PlacedImage.wrap_margin_mm
表達，不硬編（§4.4 分工鐵律：幾何屬引擎、語意與留白屬使用者）。

分層：本模組只做「rect（trim pt）→ engine.Exclusion（行槽＋字軸 pt 區間）」的
換算與兩趟流排編排；字格裁切在 engine.line_window（不認識主版與鏡像），行軸取
primitives.line_axis_x_pt（與兩後端同一事實來源）。
"""
from dataclasses import replace
from math import ceil, floor

from .engine import Exclusion
from .layout import layout_document
from .primitives import PT_PER_MM, book_number_for, line_axis_x_pt

_EPS = 1e-6


def image_exclusion(rect, template, master, book_number: int,
                    margin_pt: float = 0.0):
    """圖框 rect（trim pt、top-down）→ 該頁 Exclusion；不覆蓋任何行槽時回 None。

    行軸：行槽 slot 佔 x ∈ [axis(slot) ± 行距/2]，與圖框（含 margin）相交即受影響；
    區間夾到主版行槽數（圖溢出版心時只取版心內的部分）。
    字軸：回傳相對天頭的 pt 區間（各樣式字距不同，換算字格於斷行時做）。
    """
    x0, y0, x1, y1 = rect
    x0 -= margin_pt
    y0 -= margin_pt
    x1 += margin_pt
    y1 += margin_pt
    grid = master.grid
    pitch = grid.line_pitch_pt
    half = pitch / 2
    axis0 = line_axis_x_pt(template, master, 0, book_number)
    # 重疊條件：axis(s)−half < x1 且 axis(s)+half > x0，axis(s)＝axis0 − s×pitch
    slot_lo = max(0, int(ceil((axis0 - x1 - half) / pitch + _EPS)))
    slot_hi = min(grid.lines_per_page,
                  int(floor((axis0 - x0 + half) / pitch - _EPS)) + 1)
    if slot_hi <= slot_lo:
        return None
    top_pt = master.margins.top_mm * PT_PER_MM
    return Exclusion(slot_lo=slot_lo, slot_hi=slot_hi,
                     span_lo_pt=y0 - top_pt, span_hi_pt=y1 - top_pt)


def page_exclusions(doc, pages, template, first_page: int = 1,
                    cover_pages: int = 0) -> dict:
    """{版面頁號: (Exclusion, ...)}：doc 中 wrap 圖依其落點頁主版與鏡像換算。

    pages＝Pass 1 的 LayoutPage 序列（提供逐頁主版與書寫方向）。橫排頁 v1 不繞排
    （行軸語意不同，GAPS 誠實登記）；落點頁超出排版頁數者略過（由
    images.resolve_placed_images 於渲染時快速失敗，此處不重複報錯）。
    """
    by_page = {p.number: p for p in pages}
    out: dict = {}
    for im in doc.images:
        if not im.wrap:
            continue
        page = by_page.get(im.page)
        if page is None or not page.vertical:
            continue
        master = template.masters[page.master]
        ex = image_exclusion(im.rect, template, master,
                             book_number_for(im.page, first_page, cover_pages),
                             margin_pt=im.wrap_margin_mm * PT_PER_MM)
        if ex is not None:
            out.setdefault(im.page, []).append(ex)
    return {page: tuple(exs) for page, exs in out.items()}


def layout_with_wrap(doc, template, first_page: int = 1,
                     first_para_continues: bool = False):
    """流排並套用圖文繞排：無 wrap 圖時等同 layout_document（輸出零變更）。

    兩趟（同 Sprint 85 auto-TOC 先例）：Pass 1 無排除區流排，取得逐頁主版與書寫
    方向（排除區換算需要主版網格與鏡像）；Pass 2 帶排除區重排。Pass 2 後若 wrap
    圖落點頁的主版改變（節式多主版文件因繞排位移分頁），排除區與該頁主版失配，
    列入 violations 不沉默（不自動再迭代＝避免不收斂）。
    """
    result = layout_document(doc, template, first_para_continues)
    if not any(im.wrap for im in doc.images):
        return result
    exclusions = page_exclusions(doc, result.pages, template, first_page,
                                 result.cover_pages)
    if not exclusions:
        return result
    final = layout_document(doc, template, first_para_continues,
                            exclusions=exclusions)
    before = {p.number: p.master for p in result.pages}
    after = {p.number: p.master for p in final.pages}
    drift = [im.page for im in doc.images
             if im.wrap and before.get(im.page) != after.get(im.page)]
    if drift:
        return replace(final, violations=final.violations + [
            f"圖文繞排：置入圖頁 {sorted(set(drift))} 的主版於重排後改變"
            f"（{[before.get(p) for p in sorted(set(drift))]}"
            f"→{[after.get(p) for p in sorted(set(drift))]}），"
            "排除區依重排前主版換算，請確認圖框落點"
        ])
    return final


__all__ = ["image_exclusion", "layout_with_wrap", "page_exclusions"]
