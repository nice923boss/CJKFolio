"""smoke C25：空白起始（Sprint 123；Sprint 140 自 smoke_check.py 原樣分檔，行數紀律）。

回應 Owner 真視窗回饋：開窗即未命名空白文件（空紙面，非樣張），輸入欄第一字即成頁。

離屏可驗：未命名標題、空紙面（page None 但畫得出紙）、開場引導匯入、空白時翻頁
據實提示不炸、第一字落段 0 字位 0 且游標跟隨、第二字沿游標接續、兩步 undo 回空
紙面、匯入後標題跟隨文件名。純函式面另有 tests/test_blank_start.py（Gate 4）。
"""


def check_blank(EditorWindow, ROOT) -> None:
    win25 = EditorWindow(None)
    assert "未命名" in win25.windowTitle() and "骨架" not in win25.windowTitle(), \
        f"標題失準：{win25.windowTitle()}"
    assert win25.page is None, "空白文件應為空紙面（page None）"
    assert len(win25.scene.items()) > 0, "空紙面未畫出"
    assert "匯入稿件" in win25.statusBar().currentMessage(), "開場未引導匯入"
    win25._turn_page(1)  # 空白時翻頁不炸、據實提示
    assert "尚無頁面" in win25.statusBar().currentMessage()
    win25._ime.setText("測")
    win25._on_ime_commit()  # 第一字：空白直接落段 0 字位 0
    assert win25.doc.paragraphs[0].text == "測"
    assert win25.page is not None and win25.page.number == 1
    assert win25.cursor is not None, "第一字後游標未跟隨"
    win25._ime.setText("試")
    win25._on_ime_commit()  # 第二字：沿游標接續，不需再點字格
    assert win25.doc.paragraphs[0].text == "測試"
    win25._on_undo()
    win25._on_undo()
    assert win25.doc.paragraphs[0].text == "" and win25.page is None, "undo 未回到空紙面"
    win25._import_manuscript_dialog(str(ROOT / "samples" / "jiejiao-manxing-ch1.md"))
    assert win25.page is not None and "jiejiao-manxing-ch1" in win25.windowTitle(), \
        "匯入後標題未跟隨文件名"
    win25._shutdown_thumbnails()
    print(
        "C25 空白起始：未命名標題、空紙面、空白翻頁據實提示、輸入欄第一字即成頁"
        "＋第二字沿游標接續、兩步 undo 回空紙面、匯入後標題跟文件名"
    )
