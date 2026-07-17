"""AI 樣式指派校正對話框（Sprint 79，§4.4「逐段確認與批次改派」介面承諾）。

表格逐段列出：段序／段首文字／現行樣式／建議樣式（下拉＝模版實際段落樣式
候選集，預選 AI 建議）／採用勾選（預設勾「有建議且異於現行」者）。確定後
只回報「勾選且異於現行」的 {para_idx: 樣式名}，套用走 session.apply_para_styles
單一 undo 步（app 回呼執行）。AI 建議為初稿定位（§4.4：不宣稱全自動），
無建議段（該批降級）維持原樣式並於頂部警告列不沉默。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_PREVIEW_CHARS = 18


class AssignReviewDialog(QDialog):
    """逐段確認與批次改派（離屏可驗：程式化改勾選／下拉後呼 _assignments）。"""

    def __init__(self, doc, template, assignments, on_apply,
                 warnings=(), parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 樣式指派校正（初稿請人工確認）")
        self._doc = doc
        self._on_apply = on_apply  # callable({para_idx: style}) -> 錯誤訊息或 None
        candidates = sorted(template.paragraph_styles)

        box = QVBoxLayout(self)
        head = QLabel("逐段確認 AI 建議（§4.4 初稿＋人工校正）："
                      "勾選＝採用該列建議；可先改下拉再採用。")
        head.setWordWrap(True)
        box.addWidget(head)
        self._notice = QLabel("；".join(warnings))
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)
        box.addWidget(self._notice)

        self.table = QTableWidget(len(doc.paragraphs), 4)
        self.table.setHorizontalHeaderLabels(["採用", "段首文字", "現行樣式", "建議樣式"])
        self._combos = []
        for i, para in enumerate(doc.paragraphs):
            suggested = assignments[i] if i < len(assignments) else None
            adopt = QTableWidgetItem()
            adopt.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            adopt.setCheckState(
                Qt.CheckState.Checked
                if suggested is not None and suggested != para.style
                else Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, adopt)
            preview = QTableWidgetItem(para.text[:_PREVIEW_CHARS])
            preview.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 1, preview)
            current = QTableWidgetItem(para.style)
            current.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 2, current)
            combo = QComboBox()
            combo.addItems(candidates)
            combo.setCurrentText(suggested if suggested is not None else para.style)
            self.table.setCellWidget(i, 3, combo)
            self._combos.append(combo)
        self.table.resizeColumnsToContents()
        box.addWidget(self.table)

        all_on = QPushButton("全部採用")
        all_off = QPushButton("全部不採")
        all_on.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        all_off.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton(all_on, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(all_off, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_confirm)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def _set_all(self, state) -> None:
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(state)

    def _assignments(self) -> dict:
        """勾選且異於現行樣式的 {para_idx: 樣式名}（批次改派載荷）。"""
        out = {}
        for i, para in enumerate(self._doc.paragraphs):
            if self.table.item(i, 0).checkState() != Qt.CheckState.Checked:
                continue
            style = self._combos[i].currentText()
            if style != para.style:
                out[i] = style
        return out

    def _on_confirm(self) -> None:
        err = self._on_apply(self._assignments())
        if err:
            self._notice.setText(err)  # 套用錯誤：留在對話框修正
            return
        self.accept()
