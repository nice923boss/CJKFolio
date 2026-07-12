"""CJKFolio 編輯器 Phase 2 真視窗骨架 demo。

承 editor/canvas.py 雙層畫布，於真視窗展示：
  雙層畫布（底圖 PNG＋互動層字格）、點字格 → 反查文件游標（段／字／樣式）＋高亮、
  IME 輸入測試區（驗證 Qt 直排 IME 管線，Owner 鍵盤實測，GAPS #19）。

誠實範圍（honest-planning R3）：
  [實作] 雙層畫布顯示＋點字格反查文件游標（離屏 smoke_check.py 已驗）。
  [Shell] 直排畫布內嵌 IME 編輯（打字→游標插入→reflow）為 Phase 2 編輯引擎後續工程；
          本骨架僅示範「IME 組字 → 已知游標目標」，不變更文件、不 reflow。
  IME 直排輸入是否順暢、視覺對位＝Owner 真視窗鍵盤實測（離屏測不了）。

執行（自 repo 根，需真視窗環境）：
  python editor/app.py [文件路徑]   預設 samples/case-divider.doc.json

製作者：黃政文
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QAction, QBrush, QColor, QPen, QTransform  # noqa: E402
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
from cjkfolio.layout import layout_document  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from editor.canvas import build_page_scene, resolve_hit  # noqa: E402

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

        self.scene = QGraphicsScene()
        build_page_scene(
            self.scene, self.template, self.doc, self.layout_result, self.page, dpi=DPI
        )
        self.view = CanvasView(self.scene, self._on_pick)

        self._ime = QLineEdit()
        self._ime.setPlaceholderText(
            "IME 輸入測試區（用注音／倉頡／拼音輸入中文，驗證 Qt 直排 IME 管線）"
        )
        self._ime.textChanged.connect(self._on_ime)

        central = QWidget()
        box = QVBoxLayout(central)
        box.addWidget(self.view)
        box.addWidget(self._ime)
        self.setCentralWidget(central)

        self.statusBar().showMessage("點頁面字格 → 反查文件游標；IME 測試見下方輸入區")
        credit = QLabel(AUTHOR)
        credit.setStyleSheet("color:#999; font-size:11px; padding:0 8px;")
        self.statusBar().addPermanentWidget(credit)

        help_action = QAction("Owner IME 實測說明", self)
        help_action.triggered.connect(self._show_help)
        self.menuBar().addMenu("說明").addAction(help_action)

    def _on_pick(self, item) -> None:
        pi, ci = item.data(0)
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

    def _draw_highlight(self, rect) -> None:
        if self._highlight is not None:
            self.scene.removeItem(self._highlight)
        hl = QGraphicsRectItem(rect)
        hl.setPen(QPen(QColor(220, 30, 30), 1.5))
        hl.setBrush(QBrush(QColor(255, 220, 0, 70)))
        hl.setZValue(3)
        self.scene.addItem(hl)
        self._highlight = hl

    def _on_ime(self, text: str) -> None:
        if not text:
            return
        if self.cursor is None:
            self.statusBar().showMessage(
                f"IME 組字：「{text}」→ 未選游標（先點一個字格）"
            )
            return
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        pos = hit.span[1] if hit.span else "?"
        self.statusBar().showMessage(
            f"IME 組字：「{text}」→ 目標 段{hit.para_idx} 字位{pos}"
            "（reflow 為後續工程，未套用）"
        )

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "Owner IME 實測說明",
            "本視窗為 Phase 2 畫布骨架（GAPS #19）。\n\n"
            "已實作（離屏 smoke_check 已驗）：\n"
            "  雙層畫布顯示、點字格 → 反查文件游標（段／字／樣式）。\n\n"
            "待您鍵盤實測：\n"
            "  1. 在下方 IME 輸入區用注音／倉頡／拼音輸入中文，確認候選字窗與組字正常。\n"
            "  2. 目檢頁面字形與互動層對位（點字格看高亮是否框住字）。\n\n"
            "尚未實作（[Shell]，後續工程）：\n"
            "  直排畫布內嵌 IME 編輯（打字直接插入頁面游標並 reflow）。\n"
            "  本骨架僅示範「IME 組字 → 已知游標目標」，不變更文件、不 reflow。",
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
