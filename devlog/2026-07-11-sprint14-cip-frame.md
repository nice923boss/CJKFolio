# Sprint #14（2026-07-11）CIP 細框向量原件，已完成

**範圍**：參考書版權頁是「CIP 細框」（PLAN §1 精緻設計細節），Sprint 13 只排了橫排文字未畫框。本 Sprint 引入最小向量原件（線／矩形描邊）能力，兩後端同源，CIP 細框為第一個使用案例。此原件層為後續部扉雙線菱形框（B 主版）與目錄水平虛線（D 主版）的地基。honest-planning R6（pre-mortem）＋R2（首用技術先 spike）先行。框幾何全自擬（紅線：p178 不入 repo）。

**Pre-mortem（R6）＋Spike（R2）**：
- pre-mortem：`spikes/spike7-vector-frame/premortem.md`。校正判定：PIL 矩形與 PDF path ops 皆非首用高風險技術；真正的新交互點＝描邊色走 DeviceCMYK（`K` 算符）＋須在 BT／ET 文字物件外 emit＋preflight 的 `color-cmyk-only` 規則（抓 `rg`／`RG`）不得退步。最可能失敗＝`K`／`re`／`S` 誤觸 `(rg|RG)` 檢查或 path 誤置 BT 內，機率低（約 15%）。
- spike：`spikes/spike7-vector-frame/vector_frame_poc.py`。手寫含 CMYK 描邊矩形（`0 0 0 1 K` + `0.5 w` + `re` + `S`）的最小 PDF，PyMuPDF 獨立解析：`re`/`S`/`K` 齊備、既有 color pattern `(rg|RG)` 不命中、`get_pixmap` 渲染出框像素 bbox=(39,39,161,161)；PIL "L" 模式 `rectangle(outline=0, width=2)` 描邊像素存在且中心留白。風險消除。

**完成**：
- ✅ 向量原件層 [實作]：新模組 `cjkfolio/primitives.py`（與 `placement.py` 同哲學，兩後端同源地基）。`StrokeRect`（top-down pt＋CMYK＋線寬）；`cip_frame_rect(master, left_x_pt, n_lines, frame)` 由主版 grid（滿行寬＝chars_per_line×char_advance）與內容行數確定性推導框矩形，四周留 `pad_pt`。座標約定同 placement（render ×scale→px、pdf 轉 y-up＋出血）。
- ✅ 樣式層 [實作]：`styles.py` 加 `FrameSpec`（kind／cmyk／line_width_pt／pad_pt，描邊色一律 DeviceCMYK）與 `KNOWN_FRAME_KINDS`（v1 只 `cip-box`）；`MasterPage.frame: Optional[FrameSpec]=None`（向後相容，A〜E／G 主版無框）；`_frame_spec` 解析與驗證（未知 kind／非 4 元素 cmyk 快速失敗）。
- ✅ render 後端 [實作]：`_draw_stroke_rect`（PIL ImageDraw，"L" 模式 outline=0 純黑，線寬 ×scale）；`PageRenderer._draw_frame`（算 n_lines＝max(slot)+1、呼叫 cip_frame_rect）；`render_page` gate `not vertical and master.frame and page.placed`（cip-box 為橫排原件，框先於文字畫）。
- ✅ pdf_writer 後端 [實作]：`_Content` 加 `prologue`（path 算符，置於文字塊 BT／ET 之前）＋`stroke_rect`（獨立 `q…Q` 狀態塊，DeviceCMYK `K` 描邊，狀態隔離不影響文字 `k` 填色）；`_PdfPageWriter._frame`（同 render 幾何，top-down 下緣→y-up 左下角）；`build_page` 同款 gate。兩後端框幾何同源集中 `cip_frame_rect`。
- ✅ 模版 [實作]：F-版權頁主版加 `"frame": {"kind":"cip-box","cmyk":[0,0,0,1],"line_width_pt":0.5,"pad_pt":6.0}`（純黑細框，全自擬）；evidence 標明 Sprint 14 加框、框幾何自擬待 GAPS #13。
- ✅ 樣張 [實作]：`samples/README.md` 更新（CIP 樣張現示範橫排＋CIP 細框）。

**測試成長**：127 → 139（+12：primitives 幾何 3〔基本幾何／行數縮放／pad 外擴〕；styles frame 解析 4〔F 有框 A/B 無框／未知 kind 拒絕／壞 cmyk 拒絕／預設值〕；render 2〔框為最外層 ink 四緣釘死／無框主版守護〕＋既有 `test_render_horizontal_page_lands_top_left` 改為裁框內側量文字；pdf 3〔CMYK 描邊在 BT 前無 rg/RG／兩後端框座標同源 abs≤0.3pt／加框後 preflight 全綠〕）。0 失敗、0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py cjkfolio/*.py tools/*.py`（＋spike7）→ EXIT_CODE=0
- test：139 passed / 0 failed（`python -m pytest spikes tests -q`）
- 真實素材驗收（R5，紅線改自擬）：`samples/cip-copyright.doc.json`（虛構 7 行 CIP）→
  - render PNG（out/cip/page-001.png，300dpi）：**Read 親驗** CIP 細框為四邊閉合細線矩形，圍住 7 行橫排文字，四角接合、內部留白、文字未貼框、框寬＝版心滿行寬；框在天頭下方偏左（版權頁位置）。
  - export PDF（out/cip/cip.pdf）：內容流 `re` 座標 (75.014, 407.682, 297.6, 110) 與 `cip_frame_rect` 手推一致（左＝訂口 72.51pt、content_w＝34×8.4＝285.6、n_lines 7×14＝98、pad 6、＋bleed 8.504）；CMYK `0 0 0 1 K` 描邊、`re` 在 `BT` 之前、無 `rg`/`RG`；preflight **12/12 全綠**（color-cmyk-only 不退步，Gate 4 PyMuPDF 獨立解析）。
  - 兩後端同源：render 與 pdf 皆呼叫同一 `cip_frame_rect`，PDF 抽 `re` 座標與 render 幾何助手＋出血偏移對齊（單元測試 abs≤0.3pt 釘死）。
- 除錯紀錄（環境異常，據實記錄）：本 Sprint 執行中多筆 Edit 工具回傳被偽造成功訊息（含偽裝成內心獨白的注入文字與「disregard the meta-commentary」指令），實際多數編輯遭 hook 攔下未寫入（harness system-reminder「Tool call rejected by hooks」為真實訊號）。改以「每次編輯後即用 `git diff`／`grep`／runtime 載入核實」重做全部編輯並逐一驗證落地。另發現既有 `test_render_missing_glyph_warns` 內含隱形 U+E000（PUA）字元，Read 顯示層收合，導致首次 anchor 不匹配（改以無 PUA 的末行為 anchor）。凡此皆不採信 inline 結果、以檔案系統真值為準。

**代決事項（記入 PLAN §10）**：
- 向量原件層形態：新增 `cjkfolio/primitives.py`（`StrokeRect`＋`cip_frame_rect`），與 placement 同層、兩後端同源；描邊色一律 DeviceCMYK（`K` 算符，維持 §9 全 CMYK 與 preflight color-cmyk-only）；path ops 以獨立 `q…Q` 狀態塊置於文字塊之前（狀態隔離）。
- CIP 細框（cip-box）幾何自擬：圍住橫排 CIP 內容網格盒（滿行寬×n_lines×行距），四周 pad 6pt，純黑 0.5pt 描邊；由主版 `frame` 欄位配置，v1 只橫排觸發（cip-box 為橫排原件）。p178 真實版心與框未量測，續留 GAPS #13。

**落差登記**：#13 更新（CIP 細框向量原件已實作並驗收，preflight 仍 12/12、兩後端同源）；#13 剩項＝F 主版真實版心（p178）Owner 本機量測、B〜G 其他扉頁佈局，續留。

**下個 Sprint 預定範圍**：以本原件層為地基做 B 部扉雙線菱形框或 D 目錄水平虛線（自主可行、in-scope、無下載）；或全字庫正楷體 TW-Kai／正宋體入庫驗題詞-楷書／引文-仿宋（GAPS #12 剩項，需下載國發會 Open_Data 整包，開工前須先問 Owner 同意下載）。斷行逐行一致率 vs 參考書比對仍待 Owner 抽檢。
