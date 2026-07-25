"""smoke C38：文字框整框增刪移（Sprint 136；自 smoke_check.py 分檔，行數紀律慣例）。

Owner 真視窗回饋（封面實景）：放了封面圖之後，書名框既刪不掉（刪到最後一字撞
document@2「框 text 非空」不變式，狀態列只回「無法刪除」）也搬不動（畫布只有
框內字格可點，框本身沒有命中區）。本檔驗的就是補上的那一層。

素材＝samples/cover.doc.json（Sprint 132 真封面樣張：一張置入圖＋書名／作者／
出版者三個文字框），即 Owner 截圖的同一種版面，故驗收即代驗真情境。

離屏可驗：框空白處可點選整框而框內點字仍得字游標（z 疊序）、拖框邊移動與拖角
改大小各一步 undo、Delete 移除整框、刪到最後一字整框一併移除（不再是死結）、
新增文字框、滿版圖蓋住書名框時選單入口仍選得到且選取後的邊帶疊在圖之上（唯一
搬得動被圖蓋住的框的地方）。拖曳手感與視覺對位待 Owner 真視窗（GAPS #19 批次）。
"""
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent

DPI = 150
SCALE = DPI / 72.0


def _top(win, x_pt, y_pt):
    """畫布在該點的最上層命中鍵（複製 CanvasView._cell_item_at 的判定：top-first
    取第一個帶 data(0) 的 item），故驗的是真實點擊會取到誰。"""
    for item in win.scene.items(QPointF(x_pt * SCALE, y_pt * SCALE)):
        if item.data(0) is not None:
            return item.data(0)
    return None


def _blank_spot(win, idx):
    """框內「點得到整框」的空白處（掃格點取第一個最上層＝frame-box 者）。"""
    x0, y0, x1, y1 = win.doc.text_frames[idx].rect
    for i in range(1, 20):
        for j in range(1, 20):
            x = x0 + (x1 - x0) * i / 20
            y = y0 + (y1 - y0) * j / 20
            if _top(win, x, y) == ("frame-box", idx):
                return x, y
    raise AssertionError(f"框 {idx} 找不到可點選整框的空白處")


def _key(k):
    return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)


def check_frame_box(EditorWindow, ROOT) -> None:
    """跑 C38 並 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    doc_path = ROOT / "samples" / "cover.doc.json"

    # ── 命中層：框空白處選整框、框內字格仍是字 ──
    win = EditorWindow(str(doc_path))
    assert len(win.doc.text_frames) == 3, "封面樣張應有書名／作者／出版者三框"
    assert len(win.doc.images) == 1, "封面樣張應有一張置入圖"
    title_rect = win.doc.text_frames[0].rect
    bx, by = _blank_spot(win, 0)
    cell_key = next(k for k in win._item_by_key
                    if k and k[0] == "frame" and k[1] == 0)
    cell_rect = win._item_by_key[cell_key].rect()
    assert _top(win, cell_rect.center().x() / SCALE,
                cell_rect.center().y() / SCALE) == cell_key, \
        "框內字格上的最上層應是字格（打字為主要操作，不可被搬框攔胡）"

    # ── 拖框移動（途中只畫預覽，放開才提交一步） ──
    box = next(it for it in win.scene.items() if it.data(0) == ("frame-box", 0))
    win._on_pick(box, QPointF(bx * SCALE, by * SCALE))
    assert win._frame_box_idx == 0, "點框空白處未選中整框"
    assert win._image_idx is None, "選框應與選圖互斥"
    win._on_canvas_move(QPointF((bx + 20) * SCALE, (by - 10) * SCALE))
    assert win.doc.text_frames[0].rect == title_rect, "拖曳途中不應改動文件"
    win._on_canvas_release()
    moved = win.doc.text_frames[0].rect
    assert abs(moved[0] - (title_rect[0] + 20)) < 1e-6, f"位移不符：{moved}"
    assert abs(moved[1] - (title_rect[1] - 10)) < 1e-6, f"位移不符：{moved}"
    win._on_undo()
    assert win.doc.text_frames[0].rect == title_rect, "一步 undo 應回移動前"

    # ── 拖角改大小（不鎖長寬比：框形決定欄數與每欄字數） ──
    win._select_frame_box(0)
    se = next(it for it in win.scene.items()
              if it.data(0) == ("frame-handle", 0, "se"))
    win._on_pick(se, QPointF(title_rect[2] * SCALE, title_rect[3] * SCALE))
    win._on_canvas_move(QPointF((title_rect[0] + 60) * SCALE,
                                (title_rect[1] + 300) * SCALE))
    win._on_canvas_release()
    sized = win.doc.text_frames[0].rect
    assert abs((sized[2] - sized[0]) - 60) < 1e-6, f"寬未跟隨拖曳：{sized}"
    assert abs((sized[3] - sized[1]) - 300) < 1e-6, f"高未跟隨拖曳：{sized}"
    assert (sized[0], sized[1]) == (title_rect[0], title_rect[1]), "對角應固定"
    win._on_undo()
    assert win.doc.text_frames[0].rect == title_rect, "一步 undo 應回縮放前"

    # ── 拖出紙面：不夾界（貼邊排版是正當需求）但據實說，不讓字憑空消失 ──
    page_h_pt = win.template.page_height_mm * 72.0 / 25.4
    win._select_frame_box(0)
    win.session.move_text_frame(0, 0.0, page_h_pt + 50 - title_rect[1])
    win._rebuild()
    assert "整個移出頁面" in win._frame_overflow_note(0), \
        f"框整個在頁外未據實提示：{win._frame_overflow_note(0)!r}"
    win._on_undo()
    win.session.move_text_frame(0, 0.0, page_h_pt - title_rect[3] + 30)
    win._rebuild()
    assert "一部分在頁面外" in win._frame_overflow_note(0), \
        f"框部分在頁外未據實提示：{win._frame_overflow_note(0)!r}"
    win._on_undo()
    assert win.doc.text_frames[0].rect == title_rect
    assert win._frame_overflow_note(0) == "", "回到頁內不應仍提示"

    # ── Delete 移除整框、undo 回原（作者框：與書名框不重疊，選取不互擾） ──
    win._select_frame_box(1)
    author = win.doc.text_frames[1]
    assert win._on_key(_key(Qt.Key.Key_Delete)) is True, "選框時 Delete 未被處理"
    assert len(win.doc.text_frames) == 2, "Delete 未移除整框"
    assert win.doc.text_frames[1].text != author.text, "移除的不是選取的那一框"
    win._on_undo()
    assert win.doc.text_frames[1] == author, "undo 應把整框放回原位原文"

    # ── Owner 的死結：刪到最後一字＝整框一併移除（不再回「無法刪除」） ──
    win2 = EditorWindow(str(doc_path))
    title_text = win2.doc.text_frames[0].text
    for i in range(len(title_text)):
        cell = next(k for k in win2._item_by_key
                    if k and k[0] == "frame" and k[1] == 0)
        win2._on_pick(win2._item_by_key[cell])
        assert win2.frame_cursor is not None, "點框字格未取得框游標"
        assert win2._on_key(_key(Qt.Key.Key_Backspace)) is True
        msg = win2.statusBar().currentMessage()
        assert "無法刪除" not in msg, f"第 {i + 1} 次刪字撞不變式：{msg}"
    assert len(win2.doc.text_frames) == 2, "刪光書名框的字後整框應一併移除"
    assert "整個文字框一併移除" in win2.statusBar().currentMessage(), \
        f"末字刪除未據實說明：{win2.statusBar().currentMessage()}"
    assert win2.frame_cursor is None, "框沒了，框游標不應仍指著它"
    win2._on_undo()  # 移除框為一步
    assert len(win2.doc.text_frames) == 3, "undo 應把框放回來"
    assert win2.doc.text_frames[0].text == title_text[-1:], \
        f"undo 應回到只剩末字的那一步，得到 {win2.doc.text_frames[0].text!r}"

    # ── 新增文字框（選單路徑，離屏旁路對話框） ──
    win3 = EditorWindow(str(doc_path))
    n3 = len(win3.doc.text_frames)
    win3._add_text_frame_dialog(text="加字測試")
    assert len(win3.doc.text_frames) == n3 + 1, "選單新增未生效"
    added = win3.doc.text_frames[-1]
    assert added.text == "加字測試" and added.page == win3.page.number
    page_w = win3.template.page_width_mm * 72.0 / 25.4
    assert abs((added.rect[0] + added.rect[2]) / 2 - page_w / 2) < 1e-6, \
        f"新框未置於頁面水平中央：{added.rect}"
    assert win3._frame_box_idx == n3, "新增後應選中新框（可直接拖曳定位）"
    win3._on_undo()
    assert len(win3.doc.text_frames) == n3, "一步 undo 應撤掉新增"
    win3._add_text_frame_dialog(text="   ")  # 空白文字＝不成框（不默默建空框）
    assert len(win3.doc.text_frames) == n3
    assert "需有文字" in win3.statusBar().currentMessage(), \
        f"空文字未據實提示：{win3.statusBar().currentMessage()}"

    # ── 滿版圖蓋住書名框：選單入口選得到，選取後的邊帶疊在圖之上可搬 ──
    win4 = EditorWindow(str(doc_path))
    page_h = win4.template.page_height_mm * 72.0 / 25.4
    win4.session.resize_image(0, (0.0, 0.0, page_w, page_h))  # 滿版封面圖
    win4._rebuild()
    covered = _top(win4, *_blank_spot(win, 0))
    assert covered == ("image", 0), f"滿版圖應蓋住框的命中區，得到 {covered}"
    win4._select_page_frame_box()
    assert win4._frame_box_idx == 0, "選單入口未選到本頁第一個框"
    assert win4._image_idx is None, "選框應清掉圖選取"
    top_edge = _top(win4, (title_rect[0] + title_rect[2]) / 2, title_rect[1] + 1)
    assert top_edge == ("frame-box", 0), \
        f"選取後的邊帶應疊在圖之上（否則被圖蓋住的框仍搬不動），得到 {top_edge}"
    band = next(it for it in win4.scene.items()
                if it.data(0) == ("frame-box", 0) and it.zValue() > 1)
    win4._on_pick(band, QPointF((title_rect[0] + title_rect[2]) / 2 * SCALE,
                                (title_rect[1] + 1) * SCALE))
    win4._on_canvas_move(QPointF((title_rect[0] + title_rect[2]) / 2 * SCALE,
                                 (title_rect[1] + 31) * SCALE))
    win4._on_canvas_release()
    assert abs(win4.doc.text_frames[0].rect[1] - (title_rect[1] + 30)) < 1e-6, \
        f"被滿版圖蓋住的框未搬動：{win4.doc.text_frames[0].rect}"
    win4._select_page_frame_box()  # 多框輪流：0 → 1 → 2 → 回 0
    assert win4._frame_box_idx == 1
    win4._select_page_frame_box()
    assert win4._frame_box_idx == 2
    win4._select_page_frame_box()
    assert win4._frame_box_idx == 0, "輪到末框後應回到第一框"

    for w in (win, win2, win3, win4):
        w._shutdown_thumbnails()
    print(
        "C38 文字框整框增刪移：封面真樣張（一圖三框）框空白處點選整框而框內字格仍"
        "得字游標＋拖框邊移動與拖角改大小各一步 undo（途中只畫預覽）＋Delete 移除"
        "整框＋刪到最後一字整框一併移除（Owner 死結解除，undo 回只剩末字那一步）"
        "＋拖出紙面全出／半出各自據實提示（不夾界但不沉默）"
        "＋選單新增文字框置於頁面中央（空白文字守門）＋滿版圖蓋住書名框時選單入口"
        "選得到、選取邊帶疊在圖之上仍可搬動、多框輪流選取"
    )
