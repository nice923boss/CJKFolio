"""頁面導航動作 mixin（Sprint 125；同 StyleActionsMixin 分檔慣例控 app.py 行數）。

出版工作流補完系列甲1〜甲3：頁碼指示器（狀態列常駐「頁 N／M」）、跳頁
（Ctrl+J 對話框）、「版面」選單翻頁四式＋跳頁（PgUp／PgDn 自 Sprint 62 存在
但介面上無可見入口，Owner 據此判斷「翻頁未實裝」；本檔補齊可發現性）、
頁面面板調度（debounce＋世代守門的背景縮圖渲染，面板本體見 page_panel.py）。

縮圖重渲染時機：_rebuild 中比對 layout_result 快照（is 同一性；保留引用故
id 不會被回收重用），版面真的重排過才起 debounce 計時（翻頁不重排、不重
渲染）。連續編輯（每字 reflow 一次）由 400ms 靜默期收斂成一輪；輪進行中
再有改動則 cancel 舊輪並記 pending，執行緒 finished 後接力起新輪，任意時刻
至多一條縮圖執行緒。世代不符的 page_ready／all_done 一律丟棄（不畫舊圖）。

依賴 EditorWindow 提供：self.doc／self.template／self.layout_result／self.page／
self.cursor／self.frame_cursor／self._doc_path／self._rebuild()／self.statusBar()
與 __init__ 接線的 self._page_panel／self._page_label／self._thumb_timer。
"""
from PySide6.QtCore import QTimer

from editor.page_panel import ThumbnailThread

THUMB_DEBOUNCE_MS = 400  # 連續編輯的縮圖重渲染靜默期


class NavActionsMixin:
    # 類別層預設值（preflight_actions 慣例：不必動 EditorWindow.__init__ 主流程）
    _thumb_thread = None
    _thumb_generation = 0
    _thumb_pending = False
    _thumb_snapshot = None   # 上一輪縮圖對應的 layout_result（is 比對）
    _thumb_elapsed = None    # 最近完整一輪的耗時秒（效能實測與 smoke 讀取）
    _thumb_image_errors = 0  # 最近完整一輪的缺圖頁數

    def _init_nav(self) -> None:
        """__init__ 尾端接線：debounce 計時器＋首輪面板同步。"""
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.setInterval(THUMB_DEBOUNCE_MS)
        self._thumb_timer.timeout.connect(self._start_thumbnails)
        self._sync_page_panel()

    # --- 跳頁核心（面板點選、跳頁對話框、首末頁選單共用） ---

    def _goto_page(self, number: int) -> None:
        """跳至指定頁（1-based 版面頁號；換頁清游標，同 _turn_page 語意）。"""
        pages = self.layout_result.pages
        if not pages or self.page is None:
            self.statusBar().showMessage("空白文件尚無頁面；先匯入稿件或在輸入欄打字")
            return
        number = max(1, min(len(pages), number))
        if number == self.page.number:
            self.statusBar().showMessage(self._goto_message(number))
            return
        self.page = pages[number - 1]
        self.cursor = None
        self.frame_cursor = None
        self._rebuild()
        self.statusBar().showMessage(self._goto_message(number))

    def _goto_message(self, number: int) -> str:
        """跳頁後的狀態列訊息：無封面時維持既有「頁 N/M」（版面頁號），
        帶封面時改報書頁語意（封面標「封面」），與指示器同一套說法。"""
        if not self.layout_result.cover_pages:
            return f"頁 {number}/{len(self.layout_result.pages)}"
        return self._page_label_text(number)

    def _prompt_goto_page(self) -> None:
        """Ctrl+J：跳至頁碼對話框（InDesign 慣例鍵）。"""
        from PySide6.QtWidgets import QInputDialog

        pages = self.layout_result.pages
        if not pages or self.page is None:
            self.statusBar().showMessage("空白文件尚無頁面；先匯入稿件或在輸入欄打字")
            return
        # 對話框吃書頁碼（使用者看到的頁碼），內部轉版面頁號；無封面時兩者相等，
        # 既有行為與訊息零變更。封面不編頁碼故不在可輸入範圍（走「版面 → 第一頁」）。
        cover_pages = self.layout_result.cover_pages
        last = len(pages) - cover_pages
        number, ok = QInputDialog.getInt(
            self, "跳至頁碼", f"頁碼（1〜{last}）",
            max(1, self.page.number - cover_pages), 1, last)
        if ok:
            self._goto_page(number + cover_pages)

    # --- 面板與指示器同步（_rebuild 尾端呼叫） ---

    def _page_label_text(self, number) -> str:
        """狀態列頁碼指示器文字（Sprint 132 起認封面）。

        使用者想的是書上印的頁碼，不是版面頁號；帶封面時兩者差一。故封面頁直接
        標「封面」（它本就不編頁碼），內文頁報書頁號與內文總頁數，兩數同一語意。
        """
        if number is None:
            return "頁 −／−"
        pages = self.layout_result.pages
        cover_pages = self.layout_result.cover_pages
        if number <= cover_pages:
            return "封面"
        return f"頁 {number - cover_pages}／{len(pages) - cover_pages}"

    def _sync_page_panel(self) -> None:
        pages = self.layout_result.pages
        self._page_panel.set_page_count(len(pages))
        self._page_panel.set_current(self.page.number if self.page else None)
        self._page_label.setText(
            self._page_label_text(self.page.number if self.page else None))
        if self._thumb_snapshot is not self.layout_result:  # 版面真的重排過
            self._thumb_snapshot = self.layout_result
            self._thumb_timer.start()

    # --- 背景縮圖渲染調度（世代守門＋單執行緒接力） ---

    def _start_thumbnails(self) -> None:
        if self._thumb_thread is not None:  # 舊輪未收工：取消並記接力
            self._thumb_thread.cancel()
            self._thumb_pending = True
            return
        if not self.layout_result.pages:
            return  # 空白文件：面板已清為 0 項
        self._thumb_generation += 1
        thread = ThumbnailThread(
            self._thumb_generation, self.doc, self.template, self.layout_result,
            self._doc_path.parent, parent=self)
        thread.page_ready.connect(self._on_thumb_page)
        thread.all_done.connect(self._on_thumbs_done)
        thread.finished.connect(self._on_thumb_thread_finished)
        self._thumb_thread = thread
        thread.start()

    def _on_thumb_page(self, generation: int, number: int, qimage) -> None:
        if generation == self._thumb_generation:  # 過期輪的縮圖不上牆
            self._page_panel.set_thumbnail(number, qimage)

    def _on_thumbs_done(self, generation: int, elapsed: float, image_errors: int) -> None:
        if generation != self._thumb_generation:
            return
        self._thumb_elapsed = elapsed
        self._thumb_image_errors = image_errors
        if image_errors:  # 缺圖不沉默（主畫布另有逐次提示，此處彙整頁數）
            self.statusBar().showMessage(
                f"頁面縮圖：{image_errors} 頁置入圖未載入（該頁縮圖不顯示圖）")

    def _on_thumb_thread_finished(self) -> None:
        self._thumb_thread = None
        if self._thumb_pending:  # 輪中被取消的改動接力補渲染
            self._thumb_pending = False
            self._start_thumbnails()

    def _shutdown_thumbnails(self) -> None:
        """關窗（app.closeEvent）與 smoke 收尾：停計時器並等執行緒收工。

        QThread 於運行中被銷毀會 abort 整個進程；cancel 旗標讓 worker 於當前
        頁渲染完即返回，wait 至多一頁的時長。"""
        self._thumb_timer.stop()
        self._thumb_pending = False
        if self._thumb_thread is not None:
            self._thumb_thread.cancel()
            self._thumb_thread.wait()
            self._thumb_thread = None
