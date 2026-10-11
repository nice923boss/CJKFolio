"""smoke C46：畫布出血範圍紅框與只輸出成品範圍（Sprint 156；分檔，行數紀律慣例）。

Owner：「App畫布增加出血框範圍，用紅線框顯示，並且PDF匯出的時候可以選只需要匯出
成品範圍，但不要有白邊」。

離屏可驗：檢視選單出血項預設勾選、單頁 scene 四邊各外擴 3mm、紅框與灰虛線成品框
不攔點選（hit-test 不退步）、關掉回成品尺寸、對頁兩頁訂口側不重疊且紅框圍整個跨頁、
畫質升級後底圖仍對齊、轉存對話框「只輸出成品範圍」與裁切標記互斥並真的送進
export_pdf（PyMuPDF 讀回三框＝成品）。紅線在真螢幕的顏色與粗細待 Owner 真視窗。
"""
import tempfile
from pathlib import Path

import fitz
from PySide6.QtWidgets import QApplication, QDialog, QGraphicsPathItem, QMessageBox

from cjkfolio.press_marks import BLEED_MM
from cjkfolio.render import mm_to_pt
from editor.canvas import BLEED_LINE_COLOR
from editor.export_panel import ExportDialog
from editor.smoke_quality import _base_item, _wait_quality


def _red_guides(win) -> list:
    return [it for it in win.scene.items() if isinstance(it, QGraphicsPathItem)
            and it.pen().color().name() == BLEED_LINE_COLOR]


def check_bleed(EditorWindow, doc_path) -> None:
    app = QApplication.instance()
    win = EditorWindow(str(doc_path))
    w = mm_to_pt(win.template.page_width_mm) * 150 / 72.0
    h = mm_to_pt(win.template.page_height_mm) * 150 / 72.0
    b = mm_to_pt(BLEED_MM) * 150 / 72.0
    assert win._bleed_action.isChecked(), "出血範圍應預設顯示"

    rect = win.scene.sceneRect()
    assert abs(rect.left() + b) < 1 and abs(rect.top() + b) < 1, rect
    assert abs(rect.width() - (w + 2 * b)) < 1.5, (rect.width(), w + 2 * b)
    guides = _red_guides(win)
    assert len(guides) == 1 and guides[0].data(0) is None, "紅框應一條且不帶字格鍵"
    hit_ok = 0
    sample = list(win._item_by_key.items())[:60]
    for key, item in sample:
        c = item.sceneBoundingRect().center()
        found = next((it for it in win.scene.items(c) if it.data(0) is not None), None)
        hit_ok += int(found is not None and found.data(0) == key)
    assert hit_ok == len(sample), f"紅框攔了點選：{hit_ok}/{len(sample)}"

    win._bleed_action.trigger()  # 關掉：回成品尺寸、無紅框
    assert not _red_guides(win) and abs(win.scene.sceneRect().width() - w) < 1.5
    win._bleed_action.trigger()

    win._goto_page(2)  # 對頁：紙面 2 右、3 左
    win._facing_action.trigger()
    left, right = _base_item(win, 3), _base_item(win, 2)
    left_r = left.sceneBoundingRect()
    right_r = right.sceneBoundingRect()
    assert abs(left_r.right() - w) < 1 and abs(right_r.left() - w) < 1e-6, \
        f"訂口側出血蓋到鄰頁：左頁右緣 {left_r.right()}、右頁左緣 {right_r.left()}"
    assert abs(win.scene.sceneRect().width() - (2 * w + 2 * b)) < 1.5
    assert len(_red_guides(win)) == 2, "對頁紅框應為兩段開口路徑合成一框"

    win.view.set_zoom(3.0)  # 畫質升級後仍以同規則裁訂口、重定位
    _wait_quality(win, app)
    left_r = _base_item(win, 3).sceneBoundingRect()
    right_r = _base_item(win, 2).sceneBoundingRect()
    assert abs(left_r.left() + b) < 0.5 and abs(left_r.right() - w) < 0.5, left_r
    assert abs(right_r.left() - w) < 1e-6 and abs(right_r.right() - (2 * w + b)) < 0.5
    win._facing_action.trigger()

    with tempfile.TemporaryDirectory() as tmp:
        dlg = ExportDialog(Path(tmp) / "x.pdf", parent=win)
        dlg._crop.setChecked(True)
        assert not dlg._trim_only.isEnabled(), "勾裁切標記時應停用只輸出成品範圍"
        dlg._crop.setChecked(False)
        dlg._trim_only.setChecked(True)
        assert not dlg._crop.isEnabled() and dlg.options()["trim_only"]

        out = Path(tmp) / "成品範圍.pdf"
        orig_exec = ExportDialog.exec

        def drive(dlg: ExportDialog) -> int:
            dlg._path_edit.setText(str(out))
            dlg._trim_only.setChecked(True)
            return int(QDialog.DialogCode.Accepted)
        ExportDialog.exec = drive
        info = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
        try:
            win._export_pdf_dialog()
            result = win._export_wait()
        finally:
            ExportDialog.exec = orig_exec
            QMessageBox.information = info
        assert result is not None and result.trim_only, "只輸出成品範圍未送達 export_pdf"
        page = fitz.open(out)[0]
        pw, ph = mm_to_pt(win.template.page_width_mm), mm_to_pt(win.template.page_height_mm)
        for box in (page.mediabox, page.trimbox, page.bleedbox):
            assert abs(box.width - pw) < 0.01 and abs(box.height - ph) < 0.01, box
        pages = result.page_count
        page.parent.close()
    win._shutdown_quality()
    win._shutdown_thumbnails()
    win.close()

    print(
        "C46 出血範圍：檢視選單預設勾選、單頁 scene 四邊各外擴 3mm 且紅框不攔點選"
        f"（hit-test {hit_ok}/{len(sample)}）、關掉回成品尺寸、對頁訂口側不重疊且紅框"
        "圍整個跨頁、畫質升級後仍對齊；轉存「只輸出成品範圍」與裁切標記互斥，"
        f"真匯出 {pages} 頁 MediaBox＝TrimBox＝BleedBox＝成品（PyMuPDF 讀回）"
    )
