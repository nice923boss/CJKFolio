"""文字框框級動作 mixin（Sprint 136）：整框的新增、拖曳移動、拖角縮放、移除。

Owner 真視窗回饋：封面放了圖之後，預設書名框既刪不掉（刪到最後一字撞
document@2「框 text 非空」不變式）也搬不動（框只有字格可點，框本身沒有命中區）。
本檔補的就是「框**本身**」這一層 UI；框**內**的字仍走既有 edit_actions 那條路。

分層與 ImageActionsMixin 同一條紀律：
- 判定層全在 Qt 無關的 cjkfolio.frame_box_editing（新框幾何、平移、縮放、移除與
  鏈首文字承接皆為純函式，已由 pytest 釘死），本檔只做座標換算、預覽與提交。
- 拖曳途中只畫虛線預覽框，放開左鍵才經 session 提交一步（拖一次框只留一步 undo）。
- 座標換算與外框繪製直接用 ImageActionsMixin 的 _image_scale／_add_frame_item
  （兩者同屬 EditorWindow，scene 與 trim pt 的換算只該有一份）。

選取語意：框內點在**字**上得字游標（打字為主要操作），點在框內**空白處**才選中
整個框（互動層 z=0.5 低於字格，見 canvas.build_page_scene）。內文頁的版心被 body
字格鋪滿，落在版心內的框點不到空白處，故另備選單「選取本頁文字框」的入口。

依賴 EditorWindow 提供的 self.session／self.doc／self.page／self.scene／
self.template／self._rebuild()／self.statusBar()。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QGraphicsRectItem, QInputDialog

from cjkfolio.frame_box_editing import default_frame_rect
from cjkfolio.image_editing import HANDLE_SIZE_PT, handle_rects, resize_rect
from cjkfolio.render import mm_to_pt

FRAME_BOX_COLOR = QColor(20, 150, 90)  # 框選取外框（綠）：與圖片選取（藍）分得開
EDGE_BAND_PT = 8.0  # 選取後的邊框拖曳帶寬（同角控制點邊長，手感一致）


def _edge_bands(rect) -> tuple:
    """框四邊的窄帶矩形（上下左右各一，內縮 EDGE_BAND_PT）。

    小框的四帶會互相重疊，重疊處先命中誰都是同一個框，故不另做避讓；帶寬最多
    取半寬與半高，免得窄框的帶反而蓋滿整框。
    """
    x0, y0, x1, y1 = rect
    b = min(EDGE_BAND_PT, (x1 - x0) / 2, (y1 - y0) / 2)
    return ((x0, y0, x1, y0 + b), (x0, y1 - b, x1, y1),
            (x0, y0, x0 + b, y1), (x1 - b, y0, x1, y1))


class FrameBoxActionsMixin:
    """文字框整框編輯 UI（補 GAPS #32 的「框全刪空」與框級拖放）。"""

    # 類別層預設值＝實例未設定前的初值（不必動 EditorWindow.__init__）
    _frame_box_idx = None       # 目前選取的文字框索引（None＝未選）
    _frame_box_drag = None      # 拖曳中狀態 dict：mode／origin／rect／handle／moved
    _frame_box_outline = None   # 選取外框 item
    _frame_box_preview = None   # 拖曳預覽框 item
    _frame_box_handles = ()     # 角控制點 item（選取時才建，故只有選取框可拖角）

    # --- 選取、拖曳、縮放 -------------------------------------------------

    def _on_frame_box_press(self, key, scene_pos=None) -> None:
        """按下框拖曳區或角控制點：選取該框並記下拖曳起點（提交在放開時）。"""
        idx = key[1]
        if idx >= len(self.doc.text_frames):  # 場景與文件失步（重繪前的舊 item）
            return
        self._select_frame_box(idx)
        if scene_pos is None:
            return
        scale = self._image_scale()
        self._frame_box_drag = {
            "mode": "resize" if key[0] == "frame-handle" else "move",
            "handle": key[2] if key[0] == "frame-handle" else None,
            "origin": (scene_pos.x() / scale, scene_pos.y() / scale),
            "rect": self.doc.text_frames[idx].rect,
            "moved": False,
        }

    def _on_frame_box_move(self, scene_pos) -> None:
        """拖曳途中：只畫虛線預覽框（不動文件，故不產生 undo 步）。"""
        if self._frame_box_drag is None:
            return
        self._frame_box_drag["moved"] = True
        self._draw_frame_box_preview(self._dragged_frame_rect(scene_pos))

    def _on_frame_box_release(self) -> None:
        """放開左鍵：把預覽框提交為一步編輯（未實際移動則什麼都不做）。"""
        drag = self._frame_box_drag
        self._frame_box_drag = None
        self._clear_frame_box_preview()
        if drag is None or not drag["moved"] or self._frame_box_idx is None:
            return
        idx = self._frame_box_idx
        rect = drag["pending"]
        if drag["mode"] == "move":
            dx = rect[0] - drag["rect"][0]
            dy = rect[1] - drag["rect"][1]
            self.session.move_text_frame(idx, dx, dy)
            verb = "移動"
        else:
            try:
                self.session.resize_text_frame(idx, rect)
            except ValueError as err:  # 拖成零寬或零高（正規化擋下）
                self.statusBar().showMessage(f"無法縮放文字框：{err}")
                return
            verb = "縮放"
        self._rebuild()
        self.statusBar().showMessage(
            f"已{verb}文字框 {idx} → 框 "
            f"({rect[0]:.1f}, {rect[1]:.1f}, {rect[2]:.1f}, {rect[3]:.1f}) pt"
            f"{self._frame_overflow_note(idx)}（Ctrl+Z 一步回原）"
        )

    def _dragged_frame_rect(self, scene_pos) -> tuple:
        """拖曳中的新框（同時存進 _frame_box_drag["pending"] 供放開時提交）。

        不鎖長寬比：文字框的形狀決定每欄字數與欄數，等比縮放反而綁死排版
        （圖片鎖比例是為了不變形，文字框沒有這個問題）。
        """
        drag = self._frame_box_drag
        scale = self._image_scale()
        x_pt, y_pt = scene_pos.x() / scale, scene_pos.y() / scale
        x0, y0, x1, y1 = drag["rect"]
        if drag["mode"] == "move":
            dx = x_pt - drag["origin"][0]
            dy = y_pt - drag["origin"][1]
            rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        else:
            rect = resize_rect(drag["rect"], drag["handle"], x_pt, y_pt)
        drag["pending"] = rect
        return rect

    def _select_frame_box(self, idx) -> None:
        """設定／清除文字框選取並重畫外框、邊框拖曳帶與角控制點（None＝清除）。

        這三樣只為**選取中**的框建，故直接加進 scene 而不動 build_page_scene 的
        簽名：CanvasView 的命中掃的是 scene 內帶 data(0) 的 item，不是
        build_page_scene 的回傳表。理由：滿頁的框若都掛控制點與拖曳帶，畫布就
        點不到字了。

        拖曳帶只鋪四邊的窄帶而不鋪滿整框（z=4 高於置入圖 z=2 與字格 z=1）：鋪滿
        會把框內的字與其下的圖一併蓋掉，選了框就再也點不到字；只鋪邊框則框內照
        常點字，邊框可搬框，兩者並存。封面滿版圖蓋住書名框時，這條窄帶就是唯一
        搬得動書名框的地方，故它必須高於圖。
        """
        self._frame_box_idx = idx
        if self._frame_box_outline is not None:
            self.scene.removeItem(self._frame_box_outline)
            self._frame_box_outline = None
        for item in self._frame_box_handles:
            self.scene.removeItem(item)
        self._frame_box_handles = ()
        if idx is None or idx >= len(self.doc.text_frames):
            return
        frame = self.doc.text_frames[idx]
        if self.page is None or frame.page != self.page.number:
            return  # 選取框不在本頁：不畫（框仍為選取態，選單移除照常可用）
        self._frame_box_outline = self._add_frame_item(
            frame.rect, FRAME_BOX_COLOR, Qt.PenStyle.SolidLine, z=4)
        bands = tuple(self._add_frame_chrome(r, ("frame-box", idx), z=4,
                                             fill=None)
                      for r in _edge_bands(frame.rect))
        handles = tuple(
            self._add_frame_chrome(hrect, ("frame-handle", idx, name), z=5,
                                   fill=FRAME_BOX_COLOR)
            for name, hrect in handle_rects(frame.rect, HANDLE_SIZE_PT).items())
        self._frame_box_handles = bands + handles
        self.statusBar().showMessage(
            f"已選取文字框 {idx}「{frame.text[:10]}」｜拖框邊移動、拖四角控制點改大小、"
            "Delete 移除整個框（皆可 Ctrl+Z 回原）"
        )

    def _add_frame_chrome(self, rect, key: tuple, z: float, fill):
        """畫一個帶命中鍵的方塊（角控制點填色可見，拖曳帶透明只作命中區）。"""
        scale = self._image_scale()
        x0, y0, x1, y1 = rect
        item = QGraphicsRectItem(x0 * scale, y0 * scale,
                                 (x1 - x0) * scale, (y1 - y0) * scale)
        item.setPen(Qt.NoPen)
        item.setBrush(QBrush(fill if fill is not None else QColor(0, 0, 0, 0)))
        item.setZValue(z)
        item.setData(0, key)
        self.scene.addItem(item)
        return item

    def _draw_frame_box_preview(self, rect) -> None:
        """拖曳預覽：虛線框（不寫文件，放開才提交）。"""
        self._clear_frame_box_preview()
        self._frame_box_preview = self._add_frame_item(
            rect, QColor(220, 30, 30), Qt.PenStyle.DashLine, z=6)

    def _clear_frame_box_preview(self) -> None:
        if self._frame_box_preview is not None:
            self.scene.removeItem(self._frame_box_preview)
            self._frame_box_preview = None

    def _frame_overflow_note(self, idx: int) -> str:
        """框裝不下字、或框自己跑出頁面時的提示（兩種都是「字看不見」）。

        後者是拖曳才會發生的（Sprint 136）：本專案沒有 InDesign 的貼板概念，框拖
        出紙面就整個不畫，既不違規也不報錯，使用者只會看到字憑空消失。既然搬框是
        這一輪新開的能力，就不讓它製造第二種「我的字呢」。夾界不是解法（貼齊邊緣
        排版是正當需求），據實說出來才是。
        """
        for placement in self._page_frame_placements():
            if placement.frame_idx == idx and placement.violations:
                return "，文字放不下（框太小，字已溢出）"
        x0, y0, x1, y1 = self.doc.text_frames[idx].rect
        page_w = mm_to_pt(self.template.page_width_mm)
        page_h = mm_to_pt(self.template.page_height_mm)
        if x1 <= 0 or y1 <= 0 or x0 >= page_w or y0 >= page_h:
            return "，框已整個移出頁面（畫面上看不到，Ctrl+Z 可回原位）"
        if x0 < 0 or y0 < 0 or x1 > page_w or y1 > page_h:
            return "，框有一部分在頁面外（該處的字不會印出來）"
        return ""

    def _page_frame_placements(self) -> tuple:
        """本頁文字框 placements（溢出提示用；缺頁或解析失敗回空）。"""
        from editor.canvas import page_frame_placements

        if self.page is None:
            return ()
        return page_frame_placements(self.template, self.doc,
                                     self.layout_result, self.page)

    # --- 新增 -------------------------------------------------------------

    def _add_text_frame_dialog(self, text=None) -> None:
        """新增文字框：問文字後放在頁面中央（框大小依樣式級數與網格推導）。

        真視窗開輸入框；帶 text 呼叫則旁路對話框直接新增（離屏 smoke 可驗，承
        _edit_image_wrap 慣例）。空文字不成框（document@2 要求框 text 非空），
        據實提示而非默默建一個看不見的空框。
        """
        if self.page is None:
            self.statusBar().showMessage("空白文件尚無頁面，先匯入稿件或打字再新增文字框")
            return
        if text is None:
            text, ok = QInputDialog.getText(
                self, "新增文字框", "框內文字（可之後在畫布上點字繼續編輯）：")
            if not ok:
                self.statusBar().showMessage("已取消新增文字框")
                return
        text = (text or "").strip()
        if not text:
            self.statusBar().showMessage("新增文字框需有文字（空框不成立）")
            return
        style = self.template.md_mapping.get("paragraph", "")
        if style not in self.template.paragraph_styles:
            self.statusBar().showMessage(
                "模版 md_mapping 未宣告 paragraph（內文樣式），無法決定新框樣式")
            return
        master = self.template.masters[
            getattr(self.page, "master", "") or self.doc.master]
        rect = default_frame_rect(
            self.template, master, text, style,
            mm_to_pt(self.template.page_width_mm) / 2,
            mm_to_pt(self.template.page_height_mm) / 2)
        try:
            self.session.add_text_frame(text, style, self.page.number, rect)
        except ValueError as err:
            self.statusBar().showMessage(f"無法新增文字框：{err}")
            return
        self._select_image(None)  # 框與圖選取互斥
        self._frame_box_idx = len(self.doc.text_frames) - 1
        self._rebuild()
        self.statusBar().showMessage(
            f"已在頁 {self.page.number} 新增文字框「{text[:10]}」"
            f"（樣式 {style}；拖曳可移動、拖角可改大小、Delete 可移除）"
        )

    # --- 選單入口 ---------------------------------------------------------

    def _select_page_frame_box(self) -> None:
        """選單「選取本頁文字框」：版心內的框被 body 字格蓋住點不到時的入口。

        本頁多框時輪流選下一個（再點一次換下一個），故不必猜使用者指的是哪一個。
        """
        on_page = [i for i, tf in enumerate(self.doc.text_frames)
                   if self.page is not None and tf.page == self.page.number]
        if not on_page:
            self.statusBar().showMessage("本頁沒有文字框")
            return
        after = [i for i in on_page
                 if self._frame_box_idx is None or i > self._frame_box_idx]
        self._select_image(None)  # 框與圖選取互斥
        self._select_frame_box(after[0] if after else on_page[0])

    # --- 移除 -------------------------------------------------------------

    def _remove_selected_frame_box(self) -> bool:
        """移除選取的文字框（Delete 鍵與選單共用）；未選取回 False 交回原處理。"""
        idx = self._frame_box_idx
        if idx is None or idx >= len(self.doc.text_frames):
            return False
        return self._remove_text_frame_at(idx)

    def _remove_text_frame_at(self, idx: int) -> bool:
        """移除第 idx 個文字框並重繪（框選取與「刪到最後一字」共用單一落點）。"""
        text = self.doc.text_frames[idx].text
        self.session.remove_text_frame(idx)
        self._frame_box_idx = None
        self.frame_cursor = None  # 框沒了，框游標即無所指（IME 目標回內文）
        self._rebuild()
        self.statusBar().showMessage(
            f"已移除文字框 {idx}「{text[:10]}」（Ctrl+Z 可回原）")
        return True
