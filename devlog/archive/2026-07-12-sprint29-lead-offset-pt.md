# Sprint #29（2026-07-12）引擎 pt 精度模型：段級 inline 軸 sub-slot 偏移（lead_offset_pt），已完成

**範圍**：Owner 指示「最複雜的架構先做」。護城河核心引擎的 pt 精度化：把整數字槽定位
升級為可疊加 sub-slot pt 偏移。依專案節奏單一軸心單一 Sprint，首個軸心＝inline 軸
段級偏移，直攻 Sprint 20 明列的 B 部扉大標「首字頂比部序號低 6.02pt」（GAPS #13 已知
整數槽差）。R1 證據先行、R5 真實量測驗收。

**決策脈絡**：Sprint 20 決議「不擴段前 pt 偏移模型（Phase 2〜3 樣式系統再議）」為延後
非否決；Owner 現要求最複雜架構，正式觸發此重議（決議紀錄記錄）。

**設計**：
- `lead_offset_pt`＝段級 inline 軸 pt 偏移，純位置微調、不改斷行容量（sub-slot 語意，
  不進 `_break_cells`，斷行禁則齊行皆不動）。
- 載體鏈：ParagraphStyle（JSON）→ ParagraphSpec → PlacedLine → 兩後端 body inline-start
  `top_pt + start_slot × advance + lead_offset_pt`（render／pdf_writer 同一式，同源）。
- v1 只套用直排 body。橫排 body 與 toc 引導線／rule 穿線判定 v1 不套用（無 combined
  用例：唯一使用者部扉大標為直排、無 toc／rule），入 GAPS #13 誠實記錄。

**完成**：
- ✅ cjkfolio/engine.py [實作]：ParagraphSpec＋PlacedLine 加 lead_offset_pt 載體，flow_pages
  emit 貫通。
- ✅ cjkfolio/styles.py [實作]：ParagraphStyle.lead_offset_pt＋JSON 解析（預設 0.0）。
- ✅ cjkfolio/layout.py [實作]：style → ParagraphSpec 傳遞。
- ✅ cjkfolio/render.py＋pdf_writer.py [實作]：直排 body inline-start 各加 lead_offset_pt
  （兩後端同源一致式）。
- ✅ templates/neizai-zhengli.json [實作]：部扉大標-明體W9 lead_offset_pt 6.02（大標首字頂
  cell_top 176.84→182.86pt，貼 Sprint 20 真書量測值 182.86；部序號維持天頭 176.84）。
- ✅ tests/test_lead_offset.py [實作]：布線（font-free：大標 PlacedLine 帶 6.02、部序號帶 0）
  ＋兩後端兩渲染差分（offset 6.02 vs 0，大標下移恰 6.02pt、部序號不動）。測試 206→209。
  另開新檔（test_layout_render.py 792 行近 800 上限，依功能分檔）。

**測試成長**：206 → 209（+3：lead_offset 布線＋PDF 差分＋PNG 差分）。0 失敗、0 退步。

**驗證**：
- typecheck：`py_compile` EXIT=0
- test：`pytest spikes tests` 209 passed / 0 failed
- 兩渲染差分（Gate 4，字型 ascent 抵消只留偏移）：PDF `get_text("rawdict")` 抽字墨頂、
  PNG 裁行軸欄 `getbbox` 墨頂，兩後端皆測得大標首字下移 6.02pt（PDF abs≤0.05、PNG
  abs≤0.3px÷scale）、部序號 0 位移
- 絕對值：大標 cell_top＝top_pt 176.84＋lead 6.02＝182.86pt，吻合模版 evidence 真書 182.86
- 回歸：既有 test_part_divider_layout_geometry（slot／行軸 x／天頭／advance／para_gap）不受
  inline 軸 pt 偏移影響、不退步；offset 預設 0，其餘 15 段落樣式與全部樣張 0 位移
- 破折號掃描：異動檔（engine／styles／layout／render／pdf_writer／模版／test／devlog）0 破折號

**下個 Sprint 預定範圍**：pt 精度模型次軸，同 inline 軸機制套用＋量測驗收：目錄條目縮退
（Sprint 21 head_offset 3 槽 29.93 vs 真書 27.04，+2.89pt）與目錄章名（Sprint 24 +2.27pt）；
續 para_gap（block 軸，Sprint 25 個案中標相鄰）。橫排／toc/rule 的 lead_offset_pt 套用待
有 combined 用例再開。tests/test_pdf_writer.py 791／test_layout_render.py 792 行分檔仍待做。
