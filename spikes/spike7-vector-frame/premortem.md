# Spike 7 Pre-mortem：向量原件（CIP 細框，honest-planning R6）

Sprint 14 開工前 pre-mortem。向量原件（線／矩形描邊）是兩後端（render PIL／
pdf_writer path ops）的新繪圖能力，CIP 細框（版權頁）是第一個使用案例，也是後續
部扉雙線菱形框（B 主版）與目錄水平虛線（D 主版）的地基（PLAN §1 精緻設計細節）。

## 現況校正（降低「首用技術」風險判定）

- **PIL ImageDraw 矩形**：成熟 API，非首用高風險；風險只在 "L"（灰階）模式的
  outline／width 像素行為，spike 直接畫一格驗證。
- **PDF path ops（`re`／`S`／`w`）**：PDF 1.3 基本圖形算符，非新技術；真正的新交互
  點是「描邊色走 DeviceCMYK（`K` 算符）＋ 須在 BT／ET 文字物件之外 emit ＋ preflight
  的 `color-cmyk-only` 規則（抓 `rg`／`RG` 與 `/DeviceRGB`）不得退步」。spike 生成一個
  含 CMYK 描邊矩形的最小 PDF，用 PyMuPDF 獨立解析並跑既有 color pattern 驗證。

## 七問

1. **最可能失敗**：CMYK 描邊算符 `K` 或路徑算符 `re`/`S` 誤觸 preflight 的
   `(rg|RG)` 內容流檢查，或 path ops 誤置於 BT／ET 內導致 PyMuPDF 解析異常／不渲染。
2. **失敗機率**：低（約 15%）。`K`／`re`／`S` 字面不含 `rg`／`RG` 子串；風險集中在
   emit 位置（文字物件外）與兩後端框幾何同源。
3. **早期訊號**：spike 的 CMYK 框 PDF 經 PyMuPDF `get_pixmap` 無框線像素，或
   content 被 `(rg|RG)` pattern 命中，或 render／pdf 兩後端框座標偏移 > 0.3pt。
4. **對策**：框幾何同源集中在 `primitives.cip_frame_rect`（單一 top-down pt 矩形），
   render（PIL）與 pdf（path ops）都吃同一個 `StrokeRect`；path ops 用獨立 `q…Q`
   圖形狀態塊置於文字塊之前，狀態隔離；spike 先以既有 color pattern 釘住不退步。
5. **放棄條件**：若 CMYK 描邊無法通過 preflight（須改 DeviceGray `G`），退回單 K
   灰階描邊並於 GAPS 誠實標示「框線非 CMYK」。（預期不會：`K` 是合法 DeviceCMYK 描邊。）
6. **替代方案**：框可用「四條 `re`+`f` 填色細條」代替 `re`+`S` 描邊；但描邊 `S`
   最簡潔且線寬單一算符 `w` 可控，優先描邊。
7. **預估誤差範圍**：±0.3 Sprint。兩後端同源與 preflight 不退步順利則本 Sprint 收尾。

## 紅線

CIP 框幾何**全自擬**（由主版 grid 與內容行數確定性推導），不取參考書《內在整理》
p178 版心量測。F-版權頁真實版心仍留 GAPS #13，待 Owner 本機量測；本 Sprint 用自擬
合理幾何實作「向量原件機制」，不宣稱與參考書逐點一致。
