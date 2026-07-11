# Sprint #33（2026-07-12）個案大標 para_gap 樣式拆分（個案扉頁 vs 內頁 h2），已完成

**範圍**：Sprint 32 預定範圍第二項（GAPS #13 剩項）：`個案大標-NotoSans`（para_gap 1）
身兼 C 個案扉頁大標與 md h2／內頁大標（42 頁）兩用途。扉頁大標後接內文應相鄰落
slot 2（Sprint 25 A 級量測：資訊列/大標/內文 三列相鄰），但 para_gap 1 使內文落
slot 3。拆為兩物件樣式（InDesign 慣例：同視覺角色、不同段後距＝不同段落樣式）。

**根因（Sprint 25 A 級量測＋Sprint 31 軸澄清）**：block 軸（段落堆疊＝行軸方向）為整數
槽對齊，扉頁三列 slot 0/1/2 相鄰＝各段 para_gap 0。個案大標 para_gap 1 是唯一使內文
下移一槽的來源。此為整數槽差（非 sub-slot pt 偏移，別於 Sprint 29/30 inline 軸）。

**完成**：
- ✅ templates/neizai-zhengli.json [實作]：新增段落樣式 `個案扉頁大標-NotoSans`
  （思源黑體 Medium 17.9pt、para_gap 0）給 C 扉頁大標；`個案大標-NotoSans`（para_gap 1）
  保留給 md h2／內頁大標（42 頁不動）。C 主版 evidence 移除已修的 para_gap「已知差異」
  子句，改記 Sprint 33 修正。
- ✅ samples/case-divider.doc.json [實作]：大標改用 個案扉頁大標-NotoSans，加自擬內文段
  （紅線安全）忠實呈現扉頁三列（資訊列/大標/內文）。
- ✅ tests/test_layout_render.py：擴充 test_case_master_and_title_placement 覆蓋 body slot 2
  ＋守門（扉頁大標 para_gap 0、內頁 個案大標 para_gap 1、h2 對映不動）。
- ✅ tests/test_pdf_writer.py：C 扉頁 ink-centering 測試大標樣式對齊為 個案扉頁大標。
- ✅ tests/test_styles.py：段落樣式數守門 16→17。

**測試成長**：214 → 214（未新增 test 函式；擴充既有 case 扉頁測試覆蓋 body slot 2＋
para_gap/h2 對映守門，樣式數守門 16→17，pdf 扉頁測試樣式對齊）。0 失敗 0 退步。

**驗證**：
- typecheck（py_compile spikes/cjkfolio/tools）EXIT=0；test 214 passed / 0 failed。
- 確定性 layout（committed 樣張 samples/case-divider.doc.json）：三段 slot＝[0,1,2]、
  0 禁則違規（修正前內文為 slot 3）。
- 真實素材驗收（R5）：目標 slot 2＝Sprint 25 真書 A 級量測（內文承 A 自 slot 2）；
  紅線內容不入 repo，驗證用自擬扉頁 doc＋確定性 layout（同 Sprint 13〜16 慣例）。
  render PNG（150dpi、--first-page 2 偶＝右頁）Read 親驗：三直排列右至左相鄰，內文緊貼
  大標左側（slot 2，非 slot 3 空欄），三列共頂邊（承 A），字型 思源黑 Medium（中標/大標）
  ＋思源宋 Regular（內文）、0 禁則違規。
- 同類掃描（Gate 3）：grep 全 tests/ 樣式數量斷言僅 test_styles 一處；個案大標 殘留引用
  皆為刻意保留的 h2／內頁守門（正確）。

**代決事項（記入 PLAN §10）**：拆分方向為「新增扉頁專用樣式、保留原名給 h2」（非改
md_mapping）：md h2 → 個案大標-NotoSans 不動，test_styles/test_md_import 對 h2 對映的守門
不受影響，churn 最小。內頁 h2 para_gap 1 為保留現狀（非新量測宣稱），入 GAPS 誠實記錄。

**落差登記**：GAPS #13 關「扉頁大標 para_gap（slot 2）」子項；內頁 h2 para_gap 1 為
status-quo 未逐頁量測，續留 #13（誠實記錄）。個案中標 11.4/12.9pt 兩變體、slot 0 Case
編號 13pt 元素、雙線菱形框（美術資產不生成）仍為 #13 剩項。

**下個 Sprint 預定範圍**：個案中標 12.9pt 變體釐清（須量測，避免無目標）；或 B〜G 其他
扉頁剩項；或噪音移除軌（PLAN §6 Sprint 6〜16 逐段進度與 §10／devlog 重複，可精簡為
指標；GAPS 已關項的長篇 strikethrough 歷史）。
