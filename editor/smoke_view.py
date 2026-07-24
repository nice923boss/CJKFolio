"""smoke C26：畫布縮放與平移（Sprint 124；自 smoke_check.py 抽出，行數紀律慣例）。

離屏可驗的是邏輯與倍率數學：檢視選單五項與快捷鍵、set_zoom clamp 與狀態列
同步、Ctrl+滾輪 1.25 倍階、Shift+滾輪水平捲動（素滾輪垂直不被吃掉）、開窗
初始整頁 fit、重繪保留縮放與視口中心、中鍵與空白鍵拖曳平移（不誤觸點選）、
符合頁面／符合寬度幾何。縮放錨點手感、觸控板慣性與真滑鼠拖曳需真視窗
（GAPS #79，承 #19 批次）。
"""
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QMenu

from editor.canvas_view import ZOOM_MAX, ZOOM_MIN, ZOOM_STEP


def check_view(EditorWindow, doc_path) -> None:
    app = QApplication.instance()
    win = EditorWindow(str(doc_path))
    win.resize(900, 900)  # Sprint 125 起左側頁面 dock（約 140px）常駐，等寬加回
    win.show()
    app.processEvents()  # 佈局落定＋showEvent 排入的初始整頁 fit 於此執行
    view = win.view
    vp = view.viewport()
    assert vp.width() > 200 and vp.height() > 200, f"viewport 未展開：{vp.size()}"

    # 初始整頁 fit：頁（874×1240px @150dpi）大於視口，開窗即應縮小到整頁可見
    rect = view.scene().sceneRect()
    z0 = view.zoom_factor()
    assert rect.width() * z0 <= vp.width() + 2 and \
        rect.height() * z0 <= vp.height() + 2, "開窗未整頁入視窗"
    assert 0.4 < z0 < 1.0, f"初始 fit 倍率異常：{z0}"
    assert win._zoom_label.text() == f"{round(z0 * 100)}%", \
        f"狀態列百分比未同步：{win._zoom_label.text()}"

    # 檢視選單五項與快捷鍵（Acrobat／InDesign 慣例）。查找走 findChildren：
    # QAction.menu() 回的 wrapper 在 shiboken 下會指到已失效物件（實測），不可靠
    view_menu = next(
        m for m in win.menuBar().findChildren(QMenu) if m.title() == "檢視")
    acts = view_menu.actions()
    assert [a.text() for a in acts] == \
        ["放大", "縮小", "實際大小（100%）", "符合頁面", "符合寬度"], \
        f"檢視選單項異常：{[a.text() for a in acts]}"
    keys = {a.text(): [s.toString() for s in a.shortcuts()] for a in acts}
    assert keys["放大"] == ["Ctrl+=", "Ctrl++"] and keys["縮小"] == ["Ctrl+-"]
    assert keys["實際大小（100%）"] == ["Ctrl+1"] and keys["符合頁面"] == ["Ctrl+0"]
    assert keys["符合寬度"] == ["Ctrl+2"], f"快捷鍵異常：{keys}"

    # set_zoom 絕對倍率、clamp 邊界、狀態列同步；zoom_in/out 步進互逆
    view.set_zoom(2.0)
    assert abs(view.zoom_factor() - 2.0) < 1e-9
    assert win._zoom_label.text() == "200%"
    view.set_zoom(100.0)
    assert abs(view.zoom_factor() - ZOOM_MAX) < 1e-9, "上界未 clamp"
    view.set_zoom(0.01)
    assert abs(view.zoom_factor() - ZOOM_MIN) < 1e-9, "下界未 clamp"
    assert win._zoom_label.text() == "10%"
    view.set_zoom(1.0)
    view.zoom_in()
    assert abs(view.zoom_factor() - ZOOM_STEP) < 1e-9, "zoom_in 未依步進"
    view.zoom_out()
    assert abs(view.zoom_factor() - 1.0) < 1e-9, "zoom_out 未互逆"

    # Ctrl+滾輪縮放；Shift+滾輪水平捲動；素滾輪垂直捲動不被吃掉
    def wheel(delta, mods):
        ev = QWheelEvent(
            QPointF(vp.width() / 2, vp.height() / 2), QPointF(0, 0),
            QPoint(0, 0), QPoint(0, delta), Qt.MouseButton.NoButton, mods,
            Qt.ScrollPhase.NoScrollPhase, False)
        view.wheelEvent(ev)

    wheel(120, Qt.KeyboardModifier.ControlModifier)
    assert abs(view.zoom_factor() - ZOOM_STEP) < 1e-9, "Ctrl+滾輪未放大"
    wheel(-120, Qt.KeyboardModifier.ControlModifier)
    assert abs(view.zoom_factor() - 1.0) < 1e-9, "Ctrl+滾輪未縮回"
    view.set_zoom(4.0)
    app.processEvents()
    hbar, vbar = view.horizontalScrollBar(), view.verticalScrollBar()
    assert hbar.maximum() > 600, f"放大後水平捲動範圍不足：{hbar.maximum()}"
    hbar.setValue(300)
    wheel(-120, Qt.KeyboardModifier.ShiftModifier)
    assert hbar.value() == 420, f"Shift+滾輪未水平捲動：{hbar.value()}"
    wheel(120, Qt.KeyboardModifier.ShiftModifier)
    assert hbar.value() == 300, "Shift+滾輪反向未捲回"
    vbar.setValue(0)
    wheel(-120, Qt.KeyboardModifier.NoModifier)
    assert vbar.value() > 0, "素滾輪垂直捲動被吃掉"

    # 重繪（reflow 每次都走）保留縮放與視口中心：不保留＝每打一字畫面跳回原點
    view.set_zoom(2.0)
    hbar.setValue(hbar.maximum() // 2)
    vbar.setValue(vbar.maximum() // 2)
    c0 = view.mapToScene(vp.rect().center())
    win._rebuild()
    app.processEvents()
    assert abs(view.zoom_factor() - 2.0) < 1e-9, "重繪後縮放未保留"
    c1 = view.mapToScene(view.viewport().rect().center())
    assert (c1 - c0).manhattanLength() < 6, f"重繪後視口中心漂移：{c0} → {c1}"

    # 中鍵拖曳平移（不觸發點選）；空白鍵＋左鍵拖曳平移（InDesign 手形語意）
    def mouse(type_, x, y, button, buttons):
        return QMouseEvent(type_, QPointF(x, y), QPointF(x, y), button, buttons,
                           Qt.KeyboardModifier.NoModifier)

    view.set_zoom(4.0)
    app.processEvents()
    hbar.setValue(300)
    vbar.setValue(300)
    assert win.cursor is None and win.frame_cursor is None
    view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 300, 300,
                               Qt.MouseButton.MiddleButton,
                               Qt.MouseButton.MiddleButton))
    assert view._pan_last is not None, "中鍵未進入平移"
    view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, 250, 260,
                              Qt.MouseButton.NoButton, Qt.MouseButton.MiddleButton))
    assert (hbar.value(), vbar.value()) == (350, 340), \
        f"中鍵拖曳未平移：{(hbar.value(), vbar.value())}"
    view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 250, 260,
                                 Qt.MouseButton.MiddleButton,
                                 Qt.MouseButton.NoButton))
    assert view._pan_last is None
    view.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space,
                                 Qt.KeyboardModifier.NoModifier))
    assert view._space_pan, "空白鍵未進入手形模式"
    view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 300, 300,
                               Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    assert view._pan_last is not None, "空白鍵＋左鍵未平移"
    view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, 320, 330,
                              Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton))
    assert (hbar.value(), vbar.value()) == (330, 310), \
        f"空白鍵拖曳未平移：{(hbar.value(), vbar.value())}"
    view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 320, 330,
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))
    view.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space,
                                   Qt.KeyboardModifier.NoModifier))
    assert not view._space_pan and view._pan_last is None
    assert win.cursor is None and win.frame_cursor is None and \
        win.selection is None, "平移誤觸點選／選取"

    # 符合頁面／符合寬度幾何（fit_width 預留垂直捲軸、水平置中）
    view.fit_page()
    app.processEvents()
    z = view.zoom_factor()
    rect = view.scene().sceneRect()
    assert rect.width() * z <= view.viewport().width() + 2 and \
        rect.height() * z <= view.viewport().height() + 2, "符合頁面未入視窗"
    assert win._zoom_label.text() == f"{round(z * 100)}%"
    view.fit_width()
    app.processEvents()
    zw = view.zoom_factor()
    assert rect.width() * zw <= view.viewport().width() + 2, "符合寬度後頁寬溢出"
    assert zw > z, "符合寬度應比整頁大（本頁高>寬）"
    cx = view.mapToScene(view.viewport().rect().center()).x()
    assert abs(cx - rect.center().x()) < 3, f"符合寬度未水平置中：{cx}"
    win.close()

    print(
        f"C26 畫布縮放平移：開窗整頁 fit（{round(z0 * 100)}%，頁完整可見）＋檢視選單"
        "五項快捷鍵（Ctrl+= / - / 1 / 0 / 2）＋set_zoom clamp 10%〜800% 與狀態列同步"
        "＋Ctrl+滾輪 1.25 倍階＋Shift+滾輪水平（素滾輪垂直照舊）＋重繪保留縮放與"
        "視口中心＋中鍵與空白鍵拖曳平移（不誤觸點選）＋符合寬度置中且不溢出"
    )
