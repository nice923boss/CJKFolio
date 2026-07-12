# Sprint #38（2026-07-12）C 個案扉頁資訊區欄位卡片建模（否決「需新機制」前提，勘正 Sprint 25 第五例誤讀），已完成

**範圍**：承 Sprint 37 交接「資訊區多欄位佈局（slot 2~4 空欄＋slot 5~11 欄位標籤／內文／13pt 中標交替，線性堆疊不可表達需新機制）為 Sprint 38 專項」，Owner「最複雜架構先做」下的 Phase 1 剩項。依 honest-planning R1／R8（先量測再動工，不臆測「需新機制」），先量測資訊區完整結構，確認真實機制需求才建模。

**根因（Sprint 38 A 級量測）**：臨時探針量測參考書 33 個案扉頁（本機，紅線不入 repo，跑完即刪），三輪聚焦：
1. **首內容 slot 全頁統計**：33/33 頁首內容 slot＝5、空 slot 2~4 為鐵律（大標 slot 1 後空 3 slot）。**勘正 Sprint 25「內文自 slot 2（top 145.75）」誤讀**＝第五例 C 主版 slot 誤讀（承 Sprint 34/35/36）：真書內容自 slot 5。
2. **頁型分類**：資訊頁 10（欄位卡片）／訪談頁 23（純內文流）。欄位標籤（NotoSans 11.4pt「【格局】【居住者】」top 92.3 頂格＝indent 0）＋欄位內文（DFMingStd 11.5pt 首列 top 116.5＝indent 2 縮排、續列 top 92.1 頂格）＋欄位間固定空 1 slot（四頁一致）。
3. **13pt DFHeiStd 中標定位**：9 頁全在訪談頁 slot 5 或正文中段（節標題「父母的留戀…」等），與資訊頁 0 重疊＝訪談頁節標題（＝章節小標-黑體），非資訊區元素。

**架構判定（否決「需新機制」前提）**：Sprint 37 交接「線性堆疊不可表達需新機制」為初步判斷（當時只量 info_span_count 計數）。R1 深入量測後：**欄位標籤與內文在相鄰不同 slot（非同 slot inline 分區）**，標籤 indent 0 頂格、內文 indent 2 縮排＝既有 indent_chars 欄位自然表達；空 slot＝既有 para_gap_slots（大標 gap 3 空 2~4、內文 gap 1 空欄位間）。**現有線性流排（engine.flow_pages）＋既有樣式＋indent／gap_after 即足表達欄位卡片，無需新引擎機制**（同 Sprint 31/34/35 量測後否決「需新機制」前提）。R2 判定既有能力復用、無需新 spike（先例＝E 序文版 Sprint 23 推薦序大標 gap 4→內文 slot 5 同機制，test_layout_render 現存測試）。

**完成**：
- ✅ templates/neizai-zhengli.json [實作]：個案扉頁大標-NotoSans para_gap 0→3（大標後空 slot 2~4、內容自 slot 5），note 記 Sprint 38 全 33 頁量測勘正 Sprint 25。資訊區欄位卡片復用既有樣式：欄位標籤＝個案中標-NotoSans（indent 0／gap 0）、欄位內文＝內文-明體直排（indent 2／gap 1），無新增樣式。
- ✅ samples/case-divider.doc.json [實作]：升級欄位卡片（自擬「【空間】／【成員】」兩欄位），slot [0,1,5,6,8,9] 空 2~4／7。
- ✅ tests/test_layout_render.py [實作]：C 測試充實欄位卡片守門（slot 佈局、大標 para_gap 3、欄位標籤 indent 0／內文 indent 2、空 slot 2~4／7）。
- ✅ tests/test_pdf_writer.py [實作]：case 置中測試延伸欄位卡片（slot 0/5/6/8/9 字墨扣出血對準各自 line_axis，兩後端 parity）。

**測試成長**：218 → 218（測試數不變＝勘誤＋既有機制建模型 Sprint，同 Sprint 26/31；充實 test_case_master_and_title_placement 與 test_case_ttb_ink_centered_on_line_axis 兩測試涵蓋欄位卡片）。0 失敗 0 退步。

**驗證**：
- typecheck（py_compile spikes／cjkfolio／tools）EXIT=0；test 218 passed／0 failed。
- 真實素材驗收（R5）：render case-divider PNG（first-page 20 偶＝右頁）三字型（SourceHanSansTC-Bold 欄標／Medium 大標＋欄位標籤／SerifTC 內文，欄標 Bold 不 fallback）、0 禁則；export PDF preflight 12/12。
- Gate 4 獨立驗證（三方同源）：layout slot [0,1,5,6,8,9]／PDF 字墨 cx（test_case_ttb_ink_centered slot 0/5/6/8/9 對準 axis）／PNG 墨跡直列 cx（程式化分析，視覺 Read 因 context limit elided）＝6 直列 354.1／331.3／239.3／216.2／170.4／147.4pt 對準 line_axis，列1→2＝4.00 slot（空 2~4）、列3→4＝1.99 slot（空 7）。
- Gate 3 同類掃描：slot 建模屬 C 主版；模版 note／GAPS #13／PLAN §10／CHANGELOG 四處 Sprint 38 描述均更新，Sprint 33「para_gap 0」矛盾同步勘正為 3。
- 繁中標點：grep 本 Sprint 改動檔（模版／樣張／二測試／PLAN／GAPS／devlog／CHANGELOG）無破折號殘留。

**代決事項（記入 PLAN §10）**：資訊區欄位卡片以現有線性引擎建模、否決「需新機制」前提（證據＝33/33 slot 5、標籤與內文相鄰不同 slot）；個案扉頁大標 para_gap 0→3（勘正 Sprint 25「內文自 slot 2」＝第五例 C 主版誤讀、Sprint 33「gap 0」前提）；case-divider 升級欄位卡片；個案中標定位為欄位標籤樣式（indent 0 頂格）。屬非紅線建模決策，證據驅動，git commit 隔離供 Owner 事後檢視。

**落差登記**：GAPS #13「個案中標移資訊區＋資訊區多欄位佈局」由「Sprint 38 專項（需新機制）」更新為「已完成（線性引擎即足）」；順手折疊 Sprint 33／38 C 個案扉頁建模段為統一結論（完整過程存 devlog／CHANGELOG）。剩：10.5pt 訪談頁欄標變體、資訊區多欄位動態列數（真書內容驅動，自擬示範兩欄位）。

**下個 Sprint 預定範圍**：C 個案扉頁欄位卡片已完成，C 主版（slot 0 欄標／slot 1 大標／資訊區欄位卡片）建模齊備。GAPS #13 剩項＝F 版權頁真實版心 p178（Owner 本機量測）、目錄摘要層／【結語】變體、部扉裝飾框（美術資產待向量置入機制）、B~G 其他扉頁逐頁量測；或轉 Phase 2（WYSIWYG 編輯器，Spike 10 已驗畫布可行）。建議 Owner 指示下一優先。
