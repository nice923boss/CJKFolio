"""編輯輸入回路（Sprint 123 自 editor/app.py 依行數紀律分檔，同 Sprint 78 慣例）：

輸入欄組字提交（body 插入／框插入／選取替換／空白文件第一字）、undo／redo
統一歷史跟隨、鍵盤編輯（Backspace／Delete／Enter 分段、PgUp／PgDn 翻頁）、
手動空行增刪（Sprint 141）、點選回填輸入欄與複製、標點快捷列插入（Sprint 146）。

依賴 EditorWindow 提供：self.session／self.doc／self.page／self.cursor／
self.frame_cursor／self.selection／self.layout_result／self._ime／
self._rebuild()／self._draw_highlight()／self._item_by_key／self._frame_hit()／
self._selection_char_count()／self._delete_selection()／
self._remove_selected_image()／self._image_idx／self.statusBar()。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from cjkfolio.editing import DocCursor, DocRange
from cjkfolio.frame_editing import FrameCursor, FrameEditResult
from editor.canvas import resolve_hit


class EditActionsMixin:
    def _echo_to_ime(self, text: str) -> bool:
        """把點到的字同步顯示於下方文字輸入欄（Sprint 146）；回傳是否真的回填。

        Owner 需求：「點選文字，下方文字輸入欄要同步顯示該文字，這樣才可以複製文字
        或標點符號快速在新位置貼上。」複製走旁邊的「複製」鈕（_copy_ime_text），
        貼上就是在目標位置按 Ctrl+V 再 Enter。

        空字格與無字可顯示者不覆寫欄位（回 False）：一格空白把剛回填的來源字清掉，
        等於半路弄丟使用者要複製的東西。已知代價：打好還沒提交的字會被下一次點選
        覆蓋，這是「同一個欄位既顯示來源又當待插入內容」的必然，故只在真有字時覆寫。

        顯示的是畫布上那一格的字面（hit.text），與段內文原字可能不同一形
        （半形括號在直排轉全形、三個點併成一枚省略號）；回填畫布形＝所見即所複製，
        插回去後引擎照樣走同一條正規化路徑。

        回填後整串選取（selectAll）：接著打字、按標點鈕或 Ctrl+V 都是「取代」而非
        接在它後面，否則點了目標字格再貼上會連同回填的那個字一起插進去（多一字）。
        要留著它就直接按「複製」，複製不看選取。
        """
        if not text or not text.strip():
            return False
        self._ime.setText(text)   # 觸發 _on_ime_preview；呼叫端隨後覆寫狀態列訊息
        self._ime.selectAll()
        return True

    def _selection_text(self) -> str:
        """拖曳選取範圍的文字；跨段回空字串（一行輸入欄表達不了段落分界，
        硬把兩段接起來回填等於偷偷吃掉分段）。"""
        s, e = self.selection.start, self.selection.end
        if s.para_idx != e.para_idx:
            return ""
        return self.doc.paragraphs[s.para_idx].text[s.caret:e.caret]

    def _copy_ime_text(self) -> None:
        """「複製」鈕：文字輸入欄內容送進系統剪貼簿（空欄據實說，不靜默複製空字串）。"""
        text = self._ime.text()
        if not text:
            self.statusBar().showMessage(
                "文字輸入欄是空的（點畫布字格會把該字回填到欄裡，再按此鈕複製）")
            return
        QApplication.clipboard().setText(text)
        self._ime.setFocus()
        self.statusBar().showMessage(
            f"已複製「{text}」到剪貼簿；到新位置點字格後 Ctrl+V 貼進輸入欄，按 Enter 插入")

    def _insert_punct(self, left: str, right: str = "") -> None:
        """標點快捷列回呼（Sprint 146）：於文字輸入欄游標處插入標點，成對者游標落中間。

        只動輸入欄不動文件：提交仍是 Enter，故 undo／reflow／游標跟隨全部沿用既有
        路徑。焦點交回輸入欄＝接著按 Enter 是提交，不是再觸發同一顆按鈕。

        用 QLineEdit.insert 而非自行切字串：它自帶「有選取就取代選取」的標準語意，
        故點字格回填（整串選取）後按標點鈕是換掉那個字，與打字一致。
        """
        self._ime.insert(left + right)
        if right:  # 成對：游標退回兩枚之間，接著打的字就在括號內
            self._ime.setCursorPosition(self._ime.cursorPosition() - len(right))
        self._ime.setFocus()
        self.statusBar().showMessage(
            f"已把 {left}{right} 送進文字輸入欄"
            f"（游標在{'兩枚之間' if right else '其後'}）；"
            "可接著打字，按 Enter 插入文件"
        )

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
            f"IME 組字：「{text}」→ 目標 段{hit.para_idx + 1} 字位{pos}（按 Enter 插入並 reflow）"
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
                f"已以「{text}」替換選取（段{span.start.para_idx + 1}〜"
                f"段{span.end.para_idx + 1}）→ 游標 段{res.cursor.para_idx + 1} "
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
            f"游標 段{res.cursor.para_idx + 1} 字位{res.cursor.caret}"
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
            f"已{verb} → 段{res.cursor.para_idx + 1} 字位{res.cursor.caret}")

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
            f"已刪 段{hit.para_idx + 1} 字位 [{start}, {end}) → 游標 字位{res.cursor.caret}")
        return True

    def _cursor_para_idx(self):
        """游標所在段索引（空行增刪共用）；無可用 body 游標時提示並回 None。"""
        if self.frame_cursor is not None:
            self.statusBar().showMessage("空行只作用於內文段落（文字框為單段）")
            return None
        if self.cursor is None:
            self.statusBar().showMessage("先點一個字格選游標，再插入或移除空行")
            return None
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        if hit.para_idx is None:
            self.statusBar().showMessage("此字格無文件游標（拉丁串／空格），無法定位段落")
            return None
        return hit.para_idx

    def _insert_blank_line(self) -> None:
        """在游標段前插入一個空行（Sprint 141）：模版未宣告 starts_page、或 AI 沒指派
        到章首樣式時，手動把標題推到下一頁的備援。

        空行在畫布上沒有字格可點，故頁數變化一律報進狀態列（不然按了像沒反應），
        移除另走「移除本段前的空行」。"""
        idx = self._cursor_para_idx()
        if idx is None:
            return
        before = len(self.layout_result.pages)
        res = self.session.insert_blank(idx)
        self._follow_body_address(res)
        after = len(self.layout_result.pages)
        page_no = self.page.number if self.page is not None else "?"
        self.statusBar().showMessage(
            f"已在段{idx + 1}前插入空行 → 該段現落於頁 {page_no}"
            f"（全書 {before} 頁{'→ ' + str(after) + ' 頁' if after != before else '不變'}）；"
            "Ctrl+Z 一步回原")

    def _remove_blank_line(self) -> None:
        """移除游標段前的空行（Sprint 141）；前一段非空段則不動任何內容並據實說明。"""
        idx = self._cursor_para_idx()
        if idx is None:
            return
        if idx == 0:
            self.statusBar().showMessage("本段已是第一段，前面沒有空行可移除")
            return
        before = len(self.layout_result.pages)
        try:
            res = self.session.remove_blank(idx - 1)
        except ValueError:
            self.statusBar().showMessage(
                f"段{idx + 1} 前面不是空行（未移除任何內容；空行才可由此移除）")
            return
        self._follow_body_address(res)
        after = len(self.layout_result.pages)
        page_no = self.page.number if self.page is not None else "?"
        self.statusBar().showMessage(
            f"已移除段{idx + 1}前的空行 → 該段現落於頁 {page_no}"
            f"（全書 {before} 頁{'→ ' + str(after) + ' 頁' if after != before else '不變'}）")

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
            f"已分段 → 段{res.cursor.para_idx + 1} 起（共 {len(self.doc.paragraphs)} 段）")
        return True
