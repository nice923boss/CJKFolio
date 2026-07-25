"""成品尺寸對話框（Sprint 140 甲）：收新的 trim size 與「版心是否跟著重算」。

兩種語意都做（Owner 決定），以勾選框切換：

- 勾選（預設）＝換開本：邊距不動，紙張增減換算成版心行列數增減，內文重排、頁數會變。
- 不勾＝只換紙張：一個字都不重排；原本齊邊的版心在較小的成品上會落到紙外，
  溢出項由呼叫端據實列出（不擋：改小開本本來就可能溢出）。

換算與判定全在 cjkfolio.page_size（Qt 無關、pytest 已驗），本對話框只收數值與旗標。
"""
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
)

from cjkfolio.page_size import MAX_PAGE_MM

#: 成品尺寸下限（mm）：純層只擋「大於 0」，此處給實務下限，免手滑打出 0.01mm 的紙。
MIN_PAGE_MM = 1.0


def _mm_spin(value: float) -> QDoubleSpinBox:
    """mm 數值欄：小數兩位（模版 JSON 的 page.width_mm 即記到此精度）。"""
    spin = QDoubleSpinBox()
    spin.setRange(MIN_PAGE_MM, MAX_PAGE_MM)
    spin.setDecimals(2)
    spin.setSingleStep(1.0)
    spin.setSuffix(" mm")
    spin.setValue(float(value))
    return spin


class PageSizeDialog(QDialog):
    """改成品尺寸：寬高（mm）＋是否同時重算版心行列數。"""

    def __init__(self, template, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("成品尺寸（trim size）")
        self._width = _mm_spin(template.page_width_mm)
        self._height = _mm_spin(template.page_height_mm)

        self._refit = QCheckBox("同時重算版心行列數（維持邊距）")
        self._refit.setChecked(True)  # 換開本的常態：紙變了，版心跟著變才是換開本

        self._notice = QLabel(
            f"目前 {template.page_width_mm:g} × {template.page_height_mm:g} mm。"
            "勾選＝邊距原封不動，把紙張的增減換算成每行字數與每頁行數，內文重排、"
            "頁數會變；不勾＝只換紙張，一個字都不重排。\n"
            "兩種都不搬動頁腳基線這類絕對座標，也不動置入圖與文字框的位置；"
            "改完若有項目落到成品外，會據實列出。\n"
            "成品尺寸屬模版設定，不隨文件檔儲存，要留存請用「樣式 > 另存模版…」。")
        self._notice.setStyleSheet("color:#555; font-size:11px;")
        self._notice.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow("成品寬", self._width)
        form.addRow("成品高", self._height)
        form.addRow("", self._refit)
        form.addRow(self._notice)
        form.addRow(buttons)

    def values(self) -> dict:
        """收好的尺寸與旗標（鍵名對齊 session.update_page_size 的參數）。"""
        return {
            "width_mm": self._width.value(),
            "height_mm": self._height.value(),
            "refit_grid": self._refit.isChecked(),
        }
