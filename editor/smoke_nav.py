"""smoke C27：頁面導航與縮圖面板（Sprint 125；自 smoke_check.py 分檔，行數紀律慣例）。

離屏可驗：狀態列頁碼指示器、_goto_page 跳頁（clamp／同頁短路／清游標）、
頁面面板 item 數與真點擊訊號跳頁、目前頁高亮跟隨、「版面」選單五項與快捷鍵、
背景縮圖首輪渲染完成（等 all_done、記實測秒數、縮圖像素確認上牆非占位）、
編輯 reflow 後 debounce 重渲染與世代遞增、空白文件 0 項據實提示不炸。
縮圖視覺品質、面板點選手感待 Owner 真視窗（GAPS #19 批次）。
"""
import time

from PySide6.QtWidgets import QApplication, QMenu

from editor.page_panel import THUMB_H, THUMB_W


def _wait_thumbs(win, app, timeout_s: float = 30.0) -> float:
    """processEvents 推進到縮圖輪收工（debounce fire → worker → all_done）。"""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if (not win._thumb_timer.isActive() and win._thumb_thread is None
                and win._thumb_elapsed is not None):
            return win._thumb_elapsed
        time.sleep(0.01)
    raise AssertionError("縮圖背景渲染逾時未完成")


def check_nav(EditorWindow, doc_path) -> None:
    app = QApplication.instance()
    win = EditorWindow(str(doc_path))  # chapter-opening 2 頁樣張
    total = len(win.layout_result.pages)
    assert total == 2, f"樣張應 2 頁，得 {total}"

    # 頁碼指示器初值＋面板 item 數與目前頁高亮
    assert win._page_label.text() == f"頁 1／{total}", win._page_label.text()
    assert win._page_panel.count() == total
    assert win._page_panel.currentRow() == 0

    # 版面選單六項與快捷鍵（findChildren：QAction.menu() wrapper 不可靠，C26 教訓）
    menu = next(
        m for m in win.menuBar().findChildren(QMenu) if m.title() == "版面")
    acts = [a for a in menu.actions() if not a.isSeparator()]
    assert [a.text() for a in acts] == \
        ["上一頁", "下一頁", "第一頁", "最後一頁", "跳至頁碼…", "成品尺寸…"], \
        f"版面選單項異常：{[a.text() for a in acts]}"
    keys = {a.text(): [s.toString() for s in a.shortcuts()] for a in acts}
    assert keys["上一頁"] == ["PgUp"] and keys["下一頁"] == ["PgDown"], keys
    assert keys["第一頁"] == ["Ctrl+Home"] and keys["最後一頁"] == ["Ctrl+End"], keys
    assert keys["跳至頁碼…"] == ["Ctrl+J"], keys

    # 跳頁核心：清游標、指示器與高亮跟隨、clamp、同頁短路
    win.cursor = (0, 0)
    win._goto_page(2)
    assert win.page.number == 2 and win.cursor is None, "跳頁未清游標"
    assert win._page_label.text() == f"頁 2／{total}"
    assert win._page_panel.currentRow() == 1, "面板高亮未跟隨"
    win._goto_page(99)  # clamp 到末頁＝現頁 → 短路不重繪
    assert win.page.number == 2
    win._page_panel.itemClicked.emit(win._page_panel.item(0))  # 面板真點擊訊號
    assert win.page.number == 1, "面板點選未跳頁"
    assert "頁 1/2" in win.statusBar().currentMessage()

    # 背景縮圖首輪：等 all_done，縮圖像素上牆（角落紙白，非 #e6e6e6 占位灰）
    elapsed = _wait_thumbs(win, app)
    for i in range(total):
        icon = win._page_panel.item(i).icon()
        assert not icon.isNull()
        corner = icon.pixmap(THUMB_W, THUMB_H).toImage().pixelColor(1, 1)
        assert corner.red() > 245, f"頁 {i + 1} 縮圖未上牆（角落 {corner.name()}）"

    # 編輯 reflow → debounce 計時 → 世代遞增重渲染（翻頁不重排故不觸發）
    gen0 = win._thumb_generation
    win.cursor = (0, 0)
    win._ime.setText("測")
    win._on_ime_commit()
    assert win._thumb_timer.isActive(), "編輯後 debounce 未起"
    elapsed2 = _wait_thumbs(win, app)
    assert win._thumb_generation > gen0, "編輯後世代未遞增"
    win._goto_page(2)
    assert not win._thumb_timer.isActive(), "翻頁不重排卻起了縮圖重渲染"

    # 空白文件：面板 0 項、指示器占位、跳頁據實提示不炸
    win_blank = EditorWindow(None)
    assert win_blank._page_panel.count() == 0
    assert win_blank._page_label.text() == "頁 −／−"
    win_blank._goto_page(1)
    assert "尚無頁面" in win_blank.statusBar().currentMessage()

    for w in (win, win_blank):  # 退出安全：執行緒收工（closeEvent 同路徑）
        w._shutdown_thumbnails()
    print(
        f"C27 頁面導航與縮圖面板：指示器＋版面選單五項＋面板 {total} 項點選跳頁"
        f"＋高亮跟隨，首輪縮圖 {elapsed:.2f}s、編輯後重渲染 {elapsed2:.2f}s"
        f"（世代 {win._thumb_generation}，翻頁不觸發）"
    )
