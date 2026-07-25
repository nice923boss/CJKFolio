"""成品尺寸動作 mixin（Sprint 140 甲）：版面＞成品尺寸…。

收對話框的寬高與重算旗標 → session.update_page_size（單一 undo 步，模版層先重排
再入歷史）→ 重繪，並把這次改尺寸**新造成**的溢出項據實列出。改尺寸前就溢出的項
（模版既有狀態，如 B-部扉，GAPS #95）不重複報，免得淹掉真正該看的。

換算與判定全在 cjkfolio.page_size（Qt 無關、pytest 已驗），本檔只調度與呈現。
依賴 EditorWindow 提供的 self.template／self.doc／self.session／statusBar()／
self._after_template_change。
"""
from PySide6.QtWidgets import QDialog, QMessageBox

from cjkfolio.page_size import new_fit_warnings
from cjkfolio.styles import TemplateError

from .page_size_panel import PageSizeDialog

#: 溢出提示對話框最多列幾項（其餘以「另有 N 項」收尾，不靜默截斷）。
MAX_LISTED_WARNINGS = 10


class PageSizeActionsMixin:
    """版面選單的成品尺寸入口（InDesign 對應＝檔案＞文件設定的頁面大小）。"""

    def _page_size_dialog(self, values=None) -> None:
        """開成品尺寸對話框並套用；values 注入＝離屏可驗（同 _create_style 慣例）。"""
        if values is None:
            dlg = PageSizeDialog(self.template, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self.statusBar().showMessage("已取消成品尺寸變更")
                return
            values = dlg.values()
        before = self.template
        try:
            res = self.session.update_page_size(
                values["width_mm"], values["height_mm"],
                refit_grid=values["refit_grid"])
        except TemplateError as err:  # 非法尺寸：狀態不變，據實說明留給使用者改
            self.statusBar().showMessage(f"無法改成品尺寸：{err}")
            return
        if res is None:
            self.statusBar().showMessage("成品尺寸無變更")
            return
        warnings = new_fit_warnings(before, self.session.template, self.doc)
        pages = len(self.session.layout.pages)
        detail = (f"版心已重算，全書重排為 {pages} 頁"
                  if values["refit_grid"] else "只換紙張，一個字都沒重排")
        self._after_template_change(
            res,
            f"成品尺寸 {values['width_mm']:g} × {values['height_mm']:g} mm"
            f"（{detail}；一步 undo 可回）"
            + (f"；{len(warnings)} 項落到成品外" if warnings else ""))
        if warnings:
            self._show_fit_warnings(warnings)

    def _show_fit_warnings(self, warnings) -> None:
        """列出改尺寸新造成的溢出項（提示而非阻擋：貼邊與出血本就會超出 trim）。"""
        listed = warnings[:MAX_LISTED_WARNINGS]
        tail = ([f"（另有 {len(warnings) - len(listed)} 項未列出）"]
                if len(warnings) > len(listed) else [])
        QMessageBox.warning(
            self, "成品尺寸已變更：有項目落在成品外",
            "\n".join(["改成這個尺寸後，以下項目超出成品範圍（未自動搬動，"
                       "可 Ctrl+Z 回上一個尺寸）：", ""] + listed + tail))
