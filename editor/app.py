"""CJKFolio 編輯器真視窗（Phase 2〜5 逐 Sprint 構建；smoke C1〜C25 離屏守門）。

承 editor/canvas.py 雙層畫布與 cjkfolio/editing.py 編輯引擎（EditSession）：
  無參數開啟＝未命名空白文件從零開始（匯入稿件或於輸入欄打字，Sprint 123）、
  雙層畫布（底圖 PNG＋互動層字格）、點字格 → 反查文件／框游標（段或框／字／樣式）＋高亮、
  按住左鍵拖曳 → 範圍選取（可跨段；刪除／套字元樣式／IME 替換，Sprint 65）、
  文字輸入欄：組字後按 Enter 提交 → 於游標插入（body 全文 reflow／框鏈重佈局）→ 重繪
  → 游標跟隨、Ctrl+Z／Ctrl+Y 復原重做（body 與框統一歷史，Sprint 60）；
  選單面：稿件匯入、樣式與色票、模版庫、置圖與繞排、preflight、AI 指派、AI 設定；
  檢視面（Sprint 124）：Ctrl+滾輪游標錨縮放、Shift+滾輪水平捲動、中鍵／空白鍵
  拖曳平移、「檢視」選單（放大縮小／100%／符合頁面／符合寬度）＋狀態列縮放
  百分比；開窗整頁 fit、重繪保留縮放與視口中心。
  導航面（Sprint 125）：左側「頁面」縮圖面板（背景渲染、點選跳頁、目前頁高
  亮）、「版面」選單（上一頁／下一頁／首末頁／Ctrl+J 跳頁）＋狀態列「頁 N／M」。

誠實範圍（honest-planning R3）：
  [實作]（離屏 smoke_check.py 已驗）＝上列全部功能邏輯。
  待 Owner 真視窗（離屏測不了，GAPS #19／#23）＝IME 直排組字是否順、候選字窗、
          視覺對位、快捷鍵與拖曳手感。
  [Shell]（後續工程）＝直排畫布內嵌 IME 即點即打（現以下方輸入欄＋Enter 代替）、
          跨段選取套段落樣式、框內拖曳選取。

執行（自 repo 根，需真視窗環境）：
  python editor/app.py [文件路徑]   無參數＝空白文件；亦可雙擊 啟動編輯器.bat

製作者：黃政文
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence, QPen  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
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

from cjkfolio.document import load_document  # noqa: E402
from cjkfolio.editing import DocCursor, DocRange, DocSpan  # noqa: E402
from cjkfolio.images import ImageError  # noqa: E402
from cjkfolio.session import EditSession  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from editor.ai_actions import AiActionsMixin  # noqa: E402
from editor.blank_doc import blank_document  # noqa: E402
from editor.edit_actions import EditActionsMixin  # noqa: E402
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
from editor.import_actions import ImportActionsMixin  # noqa: E402
from editor.nav_actions import NavActionsMixin  # noqa: E402
from editor.page_panel import PagePanel  # noqa: E402
from editor.preflight_actions import PreflightActionsMixin  # noqa: E402
from editor.style_actions import StyleActionsMixin  # noqa: E402
from editor.style_panel import StylePanel  # noqa: E402

DEFAULT_DOC = ROOT / "samples" / "case-divider.doc.json"
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
DPI = 150
AUTHOR = "製作者：黃政文"


class EditorWindow(StyleActionsMixin, AiActionsMixin, PreflightActionsMixin,
                   ImageActionsMixin, ImportActionsMixin, EditActionsMixin,
                   NavActionsMixin, QMainWindow):
    def __init__(self, doc_path) -> None:
        super().__init__()
        # 編輯狀態單一事實來源＝EditSession（Sprint 61 接線；doc／layout／template
        # 由 property 委派＝樣式編輯後畫布與面板恆用現行模版，Sprint 71）
        template = load_template(str(TEMPLATE))
        if doc_path is None:  # 從零開始（Sprint 123）：未命名空白文件，匯入或打字起步
            self.session = EditSession(
                blank_document(template, TEMPLATE.stem), template)
            # 檔案不存在，僅取 parent 當置入圖／preflight 的相對路徑基準
            self._doc_path = ROOT / "未命名.doc.json"
        else:
            self.session = EditSession(load_document(str(doc_path)), template)
            self._doc_path = Path(doc_path)  # 置入圖相對路徑基準（preflight 匯出用）
        pages = self.layout_result.pages
        self.page = pages[0] if pages else None  # None＝空白文件畫空紙面（Sprint 123）
        self._update_window_title()
        self.cursor = None        # 目前選取 body 字格 (placed_idx, cell_idx)
        self.frame_cursor = None  # 目前選取框字格 ("frame", fi, li, ci)；與 body 游標互斥
        self._highlight = None
        self.selection = None     # 拖曳範圍選取（DocSpan，僅 body，Sprint 65）
        self._sel_items = []      # 選取範圍 shading items
        self._drag_anchor = None  # 拖曳起點 (para_idx, span)，按下 body 字格時設定
        self._did_fit_on_show = False  # 首次顯示整頁 fit（Sprint 124），只做一次

        if self.page is None:  # 先放預設語，_make_scene 的缺圖提示才不被蓋掉
            self.statusBar().showMessage(
                "從零開始：「檔案 > 匯入稿件」載入 txt／md／docx，"
                "或直接在下方輸入欄打字按 Enter 從第一頁開始"
            )
        else:
            self.statusBar().showMessage(
                "點頁面字格 → 反查游標；組字按 Enter 插入；Ctrl+Z／Ctrl+Y 復原重做"
            )
        self.scene, self._item_by_key = self._make_scene()
        self.view = CanvasView(self.scene, self._on_pick, self._on_key, self._on_drag,
                               on_move=self._on_image_move,
                               on_release=self._on_image_release,
                               on_drop=self._on_image_drop,
                               on_zoom=self._on_zoom_changed)

        self._ime = QLineEdit()
        self._ime.setPlaceholderText(
            "文字輸入欄：在此打字（注音／倉頡／拼音）按 Enter 插入；"
            "空白文件直接開始，點畫布字格可改插入位置"
        )
        self._ime.textChanged.connect(self._on_ime_preview)
        self._ime.returnPressed.connect(self._on_ime_commit)

        central = QWidget()
        box = QVBoxLayout(central)
        box.addWidget(self.view)
        box.addWidget(self._ime)
        self.setCentralWidget(central)

        self._page_label = QLabel("頁 −／−")  # 頁碼指示器（Sprint 125，_sync_page_panel 更新）
        self._page_label.setStyleSheet("color:#666; font-size:11px; padding:0 8px;")
        self.statusBar().addPermanentWidget(self._page_label)

        self._zoom_label = QLabel("100%")  # 縮放百分比（on_zoom 回呼更新，Sprint 124）
        self._zoom_label.setStyleSheet("color:#666; font-size:11px; padding:0 8px;")
        self.statusBar().addPermanentWidget(self._zoom_label)

        credit = QLabel(AUTHOR)
        credit.setStyleSheet("color:#999; font-size:11px; padding:0 8px;")
        self.statusBar().addPermanentWidget(credit)

        file_menu = self.menuBar().addMenu("檔案")
        import_action = QAction("匯入稿件…（txt／md／docx）", self)
        import_action.triggered.connect(lambda: self._import_manuscript_dialog())
        file_menu.addAction(import_action)

        edit_menu = self.menuBar().addMenu("編輯")
        undo_action = QAction("復原", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)  # Ctrl+Z
        undo_action.triggered.connect(self._on_undo)
        redo_action = QAction("重做", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)  # Ctrl+Y／Ctrl+Shift+Z
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)

        layout_menu = self.menuBar().addMenu("版面")  # 翻頁可見入口（Sprint 125）
        for label, keys, handler in (
            ("上一頁", ("PgUp",), lambda: self._turn_page(-1)),
            ("下一頁", ("PgDown",), lambda: self._turn_page(1)),
            ("第一頁", ("Ctrl+Home",), lambda: self._goto_page(1)),
            ("最後一頁", ("Ctrl+End",),
             lambda: self._goto_page(len(self.layout_result.pages))),
        ):  # QAction 攔下快捷鍵＝輸入欄 focus 時也可翻頁（view 鍵盤路徑為備援）
            action = QAction(label, self)
            action.setShortcuts([QKeySequence(k) for k in keys])
            action.triggered.connect(handler)
            layout_menu.addAction(action)
        layout_menu.addSeparator()
        goto_action = QAction("跳至頁碼…", self)
        goto_action.setShortcut(QKeySequence("Ctrl+J"))  # InDesign 慣例
        goto_action.triggered.connect(self._prompt_goto_page)
        layout_menu.addAction(goto_action)

        view_menu = self.menuBar().addMenu("檢視")
        for label, keys, handler in (
            ("放大", ("Ctrl+=", "Ctrl++"), self.view.zoom_in),
            ("縮小", ("Ctrl+-",), self.view.zoom_out),
            ("實際大小（100%）", ("Ctrl+1",), lambda: self.view.set_zoom(1.0)),
            ("符合頁面", ("Ctrl+0",), self.view.fit_page),
            ("符合寬度", ("Ctrl+2",), self.view.fit_width),
        ):  # 快捷鍵取 Acrobat／InDesign 慣例（Ctrl+0 整頁、Ctrl+1 實際大小）
            action = QAction(label, self)
            action.setShortcuts([QKeySequence(k) for k in keys])
            action.triggered.connect(handler)
            view_menu.addAction(action)

        page_dock = QDockWidget("頁面", self)  # 縮圖面板（Sprint 125）
        self._page_panel = PagePanel(self._goto_page)
        page_dock.setWidget(self._page_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, page_dock)

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
            ("選取圖片的文繞圖設定…", lambda: self._edit_image_wrap()),
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

        self._init_nav()  # 頁面面板首輪同步＋縮圖 debounce 計時器（Sprint 125）

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
        if self.page is None:  # 空白文件（Sprint 123）：畫空紙面等匯入或第一字
            width_px = self.template.page_width_mm / 25.4 * DPI
            height_px = self.template.page_height_mm / 25.4 * DPI
            scene.addRect(0, 0, width_px, height_px,
                          QPen(QColor("#c8c8c8")), QBrush(QColor("white")))
            return scene, {}
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
        """reflow 後重繪：換上新 scene，高亮與選取清空（舊 scene 連同其 item 一併丟棄）。

        先把 self.page 換成新版面中同一頁號的頁物件（Sprint 103）：self.page 是頁
        物件快照，重排後不換即以舊幾何重繪＝畫面看不到這次重排（繞排開關與樣式
        改動皆屬此類）。重排後頁數縮減時夾到末頁（該頁已不存在，退到仍在的最後
        一頁而非炸掉）。
        """
        pages = self.layout_result.pages
        if not pages:  # 空白文件（undo 回空亦同）：回空紙面（Sprint 123）
            self.page = None
        elif self.page is None:
            self.page = pages[0]
        else:
            self.page = pages[min(self.page.number, len(pages)) - 1]
        # 視角保留（Sprint 124）：縮放屬 view transform 本就跨 setScene 存活，
        # 視口中心需自行記回，否則每次 reflow（每打一字）畫面就跳回原點
        center = self.view.mapToScene(self.view.viewport().rect().center())
        self.scene, self._item_by_key = self._make_scene()
        self.view.setScene(self.scene)
        self.view.centerOn(center)
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
        self._update_window_title()  # 匯入／復原後標題跟隨現行文件名（Sprint 123）
        if hasattr(self, "_thumb_timer"):  # 頁面面板與指示器跟隨（Sprint 125）
            self._sync_page_panel()

    def _update_window_title(self) -> None:
        """視窗標題＝產品名＋現行文件名（init 與 _rebuild 呼叫）。"""
        self.setWindowTitle(f"CJKFolio 編輯器：{self.doc.title or '未命名'}")

    def _on_zoom_changed(self, factor: float) -> None:
        """CanvasView 縮放回呼：狀態列百分比跟隨（100%＝150dpi 像素 1:1）。"""
        self._zoom_label.setText(f"{round(factor * 100)}%")

    def showEvent(self, event) -> None:
        """首次顯示整頁 fit（Sprint 124）：開窗先看得到整張紙面，再自行縮放。"""
        super().showEvent(event)
        if not self._did_fit_on_show:
            self._did_fit_on_show = True
            QTimer.singleShot(0, self.view.fit_page)  # 佈局落定後再量視口

    def closeEvent(self, event) -> None:
        """關窗收攏背景縮圖執行緒（Sprint 125：運行中被銷毀會 abort 進程）。"""
        self._shutdown_thumbnails()
        super().closeEvent(event)

    def _on_pick(self, item, scene_pos=None) -> None:
        if self.page is None:  # 空紙面無字格；點擊不動作（Sprint 123）
            return
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
        # 視口跟隨（Sprint 123）：直排第一行在紙面右緣，小視窗下插入或點選
        # 後游標可能在可視區外，捲到可見才不迷路
        self.view.ensureVisible(hl)

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

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "Owner IME 實測說明",
            "功能邏輯已由離屏 smoke（C1〜C25）自動驗證；本清單是只有真人\n"
            "真視窗才驗得了的項目（GAPS #19／#23）。\n\n"
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
            "     （此為 §5.2 選 Qt 的關鍵理由）。\n"
            "  10. 縮放平移：Ctrl+滾輪（游標處放大縮小）、Shift+滾輪左右捲動、\n"
            "     中鍵或按住空白鍵拖曳平移；Ctrl+0 整頁、Ctrl+1 100%、Ctrl+2 符合\n"
            "     寬度，確認縮放錨點與拖曳手感、狀態列百分比跟隨。\n"
            "  11. 頁面導航：左側「頁面」面板點縮圖跳頁（目前頁藍色高亮）、\n"
            "     「版面」選單上一頁／下一頁／第一頁／最後一頁、Ctrl+J 跳至頁碼，\n"
            "     確認縮圖清晰可辨、點選跳頁順手、狀態列「頁 N／M」跟隨。\n\n"
            "尚未實作（[Shell]，後續工程）：\n"
            "  直排畫布內嵌 IME 即點即打（現以下方輸入欄＋Enter 代替）、\n"
            "  跨段選取套段落樣式、框內拖曳選取。",
        )


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    doc_path = argv[1] if len(argv) > 1 else None  # 無參數＝從零開始（Sprint 123）
    app = QApplication.instance() or QApplication(argv[:1])
    win = EditorWindow(doc_path)
    win.resize(760, 900)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
