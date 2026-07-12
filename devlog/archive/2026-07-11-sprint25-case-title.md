# Sprint #25（2026-07-11）C 個案扉頁大標置位一手量測＋直排墨偏移發現，已完成

**範圍**：GAPS #13 B〜G 頁型系列：C 個案扉頁（§4.2 主版 7 種中 C 尚未量測）。
比照 Sprint 20 部扉大標置位模式。R1 證據先行、R2 判定不需新 spike（既有機制
參數化）。

**一手量測（A 級，數十頁互證，tools/measure_case_page.py）**：
- 個案扉頁在右半頁（偶數＝右頁）。個案大標＝NotoSansCJKtc-Medium 17.9pt、首字
  墨頂 top 98.05、字距 18.36pt（數十頁完全同值）。
- 完整佈局（PDF 20 Case 1，probe 逐列）：
  - slot 0 資訊列：Case 編號「01」DFHeiStd-W5 13pt＋副標 NotoSans 11.4pt。
  - **slot 1 個案大標** NotoSans 17.9pt。
  - slot 2+ 內文 DFMingStd-W3 11.5pt（首字 top 145.75）。
- 版心承 A 一手驗證：內文天頭 92.09pt=32.49mm、扉頁內文首行縮排 116.47=
  92.09+2×12.08、內文自 slot 2 起。
- 大標 slot 1 右頁 line_axis 331.25 貼真書大標墨欄中心 331.28（差 0.03pt）；
  真書大標墨 cx 750.81（整頁）＝slot 1 欄中心 750.78，證實真書行軸置中 slot 1。

**完成**：
- ✅ 工具 [實作]：tools/measure_case_page.py（掃描定位個案扉頁＋量大標列
  行軸／字距／版心／Case 編號）。
- ✅ 模版 [實作]：C 主版 evidence 由「未量測」升級為一手量測（承 A 驗證＋
  大標 slot 1＋資訊列/內文/Case 編號佈局）；個案中標 para_gap 1→0 勘誤
  （實測資訊列 slot 0 與大標 slot 1 相鄰，同 Sprint 20 標籤先例）。
- ✅ 樣張 [實作]：samples/case-divider.doc.json（自擬副標＋大標，紅線不取
  真書文字）。
- ✅ 測試 [實作]：C 承 A＋大標 slot 1 line_axis（TDD RED→GREEN）。

**測試成長**：189 → 190（+1）。0 失敗、0 退步。

**驗證**：
- typecheck：EXIT_CODE=0；test：190 passed / 0 failed
- 真實素材驗收（R5，樣張自擬）：render PNG（out/case25，--first-page 2 右頁）
  Read 親驗資訊列 slot 0＋大標 slot 1（黑體級數區隔）＋頁碼書口右；export PDF
  preflight 12/12、字型 SourceHanSansTC-Medium 無 fallback。
- **Gate 4 閉環抽驗發現重大問題（GAPS #21）**：PyMuPDF 抽 case.pdf，大標
  layout slot 1（line_axis 331.25＝真書 331.28 ✓）；但**PDF 字墨 cx 339.75，
  偏 line_axis 欄中心 +8.5pt**。get_texttrace 深挖：資訊列 11.4pt 與大標 17.9pt
  墨 cx 皆偏 +8.50（與字級無關），真書華康大標墨 cx＝欄中心（差 0.03）。即
  產品右頁直排字墨系統性偏書口 8.5pt，真書墨置中欄中心。

**根因與範圍（誠實記錄）**：pen_x＝line_axis 欄中心，但字墨 bbox cx＝pen＋
約 8.5pt；兩後端同源（PNG/PDF 一致）故 parity 未攔截；過往 Sprint 只驗 layout
axis（同源）或 Read PNG（8.5pt≈3mm 視覺不明顯）故未暴露；Sprint 23 左頁序文
墨 cx≈推導未見同偏移（疑右頁側別相關或推導口徑差）。此為**全直排既有正確性
問題**，非 Sprint 25 引入、非單一頁型；C 大標 layout slot 1 置位本身正確。

**代決事項（記入 PLAN §10）**：C 大標 layout 交付保留（layout 定位正確）；
個案中標 para_gap 勘誤（實測相鄰）；資訊列雙元素（Case 編號 13pt）、內文精確
gap、雙線框 v1 不建模；**直排墨偏移不在本 Sprint 硬修**（context 保護，全直排
回歸屬專項，避免 Sprint 22 式同源同錯降級）。

**落差登記**：GAPS #13 C 個案扉頁量測完成；**GAPS #21 新增（直排墨 cx 偏移，
正確性問題專項）**。

**下個 Sprint 預定範圍（強烈建議）**：**專項調查並修 GAPS #21 直排字墨偏移**
（依 Owner「正確性優先於新功能」，優先於 D〜G 其他新頁型）：確認左右頁對稱性
（Sprint 23 左頁 vs Sprint 25 右頁）、根因（placement ttb 水平 origin vs
line_axis −base/2 補償）、全直排座標回歸。次選：抽取工具目錄模式、G 圖文版。
Owner 抽檢項累計：…out/toc24 章名黑 W5、**out/case25 個案大標 slot 1（並注意
直排墨偏移 GAPS #21）**。
