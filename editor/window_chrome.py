"""視窗骨架 mixin（Sprint 136）：選單列與側邊面板的組裝。

自 EditorWindow.__init__ 原樣抽出（同 StyleActionsMixin 與 ImageActionsMixin 慣例，
控管 app.py 行數；Sprint 136 加「文字框」選單後 app.py 破 800 行上限）。

只有組裝，沒有行為：每個 QAction 都接到別處已實作的 handler，故本檔改動的風險
限於「選單長什麼樣」，不涉編輯語意。順序刻意維持與原 __init__ 一致（選單列由左
至右的排列即這裡的先後）。

依賴 EditorWindow 提供的各 mixin handler、self.view、self.template。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDockWidget

from editor.page_panel import PagePanel
from editor.style_panel import StylePanel


class WindowChromeMixin:
    """選單列與面板的組裝（EditorWindow.__init__ 呼叫一次）。"""

    def _build_chrome(self) -> None:
        file_menu = self.menuBar().addMenu("檔案")
        for label, key, handler in (  # 檔案生命週期（Sprint 126）
            ("新建", "Ctrl+N", self._new_document),
            ("開啟…", "Ctrl+O", self._open_document_dialog),
            (None, None, None),
            ("儲存", "Ctrl+S", lambda: self._save_document()),
            ("另存新檔…", "Ctrl+Shift+S", lambda: self._save_document_as()),
            (None, None, None),
        ):
            if label is None:
                file_menu.addSeparator()
                continue
            action = QAction(label, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(handler)
            file_menu.addAction(action)
        import_action = QAction("匯入稿件…（txt／md／docx）", self)
        import_action.triggered.connect(lambda: self._import_manuscript_dialog())
        file_menu.addAction(import_action)
        book_action = QAction("組裝書冊…", self)  # 多章組裝＋自動目錄（Sprint 131 丁2）
        book_action.triggered.connect(lambda: self._assemble_book_dialog())
        file_menu.addAction(book_action)
        file_menu.addSeparator()
        export_action = QAction("轉存為 PDF…", self)  # 印前成品出口（Sprint 127）
        export_action.setShortcut(QKeySequence("Ctrl+E"))  # InDesign 轉存慣例
        export_action.triggered.connect(lambda: self._export_pdf_dialog())
        file_menu.addAction(export_action)

        edit_menu = self.menuBar().addMenu("編輯")
        undo_action = QAction("復原", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)  # Ctrl+Z
        undo_action.triggered.connect(self._on_undo)
        redo_action = QAction("重做", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)  # Ctrl+Y／Ctrl+Shift+Z
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        find_action = QAction("尋找…", self)  # 全文檢索（Sprint 128 丙1）
        find_action.setShortcut(QKeySequence("Ctrl+F"))
        find_action.triggered.connect(lambda: self._open_find_dialog())
        edit_menu.addAction(find_action)
        replace_action = QAction("取代…", self)
        replace_action.setShortcut(QKeySequence("Ctrl+H"))
        replace_action.triggered.connect(lambda: self._open_find_dialog(replace=True))
        edit_menu.addAction(replace_action)

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
        layout_menu.addSeparator()  # 手動空行推行（Sprint 141）：章名沒換頁時的備援
        blank_add = QAction("在游標段前插入空行", self)
        blank_add.setShortcut(QKeySequence("Ctrl+Shift+Return"))
        blank_add.triggered.connect(self._insert_blank_line)
        layout_menu.addAction(blank_add)
        blank_del = QAction("移除游標段前的空行", self)  # 空行畫布上點不到，故配對提供
        blank_del.triggered.connect(self._remove_blank_line)
        layout_menu.addAction(blank_del)
        layout_menu.addSeparator()
        trim_action = QAction("成品尺寸…", self)  # 換開本（Sprint 140 甲）
        trim_action.triggered.connect(lambda: self._page_size_dialog())
        layout_menu.addAction(trim_action)
        footer_action = QAction("書眉與頁碼…", self)  # 改字與挪位置（Sprint 142）
        footer_action.triggered.connect(lambda: self._footer_dialog())
        layout_menu.addAction(footer_action)

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
        view_menu.addSeparator()  # 對頁檢視（雙頁併排，Sprint 129）：純檢視，不影響匯出
        self._facing_action = QAction("對頁檢視（雙頁併排）", self)
        self._facing_action.setCheckable(True)
        self._facing_action.setShortcut(QKeySequence("Ctrl+3"))
        self._facing_action.triggered.connect(self._toggle_facing)
        view_menu.addAction(self._facing_action)

        tools_menu = self.menuBar().addMenu("工具")  # 字數統計與文件資訊（Sprint 128 丙2）
        info_action = QAction("文件資訊…", self)
        info_action.triggered.connect(lambda: self._show_document_info())
        tools_menu.addAction(info_action)

        page_dock = QDockWidget("頁面", self)  # 縮圖面板（Sprint 125）
        self._page_panel = PagePanel(       # 拖曳重排（Sprint 142）：搬的是整節
            self._goto_page, on_context_menu=self._page_context_menu,
            on_reorder=self._reorder_pages)
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

        frame_menu = self.menuBar().addMenu("文字框")  # 整框增刪移（Sprint 136）
        for label, handler in (
            ("新增文字框（放在頁面中央）…", lambda: self._add_text_frame_dialog()),
            ("選取本頁文字框（多框時輪流）", self._select_page_frame_box),
            ("移除選取的文字框", self._remove_selected_frame_box),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            frame_menu.addAction(action)

        check_menu = self.menuBar().addMenu("檢查")
        check_action = QAction("PDF/X-1a preflight（機械檢查）…", self)
        check_action.triggered.connect(lambda: self._run_preflight())
        check_menu.addAction(check_action)
        check_x4_action = QAction("PDF/X-4 preflight（需輸出 ICC）…", self)
        check_x4_action.triggered.connect(lambda: self._run_preflight("x-4"))
        check_menu.addAction(check_x4_action)

        settings_menu = self.menuBar().addMenu("設定")
        press_action = QAction("印前設定…", self)  # 總墨量上限與 PDF/X（Sprint 140 乙）
        press_action.triggered.connect(self._show_press_config)
        settings_menu.addAction(press_action)
        ai_action = QAction("AI 設定…", self)
        ai_action.triggered.connect(self._show_ai_config)
        settings_menu.addAction(ai_action)

        help_action = QAction("Owner IME 實測說明", self)
        help_action.triggered.connect(self._show_help)
        self.menuBar().addMenu("說明").addAction(help_action)
