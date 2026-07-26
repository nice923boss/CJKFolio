"""smoke C40：手動空行增刪（Sprint 141；分檔於 editor/，行數紀律慣例）。

空段在畫布上不產字格（看不到也點不到），故 UI 面的風險全在「按了像沒反應」與
「刪錯東西」：本檔驗狀態列據實回報、游標跟著目標段走、後續行真的下移一槽、
undo 一步回原，以及三道守門（無游標／文字框游標／段 0／前段非空）不動任何內容。

純函式與 session 面另有 tests/test_blank_line_edit.py（Gate 4：產出與驗證分途）。
未涵蓋：para_idx=None 的字格（拉丁串／空格）該走「無文件游標」提示，本樣張整頁
無此種行，離屏構不出來，留待 Owner 真視窗（GAPS #96）。
"""
from editor.canvas import resolve_hit


def check_blank_line(EditorWindow, doc_path) -> None:
    win = EditorWindow(str(doc_path))  # 41 段 11 頁樣張
    paras0 = len(win.doc.paragraphs)
    pages0 = len(win.layout_result.pages)
    assert (paras0, pages0) == (41, 11), f"樣張應 41 段 11 頁，得 {paras0} 段 {pages0} 頁"

    # 守門一：無游標不插入（開窗即未選字格）
    assert win.cursor is None, "開窗不該自帶游標"
    win._insert_blank_line()
    assert "先點一個字格" in win.statusBar().currentMessage()
    assert len(win.doc.paragraphs) == paras0, "無游標卻改了文件"

    # 守門二：文字框游標（框為單段，無前段可插）；只走守門分支，故直接設旗標
    win.cursor, win.frame_cursor = (3, 0), (0, 0)
    win._insert_blank_line()
    assert "文字框為單段" in win.statusBar().currentMessage()
    assert len(win.doc.paragraphs) == paras0, "文字框游標卻改了文件"
    win.frame_cursor = None

    # 插入：文件多一空段、狀態列報頁數、游標跟著目標段（索引 +1）、後續行下移一槽
    target = resolve_hit(win.doc, win.page, *win.cursor).para_idx
    slot0 = next(ln.slot for ln in win.page.placed if ln.para_idx == target)
    win._insert_blank_line()
    msg = win.statusBar().currentMessage()
    assert f"已在段{target}前插入空行" in msg and "Ctrl+Z 一步回原" in msg, msg
    assert f"全書 {pages0} 頁" in msg, msg
    assert len(win.doc.paragraphs) == paras0 + 1
    assert win.doc.paragraphs[target].text == "", "插入的不是空段"
    assert resolve_hit(win.doc, win.page, *win.cursor).para_idx == target + 1, "游標未跟隨"
    slot1 = next(ln.slot for ln in win.page.placed if ln.para_idx == target + 1)
    assert slot1 == slot0 + 1, f"目標段未下移一槽（{slot0} → {slot1}）"

    # 移除：回到原文件（游標仍在目標段，移除的是它前面那個空段）
    win._remove_blank_line()
    assert f"已移除段{target + 1}前的空行" in win.statusBar().currentMessage()
    assert len(win.doc.paragraphs) == paras0
    assert next(ln.slot for ln in win.page.placed if ln.para_idx == target) == slot0

    # 守門三：前段非空 → 不動任何內容（同一物件）
    doc_before = win.doc
    win._remove_blank_line()
    assert "不是空行" in win.statusBar().currentMessage()
    assert win.doc is doc_before, "前段非空卻動了文件"

    # 守門四：段 0 前面沒有空行可移除
    win._goto_page(1)
    win.cursor = (0, 0)
    assert resolve_hit(win.doc, win.page, *win.cursor).para_idx == 0
    win._remove_blank_line()
    assert "已是第一段" in win.statusBar().currentMessage()
    assert win.doc is doc_before

    # undo 一步回原：插入後撤銷，段數與版面都回去
    win.cursor = (3, 0)
    win._insert_blank_line()
    assert len(win.doc.paragraphs) == paras0 + 1
    win._on_undo()
    assert len(win.doc.paragraphs) == paras0, "undo 未回原段數"
    assert len(win.layout_result.pages) == pages0, "undo 未回原頁數"

    win._shutdown_thumbnails()
    print(
        f"C40 手動空行增刪：無游標／文字框／段 0／前段非空四道守門皆不動文件，"
        f"插入後段{target}下移一槽＋游標跟隨＋狀態列報全書 {pages0} 頁，"
        f"移除復原、undo 一步回 {paras0} 段 {pages0} 頁"
    )
