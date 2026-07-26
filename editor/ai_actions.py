"""AI 動作 mixin（Sprint 104）：把 AI 設定面板與 AI 樣式指派從 EditorWindow 抽出
（同 StyleActionsMixin／PreflightActionsMixin 慣例，控管 app.py 行數）。

Sprint 104 起 AI 指派改為背景執行緒（關 GAPS #36 (b) 的「同步呼叫凍視窗」）：
全書級指派為數分鐘的網路往返，同步呼叫期間整個視窗無回應。

- 判定層（建議索引有效性）全在 editor.ai_assign_core（Qt 無關、pytest 已驗），
  本檔只負責執行緒調度與呈現。
- 送檢前取段落文字快照；結果回來時文字序列若已改動，**不套用**舊建議並據實
  提示重跑（照索引硬套會把建議安到別段上，屬沉默的錯派）。
- 不提供取消：底層為 urllib 阻塞請求，無可中斷點；使用者可在等待期間繼續
  編輯，回來的結果若已對不上就照上一條處置（GAPS #58）。

依賴 EditorWindow 提供的 self.doc／self.template／self.session／self.statusBar()／
self._after_template_change。
"""
from PySide6.QtCore import QCoreApplication, QThread, Signal
from PySide6.QtWidgets import QDialog

from cjkfolio.ai_config import load_ai_config
from cjkfolio.ai_style import suggest_styles
from editor.ai_assign import AssignReviewDialog
from editor.ai_assign_core import assignments_still_apply, paragraph_texts
from editor.ai_panel import DEFAULT_CONFIG_PATH, AiConfigDialog


class AiAssignThread(QThread):
    """在 GUI 執行緒之外跑一次樣式建議（work 為不吃外部可變狀態的無參呼叫）。"""

    done = Signal(object)    # SuggestResult
    failed = Signal(str)

    def __init__(self, work, parent=None) -> None:
        super().__init__(parent)
        self._work = work

    def run(self) -> None:
        try:
            result = self._work()
        except Exception as e:  # noqa: BLE001（連線／解析任何失敗都回主執行緒提示）
            self.failed.emit(str(e))
        else:
            self.done.emit(result)


class AiActionsMixin:
    """AI 設定面板與 AI 樣式指派入口（§4.4）。"""

    # 類別層預設值＝實例未設定前的初值（不必動 EditorWindow.__init__）
    _ai_thread = None
    _ai_texts = None  # 送檢當下的段落文字快照（建議索引的對映依據）

    def _show_ai_config(self) -> None:
        """開 AI 設定面板（§4.4 三欄位；儲存只到本機，statusBar 不含欄位值）。"""
        if AiConfigDialog(self).exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("AI 設定已儲存（本機 local/ai-config.local.json）")

    def _run_ai_assign(self, suggest=None) -> None:
        """AI 樣式指派入口（§4.4「初稿＋人工校正」；#36 (b)）。

        suggest 注入＝離屏可驗（callable(texts, candidates) -> SuggestResult）；
        None＝真呼叫使用者私有 endpoint（未設定顯示訊息不擋流程＝誠實失敗，
        同 CLI assign-styles exit 2 語意）。

        呼叫交背景執行緒（Sprint 104），期間可繼續編輯；校正對話框於結果回來
        後由 _on_ai_assign_done 開啟（離屏驗證用 _ai_assign_wait 等待派送）。
        """
        if self._ai_thread is not None:
            self.statusBar().showMessage("AI 指派進行中，請稍候…")
            return
        texts = [p.text for p in self.doc.paragraphs]
        candidates = sorted(self.template.paragraph_styles)
        default_style = self.template.md_mapping.get("paragraph", candidates[0])
        if suggest is None:
            # 讀設定面板寫的同一份本機檔（Sprint 104 修：原漏傳 path，真呼叫路徑
            # 一觸即 TypeError；smoke 一律注入替身故從未走到，見 GAPS #58）
            config = load_ai_config(DEFAULT_CONFIG_PATH)
            if not (config.base_url and config.model):
                self.statusBar().showMessage(
                    "尚未設定 AI（「設定」選單填 Base URL 與 Model；AI 為選配增強）")
                return

            spec = self.template.auto_toc
            levels = spec.level_hints() if spec is not None else ()

            def work():
                return suggest_styles(texts, candidates, config,
                                      default_style=default_style,
                                      toc_levels=levels)
        else:
            def work():
                return suggest(texts, candidates)

        self._ai_texts = paragraph_texts(self.doc)
        thread = AiAssignThread(work, parent=self)
        thread.done.connect(self._on_ai_assign_done)
        thread.failed.connect(self._on_ai_assign_failed)
        self._ai_thread = thread
        self.statusBar().showMessage(
            "AI 指派連線中（全書級約數分鐘，背景執行，可繼續編輯）…")
        thread.start()

    def _ai_assign_wait(self, timeout_ms: int = 600000) -> None:
        """等背景指派跑完並派送結果（離屏驗證與測試用；真視窗由事件圈派送）。"""
        thread = self._ai_thread
        if thread is not None:
            thread.wait(timeout_ms)
            QCoreApplication.processEvents()  # 派送 worker 送回的佇列訊號

    def _on_ai_assign_done(self, result) -> None:
        """建議回來：索引仍對得上才開校正對話框，對不上據實請重跑。"""
        self._clear_ai_thread()
        snapshot = self._ai_texts
        self._ai_texts = None
        if snapshot is not None and not assignments_still_apply(self.doc, snapshot):
            self.statusBar().showMessage(
                "AI 指派已回，但等待期間段落文字已改動，建議的段序不再對應，"
                "未套用（請重跑）")
            return
        dlg = AssignReviewDialog(self.doc, self.template, result.assignments,
                                 self._apply_assignments,
                                 warnings=result.warnings,
                                 toc_entries=getattr(result, "toc_entries", ()),
                                 parent=self)
        dlg.exec()

    def _on_ai_assign_failed(self, message: str) -> None:
        self._clear_ai_thread()
        self._ai_texts = None
        self.statusBar().showMessage(f"AI 指派失敗：{message}")

    def _clear_ai_thread(self) -> None:
        thread = self._ai_thread
        self._ai_thread = None
        if thread is not None:
            thread.wait()
            thread.deleteLater()

    def _apply_assignments(self, assignments, toc_entries=None,
                           generate_toc: bool = False):
        """批次改派套用（session.apply_para_styles 單一 undo 步）；回錯誤訊息或 None。

        樣式、目次條目宣告、生成目次頁三件事一次送進 session（Sprint 135）：分開送
        會變三步 undo，違反對話框頂部「單一 undo 步可整批回退」的承諾。
        """
        if not assignments and not toc_entries and not generate_toc:
            self.statusBar().showMessage("未採用任何建議（文件未變更）")
            return None
        # 套用前先數會被自動換頁的段（Sprint 141）：session 會替宣告 starts_page 的
        # 樣式補節首標記，全書頁數因此跳動。不報出來，使用者只會看到頁數莫名變多
        page_starts = sum(
            1 for idx, name in assignments.items()
            if idx > 0 and self.doc.paragraphs[idx].master is None
            and getattr(self.template.paragraph_styles.get(name), "starts_page", False))
        try:
            res = self.session.apply_para_styles(
                assignments, toc_entries, generate_toc=generate_toc)
        except (KeyError, ValueError, IndexError) as err:
            return f"無法套用：{err}"
        parts = [f"AI 批次改派 {len(assignments)} 段"]
        if page_starts:
            parts.append(f"其中 {page_starts} 段依模版宣告自動起新頁")
        if toc_entries:
            parts.append(f"目次條目 {len(toc_entries)} 段")
        if generate_toc:
            entries = sum(1 for p in self.doc.paragraphs if p.toc_title)
            # 標頁碼的條目數要列出來：模版可宣告某層不標頁碼（如部名），
            # 全部條目都落在該層時會生出「一個頁碼都沒有」的目次，這裡不讓它沉默
            styles = set(self.template.auto_toc.entry_styles.values())
            numbered = sum(1 for p in self.doc.paragraphs
                           if p.style in styles and p.page_no)
            parts.append(f"生成目次 {entries} 條（{numbered} 條標頁碼），"
                         f"全書 {len(self.session.layout.pages)} 頁")
        self._after_template_change(
            res, "、".join(parts) + "（單一 undo 步可整批回退）")
        return None

    def closeEvent(self, event) -> None:
        """關窗前收掉背景執行緒（避免 QThread 執行中被銷毀）。"""
        self._clear_ai_thread()
        super().closeEvent(event)
