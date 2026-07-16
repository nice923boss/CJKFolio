"""AI 設定面板（Sprint 63，§4.4「AI 設定面板」UI 半邊；資料面＝cjkfolio.ai_config）。

金鑰紅線（§4.4／GAPS #6）：
- API Key 欄遮罩顯示（QLineEdit Password）；面板不把欄位值寫入 statusBar／log／
  例外訊息（AiConfigError 本就不含值）。
- 預設空值＝停用 AI（選配增強，核心排版不依賴）；儲存只到本機
  local/ai-config.local.json（local/ 已入 .gitignore）。
- 載入／儲存錯誤以面板內嵌警示列顯示（非 modal，離屏可驗；訊息不含欄位值）。
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from cjkfolio.ai_config import AiConfig, AiConfigError, load_ai_config, save_ai_config

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "local" / "ai-config.local.json"
)


class AiConfigDialog(QDialog):
    """三欄位設定面板：載入既有本機設定 → 編輯 → 儲存（僅本機檔）。"""

    def __init__(self, parent=None, config_path=DEFAULT_CONFIG_PATH) -> None:
        super().__init__(parent)
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
        self._notice = QLabel(load_error)
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)

        form = QFormLayout(self)
        form.addRow("Base URL", self._base_url)
        form.addRow("API Key", self._api_key)
        form.addRow("Model", self._model)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        form.addRow(self._notice)

    def current_config(self) -> AiConfig:
        return AiConfig(
            base_url=self._base_url.text().strip(),
            api_key=self._api_key.text().strip(),
            model=self._model.text().strip(),
        )

    def _on_save(self) -> None:
        """儲存到本機設定檔；失敗顯示於警示列（訊息不含欄位值）。"""
        try:
            save_ai_config(self.current_config(), self._path)
        except OSError as e:
            self._notice.setText(f"儲存失敗：{e}")
            return
        self.accept()
