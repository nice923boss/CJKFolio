# CHANGELOG

> Phase 0（Spike 1〜5）歷程見 devlog/；自 Phase 1 產品碼進場（Sprint 6）起立此檔。

## v0.27.0（2026-07-12，Sprint 32）替代軌 B：近 800 行測試檔依頁型分檔

### 變更（測試重組，行為零變更）

- test_layout_render.py（795→495 行）與 test_pdf_writer.py（791→469 行）近 800 行上限，各抽「主版向量裝飾與目錄頁型」連續塊（CIP 細框 Sprint 14、目錄天頭虛線 Sprint 15、條目頁碼引導線 Sprint 16、篇名嵌線斷開 Sprint 21，pdf 另含 G 圖文佔位框 Sprint 27）為新檔。
- 循 tests/ 既有「各檔自帶 `template` fixture＋make_ helper」慣例（8 檔皆如此），新檔自帶 fixture／helper，不建共享 conftest（避免改動全檔共享模型＝逾分檔範圍）；測試本體以 sed 逐位元組搬移（零轉錄風險），header 手寫。
- 核心 test_layout_render.py 補 `PT` 常數（章名條目 layout 測試留核心，其 PT 定義隨塊移出）；test_pdf_writer.py 移除抽出後未用的 `from cjkfolio.primitives import cip_frame_rect, toc_rule_line`。

### 新增

- [實作] tests/test_render_vectors.py：13 test（CIP 框＋目錄虛線／頁碼引導線／嵌線 的 layout＋render，自 test_layout_render.py）。
- [實作] tests/test_pdf_vectors.py：14 test（同上＋G 圖文佔位 export，自 test_pdf_writer.py）。

### 驗證

- 全套 `pytest spikes tests` 214 passed / 0 failed（總數不變：39＝26＋13、35＝21＋14，零 test 遺失或重複，分檔行為保持）；typecheck（py_compile 全部）EXIT=0。
- import 潔淨：4 檔各 import 皆有 body 使用（grep 計數 ≥2）；兩核心檔無孤兒 import（pdf 核心 cip_frame_rect／toc_rule_line 抽出後 import 行已移除）。tests/ grep 無 em-dash。分檔後最大測試檔 495 行。

## v0.26.0（2026-07-12，Sprint 31）主軌否決（block 軸整數對齊無 pt 目標）＋轉替代軌 A：measure 工具共用模組

### 決策（主軌否決，honest-planning R1／R8）

- para_gap block 軸 pt 精度主軌以 A 級量測否決：block 軸（段落堆疊＝水平欄位，`slot → line_axis`）本就整數槽對齊、無 sub-slot pt 目標，別於 Sprint 29/30 inline 軸（首字縱向 6.02/6.24pt 真實偏移）。三線證據：(1) C 主版 evidence 明載「大標 para_gap 1 使 body 落 slot 3 vs 真書 slot 2」為整數槽差非 pt；(2) 中標 cx 354.24 ＝ slot 0、大標 331.28 ＝ slot 1（Δ0.03）皆恰整數槽；(3) 本機 probe 量 33 頁內文欄 gap/pitch 4.2〜6.0 隨內容變動、無固定殘差。釐清 Sprint 30 交接「需 block 軸 pt 偏移」為前提誤讀；硬加無真實偏移的 para_gap_offset_pt 違反 R5，不建機制。依 Owner 預授權轉替代軌 A（順手移除噪音）。

### 新增

- [實作] tools/_measure_common.py：measure 工具共用層，抽 4 工具重複的 `HALF_W`（419.53 字面值免捨入漂移）、`PT_PER_MM`、`spans`（回傳 list 供同頁多次篩選）、`is_spread`（半頁判定）、`reference_pdf`、`write_measurements`（JSON 樣板＋mkdir）、`stdout_utf8`；加 `BLEED_PT`／`strip_bleed`（Gate-4 model media→trim 換算正典 helper，收斂 Sprint 24/25/30 出血口徑）。常數量測層自持（同 primitives.py 對 PT_PER_MM 的先例），不 import 產品層。

### 變更（工具重構，行為零變更）

- measure_cip／toc／case／figure_page.py 改 import 共用層；順手清 measure_toc／cip 未使用的 `PT_PER_MM` 死碼。4 檔淨減 15 行重複。

### 驗證（Gate 4 獨立）

- 行為保持：重構前跑現行 4 工具快照 JSON → 重構後刪輸出重跑 → 逐工具 diff 對照，cip／toc／case／figure 全 **IDENTICAL**（0 差異）、4 工具 run 皆 exit 0（先刪輸出避免失敗留舊檔造成假 identical）。
- 全套 `pytest spikes tests` 214 passed / 0 failed（產品碼未動）；typecheck（py_compile 全部）EXIT=0；tools/ 無 em-dash、無遺留 `reconfigure`／`ROOT`／`_spans`／`json.dumps`。

### 已知限制（詳 GAPS.md #13）

- block 軸整數對齊為本書網格特性（sub-slot 藝術偏移只現於 inline 軸），故 para_gap 無 pt 精度需求；C 個案扉頁「大標 para_gap 1 使 body 落 slot 3 vs 真書 slot 2」為整數差，正解 para_gap 1→0，但 個案大標 同時用於內頁 h2（42 頁）須拆樣式，續留 GAPS #13。
- `BLEED_PT`／`strip_bleed` 為量測工具箱之 Gate-4 換算正典（model↔trim 比對），本 sprint 量無出血真書故未觸發（工具箱基建非死碼）；測試側 test_pdf_writer.py／test_lead_offset.py 的 BLEED_PT 仍各自持有，跨 tools/tests 統一非本軌範圍。

## v0.25.0（2026-07-12，Sprint 30）目錄章名條目 inline 偏移＋Gate 4 出血座標框勘正

### 新增

- [實作] layout：`lead_offset_pt` 接入 `_toc_marks`（`title_end` → 引導線起 `leader_y0`）與 `_rule_breaks`（`line_top` 穿線判定），目錄條目 body 偏移時引導線起點與穿線與否同步跟隨 body 實際位置（Sprint 29 刻意延後部分，本 sprint 正題）；頁碼底錨 `page_no_top`／線終 `leader_y1` 為頁面固定列不隨條目。兩後端 render／pdf_writer 消費同一 `TocEntryMark`／`RuleBreak`，改 layout 即自動 parity。
- [實作] tests/test_lead_offset.py：目錄機制（font-free：`leader_y0` 隨 lead_offset 同移、頁碼底錨不動、穿線判定同步）＋兩後端絕對值（PyMuPDF span top 扣出血 → trim 貼真書 135.15）＋兩渲染差分（PNG／PDF on−off ＝ 6.24）。既有 3 toc/rule 測試預期式同步加 `lead_offset_pt`。測試 209 → 214。

### 變更（模版：Gate 4 出血座標框勘正）

- 目錄-篇章條目加 `lead_offset_pt` 6.24：條目首字墨頂（PyMuPDF span top 扣 3mm 出血 → trim 空間）貼真書 135.15（端到端實測精確 135.15）。
- **勘正 Sprint 24 墨頂比對之出血座標框錯配（GAPS #21 同型）**：Sprint 24「墨頂 137.42 vs 真書 135.15、差 +2.27」係拿 model 含出血 media 座標比真書無出血 trim（真書 PDF 本機實測 media ＝ trim ＝ bleed，頂部出血 padding 0.000pt），未扣出血 8.504pt。扣出血後 model trim 墨頂 128.91 vs 真書 135.15，正確 lead_offset ＝ +6.24（下移），方向與原記 -2.27（上移）相反。數學自洽：假差 +2.27 ＝ 真實 trim 差(-6.24) ＋ 出血(8.504)。

### 驗證（Gate 4 獨立）

- scratchpad probe：真書 PDF 頁盒本機實測（media／trim／bleed 三者同尺寸、頂部 padding 0.000pt ＝ 無出血）；model export PDF media span top 137.42（與 Sprint 24 記錄吻合 0.005pt）扣出血得 trim 128.91。
- 端到端 samples/toc.doc.json：render PNG Read 親驗（部名穿線＋4 條目縮退在虛線下＋引導線＋直排頁碼 17／63／109／155 底對齊）、export preflight 12/12、條目墨頂 trim 135.15、兩後端 parity。
- 全套 `pytest spikes tests` 214 passed / 0 failed；typecheck EXIT=0。

### 已知限制（詳 GAPS.md #13）

- +6.24 為 PyMuPDF 同口徑（字型 ascent 線）扣出血對齊，殘留思源／華康 ascent 度量差（§3.3 不比字形輪廓，位置偏移無法消除）；出血 8.504pt 才是可修正的座標框錯配。
- lead_offset_pt 仍未套用橫排 body（無 combined 用例）；para_gap block 軸（Sprint 25 個案中標相鄰）待 block 軸 pt 偏移新機制。

## v0.24.0（2026-07-12，Sprint 29）引擎 pt 精度模型：段級 inline 軸 sub-slot 偏移（lead_offset_pt）

### 新增

- [實作] 段落樣式 `lead_offset_pt`（段級 inline 軸 sub-slot pt 偏移）：載體鏈 ParagraphStyle → ParagraphSpec → PlacedLine → 兩後端 body inline-start（`top_pt + start_slot × advance + lead_offset_pt`，render／pdf_writer 同源一致式）；純位置微調不改斷行容量（不進 `_break_cells`，斷行禁則齊行不動）。整數字槽定位自此可疊加 sub-slot pt 精度（護城河引擎，Owner 指示「最複雜架構先做」）。
- [實作] tests/test_lead_offset.py：布線（font-free：大標 PlacedLine 帶 6.02、部序號帶 0）＋兩後端兩渲染差分（offset 6.02 vs 0，字型 ascent 抵消）證大標首字下移恰 6.02pt、部序號不動。測試 206 → 209（另開新檔，test_layout_render.py 792 行近上限）。

### 變更（模版：Sprint 20 三部扉一手量測，A 級）

- 部扉大標-明體W9 加 `lead_offset_pt` 6.02：大標首字頂 cell_top 176.84 → 182.86pt，貼真書量測 182.86（部序號維持天頭 176.84）。關閉 GAPS #13 的 B 部扉「大標首字頂低 6.02pt（0.26 字槽）v1 整數槽差」子項。
- 重議 Sprint 20 決議「段前 pt 偏移延後 Phase 2〜3」：Owner 要求最複雜架構，正式觸發重議（決議紀錄）。

### 已知限制（詳 GAPS.md #13）

- lead_offset_pt v1 只套用直排 body；橫排 body 與 toc 引導線／rule 穿線判定不套用（現無 combined 用例：唯一使用者部扉大標為直排無 toc／rule）。
- 目錄條目縮退（+2.89pt）、目錄章名（+2.27pt）、para_gap（Sprint 25 個案中標）等其他整數槽差待後續 Sprint 以同 inline 軸機制逐軸套用＋量測驗收。

## v0.23.0（2026-07-12，Sprint 28）preflight trailer-id 假陰性勘正（基線綠回復）

### 修正（baseline 假陰性：接手動工前跑基線發現）

- `pytest spikes tests` 全套順序下 `test_export_toc_rule_preflight_green` 假性失敗（`trailer-id`）。根因：`preflight.check_pdfx1a` 的 trailer-id 規則 regex 只認角括號 hex `<...>`；PyMuPDF `xref_object` 對「解碼後 16 bytes 全可列印」的 /ID 兩組字串重序列化為 literal `(...)`，regex 落空判失敗。全套累積使該 TOC PDF 的 /ID（＝`md5(bodies)`）位元組落入可列印區間才觸發（單獨執行不觸發）；**檔案 /ID 始終為合規的兩組非空字串，PDF 無缺陷，渲染／寫出層不動**。
- 修檢查器 regex：trailer-id 每組字串同認 `<hex>` 與 `(literal)` 兩式（空 `<>`／`()` 仍判失敗，方向安全，不假性放行真正缺 /ID 者）。

### 新增

- [實作] tests/test_preflight.py::test_preflight_accepts_literal_string_id：可列印 /ID 的手工 PDF 回歸測試（TDD：修前 RED、修後 GREEN，確定性重現不依賴全套累積）。測試 205 → 206。

### 驗證（Gate 4 獨立）

- scratchpad probe：手工組不同 /ID PDF＋fitz 讀回實測 PyMuPDF 序列化行為（可列印→`(literal)`＋regex 落空、非可列印→`<hex>`＋命中），與被修檢查器不同路徑確證機制。
- 完整基線 `pytest spikes tests` 206 passed / 0 failed，順序相依失敗消除；typecheck EXIT=0。

## v0.22.0（2026-07-12，Sprint 27）G-圖文版主版：頁型骨架（§4.2 主版 7 種完備）

### 新增

- [實作] tools/measure_figure_page.py：分類量測圖文版頁（Type 1 全頁圖文版 vs Type 2 內文內嵌小圖），只聚合 32 全頁圖文版頁的圖框保留區與辰宇圖說幾何（一手量測，輸出 assets/reference 本機不入 repo）。
- [實作] cjkfolio.styles.FigureSpec＋MasterPage.figure：圖框保留區主版欄位（photo-slot，縱向 top/bottom＋佔位框 dash/cmyk；載入驗證未知 kind／bottom≤top／壞 cmyk 快速失敗）。
- [實作] cjkfolio.primitives.figure_slot_rect／figure_slot_edges：承版心鏡像的圖框保留區幾何＋四邊虛線（reuse 既有 dashed-line 路徑，兩後端同源）。
- [實作] render._draw_figure／pdf_writer._figure：G 圖文版圖框保留區淡虛線佔位框（gate vertical＋master.figure＋page.placed），render PIL 灰值分段／pdf `d` dash＋K 描邊，兩後端幾何同源。
- [實作] 段落樣式「圖說-辰宇落雁」（辰宇落雁體 15.9pt）＋samples/figure-page.doc.json（自擬圖說標籤，紅線不取真書文字與照片）。
- [實作] tests：figure_slot_rect 鏡像 L/R＋四邊虛線（test_primitives，+4）、FigureSpec 載入/驗證＋圖說樣式（test_styles，+7）、佔位框 dash 描邊/兩後端 parity/preflight（test_pdf_writer，+3）。測試 191 → 205。

### 變更（模版：G 圖文版 32 頁一手量測，A 級）

- G-圖文版主版：evidence 由「版心承 A；佈局未量測」推定升級為一手驗證：圖框橫向承 A 版心鏡像（R 頁 x0=72.51／x1=360.0、L 頁 59.53／347.02）、雙照片區 top 107.04／bottom 467.62pt、辰宇圖說 15.92pt（31 span 同值）；加 figure（photo-slot 保留區）。
- §4.2 主版 7 種（A／B／C／D／E／F／G）於 Phase 1 骨架層完備。

### 已知限制（詳 GAPS.md #13）

- 與 B-部扉同型（美術本體延後）：真書照片嵌入為 Phase 2 圖片置入（§9 灰階單 K／300-350ppi）、房名黑體標題＋辰宇自由圖說位置＋裝飾括號為手繪美術（§8 不生成）、前後照片配對與圖文繞排為 Phase 4；真書照片略溢版心 1〜4pt、實際照片逐頁變異（單/雙、高度 385〜500pt）＝美術自由佈局。
- 佔位框為 Phase 1 版面骨架導引（InDesign 空框慣例，真書照片無邊框），Phase 2 圖片置入取代、不留框線；preflight 誠實聲明「v1 尚無影像置入」。
- tests/test_pdf_writer.py 791 行、test_layout_render.py 792 行皆近 800 上限，後續 PDF／layout 測試需先評估分檔。

### 待 Owner 真實素材驗收

- G-圖文版樣張為自擬（改造前／改造後）；真書圖文版照片置入品質、前後配對版式待 Phase 2；斷行逐行一致率比對（Owner 抽檢）延續。

## v0.21.0（2026-07-12，Sprint 26）GAPS #21 勘正：直排字墨偏移為量測框錯配（非置中 bug）

### 勘正（GAPS #21：Sprint 25 Gate 4 誤判）

- Sprint 25 Gate 4 抽驗報「直排字墨 cx 偏 line_axis +8.5pt」、判為全直排正確性問題。**本 Sprint 實證勘正為量測座標框錯配，渲染層本就正確**：+8.5pt＝3mm 出血（BLEED_PT 8.5039pt），係拿 PyMuPDF MediaBox 座標（含出血）比 trim 空間 line_axis 所致；偏移與字級無關（大標 17.9pt 與資訊列 11.4pt 同偏 +8.50）＝純出血常數，非隨字級變的置中誤差。
- 實證（probe＋回歸測試）：export 後大標 MediaBox cx 339.75、資訊列 362.75，各扣出血後 trim cx＝331.25／354.25＝line_axis（Δ+0.00pt），與真書 ink 中心同構（331.28 差 0.03）。既有 test_export_glyph_geometry_on_grid 早已用 BLEED_PT 扣出血比對、test_render_single_char_lands_in_first_cell 早已驗 PNG trim 置中；Gate 4 手驗漏扣此常數。

### 新增

- [實作] tests/test_pdf_writer.py::test_case_ttb_ink_centered_on_line_axis：釘住 PDF 側直排置中（C 大標 17.9pt＋資訊列 11.4pt，扣 BLEED_PT 後字墨 cx＝line_axis）＋反例保護（未扣出血恆偏 +BLEED_PT，佐證框差非置中錯誤）。測試 190 → 191。

### 變更

- tests/test_layout_render.py：test_case_master_and_title_placement 誤導註解（原「PDF/PNG 實際字墨 cx 偏此 +8.5pt」）勘正為出血框差說明並指向新測試；PDF 置中測試置於 test_pdf_writer.py（依 fitz／export_pdf 分層，test_layout_render.py 回 800 行以下）。

### 未動（誠實記錄）

- 不修渲染碼：placement／render／pdf_writer 直排置中本就正確；任何「補償 −8.5pt」都是反向雙重補償、會破壞現有與真書吻合的置中。

## v0.20.0（2026-07-11，Sprint 25）C 個案扉頁大標置位＋直排墨偏移發現（GAPS #21）

### 新增

- [實作] tools/measure_case_page.py：掃描定位個案扉頁（右半頁），逐列量大標行軸／字距／版心／Case 編號（數十頁互證）。
- [實作] samples/case-divider.doc.json：自擬個案扉頁樣張（副標＋大標，紅線不取真書文字）。
- [實作] tests：C 承 A（內文天頭 92.09pt、首行縮排 2 字）＋大標 slot 1 右頁 line_axis 331.25。測試 189 → 190。

### 變更（模版：C 個案扉頁數十頁一手互證，A 級）

- C-個案扉頁主版：evidence 由「未量測（承 A 推定）」升級為一手量測：個案大標 NotoSans Medium 17.9pt 置 slot 1（右頁 line_axis 331.25 貼真書墨欄中心 331.28，差 0.03）、資訊列（Case 編號 DFHeiStd-W5 13pt＋副標 11.4pt）slot 0、內文承 A 自 slot 2（首字 top 145.75）。
- 「個案中標」para_gap_slots 1 → 0 勘誤：實測資訊列 slot 0 與大標 slot 1 相鄰（同 Sprint 20 部扉標籤先例）。

### 發現（正確性問題，GAPS #21，Gate 4 閉環抽驗）

- PyMuPDF get_texttrace 抽 case.pdf：大標 layout slot 1 行軸正確（331.25＝真書 331.28），但 **PDF 字墨 cx 339.75，偏 line_axis 欄中心 +8.5pt**；資訊列 11.4pt 與大標 17.9pt 墨 cx 皆偏 +8.50（與字級無關），真書華康大標墨 cx＝欄中心。
- 判定為**全直排既有正確性問題**（placement ttb 逐字水平 origin＝line_axis 欄中心，未補償字形水平度量）：非 Sprint 25 引入、非單一頁型；兩後端同源（PNG/PDF 一致）故 parity 未攔截，過往只驗 layout axis 或 Read PNG（8.5pt≈3mm 不明顯）故未暴露。
- 本 Sprint **不硬修**（context 保護、避免 Sprint 22 式同源同錯降級）：列 GAPS #21，Sprint 26 專項調查（左右頁對稱性＋根因＋全直排座標回歸）。

### 已知限制（詳 GAPS.md #13、#21）

- C v1 不建模：資訊列雙元素（Case 編號 13pt 獨立列）、內文精確段間 gap、個案雙線框；GAPS #21 直排墨偏移待 Sprint 26 修。

### 待 Owner 真實素材驗收

- out/case25/（本機，重生成）：page-001.png（--first-page 2 右頁）資訊列 slot 0＋大標 slot 1（黑體級數區隔）＋頁碼書口右已 Read 親驗；case.pdf preflight 12/12、字型 SourceHanSansTC-Medium 無 fallback；**待 Owner 與真書並排目視比對，並注意直排墨偏移 GAPS #21（≈3mm 偏書口）**。

## v0.19.0（2026-07-11，Sprint 24）目錄章名條目黑 W5（一手量測勘誤）

### 新增

- [實作] tools/measure_toc_page.py：加 entry_columns 直排列分析（按字中心 x 聚列，標主 CJK 字型／級數／頁碼），供目錄多層條目字型辨識。
- [實作] tests：目錄章名條目勘誤斷言（font 思源黑體 TC／weight medium／11.5pt／head_offset 2／source DFHeiStd-W5、章名首字框頂 132.12）。測試 188 → 189。

### 變更（模版：p002/p003 一手量測，A 級）

- 「目錄-篇章條目」樣式勘誤：全字庫正楷體 TW-Kai 9.5pt → **思源黑體 TC Medium 11.5pt**（source DFHeiStd-W5），head_offset 3 → 2 槽：真書帶頁碼章名實為黑 W5 11.5pt（entry_columns 量測：章名全帶頁碼 top_y 135.15；楷 W3 9.5 為不帶頁碼摘要層字型，掃描誤設為章名層，同 Sprint 23 勘誤）。
- 勘誤同時解 GAPS #12 fallback：章名改用已入庫思源黑體 Medium，render 不再 fallback TW-Kai（題詞-楷書仍用 TW-Kai，fallback 測試對象不變）。

### 已知限制（詳 GAPS.md #13）

- v1 不建模：條目摘要層（楷 W3 9.5 不帶頁碼、真書 top_y 166）、【結語】黑 W5 10pt 變體、章名與摘要縱向錯落及多層列距；章名首字墨頂 137.42 vs 真書 135.15（差 +2.27pt＝整數槽＋思源華康字框度量差）。

### 待 Owner 真實素材驗收

- out/toc24/（本機，重生成）：page-001.png（--first-page 3）4 條章名黑 W5＋引導線＋直立頁碼 17／63／109／155 底對齊已 Read 親驗（黑體章名與明體部名字族區隔）；toc.pdf preflight 12/12、PyMuPDF 抽驗 4 列 SourceHanSansTC-Medium 列距 23pt；待 Owner 與真書 p002/p003 並排目視比對。

## v0.18.0（2026-07-11，Sprint 23）E 序文版頁型（三頁互證量測）

### 新增

- [實作] samples/preface.doc.json：自擬序文樣張（標題＋內文兩段，master E）。
- [實作] tests：E 主版與標題樣式量測常數＋樣張幾何（標題 slot 0、內文 slot 5、縮排 2 字）。測試 186 → 188。

### 變更（模版：p004/p007/p009 三頁一手互證，A 級同值）

- E-序文版：版心承 A **由推定升級為一手驗證**（天頭 92.09pt=32.49mm、行距 23、字距 12.08、首行縮排 2 字吻合）；**頁腳承 A**（頁碼 x 36.85pt 與 A outer_offset 36.8 精確吻合、序文偶頁書眉實測同 A）。
- 樣式勘誤：「推薦序大標-楷書W5」（16.3pt）→「**推薦序大標-黑體**」（思源黑體 Medium **12.9pt**、para_gap_slots 4）：原記為掃描誤抓署名行長橫「─」；序文標題真身 NotoSans Medium 12.9pt（個案大標 17.9pt 為不同級）。
- 模版 JSON 經 json.dump 統一重排（indent=1），內容等價、僅格式統一。

### 已知限制（詳 GAPS.md #13）

- 欄標「推薦序」（黑 W5 9pt）＝標題行右側 16.2pt 肩位（v1 無肩注機制）；署名行（楷 W5 16.3 長橫＋明 W9 11.1 混級）y 頂底皆隨頁變動＝自由手排；標題行軸實測 342.16 vs 承 A 推導 341.26（差 0.9pt≈inner 0.32mm）。

### 待 Owner 真實素材驗收

- out/preface23/（本機，重生成）：page-001.png（--first-page 7）標題右起＋內文隔 4 槽＋頁碼書口左下已 Read 親驗；preface.pdf preflight 12/12、標題行軸抽驗 341.27pt 與 v1 推導重合；待 Owner 與真書 p004 並排目視比對。

## v0.17.0（2026-07-11，Sprint 22）鏡像側別與真書對齊（正確性修正）

### 修正（GAPS #20：Sprint 12 側別基準與真書相反）

- [實作] 真書三向互證（A 級）：頁碼側（四 spread：偶頁頁碼書口右、奇頁書口左）＋書眉側（書名書眉皆偶頁）＋版心側（偶頁右邊距 21.00mm＝outer 精確）→ **偶數頁＝右頁、奇數頁＝左頁**；Sprint 12「奇右偶左」為西式左翻書慣例誤植。
- [實作] render：新增 `is_right_page` 單一事實來源（偶＝右頁），`line_axis_x_pt`／`horizontal_left_x_pt`／兩後端 `_footer` 共 5 判定點收斂；footer 奇偶 gate（pages 配置語意）與書口側別拆分；mirror=false 恆以 outer 槽為起排側（直排 B＝右、橫排 F＝左）。
- [實作] 奇偶測試矩陣第二次翻轉（line-axis／footer／page-selection／body-axis 兩後端＋styles），橫排幾何斷言改 outer 語意。測試 186 → 186（0 退步）。

### 變更（模版）

- A-內文版：書名書眉 `running_title.pages` **odd → even**（真書書名書眉在偶頁＝右頁）；左頁（奇數頁）章節副標書眉仍待章節結構（既有 note）。
- F-版權頁：margins **outer↔inner 對調**（outer 25.81＝p178 左頁書口，名實相符；inner 21.0 承 A 自擬）；mirror=false 幾何不變（CIP 框 PyMuPDF 複驗 x0 差 0.01pt）。

### 勘誤（記錄修正，幾何不受影響）

- Sprint 12 devlog／§10「與真書右翻一致」比對記錄錯誤；Sprint 20「部扉＝偶數頁」實為奇數頁（37/137/229，B mirror=false 幾何不變）；§1 補側別事實。

### 待 Owner 真實素材驗收

- out/ch1-s22/（本機，重生成）：--first-page 20 的 page-001（書頁 20 偶＝右頁：頁碼書口右下＋書名書眉）與 page-002（書頁 21 奇＝左頁：頁碼左下無書眉）已 Read 親驗，與真書 spread（PDF 索引 4/12/30/40）逐項一致；待 Owner 翻閱實體書覆核側別。

## v0.16.0（2026-07-11，Sprint 21）目錄篇名嵌線斷開＋條目縮退（p002/p003 量測）

### 新增

- [實作] engine：`ParagraphSpec.head_offset`（段級天頭縮退槽，整段每行起始槽位下移；縮退已含於 `start_slot`，兩後端 y 幾何零改動）。
- [實作] styles：`ParagraphStyle.head_offset_chars`、`RuleSpec.break_before_pt`／`break_after_pt`（篇名嵌線斷開邊距）。
- [實作] primitives：`toc_rule_segments`（虛線依斷開區間切段；gap 裁剪、零長段不產出；`toc_rule_line` 保留為全寬幾何來源）。
- [實作] layout：`RuleBreak`＋`LayoutResult.rule_breaks`（穿線行判定純幾何：行首字頂 y 高於虛線 y 即斷開，非樣式白名單）。
- [實作] render：`rule_break_ranges`（穿線行行槽範圍±斷開邊距 → 斷開 x 區間，兩後端同源）；`_draw_rule`／pdf `_rule` 改多段。
- [實作] tools/measure_toc_page.py：目錄頁虛線分段＋穿線行＋縮退量測工具（Sprint 19 先例，量測 JSON 本機不入 repo）。
- [實作] tests：engine head_offset、primitives 切段 3 項、layout 穿線判定 3 項、render 著墨斷開、pdf 兩後端 parity＋preflight。測試 176 → 186。

### 變更（模版 D-目錄：p002/p003 一手量測，A 級三處互證）

- margins：top 47.63 → **38.09mm**（篇名「第N篇」首字頂 107.96pt，三處同值；原 47.63mm 條目錨 135pt 改由縮退表達）。
- 樣式「目錄-篇章條目」：**head_offset_chars 3**（縮退 29.93pt vs 真書 27.04pt，整數槽差 +2.89pt）。
- rule：加 **break_before_pt 28.5**／**break_after_pt 3.9**（行槽緣→線端量測中值）。

### 已知限制（詳 GAPS.md #13）

- 條目縮退整數槽差 +2.89pt（v1 整數槽模型，同 Sprint 20 先例）；斷開邊距真書手排離散（before 26.9〜30.1／after 3.7〜4.1，取中值）。
- 帶起訖不建模：真書前置條目區（目次大標、推薦序）無線、帶起於首篇名、跨頁延續記號±10mm；v1 全寬貫穿＋出血。
- 篇序（第N篇 11pt W7 密排騎線）＋部名詩句 16pt 同行混排不建模（v1 部名單一樣式；真書詩句字距 17.12 亦非 §10 換算 16.81）。

### 待 Owner 真實素材驗收

- out/toc21/（本機，重生成）：page-001.png 部名穿線＋虛線斷開＋條目縮退已 Read 親驗；toc.pdf preflight 12/12、PyMuPDF 抽驗兩段虛線端點與手推**完全重合**（0.00pt）；待 Owner 與真書 p003 並排目視比對。

## v0.15.0（2026-07-11，Sprint 20）B 部扉頁型大標置位（三部扉量測）

### 新增

- [實作] samples/part-divider.doc.json：自擬部扉樣張（篇序標籤＋部名兩段，master B）。
- [實作] tests：test_part_divider_layout_geometry（行軸 228.49／194.12、天頭 176.84pt、大標字距 23.1 量測常數釘死＋標籤 gap 0）。測試 175 → 176。

### 變更（模版 B-部扉：承 A → 三部扉一手量測，A 級三頁互證）

- margins：top 32.49 → **62.38mm**（部序號首字頂錨定）、outer 21.0 → **63.53mm**（slot 0 行軸反推）；mirror true → **false**。
- grid：32×13（12.08／23.0／11.5）→ **10 字×8 行（23.1／34.37／21.9）**；字距合 §10 換算規則（W7 推導 15.72 vs 實測 15.75）。
- 樣式「標籤-篇序小標」para_gap_slots 1 → **0**（與大標間距已含於行距 34.37pt）。

### 已知限制（詳 GAPS.md #13）

- 真書大標首字頂比部序號低 6.02pt（0.26 字槽）：v1 整數槽模型兩段同天頭起排。
- 雙線菱形裝飾框不規則化（手繪美術資產，Sprint 15 決議）；bold 字重以 heavy 替（GAPS #12 既有警告不沉默）。

### 待 Owner 真實素材驗收

- out/part20/（本機，重生成）：page-001.png 部序號＋大標兩行直排置位已 Read 親驗；part.pdf preflight 12/12、PyMuPDF 抽驗兩行軸中心 x 228.49／194.12 與三部扉量測**精確重合**；待 Owner 與真書部扉（如 p069）並排目視比對。

## v0.14.0（2026-07-11，Sprint 19）F-版權頁真實版心量測（關 GAPS #13 (a)）

### 新增

- [實作] tools/measure_cip_page.py：p178（PDF 頁索引 177）CIP 量測工具（框折線重建 bbox、框內 spans 行距／字距／pad 統計、半邊判定；輸出 assets/reference/cip_measurements.json 本機不入 repo）。
- [實作] styles：FrameSpec.pad_v_pt（選配垂直 pad，None＝同 pad_pt）；primitives cip_frame_rect 支援不對稱 pad。
- 測試 173 → 175（+2：pad_v 解析＋不對稱框幾何；另 3 處寫死斷言同步為量測真值）。

### 變更（模版 F-版權頁：自擬 → p178 一手量測，A 級）

- CIP 級數 8 → **5.63pt**、字距 8.4 → **5.66pt**、行距 14 → **7.74pt**、滿行 34 → **23 字**；top 32.49 → **43.48mm**（首行 baseline 128.2pt 錨定）、inner 25.58 → **25.81mm**。
- 框：線寬 0.5 → **0.14pt**、純黑 → **暖黑 K92**（同內文色）、pad 6.0 → **5.05（水平）×4.94（垂直）**。

### 已知限制（詳 GAPS.md #13）

- 後段 3 行行距分區（12.73／11.73pt）：v1 單一 line_pitch 表達不了，樣張以主體 7.74 等距。
- 框上方 CIP 標題行：v1 不區分框內外行。框寬（網格滿行推導）與真書最長行差 1.3pt。

### 待 Owner 真實素材驗收

- out/cip19/（本機，重生成）：page-001.png 密排 CIP＋細框已 Read 親驗；cip.pdf preflight 12/12、PyMuPDF 獨立抽驗框左上角 (68.11, 118.31)／首行 baseline 128.2／字級 5.63／線寬 0.14 與 p178 量測精確重合（0.01pt 內）；待 Owner 與真書 p178 並排目視比對。

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
