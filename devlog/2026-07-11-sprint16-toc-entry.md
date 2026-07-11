# Sprint #16（2026-07-11）目錄條目頁碼＋引導線，已完成

**範圍**：目錄頁型第一片：條目直排數字頁碼（底錨對齊）＋垂直引導線（標題末→
頁碼前），PLAN §1「目錄的…直排數字頁碼」與 GAPS #13 (b) 項。接續 Sprint 15 的
天頭虛線，目錄頁的條目設計語言（標題／引導線／頁碼底對齊）本 Sprint 貫通。
honest-planning R6 pre-mortem 先行（`spikes/spike9-toc-entry/premortem.md`）；
R2 校正判定**無需新 PoC spike**：垂直實線＝Sprint 15 `StrokeLine` dash_on=0 退化
情形、直排數字直立逐位＝既有 tcy 能力（Spike 1 驗證、Sprint 8 起雙後端同源）、
頁碼掛段末行＝既有 `para_end`；新交互點只是載體欄位與純幾何推導，單元測試全釘。

**一手量測（A 級，p003 條目「被留下的人與不肯放手的家 169」）**：
- 條目標題 DFHeiStd-W5 11.5pt（目錄兩層：章名黑 W5＋摘要楷 9.5，模版 note 既記）。
- 引導線 w=0.1pt 垂直實線、x＝行軸、色暖黑同文字（產品對映單 K92，§9）。
- 頁碼 TimesNewRomanPSMT 9pt 直排逐位直立、行軸置中、末位底錨 y≈490pt、
  頁碼頂與線末間隙 ≈2pt（產品以「頁碼數字-GillSans」字元樣式對映，OFL 粉圓替）。

**完成**：
- ✅ 文件模型 [實作]：`Paragraph.page_no`（選配、僅數字字串、@2 相容擴充：無欄位
  照載、save 有值才寫；非數字快速失敗）。
- ✅ 引擎載體 [實作]：`ParagraphSpec.page_no`＋`PlacedLine.page_no`（flow 只在
  段末行帶值，純 passthrough 不影響斷行禁則）。
- ✅ 樣式層 [實作]：`TocSpec`（page_no_style／page_no_bottom_pt 必填＋leader
  寬/gap/cmyk）＋`MasterPage.toc`；模版跨引用驗證（toc.page_no_style 必須存在於
  character_styles，未知即 TemplateError）。
- ✅ layout 幾何 [實作]：`TocEntryMark`（slot／digits／digit 級數字距／頁碼頂／
  引導線 y0 y1／字元樣式）＋`LayoutResult.toc_marks`（page → marks）；幾何確定性：
  頁碼頂＝底錨−位數×字距（字距依 §10 換算規則 級數×12.08/11.5）、線起＝標題末
  ＋gap、線終＝頁碼頂−gap；標題與頁碼重疊（線長 ≤0）列入 violations 不沉默、
  後端不畫線；帶 page_no 落在無 toc 主版快速失敗。
- ✅ render 後端 [實作]：`_draw_toc_marks`（引導線復用 `_draw_stroke_line` 實線
  分支；頁碼逐位 `_draw_tcy` 直立置中；缺字警告照走 `_note_missing`）。
- ✅ pdf_writer 後端 [實作]：`_toc_marks`（引導線 `stroke_line` 無 dash、K92；
  頁碼 `tcy_placements` 逐位 emit）；`build_page`／`render_page` 加 `toc_marks`
  參數由 layout 餵入。兩後端幾何同源（mark＋`line_axis_x_pt`）。
- ✅ 模版 [實作]：D-目錄加 `toc`（頁碼樣式「頁碼數字-GillSans」、底錨 490pt、
  線寬 0.1、gap 2、K92，皆實測參數）；樣張 `samples/toc.doc.json` 條目加自擬
  頁碼（17／63／109／155）。

**測試成長**：151 → 164（+13：document 2〔page_no 載入往返／非數字拒絕〕；
styles 3〔toc 解析／缺必填拒絕／未知頁碼樣式拒絕〕；engine 1〔page_no 只掛段末行〕；
layout 2〔marks 幾何全欄位釘死／無 toc 主版快速失敗〕；render 2〔引導線細線＋頁碼
著墨幾何／無頁碼條目無線守護〕；pdf 3〔引導線 K92 無 dash＋座標 parity／頁碼三位
逐位座標 vs mark 幾何／preflight 全綠〕）。0 失敗、0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py spikes/spike8-dashed-rule/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：164 passed / 0 failed（`python -m pytest spikes tests -q`）
- 真實素材驗收（R5，紅線改自擬）：`samples/toc.doc.json`（部名＋4 條目帶頁碼）→
  - render PNG（out/toc/page-001.png，300dpi）：**Read 親驗**四條目標題末各起一條
    細垂直引導線延伸至頁碼上方；頁碼 17／63／109／155 直排逐位直立、行軸置中、
    **末位底一列水平對齊**（底錨 490pt），與參考書 p003 設計語言（標題→線→頁碼
    底對齊）一致；線長隨標題長度與頁碼位數自適應。
  - export PDF（out/toc/toc.pdf）：preflight **12/12 全綠**；PyMuPDF `get_drawings`
    獨立解析 5 條 draw＝1 虛線（dashes [3 2]）＋4 引導線（w=0.1、垂直、無 dash），
    引導線 y 起訖與幾何手推一致（線起＝135＋14×9.98＋2＝276.7、兩位數線終 471.2／
    三位數 462.8，含出血偏移全對齊）；`get_text` 抽出 10 個直立數字 word。
  - 兩後端同源：PDF 獨立渲染（toc-pdf-render.png）Read 目檢與 PNG 一致；單元
    測試釘死引導線座標 parity（abs≤0.3pt）與頁碼逐位座標 vs mark 幾何。
  - 字型紀錄：粉圓（頁碼）首次進 PDF 子集，fontTools 丟棄 Apple `meta` table
    （「meta NOT subset; dropped」stderr 提示，非渲染必要表、嵌入合法性不受影響，
    preflight fonts-embedded 照過）。
- 除錯紀錄：無（本 Sprint 基線與收尾皆一次綠）。

**代決事項（記入 PLAN §10）**：
- 目錄條目形態：`page_no` 為 document@2 相容擴充欄位（選配數字字串）；頁碼掛
  段末行、底錨對齊（參考書設計語言）；標題頁碼重疊時不畫線並列 violations。
- 頁碼字距依 §10 既有換算規則（級數×12.08/11.5＝8pt→8.40pt），與 p003 實測
  Times 9pt 字距 ≈9.5 同構不同值（字級由字元樣式決定，v1 用頁碼樣式 8pt）。

**落差登記**：#13 更新（目錄頁型：引導線＋直排頁碼已實作並驗收；剩項＝篇名嵌線
斷開、條目縮退、目錄「章名條目黑 W5」樣式層補充、F 與 B〜G 真實版心）。

**下個 Sprint 預定範圍**：候選：(a) B 部扉頁型（大標置位；裝飾框依 Sprint 15
決議不做規則化）；(b) E 序文版／推薦序頁型；(c) 全字庫正楷體 TW-Kai／正宋體
入庫驗題詞-楷書／引文-仿宋（GAPS #12 剩項，**需下載，開工前須 Owner 同意**）；
(d) 抽取工具目錄模式（真書目錄結構抽取，供本機比對驗證）。Owner 抽檢項不變：
Spike 1 對比圖（GAPS #10）、斷行逐行一致率、F 真實版心 p178 量測。
