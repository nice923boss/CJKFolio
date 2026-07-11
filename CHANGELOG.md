# CHANGELOG

> Phase 0（Spike 1〜5）歷程見 devlog/；自 Phase 1 產品碼進場（Sprint 6）起立此檔。

## v0.13.0（2026-07-11，Sprint 18）文件 provenance 載體（Phase 2 首項工程）

### 新增

- [實作] engine：`Cell.span`（文件段 text 半開區間）＋`normalize_with_offsets`（正規化＋原索引表：Cc 剝除位移精確映射、表現形 1:1 不動索引；`normalize` 改由其推導，單一事實來源）；`tokenize` 加 `offsets` 參數（None＝輸入座標 identity，舊 API 相容）；`cells_from_runs` 依 document@2 串接不變式帶 run base 位移。
- [實作] engine／layout：`ParagraphSpec.para_idx`＋`PlacedLine.para_idx`（純載體，layout 建 spec 時掛段索引，與 page_no 同模式，不影響斷行禁則齊行與兩後端）。
- 畫布點選 → 文件游標資料鏈補齊：hit-test 幾何鍵 (page, placed_idx, cell_idx) → `PlacedLine.para_idx`＋`Cell.span` → 文件 (段, 字元區間)（Spike 10 介面缺口關閉）。
- 測試 164 → 173（+9：normalize 映射 2、tokenize span 2、runs base 1、flow para_idx 2、layout 全文件 round-trip 直排＋橫排 2）。

### 待 Owner 真實素材驗收

- 本機驗證（重現：層層皆單元測試釘死；一次性掃描腳本已依紀律刪除）：第一章 22 頁 5,361 cells、samples/toc.doc.json 64 cells、samples/cip-copyright.doc.json 65 cells，round-trip（doc 段 text[span] 正規化後 == cell.text）全 0 錯、placed 行 para_idx 全數帶值。

## v0.12.0（2026-07-11，Sprint 17）Phase 2 畫布架構前置 spike（風險前置）

### 新增

- [Spike] spikes/spike10-canvas-sync/：premortem（R6 七問）＋探針 probe_canvas_sync.py（S1〜S5）＋report.md。PySide6 6.11.0 offscreen 雙層畫布：底圖層（既有 PNG 渲染後端輸出 → QGraphicsPixmapItem）＋互動層（layout 幾何同源透明字格 QGraphicsRectItem，復用 line_axis_x_pt／style_advance_pt／line_justified_advance，不另立幾何）。
- 一手數據（第一章 22 頁本機素材）：編輯回路中位 37.2ms@150dpi（重排 7.0／渲染 25.8／pixmap 1.9／互動層 2.6）、26.9ms@96dpi；全頁字格中心 hit-test 反查 214/214；22 頁 5,361 item 建立 52ms、hit-test 中位 0.90ms；重排 7.0ms 與 Spike 3 的 7.67ms 獨立互證。

### 決策

- Owner 指示「先挑最複雜的架構先做」：風險前置，Phase 2 最高風險架構件（畫布 ↔ 排版核心同步，PLAN §7 中高風險「長尾工程」）以最小 spike 先驗，不直接開蓋編輯器（R2）。
- Phase 2 首項工程定案：PlacedLine／Cell 掛文件 provenance（para_idx／char offset），供畫布點選 → 文件游標映射（Spike 10 顯式暴露的介面缺口）。
- spike 探針不入 pytest 基線（避免基線硬依賴 PySide6 GUI 套件）；測試 164 → 164（0 退步）。

### 已知限制（詳 GAPS.md #19）

- IME 直排輸入／拖曳／選取 UI 未驗（offscreen 限制），Phase 2 開工首個 Sprint 以真視窗 demo 由 Owner 人工實測。
- Phase 2 正式技術棧（含 Skia 與否、C++／Python 分層）於 Phase 2 開工定案；本 spike 供畫布層一手數據，非正式開工。

### 待 Owner 真實素材驗收

- spikes/spike10-canvas-sync/out/page1_overlay.png（本機，重生成：python spikes/spike10-canvas-sync/probe_canvas_sync.py）：4 個高亮字格（章名首格／內文中格／大標格／行末標點格）紅框黃底與底圖字形對位，已 Read 親驗（含 zoom_last.png 放大驗直排「】」vert 形貼格頂正確）；待 Owner 過目。

## v0.11.0（2026-07-11，Sprint 16）目錄條目頁碼＋引導線

### 新增

- [實作] 文件模型：Paragraph.page_no（目錄條目頁碼，選配數字字串，document@2 相容擴充：無欄位照載、save 有值才寫、非數字快速失敗）；engine ParagraphSpec／PlacedLine 純載體傳遞（只掛段末行，不影響斷行禁則）。
- [實作] 樣式：TocSpec（頁碼字元樣式＋底錨＋引導線寬/gap/cmyk）＋MasterPage.toc；模版跨引用驗證（toc.page_no_style 不存在即拒）。
- [實作] layout：TocEntryMark＋LayoutResult.toc_marks（頁碼頂＝底錨−位數×字距、線起＝標題末＋gap、線終＝頁碼頂−gap；標題頁碼重疊列 violations 不畫線；帶 page_no 落在無 toc 主版快速失敗）。
- [實作] 兩後端：render _draw_toc_marks（引導線復用 StrokeLine 實線＋頁碼 tcy 逐位直立）；pdf_writer _toc_marks（stroke_line 無 dash K92＋tcy_placements）；幾何同源、parity 單元測試釘死。
- [實作] D-目錄 toc 配置（底錨 490pt、線寬 0.1pt、gap 2pt 皆 p003 一手量測；頁碼樣式「頁碼數字-GillSans」對映粉圓）；samples/toc.doc.json 條目加自擬頁碼。
- 測試 151 → 164（+13：document 2、styles 3、engine 1、layout 2、render 2、pdf 3）。

### 紀錄

- 粉圓首次進 PDF 子集：fontTools 丟棄 Apple meta table（stderr 提示「meta NOT subset; dropped」，非渲染必要表，嵌入合法性不受影響）。

### 已知限制（詳 GAPS.md #13）

- 目錄頁型剩：篇名嵌線斷開、條目縮退、目錄「章名條目黑 W5」樣式層補充。
- 頁碼字級用頁碼字元樣式 8pt（p003 實測 Times 9pt，同構不同值）。

### 待 Owner 真實素材驗收

- out/toc/（本機，重生成）：page-001.png 四條目引導線＋頁碼 17／63／109／155 底一列對齊，已 Read 親驗與 p003 設計語言（標題→線→頁碼底對齊）一致；toc.pdf preflight 12/12、PyMuPDF 獨立解析 4 引導線 y 起訖與幾何手推一致，待 Owner 過目條目視覺與參考書風格相符度。

## v0.10.0（2026-07-11，Sprint 15）目錄水平虛線向量原件

### 新增

- [實作] 虛線原件：primitives 加 StrokeLine（端點＋cmyk＋線寬＋dash on/off，on=0 實線）與 toc_rule_line（貫穿頁寬＋兩側出血延伸 3mm，§9 貼邊全出）；styles 加 RuleSpec／KNOWN_RULE_KINDS／MasterPage.rule（未知 kind／壞 cmyk／缺 y 快速失敗）。
- [實作] render：_draw_stroke_line（PIL 分段 dash，灰值 255×(1−k) 只取 k，灰階預覽限制）；pdf_writer：_Content.stroke_line（原生 `[ on off ] 0 d` dash 算符＋灰 `K` 描邊，獨立 q…Q 置 BT 前，spike8 實證狀態不外洩）。兩後端 gate＝vertical and master.rule（toc-rule 為直排目錄原件）、幾何同源集中 toc_rule_line。
- [實作] D-目錄主版 rule（y 122.46pt、1.0pt、dash [3 2]、灰 K57，皆參考書 p003 一手量測參數；量測參數入模版依 Sprint 7 頁腳先例）；samples/toc.doc.json 自擬目錄樣張。
- 測試 139 → 151（+12：primitives 2、styles 5、render 2、pdf 3）。

### 變更

- D-目錄天頭 32.49 → 47.63mm（條目內容起點 135pt 實測；內容一律在虛線之下，修正首輪樣張文字穿線）。

### 決策

- 部扉「雙線菱形框」規則化不做：p069 實測為手繪向量（單 draw 608 段不規則路徑）＝美術資產（PLAN §8 不生成美術），待使用者置入向量資產機制。

### 已知限制（詳 GAPS.md #13）

- 目錄頁型未實作：篇名嵌線斷開、條目縮退、垂直引導線、直排數字頁碼；虛線 v1 全頁寬貫穿。
- 目錄條目樣式（全字庫正楷體）與部名 bold 仍 fallback 並警告（GAPS #12）。

### 待 Owner 真實素材驗收

- out/toc/（本機）：page-001.png（300dpi）虛線橫貫整頁寬、斷續均勻、部名＋4 條目在虛線下，已 Read 親驗；toc.pdf preflight 12/12、內容流 m/l 座標與幾何助手完全一致、PyMuPDF 獨立回報 dashes='[ 3 2 ] 0'，待 Owner 過目虛線視覺與參考書 p003 風格相符度。

## v0.9.0（2026-07-11，Sprint 14）CIP 細框向量原件（補記）

> 本段為 Sprint 15 收尾時補記（Sprint 14 commit fe525ee 漏更新 CHANGELOG，R7 落差不沉默；內容取自 devlog/2026-07-11-sprint14-cip-frame.md）。

### 新增

- [實作] 向量原件層：新模組 cjkfolio/primitives（StrokeRect＋cip_frame_rect，與 placement 同層、兩後端同源）；styles 加 FrameSpec／KNOWN_FRAME_KINDS／MasterPage.frame。
- [實作] render：_draw_stroke_rect（PIL "L" outline=0）；pdf_writer：_Content.prologue＋stroke_rect（DeviceCMYK K 描邊、獨立 q…Q 置於 BT／ET 外）。gate＝not vertical and master.frame（cip-box 為橫排原件）。
- [實作] F-版權頁主版 cip-box 框（純黑 0.5pt、pad 6pt，全自擬，紅線 p178 不入 repo）。
- 測試 127 → 139（+12）。

### 已知限制（詳 GAPS.md #13）

- F 真實版心（p178）未量測；B〜G 其他扉頁佈局未動。

## v0.8.0（2026-07-11，Sprint 13）橫排版面軸（補記）

> 本段為 Sprint 15 收尾時補記（Sprint 13 commit 27e6829 漏更新 CHANGELOG，R7 落差不沉默；內容取自 devlog/2026-07-11-sprint13-horizontal.md）。

### 新增

- [實作] 橫排 horizontal-tb 版面軸貫通四層：engine（方向感知 tokenize，橫排整串 ascii 成 latin run、不縱中橫、不切碎 ISBN）／layout（page_is_vertical 由樣式判頁面單一方向，混用與未知模式快速失敗；橫排短行不齊行）／render（horizontal_left_x_pt／horizontal_baseline_y_pt／_draw_horizontal_cell）／pdf_writer（水平 Tm）。兩後端幾何同源集中 placement horizontal_cell_advance_pt。
- [實作] F-版權頁 grid 改自擬橫排幾何（8pt CIP、字距 8.4pt、行距 14pt）；samples/cip-copyright.doc.json 自擬 CIP 樣張。
- 測試 115 → 127（+12）。

### 已知限制（詳 GAPS.md #13）

- F-版權頁真實版心（p178）為自擬；橫排「機制」與「參考書逐點版心」分離。

## v0.7.0（2026-07-11，Sprint 12）鏡像依書頁號＋PNG 缺字警告

### 新增

- [實作] PNG 缺字警告（GAPS #17）：render 四路徑（cjk／縱中橫／旋轉拉丁／頁腳）偵測 gid 0，回報缺字來源字元，PageRenderer.notdef_warnings 訊息格式與 pdf_writer 一致，經 RenderResult.font_warnings 由 CLI render 列印（不沉默）。
- 測試 112 → 115（+3：書頁鏡像 PNG／PDF 兩後端＋PNG 缺字警告）。

### 變更

- [實作] 鏡像依書頁號（GAPS #16）：頁面鏡像（行軸書口側）與頁腳奇偶改依書頁號（＝版面頁號＋first_page−1），render 與 pdf_writer 兩後端同源；first_page=1 預設向後相容，版面頁號續作檔名與 --page 選頁鍵。既有 footer 與 page-selection 奇偶頁測試同步翻轉。
- CLI --first-page 說明更新為「頁腳與鏡像奇偶依此」。

### 已知限制（詳 GAPS.md）

- 缺字偵測未統一 placement 層（render 自有塑形迴圈，外科手術範圍）；渲染後端統一時再併。
- 橫排（#13，版權頁-CIP）、斷行逐行一致率比對（Owner 抽檢）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機，--first-page 20 重生成 22 頁）：page-001.png（書頁 20 偶＝左頁）頁碼書口左、無書眉；page-002.png（書頁 21 奇＝右頁）頁碼書口右＋書眉「內在整理」，已 Read 親驗與真書右翻一致；chapter1.pdf preflight 12/12、pdffonts 六款全綠不退步，待 Owner 過目確認左右頁側別與真書鏡像相符。

## v0.6.0（2026-07-11，Sprint 11）齊行與禁則擠入

### 新增

- [實作] 齊行（justification）：非段末行行首行尾雙錨定，內容字距均勻縮放（±1 槽 ≈ ±0.4pt，與參考書 §1 實測同形態）；縮排偏移維持網格字距；偏差超容忍（2 槽）維持等距網格並入統計（不沉默）。
- [實作] 行首禁則改「擠入優先」：整串連續句逗一次決策掛入本行行尾（溢出 ≤2 槽）；超過上限改追出錨字連同句逗下移。行尾禁則維持退行。
- [實作] Line 帶 cap／para_end；LayoutResult／RenderResult／PdfResult 帶 justify_stats；CLI render 與 export-pdf 回報齊行統計。
- 測試 107 → 112（+5）。

### 變更

- 斷行點整體前移：句逗不再被追出至次行，第一章實排 23 頁 → 22 頁（樣張已重生成）。

### 已知限制（詳 GAPS.md）

- 半形「約物寬度壓縮」（JLREQ 式）不實作：參考書實測句逗置中、無半形擠壓，齊行以字距縮放達成（§10 決議）。
- 斷行逐行一致率 vs 參考書待 Owner 抽檢；鏡像依書頁號（#16）、PNG 缺字警告（#17）、橫排（#13）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機，重生成 22 頁）：page-001.png 第 2 行行尾逗號擠入、滿行行底貼齊（已 AI 目檢）；chapter1.pdf preflight 12/12 與 pdffonts 全綠不退步，待 Owner 過目並與參考書斷行抽樣比對。

## v0.5.0（2026-07-11，Sprint 10）PDF/X-1a:2001 識別＋機械 preflight

### 新增

- [實作] X-1a:2001 識別（ISO 15930-1，PLAN §9 預設）：header 改 %PDF-1.3、Info 補 GTS_PDFXVersion (PDF/X-1:2001)＋GTS_PDFXConformance (PDF/X-1a:2001)＋Trapped /False＋ModDate（帶時區）；Title 必填快速失敗。
- [實作] OutputIntent：/S /GTS_PDFX，預設 JC200103（Japan Color 2001 Coated 的 ICC registry 特性化條件名，依 ISO 15930-1 免嵌描述檔、零 ICC 授權負擔）；自訂識別強制以 --icc 嵌 CMYK 輸出（prtr）DestOutputProfile（/N 4），錯型別快速失敗。
- [實作] XMP metadata stream（不壓縮）：dc:title／日期／pdf:Trapped 與 Info 同值，pdfx:＋pdfxid: 雙命名空間 X 識別。
- [實作] 機械 preflight（cjkfolio/preflight＋CLI preflight）：12 條 X-1a 規則（header／ID／加密／Info 識別／OutputIntent／盒框／字型嵌入／CMYK-only／LZW／透明／互動項／XMP），PyMuPDF 獨立解析，未涵蓋項誠實列印，exit code 0/1。
- CLI export-pdf 新參數：--output-condition-identifier／--output-condition／--icc。
- 測試 96 → 107（+11）。

### 已知限制（詳 GAPS.md）

- veraPDF 僅驗 PDF/A／UA、不支援 PDF/X（官方文件實查），本機 preflight＝自寫機械檢查＋pdffonts；Acrobat／印廠認證級 preflight 未跑（#18 新開，#15 關閉）。
- KNOWN_PRINT_CONDITIONS 為 registry 常用子集，未列名的 registry 條目需擴充名單或附 ICC。
- 鏡像依書頁號（#16）、PNG 缺字警告（#17）、齊行（#9）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/chapter1.pdf＋chapter1-p1.pdf（本機，重生成）：自寫 preflight 12/12 全綠、pdffonts 六款全綠；pdf-render-x1a-001/006.png 已 AI 目檢與 Sprint 9 版面一致，待 Owner 以閱讀器實開，另若有 Acrobat Pro 可跑官方 preflight 對照（GAPS #18）。

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
