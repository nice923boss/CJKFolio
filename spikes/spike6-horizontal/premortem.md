# Spike 6 Pre-mortem：橫排版面軸（honest-planning R6）

Sprint 13 開工前 pre-mortem。橫排（horizontal-tb）是跨 engine／layout／render／
pdf_writer 的新版面軸（版權頁-CIP，PLAN GAPS #13）。

## 現況校正（降低「首用技術」風險判定）

橫排字形擺放**非首用技術**：頁腳三件組（Sprint 7〜12，Owner 目檢通過）已端到端
驗證水平 CJK（書名「內在整理」，`_render_horizontal_strip` 走 hb `ltr`）與 latin
（頁碼）擺放，PDF 端已用 `1 0 0 1 x y Tm` 水平文字矩陣，placement 已有
`horizontal_run`／`horizontal_placements`。真正新的只有「多行橫排流排幾何」
（行由上而下、字由左而右的 slot→位置軸），故本 spike 只驗這一項。

## 七問

1. **最可能失敗**：橫排 layout 的 slot→位置座標軸與 render／pdf 兩後端擺字不一致
   （位置對不齊），或 CJK 字與行內 latin（ISBN 數字）同行基線不齊。
2. **失敗機率**：中低（約 20%）。底層水平擺放已驗；風險集中在幾何軸與兩後端同源。
3. **早期訊號**：spike 的橫排 PDF 用 PyMuPDF 抽字座標，與預期 pen 座標偏移 > 0.5pt；
   或 CJK 與 latin 基線 y 不一致。
4. **對策**：同源邏輯集中在 placement 層單一函式（`horizontal_line_placements`），
   render（柵格）與 pdf（座標）都呼叫同一套 advance 數學；spike 先以 PDF 座標抽取
   對比預期值釘住同源。
5. **放棄條件**：若橫排需重寫 `engine._break_cells`（而非加 direction 參數復用），
   範圍爆表 → 退回「版權頁逐行預排橫排盒」最小可用，engine 不動。
6. **替代方案**：CIP 頁行數少且固定，可不走完整分頁流排；但為版面軸一致性，優先
   走完整管線（engine→layout→render／pdf 同一條路）。
7. **預估誤差範圍**：±0.5 Sprint。兩後端同源順利則本 Sprint 收尾。

## 紅線

版權頁 CIP 樣張資料**全自擬**（虛構書目），不得取自參考書《內在整理》p178 內容。
F-版權頁真實版心（p178 量測）仍留 GAPS #13，待 Owner 本機量測；本 Sprint 用自擬
合理幾何實作「機制」，不宣稱與參考書逐點一致。
