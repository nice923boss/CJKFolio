"""轉存 PDF 選項對話框（Sprint 127：乙4 匯出 PDF 介面）。

只暴露 export_pdf 已驗且對印前送印必要的選項：輸出路徑、PDF/X 形態（X-1a／X-4）、
輸出 ICC（X-4 強制嵌 DestOutputProfile）、首頁書頁碼、頁腳頁碼、裁切標記。判定與
寫檔全在 cjkfolio.pdf_writer.export_pdf（pytest 已驗），本對話框只收選項不做匯出。

印前標記與套準單 K（press_marks／registration_single_k）為耦合的一組，且印前標記
為自擬配置（非標準控制條），v1 介面未納入（GAPS #82），仍可經 CLI 使用。
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from cjkfolio.pdf_writer import PDFX_PROFILES


def _browse_row(edit: QLineEdit, button: QPushButton) -> QWidget:
    """輸入欄＋瀏覽鈕併成一列（輸出路徑與 ICC 兩處共用）。"""
    row = QWidget()
    box = QHBoxLayout(row)
    box.setContentsMargins(0, 0, 0, 0)
    box.addWidget(edit)
    box.addWidget(button)
    return row


class ExportDialog(QDialog):
    """收轉存選項；accept 前擋輸出路徑空與 X-4 未選 ICC（不默默降回 X-1a）。"""

    def __init__(self, default_path, first_page: int = 1, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("轉存為 PDF（印前成品）")

        self._path_edit = QLineEdit(str(default_path))
        path_browse = QPushButton("瀏覽…")
        path_browse.clicked.connect(self._pick_path)

        self._pdfx = QComboBox()
        for key in ("x-1a", "x-4"):
            self._pdfx.addItem(PDFX_PROFILES[key].label, key)
        self._pdfx.currentIndexChanged.connect(self._sync_icc_enabled)

        self._icc_edit = QLineEdit()
        self._icc_edit.setPlaceholderText(
            "PDF/X-4 須嵌 CMYK 輸出 ICC；X-1a 免（registry 識別）")
        self._icc_browse = QPushButton("瀏覽…")
        self._icc_browse.clicked.connect(self._pick_icc)

        self._first_page = QSpinBox()
        self._first_page.setRange(1, 9999)
        self._first_page.setValue(first_page)

        self._footer = QCheckBox("輸出頁腳頁碼")
        self._footer.setChecked(True)
        self._crop = QCheckBox("裁切標記（MediaBox 外擴、BleedBox＝trim＋出血）")

        self._notice = QLabel("")
        self._notice.setStyleSheet("color:#b00000;")
        self._notice.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow("輸出路徑", _browse_row(self._path_edit, path_browse))
        form.addRow("PDF/X 形態", self._pdfx)
        form.addRow("輸出 ICC", _browse_row(self._icc_edit, self._icc_browse))
        form.addRow("首頁書頁碼", self._first_page)
        form.addRow("", self._footer)
        form.addRow("", self._crop)
        form.addRow(self._notice)
        form.addRow(buttons)
        self._sync_icc_enabled()

    def _sync_icc_enabled(self) -> None:
        """X-4 才需輸出 ICC；X-1a 停用 ICC 列避免誤導（registry 免嵌）。"""
        need = self._pdfx.currentData() == "x-4"
        self._icc_edit.setEnabled(need)
        self._icc_browse.setEnabled(need)

    def _pick_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "轉存為 PDF", self._path_edit.text(), "PDF (*.pdf)")
        if path:
            self._path_edit.setText(path)

    def _pick_icc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 CMYK 輸出色彩描述檔（PDF/X-4 須嵌）", "",
            "ICC 色彩描述檔 (*.icc *.icm);;所有檔案 (*)")
        if path:
            self._icc_edit.setText(path)

    def _on_accept(self) -> None:
        """擋兩種缺項後才收下：空路徑、X-4 未選 ICC（都留在對話框並據實說明）。"""
        if not self._path_edit.text().strip():
            self._notice.setText("請指定輸出路徑")
            return
        if self._pdfx.currentData() == "x-4" and not self._icc_edit.text().strip():
            self._notice.setText(
                "PDF/X-4 須嵌 CMYK 輸出 ICC，請選輸出色彩描述檔（不默默改存 X-1a）")
            return
        self.accept()

    def options(self) -> dict:
        """收好的選項：out_path 由呼叫端強制 .pdf 後綴，其餘鍵直接餵 export_pdf。

        icc_profile 僅在 X-4 時帶入（X-1a 走 registry 識別免嵌，UI 亦停用該欄）。
        """
        icc = self._icc_edit.text().strip()
        pdfx = self._pdfx.currentData()
        return {
            "out_path": Path(self._path_edit.text().strip()),
            "pdfx": pdfx,
            "icc_profile": Path(icc) if (icc and pdfx == "x-4") else None,
            "first_page": self._first_page.value(),
            "footer": self._footer.isChecked(),
            "crop_marks": self._crop.isChecked(),
        }
