# Sprint #7（2026-07-11）md 匯入＋主版頁腳＋字型組入庫，已完成

**範圍**：Markdown 匯入（標題層級直接對映樣式，§4.4 設計修正 1）、主版頁腳與書眉（A-內文版）、字型組補庫（GAPS #12：思源黑體 TC 優先＋辰宇落雁體＋jf open 粉圓）、第一章 md 樣式化實排。

**完成**：

- ✅ 字型組入庫 [實作]（25fc36c）：思源黑體 TC Medium/Bold（adobe-fonts 2.004R）、辰宇落雁體 v2.0、jf open 粉圓 v2.1，fontTools 驗四款皆含 GSUB vert；FontRegistry 對映更新；FONTS.md 重現指令與授權補齊（LICENSE-SourceHanSansTC.txt 入 repo）。GAPS #12 縮至全字庫正楷體＋正宋體兩款。
- ✅ md 匯入 [實作]（25fc36c）：cjkfolio/md_import（block 級：#〜###### 標題、> 引文合併、清單項各自成段、空行段落、CJK 併行）；模版新增 md_mapping（h1→章名大標、h2→個案大標、h3→章節小標、blockquote→引文-仿宋語錄、paragraph→內文）；CLI 新增 import-md。行內強調（run 模型）明確列後續 Sprint。
- ✅ 主版頁腳 [實作]（25fc36c）：styles 新增 FooterItem（style／source／baseline_from_top_pt／outer_offset_pt／pages），A-內文版 footer 取 calibration foot_elements 實測座標（頁碼外緣內推 36.8pt≈13mm、基線 530.43pt；書眉齊版心外緣 59.53pt、基線 529.15pt）；渲染器水平字條錨定書口側、奇偶鏡像；CLI 加 --first-page／--no-footer。左頁章節副標與個案 Case 編號待章節結構（模版 note 註記）。
- ✅ 抽取工具 md 模式 [實作]（25fc36c）：--format md（級數→標題層級：≥20→#、≥14.5→##、其餘標題帶→###；仿宋欄→>）；手寫／裝飾字型（手札體、辰宇、Pepita、GillSans）固定不入正文流並於輸出摘要註明。
- ✅ 第一章 md 樣式化實排 [實作]（本機，不入 repo）：chapter1.md 79 段 → import-md 對映 4 種樣式 → 23 頁 PNG（--first-page 20），禁則 0 違規，6 款字型（含黑體 Medium/Bold、書眉辰宇、頁碼粉圓），字重 fallback（明體 W7→Heavy）誠實列警告。

**測試成長**：61 → 74（+13：md_import 7、fonts 4（含 2 項改為以全字庫驗 fallback）、styles 2、footer 渲染 2），0 失敗 0 退步。

**驗證**：
- typecheck：python -m py_compile spikes/spike1-vertical-core/\*.py cjkfolio/\*.py tools/\*.py → EXIT_CODE=0
- test：74 passed / 0 failed（python -m pytest spikes tests -q）
- 真實素材驗收（R5）：Read out/chapter1-md/page-001.png（章名思源宋 Heavy 21.9pt、個案標題思源黑 Medium 17.9pt、內文宋 Regular 同頁；右下頁腳＝辰宇書眉「內在整理」＋粉圓頁碼 20，齊書口側）與 page-002.png（頁碼 21 鏡像左下、書眉僅奇數頁）目檢通過；頁腳帶著墨與鏡像另有單元測試雙重驗證（Gate 4）。
- 除錯紀錄：辰宇／粉圓 TTF 的 hinting bytecode 使 FreeType 拋 too many function definitions（載入 glyph 即錯）；以 FT_LOAD_NO_HINTING 修正（印刷級柵格不需 hinting），入 §10 決議。

**代決事項（記入 PLAN §10）**：頁腳 v1 規格與鏡像錨定、md_mapping 入模版、FT_LOAD_NO_HINTING、抽取工具非正文流字型清單。

**下個 Sprint 預定範圍**：字元樣式 run 模型（document@2：段內 run＋字元樣式渲染，md 行內強調對映內文強調-明體W9），或 PDF 寫出層第一片（單頁 PDF、字型子集嵌入，向 Phase 1 DoD 的 PDF/X-1a 推進）；建議先 PDF 寫出層（DoD 關鍵路徑）。齊行與約物擠壓（GAPS #9）、全字庫字型（#12）列後。
