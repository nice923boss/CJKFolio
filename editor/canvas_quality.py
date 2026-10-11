"""畫布預覽畫質（Sprint 133）：縮放感知的底圖解析度分級與背景重渲染。

Owner 真視窗回饋：「預覽的畫面字體不夠清晰，改成預覽是非常清楚的字體與圖片
內容才對。」

根因（Spike 24 一手量測，spikes/spike24-canvas-dpi/）：底圖固定 150dpi，畫布
放大即把同一張點陣圖拉伸，筆畫邊緣糊掉；對照圖證實同區域 450dpi 原生仍然銳利。
**非字型或塑形問題**，故不動渲染核心。

形態：**scene 座標系維持 150dpi 空間不變**，底圖改以較高 dpi 渲染後
`setScale(150/base_dpi)` 縮回原尺寸。互動層字格幾何因此**零改動**，既有
hit-test、置圖、對頁檢視全部不受影響（取此形態而非「整個 scene 改高 dpi」的理由）。

分級而非連續（Spike 24 結論 2）：連續 dpi 會使每次滾輪微調都觸發整頁重渲染。
上限 450dpi（結論 3）：600dpi 單頁 66MB、對頁 132MB 與長書匯入同量級，而 450dpi
在 300% 縮放時已與螢幕像素 1:1。渲染一律走背景執行緒（結論 4）：最高級
162ms 超過互動門檻，且 300dpi 的 82ms 已貼近。
"""
import time

from PySide6.QtCore import QThread, Signal

from cjkfolio.images import ImageError
from cjkfolio.render import PageRenderer
from cjkfolio.press_marks import BLEED_MM
from cjkfolio.render import mm_to_pt
from editor.canvas import (
    bleed_base_pos,
    bleed_px_for,
    crop_spine_bleed,
    page_frame_placements,
    page_images,
    pil_to_qimage,
)

CANVAS_DPI = 150  # scene 座標系基準（互動層幾何依此；不隨畫質變）
# 底圖可選解析度（Spike 24 實測重繪中位：34／54／82／162ms）
BASE_DPI_LEVELS = (150, 225, 300, 450)


def target_base_dpi(zoom: float, dpr: float = 1.0) -> int:
    """畫布縮放倍率（與螢幕裝置像素比）→ 底圖該用的渲染 dpi。

    需求 dpi＝150×倍率×裝置像素比（螢幕實體像素與底圖像素 1:1 時最清晰）；
    取 ≥ 需求的最小級數，超出最高級即夾住。縮小時不降到基準以下：低 dpi 底圖
    畫小並無畫質收益，只多一次渲染。
    """
    need = CANVAS_DPI * max(zoom, 0.0) * max(dpr, 0.0)
    for level in BASE_DPI_LEVELS:
        if level >= need:
            return level
    return BASE_DPI_LEVELS[-1]


QUALITY_DEBOUNCE_MS = 180  # 縮放停止後多久起重渲染（連續滾輪收斂成一輪）


class CanvasQualityMixin:
    """畫布底圖畫質調度（Sprint 133）：縮放停止 → 背景重渲染 → 就地換底圖。

    漸進式細化：`_rebuild` 一律以 CANVAS_DPI 建 scene（Spike 24 實測 34ms，
    每打一字 reflow 都跑得動），畫質升級另由本 mixin 於停手後補上；否則編輯時
    每字都要付 450dpi 的 162ms。

    依賴宿主提供：self.doc／self.template／self.layout_result／self.page／
    self.scene／self.view／self._doc_path／self._facing／self.statusBar()。
    """

    # 類別層預設值（preflight_actions 慣例：不必動 EditorWindow.__init__ 主流程）
    _quality_thread = None
    _quality_generation = 0
    _quality_pending = False
    _quality_dpi = CANVAS_DPI     # 目前底圖的渲染 dpi
    _quality_elapsed = None       # 最近一輪耗時秒（smoke 與效能實測讀取）
    _quality_timer = None

    def _init_quality(self) -> None:
        """__init__ 尾端接線：debounce 計時器（同 _init_nav 慣例）。"""
        from PySide6.QtCore import QTimer

        self._quality_timer = QTimer(self)
        self._quality_timer.setSingleShot(True)
        self._quality_timer.setInterval(QUALITY_DEBOUNCE_MS)
        self._quality_timer.timeout.connect(self._start_quality_render)

    def _device_pixel_ratio(self) -> float:
        """螢幕裝置像素比（HiDPI）：Windows 125%／150% 縮放下為 1.25／1.5。"""
        try:
            return float(self.view.devicePixelRatioF())
        except (AttributeError, TypeError):  # 離屏平台可能未提供
            return 1.0

    def _target_quality_dpi(self) -> int:
        return target_base_dpi(self.view.zoom_factor(), self._device_pixel_ratio())

    def _schedule_quality(self) -> None:
        """縮放或重繪後排程畫質升級；已是目標 dpi 就不做（不做無謂重渲染）。"""
        if self._quality_timer is None or self.page is None:
            return
        if self._target_quality_dpi() == self._quality_dpi:
            self._quality_timer.stop()
            return
        self._quality_timer.start()

    def _quality_page_numbers(self) -> tuple:
        """本輪要重渲染的頁號：單頁模式一頁、對頁模式兩頁（畫面上看得到的才渲染）。"""
        from editor.canvas import spread_pages

        if not getattr(self, "_facing", False):
            return (self.page.number,)
        left, right = spread_pages(self.page.number,
                                   len(self.layout_result.pages))
        return tuple(n for n in (left, right) if n is not None)

    def _start_quality_render(self) -> None:
        if self._quality_thread is not None:  # 舊輪未收工：取消並記接力
            self._quality_thread.cancel()
            self._quality_pending = True
            return
        if self.page is None:
            return
        dpi = self._target_quality_dpi()
        if dpi == self._quality_dpi:
            return
        self._quality_generation += 1
        thread = PageImageThread(
            self._quality_generation, self.doc, self.template,
            self.layout_result, self._quality_page_numbers(),
            self._doc_path.parent, dpi, parent=self,
            bleed=getattr(self, "_show_bleed", False))
        thread.page_ready.connect(self._on_quality_page)
        thread.all_done.connect(self._on_quality_done)
        thread.finished.connect(self._on_quality_thread_finished)
        self._quality_thread = thread
        thread.start()

    def _on_quality_page(self, generation: int, number: int, qimage) -> None:
        """換上高解析底圖：scene 座標不變（setScale 縮回），互動層完全不動。"""
        from PySide6.QtGui import QPixmap

        if generation != self._quality_generation:  # 過期輪不上牆
            return
        thread = self._quality_thread
        dpi = thread.dpi if thread is not None else CANVAS_DPI
        for item in self.scene.items():
            if item.data(1) != number:  # data(1)＝底圖標記（見 canvas.build_page_scene）
                continue
            placement = item.data(2)  # 出血底圖（Sprint 156）：同規則裁訂口側、重定位
            if placement is not None:
                x_offset, spine = placement
                bleed_px = bleed_px_for(dpi)
                qimage = crop_spine_bleed(qimage, bleed_px, spine)
                item.setPos(*bleed_base_pos(x_offset, bleed_px * CANVAS_DPI / dpi, spine))
            item.setPixmap(QPixmap.fromImage(qimage))
            item.setScale(CANVAS_DPI / dpi)
            break

    def _on_quality_done(self, generation: int, elapsed: float,
                         image_errors: int) -> None:
        if generation != self._quality_generation:
            return
        self._quality_elapsed = elapsed
        thread = self._quality_thread
        if thread is not None:
            self._quality_dpi = thread.dpi
        if image_errors:  # 缺圖不沉默（主畫布另有逐次提示，此處彙整頁數）
            self.statusBar().showMessage(
                f"預覽畫質：{image_errors} 頁置入圖未載入（該頁不顯示圖）")

    def _on_quality_thread_finished(self) -> None:
        self._quality_thread = None
        if self._quality_pending:  # 輪中被取消的改動接力
            self._quality_pending = False
            self._start_quality_render()

    def _shutdown_quality(self) -> None:
        """關窗與 smoke 收尾：停計時器並等執行緒收工（同 _shutdown_thumbnails）。"""
        if self._quality_timer is not None:
            self._quality_timer.stop()
        self._quality_pending = False
        if self._quality_thread is not None:
            self._quality_thread.cancel()
            self._quality_thread.wait()
            self._quality_thread = None


class PageImageThread(QThread):
    """背景渲染單頁（或對頁兩頁）底圖（doc／template／layout 為不可變快照）。

    與 page_panel.ThumbnailThread 同型（Sprint 125 先例）：世代守門由呼叫端做，
    過期結果丟棄；cancel 讓 worker 於當前頁渲染完即返回。
    """

    page_ready = Signal(int, int, object)   # (generation, page_number, QImage)
    all_done = Signal(int, float, int)      # (generation, 耗時秒, 缺圖頁數)

    def __init__(self, generation: int, doc, template, layout, page_numbers,
                 base_dir, dpi: int, parent=None, bleed: bool = False) -> None:
        super().__init__(parent)
        self._bleed_pt = mm_to_pt(BLEED_MM) if bleed else 0.0
        self._generation = generation
        self._doc = doc
        self._template = template
        self._layout = layout
        self._page_numbers = tuple(page_numbers)
        self._base_dir = base_dir
        self._dpi = dpi
        self._cancelled = False

    @property
    def dpi(self) -> int:
        return self._dpi

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        from cjkfolio.primitives import book_number_for, sheet_face_for

        t0 = time.perf_counter()
        renderer = PageRenderer(self._template, self._doc.master, dpi=self._dpi)
        by_number = {p.number: p for p in self._layout.pages}
        image_errors = 0
        for number in self._page_numbers:
            if self._cancelled:  # 提前收工：不發 all_done（該輪已作廢）
                return
            page = by_number.get(number)
            if page is None:  # 版面已重排且該頁不再存在：該輪作廢
                return
            frames = page_frame_placements(
                self._template, self._doc, self._layout, page)
            try:
                images = page_images(self._template, self._doc, self._layout,
                                     page, base_dir=self._base_dir)
            except ImageError:
                images = ()
                image_errors += 1
            cover_pages = self._layout.cover_pages
            # 封面與裝訂補頁（Sprint 144）不編頁碼
            footer = None if number <= cover_pages or page.blank else {
                "number": str(book_number_for(number, 1, cover_pages)),
                "title": self._doc.title or "",
            }
            pil_img = renderer.render_page(
                page, footer_texts=footer,
                sheet_face=sheet_face_for(number),  # 側別依紙面（Sprint 145）
                vertical=getattr(page, "vertical", self._layout.vertical),
                frames=frames, images=images, bleed_pt=self._bleed_pt)
            self.page_ready.emit(
                self._generation, number, pil_to_qimage(pil_img))
        self.all_done.emit(
            self._generation, time.perf_counter() - t0, image_errors)
