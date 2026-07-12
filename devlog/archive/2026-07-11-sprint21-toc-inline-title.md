# Sprint #21（2026-07-11）目錄篇名嵌線斷開＋條目縮退（p002/p003 量測），已完成

**範圍**：GAPS #13 (b) 目錄頁型剩項：篇名嵌線斷開＋條目縮退。依 Owner
「先挑最複雜架構」指示選定：三候選中唯一含新架構路徑（向量原件首次與
內容互動：layout 感知穿線行 → 虛線切段）。honest-planning R6 pre-mortem
先行（spikes/spike14-toc-inline-title/premortem.md）；R2 判定不需新 PoC
spike（斷線＝StrokeLine 多段復用、spike8 已驗 dash 與狀態隔離；縮退＝
幾何參數化，同 Sprint 19/20 模式）。

**一手量測（A 級，tools/measure_toc_page.py＋探針，p002/p003 三篇名互證）**：
- 篇名「第N篇」（W7 11pt 密排 3 字）：首字頂 y **107.96pt 三處同值**；
  第二字騎虛線（y 122.46）；其下部名詩句 W7 16pt（y 151.24 起，不穿線，
  字距 17.12 非 §10 換算 16.81）。
- 虛線非全寬：在篇名行處**斷開**，兩側 gap 不對稱：行前方（讀序前、x 大側）
  26.9〜30.1pt、行後方 3.7〜4.1pt（行槽緣口徑，取中值 28.5／3.9 入模版）。
- 帶起訖：前置條目區（目次大標、推薦序）無線；帶起於首篇名；跨頁延續
  記號＝前頁收於頁緣內 10mm、後頁自頁緣外 10mm 畫入（v1 不建模，入 GAPS）。
- 條目縮退：條目錨 135pt（Sprint 15 既定）−篇名天頭 107.96＝27.04pt；
  另量得多類條目天頭不一（Case 標籤 135.3、推薦序 146.7、章名黑 W5 167.2），
  屬「章名條目樣式層」剩項。
- 翻案記錄：Sprint 15「貫穿頁寬＋出血」為設計推定（當時只量參數未量 x
  起訖），本次量測證實真書分段；p003＝PDF 索引 2（pNNN＝PDF 頁號慣例確認）。

**完成**：
- ✅ engine [實作]：`ParagraphSpec.head_offset`（段級縮退槽揉進 start_slot，
  首行疊 indent、容量同縮；y 幾何與齊行零改動）。TDD RED 親證後 GREEN。
- ✅ styles [實作]：`head_offset_chars`＋`RuleSpec.break_before_pt/after_pt`。
- ✅ primitives [實作]：`toc_rule_segments`（gap 排序裁剪、零長段不產出）。
- ✅ layout [實作]：`RuleBreak`＋`rule_breaks`（穿線判定純幾何：行首字頂
  y＝top＋start_slot×字距 < 虛線 y；非樣式白名單，「嵌線」本義）。
- ✅ render/pdf [實作]：`rule_break_ranges`（行槽範圍±邊距，兩後端同源，
  同 line_axis_x_pt 先例）；兩後端 `_rule` 改多段。
- ✅ 模版 D [實作]：top 38.09mm、條目 head_offset 3、break 28.5/3.9、
  evidence 全記量測依據與已知差異。
- ✅ 工具 [實作]：tools/measure_toc_page.py（量測 JSON 本機不入 repo）。

**測試成長**：176 → 186（+10：engine 縮退 1、primitives 切段 3、layout
穿線 3、render 著墨斷開 1、pdf parity＋preflight 2）。0 失敗、0 退步。
既有 2 測試手算 title_end 補縮退槽（預期影響，動態斷言者自然涵蓋）。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py
  spikes/spike10-canvas-sync/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：186 passed / 0 failed
- 真實素材驗收（R5，樣張自擬 samples/toc.doc.json）：
  - render PNG（out/toc21/page-001.png，300dpi）**Read 親驗**：部名穿線
    （首字騎線）、虛線斷開兩側 gap 不對稱（前大後小，與真書同構）、
    條目縮退＋引導線＋頁碼底錨，p003 設計語言一致。
  - export PDF preflight **12/12**；字型警告不沉默（TW-Kai fallback，#12）。
  - **閉環獨立抽驗（Gate 4）**：PyMuPDF 抽兩段虛線端點 [0, 347.35]／
    [402.75, 436.54] 與 rule_break_ranges＋toc_rule_segments 手推
    **完全重合（0.00pt）**。
  - 第一章迴歸：22 頁、禁則 0、齊行擠入 10／撐開 1／超容忍 0 不變。
- 同類掃描（Gate 3）：render_page/build_page 全呼叫點 rule_breaks 接線
  確認（spike10 走預設空參數，素材 A 主版無 rule，行為不變）。

**代決事項（記入 PLAN §10）**：穿線判定用幾何（非樣式白名單）；縮退用
整數槽（+2.89pt 差入 GAPS，不擴 pt 偏移模型，同 Sprint 20 決議）；斷開
邊距取量測中值（真書手排離散誠實記錄）；帶起訖與篇序混排不建模。

**落差登記**：GAPS #13 (b) 更新（嵌線斷開＋縮退完成；剩「章名條目黑 W5」
樣式層＋帶起訖＋篇序混排已知差異）。

**下個 Sprint 預定範圍**：候選：(a) E 序文版頁型（量測＋參數化）；
(b) 抽取工具目錄模式；(c) 目錄「章名條目黑 W5」樣式層；(d) TW-Kai 入庫
（**需下載，須 Owner 同意**）。Owner 抽檢項累計：Spike 1 對比圖（#10）、
斷行逐行一致率、Spike 10 對位樣張、out/cip19 與 p178、out/part20 與真書
部扉、out/toc21 與真書 p003 並排比對。
