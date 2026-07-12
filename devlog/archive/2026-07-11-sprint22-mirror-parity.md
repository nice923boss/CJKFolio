# Sprint #22（2026-07-11）鏡像側別與真書對齊（正確性修正），已完成

**範圍**：原定 E 序文版頁型；序文頁探測中發現**鏡像側別與真書相反**
（Sprint 12 引入的判定基準錯誤），依「正確性優先於新功能」改本範圍，
E 序文版順延。honest-planning R6 pre-mortem 先行
（spikes/spike15-mirror-parity/premortem.md）；R2 判定不需新 PoC spike
（純語意修正，風險在覆蓋面，以測試矩陣控制）。

**發現經過**：量測序文頁（p004）時，左半頁頁碼實測「007」（奇數），與
Sprint 20「左半＝偶數頁」記錄矛盾，追查後三向互證定案。

**一手量測（A 級三向互證）**：
- **頁碼側**（四 spread：PDF 索引 4/12/30/40）：右半頁碼 008/024/060/080
  皆在書口右（x 789.5）；左半頁碼 009/025/061/081 皆在書口左（x 36.9）。
- **書眉側**：書名「內在整理」（手札體）皆右半（偶頁）；章節副標
  （推薦序＋作者名等）皆左半（奇頁）。
- **版心側**：偶頁（書頁 32）右邊距 21.00mm＝outer 精確、左邊距 25.58mm＝
  inner 精確；奇頁（書頁 25）左邊距 21.40mm≈outer。
- 結論：**偶數頁＝右頁（書口右）、奇數頁＝左頁（書口左）**。右翻直排書
  spread＝（偶右、奇左），讀序右→左＝頁碼小→大。Sprint 12 的「奇右偶左」
  為西式左翻書慣例誤植；其「與真書一致」比對記錄錯誤（當時測試與實作
  同源同錯，矩陣未攔截）。

**完成**：
- ✅ render [實作]：`is_right_page` 單一事實來源；`line_axis_x_pt`／
  `horizontal_left_x_pt`／render `_draw_footer`／pdf `_footer` 共 5 判定點
  收斂；footer 奇偶 gate（pages 配置）與書口側別拆分；mirror=false 恆以
  outer 槽為起排側（直排 B＝右、橫排 F＝左，兩者幾何不變）。
- ✅ 模版 [實作]：A 書名書眉 pages odd→even；F margins outer↔inner 對調
  （outer 25.81＝p178 左頁書口名實相符、inner 21.0 承 A 自擬），evidence
  補側別依據。
- ✅ 測試 [實作]：奇偶矩陣第二次翻轉（TDD：翻轉即 RED 親證 3 failed 後
  GREEN）：line-axis／footer／body-axis（render＋pdf）／page-selection／
  styles footer spec；橫排幾何斷言改 outer 語意。
- ✅ 勘誤 [Doc]：§10 Sprint 12 決議依據欄、GAPS #16 警示、#13 部扉
  「偶數頁」→ 奇數頁（37/137/229）、§1 補側別事實、新增 GAPS #20（關閉）。

**測試成長**：186 → 186（0 新增：修正型 Sprint，翻 6 個側別測試＋
改 2 個橫排語意斷言）。0 失敗、0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py
  spikes/spike10-canvas-sync/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：186 passed / 0 failed
- 真實素材驗收（R5）：
  - 第一章 --first-page 20（out/ch1-s22/）**Read 親驗兩頁**：page-001
    （書頁 20 偶＝右頁）章名行起書口右、頁碼＋書名書眉右下；page-002
    （書頁 21 奇＝左頁）頁碼左下、無書眉。與真書 spread 逐項一致。
  - CIP 樣張（out/cip-s22/）**PyMuPDF 複驗**：框 x0 68.11 vs p178 量測
    68.10（差 0.01pt）＝F 對調＋語意翻轉雙重抵銷，幾何不變如預期。
  - toc 樣張（out/toc21/ 重生成）**Read 親驗**：book 1（奇＝左頁）行軸
    改自訂口側起排，嵌線斷開跟隨行槽正確移動，版面完整。
- 同類掃描（Gate 3）：`grep "% 2"` 全庫僅剩 pdf_writer subset_tag（雜湊，
  無關）與新語意判定點；5 判定點全數收斂至 is_right_page。

**代決事項（記入 PLAN §10）**：側別修正即刻生效（正確性無退路）；
mirror=false 語意統一「outer 槽＝起排側」；footer gate 與側別拆分。

**落差登記**：GAPS 新增 #20（已關閉）；#16 加警示；#13 部扉側別勘誤。

**下個 Sprint 預定範圍**：候選：(a) E 序文版頁型（本 Sprint 探測已起頭：
內文承 A、標題 NotoSans 12.9、裝飾「─」楷 W5 16.3 單字元、微斜小勾線屬
美術資產）；(b) 抽取工具目錄模式；(c) 目錄「章名條目黑 W5」樣式層；
(d) TW-Kai 入庫（**需下載，須 Owner 同意**）。Owner 抽檢項累計：Spike 1
對比圖（#10）、斷行逐行一致率、Spike 10 對位樣張、out/cip19 與 p178、
out/part20 與真書部扉、out/toc21 與 p003、**out/ch1-s22 側別與實體書覆核**。
