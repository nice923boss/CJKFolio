# Pre-mortem：Sprint 72 docx 匯入（Spike 11）

日期：2026-07-17　範圍：§4.4 docx 匯入（OOXML 段落與 run 屬性解析，不依賴 Word COM）

| 題 | 回答 |
| --- | --- |
| 最可能失敗 | 標題偵測跨產生器不穩：styleId 與樣式名因語系而異（英文 Word「Heading 1」、中文 Word「標題 1」、styleId 可能是「1」「Heading1」「a1」），只比對名稱會漏抓 |
| 失敗機率 | 25%（有 outlineLvl 這條語系無關路徑可走，但需 spike 實證 python-docx 產檔的實際結構） |
| 早期訊號 | spike 探針對 python-docx 產生的 Heading 1〜3 抓不到層級，或 styles.xml 無 outlineLvl |
| 對策 | 三層偵測鏈：段落直掛 pPr/outlineLvl → 樣式鏈（含 basedOn 遞迴）outlineLvl → 樣式名 regex（heading N／標題 N）；spike 逐層驗證 |
| 放棄條件 | stdlib（zipfile＋ElementTree）解析在 spike 內走不通（如命名空間地獄、結構假設全錯） |
| 替代方案 | 產品碼改依賴 python-docx 1.2.0（本機已裝，pip 可得）；解析語意不變 |
| 預估誤差 | spike 時間盒半天；實作＋測試 1 Sprint 內 |

次要風險：

- 粗斜體 run 屬性 `w:b`／`w:i` 有「存在即真」與 `w:val="0"/"false"` 關閉兩種寫法，漏判 val 會把關閉誤判為開啟 → spike 驗兩種寫法，測試釘死。
- 引文樣式偵測（Quote／Intense Quote／引文）名稱離散 → v1 以樣式名子字串（quote／引文）判定，未命中退回內文（不沉默：CLI 列出各 kind 段數）。
- 真 Word／LibreOffice 產檔本機無工具可產 → 誠實入 GAPS（v1 以 python-docx 產檔＋手工 OOXML 邊界為驗證面）。
