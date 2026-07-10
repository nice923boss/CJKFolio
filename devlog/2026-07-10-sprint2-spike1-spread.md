# Sprint #2（2026-07-10）Spike 1 直排引擎核心與真實跨頁樣張，已完成（待 Owner 抽檢一項）

**範圍**：devlog #1 接續指引三步：參考書跨頁抽取與抽序驗證、逐字斷行＋禁則引擎（TDD）、版心定位＋頁腳＋跨頁樣張與並排對比圖。

**完成**：

- ✅ 參考跨頁抽取與量測（commit 見本篇末）[實作]：extract_reference.py 選出 p.030-031（index 15，內文 624 字＋GillSans 頁碼），**抽取順序 == 直排閱讀序（右至左、上至下）驗證通過**；量測行距精確 23.0pt、天頭 32.49mm（與 PLAN §1 相符）。產出 assets/reference/{reference_page.json, measurements.json, reference_page.png}（版權紅線目錄，不入 repo）。
- ✅ 校準分析 [實作]：analyze_reference.py 逐字座標分析。**重大修正：滿行 32 字（PLAN 原記「約 22 字」實為每頁行數）**；字距 12.08pt（字級 1.05 倍）；段首縮排 24.4pt≈2 字；段間空 1 行槽（46pt）；每頁 13 行槽；本書無半形標點擠壓（字距分布主峰 12.1pt×515，無 6pt 峰），僅 ±0.4pt 齊行微調；「？」由 PMingLiU 排、頁腳書名亦為系統字型（參考書自身即混用）。已回寫 PLAN §1 與 §10 決議紀錄。
- ✅ 直排引擎 vertical_engine.py [實作]：正規化（直排表現形 ﹁﹂→「」等 34 組映射）、tokenize（cjk／tcy／latin／space，1〜2 位數字縱中橫、長串拉丁不拆轉 90 度）、break_paragraph（行首禁則追出、行尾禁則退行、追入 fallback、死循環防護）、check_kinsoku、flow_pages（縮排、段間空槽、跨頁、續段不縮排）。TDD：先寫 15 項測試（RED：ModuleNotFoundError）→ 實作 → **15 passed 0 failed（GREEN）**。測試素材全自擬，無參考書文字。
- ✅ 跨頁樣張與對比圖 [實作]：render_spread.py 以實測網格排出全跨頁。重建 5 段 628 字（內文＋PMingLiU 標點併流、排除段距槽空白 artifact）；流排 2 頁 22 行，**與參考頁行數完全一致**；行長分布 32×14、31×4（禁則追出）、短行 4；**真實素材 runtime 禁則檢查 0 違規**。頁腳三件組以實測座標繪製（Gill Sans MT／標楷體替位，GAPS #8）。
- ✅ 縱中橫示範條 [實作]：tcy_demo.py（自擬文字）。「12」「8」直立橫排、「2026」「HarfBuzz」順時針轉 90 度、禁則 0 違規。

**測試成長**：0 → 15（+15：normalize 1、tokenize 5、斷行 2、禁則 5、流排 2），0 失敗 0 退步。

**驗證**：
- typecheck：python -m py_compile spikes/spike1-vertical-core/*.py，EXIT_CODE=0
- test：15 passed / 0 failed
- 真實素材驗收（R5）：《內在整理》p.030-031 全跨頁 628 字經自製引擎排版；Read 親驗 spread_comparison.png（上參考、下樣張）：段落起訖、縮排、段間距、行序頁序、頁腳位置全對齊；tcy_demo.png 縱中橫正確。**Owner 人工抽檢待補（GAPS #10），Spike 1 關閉前提。**
- 已知偏差（誠實標示）：斷行點 ±1 字漂移（等距網格 vs 齊行，GAPS #9）；頁腳字形替位（GAPS #8）；PMingLiU 筆畫較華康明體細（字型替位固有，GAPS #3）。
- Spike 1 驗收檢核清單：7 項中 6 項打勾，「並排對比圖＋人工抽檢」半項待 Owner。

**留證**：
- 時戳：2026-07-10
- 樣本：spikes/spike1-vertical-core/out/{spread_sample.png, spread_comparison.png, tcy_demo.png}（含參考書內容，僅本機）
- commit：0c99541（root commit，13 檔 1575 行；hash 於提交後回填）

**下個 Sprint 預定範圍**：Spike 2a 輸出後端（Vivliostyle）：npm 安裝 @vivliostyle/cli，以自擬／自由散布文本走 CSS 直排產 PDF，pdffonts／qpdf preflight，比對直排品質與字型嵌入；若時間盒內有餘，啟動 Spike 4 授權桌面研究（盒 2 天）。
