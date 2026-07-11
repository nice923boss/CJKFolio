# Sprint #19（2026-07-11）F-版權頁真實版心 p178 量測，已完成

**範圍**：GAPS #13 (a)：F-版權頁真實版心（p178）量測，把 Sprint 13〜14 的自擬
幾何升級為 A 級一手量測參數。紅線內作業：量測參數入模版（Sprint 15 D-目錄
先例）、內容與量測 JSON 不入 repo。honest-planning R6 pre-mortem 先行
（spikes/spike12-cip-metrics/premortem.md），量測方法全為既有能力（get_text
dict＋get_drawings），無新 PoC spike。

**一手量測（A 級，p178＝PDF 頁索引 177 跨頁左半、tools/measure_cip_page.py）**：
- CIP 框：**5 段線折線閉合**（非 re 矩形）、線寬 **0.141pt**、色 **暖黑
  #231f20**（同內文 → 產品單 K92）；單頁座標 x0=68.10、y0=118.31、
  x1=209.69、y1=201.19。
- CIP 文字：**5.63pt 單一字級**（31 spans 全同）、字距 5.66pt（7 行樣本均值，
  ≈級數×1.005）、主體行距 **7.74pt**（前 5 行等距）；**後段 3 行行距分區
  12.73／11.73pt**（premortem 預見情形，v1 單一 pitch 不表達，入 GAPS）。
- pad 不對稱：水平 5.05／垂直（baseline 錨定口徑）4.94pt。
- 框上方另有 CIP 標題行（明體＋Times 各 span，距框頂約 9.5pt）：v1 不區分
  框內外行，入 GAPS。
- top 錨定決策：以首行 baseline 128.2pt 反推 top＝128.2−5.63×0.88＝123.25pt
  ＝43.48mm（文字位置優先；bbox 口徑會差 0.9pt）。

**完成**：
- ✅ tools/measure_cip_page.py [實作]：p178 量測工具（折線框重建、框內 spans
  統計、半邊判定；輸出本機 JSON）。除錯紀錄：首輪只認 `re` 矩形 → 實測框為
  5 段 `l` 折線，改端點聚合重建 bbox。
- ✅ styles [實作]：`FrameSpec.pad_v_pt`（選配，None＝同 pad_pt）＋解析；
  primitives `cip_frame_rect` 不對稱 pad（TDD：RED 3 項先行親證）。
- ✅ 模版 [實作]：F-版權頁 margins（top 43.48、inner 25.81mm）＋grid（23 字
  ／45 行／5.66／7.74／5.63）＋frame（0.14pt、K92、5.05×4.94）；樣式
  「版權頁-CIP橫排」8 → 5.63pt；evidence 全面改記量測依據與已知差異。
- ✅ 測試同步：寫死斷言 3 處改隨模版真值（test_master_frame_parsing 量測值、
  parity 測試字級改讀模版樣式、框描邊斷言 K92）。

**測試成長**：173 → 175（+2：frame pad_v 解析、cip_frame_rect 不對稱 pad）。
0 失敗、0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py
  spikes/spike10-canvas-sync/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：175 passed / 0 failed（`python -m pytest spikes tests -q`）
- 真實素材驗收（R5，樣張自擬）：samples/cip-copyright.doc.json 以量測後模版
  重排 →
  - render PNG（out/cip19/page-001.png，300dpi）**Read 親驗**：密排 CIP（5.63pt
    視覺明顯較舊 8pt 密）＋細框圍住 7 行、框位置頁頂約 42mm、無異常。
  - export PDF preflight **12/12 全綠**；禁則 0 違規。
  - **閉環獨立抽驗（Gate 4）**：PyMuPDF 抽樣張框左上角 **(68.11, 118.31)**、
    首行 baseline **128.2**、字級 5.63、線寬 0.14，與 p178 實測 **(68.10,
    118.31)／128.2** 精確重合（0.01pt 內）；框右緣差 1.3pt（滿行網格推導）、
    框底差異（樣張行數不同＋分區行距）皆已知已記錄。

**代決事項（記入 PLAN §10）**：top 以 baseline 錨定換算；框色暖黑 → 單 K92；
pad_v_pt 選配欄位；lines_per_page 45 為幾何推導非量測；行距分區與框上標題行
不擴 v1 模型，入 GAPS。

**落差登記**：GAPS #13 (a) 關閉（改記 v1 已知差異：行距分區、框上標題行、
框寬 1.3pt）。

**下個 Sprint 預定範圍**：候選：(a) B 部扉頁型（大標置位，部扉頁量測）；
(b) E 序文版頁型；(c) 抽取工具目錄模式；(d) TW-Kai 入庫（**需下載，須 Owner
同意**）。Owner 抽檢項：Spike 1 對比圖（GAPS #10）、斷行逐行一致率、
Spike 10 對位樣張、本 Sprint out/cip19 與真書 p178 並排比對。
