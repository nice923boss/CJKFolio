"""裝訂補頁（Sprint 144）：編輯器開的文件一律視為「要裝訂成冊的書」。

Owner 需求：「假如最後一頁的頁碼並非 4 的倍數，也要增加空白頁使其成為 4 的倍數，
這樣才是正常的書冊印製紙張的數量。」實體書以一張紙對折成 4 面成帖，內文頁數非 4
的倍數就湊不成整數張紙。

宣告層級取文件（Document.sheet_pages）而非模版：補頁增減版面頁，與 Document.cover
同性質（都是「這本書的結構」，都不動網格幾何）。模版層試過並量到代價：兩份產品模版
一宣告 4，41 個單元測試的 1〜2 頁合成稿全被補成 4〜5 頁（主題與裝訂無關的頁數斷
言），故程式庫預設不補（sheet_pages=None），預設值改由本模組在編輯器入口補上。

編輯器建 EditSession 的四個入口（開啟檔案／新建空白／模版起手／組裝書冊）皆過
with_binding，故使用者既有書檔不需手動宣告即生效；檔案裡明寫 0（明說不補）則被尊重。
存檔會把生效值寫進 meta.sheet_pages，CLI 對同一檔案的輸出因此與編輯器一致。
"""
from dataclasses import replace

SHEET_PAGES = 4  # 一張紙對折一次＝4 面（真實書冊的最小裝訂單位）


def with_binding(doc):
    """未宣告裝訂補頁的文件補上預設值；已宣告者（含明說 0）原樣回傳。"""
    if doc.sheet_pages is not None:
        return doc
    return replace(doc, sheet_pages=SHEET_PAGES)
