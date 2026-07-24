"""轉存 PDF 動作 mixin（Sprint 127：乙4 匯出 PDF 介面，開 GAPS #82）。

把「收選項 → 背景匯出 export_pdf → 如實回報成品」從 EditorWindow 抽出（同
PreflightActionsMixin 慣例，控管 app.py 行數）。地基：export_pdf 全選項已由 CLI
與 pytest 驗（X-1a／X-4、ICC、裁切標記、first_page）；背景執行緒沿用 Sprint 100
preflight 的 QThread＋done／failed Signal 模式，避免全書渲染凍 GUI。

判定與寫檔全在 cjkfolio.pdf_writer.export_pdf；本檔只負責執行緒調度與呈現，不重算。
依賴 EditorWindow 提供的 self.doc／self.template／self.page／self._doc_path／statusBar()。
"""
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, Signal
from PySide6.QtWidgets import QDialog, QMessageBox

from cjkfolio.pdf_writer import PDFX_PROFILES, export_pdf
from editor.export_panel import ExportDialog


def _pdf_default_path(doc_path: Path) -> Path:
    """依文件路徑推預設 PDF 路徑（去 .doc.json 尾綴，換 .pdf，放同目錄）。"""
    name = doc_path.name
    if name.endswith(".doc.json"):
        name = name[:-len(".doc.json")]
    else:
        name = doc_path.stem
    return doc_path.parent / f"{name}.pdf"


def _force_pdf_suffix(path: Path) -> Path:
    """輸出路徑強制 .pdf（使用者手打無副檔名或別的副檔名時補正）。"""
    if path.suffix.lower() == ".pdf":
        return path
    return path.with_suffix(".pdf")


class ExportThread(QThread):
    """在 GUI 執行緒之外跑 export_pdf（doc／template 為不可變快照，worker 讀不到後續編輯）。"""

    done = Signal(object)   # PdfResult
    failed = Signal(str)

    def __init__(self, doc, template, out_path, image_base_dir, opts,
                 parent=None) -> None:
        super().__init__(parent)
        self._doc = doc
        self._template = template
        self._out_path = out_path
        self._image_base_dir = image_base_dir
        self._opts = opts  # {pdfx, icc_profile, first_page, footer, crop_marks}

    def run(self) -> None:
        try:
            result = export_pdf(self._doc, self._template, self._out_path,
                                image_base_dir=self._image_base_dir, **self._opts)
        except Exception as e:  # noqa: BLE001（匯出任何失敗都回主執行緒提示，不留半成品）
            self.failed.emit(str(e))
        else:
            self.done.emit(result)


class ExportActionsMixin:
    """檔案＞轉存為 PDF：印前成品出口（乙4；InDesign 對應＝檔案＞轉存）。"""

    # 類別層預設＝實例未設定前的初值（不必動 EditorWindow.__init__）
    _export_thread = None
    _export_result = None   # 最近一次成品的 PdfResult（離屏驗證取用）

    def _export_pdf_dialog(self) -> None:
        """開轉存對話框 → 背景 export_pdf → 成品報告；空白文件與匯出中據實擋。"""
        if self.page is None:
            self.statusBar().showMessage("空白文件無內容可轉存，請先輸入或匯入文稿")
            return
        if self._export_thread is not None:
            self.statusBar().showMessage("PDF 轉存進行中，請稍候…")
            return
        dlg = ExportDialog(_pdf_default_path(self._doc_path), parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("已取消 PDF 轉存")
            return
        opts = dlg.options()
        out_path = _force_pdf_suffix(opts.pop("out_path"))
        label = PDFX_PROFILES[opts["pdfx"]].label
        thread = ExportThread(self.doc, self.template, out_path,
                              self._doc_path.parent, opts, parent=self)
        thread.done.connect(self._on_export_done)
        thread.failed.connect(self._on_export_failed)
        self._export_thread = thread
        self.statusBar().showMessage(
            f"{label} 轉存中（背景執行，可繼續編輯）→ {out_path.name}…")
        thread.start()

    def _export_wait(self, timeout_ms: int = 180000):
        """等背景匯出跑完並派送結果（離屏驗證與測試用；真視窗由事件圈派送）。

        回傳最近一份 PdfResult（逾時或失敗回 None）。
        """
        thread = self._export_thread
        if thread is not None:
            thread.wait(timeout_ms)
            QCoreApplication.processEvents()  # 派送 worker 送回的佇列訊號
        return self._export_result

    def _on_export_done(self, result) -> None:
        self._clear_export_thread()
        self._export_result = result
        self._export_show(result)

    def _on_export_failed(self, message: str) -> None:
        self._clear_export_thread()
        self.statusBar().showMessage(f"PDF 轉存失敗：{message}")

    def _clear_export_thread(self) -> None:
        thread = self._export_thread
        self._export_thread = None
        if thread is not None:
            thread.wait()
            thread.deleteLater()

    def _export_show(self, result) -> None:
        """statusBar 一行結論＋完整報告對話框。

        印廠條件（影像 PPI、油墨總量）與字型授權為非 PDF/X 條款，如實列為提示不改動
        X 結論；沿用 CLI cmd_export_pdf 的語彙，讓 UI 與命令列同一套說法。
        """
        lines = [f"轉存完成：{result.page_count} 頁 → {result.path}"]
        lines.append(
            f"{result.pdfx_label} 識別：OutputIntent "
            f"{result.output_condition_identifier}"
            + ("（嵌入 ICC）" if result.icc_embedded else "（registry 識別，免嵌 ICC）"))
        if result.crop_marks:
            lines.append("裁切標記：8 條單 K 角標（MediaBox 外擴、BleedBox＝trim＋出血）")
        if result.images_placed:
            lines.append(f"置入圖：{result.images_placed} 張影像 XObject")
        notes = list(result.ppi_warnings) + list(result.tac_warnings) \
            + list(result.license_warnings)
        lines.extend(notes)
        if not notes:
            lines.append(
                "印廠條件（§9，非 PDF/X 條款）：影像解析度與油墨總量皆達標、"
                "字型授權皆可散布")
        tail = f"（含 {len(notes)} 項印廠條件提示）" if notes else ""
        self.statusBar().showMessage(
            f"{result.pdfx_label} 轉存完成：{result.page_count} 頁 → "
            f"{result.path.name}{tail}")
        QMessageBox.information(self, "PDF 轉存完成", "\n".join(lines))

    def closeEvent(self, event) -> None:
        """關窗前收掉背景匯出執行緒（避免 QThread 執行中被銷毀），再續原關窗鏈。"""
        self._clear_export_thread()
        super().closeEvent(event)
