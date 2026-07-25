"""editor 轉存 PDF 介面的離屏煙霧驗證（C29；Sprint 127，自 smoke_check 分檔，行數紀律）。

離屏可驗：檔案選單「轉存為 PDF…」項與 Ctrl+E、空白文件守門、驅動選項對話框後背景
export_pdf 真產出成品（以 PyMuPDF 獨立讀回頁數／Title／頁面文字＝Gate 4 不同方法）、
匯出跑於非 GUI 執行緒（tid 相異）、X-4 未選 ICC 擋 accept（不默默降回 X-1a）、一般
PDF 形態（Sprint 137）停用 ICC 列並標明不可送印且成品確無 OutputIntent、取消據實
提示、匯出中再觸發不重入。真視窗檔案選取與匯出手感待 Owner（GAPS #82）。

由 smoke_check.main() 呼叫，需求的離屏環境（QT_QPA_PLATFORM＝offscreen、QApplication
已建）由呼叫端備妥。
"""
import tempfile
import threading
from pathlib import Path

from PySide6.QtWidgets import QDialog, QMenu, QMessageBox

from editor import export_actions as _ea
from editor.export_panel import ExportDialog


def check_export(EditorWindow, DOC) -> None:
    """跑 C29 並逐項 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    main_tid = threading.get_ident()

    # 檔案選單「轉存為 PDF…」項與 Ctrl+E（InDesign 慣例）
    win = EditorWindow(str(DOC))
    menu = next(
        m for m in win.menuBar().findChildren(QMenu) if m.title() == "檔案")
    acts = [a for a in menu.actions() if not a.isSeparator()]
    assert "轉存為 PDF…" in [a.text() for a in acts], \
        f"檔案選單缺轉存項：{[a.text() for a in acts]}"
    export_act = next(a for a in acts if a.text() == "轉存為 PDF…")
    assert export_act.shortcut().toString() == "Ctrl+E", \
        f"轉存快捷鍵非 Ctrl+E：{export_act.shortcut().toString()}"

    # 空白文件守門：無版面頁 → 不匯出、據實提示、不起執行緒
    blank = EditorWindow(None)
    blank._export_pdf_dialog()
    assert "空白文件無內容可轉存" in blank.statusBar().currentMessage(), \
        "空白文件未據實擋"
    assert blank._export_thread is None, "空白文件不應起匯出執行緒"

    orig_exec = ExportDialog.exec
    orig_info = QMessageBox.information
    infos = []
    QMessageBox.information = staticmethod(
        lambda *a, **k: infos.append(a[-1]) or QMessageBox.StandardButton.Ok)

    def _drive(out_path, pdfx="x-1a", crop=False):
        """替身：驅動對話框填入指定選項並回 Accepted（不真開 modal）。"""
        def _stub(dlg):
            dlg._path_edit.setText(str(out_path))
            dlg._pdfx.setCurrentIndex(dlg._pdfx.findData(pdfx))
            dlg._crop.setChecked(crop)
            return int(QDialog.DialogCode.Accepted)
        return _stub

    win2 = None
    real_export = _ea.export_pdf
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        try:
            # 真匯出：驅動對話框（X-1a、裁切標記開）→ 背景 export_pdf → 讀回驗
            calls = []

            def _spy(*a, **k):
                calls.append(threading.get_ident())
                return real_export(*a, **k)

            _ea.export_pdf = _spy
            out = td / "成品.pdf"
            ExportDialog.exec = _drive(out, "x-1a", crop=True)
            win._export_pdf_dialog()
            assert win._export_thread is not None, "匯出應交背景執行緒"
            assert "轉存中" in win.statusBar().currentMessage(), "未報背景轉存中"
            result = win._export_wait()
            _ea.export_pdf = real_export
            assert result is not None, "背景匯出未回結果"
            assert len(calls) == 1 and calls[0] != main_tid, \
                f"匯出未跑在非 GUI 執行緒（calls={calls}）"
            assert out.exists() and result.page_count > 0, "未產出 PDF 成品"
            assert result.pdfx_label == "PDF/X-1a:2001" and result.crop_marks, \
                "成品形態或裁切標記不符選項"
            # 獨立讀回（Gate 4 不同方法）：PyMuPDF 開檔驗頁數、/Title、頁面文字
            import fitz
            pdf = fitz.open(str(out))
            try:
                assert pdf.page_count == result.page_count, \
                    f"讀回頁數不符（{pdf.page_count} vs {result.page_count}）"
                assert pdf.metadata.get("title"), "成品缺 /Title（PDF/X 必要）"
                assert pdf[0].get_text().strip(), "成品首頁無可抽取文字（疑似空白）"
            finally:
                pdf.close()
            assert infos and "轉存完成" in infos[-1], "完成報告未列成品"
            assert "轉存完成" in win.statusBar().currentMessage(), "statusBar 未列結論"

            # X-4 未選 ICC：對話框 accept 被擋（不默默降回 X-1a）
            dlg_x4 = ExportDialog(td / "x4.pdf", parent=win)
            dlg_x4._pdfx.setCurrentIndex(dlg_x4._pdfx.findData("x-4"))
            dlg_x4._on_accept()
            assert dlg_x4.result() != int(QDialog.DialogCode.Accepted), \
                "X-4 未選 ICC 不應被接受"
            assert "PDF/X-4 須嵌" in dlg_x4._notice.text(), "X-4 缺 ICC 未據實說明"

            # 一般 PDF（Sprint 137）：ICC 列停用、就地標明非送印形態、選項回 none
            dlg_none = ExportDialog(td / "彩色.pdf", parent=win)
            assert dlg_none._pdfx.findData("none") == 2, \
                "一般 PDF 應排最後（預設索引 0 仍是 X-1a）"
            dlg_none._pdfx.setCurrentIndex(2)
            assert not dlg_none._icc_edit.isEnabled(), "一般 PDF 無 OutputIntent 可嵌"
            assert "不是 PDF/X" in dlg_none._notice.text(), "一般 PDF 未標明不可送印"
            opts_none = dlg_none.options()
            assert opts_none["pdfx"] == "none" and opts_none["icc_profile"] is None, \
                f"一般 PDF 選項不符：{opts_none}"
            dlg_none._pdfx.setCurrentIndex(dlg_none._pdfx.findData("x-1a"))
            assert dlg_none._notice.text() == "", "改回 X-1a 後提示未清"

            # 一般 PDF 真匯出：成品確實不含 OutputIntent，報告據實說不可送印
            color_out = td / "彩色.pdf"
            ExportDialog.exec = _drive(color_out, "none")
            win._export_pdf_dialog()
            result_none = win._export_wait()
            assert result_none is not None and color_out.exists(), "一般 PDF 未產出"
            assert result_none.pdfx_label.startswith("一般 PDF"), \
                f"成品形態不符：{result_none.pdfx_label}"
            assert b"/OutputIntents" not in color_out.read_bytes(), \
                "一般 PDF 不應寫 OutputIntent"
            assert "不可送印" in infos[-1], f"報告未標明不可送印：{infos[-1]}"

            # 取消：對話框 reject → 據實提示、不起執行緒
            ExportDialog.exec = lambda dlg: int(QDialog.DialogCode.Rejected)
            win._export_pdf_dialog()
            assert "已取消" in win.statusBar().currentMessage(), "取消未據實提示"
            assert win._export_thread is None, "取消不應起執行緒"

            # 匯出中不重入（可控阻塞替身固定時序，寫檔本身已由上段真匯出驗過）
            gate = threading.Event()
            entered = threading.Event()
            stub_calls = []

            def _blocking(*a, **k):
                stub_calls.append(1)
                entered.set()
                gate.wait(30)
                return real_export(*a, **k)

            _ea.export_pdf = _blocking
            ExportDialog.exec = _drive(td / "併發.pdf", "x-1a")
            win2 = EditorWindow(str(DOC))
            win2._export_pdf_dialog()
            assert entered.wait(30), "背景匯出未進入 export_pdf"
            win2._export_pdf_dialog()  # 執行中再觸發
            assert "進行中" in win2.statusBar().currentMessage(), "重入未提示進行中"
            assert len(stub_calls) == 1, f"重入起了第二輪匯出（{len(stub_calls)}）"
            gate.set()
            win2._export_wait()
        finally:
            ExportDialog.exec = orig_exec
            QMessageBox.information = orig_info
            _ea.export_pdf = real_export
    for w in (win, blank, win2):
        if w is not None:
            w._shutdown_thumbnails()

    print(
        "C29 轉存 PDF 介面：檔案選單轉存項＋Ctrl+E＋空白文件守門＋驅動選項對話框後"
        "背景 export_pdf 真產出成品（PyMuPDF 讀回頁數／Title／首頁文字）＋匯出跑於"
        "非 GUI 執行緒（tid 相異）＋X-4 未選 ICC 擋 accept（不默默降回 X-1a）＋"
        "一般 PDF 形態停用 ICC 列並標明不可送印、成品確無 OutputIntent＋"
        "取消據實提示＋匯出中再觸發不重入"
    )
