"""尋找／取代動作 mixin（Sprint 128：丙1 尋找／取代，開 GAPS #83）。

3.4 萬字真稿過去無檢索手段（PLAN 丙1）。地基：doc.paragraphs 純文字層
（p.text＝段字面）＋session.replace_span（Sprint 65：單一 replace_span＝單 undo
步，已驗）。純函式 find_matches 逐段掃出命中（段內半開區間），與 UI 分離便於離屏
釘死；命中→版面頁定位沿用 _selected_cell_keys 同款半開字格重疊判定（Sprint 65），
跳頁用 _goto_page（Sprint 125），高亮用 _set_selection 的既有選取 shading。

全部取代逐一 replace_span＝N 步復原（非單一 undo 單元）：多段單一 undo 需核心批次
替換 API，v1 未做，入 GAPS #83，狀態列據實報「N 步復原」不沉默降級。

依賴 EditorWindow 提供：self.doc／self.session／self.layout_result／self.page／
self.cursor／self.frame_cursor／self._rebuild()／self._goto_page()／
self._set_selection()／self._sel_items／self.view／self.statusBar()。
"""
from dataclasses import dataclass

from cjkfolio.editing import DocCursor, DocSpan
from editor.find_panel import FindDialog


@dataclass(frozen=True)
class FindMatch:
    """一處命中：段 para_idx 內半開區間 [start, end)（段內偏移，同 DocCursor caret）。"""

    para_idx: int
    start: int
    end: int


def find_matches(paragraphs, query: str, case_sensitive: bool = False) -> list:
    """逐段掃出 query 的所有命中（段內非重疊、由左至右）。

    區分大小寫（預設關）：關時以 str.lower() 折疊比對；CJK 與 ASCII 下 lower() 保長，
    段內偏移精確。變長折疊字元（如 ß→ss、İ）v1 未精算，屬 GAPS #83 已知限，典型
    CJK＋ASCII 檢索不觸及。空 query 回空清單（呼叫端據此不動作）。
    """
    if not query:
        return []
    needle = query if case_sensitive else query.lower()
    n = len(query)
    matches = []
    for pi, para in enumerate(paragraphs):
        hay = para.text if case_sensitive else para.text.lower()
        start = 0
        while True:
            idx = hay.find(needle, start)
            if idx < 0:
                break
            matches.append(FindMatch(pi, idx, idx + n))
            start = idx + n  # 非重疊：下一次搜尋自本命中之後起
    return matches


class FindActionsMixin:
    """編輯＞尋找…／取代…：非模態對話框驅動的全文檢索與取代（丙1）。"""

    # 類別層預設（同 NavActionsMixin 慣例：不動 EditorWindow.__init__ 主流程）
    _find_dialog = None
    _find_pos = None  # 目前命中錨 (para_idx, start)；None＝尚未定位（自首個命中起）

    def _open_find_dialog(self, *, replace: bool = False) -> None:
        """開（或聚焦既有）非模態尋找對話框；replace=True 起手聚焦取代欄（Ctrl+H）。"""
        if self._find_dialog is None:
            dlg = FindDialog(parent=self)
            dlg.find_requested.connect(self._find_next)
            dlg.replace_requested.connect(self._replace_one)
            dlg.replace_all_requested.connect(self._replace_all)
            self._find_dialog = dlg
        dlg = self._find_dialog
        dlg.show()
        dlg.raise_()
        dlg.focus_query(replace=replace)

    def _find_next(self) -> None:
        """找下一個：自目前錨之後的命中（到底環繞回首個），跳頁並高亮。"""
        dlg = self._find_dialog
        query = dlg.query()
        if not query:
            dlg.set_status("請輸入要尋找的文字")
            return
        matches = find_matches(self.doc.paragraphs, query, dlg.case_sensitive())
        if not matches:
            self._set_selection(None)
            self._find_pos = None
            dlg.set_status(f"找不到「{query}」")
            self.statusBar().showMessage(f"尋找：找不到「{query}」")
            return
        idx = self._next_match_index(matches)
        m = matches[idx]
        self._find_pos = (m.para_idx, m.start)
        self._select_match(m)
        dlg.set_status(f"第 {idx + 1}／{len(matches)} 個相符")
        self.statusBar().showMessage(
            f"尋找「{query}」：第 {idx + 1}／{len(matches)} 個"
            f"（段 {m.para_idx} 位 {m.start}）")

    def _next_match_index(self, matches) -> int:
        """自目前錨之後的第一個命中序；到底則環繞回首個（無錨＝首個）。"""
        if self._find_pos is not None:
            for i, m in enumerate(matches):
                if (m.para_idx, m.start) > self._find_pos:
                    return i
        return 0

    def _select_match(self, match) -> None:
        """跳到命中所在頁並以選取 shading 高亮（捲入可視區）。"""
        page_number = self._page_of_match(match)
        if page_number is None:  # body 命中必落於某頁；防禦性守門（不炸）
            self.statusBar().showMessage("命中未落於版面頁（略過跳頁）")
            return
        if self.page is None or page_number != self.page.number:
            self._goto_page(page_number)  # 換頁＝rebuild，之後 _item_by_key 為目標頁
        span = DocSpan(DocCursor(match.para_idx, match.start),
                       DocCursor(match.para_idx, match.end))
        self.cursor = None  # 選取以 selection 為單位，取代單格游標
        self.frame_cursor = None
        self._set_selection(span)
        if self._sel_items:  # 捲到首個選取格（同 _draw_highlight 的 ensureVisible）
            self.view.ensureVisible(self._sel_items[0])

    def _page_of_match(self, match):
        """命中段內偏移落於哪個版面頁（首個含重疊字格的頁號）。"""
        for page in self.layout_result.pages:
            for placed in page.placed:
                if placed.para_idx != match.para_idx:
                    continue
                for cell in placed.line.cells:
                    if cell.span is None:
                        continue
                    s, e = cell.span
                    if s < match.end and e > match.start:  # 半開區間相交
                        return page.number
        return None

    def _current_match(self, matches):
        """目前錨精確吻合（para_idx＋start）的命中；無錨或錨已失效回 None。"""
        if self._find_pos is None:
            return None
        for m in matches:
            if (m.para_idx, m.start) == self._find_pos:
                return m
        return None

    def _replace_one(self) -> None:
        """取代目前命中（單一 replace_span＝單 undo 步），重繪後前進到下一個。"""
        dlg = self._find_dialog
        query = dlg.query()
        if not query:
            dlg.set_status("請輸入要尋找的文字")
            return
        matches = find_matches(self.doc.paragraphs, query, dlg.case_sensitive())
        m = self._current_match(matches)
        if m is None:  # 尚未定位到命中：先找一個（InDesign 首按取代＝尋找）
            self._find_next()
            return
        repl = dlg.replacement()
        span = DocSpan(DocCursor(m.para_idx, m.start), DocCursor(m.para_idx, m.end))
        self.session.replace_span(span, repl)  # 單一 commit＝單 undo 步
        # 錨前進到取代字串之後，避免取代字串含 query 時原地反覆命中
        self._find_pos = (m.para_idx, m.start + len(repl))
        self._rebuild()
        self.statusBar().showMessage(
            f"已取代 1 處：段 {m.para_idx} 位 {m.start}「{query}」→「{repl}」")
        self._find_next()  # 前進並高亮下一個命中

    def _replace_all(self) -> None:
        """全部取代：由後往前逐一 replace_span（偏移保序有效）；N 步復原（GAPS #83）。"""
        dlg = self._find_dialog
        query = dlg.query()
        if not query:
            dlg.set_status("請輸入要尋找的文字")
            return
        matches = find_matches(self.doc.paragraphs, query, dlg.case_sensitive())
        if not matches:
            dlg.set_status(f"找不到「{query}」")
            self.statusBar().showMessage(f"全部取代：找不到「{query}」")
            return
        repl = dlg.replacement()
        for m in reversed(matches):  # 由後往前＝先動後者，不擾前者段內偏移
            span = DocSpan(DocCursor(m.para_idx, m.start),
                           DocCursor(m.para_idx, m.end))
            self.session.replace_span(span, repl)
        n = len(matches)
        self._find_pos = None
        self._set_selection(None)
        self._rebuild()
        dlg.set_status(f"已全部取代 {n} 處")
        self.statusBar().showMessage(
            f"已全部取代 {n} 處「{query}」→「{repl}」（{n} 步復原）")
