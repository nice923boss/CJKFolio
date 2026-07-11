# Spike 10 報告：WYSIWYG 畫布與排版核心同步（PoC 通過）

日期：2026-07-11（Sprint 17）。狀態：**五項成功標準全過**。
探針：`probe_canvas_sync.py`（自 repo 根 `python spikes/spike10-canvas-sync/probe_canvas_sync.py` 可重現）。
指標檔：`out/metrics.json`（本機，不入 repo）。

## 環境

- Windows 11、Python 3.12.10、PySide6 6.11.0（Qt 6 官方綁定，LGPL，已安裝零下載）
- `QT_QPA_PLATFORM=offscreen`（無視窗環境，AI 可自主驗證）
- 素材：第一章本機文件（79 段、22 頁、5,361 字格；紅線素材不入 repo，本報告僅記數字）

## 驗證架構

雙層畫布（Spike 3「背景渲染＋快取」結論的畫布面落實）：

- **底圖層**：既有 PNG 渲染後端輸出 → QImage → QGraphicsPixmapItem（z=0）
- **互動層**：由 layout 幾何直接生成透明 QGraphicsRectItem 字格（z=1，含 hit 區域）
- 互動層座標**復用 render 同一組幾何函式**（`line_axis_x_pt`／`style_advance_pt`／
  `line_justified_advance`），與雙後端同源紀律一致，不另立幾何

## 結果對成功標準

| 標準 | 門檻 | 實測 | 判定 |
| --- | --- | --- | --- |
| S1 offscreen 環境 | 可建可渲染 | QApplication＋QGraphicsView 9.5ms，scene 渲染 PNG 正常 | 過 |
| S2 對位 | 高亮框住字形 | 4 格（章名首格／內文中格／大標格／末格直排「】」）Read 親驗全準；直排標點 vert 形貼格頂為正確形態 | 過 |
| S3 hit-test 反查 | 100% | **214/214**（全頁字格中心 itemAt → (placed_idx, cell_idx) 全對） | 過 |
| S4 編輯回路 | < 200ms | **37.2ms @150dpi**（重排 7.0＋渲染 25.8＋pixmap 1.9＋互動層 2.6）；26.9ms @96dpi | 過（5 倍餘裕） |
| S5 規模 | 建立 < 2s、hit < 10ms | 22 頁 5,361 item 建立 **52ms**；hit-test 中位 **0.90ms**（max 7.0）、抽樣反查 68/68 | 過 |

S4 的重排 7.0ms 與 Spike 3 的 7.67ms 一致（獨立重測互證）。

## Phase 2 設計輸入（一手數據結論）

1. **Qt（PySide6）＋QGraphicsScene 雙層畫布路線可行性成立**：編輯 → 全章重排 →
   單頁重渲染 → 畫布更新全回路 37ms，互動級（<200ms）餘裕 5 倍；§5.2 的
   「Qt 候選」自此有一手數據。畫布語言可先 Python（與 Phase 1 管線同語言），
   效能瓶頸（渲染 25.8ms）在既有 FreeType 柵格層而非 Qt 層。
2. **規模**：5,361 item 建立 52ms，線性外推全書（179 頁 ≈ 4.4 萬格）約 430ms、
   hit-test 由 BSP 索引支撐（中位 0.9ms）。單 scene 全書可行，但維持 Spike 3
   「分章載入」設計更穩（記憶體與初始延遲）。
3. **介面缺口（本 spike 顯式暴露的 Phase 2 需求）**：`PlacedLine`／`Cell` 無文件
   provenance（para_idx／char offset）。hit-test 現能反查 layout 幾何鍵
   (page, placed_idx, cell_idx)，但「點字格 → 游標落在文件第幾段第幾字」的映射
   缺最後一躍。Phase 2 首項工程＝engine 流排時在 `PlacedLine` 掛 para_idx 與
   cell 的字元 offset（純載體，與 page_no 同模式）。
4. **未驗（誠實範圍界定）**：IME 直排輸入、拖曳、選取 UI、視窗事件迴圈，皆需
   真視窗與人工操作 → Phase 2 開工時 Owner 人工驗證（GAPS 登記）。

## 產出物

- `premortem.md`（R6 七問，開工前）
- `probe_canvas_sync.py`（探針，S1〜S5）
- `out/page1_base.png`／`out/page1_overlay.png`／`out/zoom_last.png`（對位親驗證據，本機）
- `out/metrics.json`（指標）
