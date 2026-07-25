"""轉存 PDF 選項對話框（Sprint 127：乙4 匯出 PDF 介面）。

只暴露 export_pdf 已驗且對印前送印必要的選項：輸出路徑、輸出形態（X-1a／X-4／
一般 PDF）、輸出 ICC（X-4 強制嵌 DestOutputProfile）、首頁書頁碼、頁腳頁碼、裁切
標記、RGB 影像轉 CMYK 與其 rendering intent（Sprint 139）。判定與寫檔全在
cjkfolio.pdf_writer.export_pdf（pytest 已驗），本對話框只收選項不做匯出。

色彩轉換的目標描述檔就是「輸出 ICC」那一份，故該欄空著時勾選框停用：沒有描述檔
就沒有可據以轉換的目標（本產品不做無色彩管理的換算）。

一般 PDF（Sprint 137）排在最後，預設索引 0 仍是 X-1a：送印是本產品的主用途，
保留全彩是例外，例外不搶預設。

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
        for key in ("x-1a", "x-4", "none"):
            self._pdfx.addItem(PDFX_PROFILES[key].label, key)
        self._pdfx.currentIndexChanged.connect(self._sync_icc_enabled)

        self._icc_edit = QLineEdit()
        self._icc_edit.setPlaceholderText(
            "PDF/X-4 須嵌 CMYK 輸出 ICC；X-1a 免（registry 識別）")
        self._icc_edit.textChanged.connect(self._sync_convert_enabled)
        self._icc_browse = QPushButton("瀏覽…")
        self._icc_browse.clicked.connect(self._pick_icc)

        # 色彩轉換（Sprint 139）：目標描述檔＝上方那份輸出 ICC，故沒選 ICC 就沒得轉
        self._convert = QCheckBox("RGB 影像依上方 ICC 轉 CMYK（灰階與 CMYK 來源不動）")
        self._convert.toggled.connect(self._sync_convert_enabled)
        self._intent = QComboBox()
        self._intent.addItem("相對色度（預設）", "relative")
        self._intent.addItem("感知（全域壓縮色域）", "perceptual")

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
        form.addRow("", self._convert)
        form.addRow("轉換 intent", self._intent)
        form.addRow(self._notice)
        form.addRow(buttons)
        self._sync_icc_enabled()

    def _sync_icc_enabled(self) -> None:
        """PDF/X 兩形態都可選輸出 ICC；一般 PDF 停用（無 OutputIntent 可嵌）。

        X-4 是強制嵌，X-1a 是選配（registry 識別免嵌），但 X-1a 選了也會嵌，
        且那份描述檔同時是色彩轉換的目標（Sprint 139），故不再停用該列。
        一般 PDF 就地寫明不可送印：選單標籤之外再說一次，避免為了保留彩色而
        誤把送印稿存成非 PDF/X。
        """
        key = self._pdfx.currentData()
        self._icc_edit.setEnabled(key != "none")
        self._icc_browse.setEnabled(key != "none")
        self._notice.setText(
            "一般 PDF 不是 PDF/X：無 OutputIntent 與 GTS 識別鍵，置入的 RGB 彩色影像"
            "原樣保留，但拿去送印廠會被退件。要送印請改選 X-1a 或 X-4。"
            if key == "none" else "")
        self._sync_convert_enabled()

    def _sync_convert_enabled(self) -> None:
        """沒選 ICC 就沒有轉換目標：勾選框停用並取消勾，intent 隨勾選啟用。

        停用時一併取消勾，避免留下「勾了卻不生效」的狀態（options 也會再擋一次）。
        """
        ready = bool(self._icc_edit.text().strip()) and self._icc_edit.isEnabled()
        self._convert.setEnabled(ready)
        if not ready:
            self._convert.setChecked(False)
        self._intent.setEnabled(self._convert.isChecked())

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

        icc_profile 在兩種 PDF/X 形態都帶入（X-4 強制嵌、X-1a 選配），一般 PDF
        不帶（無 OutputIntent 可嵌，export_pdf 會拒收）。
        color_convert 以「真的有描述檔」為前提再判一次：UI 已停用，這裡是第二道，
        因為送進 export_pdf 的是這份 dict，不是使用者看到的畫面。
        """
        icc = self._icc_edit.text().strip()
        pdfx = self._pdfx.currentData()
        profile = Path(icc) if (icc and pdfx != "none") else None
        return {
            "out_path": Path(self._path_edit.text().strip()),
            "pdfx": pdfx,
            "icc_profile": profile,
            "first_page": self._first_page.value(),
            "footer": self._footer.isChecked(),
            "crop_marks": self._crop.isChecked(),
            "color_convert": self._convert.isChecked() and profile is not None,
            "rendering_intent": self._intent.currentData(),
        }
