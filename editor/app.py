"""CJKFolio 編輯器 Phase 2 真視窗 demo：雙層畫布＋點字格反查游標＋IME 提交插入 reflow。

承 editor/canvas.py 雙層畫布與 cjkfolio/editing.py 編輯引擎（EditSession），於真視窗展示：
  雙層畫布（底圖 PNG＋互動層字格）、點字格 → 反查文件／框游標（段或框／字／樣式）＋高亮、
  按住左鍵拖曳 → 範圍選取（可跨段；刪除／套字元樣式／IME 替換，Sprint 65）、
  IME 輸入區：組字後按 Enter 提交 → 於游標插入（body 全文 reflow／框鏈重佈局）→ 重繪
  → 游標跟隨、Ctrl+Z／Ctrl+Y 復原重做（body 與框統一歷史，Sprint 60）。

誠實範圍（honest-planning R3）：
  [實作]（離屏 smoke_check.py 已驗）＝雙層畫布顯示＋點字格反查游標（body 與框）＋
          IME 提交插入回路（body 走 session.insert 全文重排；框走 session.insert_frame
          框鏈重佈局，Sprint 61 接線）＋undo／redo 快捷鍵＋拖曳範圍選取
          （跨段選取 → Backspace 刪除／字元樣式面板套選取／IME 替換，Sprint 65）。
  [Shell]／待 Owner（離屏測不了，GAPS #19）＝IME 直排組字是否順、候選字窗、真視窗視覺對位、
          快捷鍵與拖曳手感。本 demo 以「輸入區組字 → Enter 提交」代替直排畫布內嵌 IME 游標；
          畫布內嵌 IME 即點即打為 Phase 2 編輯 UI 後續工程。

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
    QDialog,
    QDockWidget,
    QGraphicsRectItem,
    QGraphicsScene,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from cjkfolio.ai_config import load_ai_config  # noqa: E402
from cjkfolio.ai_style import suggest_styles  # noqa: E402
from cjkfolio.document import load_document  # noqa: E402
from cjkfolio.editing import DocCursor, DocRange, DocSpan  # noqa: E402
from cjkfolio.frame_editing import FrameCursor, FrameEditResult  # noqa: E402
from cjkfolio.images import ImageError  # noqa: E402
from cjkfolio.session import EditSession  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from editor.ai_assign import AssignReviewDialog  # noqa: E402
from editor.ai_panel import AiConfigDialog  # noqa: E402
from editor.library_panel import TemplateLibraryDialog  # noqa: E402
from editor.canvas import (  # noqa: E402
    build_page_scene,
    page_frame_placements,
    page_images,
    resolve_frame_hit,
    resolve_hit,
)
from editor.canvas_view import CanvasView  # noqa: E402
from editor.image_actions import ImageActionsMixin  # noqa: E402
from editor.preflight_actions import PreflightActionsMixin  # noqa: E402
from editor.style_actions import StyleActionsMixin  # noqa: E402
from editor.style_panel import StylePanel  # noqa: E402

DEFAULT_DOC = ROOT / "samples" / "case-divider.doc.json"
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
DPI = 150
AUTHOR = "製作者：黃政文"


class EditorWindow(StyleActionsMixin, PreflightActionsMixin, ImageActionsMixin,
                   QMainWindow):
    def __init__(self, doc_path) -> None:
        super().__init__()
        self.setWindowTitle("CJKFolio 編輯器（Phase 2 骨架）")
        # 編輯狀態單一事實來源＝EditSession（Sprint 61 接線；doc／layout／template
        # 由 property 委派＝樣式編輯後畫布與面板恆用現行模版，Sprint 71）
        self.session = EditSession(
            load_document(str(doc_path)), load_template(str(TEMPLATE)))
        self._doc_path = Path(doc_path)  # 置入圖相對路徑基準（preflight 匯出用）
        self.page = self.layout_result.pages[0]
        self.cursor = None        # 目前選取 body 字格 (placed_idx, cell_idx)
        self.frame_cursor = None  # 目前選取框字格 ("frame", fi, li, ci)；與 body 游標互斥
        self._highlight = None
        self.selection = None     # 拖曳範圍選取（DocSpan，僅 body，Sprint 65）
        self._sel_items = []      # 選取範圍 shading items
        self._drag_anchor = None  # 拖曳起點 (para_idx, span)，按下 body 字格時設定

        self.statusBar().showMessage(  # 先放預設語，_make_scene 的缺圖提示才不被蓋掉
            "點頁面字格 → 反查游標；組字按 Enter 插入；Ctrl+Z／Ctrl+Y 復原重做"
        )
        self.scene, self._item_by_key = self._make_scene()
        self.view = CanvasView(self.scene, self._on_pick, self._on_key, self._on_drag,
                               on_move=self._on_image_move,
                               on_release=self._on_image_release,
                               on_drop=self._on_image_drop)

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

        dock = QDockWidget("樣式", self)
        self._style_panel = StylePanel(
            self.template, self._apply_para_style_at_cursor,
            self._apply_char_style_at_cursor, on_edit_style=self._edit_style,
            on_edit_swatch=self._edit_swatch)
        dock.setWidget(self._style_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        style_menu = self.menuBar().addMenu("樣式")
        for label, handler in (
            ("新增段落樣式（基於選取）…", lambda: self._create_style("para")),
            ("新增字元樣式（基於選取）…", lambda: self._create_style("char")),
            ("重新命名選取的段落樣式…", lambda: self._rename_selected_style("para")),
            ("重新命名選取的字元樣式…", lambda: self._rename_selected_style("char")),
            ("刪除選取的段落樣式", lambda: self._remove_selected_style("para")),
            ("刪除選取的字元樣式", lambda: self._remove_selected_style("char")),
            ("新增色票…", self._create_swatch),
            ("刪除選取的色票", self._remove_selected_swatch),
            ("AI 樣式指派（初稿，逐段校正）…", lambda: self._run_ai_assign()),
            ("另存模版…", self._save_template_dialog),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            style_menu.addAction(action)

        library_menu = self.menuBar().addMenu("模版")
        for label, handler in (
            ("模版庫（套用整份模版）…", lambda: self._open_library()),
            ("併入萃取草稿…", lambda: self._merge_draft_dialog()),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            library_menu.addAction(action)

        image_menu = self.menuBar().addMenu("圖片")
        for label, handler in (
            ("置入圖片（放在頁面中央）…", lambda: self._place_image_dialog()),
            ("移除選取的圖片", self._remove_selected_image),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            image_menu.addAction(action)

        check_menu = self.menuBar().addMenu("檢查")
        check_action = QAction("PDF/X-1a preflight（機械檢查）…", self)
        check_action.triggered.connect(lambda: self._run_preflight())
        check_menu.addAction(check_action)
        check_x4_action = QAction("PDF/X-4 preflight（需輸出 ICC）…", self)
        check_x4_action.triggered.connect(lambda: self._run_preflight("x-4"))
        check_menu.addAction(check_x4_action)

        ai_action = QAction("AI 設定…", self)
        ai_action.triggered.connect(self._show_ai_config)
        self.menuBar().addMenu("設定").addAction(ai_action)

        help_action = QAction("Owner IME 實測說明", self)
        help_action.triggered.connect(self._show_help)
        self.menuBar().addMenu("說明").addAction(help_action)

    def _show_ai_config(self) -> None:
        """開 AI 設定面板（§4.4 三欄位；儲存只到本機，statusBar 不含欄位值）。"""
        if AiConfigDialog(self).exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("AI 設定已儲存（本機 local/ai-config.local.json）")

    def _run_ai_assign(self, suggest=None) -> None:
        """AI 樣式指派入口（§4.4「初稿＋人工校正」；#36 (b)）。

        suggest 注入＝離屏可驗（callable(texts, candidates) -> SuggestResult）；
        None＝真呼叫使用者私有 endpoint（未設定顯示訊息不擋流程＝誠實失敗，
        同 CLI assign-styles exit 2 語意）。v1 同步呼叫（全書級約數分鐘會凍
        視窗，背景執行緒屬後續）。
        """
        texts = [p.text for p in self.doc.paragraphs]
        candidates = sorted(self.template.paragraph_styles)
        default_style = self.template.md_mapping.get("paragraph", candidates[0])
        if suggest is None:
            config = load_ai_config()
            if not (config.base_url and config.model):
                self.statusBar().showMessage(
                    "尚未設定 AI（「設定」選單填 Base URL 與 Model；AI 為選配增強）")
                return
            self.statusBar().showMessage("AI 指派連線中（全書級約數分鐘，視窗暫凍）…")
            result = suggest_styles(texts, candidates, config,
                                    default_style=default_style)
        else:
            result = suggest(texts, candidates)
        dlg = AssignReviewDialog(self.doc, self.template, result.assignments,
                                 self._apply_assignments,
                                 warnings=result.warnings, parent=self)
        dlg.exec()

    def _open_library(self, directory=None) -> None:
        """模版庫對話框（§4.3；v1 目錄＝內建 templates/，使用者庫目錄慣例後續）。"""
        from cjkfolio.template_library import list_templates
        entries = list_templates(directory or TEMPLATE.parent)
        dlg = TemplateLibraryDialog(entries, self._apply_template_path, parent=self)
        dlg.exec()

    def _apply_template_path(self, path):
        """載入並套用整份模版（session.apply_template 一步 undo）；回錯誤訊息或 None。"""
        from cjkfolio.styles import TemplateError

        try:
            res = self.session.apply_template(load_template(path))
        except (TemplateError, KeyError) as err:
            return f"無法套用：{err}"
        self._after_template_change(res, f"已套用模版：{Path(path).name}（一步 undo 可回）")
        return None

    def _merge_draft_dialog(self, path=None) -> None:
        """併入萃取草稿（extract-styles 產物；session.merge_draft 一步 undo）。"""
        import json as _json

        from PySide6.QtWidgets import QFileDialog

        from cjkfolio.styles import TemplateError

        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "選取萃取草稿", "", "草稿 JSON (*.json)")
            if not path:
                return
        try:
            draft = _json.loads(Path(path).read_text(encoding="utf-8"))
            res, report = self.session.merge_draft(draft)
        except (TemplateError, OSError, ValueError) as err:
            self.statusBar().showMessage(f"無法併入：{err}")
            return
        if res is None:
            self.statusBar().showMessage(
                f"未新增樣式（{len(report.skipped)} 個同名跳過，既有定義優先）")
            return
        self._after_template_change(
            res, f"已併入 {len(report.added)} 個樣式"
                 f"（跳過 {len(report.skipped)} 個同名；一步 undo 可回）")

    def _apply_assignments(self, assignments):
        """批次改派套用（session.apply_para_styles 單一 undo 步）；回錯誤訊息或 None。"""
        if not assignments:
            self.statusBar().showMessage("未採用任何建議（文件未變更）")
            return None
        try:
            res = self.session.apply_para_styles(assignments)
        except (KeyError, ValueError, IndexError) as err:
            return f"無法套用：{err}"
        self._after_template_change(
            res, f"AI 批次改派 {len(assignments)} 段（單一 undo 步可整批回退）")
        return None

    @property
    def doc(self):
        return self.session.document

    @property
    def template(self):
        return self.session.template

    @property
    def layout_result(self):
        return self.session.layout

    def _make_scene(self):
        """建雙層畫布 scene，回傳 (scene, {(placed_idx, cell_idx): item})。

        置入圖於此解析（Sprint 102）：讀不到的圖檔據實提示並照常顯示無圖版面，
        不讓一張缺圖使整個編輯器打不開（提示不沉默，缺圖仍留在文件裡）。"""
        scene = QGraphicsScene()
        try:
            images = page_images(self.template, self.doc, self.layout_result,
                                 self.page, base_dir=self._doc_path.parent)
        except ImageError as err:
            images = ()
            self.statusBar().showMessage(f"置入圖無法載入（本頁不顯示圖）：{err}")
        items = build_page_scene(
            scene, self.template, self.doc, self.layout_result, self.page, dpi=DPI,
            images=images,
        )
        return scene, {it.data(0): it for it in items}

    def _rebuild(self) -> None:
        """reflow 後重繪：換上新 scene，高亮與選取清空（舊 scene 連同其 item 一併丟棄）。"""
        self.scene, self._item_by_key = self._make_scene()
        self.view.setScene(self.scene)
        self._highlight = None
        self.selection = None
        self._sel_items = []
        self._image_outline = None  # 舊 scene 已丟棄；選取仍在則於下方重畫外框
        self._image_preview = None
        if self._image_idx is not None:
            self._select_image(min(self._image_idx, len(self.doc.images) - 1)
                               if self.doc.images else None)
        if hasattr(self, "_style_panel"):  # 面板清單同步現行模版（Sprint 71）
            self._style_panel.refresh(self.session.template)

    def _on_pick(self, item, scene_pos=None) -> None:
        key = item.data(0)
        self._set_selection(None)   # 重新按下＝清既有選取；拖曳起點隨本次點選重設
        self._drag_anchor = None    # 框字格不設拖曳起點（框選取 v1 不支援）
        if key and key[0] in ("image", "image-handle"):  # 置入圖框（Sprint 102）
            self._on_image_press(key, scene_pos)
            return
        self._select_image(None)    # 點到文字＝取消圖片選取（兩者互斥）
        if key and key[0] == "frame":  # 文字框字格（Sprint 58）：顯示框游標，不設插入游標
            self._on_pick_frame(item, *key[1:])
            return
        pi, ci = key
        hit = resolve_hit(self.doc, self.page, pi, ci)
        self.cursor = (pi, ci)
        self.frame_cursor = None  # body 與框游標互斥（最後點選者為 IME 目標）
        if hit.para_idx is not None and hit.span is not None:
            self._drag_anchor = (hit.para_idx, hit.span)
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

    def _on_drag(self, item) -> None:
        """按住左鍵拖曳過字格（Sprint 65）：自按下的 body 字格起劃範圍選取（可跨段）。

        起訖以文件序正規化（反向拖曳等價）；拖回起點字格＝退回單游標；
        框字格不支援拖曳選取（框編輯以單游標為單位，v1 設計）。"""
        key = item.data(0)
        if self._drag_anchor is None or not key or key[0] == "frame":
            return
        hit = resolve_hit(self.doc, self.page, *key)
        if hit.para_idx is None or hit.span is None:
            return
        a_para, a_span = self._drag_anchor
        if (hit.para_idx, hit.span) == (a_para, a_span):
            self._set_selection(None)  # 拖回起點字格＝維持單游標
            return
        if (a_para, a_span[0]) <= (hit.para_idx, hit.span[0]):
            span = DocSpan(DocCursor(a_para, a_span[0]),
                           DocCursor(hit.para_idx, hit.span[1]))
        else:
            span = DocSpan(DocCursor(hit.para_idx, hit.span[0]),
                           DocCursor(a_para, a_span[1]))
        self._set_selection(span)
        self.statusBar().showMessage(
            f"選取 段{span.start.para_idx} 字位{span.start.caret} 〜 "
            f"段{span.end.para_idx} 字位{span.end.caret}"
            f"（{self._selection_char_count()} 字）｜"
            "Backspace 刪除選取、點字元樣式套用至選取、組字 Enter 替換選取"
        )

    def _set_selection(self, span) -> None:
        """設定／清除拖曳範圍選取並重畫選取 shading（僅 body 字格）。"""
        for it in self._sel_items:
            self.scene.removeItem(it)
        self._sel_items = []
        self.selection = span
        if span is None:
            return
        if self._highlight is not None:  # 選取 shading 取代單格高亮
            self.scene.removeItem(self._highlight)
            self._highlight = None
        for key in self._selected_cell_keys():
            item = self._item_by_key.get(key)
            if item is None:
                continue
            hl = QGraphicsRectItem(item.rect())
            hl.setPen(Qt.NoPen)
            hl.setBrush(QBrush(QColor(60, 120, 220, 70)))
            hl.setZValue(2)
            self.scene.addItem(hl)
            self._sel_items.append(hl)

    def _selected_cell_keys(self) -> list:
        """目前頁面上落在選取範圍內的 body 字格 key（文件序半開區間相交判定）。"""
        span = self.selection
        if span is None:
            return []
        lo = (span.start.para_idx, span.start.caret)
        hi = (span.end.para_idx, span.end.caret)
        keys = []
        for pi, placed in enumerate(self.page.placed):
            if placed.para_idx is None:
                continue
            for ci, cell in enumerate(placed.line.cells):
                if cell.span is None:
                    continue
                lo_c = (placed.para_idx, cell.span[0])
                hi_c = (placed.para_idx, cell.span[1])
                if lo_c < hi and hi_c > lo:
                    keys.append((pi, ci))
        return keys

    def _selection_char_count(self) -> int:
        """選取範圍涵蓋的字元數（段界不計；供狀態列顯示）。"""
        s, e = self.selection.start, self.selection.end
        if s.para_idx == e.para_idx:
            return e.caret - s.caret
        total = len(self.doc.paragraphs[s.para_idx].text) - s.caret + e.caret
        for p in range(s.para_idx + 1, e.para_idx):
            total += len(self.doc.paragraphs[p].text)
        return total

    def _delete_selection(self) -> bool:
        """Backspace／Delete 刪除拖曳選取（session.delete_span 入統一歷史）。"""
        span = self.selection
        res = self.session.delete_span(span)
        self._follow_body_address(res)
        self.statusBar().showMessage(
            f"已刪選取 段{span.start.para_idx} 字位{span.start.caret} 〜 "
            f"段{span.end.para_idx} 字位{span.end.caret} → "
            f"游標 段{res.cursor.para_idx} 字位{res.cursor.caret}"
        )
        return True

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

    def _apply_para_style_at_cursor(self, name: str) -> None:
        """樣式面板點段落樣式 → 套用至 body 游標所在段（session 入統一歷史）。

        跨段選取套段落樣式 v1 未支援（套用於拖曳起點所在段；多段一次套用需
        核心單一 undo 單元的多段 API，屬後續樣式系統工程）。"""
        if self.frame_cursor is not None:
            self.statusBar().showMessage("文字框樣式為框屬性（單一樣式），面板套用僅 body")
            return
        if self.cursor is None:
            self.statusBar().showMessage("先點一個 body 字格選游標，再點段落樣式")
            return
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        if hit.para_idx is None or hit.span is None:
            return
        res = self.session.apply_para_style(DocCursor(hit.para_idx, hit.span[1]), name)
        self._follow_body_address(res)
        self.statusBar().showMessage(f"段{hit.para_idx} 段落樣式 → {name}")

    def _apply_char_style_at_cursor(self, name) -> None:
        """樣式面板點字元樣式 → 套用至拖曳選取範圍（Sprint 65）或 body 游標字（None＝清除）。"""
        if self.selection is not None:  # 選取中＝套整段選取（可跨段，Sprint 49 核心）
            span = self.selection
            res = self.session.apply_style_span(span, name)
            self._follow_body_address(res)
            self._set_selection(span)  # 套樣式不改 text，選取座標仍有效＝保留選取
            self.statusBar().showMessage(
                f"選取 段{span.start.para_idx}〜段{span.end.para_idx} 字元樣式 → "
                f"{name if name else '（清除）'}"
            )
            return
        if self.frame_cursor is not None:
            self.statusBar().showMessage("文字框無字元樣式（單一樣式），面板套用僅 body")
            return
        if self.cursor is None:
            self.statusBar().showMessage("先點一個 body 字格選游標，再點字元樣式")
            return
        hit = resolve_hit(self.doc, self.page, *self.cursor)
        if hit.para_idx is None or hit.span is None:
            return
        s, e = hit.span
        res = self.session.apply_style(DocRange(hit.para_idx, s, e), name)
        self._follow_body_address(res)
        self.statusBar().showMessage(
            f"段{hit.para_idx} 字位 [{s}, {e}) 字元樣式 → {name if name else '（清除）'}")

    # 樣式選單域回呼（雙擊編輯／新增／刪除／改名／色票／另存）見 StyleActionsMixin
    # （editor/style_actions.py，Sprint 78 行數紀律分檔）。

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
            "  Ctrl+Z 復原／Ctrl+Y 重做（body 與框編輯統一歷史）、\n"
            "  按住左鍵拖曳範圍選取（可跨段；刪除／套字元樣式／IME 替換）。\n\n"
            "待您鍵盤實測：\n"
            "  1. 點一個內文字格選游標，在下方輸入區用注音／倉頡／拼音組字，按 Enter，\n"
            "     確認頁面即時 reflow、游標跟到剛插入的字。\n"
            "  2. 點文字框字格（如圖說），組字按 Enter，確認文字入框並沿串接鏈流動。\n"
            "  3. Ctrl+Z／Ctrl+Y 連按，確認 body 與框編輯依序回退重做、高亮跟隨。\n"
            "  4. 點畫布後按 Backspace（刪游標字）／Delete（刪後一字）／Enter（body 分段）、\n"
            "     PgUp／PgDn 換頁，確認刪字 reflow 與換頁顯示。\n"
            "  5. 按住左鍵拖曳選取多字（可跨段、可反向），確認藍色 shading 跟手；\n"
            "     試 Backspace 刪除選取、點字元樣式套用至選取、組字 Enter 替換選取。\n"
            "  6. 雙擊面板樣式項編輯參數（如內文 size_pt 改 16）確認全書即時重排；\n"
            "     「樣式」選單試新增（基於選取）／重新命名／刪除／另存模版。\n"
            "  7. 雙擊面板色票項改值（如暖黑 k 改 0.5）確認全書變色；\n"
            "     「樣式」選單試新增色票（樣式 color 欄可引用）／刪除色票（引用中會擋）。\n"
            "  8. 「樣式」選單「AI 樣式指派…」（需先於「設定」填好 AI 三欄位）：\n"
            "     逐段勾選採用建議後套用，確認一步 Ctrl+Z 可整批回退。\n"
            "  9. 目檢頁面字形與互動層對位；確認直排 IME 組字與候選字窗正常\n"
            "     （此為 §5.2 選 Qt 的關鍵理由）。\n\n"
            "尚未實作（[Shell]，後續工程）：\n"
            "  直排畫布內嵌 IME 即點即打（本 demo 以輸入區＋Enter 代替）、\n"
            "  跨段選取套段落樣式、框內拖曳選取。",
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
