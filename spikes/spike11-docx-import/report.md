# Spike 11 報告：docx（OOXML）匯入可行性

日期：2026-07-17　時間盒：半天（實際約 1 小時）　狀態：**通過**

## 成功標準與結果

| 標準 | 結果 |
| --- | --- |
| stdlib（zipfile＋ElementTree）解析 docx 段落序與 run | ✅ 8 段全數依序解出，run 文字完整（含全形空白 U+3000） |
| 標題層級偵測不依賴語系名稱 | ✅ 三層鏈：段落直掛 pPr/outlineLvl → pStyle 樣式鏈（含 basedOn 遞迴）outlineLvl → 樣式名 fallback；python-docx 產檔走第二層命中（Heading1 樣式定義帶 outlineLvl='0'） |
| 粗斜體 run 屬性解析 | ✅ `<w:b/>` 存在即真；粗斜並用 (True, True) 正常；`w:val="0"/"false"` 關閉寫法由測試層手工 XML 釘 |
| 引文樣式偵測 | ✅ Quote 樣式無 outlineLvl，名稱（name='Quote'）子字串偵測可行 |
| 空段辨識 | ✅ runs=[] 可跳過（md blocks 同構） |

## 一手數據（probe_ooxml.py，python-docx 1.2.0 產檔）

- styles.xml：`Heading1..9` → outlineLvl '0'..'8'、basedOn Normal；`Quote` 無 outlineLvl。
- **關鍵邊界**：`TOCHeading` 帶 outlineLvl='9'。OOXML outlineLvl 有效標題層級為 0〜8，**9＝正文（無層級）**，偵測必須排除 9，否則目錄標題誤判為標題。
- 段落 pPr 不直掛 outlineLvl（python-docx 產檔），層級全靠樣式鏈；直掛路徑（Word 手動設定大綱層級）由測試層手工 XML 覆蓋。
- run 文字在 `w:t`（可多個）；hyperlink 內 run 為 `w:p` 的孫節點，需以 `.iter()` 深走否則漏字。

## 設計定案（進實作）

- 產品碼 `cjkfolio/docx_import.py` **零新依賴**（stdlib zipfile＋xml.etree.ElementTree），與自寫 PDF 層同哲學。
- 結構鍵復用 md 匯入：outlineLvl 0..8 → h1..h9、引文 → blockquote、其餘 → paragraph；對映走模版既有 `md_mapping`／`md_inline_mapping`（h4+ 未對映自然 fallback 內文，與 md 行為一致）＝零新模版 schema。
- 粗體 → strong、斜體 → em、粗斜並用 → strong（md v1 不嵌套同構）。
- python-docx 僅作**測試素材產生器**（Gate 4 獨立路徑：python-docx 寫、stdlib 讀），非產品依賴。

## 限制（誠實記錄，入 GAPS）

- 真 Word（中文版「標題 1」）與 LibreOffice 產檔本機無工具可產，名稱 fallback 層無真檔實證（以手工 XML 模擬）。
- v1 不處理：表格、圖片、註腳、追蹤修訂（w:ins/w:del）、段內強制換行（w:br）、tab。
