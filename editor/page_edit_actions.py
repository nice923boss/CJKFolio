"""刪除頁面與插入空白頁（Sprint 153）：頁面面板右鍵選單的三個項目。

Owner 的話：頁 4 只有書名「這裡不需要再看到一次標題文字」，要能刪頁並自動補空白頁
恢復為 4 的倍數；也要能新增、插入頁面，頁碼的左右側與數字自動跟著變。

頁面是段落流排的結果，故刪一頁＝刪掉排在那一頁的段落，插一頁＝插入一個自成一節的
空段（cjkfolio.section_editing.delete_page／insert_blank_page）。兩者都只在「頁界」
動手：刪頁要求該頁首段不延續自前頁、末段不延續到下一頁；插頁要求插入處不切斷跨頁段。
頁碼數字（書頁號）、左右側（紙面號）、末尾裝訂補頁都由重排推導，本檔不另算。

Sprint 155：刪頁、插頁在同一個 undo 步內自動更新目次頁碼；右鍵選單另有「更新目次
頁碼」，供其他編輯（改字、改樣式）使內文移頁後一鍵重算。

不可動的頁（封面、裝訂補頁、跨頁段的頁）選單項照常顯示，點了在狀態列與游標處說明
原因（Sprint 145 教訓：停用或沉默拒收，使用者看不到為什麼）。
"""
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu, QToolTip


class PageEditActionsMixin:
    """頁面面板右鍵刪頁、插頁（EditorWindow 混入）。"""

    def _content_page_ranges(self) -> dict:
        """版面頁號 → (lo, hi, 乾淨起頁, 乾淨收頁)；封面與裝訂補頁不列。

        [lo, hi) 是該頁擁有的段：自本頁首段起到下一頁首段前（夾在兩頁之間、不產生
        行的空段歸前一頁）；首頁從段 0 起，末頁到全書末段。"""
        layout = self.layout_result
        spans = []
        for page in layout.pages[layout.cover_pages:]:
            ids = [pl.para_idx for pl in page.placed if pl.para_idx is not None]
            if ids and not page.blank:
                spans.append((page.number, min(ids), max(ids)))
        ranges = {}
        for k, (number, first, last) in enumerate(spans):
            lo = 0 if k == 0 else first
            hi = spans[k + 1][1] if k + 1 < len(spans) else len(self.doc.paragraphs)
            clean_start = k == 0 or first != spans[k - 1][2]
            clean_end = k + 1 == len(spans) or last != spans[k + 1][1]
            ranges[number] = (lo, hi, clean_start, clean_end)
        return ranges

    def _page_edit_guard(self, page_number: int, action: str):
        """不可動的原因說詞（None＝可動）。action ∈ delete／before／after。"""
        layout = self.layout_result
        if page_number <= layout.cover_pages:
            if action == "after":
                return None  # 封面之後＝內文最前，恆為頁界
            return ("封面頁不能刪除" if action == "delete"
                    else "封面固定在最前，不能在它之前插頁")
        if layout.pages[page_number - 1].blank:
            return ("裝訂補頁是湊足 4 的倍數用的空白頁，隨內文頁數自動增減，"
                    "不能刪除或在它前後插頁；要加頁請在最後一頁內文上按右鍵新增")
        rng = self._content_page_ranges().get(page_number)
        if rng is None:
            return f"頁 {page_number} 沒有內文段落，無法{'刪除' if action == 'delete' else '插頁'}"
        lo, hi, clean_start, clean_end = rng
        cut_start = f"頁 {page_number} 開頭的段落延續自前頁"
        cut_end = f"頁 {page_number} 末段延續到下一頁"
        if action == "delete":
            if not clean_start or not clean_end:
                return (f"{cut_start if not clean_start else cut_end}，"
                        "整頁刪除會切斷段落，無法刪除")
            if lo == 0 and hi == len(self.doc.paragraphs):
                return "全書只剩這一頁內容，無法刪除"
        if action == "before" and not clean_start:
            return f"{cut_start}，在此插頁會切斷段落"
        if action == "after" and not clean_end:
            return f"{cut_end}，在此插頁會切斷段落"
        return None

    def _add_page_edit_actions(self, menu: QMenu, page_number: int) -> QMenu:
        """在右鍵選單末尾加插頁、刪頁三項（_build_page_menu 呼叫）。"""
        menu.addSeparator()
        for text, action in (("在此頁之前插入空白頁", "before"),
                             ("在此頁之後新增空白頁", "after")):
            act = menu.addAction(text)
            act.triggered.connect(
                lambda checked=False, a=action:
                self._insert_page(page_number, after=a == "after"))
        delete = menu.addAction(f"刪除此頁（頁 {page_number}）")
        delete.triggered.connect(lambda checked=False: self._delete_page(page_number))
        menu.addSeparator()
        menu.addAction("更新目次頁碼").triggered.connect(
            lambda checked=False: self._refresh_toc())
        return menu

    def _refuse_page_edit(self, reason: str) -> None:
        self.statusBar().showMessage(reason)
        QToolTip.showText(QCursor.pos(), reason)

    def _after_page_edit(self, page_number: int, msg: str) -> None:
        """重排後跳到 page_number 並回報全書頁數、補頁數與目次頁碼更新結果。"""
        pages = self.layout_result.pages
        self.page = pages[min(page_number, len(pages)) - 1]
        self.cursor = None
        self.frame_cursor = None
        self._rebuild()
        padding = sum(1 for p in pages if p.blank)
        msg += f"（全書 {len(pages)} 頁，末尾裝訂補頁 {padding} 頁）"
        toc_msg = self._toc_refresh_message()
        if toc_msg:
            msg += f"；{toc_msg}"
        self.statusBar().showMessage(msg)

    def _toc_refresh_message(self) -> str:
        """session.last_toc_refresh 的說詞（""＝文件沒有目次節）。"""
        refresh = self.session.last_toc_refresh
        if refresh.problem:
            return refresh.problem
        if not refresh.entries:
            return ""
        if not refresh.changed:
            return f"目次 {refresh.entries} 條頁碼不變"
        return f"目次頁碼已更新 {refresh.changed} 條（共 {refresh.entries} 條）"

    def _refresh_toc(self) -> None:
        """依現行版面更新目次頁碼（Sprint 155，供手動調整版面後一鍵重算）。"""
        if self.session.refresh_toc() is not None:
            self._rebuild()
        self.statusBar().showMessage(
            self._toc_refresh_message() or "文件沒有目次頁，無頁碼可更新")

    def _delete_page(self, page_number: int) -> None:
        reason = self._page_edit_guard(page_number, "delete")
        if reason is not None:
            self._refuse_page_edit(reason)
            return
        lo, hi, _, _ = self._content_page_ranges()[page_number]
        self.session.delete_page(page_number, lo, hi)
        self._after_page_edit(page_number, f"已刪除頁 {page_number}")

    def _insert_page(self, page_number: int, after: bool) -> None:
        reason = self._page_edit_guard(page_number, "after" if after else "before")
        if reason is not None:
            self._refuse_page_edit(reason)
            return
        layout = self.layout_result
        ranges = self._content_page_ranges()
        if page_number <= layout.cover_pages:  # 封面之後＝插在內文最前
            new_page = layout.cover_pages + 1
            at, master = 0, layout.pages[new_page - 1].master
        else:
            lo, hi, _, _ = ranges[page_number]
            at, new_page = (hi, page_number + 1) if after else (lo, page_number)
            master = layout.pages[page_number - 1].master
        self.session.insert_blank_page(at, new_page, master)
        side = "後" if after else "前"
        self._after_page_edit(
            new_page, f"已在頁 {page_number} 之{side}插入空白頁，新頁為頁 {new_page}")
