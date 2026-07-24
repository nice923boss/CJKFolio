"""文件資訊對話框（Sprint 128：丙2，唯讀呈現）。

呈現 document_stats 的 DocStats：總字數、段數、頁數摘要＋段落樣式用量表。純顯示，
不改文件；統計計算全在 info_actions.document_stats（純函式離屏可驗）。
"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class DocInfoDialog(QDialog):
    """唯讀文件資訊：總字數／段數／頁數摘要＋段落樣式用量表。"""

    def __init__(self, stats, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("文件資訊")
        self._stats = stats

        box = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("總字數", QLabel(str(stats.total_chars)))
        form.addRow("段數", QLabel(str(stats.paragraph_count)))
        form.addRow("頁數", QLabel(str(stats.page_count)))
        box.addLayout(form)

        box.addWidget(QLabel("段落樣式用量"))
        table = QTableWidget(len(stats.style_usage), 2)
        table.setHorizontalHeaderLabels(["段落樣式", "段數"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, (name, count) in enumerate(stats.style_usage):
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(str(count)))
        table.resizeColumnsToContents()
        self._table = table
        box.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        box.addWidget(buttons)
