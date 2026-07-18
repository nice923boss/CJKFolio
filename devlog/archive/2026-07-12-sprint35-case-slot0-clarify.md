# Sprint #35（2026-07-12）個案扉頁 slot 0「Case 編號 13pt 雙元素」量測否決＋Sprint 25 誤讀勘正，已完成

**範圍**：候選 A（Owner「最複雜架構先做」常設指令）＝個案扉頁 slot 0「Case 編號黑 W5
13pt『01』雙元素」建模（engine／layout／render／pdf 四層＋兩後端 parity）。依 honest-planning
R1／R5（先量測再動工、不憑空造 pt 目標），用臨時探針量測參考書確認 Case 編號真實位置（現有
`tools/measure_case_page.py` 的 `case_no` 抓 Pepita 頁腳、非資訊列 Case 編號，須新量測）。

**根因（Sprint 35 A 級量測）**：兩路臨時探針量測參考書《內在整理》交印檔（本機，紅線不入
repo）33 個案扉頁，交叉驗證推翻候選 A 前提：
1. 第一探針（頁頂區 span 逐一分布）：slot 0（cx 354.59，最靠書口那直行）8 頁詳列全是
   DFHeiStd-W7，無 NotoSans 11.4、無 13pt。
2. 第二探針（四問決定性交叉驗證，避免 Sprint 22 式同源同錯）：
   - **Q1 slot 0（cx 354.25±8）跨 33 頁聚合**：DFHeiStd-**W7** 11.5pt×26 頁／10.5pt×7 頁欄標
     「欄標甲／欄標乙／欄標丙／欄標丁／欄標戊」，33 頁全覆蓋，0 個 NotoSans
     11.4、0 個 13pt。
   - **Q2 個案中標 NotoSans 11.4pt**：141 span，cx 全落 93~231（median 230.94），完全不在
     slot 0（354），在資訊區內文欄。
   - **Q3 DFHeiStd 13pt**：132 span，cx 117~240（median 232），為資訊區內文中標「父母的留戀：
     物品中的情感」「初遇空間」等句子，非 slot 0 編號、非「01」。
   - **Q4 黑體與大字數字編號「01」**：全書 0 命中。真書 Case 編號＝頁腳 PepitaMT 9pt「Case 1／
     2／3」（top 508.3，33 頁齊備）。

結論：候選 A 前提徹底不成立。slot 0 無「Case 編號黑 W5 13pt『01』」雙元素，那是 Sprint 25 把
**頁腳**的 Case 編號誤植到 slot 0＋臆造字型級數（黑 W5 13pt）。連帶揭露 Sprint 25 對 C 主版
slot 0 的系統性誤讀：slot 0 實為黑 W7 欄標、個案中標 11.4pt 實在資訊區（cx 93~231）非 slot 0。
Sprint 25 量對了 slot 0 位置（354）與大標 slot 1（331），卻把 slot 0 內容認錯（黑 W7 欄標誤為
11.4pt 副標）並漏建模真正的資訊區個案中標。**第四例掃描誤讀（承 Sprint 23 署名長橫、24 摘要層
字型、34 的 12.9pt），最深（推翻 Sprint 25 C 主版 slot 0 建模）。**

**Owner 定案（AskUserQuestion）**：B（勘正記錄＋守門，不重定模型）。理由：完整重定牽涉新增黑 W7
欄標樣式、個案中標移資訊區、資訊區多欄位佈局量測（多 Sprint 工程），單 Sprint 硬推翻核心決議有
同源同錯風險。誠實記錄量測真相＋守門防復現，模型重定登記後續專項。

**完成**：
- ✅ tests/test_styles.py [實作]：新增 `test_case_info_distinct_from_slot0_hei_label_and_case_no`
  守門：個案中標 source_font==NotoSansCJKtc-Medium、font_weight==medium、size==11.4，且
  !=11.5／10.5（防併入 slot 0 黑 W7 欄標）、!=13.0（防併入虛構 Case 編號）。docstring 記
  Q1-Q4 量測結論。
- ✅ templates/neizai-zhengli.json [實作]：個案中標 note＋C-個案扉頁 evidence 兩處 slot 0 錯誤
  描述勘正，記錄量測真相（slot 0＝黑 W7 欄標、個案中標在資訊區、Case 編號在頁腳 Pepita、13pt
  為資訊區內文中標）；否決「Case 編號黑 W5 13pt『01』雙元素」。size 11.4 不動、para_gap_slots 0
  為 status-quo（Owner 定案 B）。
- ✅ 不改渲染／layout 幾何／case-divider 樣張（Owner 定案 B，同 Sprint 26／34 勘正非修碼）：不
  重定模型，兩後端 parity 不受影響。

**測試成長**：215 → 216（test_styles 28→29，新增字型與級數守門）。0 失敗 0 退步。

**驗證**：
- typecheck（py_compile spikes／cjkfolio／tools）EXIT=0；test 216 passed／0 failed。
- 真實素材驗收（R5）：兩路臨時探針 33 個案扉頁一手量測（Q1-Q4 決定性交叉驗證）；探針跑完即刪
  （scratchpad，參考書內容紅線不入 repo）。
- Gate 4 獨立驗證：量測（PyMuPDF get_text span cx／top／font／size）與守門測試（模版載入斷言）
  不同方法互證；Q4「01」全書 0 命中＋Q1 slot 0 黑 W7 33 頁全覆蓋為決定性反證（非單點推論，避免
  Sprint 22 同源同錯降級）。
- Gate 3 同類掃描：slot 0 誤讀屬 Sprint 25 C 主版建模問題；grep 模版確認 note 與 evidence 兩處
  slot 0 錯誤描述均已勘正，無遺漏。
- 繁中標點：grep 本 Sprint 改動檔（模版／GAPS／PLAN／devlog／CHANGELOG／test_styles）無破折號
  字元殘留。

**代決事項（記入 PLAN §10）**：候選 A slot 0 Case 編號 13pt 雙元素量測否決（0 命中）；Sprint 25
slot 0 誤讀勘正（slot 0＝黑 W7 欄標、個案中標在資訊區、Case 編號在頁腳）；Owner 定案 B 勘正記錄
＋守門，不改 size／幾何／模型（現狀 size 正確，同 Sprint 26／34）。

**落差登記**：GAPS #13 加「slot 0 Case 編號黑 W5 13pt『01』雙元素」否決子項（釐清為不存在，
真書 Case 編號在頁腳 Pepita）。後續專項（需 Owner 決定投入，屬定案 C 範圍）＝黑 W7 欄標樣式建模
＋個案中標移資訊區＋資訊區多欄位【標籤】佈局量測。

**下個 Sprint 預定範圍**：旁注 9pt／Case 編號 15.9pt 變體量測釐清（Sprint 34 Gate 3 掃出同類
待查標記，候選 B，同釐清型）；或黑 W7 欄標樣式建模（本 Sprint 揭露的後續專項，屬定案 C 需 Owner
確認範圍）；或噪音移除軌（PLAN §6 Sprint 6-16 verbose 收斂為指標，動前向 Owner 確認範圍，候選 C）。
