"""主版指派介面（Sprint 130 丁1）：頁面面板右鍵指派節式主版。

節式主版核心自 Sprint 51 在（主版按「節」指派，非逐頁自由套），但過去無 UI 入口，
只能手寫 .doc.json 的 meta.master 與段落 master 標記。本 mixin 給頁面面板右鍵選單：
對某頁指派主版＝對「該頁起始段」設節式主版（沿行數紀律另立檔，不擠 app.py）。

三種落點（皆作用於頁的起始段，語意見 cjkfolio.editing.set_section_master）：

- 頁 1：改首節預設主版 doc.master。
- 既有節首頁：換該節主版（節範圍不變）。
- 節內乾淨起頁：把起始段升為新節首，自該段起新開一節，延續至下一節首（狀態列據實
  提示「延續至下一節首」，非只此頁）。

守門：頁若以「跨頁續段」開頭（起始段延續自前頁），指派會逼該續段成節首而把內容往前
拉重排，非預期，故該頁指派項停用並提示「請於段落起始頁指派」（_page_start_para 回
None）。段落層級「此段起新節」入口（可對任一段而非只頁起始段）屬更通用面，本 Sprint
不做（見 GAPS #85）。
"""
from typing import Optional

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu


class MasterActionsMixin:
    """頁面面板右鍵指派節式主版（EditorWindow 混入）。"""

    def _page_start_para(self, page_number: int) -> Optional[int]:
        """回傳「乾淨起頁」的起始段 para_idx；跨頁續段開頭或無 body 行回 None。

        乾淨起頁＝該頁第一行的段落不延續自前頁。頁 1 恆乾淨；其餘頁比對前頁末行
        段落，相同即同段跨頁（非乾淨，指派會逼續段成節首而把內容往前拉重排）。
        """
        pages = self.layout_result.pages
        if not 1 <= page_number <= len(pages):
            return None
        page = pages[page_number - 1]
        if not page.placed:
            return None
        first = page.placed[0].para_idx
        if first is None:
            return None
        if page_number == 1:
            return first
        prev = pages[page_number - 2]
        prev_last = prev.placed[-1].para_idx if prev.placed else None
        if first == prev_last:   # 同一段跨頁：本頁非乾淨起頁
            return None
        return first

    def _build_page_menu(self, page_number: int) -> Optional[QMenu]:
        """建頁面面板右鍵選單（不 exec；離屏可驗）。無此頁時回 None。"""
        pages = self.layout_result.pages
        if not 1 <= page_number <= len(pages):
            return None
        page = pages[page_number - 1]
        start_para = self._page_start_para(page_number)
        menu = QMenu(self)
        assign_menu = menu.addMenu(f"指派主版（頁 {page_number}）")
        if start_para is None:
            # 無內文行者（封面、裝訂補頁、純圖頁）不是「跨頁續段」，據實分開說
            hint = assign_menu.addAction(
                "本頁以跨頁段落開頭，請於段落起始頁指派" if page.placed
                else "本頁無內文行，無法指派主版（主版按節指派，節以段落切分）")
            hint.setEnabled(False)
            return menu
        for name in self.template.masters:      # 依模版著作序（A→G）
            act = assign_menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == page.master)
            act.triggered.connect(
                lambda checked=False, n=name:
                self._assign_master(start_para, n, page_number))
        # 取消節首（併回前節）：僅當起始段本身帶節首標記（段 0 自蓋亦可，退回 doc.master）
        if self.doc.paragraphs[start_para].master is not None:
            menu.addSeparator()
            cancel = menu.addAction("取消節首（併回前節）")
            cancel.triggered.connect(
                lambda checked=False: self._assign_master(start_para, None, page_number))
        return menu

    def _page_context_menu(self, page_number: int, global_pos: QPoint) -> None:
        """頁面面板 customContextMenuRequested 回呼：建選單並於游標處 exec。"""
        menu = self._build_page_menu(page_number)
        if menu is not None:
            menu.exec(global_pos)

    def _assign_master(
        self, para_idx: int, master: Optional[str], page_number: int
    ) -> None:
        """對第 para_idx 段指派節式主版，重排後留在右鍵頁（不跳游標頁）。"""
        was_head = para_idx == 0 or self.doc.paragraphs[para_idx].master is not None
        try:
            res = self.session.set_section_master(para_idx, master)
        except KeyError:  # UI 不該發生（下拉即模版現有主版）；據實提示不炸
            self.statusBar().showMessage("主版指派失敗：主版名不存在於模版")
            return
        if res is None:
            self.statusBar().showMessage(f"主版無變更（頁 {page_number} 已是此主版）")
            return
        pages = self.layout_result.pages       # 指派後的新版面（session 屬性自動同源）
        self.page = pages[min(page_number, len(pages)) - 1]  # 留在右鍵頁（clamp）
        self.cursor = None
        self.frame_cursor = None
        self._rebuild()
        new_master = self.page.master
        npages = len(pages)
        if master is None:
            if para_idx == 0:
                msg = f"已退回首節預設主版 {new_master}"
            else:
                msg = f"已取消頁 {page_number} 節首，本節併回前節（主版 {new_master}）"
        elif was_head:
            msg = f"頁 {page_number} 起的節改用主版 {master}（全書 {npages} 頁）"
        else:
            msg = (f"自頁 {page_number}（段 {para_idx}）起新開一節，主版 {master}，"
                   f"延續至下一節首（全書 {npages} 頁）")
        self.statusBar().showMessage(msg)
