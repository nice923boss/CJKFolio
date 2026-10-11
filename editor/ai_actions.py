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

進度與結果常駐（Sprint 149）：真稿 227 段跑 10 分鐘，舊版只在開頭閃一行
statusBar 訊息、任何點擊就被蓋掉，使用者看不出是否還在跑、是否生效。狀態列右側
常駐「批次進度條＋已耗時」，結束後留下結果摘要（不會被其他訊息蓋掉）。金鑰／
端點／模型錯誤與「整份沒有任何建議」改跳非 modal 警告框，不再開一張全空的校正表。

依賴 EditorWindow 提供的 self.doc／self.template／self.session／self.statusBar()／
self._after_template_change。
"""
import time

from PySide6.QtCore import QCoreApplication, QThread, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QProgressBar

from cjkfolio.ai_config import load_ai_config
from cjkfolio.ai_style import AiConfigProblem, suggest_styles
from cjkfolio.editing import (
    change_paragraph_styles, change_paragraph_toc_entries, insert_preface,
)
from cjkfolio.toc import manual_toc_indices
from editor.ai_assign import AssignReviewDialog
from editor.ai_assign_core import assignments_still_apply, paragraph_texts
from editor.ai_panel import DEFAULT_CONFIG_PATH, AiConfigDialog

_WARN_PREVIEW = 3  # 警告框列出的前幾條警告（其餘在校正表頂部）


class AiAssignThread(QThread):
    """在 GUI 執行緒之外跑一次樣式建議。

    work(report) 為不吃外部可變狀態的呼叫；report(已完成批數, 總批數, 說明)
    經 progress 訊號跨執行緒送回主執行緒（Qt 佇列連線，worker 不碰 UI）。
    """

    done = Signal(object)    # SuggestResult
    failed = Signal(str)
    config_problem = Signal(str)  # 金鑰／端點／模型錯（AiConfigProblem，訊息已白話）
    progress = Signal(int, int, str)

    def __init__(self, work, parent=None) -> None:
        super().__init__(parent)
        self._work = work

    def run(self) -> None:
        try:
            result = self._work(self.progress.emit)
        except AiConfigProblem as e:
            self.config_problem.emit(str(e))
        except Exception as e:  # noqa: BLE001（連線／解析任何失敗都回主執行緒提示）
            self.failed.emit(str(e))
        else:
            self.done.emit(result)


class AiActionsMixin:
    """AI 設定面板與 AI 樣式指派入口（§4.4）。"""

    # 類別層預設值＝實例未設定前的初值（不必動 EditorWindow.__init__）
    _ai_thread = None
    _ai_texts = None  # 送檢當下的段落文字快照（建議索引的對映依據）
    _ai_label = None  # 狀態列常駐：進度說明／結果摘要
    _ai_bar = None
    _ai_clock = None
    _ai_started = 0.0
    _ai_note = ""
    _ai_box = None    # 最近一次警告框（持有參照免被回收；離屏驗證也讀它）

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
            self.statusBar().showMessage("AI 指派進行中，請稍候（進度見狀態列右側）…")
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

            def work(report):
                return suggest_styles(texts, candidates, config,
                                      default_style=default_style,
                                      toc_levels=levels, progress=report)
        else:
            def work(report):
                return suggest(texts, candidates)

        self._ai_texts = paragraph_texts(self.doc)
        thread = AiAssignThread(work, parent=self)
        thread.done.connect(self._on_ai_assign_done)
        thread.failed.connect(self._on_ai_assign_failed)
        thread.config_problem.connect(self._on_ai_config_problem)
        thread.progress.connect(self._on_ai_progress)
        self._ai_thread = thread
        self.statusBar().showMessage(
            f"AI 指派連線中（{len(texts)} 段，全書級約數分鐘，背景執行，可繼續編輯）…")
        self._ai_progress_start(len(texts))
        thread.start()

    # ── 狀態列常駐進度 ────────────────────────────────────────────────────

    def _ai_progress_widgets(self):
        if self._ai_label is None:
            self._ai_label = QLabel()
            self._ai_label.setStyleSheet("font-size:11px; padding:0 8px;")
            self._ai_bar = QProgressBar()
            self._ai_bar.setFixedWidth(140)
            self._ai_bar.setFormat("%v／%m 批")
            self.statusBar().addPermanentWidget(self._ai_label)
            self.statusBar().addPermanentWidget(self._ai_bar)
            self._ai_clock = QTimer(self)
            self._ai_clock.setInterval(1000)
            self._ai_clock.timeout.connect(self._ai_tick)
        return self._ai_label, self._ai_bar

    def _ai_progress_start(self, paragraphs: int) -> None:
        label, bar = self._ai_progress_widgets()
        bar.setRange(0, 0)  # 尚未知道批數：忙碌動畫
        bar.show()
        label.setStyleSheet("font-size:11px; padding:0 8px;")
        self._ai_started = time.monotonic()
        self._ai_note = f"AI 指派準備送出 {paragraphs} 段"
        self._ai_tick()
        self._ai_clock.start()

    def _ai_elapsed(self) -> str:
        sec = int(time.monotonic() - self._ai_started)
        return f"{sec // 60} 分 {sec % 60:02d} 秒"

    def _ai_tick(self) -> None:
        self._ai_label.setText(f"{self._ai_note}（已 {self._ai_elapsed()}）")

    def _on_ai_progress(self, done: int, total: int, note: str) -> None:
        _, bar = self._ai_progress_widgets()
        bar.setRange(0, max(total, 1))
        bar.setValue(done)
        self._ai_note = f"AI 指派{note}"
        self._ai_tick()

    def _ai_progress_finish(self, summary: str, ok: bool) -> None:
        """結束：收進度條，結果摘要常駐狀態列（綠＝有結果、紅＝失敗）。"""
        label, bar = self._ai_progress_widgets()
        self._ai_clock.stop()
        bar.hide()
        label.setStyleSheet(
            f"font-size:11px; padding:0 8px; color:{'#060' if ok else '#b00'};")
        label.setText(summary)

    def _ai_warn(self, title: str, text: str) -> None:
        """非 modal 警告框（.open()：不擋事件圈，離屏驗證也不會卡住）。"""
        box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=self)
        box.open()
        self._ai_box = box

    # ── 結果處置 ──────────────────────────────────────────────────────────

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
        elapsed = self._ai_elapsed()
        if snapshot is not None and not assignments_still_apply(self.doc, snapshot):
            self.statusBar().showMessage(
                "AI 指派已回，但等待期間段落文字已改動，建議的段序不再對應，"
                "未套用（請重跑）")
            self._ai_progress_finish("AI 指派已回但段落已改動，未套用（請重跑）", False)
            return
        toc_entries = getattr(result, "toc_entries", ())
        suggested = sum(s is not None for s in result.assignments)
        tocs = sum(t is not None for t in toc_entries)
        if not suggested and not tocs:
            # 全部批次降級：開一張全空的校正表只會讓人以為「AI 判斷都不用改」
            self._ai_progress_finish(f"AI 指派沒有任何建議（{elapsed}）", False)
            self._ai_warn("AI 沒有回任何建議", "AI 指派跑完了，但沒有任何一段拿到建議，文件未變更。\n\n"
                          + "\n".join(result.warnings[:_WARN_PREVIEW]))
            return
        self._ai_progress_finish(
            f"AI 指派完成：{result.batches} 批、{suggested}／{len(result.assignments)} 段有建議、"
            f"目次條目 {tocs} 條（{elapsed}），請在校正表確認後套用", True)
        dlg = AssignReviewDialog(self.doc, self.template, result.assignments,
                                 self._apply_assignments,
                                 warnings=result.warnings,
                                 toc_entries=toc_entries,
                                 batches=result.batches,
                                 preface=getattr(result, "preface", None),
                                 parent=self)
        dlg.exec()

    def _on_ai_assign_failed(self, message: str) -> None:
        self._clear_ai_thread()
        self._ai_texts = None
        self.statusBar().showMessage(f"AI 指派失敗：{message}")
        self._ai_progress_finish(f"AI 指派失敗（{self._ai_elapsed()}）", False)
        self._ai_warn("AI 指派失敗", message)

    def _on_ai_config_problem(self, message: str) -> None:
        """金鑰／端點／模型錯：第一批就停（ai_style 已不再送後續批次）。"""
        self._clear_ai_thread()
        self._ai_texts = None
        self.statusBar().showMessage(f"AI 指派失敗：{message}")
        self._ai_progress_finish("AI 指派失敗：AI 設定有誤", False)
        self._ai_warn("AI 設定有誤", message)

    def _clear_ai_thread(self) -> None:
        thread = self._ai_thread
        self._ai_thread = None
        if thread is not None:
            thread.wait()
            thread.deleteLater()

    def _apply_assignments(self, assignments, toc_entries=None,
                           generate_toc: bool = False, preface=None):
        """批次改派套用（session.apply_para_styles 單一 undo 步）；回錯誤訊息或 None。

        樣式、目次條目宣告、生成目次頁三件事一次送進 session（Sprint 135）：分開送
        會變三步 undo，違反對話框頂部「單一 undo 步可整批回退」的承諾。
        preface（Sprint 159）＝(段序, 層級, 樣式)：同一步插入「前言」標題並列入目次。
        """
        if not assignments and not toc_entries and not generate_toc and preface is None:
            self.statusBar().showMessage("未採用任何建議（文件未變更）")
            return None
        # 套用前先數會被自動換頁的段（Sprint 141）：session 會替宣告 starts_page 的
        # 樣式補節首標記，全書頁數因此跳動。不報出來，使用者只會看到頁數莫名變多
        page_starts = sum(
            1 for idx, name in assignments.items()
            if idx > 0 and self.doc.paragraphs[idx].master is None
            and getattr(self.template.paragraph_styles.get(name), "starts_page", False))
        if preface is not None and preface[0] > 0 and getattr(
                self.template.paragraph_styles.get(preface[2]), "starts_page", False):
            page_starts += 1
        try:
            manual = (self._manual_toc_count(assignments, toc_entries, preface)
                      if generate_toc else 0)
            res = self.session.apply_para_styles(
                assignments, toc_entries, generate_toc=generate_toc, preface=preface)
        except (KeyError, ValueError, IndexError) as err:
            return f"無法套用：{err}"
        parts = [f"AI 批次改派 {len(assignments)} 段"]
        if page_starts:
            parts.append(f"其中 {page_starts} 段依模版宣告自動起新頁")
        if toc_entries:
            parts.append(f"目次條目 {len(toc_entries)} 段")
        if preface is not None:
            parts.append(f"在第 {preface[0] + 1} 段前插入「前言」標題")
        if generate_toc:
            entries = sum(1 for p in self.doc.paragraphs if p.toc_title)
            # 標頁碼的條目數要列出來：模版可宣告某層不標頁碼（如部名），
            # 全部條目都落在該層時會生出「一個頁碼都沒有」的目次，這裡不讓它沉默
            styles = set(self.template.auto_toc.entry_styles.values())
            numbered = sum(1 for p in self.doc.paragraphs
                           if p.style in styles and p.page_no)
            parts.append(f"生成目次 {entries} 條（{numbered} 條標頁碼），"
                         f"全書 {len(self.session.layout.pages)} 頁")
            if manual:
                parts.append(f"移除稿件自帶的手寫目錄 {manual} 段")
        message = "、".join(parts) + "（單一 undo 步可整批回退）"
        self._after_template_change(res, message)
        self._ai_progress_finish(f"已套用：{message}", True)
        return None

    def _manual_toc_count(self, assignments, toc_entries, preface=None) -> int:
        """套用後會被當成手寫目錄拿掉的段數（session 生成目次時 drop_manual）。"""
        spec = self.template.auto_toc
        if spec is None:
            return 0
        probe = change_paragraph_styles(self.doc, assignments)
        if toc_entries:
            probe = change_paragraph_toc_entries(probe, toc_entries)
        if preface is not None:
            probe = insert_preface(probe, *preface)
        return len(manual_toc_indices(probe, spec))

    def closeEvent(self, event) -> None:
        """關窗前收掉背景執行緒（避免 QThread 執行中被銷毀）。"""
        self._clear_ai_thread()
        super().closeEvent(event)
