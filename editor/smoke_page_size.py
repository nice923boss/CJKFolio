"""smoke C39：成品尺寸與印前設定（Sprint 140；Owner 需求：APP 無法調成品尺寸、
總墨量上限與 PDF/X 形態無處可設）。

離屏可驗：
- 甲 成品尺寸：版面選單入口、對話框以現行模版尺寸起始且預設整版等比、紙張下拉與
  寬高雙向同步、含出血尺寸只影響顯示、整版等比時字級跟著放大而頁數不變、只換紙張時
  一個字都不重排、勾選重算時邊距不動而行列數與頁數跟著變、同尺寸 no-op 不入歷史、
  非法尺寸擋下且狀態不變、一步 undo 回原尺寸、改小紙張時溢出項據實列出（不擋），
  以及改完真匯出的 PDF 其 MediaBox／TrimBox 確為新尺寸（PyMuPDF 讀回＝Gate 4）。
- 乙 印前設定：設定選單入口、面板 round-trip（只寫本機檔）、轉存對話框以印前設定
  起始、對話框的總墨量上限真的送到 export_pdf。

真視窗的數值微調手感、對話框版面與 modal 行為離屏跑不了（GAPS #94）。
由 smoke_check.main() 呼叫，離屏環境（QT_QPA_PLATFORM＝offscreen、QApplication
已建）由呼叫端備妥。
"""
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QDialog, QMenu, QMessageBox

from cjkfolio.pdf_writer import export_pdf
from cjkfolio.press_marks import BLEED_MM
from cjkfolio.press_config import PressConfig, load_press_config, save_press_config
from cjkfolio.primitives import PT_PER_MM
from editor import export_actions as _ea
from editor.export_panel import ExportDialog
from editor.page_size_panel import PageSizeDialog
from editor.press_panel import PressConfigDialog

BODY = "A-內文版"


def _menu_items(win, title: str) -> list:
    menu = next(m for m in win.menuBar().findChildren(QMenu) if m.title() == title)
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def check_page_size(EditorWindow, DOC) -> None:
    """跑 C39 並逐項 print（斷言失敗即 AssertionError 中止整份 smoke）。

    全程接管 QMessageBox.warning：溢出提示是 modal，離屏沒人按就會卡死整份 smoke，
    故一律收進 warned 串列，該有的段落驗內容、不該有的段落驗其為空。
    """
    win = EditorWindow(str(DOC))
    assert "成品尺寸…" in _menu_items(win, "版面"), \
        f"版面選單缺成品尺寸項：{_menu_items(win, '版面')}"
    assert "印前設定…" in _menu_items(win, "設定"), \
        f"設定選單缺印前設定項：{_menu_items(win, '設定')}"

    # 對話框以現行模版尺寸起始、預設整版等比（Sprint 157 Owner 決定）
    dlg = PageSizeDialog(win.template, parent=win)
    vals = dlg.values()
    assert vals["width_mm"] == win.template.page_width_mm, f"寬未帶入：{vals}"
    assert vals["height_mm"] == win.template.page_height_mm, f"高未帶入：{vals}"
    assert vals["mode"] == "scale", f"換法應預設整版等比：{vals}"
    # 紙張下拉雙向同步：選 18 開填入寬高；手改成 A4 尺寸切到 A4；不符切自訂
    assert dlg._paper.currentText().startswith("25 開"), dlg._paper.currentText()
    dlg._paper.setCurrentIndex(1)
    dlg._paper.activated.emit(1)
    assert (dlg.values()["width_mm"], dlg.values()["height_mm"]) == (170.0, 230.0)
    dlg._width.setValue(210.0)
    assert dlg._paper.currentText() == "自訂", dlg._paper.currentText()
    dlg._height.setValue(297.0)
    assert dlg._paper.currentText().startswith("A4"), dlg._paper.currentText()
    assert dlg._bleed_label.isHidden(), "含出血尺寸應勾選才顯示"
    dlg._show_bleed.setChecked(True)
    assert "216 × 303 mm" in dlg._bleed_label.text(), dlg._bleed_label.text()
    assert dlg.values()["width_mm"] == 210.0, "含出血只影響顯示，收回仍是成品尺寸"

    # 整版等比：18 開（k＝230/210），字級與邊距跟著放大、行列與頁數不變、一步 undo
    size0 = win.template.paragraph_styles[win.doc.paragraphs[0].style].size_pt
    pages_before = len(win.layout_result.pages)
    win._page_size_dialog({"width_mm": 170.0, "height_mm": 230.0, "mode": "scale"})
    k = 230.0 / 210.0
    size1 = win.template.paragraph_styles[win.doc.paragraphs[0].style].size_pt
    assert abs(size1 - size0 * k) < 1e-6, (size0, size1)
    assert len(win.layout_result.pages) == pages_before, "等比縮放不應改頁數"
    assert win.template.masters[BODY].grid.chars_per_line ==         win.session._undo[-1][1].masters[BODY].grid.chars_per_line
    assert "整版等比縮放" in win.statusBar().currentMessage()
    win._on_undo()
    assert win.template.page_width_mm == 148.0, "等比縮放一步 undo 未回原尺寸"

    w0, h0 = win.template.page_width_mm, win.template.page_height_mm
    grid0 = win.template.masters[BODY].grid
    margins0 = win.template.masters[BODY].margins
    pages0 = len(win.layout_result.pages)
    chars0 = sum(len(p.text) for p in win.doc.paragraphs)

    orig_warning = QMessageBox.warning
    warned = []
    QMessageBox.warning = staticmethod(
        lambda *a, **k: warned.append(a[-1]) or QMessageBox.StandardButton.Ok)
    try:
        grid2, pages2 = _run_size_steps(
            win, w0, h0, grid0, margins0, pages0, chars0, warned)
    finally:
        QMessageBox.warning = orig_warning
    win._shutdown_thumbnails()
    print(
        f"C39 甲 成品尺寸：版面選單入口＋對話框帶入現行 {w0:g}×{h0:g}mm 且預設整版等比"
        "＋紙張下拉與寬高雙向同步＋含出血尺寸只影響顯示"
        f"＋整版等比 18 開字級 ×{230 / 210:.3f} 頁數不變一步 undo"
        f"＋只換紙張不重排（{pages0} 頁不動）＋重算版心邊距不動而行列 "
        f"{grid0.chars_per_line}×{grid0.lines_per_page}→"
        f"{grid2.chars_per_line}×{grid2.lines_per_page}、"
        f"文字量不變而全書 {pages0} 頁重排為 {pages2} 頁"
        "＋同尺寸 no-op 不佔 undo＋非法尺寸擋下狀態不變＋一步 undo 回原尺寸"
        "＋改小紙張溢出項據實列出不阻擋＋成品 TrimBox 經 PyMuPDF 讀回確為 120×180mm"
        "（MediaBox 同步為四邊各加 3mm 出血）"
    )


def _run_size_steps(win, w0, h0, grid0, margins0, pages0, chars0, warned):
    """甲的各段改尺寸驗證（QMessageBox.warning 已由呼叫端接管）。"""
    # ── 只換紙張（不勾重算）：一個字都不重排 ──
    win._page_size_dialog({"width_mm": 160.0, "height_mm": 230.0,
                           "mode": "paper"})
    assert win.template.page_width_mm == 160.0, "成品寬未變更"
    grid1 = win.template.masters[BODY].grid
    assert (grid1.chars_per_line, grid1.lines_per_page) == \
        (grid0.chars_per_line, grid0.lines_per_page), "不勾重算卻動了版心"
    assert len(win.layout_result.pages) == pages0, "不勾重算卻重排了頁數"
    assert "只換紙張" in win.statusBar().currentMessage(), \
        f"狀態列未據實說語意：{win.statusBar().currentMessage()}"
    assert not warned, f"紙張放大不應報溢出：{warned}"
    win._on_undo()
    assert (win.template.page_width_mm, win.template.page_height_mm) == (w0, h0), \
        "一步 undo 未回原尺寸"

    # ── 勾選重算：邊距不動，行列數與頁數跟著紙張走 ──
    win._page_size_dialog({"width_mm": 210.0, "height_mm": 297.0,
                           "mode": "refit"})
    grid2 = win.template.masters[BODY].grid
    assert win.template.masters[BODY].margins == margins0, "重算版心不應動邊距"
    assert grid2.chars_per_line > grid0.chars_per_line, \
        f"紙變高，每行字數未增加（{grid0.chars_per_line}→{grid2.chars_per_line}）"
    assert grid2.lines_per_page > grid0.lines_per_page, \
        f"紙變寬，每頁行數未增加（{grid0.lines_per_page}→{grid2.lines_per_page}）"
    assert grid2.char_advance_pt == grid0.char_advance_pt and \
        grid2.line_pitch_pt == grid0.line_pitch_pt, "重算版心不應動字距行距"
    assert sum(len(p.text) for p in win.doc.paragraphs) == chars0, "重排改了文字"
    pages2 = len(win.layout_result.pages)
    assert pages2 < pages0, f"版心變大頁數卻沒少（{pages0}→{pages2}）"
    assert "版心已重算" in win.statusBar().currentMessage(), \
        f"狀態列未據實說語意：{win.statusBar().currentMessage()}"
    assert not warned, f"紙張放大並重算版心不應報溢出：{warned}"

    # ── 同尺寸 no-op：不入歷史（避免看不出差別的 undo 步） ──
    win._page_size_dialog({"width_mm": 210.0, "height_mm": 297.0,
                           "mode": "refit"})
    assert "無變更" in win.statusBar().currentMessage(), "同尺寸未報無變更"
    win._on_undo()
    assert (win.template.page_width_mm, win.template.page_height_mm) == (w0, h0), \
        "no-op 佔了一步 undo（同尺寸不應入歷史）"

    # ── 非法尺寸：純層守門擋下，狀態不變 ──
    win._page_size_dialog({"width_mm": 0.0, "height_mm": 210.0, "mode": "paper"})
    assert "無法改成品尺寸" in win.statusBar().currentMessage(), "非法尺寸未擋"
    assert win.template.page_width_mm == w0, "非法尺寸卻改了狀態"

    # ── 改小紙張：溢出項據實列出（提示而非阻擋） ──
    win._page_size_dialog({"width_mm": 90.0, "height_mm": 120.0,
                           "mode": "paper"})
    assert warned and "超出成品範圍" in warned[-1], f"溢出未據實列出：{warned}"
    assert "落到成品外" in win.statusBar().currentMessage(), "狀態列未報溢出項數"
    assert win.template.page_width_mm == 90.0, "溢出不應阻擋改尺寸"
    win._on_undo()

    # ── Gate 4：改完真匯出，PyMuPDF 獨立讀回 MediaBox／TrimBox 為新尺寸 ──
    import fitz
    with tempfile.TemporaryDirectory() as td:
        win._page_size_dialog({"width_mm": 120.0, "height_mm": 180.0,
                               "mode": "refit"})
        out = Path(td) / "改尺寸成品.pdf"
        export_pdf(win.doc, win.template, out, footer=False)
        pdf = fitz.open(str(out))
        try:
            want = (120.0 * PT_PER_MM, 180.0 * PT_PER_MM)
            trim = pdf[0].trimbox  # 成品尺寸＝TrimBox（裁切後真正拿到手的大小）
            assert all(abs(a - b) < 0.1 for a, b in
                       zip((trim.width, trim.height), want)), \
                f"成品 TrimBox 非新尺寸：{trim} vs {want}"
            media = pdf[0].rect  # MediaBox 恆為 TrimBox 四邊各加 3mm 出血（§9）
            want_media = tuple(v + 2 * BLEED_MM * PT_PER_MM for v in want)
            assert all(abs(a - b) < 0.1 for a, b in
                       zip((media.width, media.height), want_media)), \
                f"MediaBox 未隨成品尺寸走：{media} vs {want_media}"
        finally:
            pdf.close()
    return grid2, pages2


def check_press_config(EditorWindow, DOC) -> None:
    """乙：印前設定面板 round-trip、轉存對話框起始值、上限真的送到 export_pdf。"""
    win = EditorWindow(str(DOC))
    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "press-config.local.json"

        # 面板 round-trip（只寫本機檔；缺檔以 §9 保守預設開啟）
        dlg = PressConfigDialog(win, config_path=cfg_path)
        assert dlg.current_config() == PressConfig(max_tac=320.0, pdfx="x-1a"), \
            f"缺檔未回 §9 預設：{dlg.current_config()}"
        dlg._max_tac.setValue(340.0)
        dlg._pdfx.setCurrentIndex(dlg._pdfx.findData("x-4"))
        dlg._on_save()
        assert dlg.result() == int(QDialog.DialogCode.Accepted), "儲存未接受"
        assert load_press_config(cfg_path) == PressConfig(max_tac=340.0, pdfx="x-4"), \
            "設定未落地"
        assert PressConfigDialog(win, config_path=cfg_path).current_config() == \
            PressConfig(max_tac=340.0, pdfx="x-4"), "重開面板未讀回"

        # 轉存對話框以印前設定起始（形態與上限都帶入）
        save_press_config(PressConfig(max_tac=330.0, pdfx="x-4"), cfg_path)
        seeded = ExportDialog(Path(td) / "a.pdf", parent=win,
                              pdfx="x-4", max_tac=330.0)
        assert seeded._pdfx.currentData() == "x-4", "形態未帶入轉存對話框"
        assert seeded.options()["max_tac"] == 330.0, "上限未帶入轉存對話框"

        # UI 路徑：印前設定 → 轉存對話框 → export_pdf 真的收到該上限
        orig_exec, orig_info = ExportDialog.exec, QMessageBox.information
        orig_load, real_export = _ea.load_press_config, _ea.export_pdf
        seen = []
        out = Path(td) / "上限.pdf"
        try:
            _ea.load_press_config = lambda *a, **k: PressConfig(max_tac=345.0)
            QMessageBox.information = staticmethod(
                lambda *a, **k: QMessageBox.StandardButton.Ok)

            def _spy(*a, **k):
                seen.append(k.get("max_tac"))
                return real_export(*a, **k)

            def _drive(dlg):
                assert dlg._max_tac.value() == 345.0, \
                    f"轉存對話框未以印前設定起始：{dlg._max_tac.value()}"
                dlg._path_edit.setText(str(out))
                return int(QDialog.DialogCode.Accepted)

            _ea.export_pdf = _spy
            ExportDialog.exec = _drive
            win._export_pdf_dialog()
            result = win._export_wait()
        finally:
            ExportDialog.exec = orig_exec
            QMessageBox.information = orig_info
            _ea.load_press_config, _ea.export_pdf = orig_load, real_export
        assert result is not None and out.exists(), "匯出未產出成品"
        assert seen == [345.0], f"上限未送到 export_pdf：{seen}"
    win._shutdown_thumbnails()
    print(
        "C39 乙 印前設定：設定選單入口＋面板缺檔回 §9 預設（320%／X-1a）與 round-trip"
        "（340%／X-4 落地、重開讀回）＋轉存對話框以印前設定起始（形態與上限）"
        "＋UI 路徑的上限 345% 確實送達 export_pdf 並產出成品"
    )
