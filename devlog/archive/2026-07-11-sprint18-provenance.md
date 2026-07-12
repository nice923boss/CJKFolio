# Sprint #18（2026-07-11）文件 provenance 載體（Phase 2 首項工程），已完成

**範圍**：Sprint 17 決議的 Phase 2 首項工程：engine／layout 掛文件 provenance
（`Cell.span`＋`PlacedLine.para_idx`），補齊畫布點選 → 文件游標的最後一躍
（Spike 10 顯式暴露的介面缺口）。honest-planning R6 pre-mortem 先行
（spikes/spike11-provenance/premortem.md）；R2 校正判定**無需新 PoC spike**
（載體模式＝page_no 既有先例、span 唯一實質邏輯＝索引數學，單元測試可全釘）。

**完成**：
- ✅ engine [實作]：`normalize_with_offsets`（正規化＋原索引表：Cc 剝除位移
  精確映射、表現形 1:1 保原索引；`normalize` 改由其推導，單一事實來源）；
  `Cell.span`（半開區間；座標系＝tokenize 輸入，經 offsets 映射＝文件段 text
  原字串座標）；`tokenize(offsets=None)`（None＝identity，舊 API 相容）；
  `_flush_ascii`／`_span` 帶 span（ascii run 覆蓋整串，內含被剝 Cc 時自然涵蓋）；
  `cells_from_runs` 依 document@2 串接不變式帶 run base 位移；
  `ParagraphSpec.para_idx`＋`PlacedLine.para_idx`（emit 掛，flow 純 passthrough）。
- ✅ layout [實作]：`layout_document` 建 spec 時 `para_idx=i`（doc.paragraphs
  1:1）。載體不影響斷行禁則齊行與兩後端（渲染與 PDF 不讀 span）。

**測試成長**：164 → 173（+9：normalize_with_offsets 2〔乾淨 identity／Cc 剝除
＋表現形映射〕；tokenize span 2〔混合 cjk/latin/tcy/space 覆蓋輸入／offsets
映射回源〕；cells_from_runs base 1；flow_pages para_idx 2〔載體正確／預設
None〕；layout_document 全文件 round-trip 2〔直排含 runs 含 Cc／橫排 ISBN
latin 串〕）。0 失敗、0 退步。TDD：先寫測試（ImportError RED 親證）再實作。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py
  spikes/spike10-canvas-sync/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：173 passed / 0 failed（`python -m pytest spikes tests -q`）
- 真實素材驗收（R5）：一次性掃描腳本（跑完依紀律刪除）對三份素材全 placed
  cells 驗 `normalize(para.text[span]) == cell.text`：
  - 第一章本機（22 頁）：**5,361 cells round-trip 錯 0、無 para_idx 行 0**
  - samples/toc.doc.json：64 cells 錯 0；samples/cip-copyright.doc.json
    （橫排 ISBN latin 串）：65 cells 錯 0
- 同類掃描（Gate 3）：Grep 全 repo `Cell(`／`PlacedLine(`／`ParagraphSpec(`
  建構點，既有位置參數最多至第 4 位（span 第 5 位、para_idx keyword），
  spike1 為獨立舊引擎不受影響；173 全綠互證。
- 除錯紀錄：無（RED → GREEN 一次過）。

**代決事項（記入 PLAN §10）**：provenance 座標系定案（文件段 text 原字串
半開區間；normalize 分解出 offsets 版單一事實來源；ascii run span 覆蓋整串；
無 offsets 時 identity 相容）。

**落差登記**：無新落差（本 Sprint 無延後降級項）；GAPS #19（IME 未驗）不變。

**下個 Sprint 預定範圍**：回收 Phase 1 頁型剩項，候選：(a) F-版權頁真實版心
p178 本機量測（量測參數入模版依 Sprint 15 先例，可自主）；(b) B 部扉頁型
（大標置位）；(c) E 序文版頁型；(d) 抽取工具目錄模式；(e) TW-Kai 入庫
（**需下載，須 Owner 同意**）。Owner 抽檢項不變。
