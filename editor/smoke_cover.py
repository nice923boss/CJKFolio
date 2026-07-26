"""smoke C35：封面（Sprint 132；自 smoke_check.py 分檔，行數紀律慣例）。

Owner 真視窗回饋：匯入稿件後封面的位置直接就是第一頁，書該有封面可放圖片與
自加文字，頁碼從封面翻開後才算第一頁。

離屏可驗：匯入預設建封面（書名框落封面頁、內文整體後移一個版面頁）、頁碼
指示器與跳頁對話框改書頁語意（封面標「封面」、頁碼扣掉封面）、畫布書頁號位移
使封面走右頁幾何而內文首頁側別不因加封面而翻轉（回歸關鍵）、封面頁不繪頁碼、
對頁檢視封面單邊在右（實體書封面不與內頁併排）、封面上可置圖與加字（既有
自由佈局載體）。封面的視覺設計與拖放手感待 Owner 真視窗（GAPS #19 批次）。
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
    assert sum(1 for p in pages if p.blank) == 1, "11 頁內文應補 1 頁湊足 12"

    # ── 頁碼指示器與跳頁：書頁語意 ──
    win._goto_page(1)
    assert win._page_label.text() == "封面", win._page_label.text()
    # 總數含裝訂補頁（12＝11 內文＋1 補頁）：使用者要的就是「成冊那疊紙的頁數」，
    # 補頁實體上翻得到，故算頁數但不印頁碼（Sprint 144）
    win._goto_page(2)
    assert win._page_label.text() == "頁 1／12", win._page_label.text()
    win._goto_page(12)
    assert win._page_label.text() == "頁 11／12", win._page_label.text()

    # ── 側別回歸：加封面不使內文側別翻轉 ──
    # 封面書頁號 0＝偶＝右頁（右翻書封面在右）；內文首頁書頁號 1＝奇＝左頁，
    # 與無封面時的內文首頁完全相同（first_page 語意＝內文首頁的書頁碼）。
    assert is_right_page(0) and not is_right_page(1)

    # ── 對頁檢視：封面單邊在右 ──
    assert spread_pages(1, 12, cover_pages=1) == (None, 1), "封面應單邊在右"
    assert spread_pages(2, 12, cover_pages=1) == (2, None), "內文首頁（書頁1 奇）在左"
    assert spread_pages(3, 12, cover_pages=1) == (4, 3), "書頁2 右、書頁3 左"

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
