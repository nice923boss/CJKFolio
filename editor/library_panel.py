"""模版庫對話框（Sprint 80，§4.3「模版庫」UI 半邊；核心 Sprint 77 template_library）。

列出目錄內模版清單（壞檔標註 error 不沉默、不可套用），選取後「套用」＝
session.apply_template 整份替換入統一 undo（文件引用缺樣式快速失敗，錯誤留
內嵌警示列不污染現態）。v1 目錄＝內建 templates/（使用者庫目錄慣例後續）。
"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class TemplateLibraryDialog(QDialog):
    """模版庫清單（離屏可驗：select_path 程式化選取後呼 _on_apply_clicked）。"""

    def __init__(self, entries, on_apply_path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("模版庫")
        self._entries = tuple(entries)
        self._on_apply_path = on_apply_path  # callable(path) -> 錯誤訊息或 None

        box = QVBoxLayout(self)
        head = QLabel("選取模版後套用（整份替換現行模版，一步 undo 可回；"
                      "文件用到而新模版沒有的樣式會擋下不套用）。")
        head.setWordWrap(True)
        box.addWidget(head)
        self._notice = QLabel("")
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)
        box.addWidget(self._notice)

        self.listing = QListWidget()
        for entry in self._entries:
            if entry.error is None:
                label = f"{entry.name}（{entry.path.name}）"
            else:
                label = f"（壞檔）{entry.path.name}：{entry.error}"
            item = QListWidgetItem(label)
            self.listing.addItem(item)
        box.addWidget(self.listing)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        apply_btn = buttons.addButton(
            "套用選取模版", QDialogButtonBox.ButtonRole.ActionRole)
        apply_btn.clicked.connect(self._on_apply_clicked)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def selected_entry(self):
        row = self.listing.currentRow()
        return self._entries[row] if 0 <= row < len(self._entries) else None

    def select_path(self, name: str) -> None:
        """程式化選取（檔名比對；選單操作與離屏驗證用）。"""
        for i, entry in enumerate(self._entries):
            if entry.path.name == name:
                self.listing.setCurrentRow(i)
                return
        raise KeyError(f"庫清單無此檔：{name}")

    def _on_apply_clicked(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            self._notice.setText("先選取一份模版")
            return
        if entry.error is not None:
            self._notice.setText(f"壞檔不可套用：{entry.error}")
            return
        err = self._on_apply_path(entry.path)
        if err:
            self._notice.setText(err)
            return
        self.accept()
