"""影像領域層（PLAN §9：灰階照片走單 K）。

圖片置入的單一事實來源：所有後端（render PNG／pdf_writer XObject）經此開啟圖檔
並轉 8-bit 灰階（DeviceGray／單 K，維持 §9 全 CMYK/灰階、無殘留 RGB）。此層負責
色彩空間決策、像素載入與 PDF 影像 XObject 形態；置入幾何（等比縮放置中）在
primitives.fit_image_rect。

v1 只支援灰階置入（§9「連續調影像／灰階照片走單 K」）；彩色 CMYK 影像與 300ppi
重採樣屬 Phase 4（GAPS #18 認證級 preflight）。
"""
from pathlib import Path

from PIL import Image, UnidentifiedImageError


class ImageError(ValueError):
    """圖檔無法開啟或非有效影像，或無置入標的。"""


def open_grayscale(path) -> Image.Image:
    """開啟圖檔並轉 8-bit 灰階（mode "L"）。回傳已載入記憶體的 PIL 影像。

    §9：灰階照片走單 K（DeviceGray）；此為圖片置入的色彩空間決策單一事實來源。
    開啟失敗（缺檔、非影像）快速失敗，不沉默。
    """
    try:
        with Image.open(path) as im:
            return im.convert("L")
    except (OSError, UnidentifiedImageError) as e:
        raise ImageError(f"讀取圖檔失敗 {path}：{e}") from e


def resolve_placed_images(doc, masters_by_page: dict, base_dir=None) -> dict:
    """把 doc.images 解析為 {版面頁號: (解析後路徑字串, PIL "L" 影像)}，供兩後端共用。

    masters_by_page＝{版面頁號: MasterPage}（節式主版指派後逐頁主版，Sprint 51）：
    - page 超出排版頁數（不在 masters_by_page）→ 快速失敗
    - 圖落點頁的主版無 figure 保留區 → 快速失敗（無置入標的）
    - 路徑相對 base_dir 解析（None＝相對 CWD）；同路徑只載一次（PDF 端 XObject 去重鍵）

    v1：每頁 figure 保留區置一張圖（document 已驗 page 不重複）。
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
        if master.figure is None:
            raise ImageError(
                f"置入圖 page {im.page} 的主版「{master.name}」無 figure 保留區配置"
            )
        resolved = str((base / im.path).resolve())
        if resolved not in cache:
            cache[resolved] = open_grayscale(base / im.path)
        out[im.page] = (resolved, cache[resolved])
    return out


class EmbeddedImage:
    """置入影像的 DeviceGray XObject 表示（§9 灰階單 K）：影像領域的 PDF 形態。

    res_name＝ImN（pdf_writer 與字型 FN 分名域）；data＝8-bit 灰階原始像素
    （row-major、首列在上，PIL "L" tobytes）。emit 經傳入的 PDF builder 的 stream
    做 FlateDecode 壓縮並回傳物件號。無 SMask（灰階無 alpha，preflight no-transparency
    不觸）；ColorSpace /DeviceGray（非禁列 RGB，X-1a 合法、preflight color-cmyk-only 不觸）。
    """

    def __init__(self, pil_gray: Image.Image, res_name: str):
        self.res_name = res_name
        self.width, self.height = pil_gray.size
        self.data = pil_gray.tobytes()

    def emit(self, pdf) -> int:
        """經 PDF builder（duck-typed，具 .stream(extra_dict, data)）寫出影像 XObject。"""
        return pdf.stream(
            f" /Type /XObject /Subtype /Image /Width {self.width} /Height {self.height} "
            f"/ColorSpace /DeviceGray /BitsPerComponent 8",
            self.data,
        )
