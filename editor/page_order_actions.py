"""頁面拖曳重排（Sprint 142）：在頁面面板拖動縮圖搬移整節。

使用者要的是投影片面板那樣的「把封面拖到第 1 頁」。本產品的頁面是段落流排的
結果而非投影片那樣的獨立物件，沒有「把版面頁 4 搬到版面頁 1」這個操作：搬走一頁
的內容，後面所有頁都要重排。可搬的最小完整單位是節（Paragraph.master 節首標記
切出的段落區塊，節首恆起新頁），故拖曳一頁＝搬「自該頁起到下一節首前」的整塊內容，
搬完全書重排（cjkfolio.section_editing.move_section）。

三道守門（封面頁／裝訂補頁／非節首頁），共用 _reorder_reject_reason 一套說詞，
且在「拖曳起點」就把關（Sprint 145）：Owner 真視窗拖非節首頁遭拒卻看不到任何
提示，因為拒收訊息原本掛在面板的放下事件上，而 Qt 對不可放的目標可以整段不遞送
Drop（縮圖項預設無 ItemIsDropEnabled，接受與否是 Qt 內部判斷），使用者就什麼都
看不到。故不可搬的頁在按下開拖的瞬間即擋下並於狀態列＋游標處說明該拖哪一頁；
放下路徑仍保留同一套守門（縱深防禦）。放回原位＝no-op（session.move_section 回
None），不推一步看不出差別的 undo。
"""
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QToolTip

from cjkfolio.layout import _sections


class PageOrderActionsMixin:
    """頁面面板拖曳重排（EditorWindow 混入）。"""

    def _section_head_pages(self) -> list:
        """節序 → 節首的版面頁號。

        節內頁號連續且節首恆起新頁，故逐頁比對「該頁最小段索引」跨過下一節的起段時，
        該頁即新節的首頁。無 body 行的頁（純圖頁）沿用當前節；封面頁不計。
        """
        starts = [lo for _, lo, _ in _sections(self.doc)]
        layout = self.layout_result
        heads = [layout.cover_pages + 1]
        si = 0
        for page in layout.pages[layout.cover_pages:]:
            first = min((pl.para_idx for pl in page.placed
                         if pl.para_idx is not None), default=None)
            if first is None:
                continue
            while si + 1 < len(starts) and first >= starts[si + 1]:
                si += 1
                heads.append(page.number)
        return heads

    def _reorder_reject_reason(self, src_page: int):
        """src_page 不可搬的原因說詞（None＝可搬）。

        拖曳起點（_check_drag_start）與放下（_reorder_pages）共用同一套守門與
        說詞：兩條路徑不允許各說各話（Gate 3 同類訊息單一來源）。
        """
        layout = self.layout_result
        if src_page <= layout.cover_pages:
            return "封面頁固定在最前，不參與拖曳重排"
        if layout.pages[src_page - 1].blank:  # 裝訂補頁（Sprint 144）
            return ("裝訂補頁不參與拖曳重排：它是湊足 4 的倍數用的空白頁，"
                    "隨內文頁數自動增減")
        heads = self._section_head_pages()
        if src_page not in heads:
            head = max(h for h in heads if h <= src_page)
            return (f"頁 {src_page} 不是節首，無法單獨搬移（頁面是段落流排的結果，"
                    f"可搬的最小單位是節）。請改拖頁 {head}，或在頁 {src_page} 上按右鍵"
                    f"指派主版讓它自成一節")
        return None

    def _check_drag_start(self, page_number: int) -> bool:
        """拖曳起點守門（Sprint 145，面板 startDrag 回呼）：可搬回 True。

        不可搬的頁按下就拖不動，並當場於狀態列＋游標處（QToolTip）指名原因與
        該拖哪一頁（使用者的眼睛在面板上，不在視窗底部的狀態列）。
        """
        reason = self._reorder_reject_reason(page_number)
        if reason is None:
            return True
        self.statusBar().showMessage(reason)
        QToolTip.showText(QCursor.pos(), reason)
        return False

    def _reorder_pages(self, src_page: int, dst_page: int) -> None:
        """頁面面板放下回呼：把 src_page 起的一節搬到 dst_page 之前。

        dst_page＝插入位（1＝搬到最前，頁數+1＝搬到最末），由面板依放下點換算。
        """
        reason = self._reorder_reject_reason(src_page)
        if reason is not None:  # 起點守門已擋大多數；此為縱深防禦（同一套說詞）
            self.statusBar().showMessage(reason)
            return
        heads = self._section_head_pages()
        src_index = heads.index(src_page)
        dst_index = sum(1 for h in heads if h < dst_page)
        res = self.session.move_section(src_index, dst_index)
        if res is None:
            self.statusBar().showMessage(f"頁面順序無變更（頁 {src_page} 放回原位）")
            return
        # 搬後節序：往後搬時插入位要扣掉自己空出的位子（同 move_section 的換算）
        new_index = dst_index - (1 if dst_index > src_index else 0)
        new_page = self._section_head_pages()[new_index]
        pages = self.layout_result.pages
        self.page = pages[min(new_page, len(pages)) - 1]
        self.cursor = None
        self.frame_cursor = None
        self._rebuild()
        self.statusBar().showMessage(
            f"已把頁 {src_page} 起的一節搬到頁 {new_page}（全書 {len(pages)} 頁）")
