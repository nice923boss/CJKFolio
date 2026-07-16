"""AI 設定檔層（Sprint 56，§4.4 LLM 介接）：Base URL／API Key／Model 三欄位。

金鑰紅線（§4.4／GAPS #6）：
- 預設一律空值；設定只存本機檔（慣例路徑 local/ai-config.local.json，local/
  已入 .gitignore），開源程式碼與公開文件零金鑰。
- 錯誤訊息不回帶欄位值（金鑰不入 log）。
- 未設定（缺檔＝空值）不擋流程：AI 為選配增強，核心排版與手動指派完全可用。

面板 UI（真視窗三欄位）屬 Phase 2 編輯器工程；本層為其資料面。
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

_FIELDS = ("base_url", "api_key", "model")


class AiConfigError(ValueError):
    """設定檔存在但無法解析（壞 JSON／欄位型別不符）。"""


@dataclass(frozen=True)
class AiConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""


def load_ai_config(path) -> AiConfig:
    """讀取本機 AI 設定：缺檔回全空預設（不擋流程）；壞檔明確錯誤（不沉默）。

    未知鍵容忍（向前相容）；缺鍵補空字串。錯誤訊息只含欄位名與型別，
    不回帶欄位值（金鑰紅線）。
    """
    p = Path(path)
    if not p.exists():
        return AiConfig()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise AiConfigError(f"讀取 AI 設定檔失敗 {p}：{e}") from e
    if not isinstance(data, dict):
        raise AiConfigError(f"AI 設定檔 {p} 需為 JSON 物件")
    values = {}
    for key in _FIELDS:
        v = data.get(key, "")
        if not isinstance(v, str):
            raise AiConfigError(
                f"AI 設定檔 {p} 欄位 {key} 需為字串（得到 {type(v).__name__}）"
            )
        values[key] = v
    return AiConfig(**values)


def save_ai_config(cfg: AiConfig, path) -> None:
    """寫入本機 AI 設定（建立父目錄；只序列化三欄位）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
