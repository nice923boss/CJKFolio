"""成品尺寸（trim size）：改紙張大小，並選配依新尺寸重算版心行列（Sprint 140）。

模版的 page.width_mm／height_mm 就是裁切後的成品尺寸（trim）：PDF 的 TrimBox
（press_marks.page_boxes_pt）與兩後端的頁面座標系皆自此推導。本層為純模版層
（同 style_editing 慣例）：回傳新 Template、等值變更 no-op 回原物件，入 undo 歷史
與全書重排由 session.update_page_size 負責。

**版心不會自己跟著紙張走。** 內文區塊錨在天頭與書口（layout 自 margins.top_mm 起排、
primitives.line_axis_x_pt 自 page_w − outer_mm 起算），而它的高與寬由主版網格決定
（高＝chars_per_line × char_advance_pt；寬＝(lines_per_page − 1) × line_pitch_pt
＋ base_size_pt，因末行只佔半個字身而非整個行距），與頁面尺寸無關。
故改尺寸有兩種語意，由呼叫端明示：

- refit_grid=False：只換紙張。一個字都不重排、頁數不變；紙縮小時版心會溢出成品範圍。
- refit_grid=True：邊距原封不動，把紙張增減的空間換算成行列數增減（字距與行距不動），
  內文重排、頁數會變。

兩種語意都不搬動絕對 pt 錨點（頁腳基線、目錄頁碼底錨、圖框保留區、裝飾線，以及
文件層置入圖與文字框的 rect）：那些是一手量測值，機械縮放會毀掉排版設計。落在新
成品範圍外的項由 page_fit_warnings 據實列出，不沉默、不自動搬。
"""
from dataclasses import dataclass, replace
from math import floor
from pathlib import Path

from .primitives import PT_PER_MM
from .styles import MasterPage, Template, TemplateError

_EPS = 1e-6

#: PDF 頁面盒框的座標上限（PDF 1.4 起 14400 units＝200 inch）；換算 5080 mm。
#: 系統邊界快速失敗用，不是排版建議值。
MAX_PAGE_MM = 14400.0 / PT_PER_MM

#: 齊邊容差 0.5pt（0.18mm）。模版邊距以 mm 記到小數兩位，換算 pt 必留此量級的捨入差：
#: 本專案模版 A-內文版的 inner 25.58mm 即由 13 行網格反推後四捨五入，實算差 0.03pt。
#: 差在此值內視為齊邊，refit 與溢出判定兩處共用同一把尺，免得「重算完立刻警告溢出」。
FIT_TOLERANCE_PT = 0.5


@dataclass(frozen=True)
class FitWarning:
    """一項超出成品範圍的回報。

    key 是與尺寸無關的身分（如 "A-內文版/版心寬"），供呼叫端比對改尺寸前後、
    只呈現這次新增的溢出項；message 是含實際座標的繁中說明。
    """
    key: str
    message: str


def _check_mm(value, label: str) -> float:
    """成品尺寸邊界守門：正數且不逾 PDF 盒框上限（同 styles 載入層的快速失敗慣例）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TemplateError(f"成品{label}需為數字，得到 {value!r}")
    mm = float(value)
    if not 0 < mm <= MAX_PAGE_MM:
        raise TemplateError(
            f"成品{label} {mm:g} mm 超出可用範圍（須大於 0 且不逾 {MAX_PAGE_MM:.0f} mm）")
    return mm


def _body_width_pt(grid) -> float:
    """版心寬：末行只佔半個字身，故為 (行數 − 1) × 行距 ＋ 字身。

    與 primitives.line_axis_x_pt 同源：slot 0 的行軸在 page_w − outer − base/2，
    slot n−1 再往左 (n−1) × pitch，兩端各外擴 base/2。
    """
    return (grid.lines_per_page - 1) * grid.line_pitch_pt + grid.base_size_pt


def _count_delta(room_delta_pt: float, unit_pt: float) -> int:
    """紙張增減的空間換算成幾個字／幾行（含齊邊容差，尺寸不變時恆為 0）。"""
    return floor((room_delta_pt + FIT_TOLERANCE_PT) / unit_pt)


def _refit_master(master: MasterPage, dw_pt: float, dh_pt: float) -> MasterPage:
    """邊距不動，把紙張寬高的增減換算成行列數增減（字距、行距、基準級數不動）。

    刻意採「增減量」而非「拿邊距框重算」：本專案模版裡 B-部扉、D-目錄、F-版權頁的
    版心本來就不齊自己的名目邊距（部扉刻意留大天地、版權頁 45 行小字橫跨訂口），
    拿邊距框重算等於在使用者只想換開本時，順手把這三個主版重新設計一次。用增減量則
    各主版與自身邊距的既有關係原樣保留，且尺寸沒變時對每個主版都恰為零變更。
    """
    grid = master.grid
    chars = max(1, grid.chars_per_line + _count_delta(dh_pt, grid.char_advance_pt))
    lines = max(1, grid.lines_per_page + _count_delta(dw_pt, grid.line_pitch_pt))
    return replace(master, grid=replace(
        grid, chars_per_line=chars, lines_per_page=lines))


def set_page_size(template: Template, width_mm, height_mm, *,
                  refit_grid: bool = False) -> Template:
    """改成品尺寸；refit_grid=True 時一併把尺寸增減換算成各主版的行列數增減。

    等值變更 no-op 回原物件，故 session 的 `template is self._template` 判定成立、
    不推一步看不出差別的 undo。
    """
    w = _check_mm(width_mm, "寬")
    h = _check_mm(height_mm, "高")
    masters = template.masters
    if refit_grid:
        dw = (w - template.page_width_mm) * PT_PER_MM
        dh = (h - template.page_height_mm) * PT_PER_MM
        masters = {name: _refit_master(mp, dw, dh)
                   for name, mp in template.masters.items()}
    updated = replace(template, page_width_mm=w, page_height_mm=h, masters=masters)
    return template if updated == template else updated


def _master_fit_warnings(name: str, master: MasterPage,
                         page_w: float, page_h: float) -> list:
    """單一主版超出成品紙面的項（版心兩軸＋四類絕對 pt 錨點）。

    量的是紙邊而非名目邊距框：版心跨過自己的 inner／bottom 名目值是本專案模版真有的
    設計（見 _refit_master），跨過紙邊才是裁掉就沒了的錯。
    """
    m, grid = master.margins, master.grid
    out = []
    body_h = grid.chars_per_line * grid.char_advance_pt
    top = m.top_mm * PT_PER_MM
    if top + body_h > page_h + FIT_TOLERANCE_PT:
        out.append(FitWarning(
            f"{name}/版心高",
            f"主版「{name}」版心高 {body_h:.1f}pt（{grid.chars_per_line} 字）"
            f"自天頭 {top:.1f}pt 起排，下緣 {top + body_h:.1f}pt 超出成品高"
            f" {page_h:.1f}pt"))
    body_w = _body_width_pt(grid)
    # 起排側：mirror 時左右頁各以 outer／inner 為錨，錨距愈大版心愈往訂口伸，取大者為最壞情形
    anchor_mm = max(m.inner_mm, m.outer_mm) if master.mirror else m.outer_mm
    anchor = anchor_mm * PT_PER_MM
    if anchor + body_w > page_w + FIT_TOLERANCE_PT:
        out.append(FitWarning(
            f"{name}/版心寬",
            f"主版「{name}」版心寬 {body_w:.1f}pt（{grid.lines_per_page} 行）"
            f"自書口 {anchor:.1f}pt 起排，末行外緣越過成品寬 {page_w:.1f}pt"
            f" {anchor + body_w - page_w:.1f}pt"))
    anchors = [(f"頁腳「{key}」基線", master.footer[key].baseline_from_top_pt)
               for key in sorted(master.footer)]
    if master.toc is not None:
        anchors.append(("目錄頁碼底錨", master.toc.page_no_bottom_pt))
    if master.figure is not None:
        anchors.append(("圖框保留區下緣", master.figure.bottom_from_top_pt))
    if master.rule is not None:
        anchors.append(("裝飾線", master.rule.y_from_top_pt))
    out += [FitWarning(f"{name}/{label}",
                       f"主版「{name}」{label} {y:.1f}pt 落在成品高 {page_h:.1f}pt 之外")
            for label, y in anchors if y > page_h + _EPS]
    return out


def _rect_fit_warning(key: str, label: str, rect, page_w: float, page_h: float):
    """任意矩形（trim pt、top-down）超出成品紙面時的一項回報；未超出回 None。"""
    x0, y0, x1, y1 = rect
    if (x0 >= -_EPS and y0 >= -_EPS
            and x1 <= page_w + _EPS and y1 <= page_h + _EPS):
        return None
    return FitWarning(key, f"{label} 佔 ({x0:.1f}, {y0:.1f})〜({x1:.1f}, {y1:.1f})pt，"
                           f"超出成品 {page_w:.1f}×{page_h:.1f}pt")


def page_fit_warnings(template: Template, doc=None) -> list:
    """列出超出成品紙面的項（據實回報、不擋流程，同 ink.tac_warnings 慣例）。

    檢查各主版的版心兩軸與絕對 pt 錨點；給了 doc 時併檢文件層置入圖與文字框的
    rect。回傳 FitWarning 串列，空串列＝全數落在成品內。

    貼邊與出血置入圖本來就會超出 trim（document.PlacedImage 明載為正當用法），
    故本函式只據實列出座標，不判斷該不該修：裁切後不入成品者由使用者自行忽略。
    """
    page_w = template.page_width_mm * PT_PER_MM
    page_h = template.page_height_mm * PT_PER_MM
    out = []
    for name in sorted(template.masters):
        out += _master_fit_warnings(name, template.masters[name], page_w, page_h)
    if doc is None:
        return out
    for i, im in enumerate(doc.images):
        if im.rect is None:  # 槽式置入圖依主版 figure 保留區推導，無自身座標
            continue
        warning = _rect_fit_warning(
            f"置入圖/{i}", f"置入圖 {i + 1}（{Path(im.path).name}，頁 {im.page}）",
            im.rect, page_w, page_h)
        if warning:
            out.append(warning)
    for i, tf in enumerate(doc.text_frames):
        warning = _rect_fit_warning(
            f"文字框/{i}", f"文字框 {i + 1}（頁 {tf.page}）", tf.rect, page_w, page_h)
        if warning:
            out.append(warning)
    return out


def new_fit_warnings(before: Template, after: Template, doc=None) -> list:
    """只回這次改尺寸「新造成」的溢出訊息（改尺寸前就溢出的項不重複列出）。

    B-部扉在原尺寸就已宣告 8 行、末行外緣本來就越過紙邊（模版既有狀態，GAPS #95），
    每改一次尺寸都報一次只會淹掉真正該看的項。
    """
    old = {w.key for w in page_fit_warnings(before, doc)}
    return [w.message for w in page_fit_warnings(after, doc) if w.key not in old]
