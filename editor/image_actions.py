"""置圖動作 mixin（Sprint 102）：畫布拖放置入、拖曳移動、拖角縮放、移除。

把「圖檔 → 圖框 → 文件」這條回路自 EditorWindow 抽出（同 StyleActionsMixin 與
PreflightActionsMixin 慣例，控管 app.py 行數）。分層與 preflight 面板同一條紀律：

- 判定層全在 Qt 無關的 cjkfolio.image_editing（預設尺寸、命中、控制點、縮放幾何
  皆為純函式，已由 pytest 釘死），本檔只做座標換算、預覽與提交。
- 拖曳途中只畫虛線預覽框，放開左鍵才經 session 提交一步（拖一次圖只留一步
  undo，不讓每個 mouseMove 各成一步）。
- 圖檔讀不到時據實提示並照常顯示無圖版面，不沉默略過（缺圖是使用者要知道的事）。

依賴 EditorWindow 提供的 self.session／self.doc／self.page／self.scene／
self._doc_path／self._rebuild()／self.statusBar()。
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsRectItem,
    QLabel,
    QLineEdit,
)

from cjkfolio.image_editing import default_image_rect, resize_rect
from cjkfolio.images import ImageError, open_placed
from cjkfolio.render import mm_to_pt


class WrapDialog(QDialog):
    """文繞圖設定對話框（Sprint 103）：繞排開關與圖文間隙，按確定才提交一步。

    兩個欄位一起提交＝調一次參數只留一步 undo（勾選框即時套用會使「開繞排並設
    間隙」變成兩步歷史，同 Sprint 102「放開左鍵才提交」的取捨）。錯誤以內嵌警示
    列顯示留在對話框內修正（非 modal 訊息＝離屏可驗，承 StyleEditDialog 慣例）。
    """

    def __init__(self, placed, on_apply, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("文繞圖設定")
        self._on_apply = on_apply  # callable(wrap: bool, margin_text) -> str 或 None

        form = QFormLayout(self)
        head = QLabel(f"「{placed.path}」（頁 {placed.page}）")
        head.setStyleSheet("font-weight:bold;")
        form.addRow(head)
        self._notice = QLabel("")
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)
        form.addRow(self._notice)
        self._wrap = QCheckBox("內文繞開這張圖（關閉＝圖疊在文字上）")
        self._wrap.setChecked(placed.wrap)
        form.addRow(self._wrap)
        self._margin = QLineEdit(f"{placed.wrap_margin_mm:g}")
        form.addRow("圖文間隙（mm）", self._margin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_save(self) -> None:
        err = self._on_apply(self._wrap.isChecked(), self._margin.text())
        if err:
            self._notice.setText(err)
            return
        self.accept()


class ImageActionsMixin:
    """畫布置圖 UI（§6 Phase 2 畫布延伸；GAPS #29 (d) 的接線）。"""

    # 類別層預設值＝實例未設定前的初值（不必動 EditorWindow.__init__）
    _image_idx = None       # 目前選取的置入圖索引（None＝未選）
    _image_drag = None      # 拖曳中狀態 dict：mode／origin／rect／handle／moved
    _image_outline = None   # 選取外框 item
    _image_preview = None   # 拖曳預覽框 item
    _image_aspect = None    # {解析後路徑: 寬高比}，等比縮放取來源影像比例

    # --- 座標與來源影像 ---------------------------------------------------

    def _image_scale(self) -> float:
        """畫布場景座標（px）與 trim pt 的比例（底圖 PNG 即 trim 空間）。"""
        from editor.app import DPI

        return DPI / 72.0

    def _image_base_dir(self) -> Path:
        """置入圖相對路徑的基準＝文件所在目錄（與匯出、渲染同一規則）。"""
        return self._doc_path.parent

    def _image_source_aspect(self, idx: int):
        """第 idx 張圖的來源寬高比；讀不到回 None（縮放退為自由拉框）。"""
        placed = self.doc.images[idx]
        resolved = str((self._image_base_dir() / placed.path).resolve())
        if self._image_aspect is None:
            self._image_aspect = {}
        if resolved not in self._image_aspect:
            try:
                img = open_placed(resolved)
            except ImageError:
                return None
            self._image_aspect[resolved] = img.width / img.height
        return self._image_aspect[resolved]

    # --- 置入 -------------------------------------------------------------

    def _place_image_dialog(self, path=None) -> None:
        """選單置入：選檔後放在頁面中央（拖放則放在落點，兩者共用 _place_image_at）。"""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "置入圖片", str(self._image_base_dir()),
                "影像檔 (*.png *.tif *.tiff *.jpg *.jpeg)")
        if not path:
            self.statusBar().showMessage("已取消置入圖片")
            return
        page_w = mm_to_pt(self.template.page_width_mm)
        page_h = mm_to_pt(self.template.page_height_mm)
        self._place_image_at(Path(path), page_w / 2, page_h / 2)

    def _on_image_drop(self, path, scene_pos) -> None:
        """自檔案總管拖圖檔進畫布：以放開處為圖框中心置入。"""
        scale = self._image_scale()
        self._place_image_at(Path(path), scene_pos.x() / scale,
                             scene_pos.y() / scale)

    def _place_image_at(self, path: Path, cx_pt: float, cy_pt: float) -> None:
        """在 (cx_pt, cy_pt) 為中心置入一張圖（預設尺寸依 §9 下限 300ppi 推導）。

        先開檔取像素尺寸：讀不到就在此快速失敗並提示，不先寫進文件再於渲染時炸。
        圖檔在文件目錄內時存相對路徑（文件可搬移），否則存絕對路徑。
        """
        try:
            img = open_placed(path)
        except ImageError as err:
            self.statusBar().showMessage(f"無法置入：{err}")
            return
        rect = default_image_rect(
            img.width, img.height, cx_pt, cy_pt,
            mm_to_pt(self.template.page_width_mm),
            mm_to_pt(self.template.page_height_mm))
        try:
            stored = str(path.resolve().relative_to(self._image_base_dir().resolve()))
        except ValueError:  # 不在文件目錄下：存絕對路徑（不擅自複製檔案進專案）
            stored = str(path.resolve())
        self.session.place_image(stored, self.page.number, rect)
        self._image_idx = len(self.doc.images) - 1
        self._rebuild()
        self.statusBar().showMessage(
            f"已置入「{path.name}」於頁 {self.page.number}"
            f"（{img.width}×{img.height} px，預設 300ppi 尺寸；拖曳可移動、拖角可縮放）"
        )

    # --- 選取、拖曳、縮放 -------------------------------------------------

    def _on_image_press(self, key, scene_pos=None) -> None:
        """按下圖框或角控制點：選取該圖並記下拖曳起點（提交在放開時）。"""
        idx = key[1]
        if idx >= len(self.doc.images):  # 場景與文件失步（重繪前的舊 item）
            return
        self._select_image(idx)
        if scene_pos is None:
            return
        scale = self._image_scale()
        self._image_drag = {
            "mode": "resize" if key[0] == "image-handle" else "move",
            "handle": key[2] if key[0] == "image-handle" else None,
            "origin": (scene_pos.x() / scale, scene_pos.y() / scale),
            "rect": self.doc.images[idx].rect,
            "moved": False,
        }

    def _on_image_move(self, scene_pos) -> None:
        """拖曳途中：只畫虛線預覽框（不動文件，故不產生 undo 步）。"""
        if self._image_drag is None:
            return
        self._image_drag["moved"] = True
        self._draw_image_preview(self._dragged_rect(scene_pos))

    def _on_image_release(self) -> None:
        """放開左鍵：把預覽框提交為一步編輯（未實際移動則什麼都不做）。"""
        drag = self._image_drag
        self._image_drag = None
        self._clear_image_preview()
        if drag is None or not drag["moved"] or self._image_idx is None:
            return
        rect = drag["pending"]
        if drag["mode"] == "move":
            dx = rect[0] - drag["rect"][0]
            dy = rect[1] - drag["rect"][1]
            self.session.move_image(self._image_idx, dx, dy)
            verb = "移動"
        else:
            self.session.resize_image(self._image_idx, rect)
            verb = "縮放"
        self._rebuild()
        self.statusBar().showMessage(
            f"已{verb}圖 {self._image_idx} → 圖框 "
            f"({rect[0]:.1f}, {rect[1]:.1f}, {rect[2]:.1f}, {rect[3]:.1f}) pt"
            "（Ctrl+Z 一步回原）"
        )

    def _dragged_rect(self, scene_pos) -> tuple:
        """拖曳中的新圖框（同時存進 _image_drag["pending"] 供放開時提交）。"""
        drag = self._image_drag
        scale = self._image_scale()
        x_pt, y_pt = scene_pos.x() / scale, scene_pos.y() / scale
        x0, y0, x1, y1 = drag["rect"]
        if drag["mode"] == "move":
            dx = x_pt - drag["origin"][0]
            dy = y_pt - drag["origin"][1]
            rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        else:
            rect = resize_rect(drag["rect"], drag["handle"], x_pt, y_pt,
                               aspect=self._image_source_aspect(self._image_idx))
        drag["pending"] = rect
        return rect

    def _select_image(self, idx) -> None:
        """設定／清除置入圖選取並重畫外框（None＝清除）。"""
        self._image_idx = idx
        if self._image_outline is not None:
            self.scene.removeItem(self._image_outline)
            self._image_outline = None
        if idx is None or idx >= len(self.doc.images):
            return
        rect = self.doc.images[idx].rect
        if rect is None:  # 槽式圖無座標（不可拖放，image_editing 模組說明）
            return
        placed = self.doc.images[idx]
        self._image_outline = self._add_frame_item(
            rect, QColor(20, 110, 220), Qt.PenStyle.SolidLine, z=4)
        self.statusBar().showMessage(
            f"已選取圖 {idx}「{placed.path}」｜拖曳圖框移動、拖四角控制點等比縮放、"
            "Delete 移除（皆可 Ctrl+Z 回原）"
        )

    def _draw_image_preview(self, rect) -> None:
        """拖曳預覽：虛線框（不寫文件，放開才提交）。"""
        self._clear_image_preview()
        self._image_preview = self._add_frame_item(
            rect, QColor(220, 30, 30), Qt.PenStyle.DashLine, z=6)

    def _clear_image_preview(self) -> None:
        if self._image_preview is not None:
            self.scene.removeItem(self._image_preview)
            self._image_preview = None

    def _add_frame_item(self, rect, color, style, z: float):
        """在場景畫一個無填充的框（選取外框與拖曳預覽共用）。"""
        scale = self._image_scale()
        x0, y0, x1, y1 = rect
        item = QGraphicsRectItem(x0 * scale, y0 * scale,
                                 (x1 - x0) * scale, (y1 - y0) * scale)
        pen = QPen(color, 1.5)
        pen.setStyle(style)
        item.setPen(pen)
        item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        item.setZValue(z)
        self.scene.addItem(item)
        return item

    # --- 繞排參數（Sprint 103） -------------------------------------------

    def _edit_image_wrap(self, wrap=None, margin_text=None) -> None:
        """選取圖的文繞圖設定（wrap 開關與 wrap_margin_mm 間隙）。

        真視窗開對話框；帶參數呼叫則旁路對話框直接套用（離屏 smoke 可驗，承
        _create_style 慣例）。未選取圖時據實提示（不猜使用者指的是哪張）。
        """
        if self._image_idx is None or self._image_idx >= len(self.doc.images):
            self.statusBar().showMessage("先點選一張置入圖，再設定文繞圖")
            return
        placed = self.doc.images[self._image_idx]
        if wrap is None and margin_text is None:
            WrapDialog(placed, self._apply_image_wrap, self).exec()
            return
        err = self._apply_image_wrap(
            placed.wrap if wrap is None else wrap,
            placed.wrap_margin_mm if margin_text is None else margin_text)
        if err:
            self.statusBar().showMessage(err)

    def _apply_image_wrap(self, wrap: bool, margin_text) -> str | None:
        """套用繞排參數；回錯誤訊息（留在對話框修正）或 None（成功／無變更）。

        間隙以字串進來（對話框輸入框），數字轉換的失敗留在此層報給使用者，不讓
        非數字一路傳到核心才炸。
        """
        try:
            margin_mm = float(margin_text)
        except (TypeError, ValueError):
            return f"間隙需為數字（毫米），得到「{margin_text}」"
        idx = self._image_idx
        try:
            res = self.session.set_image_wrap(idx, wrap=wrap, margin_mm=margin_mm)
        except ValueError as err:
            return f"無法設定文繞圖：{err}"
        if res is None:
            self.statusBar().showMessage("文繞圖設定未變更")
            return None
        self._rebuild()
        state = f"開啟（間隙 {margin_mm:g} mm）" if wrap else "關閉"
        self.statusBar().showMessage(
            f"圖 {idx} 文繞圖已{state}，內文已重排（Ctrl+Z 一步回原）")
        return None

    # --- 移除 -------------------------------------------------------------

    def _remove_selected_image(self) -> bool:
        """移除選取的置入圖（Delete 鍵與選單共用）；未選取回 False 交回原處理。"""
        if self._image_idx is None or self._image_idx >= len(self.doc.images):
            return False
        idx = self._image_idx
        path = self.doc.images[idx].path
        self.session.remove_image(idx)
        self._image_idx = None
        self._rebuild()
        self.statusBar().showMessage(f"已移除圖 {idx}「{path}」（Ctrl+Z 可回原）")
        return True
