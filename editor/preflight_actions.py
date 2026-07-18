"""preflight 動作 mixin（Sprint 87）：把「匯出臨時 PDF → 機械 preflight → 結果面板」
從 EditorWindow 抽出（同 StyleActionsMixin 慣例，控管 app.py 行數）。

Sprint 94 起同一份臨時 PDF 也跑影像解析度與油墨總量兩項 §9 印廠條件檢查
（非 X-1a 條款、不影響 X 合規結論，見 preflight_panel 說明）。

Sprint 100 起改為背景執行緒＋快取（關 GAPS #47 (d)）：

- 判定層全在 editor.preflight_core（Qt 無關、pytest 已驗），本檔只負責執行緒
  調度與呈現，不重算也不修復。
- 執行緒起跑時取的是文件與模版的當下快照（兩者皆 frozen dataclass，worker 讀
  不到後續編輯），故報告永遠對應「送檢當下」的版本；期間文件被改動時於
  statusBar 據實聲明是快照，不假裝是最新結論。
- 快取只留最近一次（鍵見 preflight_core.preflight_cache_key），鍵一致才沿用。

依賴 EditorWindow 提供的 self.doc／self.template／self._doc_path／self.statusBar()。
"""
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, Signal
from PySide6.QtWidgets import QFileDialog

from cjkfolio.pdf_writer import PDFX_PROFILES
from cjkfolio.preflight import (
    image_resolution_summary,
    ink_coverage_summary,
    preflight_summary,
)
from editor.preflight_core import preflight_cache_key, run_preflight_checks
from editor.preflight_panel import PreflightDialog


class PreflightThread(QThread):
    """在 GUI 執行緒之外跑匯出與三項檢查（doc／template 為不可變快照）。"""

    done = Signal(object)    # PreflightResults
    failed = Signal(str)

    def __init__(self, doc, template, image_base_dir, pdfx="x-1a",
                 icc_profile=None, parent=None) -> None:
        super().__init__(parent)
        self._doc = doc
        self._template = template
        self._image_base_dir = image_base_dir
        self._pdfx = pdfx
        self._icc_profile = icc_profile

    def run(self) -> None:
        try:
            results = run_preflight_checks(
                self._doc, self._template, self._image_base_dir,
                pdfx=self._pdfx, icc_profile=self._icc_profile)
        except Exception as e:  # noqa: BLE001（匯出／檢查任何失敗都回主執行緒提示）
            self.failed.emit(str(e))
        else:
            self.done.emit(results)


class PreflightActionsMixin:
    """PDF/X preflight 面板入口（§6 Phase 4「preflight 面板」）。"""

    # 類別層預設值＝實例未設定前的初值（不必動 EditorWindow.__init__）
    _preflight_thread = None
    _preflight_key = None          # 快取鍵（送檢當下的文件指紋）
    _preflight_results = None      # 快取的三份報告
    _preflight_pending_key = None  # 執行中那一輪的鍵
    _preflight_args = None         # 該輪的 (pdfx, icc)，重算鍵比對新舊用
    _preflight_icc = None          # X-4 輸出 ICC 路徑（選過一次後沿用至關窗）

    def _run_preflight(self, pdfx: str = "x-1a"):
        """啟動 preflight：快取命中即刻開面板，否則交背景執行緒。

        pdfx="x-4" 須有輸出 ICC（X-4 強制嵌 DestOutputProfile）：未選過時開檔案
        選取器，使用者取消即不執行並於 statusBar 說明，不默默改跑 X-1a。

        回傳值：快取命中回該形態的 report（同 Sprint 87 語意）；改由背景跑時回
        None，報告於完成後經 _preflight_show 呈現（離屏驗證用 _preflight_wait）。
        """
        if self._preflight_thread is not None:
            self.statusBar().showMessage("preflight 檢查進行中，請稍候…")
            return None
        icc = None
        if pdfx == "x-4":
            icc = self._ensure_preflight_icc()
            if icc is None:
                self.statusBar().showMessage(
                    "未選輸出 ICC，PDF/X-4 preflight 未執行（X-4 須嵌輸出色彩描述檔）")
                return None
        key = preflight_cache_key(self.doc, self.template, self._doc_path.parent,
                                  pdfx=pdfx, icc_profile=icc)
        if key == self._preflight_key and self._preflight_results is not None:
            self._preflight_show(self._preflight_results, cached=True)
            return self._preflight_results.report

        thread = PreflightThread(self.doc, self.template, self._doc_path.parent,
                                 pdfx=pdfx, icc_profile=icc, parent=self)
        thread.done.connect(self._on_preflight_done)
        thread.failed.connect(self._on_preflight_failed)
        self._preflight_thread = thread
        self._preflight_pending_key = key
        self._preflight_args = (pdfx, icc)
        label = PDFX_PROFILES[pdfx].label
        self.statusBar().showMessage(f"{label} preflight 檢查中（背景執行，可繼續編輯）…")
        thread.start()
        return None

    def _ensure_preflight_icc(self):
        """取 X-4 用的 CMYK 輸出 ICC：已選過則沿用，否則開檔案選取器。

        回傳 Path 或 None（使用者取消）。選過的路徑留在本視窗，換檔請重選。
        """
        if self._preflight_icc is not None and Path(self._preflight_icc).exists():
            return Path(self._preflight_icc)
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 CMYK 輸出色彩描述檔（PDF/X-4 須嵌）", "",
            "ICC 色彩描述檔 (*.icc *.icm);;所有檔案 (*)")
        if not path:
            return None
        self._preflight_icc = Path(path)
        return self._preflight_icc

    def _preflight_wait(self, timeout_ms: int = 180000):
        """等背景 preflight 跑完並派送結果（離屏驗證與測試用；真視窗由事件圈派送）。

        回傳最近一份 X-1a report（逾時或失敗回 None）。
        """
        thread = self._preflight_thread
        if thread is not None:
            thread.wait(timeout_ms)
            QCoreApplication.processEvents()  # 派送 worker 送回的佇列訊號
        return self._preflight_results.report if self._preflight_results else None

    def _on_preflight_done(self, results) -> None:
        self._clear_preflight_thread()
        self._preflight_key = self._preflight_pending_key
        self._preflight_results = results
        self._preflight_pending_key = None
        self._preflight_show(results, cached=False)

    def _on_preflight_failed(self, message: str) -> None:
        self._clear_preflight_thread()
        self._preflight_pending_key = None
        self.statusBar().showMessage(f"preflight 匯出／檢查失敗：{message}")

    def _clear_preflight_thread(self) -> None:
        thread = self._preflight_thread
        self._preflight_thread = None
        if thread is not None:
            thread.wait()
            thread.deleteLater()

    def _preflight_show(self, results, cached: bool) -> None:
        """statusBar 摘要（印廠條件未達標時附註）＋結果面板。"""
        notes = []
        if not results.image_report.ok:
            notes.append(f"影像解析度：{image_resolution_summary(results.image_report)}")
        if not results.ink_report.ok:
            notes.append(f"油墨總量：{ink_coverage_summary(results.ink_report)}")
        marks = list(notes)
        if cached:
            marks.append("沿用上次結果（文件未變）")
        elif self._preflight_stale():
            marks.append("本報告為送檢當下的快照，其後的編輯未納入")
        tail = ("；" + "；".join(marks)) if marks else ""
        label = PDFX_PROFILES[results.profile].label
        self.statusBar().showMessage(
            f"{label} preflight：{preflight_summary(results.report)}{tail}")
        PreflightDialog(results.report, results.image_report,
                        results.ink_report, self, profile_label=label).exec()

    def _preflight_stale(self) -> bool:
        """檢查期間文件是否已被改動（改動則報告只代表送檢當下）。

        以該輪的形態與 ICC 重算鍵才比得準（形態不同本來就是不同的鍵）。
        """
        if self._preflight_key is None or self._preflight_args is None:
            return False
        pdfx, icc = self._preflight_args
        return preflight_cache_key(self.doc, self.template, self._doc_path.parent,
                                   pdfx=pdfx, icc_profile=icc) != self._preflight_key

    def closeEvent(self, event) -> None:
        """關窗前收掉背景執行緒（避免 QThread 執行中被銷毀）。"""
        self._clear_preflight_thread()
        super().closeEvent(event)
