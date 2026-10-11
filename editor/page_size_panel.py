"""成品尺寸對話框（Sprint 140 甲；Sprint 157 加紙張下拉、含出血顯示、三種換法）。

紙張下拉列台灣書籍常用開本與 ISO 尺寸，選了即填入寬高；手改寬高時下拉自動切到相符的
預設（同尺寸取第一個，如 25 開與 A5 同為 148×210），不符則切「自訂」。
「顯示含出血尺寸」只影響顯示（四邊各加 3mm），收回的仍是成品尺寸。

三種換法（Owner 決定，預設等比）：

- 整版等比縮放（預設）：字級、字距、行距、邊距、頁腳、圖框與文字框同乘一倍率，行列數與
  頁數不變；寬高比例不同時取較小倍率，多出的空間平均補到邊距（cjkfolio.page_scale）。
- 維持字級，重算行列：邊距不動，紙張增減換算成版心行列數增減，內文重排、頁數會變。
- 只換紙張：一個字都不重排；溢出項由呼叫端據實列出（不擋：改小開本本來就可能溢出）。

換算與判定全在 cjkfolio.page_scale／page_size（Qt 無關、pytest 已驗），本對話框只收數值與模式。
"""
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from cjkfolio.page_size import MAX_PAGE_MM
from cjkfolio.press_marks import BLEED_MM

#: 成品尺寸下限（mm）：純層只擋「大於 0」，此處給實務下限，免手滑打出 0.01mm 的紙。
MIN_PAGE_MM = 1.0

#: 紙張預設（名稱, 寬 mm, 高 mm）：台灣書籍常用開本在前，ISO 在後。
PAPER_PRESETS = (
    ("25 開", 148.0, 210.0),
    ("18 開", 170.0, 230.0),
    ("32 開", 130.0, 185.0),
    ("菊 8 開", 210.0, 285.0),
    ("A5", 148.0, 210.0),
    ("B5", 182.0, 257.0),
    ("A4", 210.0, 297.0),
    ("B6", 128.0, 182.0),
)
CUSTOM_LABEL = "自訂"

#: 三種換法（values()["mode"] 值, 選項文字）；第一項為預設。
SIZE_MODES = (
    ("scale", "整版等比縮放（字級、邊距、圖文框一起放大縮小，頁數不變）"),
    ("refit", "維持字級，重算每行字數與每頁行數（頁數會變）"),
    ("paper", "只換紙張（一個字都不重排）"),
)


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
    """改成品尺寸：紙張預設或自訂寬高（mm）＋三種換法擇一。"""

    def __init__(self, template, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("成品尺寸（trim size）")
        self._width = _mm_spin(template.page_width_mm)
        self._height = _mm_spin(template.page_height_mm)
        self._paper = QComboBox()
        for name, w, h in PAPER_PRESETS:
            self._paper.addItem(f"{name}（{w:g} × {h:g} mm）", (w, h))
        self._paper.addItem(CUSTOM_LABEL, None)
        self._sync_paper()
        self._paper.activated.connect(self._apply_paper)
        self._width.valueChanged.connect(self._on_size_changed)
        self._height.valueChanged.connect(self._on_size_changed)

        self._show_bleed = QCheckBox(f"顯示含出血尺寸（四邊各加 {BLEED_MM:g}mm）")
        self._bleed_label = QLabel()
        self._bleed_label.setStyleSheet("color:#b00000;")
        self._show_bleed.toggled.connect(self._update_bleed_label)
        self._update_bleed_label()

        self._modes = QButtonGroup(self)
        mode_box = QVBoxLayout()
        for i, (key, label) in enumerate(SIZE_MODES):
            radio = QRadioButton(label)
            radio.setProperty("mode", key)
            radio.setChecked(i == 0)
            self._modes.addButton(radio, i)
            mode_box.addWidget(radio)

        self._notice = QLabel(
            f"目前 {template.page_width_mm:g} × {template.page_height_mm:g} mm。"
            "等比縮放時寬高比例不同，取較小的倍率，多出的空間平均補到邊距；"
            "滿版圖會重新鋪滿頁面與出血，不露白邊。\n"
            "重算行列與只換紙張都不搬動頁腳基線、置入圖與文字框的位置；"
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
        form.addRow("紙張", self._paper)
        form.addRow("成品寬", self._width)
        form.addRow("成品高", self._height)
        form.addRow("", self._show_bleed)
        form.addRow("", self._bleed_label)
        form.addRow("換法", mode_box)
        form.addRow(self._notice)
        form.addRow(buttons)

    def _apply_paper(self, index: int) -> None:
        size = self._paper.itemData(index)
        if size is None:  # 自訂：寬高留給使用者改
            return
        self._width.setValue(size[0])
        self._height.setValue(size[1])

    def _sync_paper(self) -> None:
        """下拉跟著寬高走：相符取第一個預設，不符切自訂。"""
        size = (round(self._width.value(), 2), round(self._height.value(), 2))
        index = next((i for i, (_, w, h) in enumerate(PAPER_PRESETS) if (w, h) == size),
                     len(PAPER_PRESETS))
        if self._paper.itemData(self._paper.currentIndex()) != size:
            self._paper.setCurrentIndex(index)

    def _on_size_changed(self) -> None:
        self._sync_paper()
        self._update_bleed_label()

    def _update_bleed_label(self) -> None:
        on = self._show_bleed.isChecked()
        self._bleed_label.setVisible(on)
        b = 2 * BLEED_MM
        self._bleed_label.setText(
            f"含出血 {self._width.value() + b:g} × {self._height.value() + b:g} mm"
            "（僅供參考，套用的是成品尺寸）")

    def values(self) -> dict:
        """收好的尺寸與換法（mode：scale／refit／paper，見 SIZE_MODES）。"""
        return {
            "width_mm": self._width.value(),
            "height_mm": self._height.value(),
            "mode": self._modes.checkedButton().property("mode"),
        }
