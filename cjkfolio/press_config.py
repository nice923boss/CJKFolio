"""印前設定層（Sprint 140）：總墨量上限與 PDF/X 形態的本機預設值。

這兩項都是**印廠條件**，不是本產品能替使用者決定的事：

- 總墨量上限（TAC）取決於紙張吸墨與乾燥能力，§9 給的是 320〜340% 的區間，程式
  預設取保守下限 320（ink.MAX_TAC）。印廠給了自家數字就填自家的。
- PDF/X 形態取決於印廠收哪一種：X-1a:2001 相容性最廣（不含透明、色彩全 CMYK），
  X-4 較新且強制嵌輸出 ICC。兩者都是合規送印檔，沒有一個「比較好」。

存本機檔（慣例路徑 local/press-config.local.json，local/ 已入 .gitignore），同
ai_config 形態：缺檔回預設不擋流程、壞檔明確錯誤不沉默。

**這裡存的是預設值，不是最終值。** 轉存對話框每次開啟時以本設定起始，仍可就該次
匯出改動；真正的判定與寫檔一律在 pdf_writer.export_pdf。設定與匯出各有一份值時，
以送進 export_pdf 的那份為準（單一事實來源在寫檔端）。
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .ink import MAX_TAC  # 預設值單一事實來源（§9 保守下限 320%）
from .pdfx_meta import PDFX_PROFILES

#: TAC 的物理上限：四個色版各 100%。超過此值的設定必為誤填。
MAX_POSSIBLE_TAC = 400.0

#: 慣例路徑（相對專案根）；編輯器與 CLI 共用同一份本機設定。
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "local" / "press-config.local.json"


class PressConfigError(ValueError):
    """設定檔存在但無法解析（壞 JSON／欄位型別或值域不符）。"""


@dataclass(frozen=True)
class PressConfig:
    """印前預設值：總墨量上限（%）與 PDF/X 形態鍵（x-1a／x-4／none）。"""
    max_tac: float = MAX_TAC
    pdfx: str = "x-1a"


def _check_max_tac(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PressConfigError(f"總墨量上限需為數字（得到 {type(value).__name__}）")
    tac = float(value)
    if not 0 < tac <= MAX_POSSIBLE_TAC:
        raise PressConfigError(
            f"總墨量上限 {tac:g}% 超出可能範圍"
            f"（須大於 0 且不逾四版全滿的 {MAX_POSSIBLE_TAC:g}%）")
    return tac


def _check_pdfx(value) -> str:
    if value not in PDFX_PROFILES:
        raise PressConfigError(
            f"未知 PDF/X 形態 {value!r}，可選 {sorted(PDFX_PROFILES)}")
    return value


def load_press_config(path=DEFAULT_PATH) -> PressConfig:
    """讀取本機印前設定：缺檔回預設（320%／X-1a）不擋流程；壞檔明確錯誤不沉默。

    未知鍵容忍（向前相容）；缺鍵補預設值。
    """
    p = Path(path)
    if not p.exists():
        return PressConfig()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise PressConfigError(f"讀取印前設定檔失敗 {p}：{e}") from e
    if not isinstance(data, dict):
        raise PressConfigError(f"印前設定檔 {p} 需為 JSON 物件")
    return PressConfig(
        max_tac=_check_max_tac(data.get("max_tac", MAX_TAC)),
        pdfx=_check_pdfx(data.get("pdfx", "x-1a")),
    )


def save_press_config(cfg: PressConfig, path=DEFAULT_PATH) -> None:
    """寫入本機印前設定（建立父目錄）；值域先驗過，不寫出讀不回來的檔。"""
    _check_max_tac(cfg.max_tac)
    _check_pdfx(cfg.pdfx)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
