# Sprint #13（2026-07-11）橫排版面軸（版權頁-CIP），已完成

**範圍**：GAPS #13 的橫排部分（版權頁-CIP 是全書唯一橫排 horizontal-tb，render 與 pdf_writer 原對非 vertical-rl 明確 raise）。橫排是跨 engine／layout／render／pdf_writer 的新版面軸。honest-planning R2（首用技術先 spike）＋R6（pre-mortem）先行。

**Pre-mortem（R6）＋Spike（R2）**：
- pre-mortem：`spikes/spike6-horizontal/premortem.md`。校正判定：橫排字形擺放**非首用技術**（頁腳三件組 Sprint 7〜12 已端到端驗過水平 CJK「內在整理」＋latin 頁碼，Owner 目檢過），真正新的只有「多行橫排流排幾何」。最可能失敗＝兩後端擺字不同源／CJK 與 latin 基線不齊，機率中低（約 20%），對策＝同源邏輯集中 placement 層一函式。
- spike：`spikes/spike6-horizontal/horizontal_poc.py`。自擬 4 行 CIP 塊，CJK 走 em 格、latin（ISBN）自然寬、行由上而下。Read PNG 目檢幾何正確、CJK 與 latin 同基線。風險消除。

**完成**：
- ✅ engine 方向感知 tokenize [實作]：`tokenize`／`cells_from_runs`／`break_paragraph`／`flow_pages` 加 `vertical` 參數（預設 True，直排全相容）。橫排時 `_is_run_char` 把整串連續 ascii（含空格、連字號、句點）收成一個 latin run（ISBN 不被 `-` 切碎），且短數字不轉縱中橫（無 tcy）。斷行／禁則（`_break_cells`／`check_kinsoku`）與方向無關，直接復用。
- ✅ layout 方向判定 [實作]：`page_is_vertical(doc, template)` 由文件實引用的段落樣式判頁面方向；v1 單一文件單一方向，混用 vertical-rl 與 horizontal-tb（slot 幾何不相容）快速失敗，未知 writing_mode 亦快速失敗。`LayoutResult.vertical` 供兩後端分派。齊行（雙錨定字距縮放）為直排內文特徵，橫排 CIP 短行左齊不縮放（justify_stats 皆 0）。
- ✅ placement 兩後端同源 advance [實作]：`horizontal_cell_advance_pt(shaper, cell, size, char_advance)`＝latin 走塑形自然寬、cjk／全形空格走 em 格；render（柵格）與 pdf_writer（座標）共用同一函式，保證位置同源。
- ✅ render 橫排路徑 [實作]：`horizontal_left_x_pt`（奇＝右頁訂口在左，自訂口內推；鏡像）＋`horizontal_baseline_y_pt`（行由上而下，首行含 ascent）幾何助手；`_draw_horizontal_cell`（LTR 塑形直接落頁面基線）；`render_page` 依 `vertical` 分派 `_draw_vertical_body`／`_draw_horizontal_body`。
- ✅ pdf_writer 橫排路徑 [實作]：`build_page` 依 `vertical` 分派 `_vertical_body`／`_horizontal_body`；橫排用 `horizontal_placements`（既有頁腳同款，水平 `1 0 0 1 x y Tm`）逐 cell 擺放，pen 推進與 render 同源。
- ✅ 模版 [實作]：F-版權頁主版 grid 改自擬橫排幾何（8pt CIP、字距 8.4pt＝×1.05、行距 14pt、滿行 34 字、每頁 27 行）；`版權頁-CIP橫排` 與 F 主版 note／evidence 標明 Sprint 13 已支援、版心自擬待 GAPS #13 量測。
- ✅ 自擬公開樣張 [實作]：`samples/cip-copyright.doc.json`（虛構書目 7 行 CIP，非參考書 p178 內容）＋`samples/README.md` 標紅線。

**測試成長**：115 → 127（+12：engine 橫排 tokenize/斷行 4；layout 方向判定／混用拒絕／未知模式拒絕／橫排不齊行／橫排幾何／render 橫排頁 6；pdf 橫排矩陣與閱讀序／兩後端位置同源／橫排 preflight 全綠 3；移除過時的 `test_export_rejects_horizontal_style` −1）。0 失敗、0 退步（連跑三輪穩定）。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：127 passed / 0 failed（`python -m pytest spikes tests -q`，連跑 3 輪穩定）
- 真實素材驗收（R5，紅線改自擬）：`samples/cip-copyright.doc.json`（虛構 CIP）→
  - render PNG（out/cip/page-001.png，300dpi）：Read 親驗 7 行橫排由上而下、字由左而右；CJK 等距、latin（ISBN 978-0-00-000000-0）自然寬且與 CJK 同基線；全形空格「　」em 留白；自訂口內推左起。
  - export PDF（out/cip/cip.pdf）：preflight **12/12 全綠**、思源宋體子集嵌入（57 字形）；PyMuPDF 獨立渲染（out/cip/cip-pdf-render.png）與 PNG 視覺一致（Gate 4）。
  - 兩後端位置同源：PyMuPDF 抽字 8 行首字座標，左緣皆 x0=81.0pt（bleed 8.5＋訂口 72.5）、基線每行 +14pt、首行 y=107.6（bleed 8.5＋天頭 92.1＋ascent 7.04），與 render 幾何助手推導值一致（單元測試 `test_export_horizontal_two_backend_position_parity` abs≤0.3pt 釘死）。
- 除錯紀錄：spike 首跑 `draw_horizontal_line` 漏傳 `img`（TypeError），補參數後即通過；產品化後測試一次 GREEN。

**代決事項（記入 PLAN §10）**：
- 橫排（horizontal-tb）版面軸形態：engine 加 `vertical` 參數復用斷行／禁則（橫排 ascii 整串成 latin run、不縱中橫）；layout 由樣式判頁面單一方向（混用／未知模式快速失敗）；兩後端幾何同源集中 placement `horizontal_cell_advance_pt`＋render `horizontal_left_x_pt`／`horizontal_baseline_y_pt`（latin 自然寬、cjk em 格、行由上而下）；橫排 CIP 短行不齊行。
- F-版權頁橫排版心為自擬合理幾何（8pt CIP），p178 真實版心未量測留 GAPS #13；紅線：公開 CIP 樣張全自擬。

**落差登記**：#13 橫排渲染部分關閉（渲染器已支援 horizontal-tb，不再報錯）；#13 剩項＝F 主版真實版心量測（p178）與 B〜G 其他扉頁佈局，續留。

**下個 Sprint 預定範圍**：全字庫正楷體 TW-Kai／正宋體入庫並驗題詞-楷書、引文-仿宋樣式（GAPS #12 剩項，需下載國發會 Open_Data 整包）；或從參考萃取 Phase 3（樣式面板前置）。斷行逐行一致率 vs 參考書比對仍待 Owner 抽檢。
