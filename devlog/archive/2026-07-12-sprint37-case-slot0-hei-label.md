# Sprint #37（2026-07-12）C 個案扉頁 slot 0 黑 W7 欄標樣式建模（Owner 定案升級 C），已完成

**範圍**：Owner 於 Sprint 36 收尾 AskUserQuestion 定案「升級定案 C」（完整重定 C 主版，推翻
Sprint 35「選 B 不重定模型」），正式啟動 Sprint 35 揭露的最複雜後續。GAPS #13 黑 W7 欄標專項：
slot 0（cx 354，Sprint 35 揭露＝DFHeiStd-W7 欄標非個案中標）建模為新段落樣式。依 honest-planning
R1／R5，先用臨時探針量測 C 個案扉頁完整幾何，找到真實目標才建模；資訊區多欄位佈局若複雜拆
Sprint 38（Owner 預授權「逐 Sprint 收斂，不一次吞完」）。

**根因（Sprint 37 A 級量測）**：臨時探針量測參考書《內在整理》交印檔（本機，紅線不入 repo）33 個案
扉頁全欄結構（cx 由書口右→左聚列）＋聚合統計，確定 C 個案扉頁真實佈局：
1. **slot 0 欄標（cx 354.6）**：DFHeiStd-W7，首字頂 92.1＝天頭 92.09（承 A），縱向 4~6 字佔 block
   slot 0 一行；size 11.5pt×26 頁（資訊頁「個案資料／廖心筠整理師」等）主流、10.5pt×7 頁（訪談頁
   「理解與祝福」）變體。字框頂在天頭、墨頂差為字型 bearing（lead_offset 0，同部扉／大標先例）。
2. **slot 1 大標（cx 331.6）**：NotoSans 17.9pt，首字頂 98.0（33 頁齊一）＝天頭＋字型 bearing 5.9pt。
3. **資訊區（cx 93~231＝slot 5~11）**：欄位標籤（NotoSans 11.4pt「【格局】【居住者】」天頭 92.3 起）
   ＋內文（DFMingStd 11.5pt 縮排 2 字 top 116.5）＋13pt DFHeiStd 中標交替；**slot 2~4 空欄**。列數
   4~7（衆數 6），資訊區 11.4pt 出現 10 頁、13pt 出現 9 頁。

**架構判定**：slot 0 欄標與 slot 1 大標都自 inline 天頭起、block 軸相鄰堆疊（slot 0→1），現有單欄
線性流排（engine.flow_pages）可表達，本 Sprint 建模。資訊區（slot 5+ 欄位標籤／內文交替、slot 2~4
空欄）為空間分區，超出線性堆疊需新機制，拆 Sprint 38（與 Owner 建議吻合）。

**完成**：
- ✅ templates/neizai-zhengli.json [實作]：新增段落樣式 個案欄標-黑W7（思源黑體 Bold 11.5pt、
  indent 0、para_gap 0、lead_offset 0、source_font DFHeiStd-W7），note 記 A 級量測參數（cx 354、
  天頭 92.09、11.5×26／10.5×7 變體、W7＝Bold 不 fallback）；C 主版 evidence 更新「slot 0 已建模」。
- ✅ samples/case-divider.doc.json [實作]：slot 0 個案中標→個案欄標-黑W7（自擬「案例速寫」），
  個案中標移出（真實位置＝資訊區，Sprint 38）。
- ✅ tests/test_styles.py [實作]：新增 test_case_hei_label_style_modeled 守門（font bold／11.5pt／
  indent 0／para_gap 0／lead_offset 0／source_font DFHeiStd-W7、與個案中標分離）；段落樣式數 17→18。
- ✅ tests/test_layout_render.py／test_pdf_writer.py [實作]：case-divider slot 0 測試改欄標（layout
  slot [0,1,2] 欄標／大標／內文、line_axis 欄標 354.25＋大標 331.25；PDF 字墨扣出血後＝各自 line_axis）。

**測試成長**：217 → 218（新增 test_case_hei_label_style_modeled 欄標守門）。0 失敗 0 退步。

**驗證**：
- typecheck（py_compile spikes／cjkfolio／tools）EXIT=0；test 218 passed／0 failed。
- 真實素材驗收（R5，建模 Sprint 非純守門）：render case-divider PNG（first-page 20 偶＝右頁）
  ＋export PDF＋preflight。欄標渲染用 SourceHanSansTC-Bold（W7→Bold 不 fallback，字型使用訊息證）、
  0 禁則違規、preflight 12/12。
- Gate 4 獨立驗證：render PNG 墨跡三直行 trim_cx（程式化墨跡分析，視覺 Read 因 context limit elided）
  ＝欄標 354.2／大標 331.2／內文 308.2，精確吻合模型 line_axis 354.25／331.25／308.25（slot 0/1/2，
  差 0.05pt）；欄標 y頂 32.68mm＝天頭（4 字縱向 y底 48.94mm＝4×11.5pt 佔 block slot 0 一行）；3 直行、
  無 notdef 爆量黑塊。兩後端 parity：PDF 側 test_case_ttb_ink_centered_on_line_axis 欄標 slot 0 字墨
  扣出血＝axis_label 354.25，與 PNG 側 354.2 同源。量測（PyMuPDF span cx／top）＋守門（模版載入斷言）
  ＋渲染（PNG 墨跡幾何）三方法互證。
- Gate 3 同類掃描：slot 0 建模屬 C 主版；grep 確認模版 note／C evidence／PLAN §10／GAPS #13 四處 slot 0
  描述均已更新為「已建模」，無遺漏。
- 繁中標點：grep 本 Sprint 改動檔（模版／樣張／三測試／PLAN／GAPS／devlog／CHANGELOG）無破折號殘留。

**代決事項（記入 PLAN §10）**：Owner 定案升級 C（完整重定 C 主版，推翻 Sprint 35「不重定模型」）；
slot 0 黑 W7 欄標建模為 個案欄標-黑W7（思源黑體 Bold 11.5pt、天頭起、para_gap 0）；主流 11.5pt 建模、
10.5pt 訪談頁變體記錄；個案中標移出 slot 0。render PNG cx 354.2＝line_axis、preflight 12/12、兩後端
parity。

**落差登記**：GAPS #13「黑 W7 欄標樣式建模」子項由「後續專項」更新為「Sprint 37 已建模」；資訊區
多欄位佈局（slot 2~4 空欄＋slot 5~11 欄位標籤／內文／13pt 中標交替，線性堆疊不可表達需新機制）
＋個案中標移資訊區為 Sprint 38 專項。

**下個 Sprint 預定範圍**：Sprint 38 資訊區多欄位佈局（承本 Sprint 量測：slot 5~11 欄位標籤 NotoSans
11.4pt「【格局】【居住者】」＋內文 DFMingStd 11.5pt 縮排＋13pt DFHeiStd 中標交替、slot 2~4 空欄），
需新佈局機制（線性堆疊不可表達空間分區）＋個案中標移入資訊區；建議先量測資訊區完整欄位結構（標籤／
內容相對位置、行距、欄寬）再定機制範圍（同本 Sprint R1 先量測），複雜度高可再拆分逐 Sprint 收斂。
