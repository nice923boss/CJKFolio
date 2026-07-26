"""smoke C35：封面（Sprint 132；自 smoke_check.py 分檔，行數紀律慣例）。

Owner 真視窗回饋：匯入稿件後封面的位置直接就是第一頁，書該有封面可放圖片與
自加文字，頁碼從封面翻開後才算第一頁。

離屏可驗：匯入預設建封面（書名框落封面頁、內文整體後移一個版面頁）、頁碼
指示器與跳頁對話框改書頁語意（封面標「封面」、頁碼扣掉封面）、側別依紙面
（Sprint 145：封面＝紙面 1＝左頁，加封面使內文整組換面＝翻開封面書頁 1 在右，
與實體書一致）、裝訂補頁倍數含封面、封面頁不繪頁碼、對頁檢視封面單邊（闔上
的書）、封面上可置圖與加字（既有自由佈局載體）。封面的視覺設計與拖放手感待
Owner 真視窗（GAPS #19 批次）。
"""


def check_cover(EditorWindow, md_path, ROOT) -> None:
    from cjkfolio.cover import with_cover, without_cover
    from cjkfolio.primitives import is_right_page
    from editor.canvas import spread_pages

    # ── 匯入預設建封面（editor 路徑，Owner 需求） ──
    win = EditorWindow(str(ROOT / "samples" / "paiban-xiaoji-ch1.doc.json"))
    # 內文頁數一律不計裝訂補頁（Sprint 144：末尾補到 4 的倍數，見 C42）
    before = sum(1 for p in win.layout_result.pages if not p.blank)
    win._import_manuscript_dialog(str(md_path))
    doc = win.doc
    assert doc.cover == "H-封面", f"匯入未建封面：{doc.cover}"
    pages = win.layout_result.pages
    assert win.layout_result.cover_pages == 1
    assert pages[0].master == "H-封面" and pages[0].placed == (), "封面頁應為空流排頁"
    assert doc.text_frames and doc.text_frames[0].page == 1, "書名框應落封面頁"
    msg = win.statusBar().currentMessage()
    assert "封面 1 頁＋內文" in msg, msg  # 頁數分開報（總數會與頁碼對不上）

    # 內文分頁不因封面改變（封面只多一頁，內容逐頁不動）
    body_pages = [p for p in pages[1:] if not p.blank]
    assert len(body_pages) == 11, f"內文應 11 頁，得 {len(body_pages)}"
    assert before == 11, before
    # 倍數含封面（Sprint 145）：1 封面＋11 內文＝12 已是 4 的倍數，補 0 頁
    assert sum(1 for p in pages if p.blank) == 0, "12 總頁已是 4 的倍數不應補頁"
    assert len(pages) == 12 and len(pages) % 4 == 0, len(pages)

    # ── 頁碼指示器與跳頁：書頁語意 ──
    win._goto_page(1)
    assert win._page_label.text() == "封面", win._page_label.text()
    # 總數含裝訂補頁且倍數含封面（Sprint 145）：1 封面＋11 內文＝12 已是 4 的
    # 倍數，補 0 頁（Sprint 144 只湊內文那疊係誤解：封面就是第一張紙的第一面）
    win._goto_page(2)
    assert win._page_label.text() == "頁 1／11", win._page_label.text()
    win._goto_page(12)
    assert win._page_label.text() == "頁 11／11", win._page_label.text()

    # ── 側別依紙面（Sprint 145）：加封面使內文整組換面，與實體書一致 ──
    # 封面＝紙面 1（奇＝左半、書脊在右）；翻開封面即見紙面 2（書頁 1）在右、
    # 紙面 3（書頁 2）在左（Owner：「第二頁應該是要在翻開後的右邊才正確」）。
    assert not is_right_page(1) and is_right_page(2)

    # ── 對頁檢視：紙面配對與封面無關；頭尾單邊＝闔上的書 ──
    assert spread_pages(1, 12) == (1, None), "封面＝紙面1 單邊（闔上的書）"
    assert spread_pages(2, 12) == (3, 2), "翻開封面：紙面2（書頁1）右、紙面3 左"
    assert spread_pages(12, 12) == (None, 12), "末偶紙面單邊＝翻完闔上書的封底"

    # ── 封面頁不繪頁碼（底圖層：footer 未餵給 renderer） ──
    win._goto_page(1)
    win._rebuild()  # 封面頁重繪不炸（空 placed 頁走兩後端 body 空迴圈）

    # ── 移除與再建封面（編輯層可逆） ──
    bare = without_cover(doc)
    assert bare.cover is None and not bare.text_frames  # 書名框隨封面移除
    again = with_cover(bare, win.template, title="重建書名")
    assert again.cover == "H-封面" and again.text_frames[0].text == "重建書名"

    win._shutdown_thumbnails()
    print(
        "C35 封面：匯入預設建封面（書名框落封面頁、內文 11 頁分頁不變、狀態列"
        "封面與內文頁數分報）＋頁碼指示器書頁語意（封面標『封面』、內文頁 1〜11）"
        "＋封面書頁號 0 走右頁而內文側別不翻轉＋對頁檢視封面單邊在右"
        "＋封面頁重繪不炸＋移除與再建封面可逆"
    )
