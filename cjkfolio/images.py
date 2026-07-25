"""影像領域層（PLAN §9：全文 CMYK 或 Grayscale、灰階照片走單 K）。

圖片置入的單一事實來源：所有後端（render PNG／pdf_writer XObject）經此開啟圖檔、
決定色彩空間並載入像素；置入幾何（等比縮放置中）在 primitives.fit_image_rect。

色彩空間依**來源檔自帶的形態**分流（Sprint 92 立、Sprint 137 擴 RGB，open_placed）：
CMYK 來源保持 DeviceCMYK（真書送印稿 16 次彩色置入即此形態，
tools/measure_cmyk_images.py 實測）、灰階類來源轉 8-bit 灰階 DeviceGray（單 K）、
其餘（RGB／RGBA／調色盤）保持 RGB。

RGB 保持的理由與代價（Sprint 137）：Sprint 92〜136 期間非 CMYK 一律轉灰，於是彩色
封面圖在螢幕上是黑白的（Owner 真視窗回饋）。保持 RGB 讓螢幕看到原色，但 RGB 不是
§9 的印前色彩空間，**送印路徑（PDF/X-1a／X-4）仍在嵌入時轉灰並據實警告**，不沉默
也不擋流程；要彩色送印稿請在影像軟體轉 CMYK 後置入。本產品仍不做 RGB→CMYK 換算：
色彩轉換屬印廠 ICC 範疇（Sprint 76 色票決議、§7 對策「影像外部轉 CMYK 置入」）。

CMYK JPEG 快速失敗（spike18）：PIL 對 CMYK JPEG 一律以「Adobe 反相」慣例解讀，而
真實世界的 Adobe YCCK JPEG 經此讀出的是負片值（真書兩張樣本實測，反相假設誤差
3.14／5.69 對墨量假設 221.45／193.14）。判別依據只存在於函式庫層的容器細節，猜錯
的後果是整批送印成負片，故 v1 拒收並提示轉存 TIFF。

解析度不足以警告呈現（Sprint 91，不重採樣、不擋流程）：重採樣會改動使用者素材的
像素，屬影像編修而非排版，本產品只據實回報實效 PPI 供人決定換圖或縮小置入尺寸。
"""
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

PT_PER_INCH = 72.0
MIN_IMAGE_PPI = 300.0  # §9「連續調影像 300〜350ppi」的下限
# 判定容差：PDF 座標為浮點，恰足門檻的送印稿會落在門檻下微量（參考書 p138 實測
# 299.999996ppi，差 4e-6）。取 0.5＝報告顯示精度（四捨五入至整數 ppi），使「報告
# 顯示 300ppi 卻判不足」的自相矛盾不可能出現。
PPI_TOLERANCE = 0.5


class ImageError(ValueError):
    """圖檔無法開啟或非有效影像，或無置入標的。"""


def open_grayscale(path) -> Image.Image:
    """開啟圖檔並轉 8-bit 灰階（mode "L"）。回傳已載入記憶體的 PIL 影像。

    §9：灰階照片走單 K（DeviceGray）。恆轉灰階，不看來源色彩空間；置入用的分流
    在 open_placed（自 Sprint 137 起彩色來源保持 RGB，故兩者不再等價）。開啟失敗
    （缺檔、非影像）快速失敗，不沉默。
    """
    try:
        with Image.open(path) as im:
            return im.convert("L")
    except (OSError, UnidentifiedImageError) as e:
        raise ImageError(f"讀取圖檔失敗 {path}：{e}") from e


#: 灰階類來源模式（單通道或單通道＋alpha）→ 轉 "L"。其餘非 CMYK 模式轉 "RGB"。
#: 調色盤 "P" 不在此列：調色盤可存彩色，模式本身不足以判定，故一律當彩色。
GRAY_SOURCE_MODES = frozenset({"L", "LA", "La", "1", "I", "I;16", "I;16B", "I;16L", "F"})


def open_placed(path) -> Image.Image:
    """開啟置入圖並依來源色彩空間分流：CMYK 保持、灰階類轉 "L"、其餘轉 "RGB"。

    來源檔自帶哪一種就用哪一種（機器可讀的事實，非推測）。§9 的兩種印前色彩空間
    （CMYK、Grayscale）原樣保留；RGB 保留是為了螢幕看得到原色（Sprint 137），
    送印時的轉灰與警告在 pdf_writer，不在此處靜默處理。
    CMYK JPEG 拒收（模組 docstring 記反相實測）；開啟失敗快速失敗，不沉默。
    """
    try:
        with Image.open(path) as im:
            if im.mode in GRAY_SOURCE_MODES:
                return im.convert("L")
            if im.mode != "CMYK":
                return im.convert("RGB")
            if (im.format or "").upper() in ("JPEG", "JPEG2000", "MPO"):
                raise ImageError(
                    f"不支援 CMYK JPEG 置入 {path}：JPEG 的 CMYK 分量有反相慣例歧異，"
                    f"讀錯會使送印稿成為負片。請以影像軟體另存為 CMYK TIFF 後置入"
                )
            return im.copy()
    except (OSError, UnidentifiedImageError) as e:
        raise ImageError(f"讀取圖檔失敗 {path}：{e}") from e


def resolve_placed_images(doc, masters_by_page: dict, base_dir=None) -> dict:
    """把 doc.images 解析為 {版面頁號: ((解析後路徑, PIL 影像, rect|None), ...)}。

    兩後端共用；每頁多張（文件序＝繪製序，Sprint 54）。
    masters_by_page＝{版面頁號: MasterPage}（節式主版指派後逐頁主版，Sprint 51）：
    - page 超出排版頁數（不在 masters_by_page）→ 快速失敗
    - 槽式圖（rect None）落點頁的主版無 figure 保留區 → 快速失敗（無置入標的）；
      rect 任意圖框不需 figure 槽（座標自帶）
    - 路徑相對 base_dir 解析（None＝相對 CWD）；同路徑只載一次（PDF 端 XObject 去重鍵）
    """
    if not doc.images:
        return {}
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    cache: dict = {}
    out: dict = {}
    for im in doc.images:
        master = masters_by_page.get(im.page)
        if master is None:
            raise ImageError(
                f"置入圖 page {im.page} 超出排版頁數（共 {len(masters_by_page)} 頁）"
            )
        if im.rect is None and master.figure is None:
            raise ImageError(
                f"置入圖 page {im.page} 的主版「{master.name}」無 figure 保留區配置"
            )
        resolved = str((base / im.path).resolve())
        if resolved not in cache:
            cache[resolved] = open_placed(base / im.path)
        out.setdefault(im.page, []).append((resolved, cache[resolved], im.rect))
    return {page: tuple(entries) for page, entries in out.items()}


def effective_ppi(px: int, draw_pt: float) -> float:
    """實效解析度＝像素數 ÷ 繪製英吋數（1 英吋＝72pt）。

    影像自身的 DPI metadata 不參與判定（置入後的實效值只由像素數與繪製尺寸決定）。
    非正像素數或繪製尺寸快速失敗（系統邊界，同 fit_image_rect 慣例）。
    """
    if px <= 0:
        raise ValueError(f"影像像素數須為正，得到 {px}")
    if draw_pt <= 0:
        raise ValueError(f"繪製尺寸須為正 pt，得到 {draw_pt}")
    return px * PT_PER_INCH / draw_pt


@dataclass(frozen=True)
class ImageResolution:
    """單張置入影像的解析度紀錄（來源像素數＋實際繪製尺寸）。"""
    path: str          # 圖檔名（不含目錄）
    page: int          # 版面頁號（1 起算，同 PlacedImage.page）
    px_w: int
    px_h: int
    draw_w_pt: float
    draw_h_pt: float

    @property
    def ppi(self) -> float:
        """實效 PPI 取兩軸較差者（contain 等比縮放下兩軸同值）。"""
        return min(effective_ppi(self.px_w, self.draw_w_pt),
                   effective_ppi(self.px_h, self.draw_h_pt))


def meets_ppi(ppi: float, min_ppi: float = MIN_IMAGE_PPI) -> bool:
    """實效 PPI 是否達門檻（含 PPI_TOLERANCE 浮點容差）。

    產出側 resolution_warnings 與驗證側 preflight.check_image_resolution 共用此
    判定，兩側門檻語意不得分歧。
    """
    return ppi >= min_ppi - PPI_TOLERANCE


def resolution_warnings(resolutions, min_ppi: float = MIN_IMAGE_PPI) -> list:
    """彙整實效 PPI 低於門檻的影像警告（達標者不列）。

    同字型授權檢查慣例（Sprint 84）：不沉默、不擋流程；印廠是否接受由使用者決定。
    """
    return [
        f"影像解析度：頁 {r.page} {r.path} 實效 {r.ppi:.0f}ppi 低於 {min_ppi:.0f}ppi"
        f"（§9 連續調影像 300〜350ppi；換高解析度圖或縮小置入尺寸）"
        for r in resolutions if not meets_ppi(r.ppi, min_ppi)
    ]


#: PIL mode → PDF 影像色彩空間。前兩種是 §9 的印前色彩空間，非 preflight
#: color-cmyk-only 的禁列項；"RGB" 是 preflight 會判失敗的那一種，只在非 PDF/X 的
#: 一般 PDF 走得到（PDF/X 路徑於 pdf_writer 轉灰並警告，Sprint 137）。
IMAGE_COLORSPACES = {"L": "/DeviceGray", "CMYK": "/DeviceCMYK", "RGB": "/DeviceRGB"}

#: §9 印前色彩空間（PDF/X 輸出只嵌這兩種）。
PRINT_IMAGE_MODES = frozenset({"L", "CMYK"})


class EmbeddedImage:
    """置入影像的 PDF XObject 表示（灰階單 K／CMYK／RGB）：影像領域的 PDF 形態。

    res_name＝ImN（pdf_writer 與字型 FN 分名域）；data＝8-bit 原始像素（row-major、
    首列在上，PIL tobytes）：mode "L" 為每像素 1 分量、"RGB" 為 3 分量、"CMYK" 為
    4 分量。emit 經傳入的 PDF builder 的 stream 做 FlateDecode 壓縮並回傳物件號。

    無 SMask（不置入 alpha，preflight no-transparency 不觸；真書送印稿雖有 14 處
    SMask，其交印檔本就非 PDF/X，不比照）。無 /Decode 反相陣列（分量即墨量，與真書
    DeviceCMYK 影像同形，tools/measure_cmyk_images.py 實測 16 次置入皆無此鍵）。
    """

    def __init__(self, pil_image: Image.Image, res_name: str):
        colorspace = IMAGE_COLORSPACES.get(pil_image.mode)
        if colorspace is None:
            raise ImageError(
                f"置入影像色彩空間 {pil_image.mode} 不可嵌入（§9 限 "
                f"{'／'.join(IMAGE_COLORSPACES)}）"
            )
        self.res_name = res_name
        self.colorspace = colorspace
        self.width, self.height = pil_image.size
        self.data = pil_image.tobytes()

    def emit(self, pdf) -> int:
        """經 PDF builder（duck-typed，具 .stream(extra_dict, data)）寫出影像 XObject。"""
        return pdf.stream(
            f" /Type /XObject /Subtype /Image /Width {self.width} /Height {self.height} "
            f"/ColorSpace {self.colorspace} /BitsPerComponent 8",
            self.data,
        )
