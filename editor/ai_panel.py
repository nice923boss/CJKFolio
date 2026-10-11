"""AI 設定面板（Sprint 63，§4.4「AI 設定面板」UI 半邊；資料面＝cjkfolio.ai_config）。

金鑰紅線（§4.4／GAPS #6）：
- API Key 欄遮罩顯示（QLineEdit Password）；面板不把欄位值寫入 statusBar／log／
  例外訊息（AiConfigError 本就不含值）。
- 預設空值＝停用 AI（選配增強，核心排版不依賴）；儲存只到本機
  local/ai-config.local.json（local/ 已入 .gitignore）。
- 載入／儲存錯誤以面板內嵌警示列顯示（非 modal，離屏可驗；訊息不含欄位值）。

測試連線（Sprint 149）：以面板上**目前填的值**（未儲存也可）送一則極短請求，
背景執行緒跑、結果顯示在警示列（綠＝通、紅＝不通且白話說明原因）。換了金鑰
不必跑一次全書指派等十分鐘才知道對不對。

輸出上限（Sprint 149）：每次請求的 max_tokens，0＝自動依段數推算。推理型模型
的推理量因模型而異，自動值不夠（回應一再被截斷）時在這裡調高，不必改程式。
"""
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from cjkfolio.ai_config import AiConfig, AiConfigError, load_ai_config, save_ai_config
from cjkfolio.ai_style import AiConfigProblem, check_connection

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "local" / "ai-config.local.json"
)


class _CheckThread(QThread):
    """背景跑 check_connection（最長等 60 秒，不凍面板）。"""

    finished_with = Signal(bool, str)

    def __init__(self, config: AiConfig, check, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._check = check

    def run(self) -> None:
        try:
            self.finished_with.emit(True, self._check(self._config))
        except AiConfigProblem as e:
            self.finished_with.emit(False, str(e))
        except Exception as e:  # noqa: BLE001（任何失敗都回面板顯示，不讓執行緒默死）
            self.finished_with.emit(False, f"測試失敗：{e}")


class AiConfigDialog(QDialog):
    """設定面板：載入既有本機設定 → 編輯 → 儲存（僅本機檔）。

    每分鐘請求上限（Sprint 143）做成欄位而非寫死：限額因供應商而異，
    值不對就會撞 503／429（那批段落降級成維持原樣式）。
    """

    def __init__(self, parent=None, config_path=DEFAULT_CONFIG_PATH,
                 check=check_connection) -> None:
        super().__init__(parent)
        self._check = check  # 注入＝離屏可驗（不外連）
        self._check_thread = None
        self.setWindowTitle("AI 設定（OpenAI 相容，只存本機）")
        self._path = Path(config_path)
        load_error = ""
        try:
            cfg = load_ai_config(self._path)
        except AiConfigError as e:
            cfg = AiConfig()
            load_error = f"既有設定檔無法解析，以空值開啟：{e}"

        self._base_url = QLineEdit(cfg.base_url)
        self._base_url.setPlaceholderText("例：http://localhost:8000/v1（空＝停用 AI）")
        self._api_key = QLineEdit(cfg.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)  # 金鑰遮罩（紅線）
        self._api_key.setPlaceholderText("只存本機 local/，不入 repo 與 log")
        self._model = QLineEdit(cfg.model)
        self._model.setPlaceholderText("例：qwen3-32b")
        self._rpm = QSpinBox()
        self._rpm.setRange(0, 1000)
        self._rpm.setValue(cfg.requests_per_minute)
        self._rpm.setSuffix(" 次／分")
        self._rpm.setSpecialValueText("不節流")  # 0＝自架 endpoint 無限額
        self._rpm.setToolTip(
            "送給 AI 的請求每分鐘不超過此數；撞到服務端限額（503／429）會自動退避重試。"
            "0＝不節流。")
        self._max_out = QSpinBox()
        self._max_out.setRange(0, 200000)
        self._max_out.setSingleStep(1000)
        self._max_out.setValue(cfg.max_output_tokens)
        self._max_out.setSuffix(" tokens")
        self._max_out.setSpecialValueText("自動（依段數推算）")
        self._max_out.setToolTip(
            "每次請求 AI 最多能回多少 tokens（含推理型模型的思考過程）。"
            "0＝自動依該批段數推算；回應一再被截斷時可調高。")
        self._notice = QLabel(load_error)
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)

        form = QFormLayout(self)
        form.addRow("Base URL", self._base_url)
        form.addRow("API Key", self._api_key)
        form.addRow("Model", self._model)
        form.addRow("每分鐘請求上限", self._rpm)
        form.addRow("輸出上限", self._max_out)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._test = QPushButton("測試連線")
        self._test.setToolTip("用目前填的值送一則極短請求，確認 Base URL、API Key、Model 能通")
        self._test.clicked.connect(self._on_test)
        buttons.addButton(self._test, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        form.addRow(self._notice)

    def current_config(self) -> AiConfig:
        return AiConfig(
            base_url=self._base_url.text().strip(),
            api_key=self._api_key.text().strip(),
            model=self._model.text().strip(),
            requests_per_minute=self._rpm.value(),
            max_output_tokens=self._max_out.value(),
        )

    def _on_test(self) -> None:
        """以目前欄位值測試連線（背景執行緒；結果寫警示列，不含金鑰值）。"""
        if self._check_thread is not None:
            return
        self._test.setEnabled(False)
        self._notice.setStyleSheet("color:#666; font-size:11px;")
        self._notice.setText("測試中…（最長約 60 秒）")
        thread = _CheckThread(self.current_config(), self._check, parent=self)
        thread.finished_with.connect(self._on_test_done)
        self._check_thread = thread
        thread.start()

    def _on_test_done(self, ok: bool, message: str) -> None:
        thread = self._check_thread
        self._check_thread = None
        if thread is not None:
            thread.wait()
            thread.deleteLater()
        self._test.setEnabled(True)
        self._notice.setStyleSheet(
            f"color:{'#060' if ok else '#b00'}; font-size:11px;")
        self._notice.setText(message)

    def _wait_check(self, timeout_ms: int = 60000) -> None:
        """等測試連線跑完並派送結果（離屏驗證用；真視窗由事件圈派送）。"""
        thread = self._check_thread
        if thread is not None:
            thread.wait(timeout_ms)
            QCoreApplication.processEvents()

    def done(self, result: int) -> None:
        """關面板前收掉測試執行緒（避免 QThread 執行中被銷毀）。"""
        if self._check_thread is not None:
            self._check_thread.wait()
        super().done(result)

    def _on_save(self) -> None:
        """儲存到本機設定檔；失敗顯示於警示列（訊息不含欄位值）。"""
        try:
            save_ai_config(self.current_config(), self._path)
        except OSError as e:
            self._notice.setText(f"儲存失敗：{e}")
            return
        self.accept()
