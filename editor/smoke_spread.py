"""smoke C32：對頁檢視（Sprint 129 甲4；自 smoke_check.py 分檔，行數紀律慣例）。

離屏可驗：檢視選單「對頁檢視」項可勾選與 Ctrl+3、切換後雙頁併排（兩張底圖）、
右翻書偶右奇左（Sprint 22 側別）左右定位、目前頁字格座標偏移後 itemAt 仍反查
該格（R6 首要風險）、對頁整頁標 ("facing", 頁號) 不入 item_map、點對頁跳該頁、
頁1（奇）單邊左（僅一張底圖、無對頁 item）、關閉對頁回單頁、切換不改版面頁數
（純檢視不污染匯出）。視覺對位與印刷拼版待 Owner 真視窗（GAPS #84 批次）。

Sprint 145 Owner 回饋（「封面為紙張的第一頁，而第二頁應該是要在翻開後的右邊」）：
配對改依紙面奇偶（偶右奇左，與封面無關）。帶封面時翻開封面即見紙面 2（書頁 1）在右、
紙面 3 在左＝兩張真底圖成對，Sprint 144 的封二空紙面已隨配對修正移除；封面（紙面 1）
與末偶紙面（翻完闔上書的封底畫面）單頁。本檔以底圖張數與 scene 邊界寬判定。
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
    body = [p for p in win.layout_result.pages if not p.blank]
    assert len(body) == 11, f"樣張應 11 頁內文，得 {len(body)}"
    assert total == 12, f"11 頁補足 4 的倍數應 12 頁，得 {total}"  # Sprint 144

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

    # ── 帶封面（Sprint 145 紙面配對）：翻開封面即見紙面2 右、紙面3 左（兩張真
    # 底圖成對），封面與末偶紙面單頁（闔上的書與翻完闔上書的封底畫面） ──
    from cjkfolio.cover import with_cover

    win.session.replace_document(with_cover(win.doc, win.template))
    total_c = len(win.layout_result.pages)
    assert total_c == 12 and not any(p.blank for p in win.layout_result.pages), \
        f"1 封面＋11 內文＝12 已是 4 的倍數應補 0，得 {total_c} 頁"
    facing_act.trigger()
    win._goto_page(1)                    # 封面＝紙面1：單獨一頁（闔上的書）
    w_cover = win.scene.itemsBoundingRect().width()
    assert _base_count(win) == 1 and not _facing_items(win), "封面應單頁"
    win._goto_page(2)                    # 紙面2（書頁1／目次位）：右＝本頁、左＝紙面3
    w_spread = win.scene.itemsBoundingRect().width()
    assert _base_count(win) == 2, "翻開封面應兩張真底圖（紙面2＋3），空紙面已廢"
    assert {it.data(0)[1] for it in _facing_items(win)} == {3}, "對頁應為紙面3"
    assert w_spread > w_cover * 1.9, \
        f"翻開封面應兩頁寬，得 {w_spread:.0f} vs {w_cover:.0f}"
    win._goto_page(total_c)              # 末偶紙面：單頁（翻完闔上書＝封底畫面）
    assert _base_count(win) == 1 and not _facing_items(win), "末偶紙面應單頁封底"
    facing_act.trigger()

    win._shutdown_thumbnails()
    print(
        f"C32 對頁檢視：檢視選單勾選項＋Ctrl+3，頁2 開對頁併排兩張底圖（右2左3，"
        f"紙面偶右奇左）、目前頁 {hit} 格偏移後全命中、對頁整頁標跳頁鍵不入"
        f"item_map、點對頁跳頁3、頁1 單邊左、關閉回單頁（版面 {total} 頁不變）、"
        f"帶封面時翻開封面兩頁寬（{w_spread:.0f}px）而封面與末偶紙面單頁"
        f"（{w_cover:.0f}px）＝闔上的書與封底畫面"
    )
