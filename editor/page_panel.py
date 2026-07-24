"""頁面面板（Sprint 125）：全書縮圖列表＋點選跳頁＋目前頁高亮。

出版工作流補完系列甲3（PLAN Phase 5 盤點）：128 頁真稿過去只能 PgDn 盲翻，
本面板給「全書地圖」。對標 InDesign 頁面面板的檢視與跳頁兩用途（主版指派
等進階操作屬 Sprint 130）。

縮圖渲染走背景執行緒（QThread，preflight_actions.PreflightThread 同慣例）：

- worker 收 doc／template／layout 不可變快照，逐頁以低 DPI（THUMB_DPI）建
  自己的 PageRenderer 渲染（render.py 全狀態 per-instance、無模組級快取，
  與主執行緒畫布渲染並行安全；preflight 背景匯出為既有先例）。
- QPixmap 只能在 GUI 執行緒建：worker 逐頁 emit QImage（pil_to_qimage 已
  copy，跨執行緒傳值安全），面板在 GUI slot 轉 QPixmap。
- 置入圖讀不到時該頁縮圖以無圖版面渲染並計數（不炸也不沉默：完成訊號帶
  計數，調度端於 statusBar 據實提示；主畫布對同一缺圖另有既有提示）。
- 取消協作：cancel() 設旗標，worker 於每頁迴圈頂檢查後提前收工（單頁渲染
  中不可中斷，代價為一頁的時間）。世代守門在調度端（nav_actions）。
"""
import time

from PySide6.QtCore import QSize, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from cjkfolio.images import ImageError
from cjkfolio.render import PageRenderer
from editor.canvas import page_frame_placements, page_images, pil_to_qimage

THUMB_DPI = 18          # A5 148×210mm → 約 105×149px（灰階，128 頁約 8MB 級）
THUMB_W = 106           # 占位圖尺寸取 A5 @18dpi 整數化；實際 icon 依渲染像素
THUMB_H = 149


class ThumbnailThread(QThread):
    """背景逐頁渲染縮圖（doc／template／layout 為不可變快照）。"""

    page_ready = Signal(int, int, object)   # (generation, page_number, QImage)
    all_done = Signal(int, float, int)      # (generation, 耗時秒, 缺圖頁數)

    def __init__(self, generation: int, doc, template, layout, base_dir,
                 dpi: int = THUMB_DPI, parent=None) -> None:
        super().__init__(parent)
        self._generation = generation
        self._doc = doc
        self._template = template
        self._layout = layout
        self._base_dir = base_dir
        self._dpi = dpi
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        t0 = time.perf_counter()
        renderer = PageRenderer(self._template, self._doc.master, dpi=self._dpi)
        image_error_pages = 0
        for page in self._layout.pages:
            if self._cancelled:  # 提前收工：不發 all_done（該輪已作廢）
                return
            frames = page_frame_placements(
                self._template, self._doc, self._layout, page)
            try:
                images = page_images(self._template, self._doc, self._layout,
                                     page, base_dir=self._base_dir)
            except ImageError:
                images = ()
                image_error_pages += 1
            vertical = getattr(page, "vertical", self._layout.vertical)
            footer = {"number": str(page.number), "title": self._doc.title or ""}
            pil_img = renderer.render_page(
                page, footer_texts=footer, book_number=page.number,
                vertical=vertical, frames=frames, images=images)
            self.page_ready.emit(
                self._generation, page.number, pil_to_qimage(pil_img))
        self.all_done.emit(
            self._generation, time.perf_counter() - t0, image_error_pages)


class PagePanel(QListWidget):
    """縮圖列表：icon 上、「頁 N」下（IconMode）；點選＝跳頁回呼。

    只有真點擊（itemClicked）觸發跳頁；程式面 set_current 不觸發，
    不會與 _rebuild 互相遞迴。
    """

    def __init__(self, on_goto, parent=None) -> None:
        super().__init__(parent)
        self._on_goto = on_goto
        self.setMinimumWidth(THUMB_W + 34)  # icon＋捲軸與邊距（單欄下限）
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWrapping(True)
        self.setIconSize(QSize(THUMB_W, THUMB_H))
        self.setUniformItemSizes(True)
        self.itemClicked.connect(
            lambda item: self._on_goto(self.row(item) + 1))

    def sizeHint(self) -> QSize:
        """dock 初始寬取單欄縮圖寬（QListView 預設 sizeHint 約 256px，會把
        小視窗的畫布壓到不可用；高度由 dock 佈局拉伸，此值無實效）。"""
        return QSize(THUMB_W + 34, 400)

    def _placeholder_icon(self) -> QIcon:
        pixmap = QPixmap(THUMB_W, THUMB_H)
        pixmap.fill(QColor("#e6e6e6"))  # 渲染到位前的灰紙面占位
        return QIcon(pixmap)

    def set_page_count(self, count: int) -> None:
        """頁數不變時保留既有縮圖（編輯多數不改頁數，漸進换新不閃灰）。"""
        if self.count() == count:
            return
        self.clear()
        placeholder = self._placeholder_icon()
        for number in range(1, count + 1):
            self.addItem(QListWidgetItem(placeholder, f"頁 {number}"))

    def set_current(self, number) -> None:
        self.setCurrentRow(number - 1 if number else -1)

    def set_thumbnail(self, number: int, qimage) -> None:
        if 1 <= number <= self.count():
            self.item(number - 1).setIcon(QIcon(QPixmap.fromImage(qimage)))
