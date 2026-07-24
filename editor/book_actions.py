"""書冊組裝動作 mixin（Sprint 131；分檔慣例控 app.py 行數）。

出版工作流補完系列丁2：多章組裝與自動目錄過去只有 CLI（assemble book.json
-o …），編輯器無入口。本 mixin 把 cjkfolio.toc.assemble_book_with_toc（Sprint 85
自動目錄、Sprint 108 多層階層）與 cjkfolio.book.assemble_book（Sprint 52 純 path
串接）接進「檔案 > 組裝書冊…」：選書冊清單 JSON → 以編輯器現行模版組裝 → 換為
當前工作文件（開啟語意，_adopt_session 共用），可翻頁、看自動目錄頁碼、再儲存。

模版一致守門（pre-mortem 首險＝用錯模版幾何靜默排版）：編輯器同時只持一份模版
（單模版硬綁 neizai-zhengli），故組裝前硬檢 book.template ＝現行文件 template id，
不一致即 fast-fail 不組裝（否則會用現行模版幾何排出頁碼全錯的目錄）。

first_page v1 固定 1（自足書冊清單自頁 1 起；前置頁偏移的自訂 first_page 入
GAPS #86）。組裝為同步 layout（非 raster），成本同既有 _rebuild（Sprint 130 已證
128→291 頁重排互動級），故不起背景執行緒。

modal（書冊清單選檔對話框、髒關閉確認）offscreen 跑不了：核心 _assemble_book 與
對話框薄殼 _assemble_book_dialog 分離，smoke 測核心與分支（file_actions 同慣例）。

依賴 EditorWindow 提供：self.doc／self.template／self.layout_result／self._doc_path
／self._confirm_discard()／self._adopt_session()／self.statusBar()。
"""
from pathlib import Path

from cjkfolio.book import BookError, assemble_book, load_book
from cjkfolio.document import unknown_style_refs
from cjkfolio.session import EditSession
from cjkfolio.toc import assemble_book_with_toc, toc_items
from editor.file_actions import DOC_SUFFIX

BOOK_FILTER = "書冊清單 (*.json)"


class BookActionsMixin:
    def _assemble_book_dialog(self) -> None:
        """檔案 > 組裝書冊…：髒先確認，選書冊清單 JSON 組裝。"""
        from PySide6.QtWidgets import QFileDialog

        if not self._confirm_discard("組裝書冊"):
            self.statusBar().showMessage("已取消組裝")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "組裝書冊", str(self._doc_path.parent), BOOK_FILTER)
        if not path:
            self.statusBar().showMessage("已取消組裝")
            return
        self._assemble_book(path)

    def _assemble_book(self, manifest_path) -> bool:
        """組裝核心：載入書冊清單 → 模版守門 → auto-TOC 感知組裝 → 換工作檔。

        任一步失敗（清單解析、模版不一致、章檔缺、樣式缺、空章、重排）皆據實
        提示且目前文件不動（同 _open_document 兩段守門慣例）。回傳是否成功。"""
        manifest = Path(manifest_path)
        try:
            book = load_book(str(manifest))
        except BookError as err:
            self.statusBar().showMessage(f"無法組裝書冊：{err}")
            return False
        if book.template != self.doc.template:
            self.statusBar().showMessage(
                f"無法組裝書冊「{manifest.name}」：書冊模版 {book.template!r} 與編輯器"
                f"現行模版 {self.doc.template!r} 不一致（編輯器單模版；目前文件未變動）")
            return False
        has_toc = any(ch.toc_spec for ch in book.chapters)
        try:
            if has_toc:
                items = toc_items(book, self.template, base_dir=manifest.parent,
                                  first_page=1)
                doc = assemble_book_with_toc(book, self.template,
                                             base_dir=manifest.parent, first_page=1)
            else:
                items = ()
                doc = assemble_book(book, base_dir=manifest.parent)
        except (BookError, KeyError, OSError) as err:
            self.statusBar().showMessage(
                f"無法組裝書冊「{manifest.name}」：{err}（目前文件未變動）")
            return False
        unknown = unknown_style_refs(doc, self.template)
        if unknown:
            self.statusBar().showMessage(
                f"無法組裝書冊「{manifest.name}」：引用現行模版沒有的樣式 "
                f"{'、'.join(unknown)}（目前文件未變動）")
            return False
        try:
            session = EditSession(doc, self.template)
        except KeyError as err:  # 字元樣式／主版等其餘引用缺失，重排快速失敗
            self.statusBar().showMessage(
                f"無法組裝書冊「{manifest.name}」：{err}（目前文件未變動）")
            return False
        # 組裝結果為新工作檔（未落地）：沿用清單所在目錄、以清單檔名衍生 .doc.json
        # 佔位（檔不存在故「儲存」轉「另存」），與 _new_document 未命名不落地同語意。
        placeholder = manifest.parent / (manifest.stem + DOC_SUFFIX)
        self._adopt_session(session, placeholder)
        marks = sum(1 for p in doc.paragraphs if p.master)
        # 章數只計內容章，不含 generate_toc 指令項（否則自動目錄會被誤報成一章）
        n_chapters = sum(1 for ch in book.chapters if not ch.toc_spec)
        toc_note = ""
        if has_toc:
            toc_note = (f"；自動目錄 {len(items)} 項"
                        if items else "；自動目錄（無列入章 toc_title）")
        self.statusBar().showMessage(
            f"已組裝書冊「{book.title}」：{n_chapters} 章 → "
            f"{len(doc.paragraphs)} 段（{marks} 節首）、"
            f"{len(self.layout_result.pages)} 頁{toc_note}")
        return True
