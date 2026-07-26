"""smoke C43：裝訂補頁（Sprint 144；分檔於 editor/，行數紀律慣例）。

Owner 回饋：「假如最後一頁的頁碼並非 4 的倍數，也要增加空白頁使其成為 4 的倍數，
這樣才是正常的書冊印製紙張的數量。」補頁由 layout_document 依 doc.sheet_pages 產生，
編輯器入口一律補上預設值 4（editor.book_binding.with_binding），故既有書檔開起來即生效。

離屏可驗：真樣張開檔即補足（11 → 12 頁，末頁 blank）、補頁進頁面面板與頁碼指示器
（成冊那疊紙的頁數）、跳到補頁重繪不炸且無任何可點字格、補頁底圖全白（畫布層獨立於
tests/test_sheet_padding.py 的 render 後端驗證）、存檔把生效值寫進 meta（CLI 產出同步）、
使用者明說 sheet_pages=0 者開檔不被預設值蓋回去。

補頁的視覺（面板縮圖是否一看就知道是補頁）待 Owner 真視窗（GAPS #19 批次）。
"""
import json
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QGraphicsPixmapItem

from cjkfolio.document import document_to_dict


def check_sheet_padding(EditorWindow, doc_path) -> None:
    win = EditorWindow(str(doc_path))  # paiban-xiaoji-ch1 11 頁真樣張
    pages = win.layout_result.pages
    body = [p for p in pages if not p.blank]
    blanks = [p for p in pages if p.blank]
    assert len(body) == 11 and len(blanks) == 1, f"應 11 內文＋1 補頁，得 {len(pages)}"
    assert len(pages) % 4 == 0, f"總頁數應為 4 的倍數，得 {len(pages)}"
    assert blanks[0].number == len(pages), "補頁應在最末"
    assert blanks[0].placed == () and blanks[0].master == body[-1].master, \
        "補頁應為空流排頁並承末頁主版"

    # 面板與指示器算進補頁（使用者要的是「成冊那疊紙的頁數」）
    assert win._page_panel.count() == len(pages)
    assert win._page_label.text() == f"頁 1／{len(pages)}", win._page_label.text()

    # 跳到補頁：重繪不炸、有底圖、無任何可點字格（空 placed）
    win._goto_page(blanks[0].number)
    assert win.page.number == blanks[0].number and win.page.blank
    assert win._item_by_key == {}, "補頁不該有可點字格"
    bases = [it for it in win.scene.items() if isinstance(it, QGraphicsPixmapItem)]
    assert len(bases) == 1, f"補頁應一張底圖，得 {len(bases)}"

    # 補頁底圖全白（畫布層：頁碼、書眉、天頭虛線皆不繪）
    image = bases[0].pixmap().toImage()
    assert not image.isNull() and image.width() > 100, "補頁底圖未渲染"
    corners = [image.pixelColor(x, y)
               for x in (1, image.width() - 2) for y in (1, image.height() - 2)]
    assert all(c.red() > 250 and c.green() > 250 and c.blue() > 250 for c in corners), \
        f"補頁底圖四角非紙白：{[c.name() for c in corners]}"
    grays = {image.pixelColor(x, y).red()
             for x in range(0, image.width(), 7) for y in range(0, image.height(), 7)}
    assert grays == {255}, f"補頁底圖有非白像素（取樣灰階 {sorted(grays)[:5]}）"

    # 存檔把生效值寫進 meta：同一檔案交給 CLI 也補一樣的頁（設定不只活在編輯器裡）
    assert document_to_dict(win.doc)["meta"]["sheet_pages"] == 4

    # 使用者明說不補（sheet_pages=0）：開檔不被預設值蓋回去
    raw = json.loads(Path(doc_path).read_text(encoding="utf-8"))
    raw["meta"]["sheet_pages"] = 0
    with tempfile.TemporaryDirectory() as td:
        zero_path = Path(td) / "不補頁.doc.json"
        zero_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        win0 = EditorWindow(str(zero_path))
        try:
            assert win0.doc.sheet_pages == 0, "明說 0 被預設值蓋掉"
            assert len(win0.layout_result.pages) == 11, \
                f"明說不補卻補了（{len(win0.layout_result.pages)} 頁）"
        finally:  # 縮圖執行緒以 doc 所在目錄為基準，須在暫存目錄消失前收工
            win0._shutdown_thumbnails()

    win._shutdown_thumbnails()  # 退出安全：縮圖執行緒收工（closeEvent 同路徑）
    print(
        "C43 裝訂補頁：真樣張開檔即 11 → 12 頁（末頁空流排頁、承末頁主版、總頁數 4 的"
        "倍數）＋面板與指示器算進補頁＋跳到補頁重繪不炸且無可點字格＋補頁底圖全白"
        "（頁碼書眉皆不繪）＋存檔把 sheet_pages 寫進 meta＋明說 0 者開檔不被蓋回"
    )
