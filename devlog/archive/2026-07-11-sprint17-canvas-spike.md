# Sprint #17（2026-07-11）Phase 2 畫布架構前置 spike（風險前置），已完成

**範圍**：Owner 指示「先挑最複雜的架構先做」。剩餘計畫中最複雜、風險最高的
架構件＝Phase 2「WYSIWYG 畫布 ↔ 排版核心同步」（PLAN §3.1 介面契約難點、
§7 pre-mortem 中高風險「長尾工程」）。依 honest-planning R2，先以最小 spike
驗證架構契約（Spike 10），不直接開蓋編輯器；Phase 1 頁型剩項不因此關閉。

**完成**：
- ✅ Spike 10 [Spike]（spikes/spike10-canvas-sync/，PoC 通過）：
  - premortem.md（R6 七問先行，成功標準 S1〜S5 先定義）。
  - probe_canvas_sync.py：PySide6 6.11.0（已安裝，零下載）offscreen 雙層畫布。
    底圖層＝既有 PNG 渲染後端輸出；互動層＝layout 幾何同源透明字格 item
    （復用 line_axis_x_pt／style_advance_pt／line_justified_advance，兩層同源，
    與雙後端同源紀律一致）。
  - report.md：五項標準全過＋Phase 2 設計輸入四條。
- ✅ 一手數據（第一章 22 頁本機素材，5,361 字格）：
  - S1 offscreen QApplication＋QGraphicsView 9.5ms 可建可渲染。
  - S3 hit-test：全頁 214 字格中心 itemAt 反查 **214/214 全對**。
  - S4 編輯回路（改段 → 全章重排 → 單頁重渲染 → 底圖更新＋互動層重建）：
    中位 **37.2ms@150dpi**（重排 7.0／渲染 25.8／pixmap 1.9／互動層 2.6）、
    26.9ms@96dpi；互動閾值 200ms 餘裕 5 倍。重排 7.0ms 與 Spike 3 的 7.67ms
    獨立互證。
  - S5 規模：22 頁 5,361 item 建立 **52ms**、hit-test 中位 0.90ms（max 7.0）、
    抽樣反查 68/68；線性外推全書 179 頁約 430ms，單 scene 可行、分章載入更穩
    （維持 Spike 3 結論）。

**測試成長**：164 → 164（+0：spike 探針不入 pytest 基線，避免基線硬依賴
PySide6 GUI 套件，決議入 PLAN §10）。0 失敗、0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py
  spikes/spike10-canvas-sync/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：164 passed / 0 failed（`python -m pytest spikes tests -q`）
- 真實素材驗收（R5）：第一章本機文件（紅線素材不入 repo，devlog 只記數字）→
  out/page1_overlay.png **Read 親驗**：4 高亮字格（章名首格／內文中格／大標格
  ／行末標點格）紅框黃底與底圖字形全部對位；zoom_last.png 放大親驗行末直排
  「】」vert 字形貼格頂（正確直排標點形態），框覆蓋整字槽正確。
  out/metrics.json **Read 親驗**與終端輸出一致。
- 除錯紀錄：首輪 StopIteration（md 文件全段帶 runs，編輯模擬須同步維持
  document@2 正規化不變式 text＝runs 串接）→ append_text 同步改 text 與末 run；
  S2 挑格邏輯首輪只抓 1 格 → 改等距抽 4 格＋styled 格。

**代決事項（記入 PLAN §10）**：
- Phase 2 畫布路線：PySide6＋QGraphicsScene 雙層畫布可行性成立，畫布語言候選
  Python 有一手數據；正式技術棧於 Phase 2 開工定案（本 spike 非開工）。
- Phase 2 首項工程：PlacedLine／Cell 掛文件 provenance（para_idx／char offset，
  與 page_no 同純載體模式）；spike 的 (page, placed_idx, cell_idx) 是幾何鍵，
  「點字格 → 文件游標」缺最後一躍，此為 spike 顯式暴露的介面缺口。
- spike 探針不入 pytest 基線。

**落差登記**：GAPS 新增 #19（IME 直排輸入／拖曳／選取 UI 未驗，offscreen
限制；Phase 2 開工首個 Sprint 真視窗 demo 由 Owner 鍵盤實測）。

**下個 Sprint 預定範圍**：回頭收 Phase 1 頁型剩項，候選同 Sprint 16 清單：
(a) B 部扉頁型（大標置位）；(b) E 序文版頁型；(c) 全字庫 TW-Kai／正宋體入庫
驗題詞／引文樣式（**需下載，開工前須 Owner 同意**）；(d) 抽取工具目錄模式；
另新增 (e) F-版權頁真實版心 p178 本機量測（紅線內作業：量測參數可入模版，
內容不入 repo，依 Sprint 15 D-目錄先例可自主執行）。Owner 抽檢項不變：
Spike 1 對比圖（GAPS #10）、斷行逐行一致率、Spike 10 對位樣張過目。
