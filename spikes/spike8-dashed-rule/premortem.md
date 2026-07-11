# Spike 8 Pre-mortem：虛線原件（目錄水平虛線，honest-planning R6）

Sprint 15 開工前 pre-mortem。虛線描邊是向量原件層（Sprint 14 `primitives`）的第二種
原件，目錄頁天頭水平虛線（D 主版）是第一個使用案例（PLAN §1 精緻設計細節：
「目錄的水平虛線分隔」）。參考書 p003 一手量測（A 級，量測參數可入 repo、內容不可）：
y=122.46pt、線寬 1.0pt、dash pattern [3 2]（3pt 畫 2pt 空）、灰色（RGB 0.427 ≈ 單 K 57%）、
篇名處斷開、貫穿訂口與書口頁邊。

## 現況校正（降低「首用技術」風險判定）

- **PDF 路徑算符（`m`／`l`／`S`）**：Sprint 14 已落地 `re`／`S`／`K`（spike7 驗證），
  直線描邊非新能力；真正的新交互點是 **dash 算符 `d`**（graphics state：`[on off] 0 d`）
  與**非純黑的灰 K 描邊**（`0 0 0 0.57 K`）。
- **PIL 虛線**：ImageDraw 無原生 dash，須手動分段畫短線；風險只在 "L" 灰階模式的
  灰值換算（K→pixel＝255×(1−k)）與分段像素的 on/off 節奏，spike 直接畫一條驗證。

## 七問

1. **最可能失敗**：`d` 算符字面或位置不合法（誤置 BT 內／q…Q 外洩漏 dash 狀態影響
   後續文字描邊）、或 PyMuPDF 對 dash 線渲染不出像素、或灰 K 描邊被 preflight
   `(rg|RG)` 檢查誤傷。
2. **失敗機率**：低（約 15%）。`d` 是 PDF 1.3 標準 graphics state 算符；`[ 3 2 ] 0 d`
   字面不含 `rg`／`RG` 子串；風險集中在狀態隔離（獨立 `q…Q`）與兩後端 dash 節奏同源。
3. **早期訊號**：spike 的 dash 線 PDF 經 PyMuPDF `get_drawings` 抽不到 `dashes`、
   `get_pixmap` 無線段像素或整條連續（dash 沒生效）、content 被 `(rg|RG)` 命中。
4. **對策**：虛線幾何同源集中在 `primitives.StrokeLine`（單一 top-down pt 線段＋
   dash on/off 參數），render（PIL 分段）與 pdf（`d`＋`m`/`l`/`S`）都吃同一個
   `StrokeLine`；pdf 端 dash 置於獨立 `q…Q` 狀態塊（同 spike7 形態）；spike 先以
   既有 color pattern 釘住不退步。
5. **放棄條件**：若 `d` 算符在下游（PyMuPDF／印廠 RIP 慣例）渲染不可靠，退回
   「pdf 端也逐段畫短實線」（與 PIL 同一分段數學，仍兩後端同源），GAPS 誠實標示
   「PDF 虛線非原生 dash」。（預期不會：`d` 是印前標準能力。）
6. **替代方案**：見放棄條件（分段短實線）；或虛線改用點字型字元排（否決：裝飾
   幾何屬版面原件，不入文字流，PLAN §4.4 幾何歸引擎鐵律）。
7. **預估誤差範圍**：±0.3 Sprint。dash 同源與 preflight 不退步順利則本 Sprint 收尾。

## 紅線

參考書 p003 的**量測幾何參數**（y、線寬、dash 節奏、灰值）依 Sprint 7 頁腳先例
（calibration 實測座標入模版）可入 repo；**內容**（篇章條目文字）不可。公開樣張
`samples/toc.doc.json` 全自擬虛構條目。目錄「條目排版」（引導線、直排頁碼、篇名
斷開虛線）屬目錄頁型工程，不在本 Sprint，續留 GAPS #13 剩項。
