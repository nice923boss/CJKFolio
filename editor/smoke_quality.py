"""smoke C36：預覽畫質（Sprint 133；自 smoke_check.py 分檔，行數紀律慣例）。

Owner 真視窗回饋：「預覽的畫面字體不夠清晰，改成預覽是非常清楚的字體與圖片
內容才對。」根因見 Spike 24（底圖固定 150dpi，放大即像素拉伸）。

離屏可驗：縮放後排程升級（debounce 收斂連續滾輪）、背景執行緒真的產出更高
解析度的 pixmap 且**換上畫面**、scene 座標與互動層 hit-test **零改動**（本形態
的核心保證）、回到 100% 不重渲染（無謂重繪守門）、reflow 後底圖回基準 dpi 並
重新排程（漸進式細化）、對頁模式兩頁都升級、退出安全。
畫面實際清晰度待 Owner 真視窗（GAPS #19 批次；離屏只能驗像素數與幾何）。
"""
import time

from PySide6.QtWidgets import QApplication

from editor.canvas_quality import CANVAS_DPI, target_base_dpi


def _wait_quality(win, app, timeout_s: float = 60.0) -> float:
    """processEvents 推進到畫質輪收工（debounce fire → worker → all_done）。"""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if (not win._quality_timer.isActive() and win._quality_thread is None
                and win._quality_elapsed is not None):
            return win._quality_elapsed
        time.sleep(0.01)
    raise AssertionError("底圖畫質背景渲染逾時未完成")


def _base_item(win, page_number: int):
    """該頁底圖 item（data(1)＝頁號；data(0) 是互動層字格鍵，底圖刻意不帶）。"""
    return next(it for it in win.scene.items() if it.data(1) == page_number)


def check_quality(EditorWindow, doc_path) -> None:
    app = QApplication.instance()
    win = EditorWindow(str(doc_path))
    page_no = win.page.number

    # 初始：底圖為基準 dpi，且底圖不帶 data(0)（不可被 hit-test 當字格命中）
    base = _base_item(win, page_no)
    assert win._quality_dpi == CANVAS_DPI
    assert base.data(0) is None, "底圖帶了 data(0) 會被當成字格命中"
    px0 = base.pixmap().width()
    scene_w0 = win.scene.sceneRect().width()
    keys0 = set(win._item_by_key)
    geom0 = {k: (it.rect().x(), it.rect().y(), it.rect().width())
             for k, it in win._item_by_key.items()}

    # 放大到 300%：排程升級 → 背景渲染 → 換上更高解析度底圖
    win.view.set_zoom(3.0)
    assert win._quality_timer.isActive(), "縮放後未排程畫質升級"
    elapsed = _wait_quality(win, app)
    want_dpi = target_base_dpi(3.0, win._device_pixel_ratio())
    assert win._quality_dpi == want_dpi, (win._quality_dpi, want_dpi)
    base = _base_item(win, page_no)
    px1 = base.pixmap().width()
    assert px1 > px0, f"底圖未變高解析（{px0} → {px1}）"
    assert abs(px1 / px0 - want_dpi / CANVAS_DPI) < 0.02, (px0, px1)

    # 核心保證：scene 座標與互動層幾何完全不變（高 dpi 底圖 setScale 縮回）
    assert abs(win.scene.sceneRect().width() - scene_w0) < 0.01, "scene 尺寸變了"
    assert abs(base.scale() - CANVAS_DPI / want_dpi) < 1e-6, base.scale()
    assert set(win._item_by_key) == keys0, "互動層 key 集合變了"
    for k, before in geom0.items():
        after = win._item_by_key[k]
        now = (after.rect().x(), after.rect().y(), after.rect().width())
        assert all(abs(a - b) < 1e-6 for a, b in zip(before, now)), (k, before, now)

    # 真 hit-test：字格中心仍命中同一 key（畫質升級不影響點選）
    hit_ok = 0
    for key, item in list(win._item_by_key.items())[:60]:
        c = item.sceneBoundingRect().center()
        found = next((it for it in win.scene.items(c) if it.data(0) is not None), None)
        hit_ok += int(found is not None and found.data(0) == key)
    assert hit_ok == min(60, len(keys0)), f"hit-test 退步：{hit_ok}"

    # 回到 100%：目標回基準，不再排程（無謂重繪守門）
    win._quality_elapsed = None
    win.view.set_zoom(3.0)  # 同倍率不觸發
    win.view.set_zoom(1.0)
    _wait_quality(win, app)
    assert win._quality_dpi == CANVAS_DPI
    win.view.set_zoom(1.0)
    assert not win._quality_timer.isActive(), "已是目標 dpi 仍排程重渲染"

    # reflow 後底圖回基準並重新排程（漸進式細化：編輯要快，停手再補畫質）
    win.view.set_zoom(2.0)
    _wait_quality(win, app)
    assert win._quality_dpi == target_base_dpi(2.0, win._device_pixel_ratio())
    win._rebuild()
    assert win._quality_dpi == CANVAS_DPI, "reflow 後未回基準 dpi"
    assert win._quality_timer.isActive(), "reflow 後未重新排程畫質"
    _wait_quality(win, app)
    assert _base_item(win, win.page.number).pixmap().width() > px0

    # 對頁模式：畫面上兩頁都升級（頁 2＝偶＝右頁，與頁 3 成一組；頁 1 本就單邊）
    win.view.set_zoom(1.0)
    _wait_quality(win, app)
    win._goto_page(2)
    win._facing_action.setChecked(True)
    win._toggle_facing()
    win.view.set_zoom(2.0)
    _wait_quality(win, app)
    numbers = win._quality_page_numbers()
    assert len(numbers) == 2, numbers
    for n in numbers:
        assert _base_item(win, n).pixmap().width() > px0, f"對頁 {n} 未升級"

    win._shutdown_quality()
    win._shutdown_thumbnails()
    print(
        f"C36 預覽畫質：縮放 300% 後背景重渲染底圖 {px0}→{px1}px（{CANVAS_DPI}"
        f"→{want_dpi}dpi，{elapsed:.2f}s）＋scene 尺寸與互動層幾何零改動"
        f"（{len(keys0)} 格 key 全等、hit-test {hit_ok}/{min(60, len(keys0))} 全對）"
        "＋回 100% 不重渲染＋reflow 回基準再排程（漸進式細化）＋對頁兩頁皆升級"
    )
