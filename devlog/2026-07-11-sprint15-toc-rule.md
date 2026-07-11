# Sprint #15（2026-07-11）目錄水平虛線向量原件，已完成

**範圍**：參考書目錄頁有「水平虛線分隔」（PLAN §1 精緻設計細節），Sprint 14 的
primitives 層只有描邊矩形。本 Sprint 加第二種原件（描邊線段＋虛線 dash），目錄
天頭虛線（D 主版）為第一個使用案例，兩後端同源。honest-planning R6（pre-mortem）
＋R2（新交互點先 spike）先行。與部扉框二選一的決策：部扉「雙線菱形框」經 p069
本機量測實為**手繪風向量**（單 draw 608 段不規則路徑），規則幾何自擬等效性低，
屬美術資產（PLAN §8 不生成美術）；虛線是規則幾何＋PDF `d` 算符的標準印前能力，
機制價值高，故先做虛線，部扉框續留 GAPS #13。

**一手量測（A 級，p003 本機，量測參數可入 repo、內容不可）**：
- 水平虛線兩段（篇名「第三篇」處斷開）：y=122.46pt、線寬 1.0pt、dash [3 2]
  （2.991/1.991 與 3.016/2.016，縮放誤差內＝標準 3/2）、灰 RGB 0.427 ≈ 單 K57。
- 虛線貫穿訂口並越出書口 MediaBox（x1=867.5 > 839 跨頁寬）＝貼邊出血全出。
- 目錄的 w=0.1 細線全是**垂直引導線**（條目→頁碼），非虛線本體；虛線起訖依
  篇區段內容縮退。引導線／頁碼／篇名斷開屬目錄頁型工程，不入本 Sprint。
- 條目內容起點 y≈135pt（Case 標籤實測）→ D 主版天頭定 47.63mm（內容在虛線之下）。

**Pre-mortem（R6）＋Spike（R2）**：
- pre-mortem：`spikes/spike8-dashed-rule/premortem.md`。新交互點＝PDF dash 算符
  `[ on off ] 0 d`（graphics state）＋非純黑灰 K 描邊＋PIL 手動分段虛線。
  最可能失敗＝dash 誤置／狀態外洩／preflight `(rg|RG)` 誤傷，機率低（約 15%）。
- spike：`spikes/spike8-dashed-rule/dashed_rule_poc.py` 三探針全過：[A] 手寫 dash
  線 PDF 經 PyMuPDF 解析 dashes='[ 3 2 ] 0'、渲染斷續 31 段、中位灰值 135、無
  rg/RG；[B] dash 在 q…Q 內、Q 後實線不被汙染（0 轉換）；[C] PIL "L" 分段虛線
  31 段、灰值 110（=255×(1−0.57)）。

**完成**：
- ✅ 原件層 [實作]：`primitives.py` 加 `StrokeLine`（端點＋cmyk＋線寬＋dash on/off，
  on=0 為實線）與 `toc_rule_line(page_width_pt, rule)`（y 取實測 122.46pt、x 貫穿
  頁寬並向兩側延伸出血 3mm，§9 貼邊元素出血全出）。
- ✅ 樣式層 [實作]：`styles.py` 加 `RuleSpec`（kind／y_from_top_pt 必填／cmyk／
  line_width_pt／dash_on_pt／dash_off_pt／bleed_extend_pt）＋`KNOWN_RULE_KINDS`
  （v1 只 `toc-rule`）＋`MasterPage.rule`（向後相容 None）；`_rule_spec` 驗證
  （未知 kind／壞 cmyk／缺 y 快速失敗）。
- ✅ render 後端 [實作]：`_draw_stroke_line`（PIL "L" 分段畫 dash，灰值＝255×(1−k)
  只取 k 分量，PNG 灰階預覽限制入 docstring）＋`PageRenderer._draw_rule`；gate＝
  `vertical and master.rule and page.placed`（toc-rule 為直排目錄原件）。
- ✅ pdf_writer 後端 [實作]：`_Content.stroke_line`（獨立 `q…Q`、`K` 灰描邊、
  dash_on>0 掛 `[ on off ] 0 d`、`m`/`l`/`S`，置於 BT 前）＋`_PdfPageWriter._rule`
  （top-down→y-up＋出血偏移）；同款 gate。兩後端幾何同源集中 `toc_rule_line`。
- ✅ 模版 [實作]：D-目錄加 `rule`（toc-rule、K 0.57、1.0pt、dash 3/2、y 122.46pt
  全為實測參數）；天頭 32.49→47.63mm（實測內容起點 135pt，修正文字穿線）；
  evidence 標實測來源與未實作項（篇名嵌線、條目縮退、直排頁碼 → GAPS #13）。
- ✅ 樣張 [實作]：`samples/toc.doc.json`（全自擬虛構條目：部名 1＋章條目 4）；
  `samples/README.md` 更新重現指令。

**測試成長**：139 → 151（+12：primitives 2〔toc_rule_line 幾何／dash_on=0 實線〕；
styles 5〔D 有 rule A/F 無／未知 kind 拒絕／壞 cmyk 拒絕／缺 y 拒絕／預設值〕；
render 2〔虛線斷續＋灰值＋貫穿頁寬＋虛線上方無字／無 rule 主版頁邊帶守護〕；
pdf 3〔d/m/l/S/K 在 BT 前無 rg/RG＋dashes 獨立解析／兩後端座標同源 abs≤0.3pt／
preflight 全綠〕）。0 失敗、0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py spikes/spike8-dashed-rule/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：151 passed / 0 failed（`python -m pytest spikes tests -q`）
- 真實素材驗收（R5，紅線改自擬）：`samples/toc.doc.json` →
  - render PNG（out/toc/page-001.png，300dpi）：**Read 親驗**灰色虛線橫貫整頁寬、
    斷續均勻；部名（宋 Heavy 16pt）與四條目（9.5pt）直排右至左全在虛線之下，
    無穿線（第一輪樣張文字穿線，天頭改 47.63mm 後重生成復驗）。
  - export PDF（out/toc/toc.pdf）：preflight **12/12 全綠**（color-cmyk-only 不
    退步）；內容流 `0.000 481.320 m / 436.535 481.320 l` 與 `toc_rule_line` 手推
    （bleed+x0=0、bleed+x1=436.535=154mm、page_h+bleed−122.46=481.32）**完全一致**；
    `[ 3 2 ] 0 d`＋`0 0 0 0.57 K` 在 BT 前、無 rg/RG；PyMuPDF `get_drawings` 獨立
    回報 dashes='[ 3 2 ] 0'、w=1.0。
  - 兩後端同源：PDF 獨立渲染（toc-pdf-render.png）Read 目檢與 PNG 後端一致；
    單元測試 abs≤0.3pt 釘死座標同源。
  - 字型警告不沉默：目錄條目（全字庫正楷體未入庫）fallback 思源宋並警告、
    部名 bold 以 heavy 替（皆 GAPS #12 既有）。
- 過程紀錄：第一輪樣張 Read 目檢抓到文字穿虛線（D 天頭承 A 32.49mm 在虛線之上），
  依 p003 內容起點實測改 47.63mm 並補測試斷言「虛線上方無文字墨」後復驗通過。
- 除錯紀錄（環境假信號，據實記錄）：收尾基線某一輪出現 2 failed
  （test_preflight_passes_on_exported_pdf 等），單跑通過、全套連重跑兩輪皆
  151 passed＋preflight 模組單獨 4 passed，判定為暫時性環境假信號（Windows
  防毒即時掃描鎖 tmp_path PDF 或 __pycache__ 併發干擾），依除錯紀律先排除
  環境假信號再懷疑程式碼，未改任何產品碼。

**代決事項（記入 PLAN §10）**：
- 虛線原件形態：`StrokeLine`＋`toc_rule_line` 兩後端同源；PDF 用原生 `d` dash
  算符（獨立 q…Q 隔離）、PNG 分段畫（灰值 255×(1−k) 只取 k）；虛線全頁寬貫穿
  ＋出血延伸，篇名斷開與條目縮退屬頁型工程留 GAPS。
- Sprint 15 標的選擇：虛線優先於部扉框（部扉框實測為手繪向量非規則幾何，
  規則化自擬等效性低；美術資產不生成，PLAN §8）。
- D 主版天頭修正 47.63mm（p003 內容起點 135pt 實測）；虛線 y 與天頭分離配置
  （rule.y_from_top_pt 獨立於 margins.top）。
- 補記 Sprint 13、14 漏更新的 CHANGELOG（v0.8.0、v0.9.0，內容取自 devlog 與
  commit message，標明補記）。

**落差登記**：#13 更新（目錄天頭虛線已實作並驗收；剩項改列：部扉手繪框規則化
不做〔美術資產〕、目錄頁型〔篇名嵌線、條目縮退、垂直引導線、直排數字頁碼〕、
F 與 B〜G 真實版心量測）。

**下個 Sprint 預定範圍**：候選（依 PLAN Phase 1 未完項）：(a) 目錄頁型第一片
（條目引導線＋直排數字頁碼，垂直引導線可復用 StrokeLine 實線模式）；(b) 全字庫
正楷體 TW-Kai／正宋體入庫驗題詞-楷書／引文-仿宋（GAPS #12 剩項，**需下載，開工
前須 Owner 同意**）；(c) B 部扉頁型（大標置位；裝飾框依 Sprint 15 決議不做規則化，
待使用者置入向量資產機制）。Owner 抽檢項不變：Spike 1 對比圖（GAPS #10）、斷行
逐行一致率、F 真實版心 p178 量測。
