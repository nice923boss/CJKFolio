# Spike 10 Pre-mortem：WYSIWYG 畫布與排版核心同步（honest-planning R6＋R2）

Sprint 17 開工前 pre-mortem。Owner 指示「先挑最複雜的架構先做」：剩餘計畫中
最複雜、風險最高的架構件＝Phase 2「WYSIWYG 畫布 ↔ 排版核心同步」（PLAN §3.1
「畫布與核心同步的介面契約難」、§7 pre-mortem 中高風險「長尾工程」）。依 R2
spike 門檻，先以最小 PoC 驗證架構契約，不直接開蓋編輯器。

## 依據（既有一手證據）

- Spike 3（2026-07-10）：純邏輯重排中位 7.67ms／章（8,164 字）、首跨頁渲染
  60ms；結論「分章快取即足、無需增量重排，Phase 2 以背景渲染＋快取設計」。
- PLAN §5.2：Qt 6＋QGraphicsView 為 Phase 2 候選決策（Scribus 同型先例、
  IME 一等公民、LGPL 動態連結）；執行校正明言候選需 spike 才能定案。
- 本機 PySide6 6.11.0（Qt 6 官方 Python 綁定，LGPL）已安裝，零下載成本；
  Python 3.12.10 與 Phase 1 管線同語言，spike 零 FFI 成本。

## 驗證架構（雙層畫布＝Spike 3 結論的畫布面延伸）

底圖層（既有 PNG 渲染後端輸出，背景重算）＋互動層（由 layout 幾何直接生成
的透明字格 item，輕量重建）。互動層座標**復用 render 同一組幾何函式**
（`line_axis_x_pt`／`style_advance_pt`／`line_justified_advance`），不另立
幾何（兩層同源，與雙後端同源紀律一致）。

## 成功標準（先定義，過即 [Spike] 通過）

- S1 環境：QT_QPA_PLATFORM=offscreen 下 QApplication＋QGraphicsScene 可建、
  可 render 至 QImage 存 PNG（AI 可自主驗證，無需互動視窗）。
- S2 對位：互動層字格高亮框與底圖字形對位（Read 目檢＋幾何同式推導）。
- S3 反查：全頁每個字格中心點 scene.itemAt() 反查 (placed_idx, cell_idx)
  100% 正確（畫布 → 排版幾何的 hit-test 契約）。
- S4 編輯回路：改一段文字 → 全章重排 → 單頁 PNG 重渲染 → 底圖更新＋互動層
  重建，端到端中位 < 200ms（150dpi，互動可接受閾值）。
- S5 規模：全章（22 頁級）互動層一次建進單一 scene（約 1 萬字格 item），
  建立 < 2s、單次 hit-test < 10ms；超標則結論改「分頁載入」（誠實記錄，
  不算失敗，是設計輸入）。

## 七問

1. **最可能失敗**：S4 編輯回路超 200ms（300dpi 渲染是大頭；150dpi 未實測）；
   其次 QGraphicsRectItem 透明填充不參與 hit-test（Qt shape() 對 NoBrush 的
   行為細節）。
2. **失敗機率**：中（約 25%）。重排 7.67ms 已知，渲染與 Qt 轉換未知。
3. **早期訊號**：分解計時中單項 >150ms；itemAt 回傳底圖而非字格 item。
4. **對策**：S4 超標先降預覽 dpi（96）再量；hit-test 失效改自訂 QGraphicsItem
   覆寫 shape()，或 brush 設 alpha=1 近透明。分解計時（flow／render／QImage
   轉換／scene 重建）逐項記錄，找出瓶頸供 Phase 2 設計。
5. **放棄條件**：offscreen 平台不可用且無替代（機率極低，官方 wheel 內建）；
   或編輯回路即使 96dpi 仍 >500ms 且無單項可優化 → 回報 Phase 2 需增量渲染
   架構（pre-mortem 對策路線），不硬寫結論。
6. **替代方案**：QGraphicsView 不合用則試 QQuickView（QML Canvas）或純
   QWidget paintEvent；均為 Qt 系不換依賴。egui/Slint 路線僅在 Qt 系全敗時
   重估（PLAN §5.2 替代欄）。
7. **預估誤差範圍**：±0.5 Sprint（Qt API 細節坑）。

## 範圍界定（誠實）

- 本 spike **不驗**：拖曳互動、IME 直排輸入、復原重做、選取範圍 UI。IME 需
  真視窗與人工操作，列 Owner 人工驗證項（GAPS 登記）。
- 本 spike **不是** Phase 2 開工：Phase 1 頁型剩項不因此關閉；spike 結論供
  Phase 2 技術棧決策（§5.2 候選 → 有一手數據）。
- hit-test 身分用 (page, placed_idx, cell_idx)（layout 幾何鍵）；cell → 文件
  (para_idx, char_idx) 的 provenance 反查是已知介面缺口，本 spike 負責把它
  顯式暴露成 Phase 2 需求，不在 spike 內實作。

## 紅線

素材用本機第一章（assets/reference/chapter1md.doc.json，不入 repo）量測效能；
對位與樣張輸出全在 spikes/spike10-canvas-sync/out/（.gitignore 既有涵蓋）。
報告只記數字與結論，不含參考書內容文字。PySide6 為 spike 依賴，不隨產品散布，
Phase 2 正式採用時再依 §5.2 做授權落實（LGPL 動態連結）。
