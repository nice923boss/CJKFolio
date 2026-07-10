# CHANGELOG

> Phase 0（Spike 1〜5）歷程見 devlog/；自 Phase 1 產品碼進場（Sprint 6）起立此檔。

## v0.4.0（2026-07-11，Sprint 9）字元樣式 run 模型＋md 行內強調

### 新增

- [實作] document@2：段內 run（text＋char_style），Paragraph 正規化不變式（text＝runs 串接）；@1 相容照載、@1 帶 runs 明確拒絕；save 一律寫 @2。
- [實作] 引擎與雙後端 run 支援：Cell 帶字元樣式、PNG／PDF per-cell 覆寫字型與級數（字槽網格仍依段落樣式）、layout 與 CLI 對未知字元樣式快速失敗。
- [實作] md 行內強調：**strong**／*em* 對映模版 md_inline_mapping（v1 皆映內文強調-明體W9）；相鄰同樣式合併、未閉合保留字面。
- [實作] 抽取工具：body 欄明體 W9 強調 span 標 **…**；控制字元（Cc）源頭剔除並列計數。
- 測試 83 → 96（+13）。

### 已知限制（詳 GAPS.md）

- md 行內標記 v1 不支援嵌套；em 與 strong 同映強調樣式（原書無斜體慣例）。
- 發言人標籤自動指派（訪談章黑體標籤）屬 Phase 3 AI 指派範圍。
- X-1a 收尾（#15）、鏡像依書頁號（#16）、PNG 缺字警告（#17）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機，重生成）：強調頁（書頁 25）page-006.png 與 pdf-render-strong.png，真書整句強調＋對談發言標籤以宋 Heavy 呈現，已 AI 目檢雙後端一致，待 Owner 過目。

## v0.3.0（2026-07-11，Sprint 8）PDF 寫出層第一片

### 新增

- [實作] PDF 寫出層（cjkfolio/pdf_writer）：自寫 PDF 1.4，盒框依 PLAN §9（MediaBox 154×216mm／TrimBox 148×210 置中／BleedBox＝MediaBox）、文字 DeviceCMYK 單 K92、右翻閱讀方向（/Direction /R2L）、逐字顯式 Tm（禁則與斷行在排版層烘焙）。
- [實作] 字型子集嵌入：CFF（思源）不保留 GID、原 CID 走 charset 對映（探針實證小 30 倍）；TTF（辰宇／粉圓）retain_gids＋CIDToGIDMap /Identity；皆帶 ToUnicode（可抽取）與 CIDSet（X-1a 要求）；子集前綴可重現。
- [實作] 共用字形佈局層（cjkfolio/placement）：與 PNG 渲染同一套 pen 數學（直排字槽／縱中橫／旋轉拉丁／頁腳字條）。
- [實作] CLI export-pdf：--page（單頁完稿）／--first-page／--no-footer，回報禁則與每款子集大小。
- 測試 74 → 83（+9）。

### 變更

- engine.normalize 剝除控制字元（Cc）：真章 md 素材在發言標籤後殘留 U+0007 的實測缺陷修正。
- 缺字（gid 0）於 PDF 匯出改為警告＋.notdef 輸出，不沉默、不中斷。

### 已知限制（詳 GAPS.md）

- 尚非完整 PDF/X-1a：缺 OutputIntent／XMP 識別／preflight 全綠驗證（#15），不得對外宣稱 X-1a。
- 鏡像與頁腳奇偶以版面頁號判定，偶數起頁（--first-page 20）側別與真書相反（#16，PNG/PDF 一致）。
- PNG 渲染缺字仍沉默（#17）；齊行（#9）、橫排（#13）、行內強調 run 模型未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/chapter1.pdf（本機，23 頁）＋ chapter1-p1.pdf（單頁完稿）：pdffonts 六款全綠、PyMuPDF 渲染 pdf-render-001/002.png 已 AI 目檢，待 Owner 以 PDF 閱讀器實開過目（右翻方向、選字複製、縮放銳利度）。

## v0.2.0（2026-07-11，Sprint 7）md 匯入＋主版頁腳＋字型組

### 新增

- [實作] Markdown 匯入（import-md）：block 級標題／引文／清單直接對映模版樣式（md_mapping），§4.4 設計修正 1 落地。
- [實作] 主版頁腳與書眉：頁碼（全頁）＋書名書眉（奇數頁），foot_elements 實測座標、奇偶頁鏡像；CLI --first-page／--no-footer。
- [實作] 字型組入庫：思源黑體 TC Medium/Bold、辰宇落雁體、jf open 粉圓（皆驗 GSUB vert；GAPS #12 縮至全字庫兩款）。
- 抽取工具 --format md（級數→標題層級、仿宋→引文）；手寫／裝飾字型不入正文流。
- 測試 61 → 74（+13）。

### 變更

- 渲染改以 FT_LOAD_NO_HINTING 載入字形（修辰宇／粉圓 TTF hinting bytecode 使 FreeType 拋錯；印刷級柵格不需 hinting）。

### 已知限制（詳 GAPS.md）

- 行內強調需字元樣式 run 模型（document@2），未實作；左頁章節副標書眉與 Case 編號待章節結構。
- 楷書／仿宋樣式仍 fallback（#12）；齊行未實作（#9）；橫排未支援（#13）。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機）：第一章 md 樣式化 23 頁（章名 Heavy／個案大標黑體／小標黑體／內文宋體＋頁腳），page-001／002 已 AI 目檢，待 Owner 過目。

## v0.1.0（2026-07-10，Sprint 6）Phase 1 第一片：核心排版管線

### 新增

- [實作] cjkfolio 套件：文件模型（cjkfolio/document@1）、三層樣式讀取（cjkfolio/template@1）、字型解析（fallback＋警告）、直排引擎（斷行／禁則／縱中橫，自 Spike 1 產品化）、樣式驅動流排、單頁 A5 PNG 渲染（鏡像版心）、txt 匯入、CLI（import-txt／render）。
- [實作] 《內在整理》起始模版 templates/neizai-zhengli.json：15 段落樣式＋9 字元樣式＋7 主版，參數取自全書 (font,size) 掃描（A 級）。
- [實作] tools：全書樣式掃描、章節抽取（輸出僅本機 assets/reference/，版權紅線）。
- 測試新增 46 項（合計 61），typecheck 0 error。

### 變更

- 產品管線字型：PMingLiU → 思源宋體 TC（GAPS #3 關閉）。
- 基線指令擴充至 cjkfolio 與 tools（PLAN §10 決議）。

### 已知限制（詳 GAPS.md）

- 字型組僅思源宋體 TC 兩檔，黑體／楷書／仿宋／手寫樣式 fallback 並警告（#12）。
- B〜G 主版版心承 A 未逐頁實測；橫排（版權頁）渲染未支援，遇之明確報錯（#13）。
- 齊行與約物擠壓未實作，等距網格（#9）；頁腳三件組與書眉未進場。
- txt 抽取 v1 對談段合併為單段（本機驗證素材限制，#14）。

### 待 Owner 真實素材驗收

- out/chapter1/（本機）：第一章 79 段 5,408 字 → 23 頁 A5 PNG，禁則 0 違規；page-001／002 已 AI 目檢（網格、鏡像、標點、縮排），待 Owner 過目。
- GAPS #10（Spike 1 對比圖 spread_comparison.png）仍待 Owner 抽檢，與本項可一併看。
