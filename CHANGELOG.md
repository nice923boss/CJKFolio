# CHANGELOG

> Phase 0（Spike 1〜5）歷程見 devlog/；自 Phase 1 產品碼進場（Sprint 6）起立此檔。

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
