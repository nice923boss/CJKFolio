"""尋找／取代對話框（Sprint 128：丙1，非模態）。

非模態（show 而非 exec）：檢索時仍可捲動畫布、繼續看版面，符合編輯器慣例。
本類只收欄位與發射訊號（find_requested／replace_requested／replace_all_requested），
命中計算、頁定位、取代全在 FindActionsMixin（純函式離屏可驗）。狀態由 set_status
回填到對話框內的標籤。
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)


class FindDialog(QDialog):
    """尋找欄＋取代欄＋區分大小寫＋找下一個／取代／全部取代／關閉（非模態）。"""

    find_requested = Signal()
    replace_requested = Signal()
    replace_all_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("尋找／取代")
        self.setModal(False)

        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText("要尋找的文字")
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("取代為（可留空＝刪除命中）")
        self._case = QCheckBox("區分大小寫")

        find_btn = QPushButton("找下一個")
        find_btn.setDefault(True)
        replace_btn = QPushButton("取代")
        replace_all_btn = QPushButton("全部取代")
        close_btn = QPushButton("關閉")

        find_btn.clicked.connect(lambda: self.find_requested.emit())
        replace_btn.clicked.connect(lambda: self.replace_requested.emit())
        replace_all_btn.clicked.connect(lambda: self.replace_all_requested.emit())
        close_btn.clicked.connect(self.close)
        self._query_edit.returnPressed.connect(lambda: self.find_requested.emit())

        self._status = QLabel("")
        self._status.setStyleSheet("color:#555;")
        self._status.setWordWrap(True)

        grid = QGridLayout(self)
        grid.addWidget(QLabel("尋找"), 0, 0)
        grid.addWidget(self._query_edit, 0, 1)
        grid.addWidget(find_btn, 0, 2)
        grid.addWidget(QLabel("取代為"), 1, 0)
        grid.addWidget(self._replace_edit, 1, 1)
        grid.addWidget(replace_btn, 1, 2)
        grid.addWidget(self._case, 2, 1)
        grid.addWidget(replace_all_btn, 2, 2)
        grid.addWidget(self._status, 3, 0, 1, 2)
        grid.addWidget(close_btn, 3, 2)

    def query(self) -> str:
        return self._query_edit.text()

    def replacement(self) -> str:
        return self._replace_edit.text()

    def case_sensitive(self) -> bool:
        return self._case.isChecked()

    def set_status(self, message: str) -> None:
        self._status.setText(message)

    def focus_query(self, *, replace: bool = False) -> None:
        """聚焦輸入欄：Ctrl+H 起手聚焦取代欄，Ctrl+F 聚焦尋找欄。"""
        edit = self._replace_edit if replace else self._query_edit
        edit.setFocus()
        edit.selectAll()
