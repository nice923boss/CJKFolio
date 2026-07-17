"""樣式選單回呼 mixin（Sprint 78 自 app.py 抽出行數紀律分檔；行為不變）。

EditorWindow 的樣式域操作：雙擊編輯（Sprint 71）、新增／刪除（Sprint 71）、
重新命名（Sprint 78 UI，核心 Sprint 75 成對單一 undo）、色票新增／改值／刪除
（Sprint 78 UI，核心 Sprint 76）、另存模版（Sprint 71）。QInputDialog 只在
真視窗路徑（參數注入可旁路＝離屏 smoke 可驗，承 _create_style 慣例）。
"""
from PySide6.QtWidgets import QFileDialog, QInputDialog

from cjkfolio.frame_editing import FrameEditResult
from cjkfolio.styles import TemplateError, save_template

from .style_panel import StyleEditDialog, SwatchEditDialog


class StyleActionsMixin:
    """樣式選單域回呼（掛在 EditorWindow 上；依賴 session／_style_panel／statusBar）。"""

    # ---------- 樣式參數編輯（Sprint 71） ----------

    def _edit_style(self, kind: str, name: str) -> None:
        """雙擊樣式項 → 編輯樣式參數對話框（session.update_*，改樣式即全書套用）。"""
        styles = (self.template.paragraph_styles if kind == "para"
                  else self.template.character_styles)
        dlg = StyleEditDialog(
            kind, styles[name],
            lambda changes: self._apply_style_definition(kind, name, changes), self)
        dlg.exec()

    def _apply_style_definition(self, kind: str, name: str, changes):
        """套用樣式定義變更；回錯誤訊息（留在對話框修正）或 None（成功／無變更）。"""
        if not changes:
            return None
        try:
            res = (self.session.update_para_style(name, changes) if kind == "para"
                   else self.session.update_char_style(name, changes))
        except (TemplateError, KeyError, ValueError) as err:
            return f"無法套用：{err}"
        self._after_template_change(res, f"樣式「{name}」已更新（全書重排）")
        return None

    # ---------- 樣式新增／刪除／改名 ----------

    def _create_style(self, kind: str, name=None) -> None:
        """新增樣式（基於面板選取樣式為基底；name None＝真視窗跳輸入框）。"""
        base = self._style_panel.selected_style(kind)
        if base is None:
            self.statusBar().showMessage("先在面板選取一個樣式作為新樣式的基底")
            return
        if name is None:
            name, ok = QInputDialog.getText(
                self, "新增樣式", f"新樣式名稱（承 {base}）：")
            if not ok or not name:
                return
        try:
            res = (self.session.add_para_style(name, {"based_on": base})
                   if kind == "para"
                   else self.session.add_char_style(name, {"based_on": base}))
        except TemplateError as err:
            self.statusBar().showMessage(f"無法新增：{err}")
            return
        self._after_template_change(res, f"已新增樣式「{name}」（承 {base}）")

    def _remove_selected_style(self, kind: str, name=None) -> None:
        """刪除選取樣式；參照守門（模版內引用）與文件使用中皆顯示訊息不 crash。"""
        name = name or self._style_panel.selected_style(kind)
        if name is None:
            self.statusBar().showMessage("先在面板選取要刪除的樣式")
            return
        try:
            res = (self.session.remove_para_style(name) if kind == "para"
                   else self.session.remove_char_style(name))
        except (TemplateError, KeyError) as err:
            self.statusBar().showMessage(f"無法刪除：{err}")
            return
        self._after_template_change(res, f"已刪除樣式「{name}」")

    def _rename_selected_style(self, kind: str, new_name=None) -> None:
        """重新命名選取樣式（Sprint 78 UI；核心 Sprint 75＝模版與文件全參照
        成對單一 undo 步）。new_name None＝真視窗跳輸入框。"""
        old = self._style_panel.selected_style(kind)
        if old is None:
            self.statusBar().showMessage("先在面板選取要重新命名的樣式")
            return
        if new_name is None:
            new_name, ok = QInputDialog.getText(
                self, "重新命名樣式", f"「{old}」的新名稱：")
            if not ok or not new_name:
                return
        try:
            res = (self.session.rename_para_style(old, new_name) if kind == "para"
                   else self.session.rename_char_style(old, new_name))
        except (TemplateError, KeyError) as err:
            self.statusBar().showMessage(f"無法改名：{err}")
            return
        self._after_template_change(res, f"樣式「{old}」→「{new_name}」（全書同步）")

    # ---------- 色票（Sprint 78 UI；核心 Sprint 76） ----------

    def _edit_swatch(self, name: str) -> None:
        """雙擊色票項 → 改值對話框（session.update_color，改值即全書變色）。"""
        dlg = SwatchEditDialog(
            self.template.colors[name],
            lambda changes: self._apply_swatch_definition(name, changes), self)
        dlg.exec()

    def _apply_swatch_definition(self, name: str, changes):
        """套用色票變更；回錯誤訊息（留在對話框修正）或 None（成功／無變更）。"""
        if not changes:
            return None
        try:
            res = self.session.update_color(name, changes)
        except (TemplateError, KeyError, ValueError) as err:
            return f"無法套用：{err}"
        self._after_template_change(res, f"色票「{name}」已更新（全書變色）")
        return None

    def _create_swatch(self, name=None) -> None:
        """新增色票（預設純黑 K100 起始值，雙擊改值）；name None＝真視窗跳輸入框。"""
        if name is None:
            name, ok = QInputDialog.getText(self, "新增色票", "色票名稱：")
            if not ok or not name:
                return
        try:
            res = self.session.add_color(name, cmyk=(0.0, 0.0, 0.0, 1.0))
        except TemplateError as err:
            self.statusBar().showMessage(f"無法新增：{err}")
            return
        self._after_template_change(res, f"已新增色票「{name}」（K100，雙擊改值）")

    def _remove_selected_swatch(self, name=None) -> None:
        """刪除選取色票；被樣式引用守門顯示訊息不 crash。"""
        name = name or self._style_panel.selected_swatch()
        if name is None:
            self.statusBar().showMessage("先在面板選取要刪除的色票")
            return
        try:
            res = self.session.remove_color(name)
        except (TemplateError, KeyError) as err:
            self.statusBar().showMessage(f"無法刪除：{err}")
            return
        self._after_template_change(res, f"已刪除色票「{name}」")

    # ---------- 另存與共用收尾 ----------

    def _save_template_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "另存模版", "", "模版 JSON (*.json)")
        if path:
            self._save_template_to(path)

    def _save_template_to(self, path) -> None:
        """另存現行模版（含樣式編輯結果）為人類可讀 JSON（Sprint 70 核心）。"""
        save_template(self.session.template, path)
        self.statusBar().showMessage(f"模版已另存：{path}")

    def _after_template_change(self, res, message: str) -> None:
        """模版變更（樣式／色票編輯）後：重繪＋游標跟隨＋面板清單同步。"""
        if res is None:
            self.statusBar().showMessage("樣式無變更")
            return
        if isinstance(res, FrameEditResult):
            self._follow_frame_address(res)
        else:
            self._follow_body_address(res)
        self.statusBar().showMessage(message)
