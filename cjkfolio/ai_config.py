"""AI 設定檔層（Sprint 56，§4.4 LLM 介接）：Base URL／API Key／Model 與送出速率上限。

金鑰紅線（§4.4／GAPS #6）：
- 預設一律空值；設定只存本機檔（慣例路徑 local/ai-config.local.json，local/
  已入 .gitignore），開源程式碼與公開文件零金鑰。
- 錯誤訊息不回帶欄位值（金鑰不入 log）。
- 未設定（缺檔＝空值）不擋流程：AI 為選配增強，核心排版與手動指派完全可用。

requests_per_minute（Sprint 143）：每分鐘送出上限，服務端的限額因供應商而異，
故做成設定而非寫死常數（0＝不節流，給無限額的自架 endpoint）。

max_output_tokens（Sprint 149）：每次請求的輸出上限（max_tokens）。0＝自動，
依該批段數推算並為推理預留（見 ai_style._max_tokens）；推理量因模型而異，
自動值不夠時可在設定面板手動調高，不必改程式。

面板 UI（真視窗欄位）屬 Phase 2 編輯器工程；本層為其資料面。
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

# 欄位 → 型別（載入守門用）；預設值以 AiConfig 的欄位預設為唯一真相。
_FIELDS = {"base_url": str, "api_key": str, "model": str, "requests_per_minute": int,
           "max_output_tokens": int}
_TYPE_NAMES = {str: "字串", int: "整數"}


class AiConfigError(ValueError):
    """設定檔存在但無法解析（壞 JSON／欄位型別不符）。"""


@dataclass(frozen=True)
class AiConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    requests_per_minute: int = 40
    max_output_tokens: int = 0


def load_ai_config(path) -> AiConfig:
    """讀取本機 AI 設定：缺檔回全空預設（不擋流程）；壞檔明確錯誤（不沉默）。

    未知鍵容忍（向前相容）；缺鍵補該欄位預設（Sprint 143 前寫的設定檔沒有
    requests_per_minute，補預設 40 而非 0，否則舊檔會靜默變成不節流）。
    錯誤訊息只含欄位名與型別，不回帶欄位值（金鑰紅線）。
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
    defaults = AiConfig()
    values = {}
    for key, want in _FIELDS.items():
        v = data.get(key, getattr(defaults, key))
        # 真布林是 int 的子類，True 會被當成每分鐘 1 次；型別一律取精確相等
        if type(v) is not want:
            raise AiConfigError(
                f"AI 設定檔 {p} 欄位 {key} 需為{_TYPE_NAMES[want]}"
                f"（得到 {type(v).__name__}）"
            )
        values[key] = v
    if values["requests_per_minute"] < 0:
        raise AiConfigError(
            f"AI 設定檔 {p} 欄位 requests_per_minute 需為 ≥0 整數（0＝不節流）")
    if values["max_output_tokens"] < 0:
        raise AiConfigError(
            f"AI 設定檔 {p} 欄位 max_output_tokens 需為 ≥0 整數（0＝自動）")
    return AiConfig(**values)


def save_ai_config(cfg: AiConfig, path) -> None:
    """寫入本機 AI 設定（建立父目錄；只序列化 AiConfig 宣告的欄位）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
