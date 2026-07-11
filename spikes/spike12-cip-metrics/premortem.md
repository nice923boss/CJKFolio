# Spike 12 Pre-mortem：F-版權頁真實版心量測（honest-planning R6）

Sprint 19 開工前 pre-mortem。GAPS #13 (a)：F-版權頁（p178 CIP）真實版心未量測，
現用自擬合理幾何（8pt、字距 8.4、行距 14、框 pad 6pt）。本 Sprint 以 PyMuPDF
一手量測 p178（PDF 頁索引 177，探勘已確認：839×595pt 跨頁、含 ISBN、1 draw
＝CIP 細框），把 F 主版從「自擬」升級為「A 級量測參數」。

## 現況校正（無首用技術，判定不需新 PoC spike）

- 量測方法＝Sprint 15 p003（D-目錄虛線／天頭）與 Sprint 6 全書掃描的既有能力
  （get_text("dict") spans＋get_drawings），工具入 tools/（scan_reference_styles
  先例）。
- 模版參數化＝Sprint 15 先例（量測參數入模版、內容不入 repo）。
- 樣張重驗＝samples/cip-copyright.doc.json（自擬虛構書目）既有流程。

## 成功標準

- 量出：CIP 框（x0,y0,x1,y1、線寬、色）、CIP 文字（字級、字距、行距、行數、
  框內 pad）、版權頁半邊判定與單頁版心（top／bottom／inner／outer）。
- F 主版 margins／grid／frame 換算為量測值；樣張重排 render＋export-pdf，
  preflight 12/12 不退步、兩後端框座標 parity 測試不退步。
- GAPS #13 (a) 關閉；量測數據記 devlog（數字，不含內容文字）。

## 七問

1. **最可能失敗**：p178 的 CIP 版面與 v1 網格模型不相容（如多欄、行距不均、
   框非矩形），單一 grid 參數組表達不了。
2. **失敗機率**：低〜中（約 20%）。探勘已見 1 draw（暗示規則框）；CIP 慣例
   為單欄等距行。
3. **早期訊號**：行 y 差序列不等距（std 大）、框 path 非 re 矩形。
4. **對策**：不相容處誠實記錄（如行距分兩段：書目資訊與販售資訊行距不同），
   v1 取主要區塊參數、剩餘差異入 GAPS 不沉默；框非矩形則框幾何維持推導式
  （內容盒＋pad 反推 pad 值）。
5. **放棄條件**：p178 實測非橫排 CIP（機率極低，§1 已載明）。
6. **替代方案**：維持自擬幾何＋GAPS 續留（現狀，無新風險）。
7. **預估誤差範圍**：±0.2 Sprint。

## 紅線

p178 為參考書內容：量測腳本輸出（含文字）只落 assets/reference/（不入 repo）；
devlog／模版／CHANGELOG 只記幾何參數數字。樣張仍用自擬虛構書目。
