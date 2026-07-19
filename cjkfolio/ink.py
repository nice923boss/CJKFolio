"""油墨總量 TAC 領域層（PLAN §9：總墨量 ≤ 320〜340%）。

TAC（Total Area Coverage）＝同一點四色版墨量的百分比和。上限是**印廠條件**
（紙張吸墨與乾燥能力），不是 ISO 15930-1（PDF/X-1a）條款：超標的 PDF 仍是合規的
PDF/X，只是印刷風險（背印、糊版、乾燥不及）。故 TAC 不入 preflight.check_pdfx
規則集，另由 preflight.check_ink_coverage 獨立檢查（同 Sprint 91 PPI 的規則集分離）。

門檻取 §9 區間下限 320% 為預設（保守側）；印廠條件較寬時可調（CLI --max-tac）。

**只警告不擋流程**（同 Sprint 84 授權檢查、Sprint 91 解析度慣例）：真書送印稿實測
（tools/measure_ink_coverage.py，179 頁全掃）本身即有超標處（手繪路徑富黑
TAC 349.5%，8 頁；9 張影像最大 TAC 逾 320%，最高 357%），該書仍順利付印，可見
是否接受屬印廠與紙張條件的判斷，不是排版軟體可代為否決的事。本產品據實回報。

本產品的預設輸出不會超標：內文暖黑單 K92（§9 內文轉單 K90-92）、裁切標記單 K100、
向量原件皆單 K。超標有三個來源：使用者自訂的富黑色票、置入的彩色 CMYK 影像，以及
**opt-in 的印前標記**（Sprint 109，`--press-marks`）：套準十字為四版套準色，TAC 400%
必然超標並照實回報。該標記位於 TrimBox 外、裁切後不入成品，但本層不讀盒框也無座標
欄位，故無從據此豁免；產出側改以 `InkUse.kind`＝「印前標記」標明來源供判讀（見
GAPS #42）。要墨量全綠者可加 `--registration-single-k`（代價是該標記不曬在 C／M／Y 版）。
"""
from dataclasses import dataclass

from PIL import Image, ImageMath

MAX_TAC = 320.0        # §9「總墨量 ≤ 320〜340%」的保守下限
# 判定容差：報告顯示四捨五入至整數 %，取 0.5 使「顯示 320% 卻判超標」的自相矛盾
# 不可能出現（同 images.PPI_TOLERANCE 的理由）。
TAC_TOLERANCE = 0.5

#: PIL mode → 每像素墨量的算法（"L" 為 DeviceGray：0＝全黑＝單 K 100%）
_SUPPORTED_MODES = ("L", "CMYK")


def tac_percent(cmyk) -> float:
    """DeviceCMYK 四分量（各 0〜1）→ 總墨量百分比（0〜400）。

    分量數不為 4 或超出 [0, 1] 快速失敗（系統邊界，同 images.effective_ppi 慣例）。
    """
    values = tuple(cmyk)
    if len(values) != 4:
        raise ValueError(f"CMYK 須為四分量，得到 {len(values)} 個")
    for v in values:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"CMYK 分量須在 0〜1，得到 {v}")
    return sum(values) * 100.0


def meets_tac(tac: float, max_tac: float = MAX_TAC) -> bool:
    """總墨量是否在上限內（含 TAC_TOLERANCE 顯示精度容差）。

    產出側 tac_warnings 與驗證側 preflight.check_ink_coverage 共用此判定，
    兩側門檻語意不得分歧。
    """
    return tac <= max_tac + TAC_TOLERANCE


def image_max_tac(image: Image.Image) -> float:
    """置入影像的**最高**單點墨量百分比（不取平均：一枚重墨像素即構成風險）。

    mode "L"＝DeviceGray（0 全黑）：墨量＝(255 − 值) / 2.55，上限 100%（單 K）。
    mode "CMYK"：四分量和 / 2.55，上限 400%。其餘 mode 快速失敗（本產品只寫出
    這兩種影像色彩空間，images.IMAGE_COLORSPACES）。

    四分量相加走 PIL ImageMath（C 層、"I" 模式不飽和截斷），逐像素相加在
    Python 層對送印級影像過慢，且 ImageChops.add 會在 255 截斷而失真。
    """
    if image.mode not in _SUPPORTED_MODES:
        raise ValueError(
            f"影像 mode {image.mode} 不可判墨量（限 {'／'.join(_SUPPORTED_MODES)}）")
    if image.mode == "L":
        darkest = image.getextrema()[0]
        return (255 - darkest) / 2.55
    c, m, y, k = image.split()
    total = ImageMath.lambda_eval(
        lambda a: a["c"] + a["m"] + a["y"] + a["k"], c=c, m=m, y=y, k=k)
    return total.getextrema()[1] / 2.55


@dataclass(frozen=True)
class InkUse:
    """一處墨量來源（產出側紀錄）：著色值或置入影像各一筆。"""
    kind: str      # "著色"（內容流 k／K）或"影像"（置入的 XObject）
    label: str     # 著色＝色票或色值字串；影像＝圖檔名
    tac: float     # 該來源的最高總墨量百分比


def tac_warnings(uses, max_tac: float = MAX_TAC) -> list:
    """彙整超出上限的墨量警告（達標者不列）。

    不沉默、不擋流程：印廠條件與紙張決定是否可接受，本產品只據實回報供人決定
    （降低富黑成分、改用單 K，或與印廠確認可接受的上限）。
    """
    return [
        f"油墨總量：{u.kind} {u.label} 最高 TAC {u.tac:.0f}% 超過 {max_tac:.0f}%"
        f"（§9 總墨量 ≤ 320〜340%；降低富黑成分或與印廠確認上限）"
        for u in uses if not meets_tac(u.tac, max_tac)
    ]
