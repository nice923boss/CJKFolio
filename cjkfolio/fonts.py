"""字型解析：樣式的（家族, 字重）→ assets/fonts 檔案，缺項 fallback 並警告。

內建字型組以 PLAN §8 可散布清單為準（OFL／政府開放授權）。
GAPS：目前僅思源宋體 TC 兩檔在庫，其餘家族一律 fallback 並記警告，不沉默。
"""
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
DEFAULT_FAMILY = "思源宋體 TC"

# 家族 → 字重 → 檔名。空 dict = 已規劃（PLAN §8）但尚未入庫（FONTS.md 待補）。
FAMILY_FILES = {
    "思源宋體 TC": {
        "regular": "SourceHanSerifTC-Regular.otf",
        "heavy": "SourceHanSerifTC-Heavy.otf",
    },
    "思源黑體 TC": {},
    "全字庫正楷體 TW-Kai": {},
    "全字庫正宋體": {},
    "辰宇落雁體": {},
    "jf open 粉圓": {},
}

# 字重替代順序（找不到請求字重時，依序找可用檔）
WEIGHT_ALIASES = {
    "light": ["light", "regular"],
    "regular": ["regular", "medium"],
    "medium": ["medium", "regular"],
    "bold": ["bold", "heavy", "regular"],
    "heavy": ["heavy", "bold", "regular"],
}


class FontError(RuntimeError):
    """完全無可用字型檔。"""


@dataclass(frozen=True)
class ResolvedFont:
    path: Path
    index: int
    family: str
    weight: str
    requested_family: str
    requested_weight: str

    @property
    def family_fallback(self) -> bool:
        return self.family != self.requested_family

    @property
    def weight_fallback(self) -> bool:
        return self.weight != self.requested_weight


class FontRegistry:
    def __init__(self, font_dir=DEFAULT_FONT_DIR):
        self.font_dir = Path(font_dir)
        self.warnings: list = []

    def _warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def _find(self, family: str, weight: str):
        files = FAMILY_FILES.get(family, {})
        for w in WEIGHT_ALIASES.get(weight, [weight, "regular"]):
            filename = files.get(w)
            if filename and (self.font_dir / filename).exists():
                return self.font_dir / filename, w
        return None, None

    def resolve(self, family: str, weight: str) -> ResolvedFont:
        path, actual_weight = self._find(family, weight)
        actual_family = family
        if path is None and family != DEFAULT_FAMILY:
            path, actual_weight = self._find(DEFAULT_FAMILY, weight)
            actual_family = DEFAULT_FAMILY
            if path is not None:
                self._warn(
                    f"字型家族「{family}」未入 assets/fonts，"
                    f"以 {DEFAULT_FAMILY} 替代（FONTS.md 待補清單）"
                )
        if path is None:
            raise FontError(
                f"找不到可用字型：{family}/{weight}（assets/fonts 依 FONTS.md 指令重現下載）"
            )
        if actual_family == family and actual_weight != weight:
            self._warn(f"家族「{family}」無字重 {weight} 檔，以 {actual_weight} 替代")
        return ResolvedFont(
            path=path,
            index=0,
            family=actual_family,
            weight=actual_weight,
            requested_family=family,
            requested_weight=weight,
        )
