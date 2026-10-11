"""smoke C41 附驗：刪除頁面與插入空白頁（Sprint 153）。

由 smoke_page_order.check_page_order 末尾呼叫（smoke_check.py 已超 800 行，不再往
它加註冊行，同 Sprint 147 把新驗收塞進既有 C19 的處置）。

離屏可驗：右鍵選單三項、插入前後跳到新頁、空白頁占一頁且照常編頁碼、裝訂補頁
自動湊回 4 的倍數、一步 undo、刪頁、封面／裝訂補頁／跨頁段頁拒收並說明原因；
插頁後目次頁碼在同一步內更新、右鍵「更新目次頁碼」一鍵重算（Sprint 155）。
真右鍵手感與縮圖重繪屬真視窗驗收（GAPS #19 批次）。
"""
from PySide6.QtCore import Qt


def _act(menu, prefix: str):
    return next(a for a in menu.actions() if a.text().startswith(prefix))


def _content(win) -> list:
    return [p for p in win.layout_result.pages if not p.blank]


def check_page_edit(EditorWindow, chapter_path, paiban_path) -> None:
    # ── 單節多頁真樣張 paiban-xiaoji-ch1：頁 2 乾淨起頁、頁 3 跨頁續段 ──
    win = EditorWindow(str(paiban_path))
    original = win.doc
    pages0 = len(win.layout_result.pages)
    content0 = len(_content(win))
    assert pages0 % 4 == 0, pages0
    menu = win._build_page_menu(2)
    for label in ("在此頁之前插入空白頁", "在此頁之後新增空白頁", "刪除此頁（頁 2）"):
        _act(menu, label)

    # 在頁 2 之前插入：新頁 2 是只有一條空行的頁，原頁 2 內容退到頁 3
    _act(menu, "在此頁之前插入空白頁").trigger()
    pages = win.layout_result.pages
    assert len(_content(win)) == content0 + 1
    assert len(pages) % 4 == 0, f"插頁後總頁數 {len(pages)} 非 4 的倍數"
    assert win.page.number == 2
    assert [pl.line.cells for pl in pages[1].placed] == [()], "新頁應只有一條空行"
    assert not pages[1].blank, "插入的空白頁照常編頁碼"
    msg = win.statusBar().currentMessage()
    assert "已在頁 2 之前插入空白頁" in msg and "全書" in msg, msg

    # 空白頁直接打字（Sprint 154）：點空行的落點槽位，組字 Enter 落在新頁
    win._on_pick(win._item_by_key[(0, 0)])
    assert "空白頁" in win.statusBar().currentMessage()
    win._on_key(type("K", (), {"key": lambda self: Qt.Key.Key_Backspace})())
    assert "沒有字可刪" in win.statusBar().currentMessage()
    win._ime.setText("補記")
    win._on_ime_commit()
    assert win.page.number == 2 and win.cursor is not None
    assert [c.text for c in win.page.placed[0].line.cells] == ["補", "記"]
    win.session.undo()

    # 刪掉剛插的空白頁，再一步一步 undo 回原稿
    _act(win._build_page_menu(2), "刪除此頁").trigger()
    assert len(_content(win)) == content0
    assert "已刪除頁 2" in win.statusBar().currentMessage()
    win.session.undo()
    win.session.undo()
    assert win.doc == original, "兩步 undo 應回到原稿"

    # 頁 2 之後新增：頁 2 末段若延續到頁 3 則拒收並說明，否則新頁為頁 3
    guard = win._page_edit_guard(2, "after")
    _act(win._build_page_menu(2), "在此頁之後新增空白頁").trigger()
    if guard is None:
        assert len(_content(win)) == content0 + 1
        assert win.page.number == 3
        win.session.undo()
    else:
        assert guard in win.statusBar().currentMessage()
        assert win.doc is original

    # 拒收：跨頁續段頁、裝訂補頁（說詞與 guard 單一來源）
    _act(win._build_page_menu(3), "刪除此頁").trigger()
    msg3 = win.statusBar().currentMessage()
    assert "頁 3 開頭的段落延續自前頁" in msg3 and "無法刪除" in msg3, msg3
    blank_no = next((p.number for p in win.layout_result.pages if p.blank), None)
    if blank_no is not None:
        _act(win._build_page_menu(blank_no), "刪除此頁").trigger()
        assert "裝訂補頁" in win.statusBar().currentMessage()
    assert win.doc == original, "拒收時文件不得變動"

    # ── 兩節樣張 chapter-opening 加封面：封面不可刪、封面之後可插 ──
    from cjkfolio.cover import with_cover

    win2 = EditorWindow(str(chapter_path))
    win2.session.replace_document(with_cover(win2.doc, win2.template))
    covered = win2.doc
    _act(win2._build_page_menu(1), "刪除此頁").trigger()
    assert "封面頁不能刪除" in win2.statusBar().currentMessage()
    _act(win2._build_page_menu(1), "在此頁之前插入空白頁").trigger()
    assert "封面固定在最前" in win2.statusBar().currentMessage()
    assert win2.doc is covered
    _act(win2._build_page_menu(1), "在此頁之後新增空白頁").trigger()
    pages2 = win2.layout_result.pages
    assert win2.page.number == 2 and [pl.line.cells for pl in pages2[1].placed] == [()]
    assert len(pages2) % 4 == 0, len(pages2)
    # 刪掉原本的部扉頁（現為頁 3，整節一頁）：剩封面、空白頁、內文頁
    _act(win2._build_page_menu(3), "刪除此頁").trigger()
    assert [p.master for p in _content(win2)][1:] == ["B-部扉", "A-內文版"], \
        [p.master for p in _content(win2)]

    # ── 目次頁碼自動更新（Sprint 155）：chapter-opening 兩節各宣告一條層 2 條目 ──
    from dataclasses import replace

    from cjkfolio.toc import document_with_toc

    win3 = EditorWindow(str(chapter_path))
    paras = list(win3.doc.paragraphs)
    for i in (1, 2):
        paras[i] = replace(paras[i], toc_title=paras[i].text[:6], toc_level=2)
    win3.session.replace_document(document_with_toc(
        replace(win3.doc, paragraphs=tuple(paras)), win3.template))
    with_toc = win3.doc
    numbers = [p.page_no for p in with_toc.paragraphs[1:3]]
    _act(win3._build_page_menu(1), "在此頁之後新增空白頁").trigger()
    assert [p.page_no for p in win3.doc.paragraphs[1:3]] == [
        str(int(n) + 1) for n in numbers], "目錄頁之後插頁，各條目頁碼應各加 1"
    assert "目次頁碼已更新 2 條" in win3.statusBar().currentMessage()
    _act(win3._build_page_menu(1), "更新目次頁碼").trigger()
    assert "目次 2 條頁碼不變" in win3.statusBar().currentMessage()
    win3.session.undo()
    assert win3.doc is with_toc, "插頁與目次頁碼更新應同屬一個 undo 步"

    for w in (win, win2, win3):
        w._shutdown_thumbnails()
    print("C41 附驗 刪頁／插頁：右鍵三項＋插頁跳新頁且空白頁編頁碼、可直接打字＋補頁湊回 4 的"
          "倍數＋刪頁＋兩步 undo 回原稿＋封面、裝訂補頁、跨頁續段頁拒收並說明原因"
          "＋插頁後目次頁碼同步更新、右鍵一鍵重算")
