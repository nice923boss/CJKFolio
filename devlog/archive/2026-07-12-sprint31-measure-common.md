# Sprint #31（2026-07-12）主軌否決（block 軸整數對齊無 pt 目標）＋轉替代軌 A：measure 工具共用模組，已完成

**範圍**：延續引擎 pt 精度模型，主軌為 para_gap block 軸 pt 精度（Sprint 25 個案扉頁
「內文精確 gap」）。honest-planning R1 證據先行、R8 不憑假設動工：先量測驗證主軌有無
真實目標。結論主軌無 pt 目標（block 軸本就整數槽對齊），依 Owner 預授權轉替代軌 A
（measure_*.py 共用模組抽出，順手移除噪音）。

**前置調查（主軌否決，A 級證據）**：
- 軸向釐清（Read engine／layout／render／styles）：`slot → line_axis_x_pt` 為 block 軸
  （段落堆疊＝水平欄位，右起左行）；`start_slot ＋ lead_offset_pt` 為 inline 軸（段內字流
  ＝縱向 top-down）。Sprint 29／30 的 pt 偏移皆 inline 軸。
- 主軌需 block 軸 sub-slot pt 目標。三線證據皆指整數槽對齊：
  1. C 主版 evidence 明載「大標 para_gap 1 使樣張內文落 slot 3 vs 真書 slot 2」，是整數槽
     差（para_gap 該 0 不是 1），非 pt 級。
  2. 既有量測：個案中標 cx 354.24 ＝ slot 0（恰）、大標 cx 331.28 ＝ slot 1（Δ0.03），皆
     整數槽；資訊列與大標無 sub-slot 殘差，故 Sprint 25 勘誤是乾淨整數（1→0）。
  3. 本機 probe 量 33 個案扉頁內文欄水平 cx：位置隨頁內容變動（gap/pitch 4.2〜6.0），
     無單一 para_gap_offset_pt 可模型化的固定殘差。
- 跨 sprint 佐證：部扉欄距 34.37 ＝ 1 pitch（整數）、序文 4.99 槽（0.9pt 歸因 inner margin
  非 para_gap）。block 軸一律網格對齊，藝術 sub-slot 偏移只現於 inline 軸。硬加無真實偏移
  可套的 para_gap_offset_pt 將違反 R5（無真實素材驗收），故否決主軌、不建該機制。

**完成（替代軌 A：measure 工具共用模組）**：
- ✅ tools/_measure_common.py [實作／新增]：抽 4 個 measure 工具重複的 `HALF_W`（419.53
  字面值，免捨入漂移翻動輸出）、`PT_PER_MM`、`spans`（回傳 list 供同頁多次篩選）、
  `is_spread`（半頁判定）、`reference_pdf`（PDF 路徑）、`write_measurements`（JSON 樣板
  ＋mkdir）、`stdout_utf8`；加 `BLEED_PT`／`strip_bleed`（Gate-4 model media→trim 換算正典
  helper，收斂 Sprint 24/25/30 出血口徑）。常數量測層自持（同 primitives.py 對 PT_PER_MM
  的「底層層各自持有免循環依賴」先例），不 import 產品層，保持工具輕量獨立。
- ✅ measure_cip／toc／case／figure_page.py [重構]：改 import 共用層；順手清 measure_toc／
  cip 未使用的 `PT_PER_MM` 死碼。4 檔 −62／+47 行（淨 −15 重複），行為零變更。

**測試成長**：214 → 214（重構行為保持；measure 工具非 pytest 基線，以 JSON 逐字 diff 驗證）。

**驗證**：
- typecheck（py_compile 全部）EXIT_CODE=0；test：214 passed / 0 failed（產品碼未動，0 退步）。
- **行為保持（Gate 4 獨立法）**：重構前跑現行 4 工具快照 JSON → 重構後刪輸出重跑 → 逐工具
  diff 對照快照，cip／toc／case／figure 全 **IDENTICAL**（0 差異）；4 工具 run 皆 exit 0。
  先刪輸出再重跑，避免工具失敗留舊檔造成假 identical。
- 紅線掃描：tools/ 全域無 em-dash；4 工具無遺留 `sys.stdout.reconfigure`／`ROOT`／
  `def _spans`／`json.dumps`。

**代決事項（記入 PLAN §10）**：主軌 para_gap block 軸 pt 精度依 A 級量測否決（block 軸整數槽
對齊，無 sub-slot pt 目標）。釐清 Sprint 30 交接語「需 block 軸 pt 偏移」之前提誤讀：Sprint 25
「內文精確 gap」實為整數槽差（大標 para_gap 1 使 body 落 slot 3 vs 真書 slot 2），非 pt 殘差。
Owner 預授權「量測素材不足轉替代軌」，此處為確認 block 軸本就整數對齊（此軸無 pt 目標），
轉替代軌 A 落地量測工具共用模組。

**落差登記**：
- GAPS #13 C 個案扉頁「大標 para_gap 1 使 body 落 slot 3 vs 真書 slot 2」為整數槽差非 pt（本
  sprint 澄清，非新增缺口）；正解 個案大標 para_gap 1→0，但 個案大標 同時用於內頁 h2
  （42 頁），全域改動須拆樣式（設計變更），續留 GAPS #13 不在本 sprint 硬修。
- `BLEED_PT`／`strip_bleed` 為量測工具箱提供之 Gate-4 換算正典（model↔trim 比對，避免
  Sprint 24/25 式未扣出血覆轍）；本 sprint 量的是無出血真書故 4 工具未觸發（誠實記錄：屬
  工具箱基建非死碼）。測試側 test_pdf_writer.py／test_lead_offset.py 的 BLEED_PT 仍各自持有，
  跨 tools/tests 統一非本軌範圍。

**下個 Sprint 預定範圍**：替代軌 B（test_pdf_writer.py／test_layout_render.py 近 800 行上限
分檔）；或引擎 pt 精度模型其他 inline 軸用例（如橫排 body，GAPS #13）；或個案大標 para_gap
整數修正（需拆 個案扉專用 vs 內頁 h2 兩樣式）。本 sprint 無新樣張（純工具重構，行為保持以
JSON diff 驗證），無新 Owner 抽檢項。
