# Sprint #20（2026-07-11）B 部扉頁型大標置位（三部扉量測），已完成

**範圍**：GAPS #13 剩項：B 部扉頁型（大標置位；裝飾框依 Sprint 15 決議不做）。
honest-planning R6 pre-mortem 先行（spikes/spike13-part-divider/premortem.md）；
無新程式碼路徑（純模版參數化＋樣張＋測試），判定不需新 PoC spike。

**一手量測（A 級，PDF 索引 18／68／114 三頁互證完全同值）**：
- 大標（W9 21.9pt，7 字直排）：行軸中心 194.12pt、首字頂 182.86pt、字距
  23.1pt（＝21.9×12.08/11.5 換算規則精確吻合）。
- 部序號（W7 14.9pt，3 字）：行軸中心 228.49pt（大標右側＝直排先讀行）、
  首字頂 176.84pt、字距 15.75pt（換算 15.72，差 0.03）。
- 行距＝行軸差 34.37pt；部扉皆左半頁（偶數頁）、同半頁無頁腳。

**完成**：
- ✅ 模版 [實作]：B-部扉 margins（top 62.38、outer 63.53mm、mirror false）＋
  grid（10×8、23.1／34.37／21.9，比例網格自動涵蓋 W7）；「標籤-篇序小標」
  para_gap_slots 1→0（間距含於行距）；evidence 改記量測依據與已知差異。
- ✅ 樣張 [實作]：samples/part-divider.doc.json（自擬「第一部」＋自擬部名，
  紅線：不取真書部名）。
- ✅ 測試 [實作]：test_part_divider_layout_geometry（TDD：RED 親證後 GREEN；
  slot 0／1、行軸 228.49／194.12、天頭 176.84、字距 23.1、gap 0 全釘死）。

**測試成長**：175 → 176（+1）。0 失敗、0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py
  spikes/spike10-canvas-sync/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：176 passed / 0 failed（連跑三次全綠確認穩定）
- 真實素材驗收（R5，樣張自擬）：
  - render PNG（out/part20/page-001.png，300dpi）**Read 親驗**：部序號（右，
    小）＋部名（左，大）兩行直排、頁面中央偏上置位、字級層次分明、無頁腳，
    與真書部扉設計語言一致。
  - export PDF preflight **12/12**；字型警告不沉默（bold→heavy 替，GAPS #12）。
  - **閉環獨立抽驗（Gate 4）**：PyMuPDF 抽兩行軸中心 x＝**228.49／194.12**，
    與三部扉量測**精確重合（0.00pt）**。
  - y 向 bbox 口徑：抽出首字 bbox 頂 170.89〜172.79 vs 真書 176.84～182.86，
    差異屬思源（ascender 鬆）與華康（緊）字型度量差，非位置錯誤（渲染字槽頂
    由 margins.top 確定性控制；§3.3 不比字形輪廓）。
- 除錯紀錄：全套跑一次出現 test_export_horizontal_preflight_green 單次失敗，
  單跑／全檔／全套連三次複跑皆綠 → 判定一次性環境假信號（模版編輯與
  module-scope fixture 載入時窗），非程式碼回歸。

**代決事項（記入 PLAN §10）**：兩段行距全含於 B 行距（標籤 gap 0）；大標頂
6.02pt 差不擴段前 pt 偏移模型（v1 整數槽，Phase 2〜3 樣式系統再議）。

**落差登記**：GAPS #13 更新（B 大標置位完成；剩已知差異 6.02pt 記錄）。

**下個 Sprint 預定範圍**：候選：(a) E 序文版頁型；(b) 抽取工具目錄模式；
(c) 目錄頁型剩項（篇名嵌線斷開、條目縮退）；(d) TW-Kai 入庫（**需下載，須
Owner 同意**）。Owner 抽檢項：Spike 1 對比圖（#10）、斷行逐行一致率、
Spike 10 對位樣張、out/cip19 與 p178、out/part20 與真書部扉並排比對。
