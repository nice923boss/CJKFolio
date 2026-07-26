"""smoke C41：頁面拖曳重排（Sprint 142；自 smoke_check.py 分檔，行數紀律慣例）。

Owner 回饋：AI 樣式指派後封面跑到第 4 頁，要能像搬投影片那樣把它拖回第 1 頁。
本產品的頁面是段落流排的結果，可搬的最小完整單位是節，故拖曳一頁＝搬整節後全書重排。

離屏可驗：插入位換算（drop_index 純函式，含 IconMode 多欄）、面板 dropEvent 把
（來源頁, 插入位）交給 mixin、搬節後逐頁主版與目前頁跟隨、一步 undo 回原序、
非節首頁拒收並指名該搬哪一頁、放回原位不佔 undo、封面頁不參與。真滑鼠拖曳手感
與插入線視覺待 Owner 真視窗（GAPS #19 批次）。
"""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QDropEvent

from editor.page_panel import drop_index


def _masters(win) -> list:
    """逐頁主版；裝訂補頁不計（Sprint 144：它承末頁主版，不代表任何節）。"""
    return [p.master for p in win.layout_result.pages if not p.blank]


def _drop_at(panel, x: float, y: float) -> None:
    """對面板送一次放下事件（QDropEvent 的 position 即 viewport 座標）。"""
    from PySide6.QtCore import QMimeData

    data = QMimeData()  # QDropEvent 不接管所有權，需在事件期間保住參照
    event = QDropEvent(QPointF(x, y), Qt.DropAction.MoveAction, data,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    panel.dropEvent(event)


def check_page_order(EditorWindow, chapter_path, paiban_path) -> None:
    # ── 插入位換算（純函式；bands＝各縮圖的 (top, bottom, 中心 x)）──
    one_col = [(0, 100, 50), (100, 200, 50), (200, 300, 50)]
    assert drop_index(one_col, 50, -10) == 0, "落在最上方＝搬到最前"
    assert drop_index(one_col, 50, 150) == 1, "落在第 2 項上＝插在其前"
    assert drop_index(one_col, 50, 999) == 3, "落在最下方＝搬到最末"
    two_col = [(0, 100, 50), (0, 100, 150), (100, 200, 50)]
    assert drop_index(two_col, 100, 50) == 1, "同列帶內比欄位"
    assert drop_index(two_col, 40, 50) == 0, "同列帶最左＝插在該列帶之首"
    assert drop_index(two_col, 999, 50) == 2, "同列帶最右＝插在下一列帶之首"

    # ── 兩節樣張 chapter-opening：頁 1＝B-部扉節、頁 2＝A-內文版節 ──
    win = EditorWindow(str(chapter_path))
    assert _masters(win) == ["B-部扉", "A-內文版"], _masters(win)
    assert win._section_head_pages() == [1, 2], win._section_head_pages()

    # 面板放下（來源列＝頁 2、放下點在所有縮圖之上＝插到最前）：走真 dropEvent
    panel = win._page_panel
    panel.setCurrentRow(1)
    _drop_at(panel, 0.0, -1000.0)
    assert _masters(win) == ["A-內文版", "B-部扉"], _masters(win)
    assert win.doc.master == "A-內文版", "新首節主版須升格為 doc.master"
    assert win.page.number == 1, f"搬後未跳到新節首頁，得頁 {win.page.number}"
    msg = win.statusBar().currentMessage()
    assert "已把頁 2 起的一節搬到頁 1" in msg, msg

    # 一步 undo 回原序（與文字、樣式編輯共用同一條歷史）
    win.session.undo()
    assert _masters(win) == ["B-部扉", "A-內文版"]
    assert win.doc.master == "B-部扉"

    # 放回原位：不佔 undo 步、據實提示
    depth = len(win.session._undo)
    win._reorder_pages(1, 1)
    assert len(win.session._undo) == depth, "原位放下不應推 undo 步"
    assert "頁面順序無變更" in win.statusBar().currentMessage()

    # 封面頁不參與（with_cover 建封面後版面頁 1 即封面）
    from cjkfolio.cover import with_cover

    win.session.replace_document(with_cover(win.doc, win.template))
    assert win.layout_result.cover_pages == 1
    before = _masters(win)
    win._reorder_pages(1, 3)
    assert "封面頁固定在最前" in win.statusBar().currentMessage()
    assert _masters(win) == before, "封面拖曳不應改版面"
    assert win._section_head_pages() == [2, 3], win._section_head_pages()

    # ── 單節多頁真稿 paiban-xiaoji-ch1：非節首頁拒收並指名該搬哪一頁 ──
    win2 = EditorWindow(str(paiban_path))
    assert len(_masters(win2)) == 11
    assert win2._section_head_pages() == [1], win2._section_head_pages()
    doc_before = win2.doc
    win2._reorder_pages(3, 1)
    msg2 = win2.statusBar().currentMessage()
    assert "頁 3 不是節首" in msg2 and "請改拖頁 1" in msg2, msg2
    assert win2.doc is doc_before, "拒收時文件不得變動"

    # 裝訂補頁不參與（Sprint 144）：末尾補的空白頁隨內文頁數自動增減，不是可搬的節
    blank_no = next(p.number for p in win2.layout_result.pages if p.blank)
    win2._reorder_pages(blank_no, 1)
    msg3 = win2.statusBar().currentMessage()
    assert "裝訂補頁不參與拖曳重排" in msg3, msg3
    assert win2.doc is doc_before, "拒收時文件不得變動"

    for w in (win, win2):  # 退出安全：縮圖執行緒收工（closeEvent 同路徑）
        w._shutdown_thumbnails()
    print(
        "C41 頁面拖曳重排：插入位換算（單欄／多欄）＋面板 dropEvent 交回呼＋搬節後"
        "逐頁主版與 doc.master 跟隨＋跳到新節首頁＋一步 undo 回原序＋原位放下不佔"
        "undo＋封面頁不參與＋非節首頁拒收並指名節首頁＋裝訂補頁拒收"
    )
