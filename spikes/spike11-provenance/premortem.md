# Spike 11 Pre-mortem：文件 provenance 載體（honest-planning R6）

Sprint 18 開工前 pre-mortem。Phase 2 首項工程（Sprint 17 決議）：engine 流排時
在 Cell／PlacedLine 掛文件 provenance，供畫布點選 → 文件游標映射（Spike 10
顯式暴露的介面缺口：hit-test 只能反查幾何鍵，缺「第幾段第幾字」的最後一躍）。

## 現況校正（無首用技術，判定不需新 PoC spike）

- **載體模式既有先例**：`page_no`（Sprint 16）同款純載體欄位（ParagraphSpec →
  PlacedLine passthrough，不影響斷行禁則）；para_idx 完全同構。
- **span 唯一的實質邏輯＝索引映射**：normalize 剝除 Cc 會位移 offset，須以
  `normalize_with_offsets`（正規化＋原索引表）建立映射；presentation forms
  為 1:1 替換不動 offset。純索引數學，單元測試可全釘。
- **runs 的 base 位移**：document@2 不變式（text＝runs 串接）保證 run k 的
  文件座標基底＝前 k−1 個 run 的 text 長度和。既有不變式，直接復用。
- 兩後端與齊行不受影響：span／para_idx 是載體，渲染與 PDF 不讀它。

## 設計

- `Cell.span`：半開區間 (start, end)，座標系＝tokenize 輸入 text；經 offsets
  映射後＝文件段 text 座標（flow_pages／cells_from_runs 一律傳映射）。
  預設 identity（直呼 tokenize 的舊 API 行為相容）。
- `ParagraphSpec.para_idx`／`PlacedLine.para_idx`：文件段索引，layout 建 spec
  時掛（doc.paragraphs 與 specs 1:1）。
- ascii run（latin／tcy）span 覆蓋整串；span 內若有被剝除的 Cc，區間自然涵蓋
  （選取涵蓋不可見字元，合理語意）。

## 成功標準

- 全 placed cells round-trip：`doc.paragraphs[pl.para_idx].text[c.span[0]:c.span[1]]`
  正規化後 == cell.text，第一章本機素材（含 runs 段）100%。
- 既有 164 測試 0 退步（載體欄位 default 相容）。

## 七問

1. **最可能失敗**：offset 座標系混淆（normalize 前 vs 後）致 round-trip 錯位；
   或 runs base 與 run 內 Cc 剝除疊加時的邊界差一。
2. **失敗機率**：低（約 10%）。純索引數學，round-trip 測試直接抓錯位。
3. **早期訊號**：round-trip 測試在含 Cc／presentation forms 自擬段落上失敗。
4. **對策**：座標系單一定義（文件段 text 半開區間）寫進 docstring；含 Cc、
   含表現形、跨 run、tcy／latin 串各寫獨立測試釘死。
5. **放棄條件**：無（無外部依賴、不動斷行禁則）。
6. **替代方案**：畫布層自行做 text diff 反推位置；不採（脆弱且 O(n)，載體
   模式是既有慣例）。
7. **預估誤差範圍**：±0.2 Sprint。

## 紅線

單元測試素材全自擬；第一章 round-trip 驗證只在本機執行、只回報統計數字。
