"""稿件匯入的呈現層（Sprint 107）：檔案選單 → 選檔 → 換掉目前稿件 → 重繪。

判定層在 editor/import_core.py（Qt 無關，pytest 基線已驗分派與模版推導）；
本層只負責檔案對話框、畫布更新與訊息，同 Sprint 100／104 的兩層分工。

不設「確定要取代嗎」的 modal 確認：匯入走 session.replace_document 入統一 undo
歷史，誤匯入一步 Ctrl+Z 即回（同 Sprint 77 套用整份模版的處置），且 offscreen
驗證跑不了 modal。取代的事實與復原方式一律寫在 statusBar 訊息裡，不靜默。
"""
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from editor.import_core import FILE_DIALOG_FILTER, import_manuscript


class ImportActionsMixin:
    """需要宿主提供：session、doc、layout_result、page、_rebuild、statusBar。"""

    def _import_manuscript_dialog(self, path=None) -> None:
        """匯入 txt／md／docx 為新稿件（取代目前文件，一步 undo 可回）。

        兩段錯誤各自攔在原地並據實提示，不讓壞稿進到畫布：解析階段（格式不支援、
        檔案讀不到、編碼不是 UTF-8、docx 不是有效 zip）與套用階段（稿件引用現行
        模版沒有的樣式）。
        """
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "匯入稿件（txt／md／docx）", "", FILE_DIALOG_FILTER)
        if not path:
            self.statusBar().showMessage("已取消匯入稿件")
            return
        path = Path(path)

        try:
            # 模版 id 取自目前文件的宣告（編輯器同時只持一份模版）
            incoming = import_manuscript(
                path, self.session.template, self.doc.template)
        except (OSError, ValueError, UnicodeDecodeError) as err:
            self.statusBar().showMessage(f"無法匯入「{path.name}」：{err}")
            return

        try:
            result = self.session.replace_document(incoming)
        except KeyError as err:
            self.statusBar().showMessage(
                f"無法匯入「{path.name}」：稿件引用現行模版沒有的樣式 {err}"
                "（原稿未變動）")
            return
        if result is None:
            self.statusBar().showMessage(f"「{path.name}」與目前稿件相同，未變更")
            return

        self.page = self.layout_result.pages[0]  # 新稿一律從第一頁看起
        self._rebuild()
        self.statusBar().showMessage(self._import_summary(path, incoming))

    def _import_summary(self, path: Path, doc) -> str:
        """匯入結果摘要：段數、頁數、樣式分布，txt 另提示可接 AI 指派。"""
        styles = sorted({p.style for p in doc.paragraphs})
        summary = (f"已匯入「{path.name}」：{len(doc.paragraphs)} 段、"
                   f"{len(self.layout_result.pages)} 頁，"
                   f"樣式 {'、'.join(styles)}")
        if path.suffix.lower() == ".txt":
            # txt 無結構訊號（PLAN §4.4），全段落同一樣式，正是 AI 指派的用例
            summary += "；純文字全掛內文樣式，可用「樣式 → AI 樣式指派」分派結構"
        return summary + "（一步 Ctrl+Z 可回原稿）"
