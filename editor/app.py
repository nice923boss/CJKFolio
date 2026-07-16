"""CJKFolio 編輯器 Phase 2 真視窗 demo：雙層畫布＋點字格反查游標＋IME 提交插入 reflow。

承 editor/canvas.py 雙層畫布與 cjkfolio/editing.py 編輯引擎，於真視窗展示：
  雙層畫布（底圖 PNG＋互動層字格）、點字格 → 反查文件游標（段／字／樣式）＋高亮、
  IME 輸入區：組字後按 Enter 提交 → 於游標插入 → 全文 reflow → 畫布重繪 → 游標跟隨。

誠實範圍（honest-planning R3）：
  [實作]（離屏 smoke_check.py 已驗）＝雙層畫布顯示＋點字格反查文件游標＋
          IME 提交插入 reflow 回路（插字 → layout_document 全文重排 → 反查新游標畫布落點；
          reflow 走全文重排，Spike 3 實測 7.67ms/章、互動級，非增量近似）。
  [Shell]／待 Owner（離屏測不了，GAPS #19）＝IME 直排組字是否順、候選字窗、真視窗視覺對位。
          本 demo 以「輸入區組字 → Enter 提交」代替直排畫布內嵌 IME 游標；畫布內嵌 IME
          即點即打與拖曳／選取 UI 為 Phase 2 編輯 UI 後續工程。

執行（自 repo 根，需真視窗環境）：
  python editor/app.py [文件路徑]   預設 samples/case-divider.doc.json

製作者：黃政文
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QAction, QBrush, QColor, QPen  # noqa: E402
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
from cjkfolio.editing import DocCursor, apply_insert  # noqa: E402
from cjkfolio.layout import layout_document  # noqa: E402
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
    """點畫布 → 反查最上層帶 provenance 的字格 item，回呼 on_pick(item)。"""

    def __init__(self, scene: QGraphicsScene, on_pick) -> None:
        super().__init__(scene)
        self._on_pick = on_pick

    def mousePressEvent(self, event) -> None:
        pt = self.mapToScene(event.position().toPoint())
        for item in self.scene().items(pt):  # top-first；跳過高亮（data None）
            if item.data(0) is not None:
                self._on_pick(item)
                break
        super().mousePressEvent(event)


class EditorWindow(QMainWindow):
    def __init__(self, doc_path) -> None:
        super().__init__()
        self.setWindowTitle("CJKFolio 編輯器（Phase 2 骨架）")
        self.doc = load_document(str(doc_path))
        self.template = load_template(str(TEMPLATE))
        self.layout_result = layout_document(self.doc, self.template)
        self.page = self.layout_result.pages[0]
        self.cursor = None  # 目前選取字格 (placed_idx, cell_idx)
        self._highlight = None

        self.scene, self._item_by_key = self._make_scene()
        self.view = CanvasView(self.scene, self._on_pick)

        self._ime = QLineEdit()
        self._ime.setPlaceholderText(
            "先點頁面字格選游標，再用注音／倉頡／拼音組字，按 Enter 於游標插入並 reflow"
        )
        self._ime.textChanged.connect(self._on_ime_preview)
        self._ime.returnPressed.connect(self._on_ime_commit)

        central = QWidget()
        box = QVBoxLayout(central)
        box.addWidget(self.view)
        box.addWidget(self._ime)
        self.setCentralWidget(central)

        self.statusBar().showMessage(
            "點頁面字格 → 反查文件游標；下方輸入區組字後按 Enter 插入並 reflow"
        )
        credit = QLabel(AUTHOR)
        credit.setStyleSheet("color:#999; font-size:11px; padding:0 8px;")
        self.statusBar().addPermanentWidget(credit)

        help_action = QAction("Owner IME 實測說明", self)
        help_action.triggered.connect(self._show_help)
        self.menuBar().addMenu("說明").addAction(help_action)

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
        """點文字框字格：反查框游標並顯示來源切片（框編輯待框編輯專項，IME 不入框）。"""
        placements = page_frame_placements(
            self.template, self.doc, self.layout_result, self.page)
        placement = next(pl for pl in placements if pl.frame_idx == fi)
        hit = resolve_frame_hit(self.page.number, placement, li, ci)
        src = ""
        if hit.span is not None:
            s, e = hit.span
            src = self.doc.text_frames[hit.source_idx].text[s:e]
        self.statusBar().showMessage(
            f"框游標｜框 {hit.frame_idx}（文字來源框 {hit.source_idx}）｜"
            f"字 {hit.span}＝「{hit.text}」｜樣式 {hit.style}／{hit.kind}｜"
            f"來源切片「{src}」｜框編輯待後續（IME 插入僅 body）"
        )
        self._draw_highlight(item.rect())

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
        if self.cursor is None:
            self.statusBar().showMessage(f"IME 組字：「{text}」→ 未選游標（先點一個字格）")
            return
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        pos = hit.span[1] if hit.span else "?"
        self.statusBar().showMessage(
            f"IME 組字：「{text}」→ 目標 段{hit.para_idx} 字位{pos}（按 Enter 插入並 reflow）"
        )

    def _on_ime_commit(self) -> None:
        """Enter 提交：於游標插入組字文字 → 全文 reflow → 畫布重繪 → 游標跟隨新落點。"""
        text = self._ime.text()
        if not text:
            return
        if self.cursor is None:
            self.statusBar().showMessage("先點一個字格選游標，再組字並按 Enter")
            return
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        if hit.para_idx is None or hit.span is None:
            self.statusBar().showMessage("此字格無文件游標（拉丁串／空格），無法定位插入")
            return
        res = apply_insert(
            self.doc, self.template, DocCursor(hit.para_idx, hit.span[1]), text
        )
        self.doc = res.document
        self.layout_result = res.layout
        if res.address is not None:
            self.page = self.layout_result.pages[res.address.page_number - 1]
            self.cursor = (res.address.placed_idx, res.address.cell_idx)
        else:
            self.page = self.layout_result.pages[0]
            self.cursor = None
        self._rebuild()
        self._ime.clear()
        if self.cursor is not None and self.cursor in self._item_by_key:
            self._draw_highlight(self._item_by_key[self.cursor].rect())
        self.statusBar().showMessage(
            f"已插入「{text}」→ reflow：{len(self.layout_result.pages)} 頁、"
            f"{len(self.layout_result.violations)} 禁則違規；"
            f"游標 段{res.cursor.para_idx} 字位{res.cursor.caret}"
        )

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "Owner IME 實測說明",
            "本視窗為 Phase 2 畫布骨架＋編輯引擎 demo（GAPS #19）。\n\n"
            "已實作（離屏 smoke_check 已驗）：\n"
            "  雙層畫布顯示、點字格 → 反查文件游標（段／字／樣式）、\n"
            "  IME 提交插入 reflow（組字後按 Enter → 於游標插入 → 全文重排 → 重繪 → 游標跟隨）。\n\n"
            "待您鍵盤實測：\n"
            "  1. 點一個內文字格選游標，在下方輸入區用注音／倉頡／拼音組字，按 Enter，\n"
            "     確認頁面即時 reflow、游標跟到剛插入的字。\n"
            "  2. 目檢頁面字形與互動層對位（點字格看高亮是否框住字）。\n"
            "  3. 確認直排 IME 組字與候選字窗正常（此為 §5.2 選 Qt 的關鍵理由）。\n\n"
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
