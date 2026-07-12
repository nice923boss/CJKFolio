# Sprint #26（2026-07-12）GAPS #21 勘正：直排字墨偏移為量測框錯配，非置中 bug，已完成

**範圍**：Owner 指示「先挑最複雜的架構先做」＋正確性優先。專項調查 Sprint 25 Gate 4
抽驗發現的 GAPS #21（直排字墨 cx 偏 line_axis +8.5pt，疑全直排既有正確性問題）。
R1 證據先行、R8 不預設有 bug 就改碼。

**調查與根因（A 級實證）**：
- 關鍵線索：偏移固定 8.50pt、與字級無關（大標 17.9pt 與資訊列 11.4pt 同偏 +8.50）。
  真置中誤差會隨字級（em）變，剛性常數偏移＝座標框平移的特徵。
- 3mm 出血＝3×72/25.4＝8.5039pt≈8.50。pdf_writer 逐字 `x = self.bleed_pt + pl.x_pt`：
  PDF 每字 x＝出血(8.5)＋trim 空間原點。故 trim 空間正確置中的字，在 MediaBox
  空間 cx＝trim_cx＋8.5。
- 量測工具 measure_case_page.py 量真書用 trim 局部座標（h(v)=v−419.53，無出血）；
  Sprint 25 Gate 4 手驗卻拿我方 PDF MediaBox 座標（含出血）比 trim 空間 line_axis，
  漏扣出血常數 → 假性 +8.5。
- probe 實證（scratchpad，執行後刪）：export C 樣張（--first-page 2 右頁），
  fitz rawdict 抽字墨 cx：大標 MediaBox 339.75、資訊列 362.75；各扣出血後
  trim cx＝331.25／354.25＝line_axis（Δ+0.00pt），吻合真書 ink 中心 331.28（差 0.03）。
- 佐證（既有測試早已正確）：test_export_glyph_geometry_on_grid 早已用
  `(BLEED_PT + line_axis)` 比對 PDF 字墨、test_render_single_char_lands_in_first_cell
  早已驗 PNG（trim 尺寸無出血）ink cx ≈ line_axis（容差 2.4pt；若真偏 8.5≈17.7px 必炸）。
  兩測試皆在 190 綠內，即渲染置中一直是對的。

**結論**：GAPS #21 為量測座標框錯配（MediaBox vs trim）之假象，非渲染缺陷。
渲染層 placement／render／pdf_writer 直排置中本就正確。**不修渲染碼**：任何
「補償 −8.5pt」皆反向雙重補償、會破壞現有與真書吻合的置中，重演 Sprint 22 式
同源同錯風險（該次是測試與實作同錯；本次是手驗與工具口徑不一致）。

**完成**：
- ✅ 勘正 [實作]：GAPS #21 由「待修正確性 bug」改「已勘正：量測框錯配」（GAPS.md）。
- ✅ 回歸測試 [實作]：tests/test_pdf_writer.py::test_case_ttb_ink_centered_on_line_axis
  （C 大標＋資訊列，扣 BLEED_PT 後 cx＝line_axis＋反例保護：未扣出血恆偏 +BLEED_PT，
  與字級無關，佐證框差非置中錯誤）。
- ✅ 勘正誤導註解 [實作]：test_layout_render.py test_case_master_and_title_placement
  原註「PDF/PNG 實際字墨 cx 偏此 +8.5pt」改為出血框差說明並指向新測試；PDF 置中
  測試分層入 test_pdf_writer.py（依 fitz／export_pdf 分層，test_layout_render.py 回 792 行、
  解 800 行上限 hook）。

**測試成長**：190 → 191（+1：PDF 直排置中回歸測試）。0 失敗、0 退步。

**驗證**：
- typecheck：EXIT_CODE=0；test：191 passed / 0 failed
- Gate 4 獨立實證（R5）：probe 以 fitz rawdict 抽真實 export PDF 字墨 cx，扣出血後
  ＝line_axis（Δ+0.00pt，實跑非只讀碼）；新回歸測試單獨執行 1 passed。
- 除錯紀錄：Sprint 25 Gate 4 誤判根因＝手驗漏扣 BLEED_PT 出血常數（既有自動測試本已
  正確扣出血，未被納入 Gate 4 手驗對照）。

**下個 Sprint 預定範圍**：回 GAPS #13 B〜G 頁型系列，剩 G 圖文版（§4.2 主版 7 種
最後一種）；次選抽取工具目錄模式。Owner 抽檢項：out/case25 個案大標 slot 1
（直排墨偏移 GAPS #21 已勘正為 3mm 出血框差、非缺陷，並排比對時 MediaBox 的 3mm
位移屬正常出血，不需在意）。
