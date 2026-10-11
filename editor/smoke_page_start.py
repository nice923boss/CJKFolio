"""smoke C47：從游標段起新頁（Sprint 158；分檔於 editor/，行數紀律慣例）。

Owner：「我要讓這個標題後也能直接換到下一頁」。UI 面的風險在「按了像沒反應」與
「動錯段」：本檔驗選單動作確實掛上 Ctrl+Return、游標段移到新頁第一行、畫面跟到
該頁、狀態列報頁數與 Ctrl+Z，取消起新頁接回原處，undo 一步回原，以及守門（無游標、
文字框游標、段 0、重複起新頁、未設可取消）不動文件。主版不同的節首拒收在 pytest 驗。

純函式與 session 面另有 tests/test_page_break.py。由 smoke_blank_line 結尾延遲匯入呼叫
（同一樣張，smoke_check.py 行數紀律）。
"""
import tempfile
from dataclasses import replace
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QAction

from cjkfolio.document import PlacedImage, load_document, save_document

from editor.canvas import resolve_hit


def check_page_start(EditorWindow, doc_path) -> None:
    win = EditorWindow(str(doc_path))
    doc0, pages0 = win.doc, len(win.layout_result.pages)
    shortcuts = {a.text(): a.shortcut().toString() for a in win.findChildren(QAction)}
    assert shortcuts.get("從游標段起新頁") == "Ctrl+Return", shortcuts.get("從游標段起新頁")
    assert "取消游標段起新頁" in shortcuts

    # 守門：無游標、文字框游標
    assert win.cursor is None
    win._start_page_at_cursor()
    assert "先點要移到新頁的標題" in win.statusBar().currentMessage()
    win.cursor, win.frame_cursor = (3, 0), (0, 0)
    win._start_page_at_cursor()
    assert "文字框不跨頁" in win.statusBar().currentMessage()
    win.frame_cursor = None
    assert win.doc is doc0, "守門卻動了文件"

    # 起新頁：頁 2 第 5 行起的段移到頁 3 第 1 行，畫面跟到頁 3
    win._goto_page(2)
    win.cursor = (4, 0)
    target = resolve_hit(win.doc, win.page, *win.cursor).para_idx
    assert target is not None and win.page.placed[3].para_idx != target
    win._start_page_at_cursor()
    msg = win.statusBar().currentMessage()
    assert f"段 {target + 1} 已移到頁 3 開頭" in msg and "Ctrl+Z" in msg, msg
    assert win.page.number == 3 and win.page.placed[0].para_idx == target
    assert resolve_hit(win.doc, win.page, *win.cursor).para_idx == target, "游標未跟隨"
    pages1 = len(win.layout_result.pages)

    # 重複起新頁不動文件
    doc1 = win.doc
    win._start_page_at_cursor()
    assert "已經從新頁開始" in win.statusBar().currentMessage() and win.doc is doc1

    # 取消起新頁：接回頁 2，段落與原文件相同
    win._clear_page_start_at_cursor()
    assert f"段 {target + 1} 已取消起新頁，接回頁 2" in win.statusBar().currentMessage()
    assert win.doc.paragraphs == doc0.paragraphs and len(win.layout_result.pages) == pages0

    # 未設起新頁的段取消＝提示不動；段 0 起新頁＝提示不動
    doc2 = win.doc
    win._clear_page_start_at_cursor()
    assert "沒有設起新頁" in win.statusBar().currentMessage() and win.doc is doc2
    win._goto_page(1)
    win.cursor = (0, 0)
    win._start_page_at_cursor()
    assert "本來就在書首" in win.statusBar().currentMessage() and win.doc is doc2

    # undo 一步回原
    win._goto_page(2)
    win.cursor = (4, 0)
    win._start_page_at_cursor()
    win._on_undo()
    assert win.doc.paragraphs == doc0.paragraphs, "undo 未回原"
    assert len(win.layout_result.pages) == pages0

    win._shutdown_thumbnails()
    _check_snap_on_open(EditorWindow, doc_path)
    print(
        f"C47 從游標段起新頁：Ctrl+Return 已掛選單，段 {target + 1} 由頁 2 第 5 行移到頁 3 "
        f"第 1 行（全書 {pages0} → {pages1} 頁）＋游標與畫面跟隨，取消接回原處、undo 一步回原，"
        "無游標／文字框／段 0／重複起新頁／未設可取消五道守門皆不動文件"
    )


def _check_snap_on_open(EditorWindow, doc_path) -> None:
    """C48：封底圖頁號超出全書（存檔前全書變短）時，開檔移回末頁且封面圖照常顯示。"""
    with tempfile.TemporaryDirectory() as tmp:
        Image.new("RGB", (8, 8), "red").save(Path(tmp) / "c.png")
        probe = EditorWindow(str(doc_path))
        last = len(probe.layout_result.pages)
        probe._shutdown_thumbnails()
        rect = (0.0, 0.0, 10.0, 10.0)
        path = Path(tmp) / "past-end.doc.json"
        save_document(replace(load_document(str(doc_path)), images=(
            PlacedImage(path="c.png", page=1, rect=rect),
            PlacedImage(path="c.png", page=last + 4, rect=rect))), str(path))
        win = EditorWindow(str(path))
        msg = win.statusBar().currentMessage()
        assert f"頁 {last + 4} 超出全書，已移到末頁 {last}" in msg, msg
        assert [im.page for im in win.doc.images] == [1, last] and win._is_dirty()
        assert win.windowTitle().endswith("*"), win.windowTitle()
        win._goto_page(1)
        assert "置入圖無法載入" not in win.statusBar().currentMessage()
        win._on_undo()
        assert win.doc.images[1].page == last + 4
        win._on_thumbs_done(win._thumb_generation, 0.0, 0)
        assert "超出全書" in win.statusBar().currentMessage()
        win._shutdown_thumbnails()
    print(f"C48 開檔移回書外封底圖：頁 {last + 4} → 末頁 {last}、標未存、封面照常、undo 後狀態列警告")
