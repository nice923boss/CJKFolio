"""RGB → CMYK 的 ICC 色彩轉換（Sprint 139；R2 閘門的量測見 spikes/spike25-icc-cmyk/）。

Sprint 76 與 Sprint 137 兩度決議「不做 RGB→CMYK」。推翻的只有「不做」二字，不是理由：
兩條決議反對的是**沒有色彩管理的 naive 換算**（逐通道套公式），而 naive 換算此後仍然
禁止。Spike 25 實測後定案的形態是「有描述檔才轉」，三個條件缺一不可，本模組即這三條
的落點：

1. **描述檔由使用者提供**：目標 CMYK 描述檔＝送印稿要嵌的 DestOutputProfile（同一份
   位元組，故轉換目標與 PDF 宣告的輸出條件必然一致）。本產品不內建描述檔：§9 指定的
   Japan Color 屬第三方散布物，內建會把授權義務轉嫁給下游（同 §10 Sprint 10 對
   OutputIntent 的處置）。**無描述檔時快速失敗，不降級**。
2. **灰階來源不進轉換**：256 階中性灰經 ICC 轉換後，SWOP 有 254 階、Japan Color 2011
   Coated 有 255 階的 C／M／Y 非零；中灰在後者轉出 (141, 122, 122, 3)＝近乎無 K 的
   四色灰。這違反 §9「灰階照片走單 K」，且四版沒對準就偏色。故 "L" 原樣返回。
3. **轉出照過墨量檢查**：轉出的是 CMYK，pdf_writer 既有的 image_max_tac 與
   tac_warnings 自然接手。實測 Japan Color 2011 Coated 轉出的最高 TAC 為 350%，
   **高於本產品 320% 預設門檻**，警告會照實響。那是描述檔自身的墨量上限，不是本產品
   可代為抹掉的事（§9 區間上緣 340%，仍須與印廠確認）。

CMYK 來源同樣原樣返回：來源已在印刷色彩空間，再轉一次是 device → device 二次換算，
只會多累積一層誤差。

**本模組不擔保顏色正確。**它做得到的是「照你給的描述檔換算」，做不到的是「保證印出來
的顏色對」，後者要打樣（本機無分光儀、無標準光源、無打樣，Spike 25 §3 記明驗不到的
範圍）。UI 與文件不得出現顏色正確性的宣稱。
"""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageCms

from .pdfx_meta import validate_output_profile

#: 可選的 rendering intent（人讀名 → ICC 值）。預設 relative colorimetric：
#: Spike 25 四 intent 中它的 TAC 最低，且色域內的顏色維持原值（perceptual 全域壓縮）。
RENDERING_INTENTS = {"perceptual": 0, "relative": 1}
DEFAULT_INTENT = "relative"

#: 不開放的 intent 與理由（拒收時原樣回給使用者，不沉默改選）。
REJECTED_INTENTS = {
    "saturation": "飽和度優先（ICC intent 2）以鮮豔為目標，實測連純黑都轉成四色"
                  "（(63, 73, 81, 255)、TAC 185%），不適合送印稿",
    "absolute": "絕對色度（ICC intent 3）用於打樣時模擬另一種紙白，本產品的用途是"
                "送印稿而非模擬，且本機沒有打樣可據以判斷差異",
}

#: 內嵌來源描述檔的最短長度與 RGB 色彩空間標記（ICC header 位元組，同
#: pdfx_meta.validate_output_profile 的判讀方式：讀檔案自己說的，不猜副檔名）。
_ICC_HEADER_MIN = 132
_ICC_RGB_SPACE = b"RGB "

#: 來源未標記描述檔時的假設。Spike 25 實測：內嵌 sRGB 與合成 sRGB 轉出的分量差平均
#: 0.007／255（捨入級），故此假設不構成可觀測的差異。
_ASSUMED_SOURCE = "sRGB（來源未標記描述檔）"


class ColorConvertError(ValueError):
    """色彩轉換無法進行：缺描述檔、intent 不受理，或來源模式不可轉。"""


def resolve_intent(intent: str) -> int:
    """rendering intent 人讀名 → ICC 值；不受理者快速失敗並附理由。"""
    if intent in RENDERING_INTENTS:
        return RENDERING_INTENTS[intent]
    if intent in REJECTED_INTENTS:
        raise ColorConvertError(
            f"rendering intent {intent!r} 不開放：{REJECTED_INTENTS[intent]}")
    raise ColorConvertError(
        f"未知 rendering intent {intent!r}，可選 {sorted(RENDERING_INTENTS)}")


def _source_profile(image: Image.Image):
    """來源描述檔：內嵌且為 RGB 者取之，否則假設 sRGB。回傳 (profile, 人讀來源)。

    內嵌描述檔非 RGB（灰階或 CMYK 的標記混入 RGB 像素）時不採用：那是來源檔自身的
    矛盾，拿去當轉換來源會靜默轉錯，改以 sRGB 假設並在說明中言明。
    """
    raw = image.info.get("icc_profile")
    if raw and len(raw) >= _ICC_HEADER_MIN and raw[16:20] == _ICC_RGB_SPACE:
        return ImageCms.getOpenProfile(BytesIO(raw)), "來源內嵌描述檔"
    return ImageCms.createProfile("sRGB"), _ASSUMED_SOURCE


def convert_to_cmyk(image: Image.Image, icc_bytes: bytes,
                    intent: str = DEFAULT_INTENT,
                    source="輸出描述檔") -> tuple[Image.Image, str]:
    """RGB 影像依 icc_bytes 轉 CMYK，回傳 (影像, 來源色彩空間說明)。

    "L"（灰階單 K）與 "CMYK"（已在印刷色彩空間）原樣返回，說明為空字串：
    理由見模組 docstring 條件 2。其餘 mode 快速失敗（系統邊界慣例）。
    icc_bytes 須為 CMYK 輸出（prtr）描述檔，判定與 DestOutputProfile 同一條
    （validate_output_profile）：能當轉換目標的，就是能嵌進 OutputIntent 的那一份。
    """
    if not icc_bytes:
        raise ColorConvertError(
            "色彩轉換須有目標 CMYK 輸出描述檔：請以 icc_profile 提供"
            "（PDF/X-1a／X-4 適用；一般 PDF 不寫 OutputIntent 故不收描述檔）。"
            "無描述檔時本產品不做無色彩管理的換算（§10 Sprint 76 決議）")
    validate_output_profile(icc_bytes, source)
    value = resolve_intent(intent)
    if image.mode in ("L", "CMYK"):
        return image, ""
    if image.mode != "RGB":
        raise ColorConvertError(
            f"影像 mode {image.mode} 不可轉換（限 RGB；灰階與 CMYK 原樣保留）")
    src, src_label = _source_profile(image)
    try:
        dst = ImageCms.getOpenProfile(BytesIO(icc_bytes))
        out = ImageCms.profileToProfile(
            image, src, dst, renderingIntent=value, outputMode="CMYK")
    except ImageCms.PyCMSError as e:
        raise ColorConvertError(
            f"描述檔 {Path(source).name} 無法用於色彩轉換：{e}"
            "（header 合格不代表色彩轉換表完整，littleCMS 打不開就不轉）") from e
    return out, src_label


def profile_label(icc_bytes: bytes, source) -> str:
    """描述檔的人讀名：取其自報的 description，空白或讀不到時退回檔名。"""
    try:
        desc = ImageCms.getProfileDescription(
            ImageCms.getOpenProfile(BytesIO(icc_bytes))).strip()
    except ImageCms.PyCMSError:
        return Path(source).name
    return desc or Path(source).name


def convert_placed_images(images_by_page: dict, icc_bytes: bytes,
                          intent: str = DEFAULT_INTENT,
                          source="輸出描述檔") -> tuple[dict, list]:
    """置入圖對映（images.resolve_placed_images 的產物）整批轉 CMYK。

    回傳 (新對映, 說明清單)。同路徑跨頁只轉一次（與 XObject 去重同一把鑰匙）；
    未轉的（灰階、CMYK）原樣留在對映中，不產生說明。
    說明逐張列明描述檔、intent 與來源色彩空間，並言明本產品不擔保顏色正確性：
    轉換是機械換算，是否符合印出來的樣子要打樣才知道。
    """
    resolve_intent(intent)   # 無圖也要擋掉不受理的 intent（不等到有圖才報）
    label = profile_label(icc_bytes, source) if icc_bytes else ""
    converted: dict = {}
    notes: list = []
    out: dict = {}
    for page, entries in images_by_page.items():
        new_entries = []
        for path, pil, rect in entries:
            if path not in converted:
                image, src_label = convert_to_cmyk(pil, icc_bytes, intent, source)
                converted[path] = image
                if src_label:
                    notes.append(
                        f"{Path(path).name}：RGB 影像已依「{label}」以 {intent} "
                        f"intent 轉為 CMYK 嵌入（來源＝{src_label}）；"
                        "顏色正確性須經印廠打樣確認，本產品不擔保")
            new_entries.append((path, converted[path], rect))
        out[page] = tuple(new_entries)
    return out, notes
