"""preflight 動作 mixin（Sprint 87）：把「匯出臨時 PDF → 機械 preflight → 結果面板」
從 EditorWindow 抽出（同 StyleActionsMixin 慣例，控管 app.py 行數）。

Sprint 94 起同一份臨時 PDF 也跑影像解析度與油墨總量兩項 §9 印廠條件檢查
（非 X-1a 條款、不影響 X 合規結論，見 preflight_panel 說明）。

依賴 EditorWindow 提供的 self.doc／self.template／self._doc_path／self.statusBar()。
"""
import tempfile
from pathlib import Path

from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import (
    check_image_resolution,
    check_ink_coverage,
    check_pdfx,
    image_resolution_summary,
    ink_coverage_summary,
    preflight_summary,
)
from editor.preflight_panel import PreflightDialog


class PreflightActionsMixin:
    """PDF/X preflight 面板入口（§6 Phase 4「preflight 面板」）。"""

    def _run_preflight(self):
        """把當前文件匯出臨時 PDF/X-1a → 三項機械檢查 → 結果面板。

        v1 只驗預設 X-1a（無需 ICC）；X-4 需自備輸出 ICC，editor 尚無 ICC 選取（後續）。
        匯出／檢查失敗（如缺字型）以 statusBar 提示不 crash。回傳 X-1a report
        （statusBar 與退出語意依 X-1a，印廠條件兩項只警示）供離屏驗證；
        影像與墨量報告掛於面板（dlg.image_report／dlg.ink_report）。
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                pdf_path = Path(td) / "preflight.pdf"
                export_pdf(self.doc, self.template, pdf_path,
                           image_base_dir=self._doc_path.parent)
                report = check_pdfx(str(pdf_path), profile="x-1a")
                image_report = check_image_resolution(str(pdf_path))
                ink_report = check_ink_coverage(str(pdf_path))
        except Exception as e:  # noqa: BLE001（匯出／檢查任何失敗都提示不中斷編輯）
            self.statusBar().showMessage(f"preflight 匯出／檢查失敗：{e}")
            return None
        notes = []
        if not image_report.ok:
            notes.append(f"影像解析度：{image_resolution_summary(image_report)}")
        if not ink_report.ok:
            notes.append(f"油墨總量：{ink_coverage_summary(ink_report)}")
        tail = ("；" + "；".join(notes)) if notes else ""
        self.statusBar().showMessage(f"preflight：{preflight_summary(report)}{tail}")
        PreflightDialog(report, image_report, ink_report, self).exec()
        return report
