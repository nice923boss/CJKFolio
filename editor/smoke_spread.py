"""smoke C32：對頁檢視（Sprint 129 甲4；自 smoke_check.py 分檔，行數紀律慣例）。

離屏可驗：檢視選單「對頁檢視」項可勾選與 Ctrl+3、切換後雙頁併排（兩張底圖）、
右翻書偶右奇左（Sprint 22 側別）左右定位、目前頁字格座標偏移後 itemAt 仍反查
該格（R6 首要風險）、對頁整頁標 ("facing", 頁號) 不入 item_map、點對頁跳該頁、
頁1（奇）單邊左（僅一張底圖、無對頁 item）、關閉對頁回單頁、切換不改版面頁數
（純檢視不污染匯出）。視覺對位與印刷拼版待 Owner 真視窗（GAPS #84 批次）。
"""
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QMenu


def _base_count(win) -> int:
    """scene 內底圖 pixmap 張數＝已渲染頁數（互動層與高亮皆 RectItem，不計）。"""
    return sum(1 for it in win.scene.items()
              if isinstance(it, QGraphicsPixmapItem))


def _facing_items(win) -> list:
    return [it for it in win.scene.items()
            if it.data(0) and it.data(0)[0] == "facing"]


def check_spread(EditorWindow, doc_path) -> None:
    app = QApplication.instance()
    assert app is not None
    win = EditorWindow(str(doc_path))  # paiban-xiaoji-ch1 11 頁真樣張
    total = len(win.layout_result.pages)
    assert total == 11, f"樣張應 11 頁，得 {total}"

    # 檢視選單「對頁檢視」項：可勾選、快捷鍵 Ctrl+3、初始未勾＝單頁
    menu = next(
        m for m in win.menuBar().findChildren(QMenu) if m.title() == "檢視")
    facing_act = next(
        a for a in menu.actions() if a.text() == "對頁檢視（雙頁併排）")
    assert facing_act is win._facing_action
    assert facing_act.isCheckable(), "對頁檢視項應可勾選"
    assert facing_act.shortcut().toString() == "Ctrl+3", \
        facing_act.shortcut().toString()
    assert not facing_act.isChecked() and not win._facing, "初始應為單頁"
    assert _base_count(win) == 1, "單頁模式應只有一張底圖"

    # 導航到頁2（偶＝右頁），開對頁 → 併排（右2、左3），兩張底圖
    win._goto_page(2)
    facing_act.trigger()  # ＝_toggle_facing：勾選並重繪
    assert win._facing and facing_act.isChecked(), "切換後應為對頁模式"
    assert _base_count(win) == 2, f"對頁應兩張底圖，得 {_base_count(win)}"

    # item_map 僅含目前頁（頁2）字格、無 facing 鍵；scene 另有 ("facing", 3)
    assert all(not (k and k[0] == "facing") for k in win._item_by_key), \
        "對頁跳頁鍵不應入 item_map（否則污染單頁命中路徑）"
    body_keys = [k for k in win._item_by_key
                 if isinstance(k, tuple) and len(k) == 2
                 and all(isinstance(v, int) for v in k)]
    assert body_keys, "目前頁應有 body 字格於 item_map"
    facing_items = _facing_items(win)
    assert facing_items, "對頁應有 ('facing', 頁號) item"
    assert {it.data(0)[1] for it in facing_items} == {3}, \
        f"對頁頁號應為 3，得 {{it.data(0)[1] for it in facing_items}}"

    # 座標偏移後目前頁（右頁 x=頁寬）字格仍 100% 命中（itemAt 取回同格）
    hit = miss = 0
    for k in body_keys:
        it = win._item_by_key[k]
        found = win.scene.itemAt(it.sceneBoundingRect().center(), QTransform())
        if found is not None and found.data(0) == k:
            hit += 1
        else:
            miss += 1
    assert miss == 0, f"偏移後命中失準：{hit} 中 {miss} 失"

    # 點對頁 → 跳該頁（頁3），維持對頁模式
    win._on_pick(facing_items[0])
    assert win.page.number == 3, f"點對頁未跳頁，仍在 {win.page.number}"
    assert win._facing, "跳頁後應維持對頁模式"

    # 頁1（奇）單邊左：僅一張底圖、無對頁 item
    win._goto_page(1)
    assert _base_count(win) == 1, "頁1 對頁應單邊（一張底圖）"
    assert not _facing_items(win), "頁1 不應有對頁 item"

    # 關閉對頁 → 回單頁；全程不改版面頁數（純檢視不污染匯出）
    facing_act.trigger()
    assert not win._facing and _base_count(win) == 1, "關閉對頁未回單頁"
    assert len(win.layout_result.pages) == total, "對頁切換不得改版面頁數"

    win._shutdown_thumbnails()
    print(
        f"C32 對頁檢視：檢視選單勾選項＋Ctrl+3，頁2 開對頁併排兩張底圖（右2左3，"
        f"Sprint 22 偶右奇左）、目前頁 {hit} 格偏移後全命中、對頁整頁標跳頁鍵不入"
        f"item_map、點對頁跳頁3、頁1 單邊左、關閉回單頁（版面 {total} 頁不變）"
    )
