"""CJKFolio 編輯器 Phase 2 真視窗 demo：雙層畫布＋點字格反查游標＋IME 提交插入 reflow。

承 editor/canvas.py 雙層畫布與 cjkfolio/editing.py 編輯引擎（EditSession），於真視窗展示：
  雙層畫布（底圖 PNG＋互動層字格）、點字格 → 反查文件／框游標（段或框／字／樣式）＋高亮、
  IME 輸入區：組字後按 Enter 提交 → 於游標插入（body 全文 reflow／框鏈重佈局）→ 重繪
  → 游標跟隨、Ctrl+Z／Ctrl+Y 復原重做（body 與框統一歷史，Sprint 60）。

誠實範圍（honest-planning R3）：
  [實作]（離屏 smoke_check.py 已驗）＝雙層畫布顯示＋點字格反查游標（body 與框）＋
          IME 提交插入回路（body 走 session.insert 全文重排；框走 session.insert_frame
          框鏈重佈局，Sprint 61 接線）＋undo／redo 快捷鍵。
  [Shell]／待 Owner（離屏測不了，GAPS #19）＝IME 直排組字是否順、候選字窗、真視窗視覺對位、
          快捷鍵手感。本 demo 以「輸入區組字 → Enter 提交」代替直排畫布內嵌 IME 游標；
          畫布內嵌 IME 即點即打與拖曳／選取 UI 為 Phase 2 編輯 UI 後續工程。

執行（自 repo 根，需真視窗環境）：
  python editor/app.py [文件路徑]   預設 samples/case-divider.doc.json

製作者：黃政文
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence, QPen  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from cjkfolio.document import load_document  # noqa: E402
from cjkfolio.editing import DocCursor, DocRange, EditSession  # noqa: E402
from cjkfolio.frame_editing import FrameCursor, FrameEditResult  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from editor.canvas import (  # noqa: E402
    build_page_scene,
    page_frame_placements,
    resolve_frame_hit,
    resolve_hit,
)

DEFAULT_DOC = ROOT / "samples" / "case-divider.doc.json"
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
DPI = 150
AUTHOR = "製作者：黃政文"


class CanvasView(QGraphicsView):
    """點畫布 → 反查最上層帶 provenance 的字格 item，回呼 on_pick(item)；
    鍵盤事件（Backspace／Delete／Enter／PgUp／PgDn）回呼 on_key(event)（Sprint 62）。"""

    def __init__(self, scene: QGraphicsScene, on_pick, on_key=None) -> None:
        super().__init__(scene)
        self._on_pick = on_pick
        self._on_key = on_key

    def mousePressEvent(self, event) -> None:
        pt = self.mapToScene(event.position().toPoint())
        for item in self.scene().items(pt):  # top-first；跳過高亮（data None）
            if item.data(0) is not None:
                self._on_pick(item)
                break
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._on_key is not None and self._on_key(event):
            return
        super().keyPressEvent(event)


class EditorWindow(QMainWindow):
    def __init__(self, doc_path) -> None:
        super().__init__()
        self.setWindowTitle("CJKFolio 編輯器（Phase 2 骨架）")
        self.template = load_template(str(TEMPLATE))
        # 編輯狀態單一事實來源＝EditSession（Sprint 61 接線；doc／layout 由 property 委派）
        self.session = EditSession(load_document(str(doc_path)), self.template)
        self.page = self.layout_result.pages[0]
        self.cursor = None        # 目前選取 body 字格 (placed_idx, cell_idx)
        self.frame_cursor = None  # 目前選取框字格 ("frame", fi, li, ci)；與 body 游標互斥
        self._highlight = None

        self.scene, self._item_by_key = self._make_scene()
        self.view = CanvasView(self.scene, self._on_pick, self._on_key)

        self._ime = QLineEdit()
        self._ime.setPlaceholderText(
            "先點頁面字格選游標（body 或文字框），組字後按 Enter 於游標插入"
        )
        self._ime.textChanged.connect(self._on_ime_preview)
        self._ime.returnPressed.connect(self._on_ime_commit)

        central = QWidget()
        box = QVBoxLayout(central)
        box.addWidget(self.view)
        box.addWidget(self._ime)
        self.setCentralWidget(central)

        self.statusBar().showMessage(
            "點頁面字格 → 反查游標；組字按 Enter 插入；Ctrl+Z／Ctrl+Y 復原重做"
        )
        credit = QLabel(AUTHOR)
        credit.setStyleSheet("color:#999; font-size:11px; padding:0 8px;")
        self.statusBar().addPermanentWidget(credit)

        edit_menu = self.menuBar().addMenu("編輯")
        undo_action = QAction("復原", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)  # Ctrl+Z
        undo_action.triggered.connect(self._on_undo)
        redo_action = QAction("重做", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)  # Ctrl+Y／Ctrl+Shift+Z
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)

        help_action = QAction("Owner IME 實測說明", self)
        help_action.triggered.connect(self._show_help)
        self.menuBar().addMenu("說明").addAction(help_action)

    @property
    def doc(self):
        return self.session.document

    @property
    def layout_result(self):
        return self.session.layout

    def _make_scene(self):
        """建雙層畫布 scene，回傳 (scene, {(placed_idx, cell_idx): item})。"""
        scene = QGraphicsScene()
        items = build_page_scene(
            scene, self.template, self.doc, self.layout_result, self.page, dpi=DPI
        )
        return scene, {it.data(0): it for it in items}

    def _rebuild(self) -> None:
        """reflow 後重繪：換上新 scene，高亮清空（舊 scene 連同高亮一併丟棄）。"""
        self.scene, self._item_by_key = self._make_scene()
        self.view.setScene(self.scene)
        self._highlight = None

    def _on_pick(self, item) -> None:
        key = item.data(0)
        if key and key[0] == "frame":  # 文字框字格（Sprint 58）：顯示框游標，不設插入游標
            self._on_pick_frame(item, *key[1:])
            return
        pi, ci = key
        hit = resolve_hit(self.doc, self.page, pi, ci)
        self.cursor = (pi, ci)
        self.frame_cursor = None  # body 與框游標互斥（最後點選者為 IME 目標）
        src = ""
        if hit.para_idx is not None and hit.span is not None:
            s, e = hit.span
            src = self.doc.paragraphs[hit.para_idx].text[s:e]
        self.statusBar().showMessage(
            f"游標｜段 {hit.para_idx}｜字 {hit.span}＝「{hit.text}」｜"
            f"樣式 {hit.style}／{hit.kind}｜段內文切片「{src}」"
        )
        self._draw_highlight(item.rect())

    def _on_pick_frame(self, item, fi: int, li: int, ci: int) -> None:
        """點文字框字格：反查框游標（Sprint 61 起為 IME 插入目標，與 body 游標互斥）。"""
        hit = self._frame_hit(fi, li, ci)
        self.frame_cursor = ("frame", fi, li, ci)
        self.cursor = None
        src = ""
        if hit.span is not None:
            s, e = hit.span
            src = self.doc.text_frames[hit.source_idx].text[s:e]
        self.statusBar().showMessage(
            f"框游標｜框 {hit.frame_idx}（文字來源框 {hit.source_idx}）｜"
            f"字 {hit.span}＝「{hit.text}」｜樣式 {hit.style}／{hit.kind}｜"
            f"來源切片「{src}」｜組字按 Enter 插入框內"
        )
        self._draw_highlight(item.rect())

    def _frame_hit(self, fi: int, li: int, ci: int):
        placements = page_frame_placements(
            self.template, self.doc, self.layout_result, self.page)
        placement = next(pl for pl in placements if pl.frame_idx == fi)
        return resolve_frame_hit(self.page.number, placement, li, ci)

    def _draw_highlight(self, rect) -> None:
        if self._highlight is not None:
            self.scene.removeItem(self._highlight)
        hl = QGraphicsRectItem(rect)
        hl.setPen(QPen(QColor(220, 30, 30), 1.5))
        hl.setBrush(QBrush(QColor(255, 220, 0, 70)))
        hl.setZValue(3)
        self.scene.addItem(hl)
        self._highlight = hl

    def _on_ime_preview(self, text: str) -> None:
        """組字中預覽插入目標（不變更文件；提交在 Enter）。"""
        if not text:
            return
        if self.frame_cursor is not None:
            hit = self._frame_hit(*self.frame_cursor[1:])
            pos = hit.span[1] if hit.span else "?"
            self.statusBar().showMessage(
                f"IME 組字：「{text}」→ 目標 框{hit.source_idx} 字位{pos}（按 Enter 插入框內）"
            )
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
        if self.frame_cursor is not None:
            self._commit_frame_insert(text)
            return
        if self.cursor is None:
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
            self.page = self.layout_result.pages[0]
            self.cursor = None
        self.frame_cursor = None
        self._rebuild()
        if self.cursor is not None and self.cursor in self._item_by_key:
            self._draw_highlight(self._item_by_key[self.cursor].rect())

    def _on_undo(self) -> None:
        self._apply_history(self.session.undo(), "復原")

    def _on_redo(self) -> None:
        self._apply_history(self.session.redo(), "重做")

    def _apply_history(self, res, verb: str) -> None:
        """undo／redo 共用：依還原態型別（body／框）跟隨游標並重繪（Sprint 61）。"""
        if res is None:
            self.statusBar().showMessage(f"無可{verb}")
            return
        if isinstance(res, FrameEditResult):
            self._follow_frame_address(res)
            self.statusBar().showMessage(
                f"已{verb} → 框{res.cursor.source_idx} 字位{res.cursor.caret}")
            return
        self._follow_body_address(res)
        self.statusBar().showMessage(
            f"已{verb} → 段{res.cursor.para_idx} 字位{res.cursor.caret}")

    def _on_key(self, event) -> bool:
        """畫布鍵盤事件（Sprint 62）：Backspace／Delete 刪字、Enter 分段、PgUp／PgDn 換頁。

        游標語意＝點選字格之後（與 IME 插入同）：Backspace 刪游標字、Delete 刪其後一字。
        回 True＝已處理（未處理交回 QGraphicsView 預設行為）。"""
        key = event.key()
        if key in (Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
            self._turn_page(1 if key == Qt.Key.Key_PageDown else -1)
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
            try:
                res = self.session.delete_frame(hit.source_idx, start, end)
            except ValueError as err:  # 框不可刪空（document@2 不變式）
                self.statusBar().showMessage(f"無法刪除：{err}")
                return True
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

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "Owner IME 實測說明",
            "本視窗為 Phase 2 畫布骨架＋編輯引擎 demo（GAPS #19）。\n\n"
            "已實作（離屏 smoke_check 已驗）：\n"
            "  雙層畫布顯示、點字格 → 反查游標（body 段落與文字框皆可）、\n"
            "  IME 提交插入（body 全文重排／文字框框鏈重佈局，含串接跨框流動）、\n"
            "  Ctrl+Z 復原／Ctrl+Y 重做（body 與框編輯統一歷史）。\n\n"
            "待您鍵盤實測：\n"
            "  1. 點一個內文字格選游標，在下方輸入區用注音／倉頡／拼音組字，按 Enter，\n"
            "     確認頁面即時 reflow、游標跟到剛插入的字。\n"
            "  2. 點文字框字格（如圖說），組字按 Enter，確認文字入框並沿串接鏈流動。\n"
            "  3. Ctrl+Z／Ctrl+Y 連按，確認 body 與框編輯依序回退重做、高亮跟隨。\n"
            "  4. 點畫布後按 Backspace（刪游標字）／Delete（刪後一字）／Enter（body 分段）、\n"
            "     PgUp／PgDn 換頁，確認刪字 reflow 與換頁顯示。\n"
            "  5. 目檢頁面字形與互動層對位；確認直排 IME 組字與候選字窗正常\n"
            "     （此為 §5.2 選 Qt 的關鍵理由）。\n\n"
            "尚未實作（[Shell]，後續工程）：\n"
            "  直排畫布內嵌 IME 即點即打（本 demo 以輸入區＋Enter 代替）、拖曳與範圍選取 UI。",
        )


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    doc_path = argv[1] if len(argv) > 1 else DEFAULT_DOC
    app = QApplication.instance() or QApplication(argv[:1])
    win = EditorWindow(doc_path)
    win.resize(760, 900)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
