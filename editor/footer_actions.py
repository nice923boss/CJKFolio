"""書眉動作 mixin（Sprint 142）：版面＞書眉與頁碼…。

Owner 回饋：右下角固定呈現的書名要能改文字、移動位置、批次移動位置。
對象取**目前頁所用主版**的頁腳元素（同 master_actions 以目前頁為準的慣例）：
書眉是主版屬性，改的是「這個版型的書眉」，不是某一頁的書眉。

目前主版沒宣告頁腳（如封面 H-封面）時據實拒收，並指名哪些主版有書眉可改，
不靜默什麼都不做。改完不重排文字（書眉不參與斷行幾何），仍走 session 的
_commit_template 紀律先重排快速失敗再入單一 undo 步。

依賴 EditorWindow 提供的 self.template／self.session／self.page／statusBar()／
self._after_template_change／self.layout_result。
"""
from PySide6.QtWidgets import QDialog

from cjkfolio.styles import TemplateError

from .footer_panel import FooterItemDialog


class FooterActionsMixin:
    """版面選單的書眉入口（InDesign 對應＝主版頁上的頁首／頁尾文字框）。"""

    def _current_master_name(self) -> str:
        """目前頁所用的主版名（版面已算好逐頁主版，不必回推節）。"""
        return self.layout_result.pages[self.page.number - 1].master

    def _footer_dialog(self, item_name=None, values=None,
                       all_masters: bool = False) -> None:
        """開書眉對話框並套用；item_name／values 注入＝離屏可驗（同慣例）。"""
        master_name = self._current_master_name()
        if not self.template.masters[master_name].footer:
            others = sorted(n for n, m in self.template.masters.items() if m.footer)
            self.statusBar().showMessage(
                f"主版 {master_name} 沒有書眉或頁碼可改（頁 {self.page.number} 用的是"
                f"它）。有書眉的主版：{'、'.join(others) or '無'}；請先翻到用這些主版"
                "的頁面再開此對話框")
            return
        if values is None:
            dlg = FooterItemDialog(self.template, master_name, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self.statusBar().showMessage("已取消書眉變更")
                return
            item_name, values, all_masters = (
                dlg.item_name(), dlg.values(), dlg.all_masters())
        try:
            res = self.session.update_footer_item(
                master_name, item_name, values, all_masters=all_masters)
        except (TemplateError, KeyError) as err:  # 狀態不變，據實說明留給使用者改
            self.statusBar().showMessage(f"無法改書眉：{err}")
            return
        if res is None:
            self.statusBar().showMessage("書眉無變更")
            return
        item = self.session.template.masters[master_name].footer[item_name]
        scope = "所有含此元素的主版" if all_masters else f"主版 {master_name}"
        self._after_template_change(
            res,
            f"已改{scope}的「{item_name}」："
            f"文字＝{item.text or '（照文件書名）'}，"
            f"距上緣 {item.baseline_from_top_pt:.1f}pt、"
            f"距書口 {item.outer_offset_pt:.1f}pt（一步 undo 可回）")
