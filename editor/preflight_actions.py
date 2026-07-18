"""preflight 動作 mixin（Sprint 87）：把「匯出臨時 PDF → 機械 preflight → 結果面板」
從 EditorWindow 抽出（同 StyleActionsMixin 慣例，控管 app.py 行數）。

依賴 EditorWindow 提供的 self.doc／self.template／self._doc_path／self.statusBar()。
"""
import tempfile
from pathlib import Path

from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import check_pdfx, preflight_summary
from editor.preflight_panel import PreflightDialog


class PreflightActionsMixin:
    """PDF/X preflight 面板入口（§6 Phase 4「preflight 面板」）。"""

    def _run_preflight(self):
        """把當前文件匯出臨時 PDF/X-1a → 機械 preflight → 結果面板。

        v1 只驗預設 X-1a（無需 ICC）；X-4 需自備輸出 ICC，editor 尚無 ICC 選取（後續）。
        匯出／檢查失敗（如缺字型）以 statusBar 提示不 crash。回傳 report 供離屏驗證。
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                pdf_path = Path(td) / "preflight.pdf"
                export_pdf(self.doc, self.template, pdf_path,
                           image_base_dir=self._doc_path.parent)
                report = check_pdfx(str(pdf_path), profile="x-1a")
        except Exception as e:  # noqa: BLE001（匯出／檢查任何失敗都提示不中斷編輯）
            self.statusBar().showMessage(f"preflight 匯出／檢查失敗：{e}")
            return None
        self.statusBar().showMessage(f"preflight：{preflight_summary(report)}")
        PreflightDialog(report, self).exec()
        return report
