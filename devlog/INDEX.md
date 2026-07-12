# devlog 索引

> 逐 Sprint 開發日誌總覽。Phase 0（Spike）與 Phase 1（Sprint 6〜39）已歸檔於 `archive/`，
> 進行中的 Phase 2（Sprint 40 起）留於本目錄。內容不變，僅位置整理（2026-07-12 Sprint 41 索引化）。
> 決議正典見 PLAN §10、落差見 GAPS.md，本索引只做導覽。

## Phase 2：WYSIWYG 編輯器（進行中，本目錄）

| Sprint | 主題 | 檔案 |
| --- | --- | --- |
| 40 | Phase 2 開工：PySide6 雙層畫布骨架（技術棧定案＋點字格反查游標） | 2026-07-12-sprint40-phase2-canvas-skeleton.md |
| 41 | 編輯引擎 reflow 回路（游標插字→全文重排→反查新游標畫布落點） | 2026-07-12-sprint41-edit-engine.md |

## Phase 0：可行性驗證 Spike（`archive/`）

| Sprint | 主題 | 檔案 |
| --- | --- | --- |
| 1 | Spike 1 直排核心管線探針 | archive/2026-07-10-spike1-pipeline-probe.md |
| 2 | Spike 1 真實跨頁排版＋驗收檢核清單 | archive/2026-07-10-sprint2-spike1-spread.md |
| 3 | Spike 2a Vivliostyle 輸出後端＋Spike 3 效能 | archive/2026-07-10-sprint3-spike2a-vivliostyle.md |
| 4 | Spike 3 重排效能＋Spike 5 AI 樣式真章重測 | archive/2026-07-10-sprint4-spike3-spike5.md |
| 5 | Spike 4 授權＋Phase 0 閘門判定 | archive/2026-07-10-sprint5-spike4-license-gate.md |

## Phase 1：核心排版管線 MVP（`archive/`）

| Sprint | 主題 | 檔案 |
| --- | --- | --- |
| 6 | Phase 1 開工：文件模型＋三層樣式＋直排引擎產品化 | archive/2026-07-10-sprint6-phase1-pipeline.md |
| 7 | md 匯入＋主版頁腳＋字型組入庫 | archive/2026-07-11-sprint7-md-footer-fonts.md |
| 8 | 自寫 PDF 1.4 寫出層＋字型子集嵌入 | archive/2026-07-11-sprint8-pdf-writer.md |
| 9 | 字元樣式 run 模型（document@2） | archive/2026-07-11-sprint9-run-model.md |
| 10 | PDF/X-1a:2001 識別＋機械 preflight 12 規則 | archive/2026-07-11-sprint10-pdfx1a.md |
| 11 | 齊行與禁則擠入 | archive/2026-07-11-sprint11-justification.md |
| 12 | 依書頁號鏡像＋PNG 缺字警告 | archive/2026-07-11-sprint12-mirror-book-page.md |
| 13 | 橫排版面軸（版權頁 CIP） | archive/2026-07-11-sprint13-horizontal.md |
| 14 | CIP 細框向量原件 | archive/2026-07-11-sprint14-cip-frame.md |
| 15 | 目錄水平虛線向量原件 | archive/2026-07-11-sprint15-toc-rule.md |
| 16 | 目錄條目頁碼＋引導線 | archive/2026-07-11-sprint16-toc-entry.md |
| 17 | Spike 10 Phase 2 畫布前置＋provenance 缺口 | archive/2026-07-11-sprint17-canvas-spike.md |
| 18 | 文件 provenance 載體（Cell.span／para_idx） | archive/2026-07-11-sprint18-provenance.md |
| 19 | F 版權頁版心量測 | archive/2026-07-11-sprint19-cip-metrics.md |
| 20 | B 部扉頁型大標置位 | archive/2026-07-11-sprint20-part-divider.md |
| 21 | 目錄嵌線斷開＋條目縮退 | archive/2026-07-11-sprint21-toc-inline-title.md |
| 22 | 鏡像側別勘誤（偶右奇左三向互證） | archive/2026-07-11-sprint22-mirror-parity.md |
| 23 | E 序文版量測 | archive/2026-07-11-sprint23-preface-master.md |
| 24 | 目錄章名條目黑 W5 | archive/2026-07-11-sprint24-toc-chapter-entry.md |
| 25 | C 個案扉頁大標 | archive/2026-07-11-sprint25-case-title.md |
| 26 | GAPS #21 出血座標框勘正 | archive/2026-07-12-sprint26-gaps21-frame.md |
| 27 | G 圖文版頁型骨架 | archive/2026-07-12-sprint27-figure-master.md |
| 28 | preflight /ID 兩式修正 | archive/2026-07-12-sprint28-preflight-id-fix.md |
| 29 | 引擎 pt 精度（lead_offset_pt）部扉大標 | archive/2026-07-12-sprint29-lead-offset-pt.md |
| 30 | 目錄條目 inline 偏移＋出血座標勘正 | archive/2026-07-12-sprint30-toc-entry-lead-offset.md |
| 31 | para_gap pt 主軌否決＋measure 共用模組 | archive/2026-07-12-sprint31-measure-common.md |
| 32 | 測試檔依頁型分檔 | archive/2026-07-12-sprint32-test-split.md |
| 33 | 個案大標 para_gap 樣式拆分 | archive/2026-07-12-sprint33-case-title-split.md |
| 34 | 個案中標 12.9pt 變體釐清否決 | archive/2026-07-12-sprint34-case-info-129-clarify.md |
| 35 | 個案扉頁 slot 0 誤讀勘正 | archive/2026-07-12-sprint35-case-slot0-clarify.md |
| 36 | 旁注 9pt／Case 15.9pt 變體量測確認 | archive/2026-07-12-sprint36-handwritten-variants-confirm.md |
| 37 | C slot 0 黑 W7 欄標建模 | archive/2026-07-12-sprint37-case-slot0-hei-label.md |
| 38 | C 資訊區欄位卡片建模 | archive/2026-07-12-sprint38-case-info-zone-field-cards.md |
| 39 | Phase 1 骨架收尾定案 | archive/2026-07-12-sprint39-phase1-closure.md |
