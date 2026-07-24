"""畫布檢視元件（CanvasView）：滑鼠與鍵盤事件 → EditorWindow 回呼，縮放與平移。

自 editor/app.py 抽出（Sprint 102 行數紀律分檔，先例 Sprint 93 pdf_objects／
Sprint 101 smoke_preflight）：搬移時 mousePress／mouseMove／keyPress 三個回呼
的行為逐字不變，本 Sprint 新增的是置圖 UI 需要的三件事：

- on_move(scene_pos)：按住左鍵移動時回報場景座標（圖框拖曳與縮放要的是座標，
  不是游標下的 item），拖曳途中只畫預覽、不提交，避免每個 mouseMove 都灌一步
  undo（拖一次圖就吃掉數十步歷史）。
- on_release()：放開左鍵才提交一步（InDesign 的拖曳語意）。
- on_drop(path, scene_pos)：自檔案總管拖圖檔進畫布即置入落點。

拖放只接受副檔名在 IMAGE_SUFFIXES 內的本機檔案；其餘一律不接受（dragEnter
即拒絕），不猜測未知格式再於稍後失敗。

縮放與平移（Sprint 124）：
- Ctrl+滾輪＝以游標位置為錨縮放（每格 1.25 倍，clamp 10%〜800%）；
  set_zoom／zoom_in／zoom_out／fit_page／fit_width 供「檢視」選單與快捷鍵
  呼叫，倍率變動一律經 on_zoom(factor) 回報（app 狀態列百分比跟隨）。
- Shift+滾輪＝水平捲動（明確實作，不賴平台預設）；素滾輪維持垂直捲動。
- 中鍵拖曳、按住空白鍵＋左鍵拖曳＝平移（InDesign 手形語意）；平移中不觸發
  點選／範圍選取／置圖拖曳回呼（按下即被平移吃掉，游標與選取維持原狀）。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

# 置入圖可接受的副檔名：cjkfolio.images 以 PIL 開檔，此處取本產品實際驗過的形態
# （PNG／TIFF 灰階與 CMYK）＋一般 JPEG；CMYK JPEG 由 images.open_placed 拒收並說明。
IMAGE_SUFFIXES = (".png", ".tif", ".tiff", ".jpg", ".jpeg")

# 縮放邊界與滾輪步進（Sprint 124）：100%＝底圖 150dpi 像素 1:1；
# 1.25 倍/格為常見編輯器步進（InDesign／PDF 閱讀器同量級）。
ZOOM_MIN = 0.1
ZOOM_MAX = 8.0
ZOOM_STEP = 1.25


def _dropped_image_path(mime):
    """自拖放載荷取第一個可接受的本機圖檔路徑；沒有則回 None。"""
    if not mime.hasUrls():
        return None
    for url in mime.urls():
        if not url.isLocalFile():
            continue
        path = Path(url.toLocalFile())
        if path.suffix.lower() in IMAGE_SUFFIXES:
            return path
    return None


class CanvasView(QGraphicsView):
    """點畫布 → 反查最上層帶 provenance 的字格 item，回呼 on_pick(item)；
    按住左鍵拖曳過字格 → 回呼 on_drag(item)（範圍選取，Sprint 65）；
    鍵盤事件（Backspace／Delete／Enter／PgUp／PgDn）回呼 on_key(event)（Sprint 62）；
    按住左鍵移動 → on_move(場景座標)、放開 → on_release()、拖入圖檔 →
    on_drop(路徑, 場景座標)（置圖 UI，Sprint 102）；
    Ctrl+滾輪縮放（游標錨）／Shift+滾輪水平捲動／中鍵或空白鍵拖曳平移，
    倍率變動回呼 on_zoom(factor)（Sprint 124）。"""

    def __init__(self, scene: QGraphicsScene, on_pick, on_key=None,
                 on_drag=None, on_move=None, on_release=None,
                 on_drop=None, on_zoom=None) -> None:
        super().__init__(scene)
        self._on_pick = on_pick
        self._on_key = on_key
        self._on_drag = on_drag
        self._on_move = on_move
        self._on_release = on_release
        self._on_drop = on_drop
        self._on_zoom = on_zoom
        self._space_pan = False  # 空白鍵按住＝手形平移模式（InDesign 慣例）
        self._pan_last = None    # 平移拖曳前一點（viewport 座標）；None＝未在平移
        self.setAcceptDrops(on_drop is not None)

    # ---- 縮放 API（「檢視」選單、快捷鍵與 Ctrl+滾輪共用） ----

    def zoom_factor(self) -> float:
        """目前縮放倍率（1.0＝100%＝底圖 150dpi 像素 1:1）。"""
        return self.transform().m11()

    def set_zoom(self, factor: float, anchor=None) -> None:
        """設定絕對縮放倍率（clamp 於 ZOOM_MIN〜ZOOM_MAX）；anchor 預設視圖中心。"""
        factor = max(ZOOM_MIN, min(ZOOM_MAX, factor))
        self.setTransformationAnchor(
            anchor if anchor is not None
            else QGraphicsView.ViewportAnchor.AnchorViewCenter)
        ratio = factor / self.zoom_factor()
        self.scale(ratio, ratio)
        self._emit_zoom()

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom_factor() * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom_factor() / ZOOM_STEP)

    def fit_page(self) -> None:
        """整頁入視窗（含空白文件的空紙面；空 scene 不動作）。"""
        scene = self.scene()
        rect = scene.sceneRect() if scene is not None else None
        if rect is None or rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        z = self.zoom_factor()
        if not ZOOM_MIN <= z <= ZOOM_MAX:  # 極端視窗尺寸：夾回邊界（set_zoom 會回報）
            self.set_zoom(z)
            return
        self._emit_zoom()

    def fit_width(self) -> None:
        """符合寬度：頁寬貼齊視窗寬（預留垂直捲軸），水平置中、垂直位置維持。"""
        scene = self.scene()
        rect = scene.sceneRect() if scene is not None else None
        if rect is None or rect.width() <= 0:
            return
        vw = self.viewport().width()
        if rect.height() * (vw / rect.width()) > self.viewport().height():
            vw -= self.verticalScrollBar().sizeHint().width()  # 縮放後必出垂直捲軸
        if vw <= 0:
            return
        center_y = self.mapToScene(self.viewport().rect().center()).y()
        self.set_zoom(vw / rect.width())
        self.centerOn(rect.center().x(), center_y)

    def _emit_zoom(self) -> None:
        if self._on_zoom is not None:
            self._on_zoom(self.zoom_factor())

    # ---- 平移（中鍵拖曳／空白鍵＋左鍵拖曳） ----

    def _start_pan(self, event) -> None:
        self._pan_last = event.position()
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def _pan_move(self, event) -> None:
        d = event.position() - self._pan_last
        self._pan_last = event.position()
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        h.setValue(h.value() - round(d.x()))
        v.setValue(v.value() - round(d.y()))

    def _end_pan(self) -> None:
        self._pan_last = None
        self.viewport().setCursor(
            Qt.CursorShape.OpenHandCursor if self._space_pan
            else Qt.CursorShape.ArrowCursor)

    # ---- 事件處理 ----

    def _cell_item_at(self, event):
        pt = self.mapToScene(event.position().toPoint())
        for item in self.scene().items(pt):  # top-first；跳過高亮（data None）
            if item.data(0) is not None:
                return item
        return None

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y() or event.angleDelta().x()
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            if delta:  # 高解析裝置給非 120 倍數：以 delta/120 為指數平滑縮放
                self.set_zoom(
                    self.zoom_factor() * ZOOM_STEP ** (delta / 120.0),
                    anchor=QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            event.accept()
            return
        if mods & Qt.KeyboardModifier.ShiftModifier:  # 滾輪向下＝往右（瀏覽器慣例）
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            event.accept()
            return
        super().wheelEvent(event)  # 素滾輪＝垂直捲動（QGraphicsView 預設）

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or (
                self._space_pan and event.button() == Qt.MouseButton.LeftButton):
            self._start_pan(event)  # 平移吃掉按下：不觸發點選，游標與選取維持原狀
            event.accept()
            return
        item = self._cell_item_at(event)
        if item is not None:
            # 場景座標一併回報：圖框拖曳的位移要以按下處為起點（Sprint 102）
            self._on_pick(item, self.mapToScene(event.position().toPoint()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pan_last is not None:
            self._pan_move(event)
            event.accept()
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._on_move is not None:
                self._on_move(self.mapToScene(event.position().toPoint()))
            if self._on_drag is not None:
                item = self._cell_item_at(event)
                if item is not None:
                    self._on_drag(item)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._pan_last is not None:
            self._end_pan()  # 平移收尾不走 on_release（沒有置圖拖曳要提交）
            event.accept()
            return
        if self._on_release is not None:
            self._on_release()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan = True
            if self._pan_last is None:
                self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if self._on_key is not None and self._on_key(event):
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan = False
            if self._pan_last is None:  # 拖曳中放開空白鍵：讓本次拖完再還原游標
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def dragEnterEvent(self, event) -> None:
        if self._on_drop is not None and _dropped_image_path(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._on_drop is not None and _dropped_image_path(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        path = _dropped_image_path(event.mimeData())
        if self._on_drop is None or path is None:
            event.ignore()
            return
        self._on_drop(path, self.mapToScene(event.position().toPoint()))
        event.acceptProposedAction()
