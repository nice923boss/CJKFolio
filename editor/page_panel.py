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

from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from cjkfolio.images import ImageError
from cjkfolio.primitives import book_number_for
from cjkfolio.render import PageRenderer
from editor.canvas import page_frame_placements, page_images, pil_to_qimage

THUMB_DPI = 18          # A5 148×210mm → 約 105×149px（RGB，128 頁約 8MB 級）
THUMB_W = 106           # 占位圖尺寸取 A5 @18dpi 整數化；實際 icon 依渲染像素
THUMB_H = 149


def thumbnail_footer(page_number: int, cover_pages: int, title: str,
                     blank: bool = False):
    """縮圖的頁腳內容；封面與裝訂補頁回 None（不編頁碼）。

    Sprint 132 的書頁號位移原漏了本處（Gate 3 只掃到兩後端、wrap、toc 與主畫布
    五處）：縮圖直接拿版面頁號當書頁號，帶封面時整份縮圖的頁碼會比實際大 1，
    且封面縮圖會印出頁碼。Sprint 133 補上並以純函式釘死。
    blank＝裝訂補頁（Sprint 144，LayoutPage.blank）：空白頁不編頁碼，同封面。
    """
    if page_number <= cover_pages or blank:
        return None
    return {"number": str(book_number_for(page_number, 1, cover_pages)),
            "title": title or ""}


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
            cover_pages = self._layout.cover_pages
            footer = thumbnail_footer(page.number, cover_pages, self._doc.title,
                                      blank=page.blank)
            pil_img = renderer.render_page(
                page, footer_texts=footer,
                book_number=book_number_for(page.number, 1, cover_pages),
                vertical=vertical, frames=frames, images=images)
            self.page_ready.emit(
                self._generation, page.number, pil_to_qimage(pil_img))
        self.all_done.emit(
            self._generation, time.perf_counter() - t0, image_error_pages)


def drop_index(bands, x: float, y: float) -> int:
    """插入位＝流序上排在放下點之前的縮圖數（純函式，離屏可驗）。

    bands＝各縮圖的 (top, bottom, 中心 x)，依流序。IconMode 會換行成多欄，故先比
    列帶（整項在放下點上方＝在前）、同列帶內再比欄位（中心在放下點左側＝在前）。
    放下點落在所有縮圖之後回 len(bands)＝搬到最末。
    """
    return sum(1 for top, bottom, cx in bands
               if bottom < y or (top <= y and cx < x))


class PagePanel(QListWidget):
    """縮圖列表：icon 上、「頁 N」下（IconMode）；點選＝跳頁回呼。

    只有真點擊（itemClicked）觸發跳頁；程式面 set_current 不觸發，
    不會與 _rebuild 互相遞迴。

    拖曳重排（Sprint 142，給 on_reorder 才開）：本面板不動 Qt 的模型，只把
    （來源頁號, 插入位頁號）交回呼，由文件層搬節後全書重排、面板整份重建。故
    dropEvent 一律 ignore（讓 QDrag 收 IgnoreAction，Qt 不會自行刪列），插入線
    也自繪（IconMode 的內建 drop indicator 恆為 OnViewport，畫不出插入位）。
    """

    def __init__(self, on_goto, on_context_menu=None, on_reorder=None,
                 parent=None) -> None:
        super().__init__(parent)
        self._on_goto = on_goto
        self._on_context_menu = on_context_menu
        self._on_reorder = on_reorder
        self._drop_row = -1  # 拖曳途中的插入位（-1＝無）
        self.setMinimumWidth(THUMB_W + 34)  # icon＋捲軸與邊距（單欄下限）
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        if on_reorder is None:
            self.setMovement(QListWidget.Movement.Static)
        else:
            # Static 會連拖曳一起關掉（QListView::setMovement 內設 dragEnabled），
            # 故改 Snap；順序必須在 setDragDropMode 之前，否則旗標被蓋回去。
            self.setMovement(QListWidget.Movement.Snap)
            self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
            self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setWrapping(True)
        self.setIconSize(QSize(THUMB_W, THUMB_H))
        self.setUniformItemSizes(True)
        self.itemClicked.connect(
            lambda item: self._on_goto(self.row(item) + 1))
        if on_context_menu is not None:  # 右鍵指派主版（Sprint 130）
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._emit_context_menu)

    def _emit_context_menu(self, pos) -> None:
        """把面板本地座標的右鍵轉成（頁碼, 全域座標）交回呼；空白處不觸發。"""
        row = self.indexAt(pos).row()
        if row < 0:
            return
        self._on_context_menu(row + 1, self.viewport().mapToGlobal(pos))

    # ---------- 拖曳重排 ----------

    def _row_rect(self, row: int):
        """第 row 列的 viewport 矩形；越界回 None。"""
        if 0 <= row < self.count():
            return self.visualItemRect(self.item(row))
        return None

    def drop_row_at(self, x: float, y: float) -> int:
        """放下點（viewport 座標）對應的插入位（0..頁數）。"""
        bands = []
        for row in range(self.count()):
            r = self.visualItemRect(self.item(row))
            bands.append((r.top(), r.bottom(), r.center().x()))
        return drop_index(bands, x, y)

    def _marker_line(self):
        """插入線兩端點 (x1, y1, x2, y2)：單欄畫上緣橫線、多欄畫前緣直線。"""
        n = self.count()
        if not 0 <= self._drop_row <= n or n == 0:
            return None
        tail = self._drop_row >= n  # 放到最末：畫在末項的後緣
        rect = self._row_rect(n - 1 if tail else self._drop_row)
        prev = self._row_rect((n - 1 if tail else self._drop_row) - 1)
        if prev is not None and prev.top() == rect.top():  # 與前項同列帶＝多欄
            x = rect.right() if tail else rect.left()
            return (x, rect.top(), x, rect.bottom())
        y = rect.bottom() if tail else rect.top()
        return (rect.left(), y, rect.right(), y)

    def _set_drop_row(self, row: int) -> None:
        if row != self._drop_row:
            self._drop_row = row
            self.viewport().update()

    def dragMoveEvent(self, event) -> None:
        super().dragMoveEvent(event)
        pos = event.position()
        self._set_drop_row(self.drop_row_at(pos.x(), pos.y()))

    def dragLeaveEvent(self, event) -> None:
        self._set_drop_row(-1)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        """把（來源頁號, 插入位頁號）交回呼；Qt 的內建搬移一律不執行。"""
        pos = event.position()
        dst = self.drop_row_at(pos.x(), pos.y())
        src = self.currentRow()
        self._set_drop_row(-1)
        event.ignore()  # 搬的是文件的節，不是清單的列（見類別說明）
        if self._on_reorder is not None and src >= 0:
            self._on_reorder(src + 1, dst + 1)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        line = self._marker_line()
        if line is None:
            return
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor("#0a66c2"), 3))
        painter.drawLine(*line)
        painter.end()

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
