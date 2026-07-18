"""畫布檢視元件（CanvasView）：滑鼠與鍵盤事件 → EditorWindow 回呼。

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
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

# 置入圖可接受的副檔名：cjkfolio.images 以 PIL 開檔，此處取本產品實際驗過的形態
# （PNG／TIFF 灰階與 CMYK）＋一般 JPEG；CMYK JPEG 由 images.open_placed 拒收並說明。
IMAGE_SUFFIXES = (".png", ".tif", ".tiff", ".jpg", ".jpeg")


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
    on_drop(路徑, 場景座標)（置圖 UI，Sprint 102）。"""

    def __init__(self, scene: QGraphicsScene, on_pick, on_key=None,
                 on_drag=None, on_move=None, on_release=None,
                 on_drop=None) -> None:
        super().__init__(scene)
        self._on_pick = on_pick
        self._on_key = on_key
        self._on_drag = on_drag
        self._on_move = on_move
        self._on_release = on_release
        self._on_drop = on_drop
        self.setAcceptDrops(on_drop is not None)

    def _cell_item_at(self, event):
        pt = self.mapToScene(event.position().toPoint())
        for item in self.scene().items(pt):  # top-first；跳過高亮（data None）
            if item.data(0) is not None:
                return item
        return None

    def mousePressEvent(self, event) -> None:
        item = self._cell_item_at(event)
        if item is not None:
            # 場景座標一併回報：圖框拖曳的位移要以按下處為起點（Sprint 102）
            self._on_pick(item, self.mapToScene(event.position().toPoint()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._on_move is not None:
                self._on_move(self.mapToScene(event.position().toPoint()))
            if self._on_drag is not None:
                item = self._cell_item_at(event)
                if item is not None:
                    self._on_drag(item)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._on_release is not None:
            self._on_release()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._on_key is not None and self._on_key(event):
            return
        super().keyPressEvent(event)

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
