"""印前設定對話框（Sprint 140 乙）：總墨量上限與 PDF/X 形態的本機預設值。

資料面＝cjkfolio.press_config（缺檔回 §9 保守預設、壞檔明確錯誤，pytest 已驗）；
本對話框只做 round-trip 與錯誤呈現，同 AiConfigDialog 慣例（載入失敗以內嵌警示列
顯示、以預設值開啟，不擋流程）。

**存的是預設值，不是最終值。** 轉存對話框每次開啟時以本設定起始，仍可就該次匯出改；
真正的判定與寫檔一律在 pdf_writer.export_pdf。總墨量上限是印廠條件（非 PDF/X 條款），
只影響油墨警告的門檻，不改任何寫出的位元。
"""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
)

from cjkfolio.pdfx_meta import PDFX_PROFILES
from cjkfolio.press_config import (
    DEFAULT_PATH,
    MAX_POSSIBLE_TAC,
    PressConfig,
    PressConfigError,
    load_press_config,
    save_press_config,
)


class PressConfigDialog(QDialog):
    """兩欄位設定面板：載入既有本機設定 → 編輯 → 儲存（僅本機檔）。"""

    def __init__(self, parent=None, config_path=DEFAULT_PATH) -> None:
        super().__init__(parent)
        self.setWindowTitle("印前設定（總墨量上限與 PDF/X 形態，只存本機）")
        self._path = config_path
        load_error = ""
        try:
            cfg = load_press_config(self._path)
        except PressConfigError as e:
            cfg = PressConfig()
            load_error = f"既有設定檔無法解析，以預設值開啟：{e}"

        self._max_tac = QDoubleSpinBox()
        self._max_tac.setRange(1.0, MAX_POSSIBLE_TAC)  # 上限＝四個色版各 100%
        self._max_tac.setDecimals(0)  # 印廠給的是整數百分比（§9 320〜340）
        self._max_tac.setSingleStep(10.0)
        self._max_tac.setSuffix(" %")
        self._max_tac.setValue(cfg.max_tac)

        self._pdfx = QComboBox()
        for key in ("x-1a", "x-4", "none"):  # 排序同轉存對話框
            self._pdfx.addItem(PDFX_PROFILES[key].label, key)
        self._pdfx.setCurrentIndex(self._pdfx.findData(cfg.pdfx))

        hint = QLabel(
            "這兩項都是印廠條件，不是本產品能替你決定的事：總墨量上限取決於紙張吸墨與"
            "乾燥能力（§9 給 320〜340% 的區間，預設取保守下限 320），PDF/X 形態取決於"
            "印廠收哪一種（X-1a 相容性最廣，X-4 較新且強制嵌輸出 ICC）。\n"
            "此處存的是**預設值**：轉存 PDF 對話框每次以這裡的值起始，仍可就該次匯出"
            "改動。總墨量上限只影響油墨警告的門檻，不改任何寫出的位元。\n"
            "輸出 ICC 的路徑不在此設定，選 X-4 時仍須於轉存對話框指定描述檔。")
        hint.setStyleSheet("color:#555; font-size:11px;")
        hint.setWordWrap(True)
        self._notice = QLabel(load_error)
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow("總墨量上限（TAC）", self._max_tac)
        form.addRow("PDF/X 形態", self._pdfx)
        form.addRow(hint)
        form.addRow(buttons)
        form.addRow(self._notice)

    def current_config(self) -> PressConfig:
        return PressConfig(max_tac=self._max_tac.value(),
                           pdfx=self._pdfx.currentData())

    def _on_save(self) -> None:
        """儲存到本機設定檔；失敗顯示於警示列（值域守門在 save_press_config）。"""
        try:
            save_press_config(self.current_config(), self._path)
        except (PressConfigError, OSError) as e:
            self._notice.setText(f"儲存失敗：{e}")
            return
        self.accept()
