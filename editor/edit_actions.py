"""編輯輸入回路（Sprint 123 自 editor/app.py 依行數紀律分檔，同 Sprint 78 慣例）：

輸入欄組字提交（body 插入／框插入／選取替換／空白文件第一字）、undo／redo
統一歷史跟隨、鍵盤編輯（Backspace／Delete／Enter 分段、PgUp／PgDn 翻頁）。

依賴 EditorWindow 提供：self.session／self.doc／self.page／self.cursor／
self.frame_cursor／self.selection／self.layout_result／self._ime／
self._rebuild()／self._draw_highlight()／self._item_by_key／self._frame_hit()／
self._selection_char_count()／self._delete_selection()／
self._remove_selected_image()／self._image_idx／self.statusBar()。
"""
from PySide6.QtCore import Qt

from cjkfolio.editing import DocCursor, DocRange
from cjkfolio.frame_editing import FrameCursor, FrameEditResult
from editor.canvas import resolve_hit


class EditActionsMixin:
    def _on_ime_preview(self, text: str) -> None:
        """組字中預覽插入目標（不變更文件；提交在 Enter）。"""
        if not text:
            return
        if self.selection is not None:
            self.statusBar().showMessage(
                f"IME 組字：「{text}」→ 將替換選取"
                f"（{self._selection_char_count()} 字，按 Enter）"
            )
            return
        if self.frame_cursor is not None:
            hit = self._frame_hit(*self.frame_cursor[1:])
            pos = hit.span[1] if hit.span else "?"
            self.statusBar().showMessage(
                f"IME 組字：「{text}」→ 目標 框{hit.source_idx} 字位{pos}（按 Enter 插入框內）"
            )
            return
        if self.page is None:  # 空白文件：第一字的去向明確（Sprint 123）
            self.statusBar().showMessage(f"IME 組字：「{text}」→ 按 Enter 從第一頁第一字開始")
            return
        if self.cursor is None:
            self.statusBar().showMessage(f"IME 組字：「{text}」→ 未選游標（先點一個字格）")
            return
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        pos = hit.span[1] if hit.span else "?"
        self.statusBar().showMessage(
            f"IME 組字：「{text}」→ 目標 段{hit.para_idx} 字位{pos}（按 Enter 插入並 reflow）"
        )

    def _on_ime_commit(self) -> None:
        """Enter 提交：於游標插入（body 走 session.insert 全文 reflow；框走
        session.insert_frame 框鏈重佈局）→ 畫布重繪 → 游標跟隨新落點。"""
        text = self._ime.text()
        if not text:
            return
        if self.selection is not None:  # 選取中提交＝替換選取（Sprint 65）
            span = self.selection
            res = self.session.replace_span(span, text)
            self._follow_body_address(res)
            self._ime.clear()
            self.statusBar().showMessage(
                f"已以「{text}」替換選取（段{span.start.para_idx}〜"
                f"段{span.end.para_idx}）→ 游標 段{res.cursor.para_idx} "
                f"字位{res.cursor.caret}"
            )
            return
        if self.frame_cursor is not None:
            self._commit_frame_insert(text)
            return
        if self.cursor is None:
            if self.page is None:  # 空白文件：第一字直接落段 0 字位 0（Sprint 123）
                res = self.session.insert(DocCursor(0, 0), text)
                self._follow_body_address(res)
                self._ime.clear()
                self.statusBar().showMessage(
                    f"已插入「{text}」，從第一頁開始；繼續打字按 Enter 接續，"
                    "點字格可改插入位置"
                )
                return
            self.statusBar().showMessage("先點一個字格選游標，再組字並按 Enter")
            return
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        if hit.para_idx is None or hit.span is None:
            self.statusBar().showMessage("此字格無文件游標（拉丁串／空格），無法定位插入")
            return
        res = self.session.insert(DocCursor(hit.para_idx, hit.span[1]), text)
        self._follow_body_address(res)
        self._ime.clear()
        self.statusBar().showMessage(
            f"已插入「{text}」→ reflow：{len(self.layout_result.pages)} 頁、"
            f"{len(self.layout_result.violations)} 禁則違規；"
            f"游標 段{res.cursor.para_idx} 字位{res.cursor.caret}"
        )

    def _commit_frame_insert(self, text: str) -> None:
        """框游標插入（Sprint 61）：session.insert_frame → 框鏈重佈局 → 游標跟隨。"""
        hit = self._frame_hit(*self.frame_cursor[1:])
        if hit.span is None:
            self.statusBar().showMessage("此框字格無來源游標，無法定位插入")
            return
        res = self.session.insert_frame(FrameCursor(hit.source_idx, hit.span[1]), text)
        self._follow_frame_address(res)
        self._ime.clear()
        self.statusBar().showMessage(
            f"已插入框「{text}」→ 框{res.cursor.source_idx} 字位{res.cursor.caret}"
            "（body 版面不重排）"
        )

    def _follow_frame_address(self, res) -> None:
        """框編輯／還原後：重繪並讓框游標與高亮跟隨 address。"""
        if res.address is not None:
            self.page = self.layout_result.pages[res.address.page_number - 1]
            self.frame_cursor = ("frame", res.address.frame_idx,
                                 res.address.line_idx, res.address.cell_idx)
        else:
            self.frame_cursor = None
        self.cursor = None
        self._rebuild()
        if self.frame_cursor is not None and self.frame_cursor in self._item_by_key:
            self._draw_highlight(self._item_by_key[self.frame_cursor].rect())

    def _follow_body_address(self, res) -> None:
        """body 編輯／還原後：重繪並讓 body 游標與高亮跟隨 address。"""
        if res.address is not None:
            self.page = self.layout_result.pages[res.address.page_number - 1]
            self.cursor = (res.address.placed_idx, res.address.cell_idx)
        else:
            pages = self.layout_result.pages
            self.page = pages[0] if pages else None  # undo 回空白文件（Sprint 123）
            self.cursor = None
        self.frame_cursor = None
        self._rebuild()
        if self.cursor is not None and self.cursor in self._item_by_key:
            self._draw_highlight(self._item_by_key[self.cursor].rect())

    def _on_undo(self) -> None:
        probe = self._history_probe()  # 先取樣：undo() 一跑 self.doc 就換人了
        self._apply_history(self.session.undo(), "復原", probe)

    def _on_redo(self) -> None:
        probe = self._history_probe()
        self._apply_history(self.session.redo(), "重做", probe)

    def _history_probe(self) -> tuple:
        """undo／redo 之前的三個文件切片，用來判斷這一步動的是內文還是框／圖。

        比的是身分（is）不是內容：編輯層一律以 replace() 產生新文件，沒動到的欄位
        會沿用同一個 tuple 物件，故身分不變＝這一步確實沒碰它，也不會把「兩次編輯
        剛好排出相同內容」誤判成沒動。
        """
        return (self.doc.paragraphs, self.doc.text_frames, self.doc.images)

    def _apply_history(self, res, verb: str, probe=None) -> None:
        """undo／redo 共用：依還原態型別（body／框）跟隨游標並重繪（Sprint 61）。"""
        if res is None:
            self.statusBar().showMessage(f"無可{verb}")
            return
        if isinstance(res, FrameEditResult):
            self._follow_frame_address(res)
            self.statusBar().showMessage(
                f"已{verb} → 框{res.cursor.source_idx} 字位{res.cursor.caret}")
            return
        paras, frames, images = probe or (None, None, None)
        if paras is self.doc.paragraphs and (frames is not self.doc.text_frames
                                             or images is not self.doc.images):
            # 整框或置入圖的移動／縮放／增刪（Sprint 136）：body 游標並未參與這一步，
            # 跟著它的落點跳頁會把正在排封面的人丟到內文頁、框選取也一併失蹤。
            self.cursor = None       # 版面可能因繞排重排，舊字格座標不再可信
            self.frame_cursor = None
            self._rebuild()          # 停在本頁重畫（框選取由 _rebuild 夾界後復原）
            self.statusBar().showMessage(f"已{verb}（這一步動的是框或圖，停在本頁）")
            return
        self._follow_body_address(res)
        self.statusBar().showMessage(
            f"已{verb} → 段{res.cursor.para_idx} 字位{res.cursor.caret}")

    def _on_key(self, event) -> bool:
        """畫布鍵盤事件（Sprint 62）：Backspace／Delete 刪字、Enter 分段、PgUp／PgDn 換頁。

        游標語意＝點選字格之後（與 IME 插入同）：Backspace 刪游標字、Delete 刪其後一字；
        拖曳選取中（Sprint 65）Backspace／Delete 刪整段選取。
        回 True＝已處理（未處理交回 QGraphicsView 預設行為）。"""
        key = event.key()
        if key in (Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
            self._turn_page(1 if key == Qt.Key.Key_PageDown else -1)
            return True
        if (self._image_idx is not None
                and key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)):
            return self._remove_selected_image()  # 選取圖片時刪除吃圖不吃字
        if (self._frame_box_idx is not None
                and key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)):
            return self._remove_selected_frame_box()  # 選取整框時刪除吃框（Sprint 136）
        if self.selection is not None:  # 選取中（Sprint 65）：刪除吃整段選取、不分段
            if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                return self._delete_selection()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.statusBar().showMessage("選取中不分段；先刪除選取或重新點選單一字格")
                return True
        if key == Qt.Key.Key_Backspace:
            return self._delete_at_cursor(before=True)
        if key == Qt.Key.Key_Delete:
            return self._delete_at_cursor(before=False)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return self._split_at_cursor()
        return False

    def _turn_page(self, step: int) -> None:
        """PgUp／PgDn 換顯示頁（版面頁號連續，index＝number−1）；換頁清游標。"""
        pages = self.layout_result.pages
        if not pages or self.page is None:  # 空白文件無頁可翻（Sprint 123）
            self.statusBar().showMessage("空白文件尚無頁面；先匯入稿件或在輸入欄打字")
            return
        new_idx = max(0, min(len(pages) - 1, self.page.number - 1 + step))
        if new_idx == self.page.number - 1:
            self.statusBar().showMessage(
                f"已在{'末' if step > 0 else '首'}頁（{self.page.number}/{len(pages)}）")
            return
        self.page = pages[new_idx]
        self.cursor = None
        self.frame_cursor = None
        self._rebuild()
        self.statusBar().showMessage(f"頁 {self.page.number}/{len(pages)}")

    def _delete_at_cursor(self, before: bool) -> bool:
        """Backspace（刪游標字）／Delete（刪其後一字）：body 與框皆走 session 入歷史。"""
        if self.frame_cursor is not None:
            hit = self._frame_hit(*self.frame_cursor[1:])
            if hit.span is None:
                return False
            s, e = hit.span
            src_len = len(self.doc.text_frames[hit.source_idx].text)
            start, end = (s, e) if before else (e, min(e + 1, src_len))
            if start >= end:
                self.statusBar().showMessage("已在框文末，無後一字可刪")
                return True
            if end - start >= src_len:  # 刪掉的就是全部：整個框一併移除（Sprint 136）
                # document@2 不留空框，故「刪最後一字」的正解是刪框而非拒絕刪除。
                # Owner 真視窗回饋：原先在此丟不變式錯誤，封面書名框成了死結。
                self._remove_text_frame_at(hit.source_idx)
                self.statusBar().showMessage(
                    f"已刪框{hit.source_idx}最後一字，整個文字框一併移除"
                    "（Ctrl+Z 一步回原）")
                return True
            res = self.session.delete_frame(hit.source_idx, start, end)
            self._follow_frame_address(res)
            self.statusBar().showMessage(
                f"已刪框{hit.source_idx} 字位 [{start}, {end})")
            return True
        if self.cursor is None:
            return False
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        if hit.para_idx is None or hit.span is None:
            return False
        s, e = hit.span
        para_len = len(self.doc.paragraphs[hit.para_idx].text)
        start, end = (s, e) if before else (e, min(e + 1, para_len))
        if start >= end:
            self.statusBar().showMessage("已在段末，無後一字可刪")
            return True
        res = self.session.delete(DocRange(hit.para_idx, start, end))
        self._follow_body_address(res)
        self.statusBar().showMessage(
            f"已刪 段{hit.para_idx} 字位 [{start}, {end}) → 游標 字位{res.cursor.caret}")
        return True

    def _split_at_cursor(self) -> bool:
        """Enter＝body 游標處分段（session.split）；文字框為單段不分段。"""
        if self.frame_cursor is not None:
            self.statusBar().showMessage("文字框為單段，不分段（Enter 僅 body）")
            return True
        if self.cursor is None:
            return False
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        if hit.para_idx is None or hit.span is None:
            return False
        res = self.session.split(DocCursor(hit.para_idx, hit.span[1]))
        self._follow_body_address(res)
        self.statusBar().showMessage(
            f"已分段 → 段{res.cursor.para_idx} 起（共 {len(self.doc.paragraphs)} 段）")
        return True
