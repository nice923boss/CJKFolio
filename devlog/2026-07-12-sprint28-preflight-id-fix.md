# Sprint #28（2026-07-12）preflight trailer-id 假陰性勘正（基線綠回復），已完成

**範圍**：接手動工前跑 PLAN 基線（`pytest spikes tests`），發現 1 筆順序相依失敗
（`test_export_toc_rule_preflight_green`，`trailer-id` 規則）。依 SKILL 除錯紀律「先排除
環境假信號、找根因，不在紅基線上疊功能」，定位根因、TDD 回歸測試（先 RED）、修檢查器
（後 GREEN）、完整基線覆驗。R1 證據先行、R5 真實驗收（實跑基線）。

**根因（機制已證，A 級 probe）**：
- `preflight.check_pdfx1a` 的 `trailer-id` 規則 regex 只認角括號 hex `<[0-9A-Fa-f]+>`。
- PyMuPDF `xref_object(-1)` 讀回 trailer 時，對「解碼後 16 bytes 全可列印」的 /ID 字串
  重序列化為 literal `(...)` 而非 `<hex>`（probe 實證：可列印→`(0123456789ABCDEF)`、
  非可列印→`<hex>`，見下驗證）。此時 regex 落空，`trailer-id` 假性判失敗。
- 觸發條件：`pdf_writer.build` 的 /ID＝`md5(bodies)`。全套執行順序下該 TOC PDF 的 /ID
  位元組落入全可列印區間（單獨執行時非可列印，故隔離跑通過）；檔案 /ID 始終為合規的
  兩組非空字串，**PDF 本身無缺陷，渲染／寫出層不動**。
- 判別過程：單獨此測試通過、`test_pdf_writer.py` 全檔通過、`pytest tests`（無 spikes）
  190 全過、`pytest spikes tests` 紅 1 → 確認為跨檔累積的檢查器脆弱點，非產品回歸。

**完成**：
- ✅ scratchpad/probe_id.py [Spike]：手工組不同 /ID PDF，fitz 讀回實測：可列印 bytes
  →`(literal)`＋regex 落空、非可列印→`<hex>`＋regex 命中（機制確證）。
- ✅ cjkfolio/preflight.py `trailer-id` regex [實作]：每組字串同認 `<hex>` 與 `(literal)`
  兩式（`(?:<[0-9A-Fa-f]+>|\((?:[^()\\]|\\.)+\))`）；空 `<>`／`()` 仍判失敗（方向安全，
  不會假性放行真正缺 /ID 的檔）。
- ✅ tests/test_preflight.py::test_preflight_accepts_literal_string_id [實作]：可列印 /ID
  的手工 PDF，斷言 `trailer-id` 通過（TDD：修前 RED、修後 GREEN，確定性重現不依賴全套累積）。

**測試成長**：205 → 206（+1：preflight 回歸）。0 失敗、0 退步。

**驗證**：
- typecheck：`py_compile` EXIT=0
- test：`pytest spikes tests` 206 passed / 0 failed（原順序相依失敗消除）
- 交叉驗證：新回歸測試修前單獨跑 RED（`trailer-id` 落網）、修後 GREEN；原
  `test_export_toc_rule_preflight_green` 修後全套跑通過
- Gate 4 獨立驗證：probe 以手工 PDF＋fitz 讀回實測 PyMuPDF 序列化行為（與被修的檢查器
  不同路徑），確證「可列印→(literal)」非臆測
- 破折號掃描：異動檔（preflight.py、test_preflight.py、devlog）0 破折號

**下個 Sprint 預定範圍**：基線已綠，回到 Owner 指示。最複雜架構（直排引擎）已建於
Sprint 1〜27；剩最複雜者為 Phase 2 畫布，其 IME 直排輸入須真視窗＋人工鍵盤（GAPS #19）
無法自主驗收。能自主檔案驗收且最貼近架構的：Phase 2 資料平面（可編輯模型＋編輯→重排→
游標回鏈，承 Sprint 18 provenance）。噪音移除（`measure_*.py` 共用模組、`test_pdf_writer.py`
791／`test_layout_render.py` 792 行近 800 上限分檔）另立 Sprint，不混入架構 Sprint。
