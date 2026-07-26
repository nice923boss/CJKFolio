"""檔案生命週期動作 mixin（Sprint 126；分檔慣例控 app.py 行數）。

出版工作流補完系列乙1〜乙3：儲存／另存（過去編輯成果無法保存＝改完關窗即
遺失）、開啟／新建、髒標記與關閉確認。

髒判定＝document 引用同一性：EditSession 的 undo 堆疊存 (document, template,
cursor) 引用三元組，undo 回到存檔點時 session.document 就是存檔當下同一個
物件（session.py:133 一手實查），故「self.doc is not self._saved_document」
即未存改動，undo 回存檔點自動轉乾淨，無需序列化比對。

儲存目標防呆（pre-mortem 首險＝覆寫非文件檔）：儲存一律要求 `.doc.json` 結
尾且檔案已存在，否則轉另存對話框；另存強制補齊 `.doc.json`。匯入 txt／md
不改 _doc_path（import_actions 既有行為），故「儲存」永遠不會指到稿件原檔。

誠實邊界：文件檔（document@2）存段落／樣式引用／置圖／文字框，**不含模版
參數**（樣式定義住在模版檔，變更需「樣式 > 另存模版」既有功能）；模版改過
時於儲存訊息與關閉確認中明示，不默默讓使用者以為樣式跟著存了。

modal（另存／開啟對話框、關閉確認）offscreen 跑不了：核心函式（_write_document
／_open_document／_new_document）與對話框薄殼分離，smoke 測核心與分支。

依賴 EditorWindow 提供：self.session／self.doc／self.template／self.layout_result
／self.page／self.cursor／self.frame_cursor／self._image_idx／self._doc_path／
self._rebuild()／self._update_window_title()／self.statusBar()。
"""
from pathlib import Path

from cjkfolio.document import (
    DocumentError,
    load_document,
    save_document,
    unknown_style_refs,
)
from cjkfolio.session import EditSession
from editor.blank_doc import blank_document
from editor.book_binding import with_binding

DOC_SUFFIX = ".doc.json"
FILE_FILTER = f"CJKFolio 文件 (*{DOC_SUFFIX})"


class FileActionsMixin:
    # 類別層預設（未 _init_file_state 前一律視為乾淨，標題不誤標 *）
    _saved_document = None
    _saved_template = None

    def _init_file_state(self) -> None:
        """__init__ 尾端：以開檔當下的 document／template 引用為存檔基準。"""
        self._saved_document = self.session.document
        self._saved_template = self.session.template
        self._update_window_title()

    def _is_dirty(self) -> bool:
        return (self._saved_document is not None
                and self.doc is not self._saved_document)

    def _template_note(self) -> str:
        """模版改過時的誠實提醒（文件檔不含模版參數）。"""
        if (self._saved_template is not None
                and self.template is not self._saved_template):
            return "；樣式／模版變更不隨文件檔儲存，需「樣式 > 另存模版」"
        return ""

    # --- 儲存 ---

    def _save_document(self) -> bool:
        """Ctrl+S：寫回 _doc_path；未命名（檔不存在）或非 .doc.json 一律轉另存。"""
        path = self._doc_path
        if not path.name.endswith(DOC_SUFFIX) or not path.exists():
            return self._save_document_as()
        return self._write_document(path)

    def _save_document_as(self) -> bool:
        """Ctrl+Shift+S：選路徑另存（強制 .doc.json 結尾）。"""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "另存文件", str(self._doc_path), FILE_FILTER)
        if not path:
            self.statusBar().showMessage("已取消儲存")
            return False
        return self._write_document(self._force_suffix(Path(path)))

    @staticmethod
    def _force_suffix(path: Path) -> Path:
        """另存路徑強制 `.doc.json`：裸名補齊、`.json` 升格，其餘一律追加。"""
        if path.name.endswith(DOC_SUFFIX):
            return path
        if path.name.endswith(".json"):
            return path.with_name(path.name[: -len(".json")] + DOC_SUFFIX)
        return path.with_name(path.name + DOC_SUFFIX)

    def _write_document(self, path: Path) -> bool:
        """寫檔核心：成功後 _doc_path 跟隨、存檔基準更新、標題 * 消失。"""
        path = Path(path)
        try:
            save_document(self.doc, path)
        except OSError as err:
            self.statusBar().showMessage(f"儲存失敗「{path}」：{err}")
            return False
        self._doc_path = path
        self._saved_document = self.doc
        self._update_window_title()
        self.statusBar().showMessage(
            f"已儲存「{path.name}」：{len(self.doc.paragraphs)} 段、"
            f"{len(self.layout_result.pages)} 頁{self._template_note()}")
        return True

    # --- 開啟／新建 ---

    def _open_document_dialog(self) -> None:
        """Ctrl+O：髒先確認，選 .doc.json 開啟。"""
        from PySide6.QtWidgets import QFileDialog

        if not self._confirm_discard("開啟文件"):
            self.statusBar().showMessage("已取消開啟")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "開啟文件", str(self._doc_path.parent), FILE_FILTER)
        if not path:
            self.statusBar().showMessage("已取消開啟")
            return
        self._open_document(path)

    def _open_document(self, path) -> bool:
        """開啟核心：換工作檔（undo 歷史清空，與匯入的一步可回不同語意）。

        兩段守門與匯入同慣例：讀檔／解析失敗、文件引用現行模版沒有的樣式
        （編輯器同時只持一份模版），皆據實提示且目前文件不動。"""
        path = Path(path)
        try:
            doc = load_document(str(path))
        except DocumentError as err:
            self.statusBar().showMessage(f"無法開啟：{err}")
            return False
        unknown = unknown_style_refs(doc, self.template)
        if unknown:
            self.statusBar().showMessage(
                f"無法開啟「{path.name}」：文件引用現行模版沒有的樣式 "
                f"{'、'.join(unknown)}（目前文件未變動）")
            return False
        try:
            # with_binding＝未宣告裝訂補頁者補足 4 的倍數（Sprint 144）
            session = EditSession(with_binding(doc), self.template)
        except KeyError as err:  # 其餘引用缺失（字元樣式／主版），重排快速失敗
            self.statusBar().showMessage(
                f"無法開啟「{path.name}」：{err}（目前文件未變動）")
            return False
        self._adopt_session(session, path)
        self.statusBar().showMessage(
            f"已開啟「{path.name}」：{len(doc.paragraphs)} 段、"
            f"{len(self.layout_result.pages)} 頁")
        return True

    def _new_document(self) -> None:
        """Ctrl+N：髒先確認，換未命名空白文件（Sprint 123 空紙面起始）。"""
        if not self._confirm_discard("新建文件"):
            self.statusBar().showMessage("已取消新建")
            return
        template = self.session.template
        session = EditSession(
            with_binding(blank_document(template, self.doc.template)), template)
        # 未命名不落地：僅沿用現行目錄當置入圖／preflight 相對基準（Sprint 123）
        self._adopt_session(session, self._doc_path.with_name(f"未命名{DOC_SUFFIX}"))
        self.statusBar().showMessage(
            "已新建未命名空白文件：匯入稿件或在輸入欄打字開始")

    def _adopt_session(self, session, doc_path) -> None:
        """換 session 的集中重置（開啟／新建共用）：游標／選取／置圖選取歸零、
        存檔基準改記新檔、重繪（頁面面板／縮圖／標題隨 _rebuild 跟上）。"""
        self.session = session
        self._doc_path = Path(doc_path)
        pages = self.layout_result.pages
        self.page = pages[0] if pages else None
        self.cursor = None
        self.frame_cursor = None
        self._image_idx = None
        self._saved_document = session.document
        self._saved_template = session.template
        self._rebuild()

    # --- 關閉確認 ---

    def _confirm_discard(self, action: str) -> bool:
        """髒時三選一（儲存／不儲存／取消）；乾淨直接放行。

        modal 離屏跑不了：smoke 以替身函式驗呼叫端分支（closeEvent／開啟／新建），
        本函式的按鈕邏輯屬真視窗項（GAPS #19 批次）。"""
        if not self._is_dirty():
            return True
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self)
        box.setWindowTitle(action)
        box.setText(
            f"「{self.doc.title or '未命名'}」有未儲存的變更，要先儲存嗎？"
            f"{self._template_note()}")
        save_btn = box.addButton("儲存", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("不儲存", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_btn:
            return self._save_document()  # 另存被取消＝整個動作取消（不丟改動）
        return clicked is not cancel_btn
