# CHANGELOG

> Phase 0（Spike 1〜5）歷程見 devlog/；自 Phase 1 產品碼進場（Sprint 6）起立此檔。

## v0.43.0（2026-07-12，Sprint 48）Phase 2 編輯引擎跨段選取範圍（DocSpan 跨段刪除／替換）

### 新增

- [實作] cjkfolio/editing.py（**入 pytest 基線**）跨段選取範圍 DocSpan＋跨段刪除／替換，續 Sprint 41〜47 編輯核心，補齊改變段落邊界的範圍編輯（PLAN §6 Phase 2「選取」編輯；為 GAPS #26 跨段字元樣式所需的跨段範圍機制地基）：
  - `DocSpan`（凍結資料類）：起訖兩個 DocCursor 界定的跨段選取（start ≤ end，段索引優先再比 caret）；DocRange 為段內範圍，DocSpan 一般化為可跨段，同段（start.para_idx==end.para_idx）退化為段內範圍，start==end 為空範圍（刪除 no-op、替換退化純插入）。
  - `delete_span`（純文件層）：同段委派 delete_range；跨段時頭段保留 start 之前、尾段保留 end 之後併為一段承頭段樣式與 page_no（頭段存活，同 merge_paragraph 慣例），中間整段移除、兩端 run 各保字元樣式，全刪空正規化為單一空 run（守 document@2）；空範圍 no-op 回原物件。內部 `_slice_runs`（邊界 run 切割、保字元樣式、濾空段）與 `_validate_span`（para_idx 越界 IndexError、caret 越界或起點晚於終點 ValueError）。
  - `replace_span`（純文件層）：delete_span 後於縫（start.para_idx, start.caret）插入 text，新字承接縫左側 run 字元樣式（同 insert_text 慣例）；text 空＝退化純刪除。
  - `apply_delete_span`／`apply_replace_span`（回路層，對稱 apply_delete／apply_replace）：跨段編輯 → layout_document 全文重排 → locate_cell 反查；delete 新 caret＝縫、replace 新 caret＝縫＋len(text)；全刪空段 address=None。
  - `EditSession.delete_span`／`replace_span`：委派統一經 _commit 記錄 undo／redo（同 delete／replace／split／merge），非插入操作重置連續輸入序列（打斷 coalesce）。

### 驗證

- 核心基線 `pytest spikes tests` **346 passed / 0 failed**（326→346，+20，新檔 tests/test_edit_span.py：delete_span 11／replace_span 3／apply 4／EditSession 2）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 循 tests/ 分檔慣例（test_edit_style／test_edit_para_style 先例）：跨段編輯測試獨立為 tests/test_edit_span.py（自帶 fixture／helper／_FakeClock，不建共享 conftest），test_edit_engine.py 維持 794 行不撐破 800 上限。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅追加新函式與 EditSession 方法、未改既有函式與 editor/）。
- 真實素材驗收（R5，自擬多段內文樣張）：段 0「三房兩廳」到段 1「採光良好」跨段刪 → 頭「三房」＋尾「良好」併為單段「三房良好」reflow 0 違規、游標落縫左鄰「廳」；跨段替換「格局」→「三房格局良好」；併段承頭段樣式與 page_no、兩端 run 字元樣式各保，皆基線斷言。
- Gate 4 獨立驗證：pytest 走狀態機斷言（段數／text／run 樣式／堆疊），另寫獨立 probe 以不同路徑（直接印出觀察＋直接檢視 session._undo 深度）互證：跨段刪除段數 3→1、頭段存活承 style／page_no、兩端 run 樣式各保、同段退化＝delete_range 等價、替換於縫插入、apply reflow violations 空、session undo 深度 0→1→2 兩步歸零 can_redo=True、三守門（逆序／段越界／caret 越界）全擋，probe 跑完即刪（scratchpad 不入 repo）；繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3）

- [實作]（基線＋離屏驗）：DocSpan 跨段選取範圍、跨段刪除（頭尾併段承頭段樣式）／替換（於縫插入）、apply_* 回路 reflow 與游標反查、EditSession undo／redo 整合。
- [Shell]／待 Owner（GAPS #28／#19，離屏測不了）：app.py 尚未接線選取拖曳與跨段刪除／替換（滑鼠框選→跨段刪除為真視窗工程）。
- 尚未做（下一 Sprint 剩項）：跨段「字元樣式套用」（apply_char_style over DocSpan，GAPS #26）本 Sprint 只建範圍機制、未套字元樣式。

### 待 Owner 真實素材驗收（R5）

- 真視窗滑鼠跨段框選後刪除／替換的手感與視覺對位（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 跨段字元樣式套用（apply_char_style over DocSpan，關 GAPS #26 跨段字元樣式子項），或其他編輯引擎純邏輯離屏可驗項；編輯 UI 接線（選取／Enter／Backspace／undo／redo app.py 真視窗工程）待 Owner 真視窗回報批次。

## v0.42.0（2026-07-12，Sprint 47）Phase 2 編輯引擎連續輸入合併為單一 undo 單元（EditSession 輸入序列邊界合併）

### 新增

- [實作] cjkfolio/editing.py（**入 pytest 基線**）EditSession 連續輸入合併，續 Sprint 41〜46 編輯核心，補齊 Phase 2「復原重做」的輸入序列合併（對標 InDesign／多數編輯器逐字輸入合併為單一 undo 單元，PLAN §6 Phase 2）：
  - `EditSession.insert`（合併回路）：對前進打字（游標接續前一輸入 run 尾 caret＋兩次輸入間隔 `now − ts ≤ coalesce_window` 秒）併入同一 undo 單元（更新現態 document／cursor／layout，但不新增 undo 快照、不動 redo）；非合併路徑委派 `_commit` 起新 undo 單元（推編輯前態、清 redo）。每次輸入後記錄 `_pending_insert=(para_idx, run 尾 caret, 時戳)` 為序列新尾（含合併路徑刷新時戳為最近一次輸入）。
  - `_can_coalesce`：判定連續輸入是否併入當前單元（承前一輸入、`cursor.para_idx／caret` 接續其尾、未逾時間窗）；`_pending_insert is None` 即不合併。
  - 輸入序列邊界（皆令 `_pending_insert` 歸零、其後起新單元）：游標不連續、逾 coalesce_window、或任何非插入操作（delete／replace／split／merge／apply_style／apply_para_style 經 `_commit`；undo／redo 經 `_restore`）介入。
  - EditSession 建構加 keyword-only 參數 `coalesce_window`（預設 2.0s）與 `clock`（預設 `time.monotonic`）；既有 `EditSession(doc, template)` 建構相容不變，測試注入可控假時鐘離屏確定性驗時間邊界。

### 驗證

- 核心基線 `pytest spikes tests` **326 passed / 0 failed**（319→326，+7：連續合併一單元／redo 整串／游標不連續起新單元／逾時起新單元／恰達窗合併／刪除打斷／undo 重置序列）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅改 EditSession.insert／加 _can_coalesce／_commit 與 _restore 加序列重置、未改既有純函式與 editor/）。
- 真實素材驗收（R5，自擬 _plain 內文樣張）：連續前進打「三」「房」「兩」（游標 0→1→2 接續、凍結時鐘不逾窗）→ undo 堆疊深度只 +1、一步 undo 還原整串回「的老公寓」、reflow 0 違規；逾 2.0s 窗或刪除介入則起新單元、一步 undo 只退最後一字，皆基線斷言。
- Gate 4 獨立驗證：pytest 走狀態機斷言（can_undo／can_redo／document.text），另寫獨立 probe 以不同路徑（直接檢視 `session._undo` 堆疊深度＋逐步印出觀察）互證：連續三字深度只 +1、逾時／刪除打斷深度 +2／+3、redo 一步重做整串、預設真時鐘（time.monotonic）快速連打仍合併，probe 跑完即刪（scratchpad 不入 repo）；繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3）

- [實作]（基線＋離屏驗）：EditSession 連續輸入合併為單一 undo 單元、輸入序列邊界判定（游標連續性／時間窗／非插入操作打斷）、可注入時鐘離屏確定性驗時間邊界。
- [Shell]／待 Owner（GAPS #25／#19，離屏測不了）：app.py 尚未接線 undo／redo（Ctrl+Z／Y 鍵盤與選單為真視窗工程）。

### 待 Owner 真實素材驗收（R5）

- 真視窗連續打字後 Ctrl+Z 一步撤整串輸入的手感（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 續 Phase 2 編輯引擎純邏輯離屏可驗項，或編輯 UI 接線（app.py 樣式面板／Enter／Backspace／undo／redo 真視窗工程，待 Owner 真視窗回報批次）。

## v0.41.0（2026-07-12，Sprint 46）Phase 2 編輯引擎段落樣式變更（Paragraph.style 換名＋游標保持 reflow 回路）

### 新增

- [實作] cjkfolio/editing.py（**入 pytest 基線**）段落樣式變更，續 Sprint 41〜45 編輯核心，補齊 Phase 2「段落樣式套用」（對標 InDesign 段落樣式，PLAN §4.1）：
  - `change_paragraph_style`（純文件層，不碰 template）：把段 para_idx 的 Paragraph.style 換為 style，runs（含字元樣式）與 page_no 完全不變；樣式相同為 no-op 回原物件、不可變；para_idx 越界 IndexError；style 空字串 ValueError（守 document@2「段落需非空 style」不變式）。段落樣式名有效性不在此層驗，由 apply_para_style 的 layout_document 守門（同 apply_char_style／insert_text 慣例）。
  - `apply_para_style`（回路層，對稱 apply_insert／apply_style）：change_paragraph_style（改 cursor.para_idx 段）→ layout_document 全文重排 → locate_cell 反查；段落樣式變更不改 text，故游標（para_idx／caret）保持不變，reflow 後畫布落點隨版面更新、文件座標不動；未知段落樣式名由 layout_document raise KeyError（同 apply_style 字元樣式守門）。
  - `EditSession.apply_para_style`：委派 apply_para_style 統一經 _commit 記錄 undo／redo（同 insert／delete／replace／split／merge／apply_style）。

### 驗證

- 核心基線 `pytest spikes tests` **319 passed / 0 failed**（304→319，+15：change_paragraph_style 純文件層 8／apply_para_style 回路 3／EditSession 3／R5 往返 1）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅追加新函式與 EditSession 方法、未改既有函式與 editor/）。
- 真實素材驗收（R5，自擬 _plain 內文樣張）：內文「三房兩廳，約三十坪的老公寓。」段落樣式「內文-明體直排」→「引文-仿宋語錄」→ placed line.style 換名、reflow 0 違規、游標保持 caret 4、原文件不變；EditSession undo 回原段落樣式、redo 復原，皆基線斷言。
- Gate 4 獨立驗證：pytest 走狀態機斷言（Paragraph.style／layout placed line.style／堆疊深度），另寫獨立 probe 以「實際印出觀察」不同路徑互證（純函式換名／no-op／空字串守門、回路 placed line.style＝引文／violations 0／游標保持／undo-redo 往返、未知樣式 KeyError），probe 跑完即刪（scratchpad 不入 repo）；繁中標點 grep 無破折號。
- 誠實記錄（幾何 nuance）：測試用「內文→引文」兩樣式版面幾何參數相同（advance 12.08／cap 32／indent 2，差異僅字型明體 vs 仿宋於渲染層選字），故證的是「段落樣式參照流入 layout（placed line.style 換名）＋reflow 乾淨」，非斷行幾何改變；layout 由樣式推導幾何為結構保證（layout.py 依 p.style 取 ParagraphStyle）。改「內文→題詞-楷書」（indent 0 vs 2）則首行起點位移，機制不限樣式對。

### 誠實範圍（honest-planning R3）

- [實作]（基線＋離屏驗）：段落樣式換名純文件層、回路 reflow 與游標保持反查、EditSession undo／redo 整合。
- [Shell]／待 Owner（GAPS #27／#19，離屏測不了）：app.py 尚未接線段落樣式面板（游標所在段→套段落樣式 UI 為真視窗工程）。

### 待 Owner 真實素材驗收（R5）

- 真視窗段落樣式面板套用與視覺回饋（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 續 Phase 2 編輯引擎：連續輸入合併為單一 undo 單元（GAPS #25 剩項，需輸入序列邊界判定），或編輯 UI 接線（app.py 樣式面板／Enter／Backspace／undo／redo 真視窗工程，待 Owner 真視窗回報批次）。

## v0.40.0（2026-07-12，Sprint 45）Phase 2 編輯引擎字元樣式套用到選取範圍（run 模型切割＋相鄰同樣式併合）

### 新增

- [實作] cjkfolio/editing.py（**入 pytest 基線**）字元樣式套用，續 Sprint 41〜44 編輯核心，補齊 Phase 2「選取範圍套字元樣式」（對標 InDesign 字元樣式，PLAN §4.1）：
  - `apply_char_style`（純文件層，不碰 template）：對段內 DocRange [start, end) 逐字元改掛 char_style（None＝清除字元樣式、回段落樣式預設），範圍外字元保留原字元樣式；切割後連續同字元樣式的字元併為單一 run（避免碎片化，text 與視覺不變，同 InDesign 慣例）；空範圍 no-op 回原物件、不可變；para_idx 越界 IndexError、start／end 越界或 start＞end ValueError。
  - `apply_style`（回路層，對稱 apply_insert／apply_delete）：apply_char_style → layout_document 全文重排 → locate_cell 反查新游標；新 caret＝drange.end（游標停選取尾）；套用不改 text 故 Cell.span 座標系不動、字格 char_style 隨 run 模型流入渲染層；未知字元樣式名由 layout_document 守門（raise KeyError，同既有 run 驗證慣例）。
  - `EditSession.apply_style`：委派 apply_style 統一經 _commit 記錄 undo／redo 歷史（同 insert／delete／replace／split／merge）。

### 驗證

- 核心基線 `pytest spikes tests` **304 passed / 0 failed**（284→304，+20：apply_char_style 純文件層 12／apply_style 回路 4／EditSession.apply_style 3／R5 往返 1）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅追加新函式與 EditSession 方法、未改既有函式與 editor/）。
- 真實素材驗收（R5，自擬 _plain 內文樣張）：內文「三房兩廳，約三十坪的老公寓。」對 [5,8)「約三十」套「內文強調-明體W9」→ run 切割為三段（三房兩廳，＝None／約三十＝強調／坪的老公寓。＝None）、reflow 0 違規、游標停 caret 8、layout 字格 span 5-7 char_style＝內文強調（端到端流入渲染層）；EditSession undo 字元樣式全清回原、redo 復原，皆基線斷言。
- Gate 4 獨立驗證：pytest 走狀態機斷言（runs tuple／layout cell.char_style／堆疊深度），另寫獨立 probe 以「實際印出觀察」不同路徑互證（套用後三 run／reflow 0／游標 8／span 5-7 帶強調／undo-redo 往返），probe 跑完即刪（scratchpad 不入 repo）；繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3）

- [實作]（基線＋離屏驗）：字元樣式套用純文件層 run 切割與併合、回路 reflow 與游標反查、EditSession undo／redo 整合。
- [Shell]／待 Owner（GAPS #26／#19，離屏測不了）：app.py 尚未接線樣式面板（選取範圍→套字元樣式 UI 為真視窗工程）；DocRange 限段內（跨段選取套樣式需跨段範圍機制）為 v1 已知限制。

### 待 Owner 真實素材驗收（R5）

- 真視窗樣式面板套用字元樣式與視覺回饋（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 續 Phase 2 編輯引擎：段落樣式變更（change_paragraph_style，純邏輯可離屏驗，承段落樣式模型）、或連續輸入合併為單一 undo 單元（GAPS #25 剩項，需輸入序列邊界判定），或編輯 UI 接線（app.py 樣式面板／Enter／Backspace／undo／redo 真視窗工程，待 Owner 真視窗回報批次）。

## v0.39.0（2026-07-12，Sprint 44）Phase 2 編輯引擎 undo／redo 堆疊（EditSession 提交態歷史）

### 新增

- [實作] cjkfolio/editing.py `EditSession`（**入 pytest 基線**）＝編輯會談控制器，補齊 Phase 2「復原重做」核心：
  - 現態＝(document, cursor, layout)＋undo／redo 兩 (document, cursor) 快照堆疊，採標準「回上一個提交態」模型：編輯把編輯前態推入 undo 並清 redo；undo 把現態推入 redo、彈回上一態並 layout_document 全文重排（Spike 3 認可 7.67ms/章，非增量），redo 對稱。
  - 編輯方法 insert／delete／replace／split／merge 委派既有 apply_*（Sprint 41〜43），統一經 `_commit` 記錄歷史、回 EditResult；undo／redo 還原後 locate_cell 反查游標畫布落點、回 EditResult，無可回退／重做回 None（no-op）；can_undo／can_redo／document／cursor／layout 唯讀屬性。
  - 初始游標＝段 0 caret 0（v1 undo 還原上一提交態游標，不追 UI 中途點選）。

### 驗證

- 核心基線 `pytest spikes tests` **284 passed / 0 failed**（273→284，+11：starts_clean／insert／undo／redo／clear_redo／empty no-op×2／多步反向／游標反查／split-merge 路由／delete-replace 路由）；typecheck EXIT=0。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅追加 EditSession、未改既有函式與 editor/）。
- 真實素材驗收（R5，自擬 make_doc／_plain 樣張）：插入→undo 回編輯前文件、can_redo 真、undo 後重排 0 違規、游標反查落首字格「三」；redo 復原編輯；新編輯清空 redo；split／merge／delete／replace 皆經 session 記錄可反向 undo，皆基線斷言。
- 獨立方法：核心走 pytest 狀態機斷言（堆疊深度／文件內容／游標反查），editor 走 smoke_check 離屏建構；繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3）

- [實作]（基線驗）：undo／redo 提交態歷史、編輯方法路由、還原重排與游標反查。
- [Shell]／待 Owner（GAPS #24／#25／#19，離屏測不了）：app.py 尚未接線 undo／redo（Ctrl+Z／Ctrl+Y 鍵盤與選單為真視窗工程）；undo 粒度為每次 apply 一步（未合併連續輸入為單一 undo 單元）為 v1 已知限制。

### 待 Owner 真實素材驗收（R5）

- 真視窗 undo／redo 鍵盤操作與視覺回饋（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 續 Phase 2 編輯引擎：字元樣式套用到選取範圍（apply_char_style，純邏輯可離屏驗，承 run 模型與 DocRange），或編輯 UI 接線（app.py Enter／Backspace／刪除／undo／redo 真視窗工程，待 Owner 真視窗回報批次）。

## v0.38.0（2026-07-12，Sprint 43）Phase 2 編輯引擎跨段合併與分裂（para_idx 重編＋游標跨段映射）

### 新增

- [實作] cjkfolio/editing.py（**入 pytest 基線**）跨段合併與分裂，續 Sprint 41 插入／42 段內刪除，補齊改變段落數量的編輯：
  - `split_paragraph`（Enter 於段中分段）：於 cursor 把段切成 head（caret 前）／tail（caret 後）兩段，兩段同承原段落樣式；page_no 留於 head（保有原段身分）、tail 為 None；跨 run 切割時 caret 所在 run 一分為二、兩側各保字元樣式；空側正規化為單一空 run（守 document@2 不變式）；不可變、越界快速失敗。
  - `merge_paragraph`（Backspace 於段首併前段）：段 para_idx 併入前段 para_idx−1，合併段承前段樣式與 page_no（前段存活，InDesign 慣例）；runs＝前段＋本段串接、濾除空 run、全空正規化為單一空 run；para_idx 0 無前段可併 raise IndexError。
  - `apply_split`／`apply_merge`：對稱 apply_insert 的完整回路（編輯→layout_document 全文重排→locate_cell 反查新游標）；split 新游標＝tail 起點（para_idx+1, 0）、merge 新游標＝合併縫（para_idx−1, 前段原長）；tail 空段或合併全空段 address=None。para_idx 重編由 layout_document 依 enumerate 位置自動指派，cursor 指向新位置（split→idx+1、merge→idx−1）。

### 驗證

- 核心基線 `pytest spikes tests` **273 passed / 0 failed**（250→273，+23：split 10／merge 9／apply_split 2／apply_merge 2）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅追加新函式、未改既有函式與 editor/，插入回路不受影響）。
- 真實素材驗收（R5，自擬 make_doc C 個案扉頁樣張）：段 1 於 caret 4 分段→原段 2 順移段 3（para_idx 重編正確）、reflow 0 違規、tail 首字反查 cell.text＝「約」；段 2 併入段 1→原段 3 順移段 2、reflow 0 違規、合併縫反查前段末字 cell.text＝「廳」；跨 run 分裂／合併保兩側字元樣式、空段 address=None，皆基線斷言。
- 獨立方法：核心走 pytest 座標／span／para_idx 斷言，editor 走 smoke_check 離屏建構；繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3）

- [實作]（基線＋離屏驗）：跨段合併／分裂的核心邏輯、para_idx 重編、游標跨段映射與 reflow 回路。
- [Shell]／待 Owner（GAPS #19／#24，離屏測不了）：Enter／Backspace／刪除／範圍選取的鍵盤與拖曳畫布 UI 接線（app.py 未接線）為後續真視窗工程。

### 待 Owner 真實素材驗收（R5）

- 真視窗 IME 直排輸入與 Enter／Backspace／刪除／選取鍵盤操作（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 續 Phase 2 編輯引擎：直排畫布內嵌 IME 即點即打與 Enter／Backspace／刪除／選取 UI 接線（editor/ app.py 真視窗工程，待 Owner 真視窗回報批次），或編輯回路 undo／redo 堆疊（純邏輯可離屏驗，承編輯引擎核心）。

## v0.37.0（2026-07-12，Sprint 42）Phase 2 編輯引擎段內刪除與範圍替換（多 run 切割＋reflow 回路）

### 新增

- [實作] cjkfolio/editing.py（**入 pytest 基線**）段內刪除與範圍編輯，續 Sprint 41 插入回路：
  - `DocRange`（段索引＋段 text 半開區間 [start, end)，與 DocCursor caret 同座標系；start==end 為空範圍）。
  - `delete_range`：段內範圍刪除，橫跨多 run 逐 run 切除交集、保留兩端 run 及字元樣式，整個 run 落範圍內則連樣式一併消失；全段刪空回合法空段（text 為空，Paragraph 正規化為單一空 run，守 document@2 不變式）；不可變。
  - `replace_range`：delete_range 後於 start 插入，新字承接 start 左側 run 字元樣式（復用 insert_text 慣例）；text 空＝退化為純刪除。全刪再插無需改 insert_text（空段正規化為單一空 run，既有 for 迴圈於該空 run 邊界插入）。
  - `apply_delete`／`apply_replace`：對稱 apply_insert 的完整回路（編輯→layout_document 全文重排→locate_cell 反查新游標畫布落點）；全段刪空 address=None。

### 驗證

- 核心基線 `pytest spikes tests` **250 passed / 0 failed**（231→250，+19：delete_range 11／replace_range 4／apply_delete／apply_replace 4）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅追加新函式、未改 insert_text／apply_insert，C5 插入回路不受影響）。
- 真實素材驗收（R5，自擬 samples/case-divider 與 make_doc 樣張）：段內 [4,6) 刪「，約」→reflow 0 違規、游標反查 cell.text＝「廳」；範圍 [0,4) 替換「兩房」→reflow 0 違規、游標跟隨「房」；跨 run 刪除保留兩端字元樣式、全刪成空段 address=None，皆基線斷言。
- 獨立方法：核心走 pytest 座標／span 斷言，editor 走 smoke_check 離屏建構；繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3）

- [實作]（基線＋離屏驗）：段內刪除、範圍替換的核心邏輯與 reflow 回路。
- [Shell]／待 Owner（GAPS #19／#24，離屏測不了）：刪除／範圍選取的鍵盤與拖曳畫布 UI 接線（app.py 未接線）、跨段合併／分裂（Backspace 段首併前段、Enter 分段，改 para_idx 語意需新機制）為後續。

### 待 Owner 真實素材驗收（R5）

- 真視窗 IME 直排輸入與刪除／選取鍵盤操作（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 續 Phase 2 編輯引擎：直排畫布內嵌 IME 即點即打與刪除／選取 UI 接線（editor/ UI 工程，待 Owner 真視窗回報），或跨段合併／分裂機制（需 R1 設計 para_idx 重編與游標跨段映射）。

## v0.36.0（2026-07-12，Sprint 41）Phase 2 編輯引擎 reflow 回路（游標插字→重排→反查新游標）

### 決策（Owner「最複雜架構先做」常設定案下，承 Sprint 40 預告的 Phase 2 編輯引擎）

- Phase 2 最複雜且可離屏驗證的架構核心＝編輯回路「寫」方向（Sprint 40 只有「讀」方向 resolve_hit），正對應 §7 Pre-mortem 未退場最大風險「畫布與排版核心同步／選取錯位」。核心置 cjkfolio/（非 editor/）並入 pytest 基線；游標座標系＝段 text 半開座標（與 Cell.span 同）；reflow 全文重排（Spike 3 認可 7.67ms/章，非增量）。

### 變更

- [實作] cjkfolio/editing.py（**入 pytest 基線**，純邏輯非 GUI，與 layout/engine 同層）：DocCursor／CellAddress／EditResult＋insert_text（不可變、run 邊界左偏承接字元樣式、越界快速失敗）／locate_cell（resolve_hit 的逆，Cell.span 反查、段內命中唯一、查無回 None）／apply_insert（插字→layout_document 全文重排→反查新游標畫布落點）。
- [實作] tests/test_edit_engine.py：13 測試（插字 7／run 邊界 2／locate_cell 2／apply_insert 2），素材自擬（C 個案扉頁樣式）。
- [實作] editor/app.py：IME 提交回路接線（returnPressed→_on_ime_commit→apply_insert→_rebuild 重繪→游標跟隨）；_on_ime 拆為 _on_ime_preview（組字預覽）＋_on_ime_commit（Enter 提交）；誠實範圍 docstring／說明對話框更新。**噪音清理**：移除未使用的 import QTransform。
- [實作] editor/smoke_check.py：新增 C5 編輯回路離屏驗（選內文字格→提交→reflow→游標跟隨），升級 Sprint 40 一次性 app 探針為永久回歸。

### 驗證

- 核心基線 `pytest spikes tests` **231 passed / 0 failed**（218→231，+13）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C4（48/48）＋**C5「段3內文插『測試』→reflow（1 頁 0 違規）游標跟隨到『試』」**。
- 真實素材驗收（R5，自擬 samples/case-divider C 個案扉頁）：apply_insert 段 3 插「大大」→文件實變且原文件不變、reflow 0 禁則違規、新游標 cell.text＝「大」，皆基線 Read 斷言。
- 獨立方法：核心走 pytest 座標／span 斷言，app 接線走 smoke_check QMainWindow 離屏建構，兩路互證；繁中標點 grep 全綠無破折號。

### 誠實範圍（honest-planning R3；GAPS #19）

- [實作]（離屏驗）：編輯回路「打字→插入→全文 reflow→畫布更新→游標跟隨」。
- [Shell]／待 Owner（離屏測不了）：真視窗 IME 直排組字順暢度、提交後 reflow 視覺流暢與對位；直排畫布內嵌 IME 即點即打、拖曳／範圍選取、刪除編輯（v1 只插入）為後續 UI 工程。

### 待 Owner 真實素材驗收（R5）

- 真視窗 `python editor/app.py`：點內文字格→輸入區組字→Enter，確認 reflow 即時、游標跟到插入字、直排 IME 候選字窗正常、字形與互動層對位（GAPS #19）。
- 並行 Owner-hands-on：GAPS #10（Spike 1 對比圖抽檢）、#23（斷行逐行一致率）。

### 下個 Sprint 預定範圍

- 續 Phase 2 編輯引擎：刪除與範圍編輯（delete_range，locate_cell 已備反查）、或畫布內嵌 IME 即點即打（editor/ UI 工程，待 Owner 真視窗 IME 回報）。

## v0.35.0（2026-07-12，Sprint 40）Phase 2 開工：PySide6 真視窗畫布骨架（技術棧定案＋點字格反查文件游標）

### 決策（Owner AskUserQuestion 定案「建 PySide6 真視窗 demo 骨架」）

- Phase 1 收尾後 Owner 定案進 Phase 2，並於 Phase 2 開工方式三選項（建 PySide6 真視窗 demo 骨架／先做 Owner 抽檢／另定範圍）選**建 demo 骨架**。**技術棧正式定案 PySide6**（Qt 6 官方綁定、LGPL；Spike 10 A 級數據，§5.2「Phase 2 開工定案」條件成就）。

### 變更（editor/ 新套件，不入 pytest 基線）

- [實作] editor/canvas.py：雙層畫布核心。底圖層＝既有 PNG 渲染後端（QGraphicsPixmapItem z=0）；互動層＝layout 幾何直接生成透明字格（QGraphicsRectItem z=1，data=(placed_idx, cell_idx)）。iter_cell_rects 逐項對齊 render._draw_vertical_body（line_axis_x_pt／style_advance_pt／line_justified_advance／lead_offset_pt，兩後端同源）。resolve_hit 點字格 → 文件游標（para_idx／span／text，承 Sprint 18 provenance）。
- [實作] editor/app.py：真視窗 QMainWindow demo（雙層畫布顯示＋點字格反查游標＋高亮＋IME 測試區＋Owner 實測說明對話框＋製作者標示）。
- [實作] editor/smoke_check.py：離屏 Gate-5 驗證（可跑＋雙層建構＋hit-test 100%＋provenance 一致），不入 pytest 基線（Sprint 17：GUI 不綁核心），獨立跑。
- [Doc] editor/README.md：執行方式＋誠實範圍表＋Owner IME 實測協議。

### 驗證

- 離屏 smoke_check（samples/case-divider 自擬 C 個案扉頁）：雙層畫布建構、hit-test **48/48** 全對、48 cjk 字格 provenance span 切片＝cell.text；樣本 段0 字(0,1)＝「案」。
- app 離屏建構：EditorWindow 建構無誤，模擬點選 段5 字(12,13)＝「。」（provenance 讀出）＋IME 回呼＋高亮皆驗。
- 核心基線 `pytest spikes tests` **218 passed**（editor/ 未被收集，守 Sprint 17）；typecheck EXIT=0。
- 繁中標點：editor/ 與本 Sprint 改動檔 grep 無破折號殘留。

### 誠實範圍（honest-planning R3；詳 editor/README.md）

- [實作]（離屏驗）：雙層畫布顯示＋點字格反查文件游標。
- [Shell]／待 Owner（GAPS #19，離屏測不了）：真視窗視覺對位＋IME 直排輸入鍵盤實測；直排畫布內嵌 IME 編輯（打字→插入→reflow）為 Phase 2 編輯引擎後續工程，本骨架僅示範「IME 組字 → 已知游標目標」不變更文件、不 reflow。

### 下個 Sprint 預定範圍

- 待 Owner `python editor/app.py` 真視窗鍵盤實測 IME 直排輸入與視覺對位（GAPS #19）。回報順暢後進 Phase 2 編輯引擎（游標插入→局部 reflow→畫布更新），或依 Owner 指示調整畫布架構。

## v0.34.0（2026-07-12，Sprint 39）Phase 1 骨架收尾定案（honest review＋Known Limitations 彙整，Owner 定案收尾轉 Phase 2）

### 決策（Owner AskUserQuestion 定案「收尾轉 Phase 2」；honest-planning R5／R7）

- Sprint 38 完成 C 個案扉頁資訊區欄位卡片，「最複雜架構先做」線程收束，Phase 1 已無需新引擎機制的大型建模。Owner 經 AskUserQuestion 於三選項（收尾轉 Phase 2／續建小型變體／建目錄摘要層）定案**收尾轉 Phase 2**。本 Sprint [Doc] 無程式碼變更：honest review 確認 Phase 1 骨架完成、彙整 Known Limitations、正式關 Phase 1、標記 Owner-only sign-off 待辦，下個 Sprint 進 Phase 2 首項。

### honest review（A 級實查，非橡皮圖章）

- 模版 templates/neizai-zhengli.json 實查：**A〜G 七主版齊備**（grep 命中 7 master id）、段落樣式 18／字元樣式 9。
- 引擎能力：直排版面（禁則／約物擠壓／齊行擠入／縱中橫／橫排／依書頁號鏡像）＋自寫 PDF/X-1a:2001 匯出（OutputIntent／XMP／GTS 兩鍵／子集嵌入）＋機械 preflight 12 規則＋txt／md 匯入＋兩後端（PNG／PDF）幾何同源。
- 基線：`pytest spikes tests` **218 passed / 0 failed**、typecheck（py_compile 全部）EXIT=0。
- 結論：**Phase 1 §6 骨架機制級 DoD 達成**。

### 變更（[Doc]，無程式碼／測試變更）

- [Doc] 開源CJK排版編輯器-PLAN.md：§6 新增「Phase 1 收尾判定（Sprint 39）」子節（鏡像 Phase 0 閘門判定體例）；§10 新增 Sprint 39 決議列。
- [Doc] GAPS.md：新增 #22（Phase 1 收尾 Known Limitations 彙整，剩項分甲 細項延後／乙 需新機制／丙 §8 美術不生成／丁 後續 Phase 四類）、#23（斷行逐行一致率比對待 Owner sign-off，與 #10 同批）。
- [Doc] devlog/archive/2026-07-12-sprint39-phase1-closure.md：本 Sprint 記錄。
- [Doc] CHANGELOG.md：本條。

### 正式 sign-off 待 Owner（R5 人類抽檢，執行工程師不代行）

- GAPS #10：Spike 1 對比圖 spikes/spike1-vertical-core/out/spread_comparison.png 抽檢（Phase 0 正式通過前提）。
- GAPS #23：斷行逐行一致率比對（Phase 1 DoD 一致度抽檢的斷行維度）。
- 二者為 Owner-hands-on；排版機制級品質已 A 級驗證且樣張 0 禁則違規，但「無重大排版瑕疵」與「逐行一致率」屬人類品質判斷。

### 驗證

- 測試數 218 不變（[Doc] Sprint 無程式碼變更）；typecheck EXIT=0。
- 繁中標點：本 Sprint 改動檔（PLAN／GAPS／devlog／CHANGELOG）grep 確認無破折號殘留。

### 已知限制（詳 GAPS.md #22）

- Phase 1 剩項全數為 細項延後／需新機制（v1 不建模）／§8 美術不生成／後續 Phase，均不阻擋轉 Phase 2；開源釋出前以 Known Limitations 公開承認（R7）。

### 下個 Sprint 預定範圍

- Phase 2 開工首項＝Qt 畫布 IME 直排輸入真視窗實測（GAPS #19）；§5.2 選 Qt 的關鍵理由（IME 一等公民）本機未實測，且 §7 Pre-mortem 未退場最大產品風險＝畫布與排版核心同步（僅 Spike 10 初驗）。GAPS #19 註明需真視窗 demo＋Owner 鍵盤實測，屬 Owner-hands-on，執行工程師先備 demo 骨架。

## v0.33.0（2026-07-12，Sprint 38）C 個案扉頁資訊區欄位卡片建模（否決「需新機制」前提，勘正 Sprint 25 第五例誤讀）

### 決策（honest-planning R1 先量測再動工；承 Sprint 37 交接「線性堆疊不可表達需新機制」）

- Sprint 37 交接資訊區「線性堆疊不可表達需新機制」為初步判斷。依 R1 先量測全 33 個案扉頁（scratchpad 探針跑完即刪），確認真實結構才定機制。**架構結論**：資訊區欄位卡片＝相鄰不同 slot 的線性段落（欄位標籤與內文非同 slot inline 分區），現有線性流排（engine.flow_pages）＋既有樣式＋indent／gap_after 即足表達，**無需新引擎機制**（同 Sprint 31/34/35 量測後否決「需新機制」前提）。R2 判定既有能力復用、無需新 spike（先例＝E 序文版 Sprint 23 推薦序大標 gap 4→內文 slot 5 同機制）。

### 量測（A 級一手證據，本機紅線不入 repo）

- 全 33 個案扉頁探針：**首內容 slot 分佈 33/33＝slot 5、空 slot 2~4 為鐵律**（大標 slot 1 後空 3 slot）。勘正 Sprint 25「內文自 slot 2（top 145.75）」誤讀＝第五例 C 主版 slot 誤讀（承 Sprint 34/35/36）。
- 資訊頁 10（欄位卡片）／訪談頁 23（純內文流）；欄位標籤（NotoSans 11.4pt、top 92.3 頂格＝indent 0）＋欄位內文（DFMingStd 11.5pt、首列 top 116.5＝indent 2 縮排、續列 top 92.1），欄位間固定空 1 slot。13pt DFHeiStd 中標經量測屬訪談頁節標題（＝章節小標-黑體），不在資訊區（與資訊頁 0 重疊）。

### 變更

- [實作] templates/neizai-zhengli.json：個案扉頁大標-NotoSans para_gap 0→3（大標後空 slot 2~4、內容自 slot 5），note 記 Sprint 38 全 33 頁量測勘正 Sprint 25。資訊區欄位卡片復用既有樣式（欄位標籤＝個案中標-NotoSans indent 0/gap 0、欄位內文＝內文-明體直排 indent 2/gap 1），無新增樣式。
- [實作] samples/case-divider.doc.json：升級為欄位卡片（自擬「【空間】／【成員】」兩欄位，欄標＋大標＋兩組標籤／內文），slot [0,1,5,6,8,9] 空 2~4／7。
- [實作] tests/test_layout_render.py：C 測試充實欄位卡片守門（slot 佈局 [0,1,5,6,8,9]、大標 para_gap 3、欄位標籤 indent 0／內文 indent 2、空 slot 2~4/7）。
- [實作] tests/test_pdf_writer.py：case 置中測試延伸欄位卡片（slot 0/5/6/8/9 字墨扣出血對準各自 line_axis，兩後端 parity）。

### 驗證

- 全套 `pytest spikes tests` 218 passed / 0 failed（測試數不變＝勘誤＋既有機制建模型 Sprint，同 Sprint 26/31）；typecheck（py_compile 全部）EXIT=0。
- 真實素材驗收（R5）：render case-divider PNG（first-page 20 偶＝右頁）三字型（SourceHanSansTC-Bold 欄標／Medium 大標＋欄位標籤／SerifTC 內文，欄標 Bold 不 fallback）、0 禁則；export PDF preflight 12/12。
- Gate 4 獨立驗證：PNG 墨跡直列分析（程式化，視覺 Read 因 context limit elided）＝6 直列 cx 對準 slot 0/1/5/6/8/9 line_axis（354.1／331.3／239.3／216.2／170.4／147.4pt），列1→2＝4.00 slot（空 2~4）、列3→4＝1.99 slot（空 7）；三方同源＝layout slot [0,1,5,6,8,9]／PDF 字墨 cx／PNG 墨跡直列 cx 皆對準 line_axis。
- 繁中標點：本 Sprint 改動檔（模版／樣張／二測試／PLAN／GAPS／devlog／CHANGELOG）無破折號字元殘留。

### 已知限制（詳 GAPS.md #13）

- 10.5pt 訪談頁欄標變體（7 頁「理解與祝福」）以主流 11.5pt 建模、未建獨立樣式。
- 資訊區多欄位動態列數以真書內容驅動；自擬 case-divider 示範兩欄位，機制不限欄位數。
- 續留 #13 其他剩項：F 版權頁真實版心 p178、目錄摘要層／【結語】變體、部扉裝飾框（美術資產）、B~G 其他扉頁逐頁量測。

## v0.32.0（2026-07-12，Sprint 37）C 個案扉頁 slot 0 黑 W7 欄標樣式建模（Owner 定案升級 C）

### 決策（honest-planning R1／R5 先量測再動工；Owner AskUserQuestion 定案升級 C）

- Owner 於 Sprint 36 收尾定案「升級定案 C」（完整重定 C 主版，推翻 Sprint 35「選 B 不重定模型」），啟動 GAPS #13 黑 W7 欄標專項。依 R1 先量測 33 個案扉頁完整幾何，找到真實目標才建模。**架構判定**：slot 0 欄標與 slot 1 大標自 inline 天頭起、block 軸相鄰堆疊，現有單欄線性流排（engine.flow_pages）可表達，本 Sprint 建模；資訊區（slot 5+ 欄位標籤／內文交替、slot 2~4 空欄）為空間分區超出線性堆疊，拆 Sprint 38（與 Owner 建議吻合）。

### 量測（A 級一手證據，本機紅線不入 repo）

- slot 0 欄標（cx 354.6）：DFHeiStd-W7、首字頂 92.1＝天頭 92.09（承 A）、縱向 4~6 字佔 block slot 0 一行；11.5pt×26 頁（資訊頁「個案資料」等）主流、10.5pt×7 頁（訪談頁「理解與祝福」）變體。字框頂天頭、墨頂差為字型 bearing（lead_offset 0，同部扉／大標先例）。
- slot 1 大標（cx 331.6）：NotoSans 17.9pt、首字頂 98.0（33 頁齊一）＝天頭＋bearing 5.9pt。
- 資訊區（cx 93~231＝slot 5~11）：欄位標籤 NotoSans 11.4pt（「【格局】【居住者】」天頭 92.3）＋內文 DFMingStd 11.5pt（縮排 top 116.5）＋13pt DFHeiStd 中標交替；slot 2~4 空欄；列數 4~7（衆數 6）。

### 變更

- [實作] templates/neizai-zhengli.json：新增段落樣式 `個案欄標-黑W7`（思源黑體 Bold 11.5pt、indent 0、para_gap 0、lead_offset 0、source_font DFHeiStd-W7），note 記 A 級量測參數（cx 354、天頭 92.09、11.5×26／10.5×7 變體、W7＝Bold 不 fallback）；C 主版 evidence 更新「slot 0 已建模」。段落樣式 17 → 18。
- [實作] samples/case-divider.doc.json：slot 0 `個案中標-NotoSans` → `個案欄標-黑W7`（自擬「案例速寫」），個案中標移出（真實位置＝資訊區，Sprint 38）。
- [實作] tests/test_styles.py：新增 `test_case_hei_label_style_modeled` 守門（font bold／11.5pt／indent 0／para_gap 0／lead_offset 0／source_font DFHeiStd-W7、與個案中標分離）。
- [實作] tests/test_layout_render.py／test_pdf_writer.py：case-divider slot 0 測試改欄標（layout slot [0,1,2] 欄標／大標／內文、line_axis 欄標 354.25＋大標 331.25；PDF 字墨扣出血＝各自 line_axis）。

### 驗證

- 全套 `pytest spikes tests` 218 passed / 0 failed（217 → 218）；typecheck（py_compile 全部）EXIT=0。
- 真實素材驗收（R5 建模 Sprint 非純守門）：render case-divider PNG（first-page 20 偶＝右頁）欄標用 SourceHanSansTC-Bold（W7→Bold 不 fallback，字型使用訊息證）、0 禁則違規；export PDF preflight 12/12。
- Gate 4 獨立驗證：render PNG 墨跡三直行 trim_cx（程式化墨跡分析，視覺 Read 因 context limit elided）＝欄標 354.2／大標 331.2／內文 308.2 吻合 line_axis 354.25／331.25／308.25（slot 0/1/2，差 0.05pt）；欄標 y頂 32.68mm＝天頭、4 字縱向 y底 48.94mm＝4×11.5pt 佔 block slot 0 一行；3 直行無 notdef 爆量。兩後端 parity：PDF 側 `test_case_ttb_ink_centered_on_line_axis` 欄標 slot 0 字墨扣出血＝axis_label 354.25，與 PNG 側 354.2 同源。
- 繁中標點：本 Sprint 改動檔（模版／樣張／三測試／PLAN／GAPS／devlog／CHANGELOG）無破折號字元殘留。

### 已知限制（詳 GAPS.md #13）

- 資訊區多欄位佈局（slot 2~4 空欄＋slot 5~11 欄位標籤／內文／13pt 中標交替，線性堆疊不可表達需新機制）＋個案中標移資訊區為 Sprint 38 專項。
- 10.5pt 訪談頁欄標變體（7 頁「理解與祝福」）以主流 11.5pt 建模、變體 note 記錄，未建獨立樣式。
- 續留 #13 其他剩項：F 版權頁真實版心 p178（待 Owner 本機量測）、目錄摘要層／【結語】變體、部扉裝飾框（美術資產待向量置入機制）、B〜G 其他扉頁逐頁量測。

## v0.31.0（2026-07-12，Sprint 36）旁注 9pt／Case 編號 15.9pt 兩「掃描見變體」量測確認為真（GAPS #13 待查標記清查完畢）

### 決策（honest-planning R1／R5 先量測再動工）

- 候選 A（承 Sprint 34 Gate 3 待查標記清查收尾）＝`旁注-手札圖注` 9pt 與 `Case編號-手寫拉丁` 15.9pt 兩「掃描見變體」待查標記（templates note 記「（掃描）」未量測）。依 R1 先量測，確認真實變體或掃描誤植。**結論：與 Sprint 34（12.9pt）／35（slot 0 13pt）誤植 0 命中相反，兩變體皆真實存在**。處置（同 Sprint 34／35 勘正記錄型）：變體屬美術／自由佈局層（§8）Phase 1 無渲染用例，不建獨立樣式（建模會是 [Shell]，登記 GAPS #13 後續）；以勘正 note 升 A 級量測參數＋守門交付。不推翻核心決議，無須 Owner 定案。

### 量測（A 級一手證據，本機紅線不入 repo）

- A HanziPen（華康手札體）：8.0pt 主體 173 頁（頁腳書眉副標與旁注同級）；9.0pt（raw 8.955）變體 4 頁（PDF 25／60／61／93）34 字、頁面中上部 top 82~338（非頁腳 508）＝圖注大一號（note 原記「9pt 變體掃描 4 頁」頁數吻合）。
- B Pepita（Case 編號拉丁）：9.0pt 頁腳主體 153 頁（top 508.3）；15.9pt（raw 15.92）章扉大號 10 頁（PDF 19／35／53／69／84／98／115／133／144／156）top 86.2；另揭 10.4pt（raw 10.447）目錄 Case 編號 2 頁（PDF 1／2）note 原漏。
- C 全書 8.5~9.5pt 級數反查：HanziPen 9pt 獨立 34 字 4 頁，與 Pepita 9pt 頁腳、楷 W3 9.5 目錄各自分離（非捨入邊界）。
- D 全書 15~17pt 級數反查：Pepita 15.9pt（61 字 10 頁）與辰宇落雁 15.9pt（186 字 31 頁圖說／裝飾大字）同級不同字型，不可混淆。

### 變更

- [實作] tests/test_styles.py：新增 `test_handwritten_variants_measured_not_conflated` 守門（旁注主體 8.0!=9.0、Case 編號主體 9.0!=15.9 與 source_font，且 Pepita 15.9 章扉與辰宇 15.9 圖說同級不同 source_font 防混淆）。測試 216 → 217。
- [實作] templates/neizai-zhengli.json：`旁注-手札圖注`／`Case編號-手寫拉丁` 兩 note 勘正，「（掃描）」待查語氣升 A 級量測參數；Case 編號 note 補記原漏 10.4pt 目錄變體。size／source_font 不動（status-quo，不新增樣式）。

### 驗證

- 全套 `pytest spikes tests` 217 passed / 0 failed；typecheck（py_compile 全部）EXIT=0。
- Gate 4 獨立驗證：量測（PyMuPDF get_text span font／size／bbox）與守門測試（模版載入斷言 size_pt／source_font）不同方法互證；C／D 級數反查決定性交叉（各字型變體獨立命中，非單點推論）。
- Gate 3 同類掃描：「掃描見變體」為 Sprint 34 Gate 3 待查類；本 Sprint 釐清最後兩個（旁注 9pt／Case 編號 15.9pt），grep 模版確認兩 note 均已勘正，該類全數清查完畢。
- 繁中標點：本 Sprint 改動檔（模版／test_styles／GAPS／PLAN／devlog／CHANGELOG）無破折號字元殘留。

### 已知限制（詳 GAPS.md #13）

- 兩變體真實存在但屬美術／自由佈局層（§8），Phase 1 無渲染用例，不建獨立樣式；變體建模（旁注 9pt 圖注、Case 編號 15.9pt 章扉大號、10.4pt 目錄）登記後續專項（需 Owner 決定投入，與 Phase 2〜4 圖片置入／圖文繞排相關）。
- 續留 #13 其他剩項：黑 W7 欄標樣式建模＋個案中標移資訊區（Sprint 35 揭露，屬定案 C 需 Owner 確認）、F 版權頁真實版心 p178（待 Owner 本機量測）、目錄摘要層／【結語】變體、部扉裝飾框（美術資產待向量置入機制）、B〜G 其他扉頁逐頁量測。

## v0.30.0（2026-07-12，Sprint 35）個案扉頁 slot 0「Case 編號 13pt 雙元素」量測否決＋Sprint 25 誤讀勘正（GAPS #13）

### 決策（honest-planning R1／R5／R8 先量測再動工；Owner AskUserQuestion 定案 B）

- 候選 A（Owner「最複雜架構先做」常設指令）＝個案扉頁 slot 0「Case 編號黑 W5 13pt『01』雙元素」建模。依 R1 先量測，兩路探針 33 頁交叉驗證推翻前提：slot 0 無 Case 編號 13pt「01」（係把頁腳 Case 編號誤植＋臆造字級），連帶揭露 Sprint 25 對 C 主版 slot 0 系統性誤讀。第四例掃描誤讀（承 Sprint 23 署名長橫、24 摘要層字型、34 的 12.9pt），最深（推翻 Sprint 25 slot 0 建模）。Owner 定案 B（勘正記錄＋守門，不重定模型）：誠實記錄量測真相＋守門防復現，模型重定登記後續專項。

### 量測（A 級一手證據，本機紅線不入 repo）

- Q1 slot 0（cx 354.25±8）跨 33 頁：DFHeiStd-W7 11.5pt×26 頁／10.5pt×7 頁欄標「個案資料／廖心筠整理／鄧惠文醫師／心理師訪談／理解與祝福」，33 頁全覆蓋、0 個 NotoSans 11.4、0 個 13pt。
- Q2 個案中標 NotoSans 11.4pt：141 span，cx 全落 93~231（median 230.94），非 slot 0（354），在資訊區內文欄。
- Q3 DFHeiStd 13pt：132 span，cx 117~240，為資訊區內文中標「父母的留戀…」，非 slot 0 編號。
- Q4 黑體與大字數字編號「01」全書 0 命中；真書 Case 編號＝頁腳 PepitaMT 9pt「Case 1／2／3」（top 508.3，33 頁齊備）。

### 變更

- [實作] templates/neizai-zhengli.json：個案中標 note＋C-個案扉頁 evidence 兩處 slot 0 錯誤描述勘正（slot 0＝黑 W7 欄標、個案中標在資訊區、Case 編號在頁腳 Pepita、13pt 為資訊區內文中標）；否決「Case 編號黑 W5 13pt『01』雙元素」。size 11.4 與 para_gap_slots 0 不動（status-quo，Owner 定案 B 不重定模型）。
- [實作] tests/test_styles.py：新增 `test_case_info_distinct_from_slot0_hei_label_and_case_no` 守門（個案中標 NotoSans Medium 11.4，不等於黑 W7 欄標 11.5／10.5、不等於虛構 Case 編號 13.0，防依誤導 note 併入）。測試 215 → 216。

### 驗證

- 全套 `pytest spikes tests` 216 passed / 0 failed；typecheck（py_compile 全部）EXIT=0。
- Gate 4 獨立驗證：量測（PyMuPDF get_text span cx／top／font／size）與守門測試（模版載入斷言）不同方法互證；Q4「01」全書 0 命中＋Q1 slot 0 黑 W7 33 頁全覆蓋為決定性反證（非單點推論，避免 Sprint 22 同源同錯）。
- Gate 3 同類掃描：grep 模版確認 note 與 evidence 兩處 slot 0 錯誤描述均已勘正、無遺漏。
- 繁中標點：本 Sprint 改動檔（模版／GAPS／PLAN／devlog／CHANGELOG／test_styles）無破折號字元殘留。

### 已知限制（詳 GAPS.md #13）

- slot 0「Case 編號 13pt 雙元素」否決（不存在，真書 Case 編號在頁腳 Pepita）。後續專項（需 Owner 決定投入，屬定案 C）＝黑 W7 欄標樣式建模＋個案中標移資訊區＋資訊區多欄位【標籤】佈局量測。
- 續留 #13 其他剩項：旁注 9pt 變體＋Case 編號 15.9pt 變體（Sprint 34 Gate 3 掃出，未量測）、雙線菱形框（美術資產不生成）、B〜G 其他扉頁逐頁量測。

## v0.29.0（2026-07-12，Sprint 34）個案中標「12.9pt 變體」量測釐清否決（GAPS #13 剩項）

### 決策（honest-planning R1／R5 先量測再動工）

- `個案中標-NotoSans`（size 11.4pt）模版 note 末記「另有 12.9pt 變體見掃描」為誤導待查標記。量測參考書確認 12.9pt 歸屬（避免如 Sprint 23 署名長橫、Sprint 24 摘要層字型、Sprint 30 出血座標框錯配之掃描誤植）。結論：個案中標＝單一 11.4pt，12.9pt 屬 Sprint 23 已定的「推薦序大標-黑體」（序文標題），非個案中標變體。無新 pt 目標，誠實否決造變體（同 Sprint 31 para_gap 否決精神）；不改 size／幾何（現狀正確，同 Sprint 26 勘正非修碼）。

### 量測（A 級一手證據，本機紅線不入 repo）

- 33 個案扉頁（右頁頂 17.9pt 大標）右半頁頂 NotoSans 級數分布：全數僅 11.4pt（資訊列副標「【格局】…」）＋17.9pt（大標），12.9pt 0 命中。
- 全書跨頁 81 個 12.9pt NotoSans span：全落序文頁左半（PDF 3/6/8/12/14/16/174），文字為序文標題句（「把自己放回生命的正中央」等）。交叉檢查 12.9pt 與 33 個案扉頁交集＝空集（決定性反證）。

### 變更

- [實作] templates/neizai-zhengli.json：個案中標 note 末尾「另有 12.9pt 變體見掃描」勘正為量測釐清結論（33 扉頁 0 命中、81 span 全序文、屬推薦序大標）；size_pt 11.4 不動（現狀正確）。
- [實作] tests/test_styles.py：新增 `test_case_info_size_single_and_distinct_from_preface` 守門（個案中標 11.4 不等於推薦序 12.9、同 source_font 但級數用途分離，防依誤導 note 把 12.9 併回個案中標）。測試 214 → 215。

### 驗證

- 全套 `pytest spikes tests` 215 passed / 0 failed；typecheck（py_compile 全部）EXIT=0。
- Gate 4 獨立驗證：量測（PyMuPDF get_text span）與守門測試（模版載入斷言）不同方法互證；交叉檢查空集為反證，非單點推論。
- Gate 3 同類掃描：grep 模版 note「見掃描／變體／待查」，掃出同類「掃描見變體」待查標記兩條（旁注-手札圖注 9pt、Case編號-手寫拉丁 15.9pt），屬不同樣式不同級數，依 R1/R5 須各自量測，本 Sprint 未量測不動、登記後續。
- 繁中標點：本 Sprint 改動檔（模版／GAPS／PLAN／devlog／CHANGELOG／test_styles）無破折號字元殘留。

### 已知限制（詳 GAPS.md #13）

- 續留 #13 剩項：slot 0 Case 編號黑 W5 13pt 雙元素（v1 只建副標）、雙線菱形框（美術資產不生成）、旁注 9pt 變體＋Case 編號 15.9pt 變體（Gate 3 新掃出，未量測）、B〜G 其他扉頁逐頁量測。

## v0.28.0（2026-07-12，Sprint 33）個案大標 para_gap 樣式拆分（個案扉頁 vs 內頁 h2）

### 決策（GAPS #13 剩項，承 Sprint 31 診斷）

- `個案大標-NotoSans`（para_gap 1）身兼 C 個案扉頁大標與 md h2／內頁大標（42 頁）兩用途；C 扉頁三列（資訊列 slot 0／大標 slot 1／內文 slot 2）相鄰為 Sprint 25 A 級量測，但 para_gap 1 使扉頁大標後內文落 slot 3。Sprint 31 已診斷此為整數槽差（非 sub-slot pt），正解拆樣式：新增 `個案扉頁大標-NotoSans`（para_gap 0）給 C 扉頁，原名 `個案大標-NotoSans`（para_gap 1）保留給 md h2／內頁大標（不改 md_mapping、churn 最小）。InDesign 慣例：同視覺角色不同段後距屬不同段落樣式。內頁 h2 para_gap 1 為 status-quo 保留（非新量測宣稱）。

### 新增

- [實作] templates/neizai-zhengli.json：段落樣式 `個案扉頁大標-NotoSans`（思源黑體 Medium 17.9pt、para_gap 0）；C 主版 evidence 移除已修的 para_gap「已知差異」子句、改記 Sprint 33 修正。段落樣式數 16 → 17。
- [實作] samples/case-divider.doc.json：扉頁大標改用新樣式，加自擬內文段（紅線安全）忠實呈現扉頁三列。

### 變更（測試）

- test_layout_render.py：擴充 `test_case_master_and_title_placement` 覆蓋 body slot 2＋守門（扉頁大標 para_gap 0、內頁 個案大標 para_gap 1、h2 對映不動）。
- test_pdf_writer.py：C 扉頁 ink-centering 測試大標樣式對齊為 個案扉頁大標。
- test_styles.py：段落樣式數守門 16 → 17。

### 驗證

- 全套 `pytest spikes tests` 214 passed / 0 failed；typecheck（py_compile 全部）EXIT=0。
- 確定性 layout（committed 樣張 case-divider）：三段 slot ＝ [0,1,2]、0 禁則違規（修正前內文 slot 3）。
- 真實素材驗收（R5）：目標 slot 2 ＝ Sprint 25 真書 A 級量測；紅線內容不入 repo，驗證用自擬扉頁 doc＋確定性 layout（同 Sprint 13〜16 慣例）。render PNG（150dpi、--first-page 2 偶＝右頁）Read 親驗：三直排列右至左相鄰、內文緊貼大標左側（slot 2 非 slot 3 空欄）、承 A 共頂邊、0 禁則違規。
- 同類掃描（Gate 3）：tests/ 樣式數量斷言僅 test_styles 一處；個案大標 殘留引用皆為刻意 h2／內頁守門。tests/、devlog/、GAPS.md 無 em-dash。

### 已知限制（詳 GAPS.md #13）

- 內頁 h2 para_gap 1 為 status-quo，未逐頁量測（誠實記錄）；個案中標 11.4/12.9pt 兩變體、slot 0 Case 編號 13pt 元素、雙線菱形框（美術資產不生成）仍為 #13 剩項。

## v0.27.0（2026-07-12，Sprint 32）替代軌 B：近 800 行測試檔依頁型分檔

### 變更（測試重組，行為零變更）

- test_layout_render.py（795→495 行）與 test_pdf_writer.py（791→469 行）近 800 行上限，各抽「主版向量裝飾與目錄頁型」連續塊（CIP 細框 Sprint 14、目錄天頭虛線 Sprint 15、條目頁碼引導線 Sprint 16、篇名嵌線斷開 Sprint 21，pdf 另含 G 圖文佔位框 Sprint 27）為新檔。
- 循 tests/ 既有「各檔自帶 `template` fixture＋make_ helper」慣例（8 檔皆如此），新檔自帶 fixture／helper，不建共享 conftest（避免改動全檔共享模型＝逾分檔範圍）；測試本體以 sed 逐位元組搬移（零轉錄風險），header 手寫。
- 核心 test_layout_render.py 補 `PT` 常數（章名條目 layout 測試留核心，其 PT 定義隨塊移出）；test_pdf_writer.py 移除抽出後未用的 `from cjkfolio.primitives import cip_frame_rect, toc_rule_line`。

### 新增

- [實作] tests/test_render_vectors.py：13 test（CIP 框＋目錄虛線／頁碼引導線／嵌線 的 layout＋render，自 test_layout_render.py）。
- [實作] tests/test_pdf_vectors.py：14 test（同上＋G 圖文佔位 export，自 test_pdf_writer.py）。

### 驗證

- 全套 `pytest spikes tests` 214 passed / 0 failed（總數不變：39＝26＋13、35＝21＋14，零 test 遺失或重複，分檔行為保持）；typecheck（py_compile 全部）EXIT=0。
- import 潔淨：4 檔各 import 皆有 body 使用（grep 計數 ≥2）；兩核心檔無孤兒 import（pdf 核心 cip_frame_rect／toc_rule_line 抽出後 import 行已移除）。tests/ grep 無 em-dash。分檔後最大測試檔 495 行。

## v0.26.0（2026-07-12，Sprint 31）主軌否決（block 軸整數對齊無 pt 目標）＋轉替代軌 A：measure 工具共用模組

### 決策（主軌否決，honest-planning R1／R8）

- para_gap block 軸 pt 精度主軌以 A 級量測否決：block 軸（段落堆疊＝水平欄位，`slot → line_axis`）本就整數槽對齊、無 sub-slot pt 目標，別於 Sprint 29/30 inline 軸（首字縱向 6.02/6.24pt 真實偏移）。三線證據：(1) C 主版 evidence 明載「大標 para_gap 1 使 body 落 slot 3 vs 真書 slot 2」為整數槽差非 pt；(2) 中標 cx 354.24 ＝ slot 0、大標 331.28 ＝ slot 1（Δ0.03）皆恰整數槽；(3) 本機 probe 量 33 頁內文欄 gap/pitch 4.2〜6.0 隨內容變動、無固定殘差。釐清 Sprint 30 交接「需 block 軸 pt 偏移」為前提誤讀；硬加無真實偏移的 para_gap_offset_pt 違反 R5，不建機制。依 Owner 預授權轉替代軌 A（順手移除噪音）。

### 新增

- [實作] tools/_measure_common.py：measure 工具共用層，抽 4 工具重複的 `HALF_W`（419.53 字面值免捨入漂移）、`PT_PER_MM`、`spans`（回傳 list 供同頁多次篩選）、`is_spread`（半頁判定）、`reference_pdf`、`write_measurements`（JSON 樣板＋mkdir）、`stdout_utf8`；加 `BLEED_PT`／`strip_bleed`（Gate-4 model media→trim 換算正典 helper，收斂 Sprint 24/25/30 出血口徑）。常數量測層自持（同 primitives.py 對 PT_PER_MM 的先例），不 import 產品層。

### 變更（工具重構，行為零變更）

- measure_cip／toc／case／figure_page.py 改 import 共用層；順手清 measure_toc／cip 未使用的 `PT_PER_MM` 死碼。4 檔淨減 15 行重複。

### 驗證（Gate 4 獨立）

- 行為保持：重構前跑現行 4 工具快照 JSON → 重構後刪輸出重跑 → 逐工具 diff 對照，cip／toc／case／figure 全 **IDENTICAL**（0 差異）、4 工具 run 皆 exit 0（先刪輸出避免失敗留舊檔造成假 identical）。
- 全套 `pytest spikes tests` 214 passed / 0 failed（產品碼未動）；typecheck（py_compile 全部）EXIT=0；tools/ 無 em-dash、無遺留 `reconfigure`／`ROOT`／`_spans`／`json.dumps`。

### 已知限制（詳 GAPS.md #13）

- block 軸整數對齊為本書網格特性（sub-slot 藝術偏移只現於 inline 軸），故 para_gap 無 pt 精度需求；C 個案扉頁「大標 para_gap 1 使 body 落 slot 3 vs 真書 slot 2」為整數差，正解 para_gap 1→0，但 個案大標 同時用於內頁 h2（42 頁）須拆樣式，續留 GAPS #13。
- `BLEED_PT`／`strip_bleed` 為量測工具箱之 Gate-4 換算正典（model↔trim 比對），本 sprint 量無出血真書故未觸發（工具箱基建非死碼）；測試側 test_pdf_writer.py／test_lead_offset.py 的 BLEED_PT 仍各自持有，跨 tools/tests 統一非本軌範圍。

## v0.25.0（2026-07-12，Sprint 30）目錄章名條目 inline 偏移＋Gate 4 出血座標框勘正

### 新增

- [實作] layout：`lead_offset_pt` 接入 `_toc_marks`（`title_end` → 引導線起 `leader_y0`）與 `_rule_breaks`（`line_top` 穿線判定），目錄條目 body 偏移時引導線起點與穿線與否同步跟隨 body 實際位置（Sprint 29 刻意延後部分，本 sprint 正題）；頁碼底錨 `page_no_top`／線終 `leader_y1` 為頁面固定列不隨條目。兩後端 render／pdf_writer 消費同一 `TocEntryMark`／`RuleBreak`，改 layout 即自動 parity。
- [實作] tests/test_lead_offset.py：目錄機制（font-free：`leader_y0` 隨 lead_offset 同移、頁碼底錨不動、穿線判定同步）＋兩後端絕對值（PyMuPDF span top 扣出血 → trim 貼真書 135.15）＋兩渲染差分（PNG／PDF on−off ＝ 6.24）。既有 3 toc/rule 測試預期式同步加 `lead_offset_pt`。測試 209 → 214。

### 變更（模版：Gate 4 出血座標框勘正）

- 目錄-篇章條目加 `lead_offset_pt` 6.24：條目首字墨頂（PyMuPDF span top 扣 3mm 出血 → trim 空間）貼真書 135.15（端到端實測精確 135.15）。
- **勘正 Sprint 24 墨頂比對之出血座標框錯配（GAPS #21 同型）**：Sprint 24「墨頂 137.42 vs 真書 135.15、差 +2.27」係拿 model 含出血 media 座標比真書無出血 trim（真書 PDF 本機實測 media ＝ trim ＝ bleed，頂部出血 padding 0.000pt），未扣出血 8.504pt。扣出血後 model trim 墨頂 128.91 vs 真書 135.15，正確 lead_offset ＝ +6.24（下移），方向與原記 -2.27（上移）相反。數學自洽：假差 +2.27 ＝ 真實 trim 差(-6.24) ＋ 出血(8.504)。

### 驗證（Gate 4 獨立）

- scratchpad probe：真書 PDF 頁盒本機實測（media／trim／bleed 三者同尺寸、頂部 padding 0.000pt ＝ 無出血）；model export PDF media span top 137.42（與 Sprint 24 記錄吻合 0.005pt）扣出血得 trim 128.91。
- 端到端 samples/toc.doc.json：render PNG Read 親驗（部名穿線＋4 條目縮退在虛線下＋引導線＋直排頁碼 17／63／109／155 底對齊）、export preflight 12/12、條目墨頂 trim 135.15、兩後端 parity。
- 全套 `pytest spikes tests` 214 passed / 0 failed；typecheck EXIT=0。

### 已知限制（詳 GAPS.md #13）

- +6.24 為 PyMuPDF 同口徑（字型 ascent 線）扣出血對齊，殘留思源／華康 ascent 度量差（§3.3 不比字形輪廓，位置偏移無法消除）；出血 8.504pt 才是可修正的座標框錯配。
- lead_offset_pt 仍未套用橫排 body（無 combined 用例）；para_gap block 軸（Sprint 25 個案中標相鄰）待 block 軸 pt 偏移新機制。

## v0.24.0（2026-07-12，Sprint 29）引擎 pt 精度模型：段級 inline 軸 sub-slot 偏移（lead_offset_pt）

### 新增

- [實作] 段落樣式 `lead_offset_pt`（段級 inline 軸 sub-slot pt 偏移）：載體鏈 ParagraphStyle → ParagraphSpec → PlacedLine → 兩後端 body inline-start（`top_pt + start_slot × advance + lead_offset_pt`，render／pdf_writer 同源一致式）；純位置微調不改斷行容量（不進 `_break_cells`，斷行禁則齊行不動）。整數字槽定位自此可疊加 sub-slot pt 精度（護城河引擎，Owner 指示「最複雜架構先做」）。
- [實作] tests/test_lead_offset.py：布線（font-free：大標 PlacedLine 帶 6.02、部序號帶 0）＋兩後端兩渲染差分（offset 6.02 vs 0，字型 ascent 抵消）證大標首字下移恰 6.02pt、部序號不動。測試 206 → 209（另開新檔，test_layout_render.py 792 行近上限）。

### 變更（模版：Sprint 20 三部扉一手量測，A 級）

- 部扉大標-明體W9 加 `lead_offset_pt` 6.02：大標首字頂 cell_top 176.84 → 182.86pt，貼真書量測 182.86（部序號維持天頭 176.84）。關閉 GAPS #13 的 B 部扉「大標首字頂低 6.02pt（0.26 字槽）v1 整數槽差」子項。
- 重議 Sprint 20 決議「段前 pt 偏移延後 Phase 2〜3」：Owner 要求最複雜架構，正式觸發重議（決議紀錄）。

### 已知限制（詳 GAPS.md #13）

- lead_offset_pt v1 只套用直排 body；橫排 body 與 toc 引導線／rule 穿線判定不套用（現無 combined 用例：唯一使用者部扉大標為直排無 toc／rule）。
- 目錄條目縮退（+2.89pt）、目錄章名（+2.27pt）、para_gap（Sprint 25 個案中標）等其他整數槽差待後續 Sprint 以同 inline 軸機制逐軸套用＋量測驗收。

## v0.23.0（2026-07-12，Sprint 28）preflight trailer-id 假陰性勘正（基線綠回復）

### 修正（baseline 假陰性：接手動工前跑基線發現）

- `pytest spikes tests` 全套順序下 `test_export_toc_rule_preflight_green` 假性失敗（`trailer-id`）。根因：`preflight.check_pdfx1a` 的 trailer-id 規則 regex 只認角括號 hex `<...>`；PyMuPDF `xref_object` 對「解碼後 16 bytes 全可列印」的 /ID 兩組字串重序列化為 literal `(...)`，regex 落空判失敗。全套累積使該 TOC PDF 的 /ID（＝`md5(bodies)`）位元組落入可列印區間才觸發（單獨執行不觸發）；**檔案 /ID 始終為合規的兩組非空字串，PDF 無缺陷，渲染／寫出層不動**。
- 修檢查器 regex：trailer-id 每組字串同認 `<hex>` 與 `(literal)` 兩式（空 `<>`／`()` 仍判失敗，方向安全，不假性放行真正缺 /ID 者）。

### 新增

- [實作] tests/test_preflight.py::test_preflight_accepts_literal_string_id：可列印 /ID 的手工 PDF 回歸測試（TDD：修前 RED、修後 GREEN，確定性重現不依賴全套累積）。測試 205 → 206。

### 驗證（Gate 4 獨立）

- scratchpad probe：手工組不同 /ID PDF＋fitz 讀回實測 PyMuPDF 序列化行為（可列印→`(literal)`＋regex 落空、非可列印→`<hex>`＋命中），與被修檢查器不同路徑確證機制。
- 完整基線 `pytest spikes tests` 206 passed / 0 failed，順序相依失敗消除；typecheck EXIT=0。

## v0.22.0（2026-07-12，Sprint 27）G-圖文版主版：頁型骨架（§4.2 主版 7 種完備）

### 新增

- [實作] tools/measure_figure_page.py：分類量測圖文版頁（Type 1 全頁圖文版 vs Type 2 內文內嵌小圖），只聚合 32 全頁圖文版頁的圖框保留區與辰宇圖說幾何（一手量測，輸出 assets/reference 本機不入 repo）。
- [實作] cjkfolio.styles.FigureSpec＋MasterPage.figure：圖框保留區主版欄位（photo-slot，縱向 top/bottom＋佔位框 dash/cmyk；載入驗證未知 kind／bottom≤top／壞 cmyk 快速失敗）。
- [實作] cjkfolio.primitives.figure_slot_rect／figure_slot_edges：承版心鏡像的圖框保留區幾何＋四邊虛線（reuse 既有 dashed-line 路徑，兩後端同源）。
- [實作] render._draw_figure／pdf_writer._figure：G 圖文版圖框保留區淡虛線佔位框（gate vertical＋master.figure＋page.placed），render PIL 灰值分段／pdf `d` dash＋K 描邊，兩後端幾何同源。
- [實作] 段落樣式「圖說-辰宇落雁」（辰宇落雁體 15.9pt）＋samples/figure-page.doc.json（自擬圖說標籤，紅線不取真書文字與照片）。
- [實作] tests：figure_slot_rect 鏡像 L/R＋四邊虛線（test_primitives，+4）、FigureSpec 載入/驗證＋圖說樣式（test_styles，+7）、佔位框 dash 描邊/兩後端 parity/preflight（test_pdf_writer，+3）。測試 191 → 205。

### 變更（模版：G 圖文版 32 頁一手量測，A 級）

- G-圖文版主版：evidence 由「版心承 A；佈局未量測」推定升級為一手驗證：圖框橫向承 A 版心鏡像（R 頁 x0=72.51／x1=360.0、L 頁 59.53／347.02）、雙照片區 top 107.04／bottom 467.62pt、辰宇圖說 15.92pt（31 span 同值）；加 figure（photo-slot 保留區）。
- §4.2 主版 7 種（A／B／C／D／E／F／G）於 Phase 1 骨架層完備。

### 已知限制（詳 GAPS.md #13）

- 與 B-部扉同型（美術本體延後）：真書照片嵌入為 Phase 2 圖片置入（§9 灰階單 K／300-350ppi）、房名黑體標題＋辰宇自由圖說位置＋裝飾括號為手繪美術（§8 不生成）、前後照片配對與圖文繞排為 Phase 4；真書照片略溢版心 1〜4pt、實際照片逐頁變異（單/雙、高度 385〜500pt）＝美術自由佈局。
- 佔位框為 Phase 1 版面骨架導引（InDesign 空框慣例，真書照片無邊框），Phase 2 圖片置入取代、不留框線；preflight 誠實聲明「v1 尚無影像置入」。
- tests/test_pdf_writer.py 791 行、test_layout_render.py 792 行皆近 800 上限，後續 PDF／layout 測試需先評估分檔。

### 待 Owner 真實素材驗收

- G-圖文版樣張為自擬（改造前／改造後）；真書圖文版照片置入品質、前後配對版式待 Phase 2；斷行逐行一致率比對（Owner 抽檢）延續。

## v0.21.0（2026-07-12，Sprint 26）GAPS #21 勘正：直排字墨偏移為量測框錯配（非置中 bug）

### 勘正（GAPS #21：Sprint 25 Gate 4 誤判）

- Sprint 25 Gate 4 抽驗報「直排字墨 cx 偏 line_axis +8.5pt」、判為全直排正確性問題。**本 Sprint 實證勘正為量測座標框錯配，渲染層本就正確**：+8.5pt＝3mm 出血（BLEED_PT 8.5039pt），係拿 PyMuPDF MediaBox 座標（含出血）比 trim 空間 line_axis 所致；偏移與字級無關（大標 17.9pt 與資訊列 11.4pt 同偏 +8.50）＝純出血常數，非隨字級變的置中誤差。
- 實證（probe＋回歸測試）：export 後大標 MediaBox cx 339.75、資訊列 362.75，各扣出血後 trim cx＝331.25／354.25＝line_axis（Δ+0.00pt），與真書 ink 中心同構（331.28 差 0.03）。既有 test_export_glyph_geometry_on_grid 早已用 BLEED_PT 扣出血比對、test_render_single_char_lands_in_first_cell 早已驗 PNG trim 置中；Gate 4 手驗漏扣此常數。

### 新增

- [實作] tests/test_pdf_writer.py::test_case_ttb_ink_centered_on_line_axis：釘住 PDF 側直排置中（C 大標 17.9pt＋資訊列 11.4pt，扣 BLEED_PT 後字墨 cx＝line_axis）＋反例保護（未扣出血恆偏 +BLEED_PT，佐證框差非置中錯誤）。測試 190 → 191。

### 變更

- tests/test_layout_render.py：test_case_master_and_title_placement 誤導註解（原「PDF/PNG 實際字墨 cx 偏此 +8.5pt」）勘正為出血框差說明並指向新測試；PDF 置中測試置於 test_pdf_writer.py（依 fitz／export_pdf 分層，test_layout_render.py 回 800 行以下）。

### 未動（誠實記錄）

- 不修渲染碼：placement／render／pdf_writer 直排置中本就正確；任何「補償 −8.5pt」都是反向雙重補償、會破壞現有與真書吻合的置中。

## v0.20.0（2026-07-11，Sprint 25）C 個案扉頁大標置位＋直排墨偏移發現（GAPS #21）

### 新增

- [實作] tools/measure_case_page.py：掃描定位個案扉頁（右半頁），逐列量大標行軸／字距／版心／Case 編號（數十頁互證）。
- [實作] samples/case-divider.doc.json：自擬個案扉頁樣張（副標＋大標，紅線不取真書文字）。
- [實作] tests：C 承 A（內文天頭 92.09pt、首行縮排 2 字）＋大標 slot 1 右頁 line_axis 331.25。測試 189 → 190。

### 變更（模版：C 個案扉頁數十頁一手互證，A 級）

- C-個案扉頁主版：evidence 由「未量測（承 A 推定）」升級為一手量測：個案大標 NotoSans Medium 17.9pt 置 slot 1（右頁 line_axis 331.25 貼真書墨欄中心 331.28，差 0.03）、資訊列（Case 編號 DFHeiStd-W5 13pt＋副標 11.4pt）slot 0、內文承 A 自 slot 2（首字 top 145.75）。
- 「個案中標」para_gap_slots 1 → 0 勘誤：實測資訊列 slot 0 與大標 slot 1 相鄰（同 Sprint 20 部扉標籤先例）。

### 發現（正確性問題，GAPS #21，Gate 4 閉環抽驗）

- PyMuPDF get_texttrace 抽 case.pdf：大標 layout slot 1 行軸正確（331.25＝真書 331.28），但 **PDF 字墨 cx 339.75，偏 line_axis 欄中心 +8.5pt**；資訊列 11.4pt 與大標 17.9pt 墨 cx 皆偏 +8.50（與字級無關），真書華康大標墨 cx＝欄中心。
- 判定為**全直排既有正確性問題**（placement ttb 逐字水平 origin＝line_axis 欄中心，未補償字形水平度量）：非 Sprint 25 引入、非單一頁型；兩後端同源（PNG/PDF 一致）故 parity 未攔截，過往只驗 layout axis 或 Read PNG（8.5pt≈3mm 不明顯）故未暴露。
- 本 Sprint **不硬修**（context 保護、避免 Sprint 22 式同源同錯降級）：列 GAPS #21，Sprint 26 專項調查（左右頁對稱性＋根因＋全直排座標回歸）。

### 已知限制（詳 GAPS.md #13、#21）

- C v1 不建模：資訊列雙元素（Case 編號 13pt 獨立列）、內文精確段間 gap、個案雙線框；GAPS #21 直排墨偏移待 Sprint 26 修。

### 待 Owner 真實素材驗收

- out/case25/（本機，重生成）：page-001.png（--first-page 2 右頁）資訊列 slot 0＋大標 slot 1（黑體級數區隔）＋頁碼書口右已 Read 親驗；case.pdf preflight 12/12、字型 SourceHanSansTC-Medium 無 fallback；**待 Owner 與真書並排目視比對，並注意直排墨偏移 GAPS #21（≈3mm 偏書口）**。

## v0.19.0（2026-07-11，Sprint 24）目錄章名條目黑 W5（一手量測勘誤）

### 新增

- [實作] tools/measure_toc_page.py：加 entry_columns 直排列分析（按字中心 x 聚列，標主 CJK 字型／級數／頁碼），供目錄多層條目字型辨識。
- [實作] tests：目錄章名條目勘誤斷言（font 思源黑體 TC／weight medium／11.5pt／head_offset 2／source DFHeiStd-W5、章名首字框頂 132.12）。測試 188 → 189。

### 變更（模版：p002/p003 一手量測，A 級）

- 「目錄-篇章條目」樣式勘誤：全字庫正楷體 TW-Kai 9.5pt → **思源黑體 TC Medium 11.5pt**（source DFHeiStd-W5），head_offset 3 → 2 槽：真書帶頁碼章名實為黑 W5 11.5pt（entry_columns 量測：章名全帶頁碼 top_y 135.15；楷 W3 9.5 為不帶頁碼摘要層字型，掃描誤設為章名層，同 Sprint 23 勘誤）。
- 勘誤同時解 GAPS #12 fallback：章名改用已入庫思源黑體 Medium，render 不再 fallback TW-Kai（題詞-楷書仍用 TW-Kai，fallback 測試對象不變）。

### 已知限制（詳 GAPS.md #13）

- v1 不建模：條目摘要層（楷 W3 9.5 不帶頁碼、真書 top_y 166）、【結語】黑 W5 10pt 變體、章名與摘要縱向錯落及多層列距；章名首字墨頂 137.42 vs 真書 135.15（差 +2.27pt＝整數槽＋思源華康字框度量差）。

### 待 Owner 真實素材驗收

- out/toc24/（本機，重生成）：page-001.png（--first-page 3）4 條章名黑 W5＋引導線＋直立頁碼 17／63／109／155 底對齊已 Read 親驗（黑體章名與明體部名字族區隔）；toc.pdf preflight 12/12、PyMuPDF 抽驗 4 列 SourceHanSansTC-Medium 列距 23pt；待 Owner 與真書 p002/p003 並排目視比對。

## v0.18.0（2026-07-11，Sprint 23）E 序文版頁型（三頁互證量測）

### 新增

- [實作] samples/preface.doc.json：自擬序文樣張（標題＋內文兩段，master E）。
- [實作] tests：E 主版與標題樣式量測常數＋樣張幾何（標題 slot 0、內文 slot 5、縮排 2 字）。測試 186 → 188。

### 變更（模版：p004/p007/p009 三頁一手互證，A 級同值）

- E-序文版：版心承 A **由推定升級為一手驗證**（天頭 92.09pt=32.49mm、行距 23、字距 12.08、首行縮排 2 字吻合）；**頁腳承 A**（頁碼 x 36.85pt 與 A outer_offset 36.8 精確吻合、序文偶頁書眉實測同 A）。
- 樣式勘誤：「推薦序大標-楷書W5」（16.3pt）→「**推薦序大標-黑體**」（思源黑體 Medium **12.9pt**、para_gap_slots 4）：原記為掃描誤抓署名行長橫「─」；序文標題真身 NotoSans Medium 12.9pt（個案大標 17.9pt 為不同級）。
- 模版 JSON 經 json.dump 統一重排（indent=1），內容等價、僅格式統一。

### 已知限制（詳 GAPS.md #13）

- 欄標「推薦序」（黑 W5 9pt）＝標題行右側 16.2pt 肩位（v1 無肩注機制）；署名行（楷 W5 16.3 長橫＋明 W9 11.1 混級）y 頂底皆隨頁變動＝自由手排；標題行軸實測 342.16 vs 承 A 推導 341.26（差 0.9pt≈inner 0.32mm）。

### 待 Owner 真實素材驗收

- out/preface23/（本機，重生成）：page-001.png（--first-page 7）標題右起＋內文隔 4 槽＋頁碼書口左下已 Read 親驗；preface.pdf preflight 12/12、標題行軸抽驗 341.27pt 與 v1 推導重合；待 Owner 與真書 p004 並排目視比對。

## v0.17.0（2026-07-11，Sprint 22）鏡像側別與真書對齊（正確性修正）

### 修正（GAPS #20：Sprint 12 側別基準與真書相反）

- [實作] 真書三向互證（A 級）：頁碼側（四 spread：偶頁頁碼書口右、奇頁書口左）＋書眉側（書名書眉皆偶頁）＋版心側（偶頁右邊距 21.00mm＝outer 精確）→ **偶數頁＝右頁、奇數頁＝左頁**；Sprint 12「奇右偶左」為西式左翻書慣例誤植。
- [實作] render：新增 `is_right_page` 單一事實來源（偶＝右頁），`line_axis_x_pt`／`horizontal_left_x_pt`／兩後端 `_footer` 共 5 判定點收斂；footer 奇偶 gate（pages 配置語意）與書口側別拆分；mirror=false 恆以 outer 槽為起排側（直排 B＝右、橫排 F＝左）。
- [實作] 奇偶測試矩陣第二次翻轉（line-axis／footer／page-selection／body-axis 兩後端＋styles），橫排幾何斷言改 outer 語意。測試 186 → 186（0 退步）。

### 變更（模版）

- A-內文版：書名書眉 `running_title.pages` **odd → even**（真書書名書眉在偶頁＝右頁）；左頁（奇數頁）章節副標書眉仍待章節結構（既有 note）。
- F-版權頁：margins **outer↔inner 對調**（outer 25.81＝p178 左頁書口，名實相符；inner 21.0 承 A 自擬）；mirror=false 幾何不變（CIP 框 PyMuPDF 複驗 x0 差 0.01pt）。

### 勘誤（記錄修正，幾何不受影響）

- Sprint 12 devlog／§10「與真書右翻一致」比對記錄錯誤；Sprint 20「部扉＝偶數頁」實為奇數頁（37/137/229，B mirror=false 幾何不變）；§1 補側別事實。

### 待 Owner 真實素材驗收

- out/ch1-s22/（本機，重生成）：--first-page 20 的 page-001（書頁 20 偶＝右頁：頁碼書口右下＋書名書眉）與 page-002（書頁 21 奇＝左頁：頁碼左下無書眉）已 Read 親驗，與真書 spread（PDF 索引 4/12/30/40）逐項一致；待 Owner 翻閱實體書覆核側別。

## v0.16.0（2026-07-11，Sprint 21）目錄篇名嵌線斷開＋條目縮退（p002/p003 量測）

### 新增

- [實作] engine：`ParagraphSpec.head_offset`（段級天頭縮退槽，整段每行起始槽位下移；縮退已含於 `start_slot`，兩後端 y 幾何零改動）。
- [實作] styles：`ParagraphStyle.head_offset_chars`、`RuleSpec.break_before_pt`／`break_after_pt`（篇名嵌線斷開邊距）。
- [實作] primitives：`toc_rule_segments`（虛線依斷開區間切段；gap 裁剪、零長段不產出；`toc_rule_line` 保留為全寬幾何來源）。
- [實作] layout：`RuleBreak`＋`LayoutResult.rule_breaks`（穿線行判定純幾何：行首字頂 y 高於虛線 y 即斷開，非樣式白名單）。
- [實作] render：`rule_break_ranges`（穿線行行槽範圍±斷開邊距 → 斷開 x 區間，兩後端同源）；`_draw_rule`／pdf `_rule` 改多段。
- [實作] tools/measure_toc_page.py：目錄頁虛線分段＋穿線行＋縮退量測工具（Sprint 19 先例，量測 JSON 本機不入 repo）。
- [實作] tests：engine head_offset、primitives 切段 3 項、layout 穿線判定 3 項、render 著墨斷開、pdf 兩後端 parity＋preflight。測試 176 → 186。

### 變更（模版 D-目錄：p002/p003 一手量測，A 級三處互證）

- margins：top 47.63 → **38.09mm**（篇名「第N篇」首字頂 107.96pt，三處同值；原 47.63mm 條目錨 135pt 改由縮退表達）。
- 樣式「目錄-篇章條目」：**head_offset_chars 3**（縮退 29.93pt vs 真書 27.04pt，整數槽差 +2.89pt）。
- rule：加 **break_before_pt 28.5**／**break_after_pt 3.9**（行槽緣→線端量測中值）。

### 已知限制（詳 GAPS.md #13）

- 條目縮退整數槽差 +2.89pt（v1 整數槽模型，同 Sprint 20 先例）；斷開邊距真書手排離散（before 26.9〜30.1／after 3.7〜4.1，取中值）。
- 帶起訖不建模：真書前置條目區（目次大標、推薦序）無線、帶起於首篇名、跨頁延續記號±10mm；v1 全寬貫穿＋出血。
- 篇序（第N篇 11pt W7 密排騎線）＋部名詩句 16pt 同行混排不建模（v1 部名單一樣式；真書詩句字距 17.12 亦非 §10 換算 16.81）。

### 待 Owner 真實素材驗收

- out/toc21/（本機，重生成）：page-001.png 部名穿線＋虛線斷開＋條目縮退已 Read 親驗；toc.pdf preflight 12/12、PyMuPDF 抽驗兩段虛線端點與手推**完全重合**（0.00pt）；待 Owner 與真書 p003 並排目視比對。

## v0.15.0（2026-07-11，Sprint 20）B 部扉頁型大標置位（三部扉量測）

### 新增

- [實作] samples/part-divider.doc.json：自擬部扉樣張（篇序標籤＋部名兩段，master B）。
- [實作] tests：test_part_divider_layout_geometry（行軸 228.49／194.12、天頭 176.84pt、大標字距 23.1 量測常數釘死＋標籤 gap 0）。測試 175 → 176。

### 變更（模版 B-部扉：承 A → 三部扉一手量測，A 級三頁互證）

- margins：top 32.49 → **62.38mm**（部序號首字頂錨定）、outer 21.0 → **63.53mm**（slot 0 行軸反推）；mirror true → **false**。
- grid：32×13（12.08／23.0／11.5）→ **10 字×8 行（23.1／34.37／21.9）**；字距合 §10 換算規則（W7 推導 15.72 vs 實測 15.75）。
- 樣式「標籤-篇序小標」para_gap_slots 1 → **0**（與大標間距已含於行距 34.37pt）。

### 已知限制（詳 GAPS.md #13）

- 真書大標首字頂比部序號低 6.02pt（0.26 字槽）：v1 整數槽模型兩段同天頭起排。
- 雙線菱形裝飾框不規則化（手繪美術資產，Sprint 15 決議）；bold 字重以 heavy 替（GAPS #12 既有警告不沉默）。

### 待 Owner 真實素材驗收

- out/part20/（本機，重生成）：page-001.png 部序號＋大標兩行直排置位已 Read 親驗；part.pdf preflight 12/12、PyMuPDF 抽驗兩行軸中心 x 228.49／194.12 與三部扉量測**精確重合**；待 Owner 與真書部扉（如 p069）並排目視比對。

## v0.14.0（2026-07-11，Sprint 19）F-版權頁真實版心量測（關 GAPS #13 (a)）

### 新增

- [實作] tools/measure_cip_page.py：p178（PDF 頁索引 177）CIP 量測工具（框折線重建 bbox、框內 spans 行距／字距／pad 統計、半邊判定；輸出 assets/reference/cip_measurements.json 本機不入 repo）。
- [實作] styles：FrameSpec.pad_v_pt（選配垂直 pad，None＝同 pad_pt）；primitives cip_frame_rect 支援不對稱 pad。
- 測試 173 → 175（+2：pad_v 解析＋不對稱框幾何；另 3 處寫死斷言同步為量測真值）。

### 變更（模版 F-版權頁：自擬 → p178 一手量測，A 級）

- CIP 級數 8 → **5.63pt**、字距 8.4 → **5.66pt**、行距 14 → **7.74pt**、滿行 34 → **23 字**；top 32.49 → **43.48mm**（首行 baseline 128.2pt 錨定）、inner 25.58 → **25.81mm**。
- 框：線寬 0.5 → **0.14pt**、純黑 → **暖黑 K92**（同內文色）、pad 6.0 → **5.05（水平）×4.94（垂直）**。

### 已知限制（詳 GAPS.md #13）

- 後段 3 行行距分區（12.73／11.73pt）：v1 單一 line_pitch 表達不了，樣張以主體 7.74 等距。
- 框上方 CIP 標題行：v1 不區分框內外行。框寬（網格滿行推導）與真書最長行差 1.3pt。

### 待 Owner 真實素材驗收

- out/cip19/（本機，重生成）：page-001.png 密排 CIP＋細框已 Read 親驗；cip.pdf preflight 12/12、PyMuPDF 獨立抽驗框左上角 (68.11, 118.31)／首行 baseline 128.2／字級 5.63／線寬 0.14 與 p178 量測精確重合（0.01pt 內）；待 Owner 與真書 p178 並排目視比對。

## v0.13.0（2026-07-11，Sprint 18）文件 provenance 載體（Phase 2 首項工程）

### 新增

- [實作] engine：`Cell.span`（文件段 text 半開區間）＋`normalize_with_offsets`（正規化＋原索引表：Cc 剝除位移精確映射、表現形 1:1 不動索引；`normalize` 改由其推導，單一事實來源）；`tokenize` 加 `offsets` 參數（None＝輸入座標 identity，舊 API 相容）；`cells_from_runs` 依 document@2 串接不變式帶 run base 位移。
- [實作] engine／layout：`ParagraphSpec.para_idx`＋`PlacedLine.para_idx`（純載體，layout 建 spec 時掛段索引，與 page_no 同模式，不影響斷行禁則齊行與兩後端）。
- 畫布點選 → 文件游標資料鏈補齊：hit-test 幾何鍵 (page, placed_idx, cell_idx) → `PlacedLine.para_idx`＋`Cell.span` → 文件 (段, 字元區間)（Spike 10 介面缺口關閉）。
- 測試 164 → 173（+9：normalize 映射 2、tokenize span 2、runs base 1、flow para_idx 2、layout 全文件 round-trip 直排＋橫排 2）。

### 待 Owner 真實素材驗收

- 本機驗證（重現：層層皆單元測試釘死；一次性掃描腳本已依紀律刪除）：第一章 22 頁 5,361 cells、samples/toc.doc.json 64 cells、samples/cip-copyright.doc.json 65 cells，round-trip（doc 段 text[span] 正規化後 == cell.text）全 0 錯、placed 行 para_idx 全數帶值。

## v0.12.0（2026-07-11，Sprint 17）Phase 2 畫布架構前置 spike（風險前置）

### 新增

- [Spike] spikes/spike10-canvas-sync/：premortem（R6 七問）＋探針 probe_canvas_sync.py（S1〜S5）＋report.md。PySide6 6.11.0 offscreen 雙層畫布：底圖層（既有 PNG 渲染後端輸出 → QGraphicsPixmapItem）＋互動層（layout 幾何同源透明字格 QGraphicsRectItem，復用 line_axis_x_pt／style_advance_pt／line_justified_advance，不另立幾何）。
- 一手數據（第一章 22 頁本機素材）：編輯回路中位 37.2ms@150dpi（重排 7.0／渲染 25.8／pixmap 1.9／互動層 2.6）、26.9ms@96dpi；全頁字格中心 hit-test 反查 214/214；22 頁 5,361 item 建立 52ms、hit-test 中位 0.90ms；重排 7.0ms 與 Spike 3 的 7.67ms 獨立互證。

### 決策

- Owner 指示「先挑最複雜的架構先做」：風險前置，Phase 2 最高風險架構件（畫布 ↔ 排版核心同步，PLAN §7 中高風險「長尾工程」）以最小 spike 先驗，不直接開蓋編輯器（R2）。
- Phase 2 首項工程定案：PlacedLine／Cell 掛文件 provenance（para_idx／char offset），供畫布點選 → 文件游標映射（Spike 10 顯式暴露的介面缺口）。
- spike 探針不入 pytest 基線（避免基線硬依賴 PySide6 GUI 套件）；測試 164 → 164（0 退步）。

### 已知限制（詳 GAPS.md #19）

- IME 直排輸入／拖曳／選取 UI 未驗（offscreen 限制），Phase 2 開工首個 Sprint 以真視窗 demo 由 Owner 人工實測。
- Phase 2 正式技術棧（含 Skia 與否、C++／Python 分層）於 Phase 2 開工定案；本 spike 供畫布層一手數據，非正式開工。

### 待 Owner 真實素材驗收

- spikes/spike10-canvas-sync/out/page1_overlay.png（本機，重生成：python spikes/spike10-canvas-sync/probe_canvas_sync.py）：4 個高亮字格（章名首格／內文中格／大標格／行末標點格）紅框黃底與底圖字形對位，已 Read 親驗（含 zoom_last.png 放大驗直排「】」vert 形貼格頂正確）；待 Owner 過目。

## v0.11.0（2026-07-11，Sprint 16）目錄條目頁碼＋引導線

### 新增

- [實作] 文件模型：Paragraph.page_no（目錄條目頁碼，選配數字字串，document@2 相容擴充：無欄位照載、save 有值才寫、非數字快速失敗）；engine ParagraphSpec／PlacedLine 純載體傳遞（只掛段末行，不影響斷行禁則）。
- [實作] 樣式：TocSpec（頁碼字元樣式＋底錨＋引導線寬/gap/cmyk）＋MasterPage.toc；模版跨引用驗證（toc.page_no_style 不存在即拒）。
- [實作] layout：TocEntryMark＋LayoutResult.toc_marks（頁碼頂＝底錨−位數×字距、線起＝標題末＋gap、線終＝頁碼頂−gap；標題頁碼重疊列 violations 不畫線；帶 page_no 落在無 toc 主版快速失敗）。
- [實作] 兩後端：render _draw_toc_marks（引導線復用 StrokeLine 實線＋頁碼 tcy 逐位直立）；pdf_writer _toc_marks（stroke_line 無 dash K92＋tcy_placements）；幾何同源、parity 單元測試釘死。
- [實作] D-目錄 toc 配置（底錨 490pt、線寬 0.1pt、gap 2pt 皆 p003 一手量測；頁碼樣式「頁碼數字-GillSans」對映粉圓）；samples/toc.doc.json 條目加自擬頁碼。
- 測試 151 → 164（+13：document 2、styles 3、engine 1、layout 2、render 2、pdf 3）。

### 紀錄

- 粉圓首次進 PDF 子集：fontTools 丟棄 Apple meta table（stderr 提示「meta NOT subset; dropped」，非渲染必要表，嵌入合法性不受影響）。

### 已知限制（詳 GAPS.md #13）

- 目錄頁型剩：篇名嵌線斷開、條目縮退、目錄「章名條目黑 W5」樣式層補充。
- 頁碼字級用頁碼字元樣式 8pt（p003 實測 Times 9pt，同構不同值）。

### 待 Owner 真實素材驗收

- out/toc/（本機，重生成）：page-001.png 四條目引導線＋頁碼 17／63／109／155 底一列對齊，已 Read 親驗與 p003 設計語言（標題→線→頁碼底對齊）一致；toc.pdf preflight 12/12、PyMuPDF 獨立解析 4 引導線 y 起訖與幾何手推一致，待 Owner 過目條目視覺與參考書風格相符度。

## v0.10.0（2026-07-11，Sprint 15）目錄水平虛線向量原件

### 新增

- [實作] 虛線原件：primitives 加 StrokeLine（端點＋cmyk＋線寬＋dash on/off，on=0 實線）與 toc_rule_line（貫穿頁寬＋兩側出血延伸 3mm，§9 貼邊全出）；styles 加 RuleSpec／KNOWN_RULE_KINDS／MasterPage.rule（未知 kind／壞 cmyk／缺 y 快速失敗）。
- [實作] render：_draw_stroke_line（PIL 分段 dash，灰值 255×(1−k) 只取 k，灰階預覽限制）；pdf_writer：_Content.stroke_line（原生 `[ on off ] 0 d` dash 算符＋灰 `K` 描邊，獨立 q…Q 置 BT 前，spike8 實證狀態不外洩）。兩後端 gate＝vertical and master.rule（toc-rule 為直排目錄原件）、幾何同源集中 toc_rule_line。
- [實作] D-目錄主版 rule（y 122.46pt、1.0pt、dash [3 2]、灰 K57，皆參考書 p003 一手量測參數；量測參數入模版依 Sprint 7 頁腳先例）；samples/toc.doc.json 自擬目錄樣張。
- 測試 139 → 151（+12：primitives 2、styles 5、render 2、pdf 3）。

### 變更

- D-目錄天頭 32.49 → 47.63mm（條目內容起點 135pt 實測；內容一律在虛線之下，修正首輪樣張文字穿線）。

### 決策

- 部扉「雙線菱形框」規則化不做：p069 實測為手繪向量（單 draw 608 段不規則路徑）＝美術資產（PLAN §8 不生成美術），待使用者置入向量資產機制。

### 已知限制（詳 GAPS.md #13）

- 目錄頁型未實作：篇名嵌線斷開、條目縮退、垂直引導線、直排數字頁碼；虛線 v1 全頁寬貫穿。
- 目錄條目樣式（全字庫正楷體）與部名 bold 仍 fallback 並警告（GAPS #12）。

### 待 Owner 真實素材驗收

- out/toc/（本機）：page-001.png（300dpi）虛線橫貫整頁寬、斷續均勻、部名＋4 條目在虛線下，已 Read 親驗；toc.pdf preflight 12/12、內容流 m/l 座標與幾何助手完全一致、PyMuPDF 獨立回報 dashes='[ 3 2 ] 0'，待 Owner 過目虛線視覺與參考書 p003 風格相符度。

## v0.9.0（2026-07-11，Sprint 14）CIP 細框向量原件（補記）

> 本段為 Sprint 15 收尾時補記（Sprint 14 commit fe525ee 漏更新 CHANGELOG，R7 落差不沉默；內容取自 devlog/archive/2026-07-11-sprint14-cip-frame.md）。

### 新增

- [實作] 向量原件層：新模組 cjkfolio/primitives（StrokeRect＋cip_frame_rect，與 placement 同層、兩後端同源）；styles 加 FrameSpec／KNOWN_FRAME_KINDS／MasterPage.frame。
- [實作] render：_draw_stroke_rect（PIL "L" outline=0）；pdf_writer：_Content.prologue＋stroke_rect（DeviceCMYK K 描邊、獨立 q…Q 置於 BT／ET 外）。gate＝not vertical and master.frame（cip-box 為橫排原件）。
- [實作] F-版權頁主版 cip-box 框（純黑 0.5pt、pad 6pt，全自擬，紅線 p178 不入 repo）。
- 測試 127 → 139（+12）。

### 已知限制（詳 GAPS.md #13）

- F 真實版心（p178）未量測；B〜G 其他扉頁佈局未動。

## v0.8.0（2026-07-11，Sprint 13）橫排版面軸（補記）

> 本段為 Sprint 15 收尾時補記（Sprint 13 commit 27e6829 漏更新 CHANGELOG，R7 落差不沉默；內容取自 devlog/archive/2026-07-11-sprint13-horizontal.md）。

### 新增

- [實作] 橫排 horizontal-tb 版面軸貫通四層：engine（方向感知 tokenize，橫排整串 ascii 成 latin run、不縱中橫、不切碎 ISBN）／layout（page_is_vertical 由樣式判頁面單一方向，混用與未知模式快速失敗；橫排短行不齊行）／render（horizontal_left_x_pt／horizontal_baseline_y_pt／_draw_horizontal_cell）／pdf_writer（水平 Tm）。兩後端幾何同源集中 placement horizontal_cell_advance_pt。
- [實作] F-版權頁 grid 改自擬橫排幾何（8pt CIP、字距 8.4pt、行距 14pt）；samples/cip-copyright.doc.json 自擬 CIP 樣張。
- 測試 115 → 127（+12）。

### 已知限制（詳 GAPS.md #13）

- F-版權頁真實版心（p178）為自擬；橫排「機制」與「參考書逐點版心」分離。

## v0.7.0（2026-07-11，Sprint 12）鏡像依書頁號＋PNG 缺字警告

### 新增

- [實作] PNG 缺字警告（GAPS #17）：render 四路徑（cjk／縱中橫／旋轉拉丁／頁腳）偵測 gid 0，回報缺字來源字元，PageRenderer.notdef_warnings 訊息格式與 pdf_writer 一致，經 RenderResult.font_warnings 由 CLI render 列印（不沉默）。
- 測試 112 → 115（+3：書頁鏡像 PNG／PDF 兩後端＋PNG 缺字警告）。

### 變更

- [實作] 鏡像依書頁號（GAPS #16）：頁面鏡像（行軸書口側）與頁腳奇偶改依書頁號（＝版面頁號＋first_page−1），render 與 pdf_writer 兩後端同源；first_page=1 預設向後相容，版面頁號續作檔名與 --page 選頁鍵。既有 footer 與 page-selection 奇偶頁測試同步翻轉。
- CLI --first-page 說明更新為「頁腳與鏡像奇偶依此」。

### 已知限制（詳 GAPS.md）

- 缺字偵測未統一 placement 層（render 自有塑形迴圈，外科手術範圍）；渲染後端統一時再併。
- 橫排（#13，版權頁-CIP）、斷行逐行一致率比對（Owner 抽檢）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機，--first-page 20 重生成 22 頁）：page-001.png（書頁 20 偶＝左頁）頁碼書口左、無書眉；page-002.png（書頁 21 奇＝右頁）頁碼書口右＋書眉「內在整理」，已 Read 親驗與真書右翻一致；chapter1.pdf preflight 12/12、pdffonts 六款全綠不退步，待 Owner 過目確認左右頁側別與真書鏡像相符。

## v0.6.0（2026-07-11，Sprint 11）齊行與禁則擠入

### 新增

- [實作] 齊行（justification）：非段末行行首行尾雙錨定，內容字距均勻縮放（±1 槽 ≈ ±0.4pt，與參考書 §1 實測同形態）；縮排偏移維持網格字距；偏差超容忍（2 槽）維持等距網格並入統計（不沉默）。
- [實作] 行首禁則改「擠入優先」：整串連續句逗一次決策掛入本行行尾（溢出 ≤2 槽）；超過上限改追出錨字連同句逗下移。行尾禁則維持退行。
- [實作] Line 帶 cap／para_end；LayoutResult／RenderResult／PdfResult 帶 justify_stats；CLI render 與 export-pdf 回報齊行統計。
- 測試 107 → 112（+5）。

### 變更

- 斷行點整體前移：句逗不再被追出至次行，第一章實排 23 頁 → 22 頁（樣張已重生成）。

### 已知限制（詳 GAPS.md）

- 半形「約物寬度壓縮」（JLREQ 式）不實作：參考書實測句逗置中、無半形擠壓，齊行以字距縮放達成（§10 決議）。
- 斷行逐行一致率 vs 參考書待 Owner 抽檢；鏡像依書頁號（#16）、PNG 缺字警告（#17）、橫排（#13）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機，重生成 22 頁）：page-001.png 第 2 行行尾逗號擠入、滿行行底貼齊（已 AI 目檢）；chapter1.pdf preflight 12/12 與 pdffonts 全綠不退步，待 Owner 過目並與參考書斷行抽樣比對。

## v0.5.0（2026-07-11，Sprint 10）PDF/X-1a:2001 識別＋機械 preflight

### 新增

- [實作] X-1a:2001 識別（ISO 15930-1，PLAN §9 預設）：header 改 %PDF-1.3、Info 補 GTS_PDFXVersion (PDF/X-1:2001)＋GTS_PDFXConformance (PDF/X-1a:2001)＋Trapped /False＋ModDate（帶時區）；Title 必填快速失敗。
- [實作] OutputIntent：/S /GTS_PDFX，預設 JC200103（Japan Color 2001 Coated 的 ICC registry 特性化條件名，依 ISO 15930-1 免嵌描述檔、零 ICC 授權負擔）；自訂識別強制以 --icc 嵌 CMYK 輸出（prtr）DestOutputProfile（/N 4），錯型別快速失敗。
- [實作] XMP metadata stream（不壓縮）：dc:title／日期／pdf:Trapped 與 Info 同值，pdfx:＋pdfxid: 雙命名空間 X 識別。
- [實作] 機械 preflight（cjkfolio/preflight＋CLI preflight）：12 條 X-1a 規則（header／ID／加密／Info 識別／OutputIntent／盒框／字型嵌入／CMYK-only／LZW／透明／互動項／XMP），PyMuPDF 獨立解析，未涵蓋項誠實列印，exit code 0/1。
- CLI export-pdf 新參數：--output-condition-identifier／--output-condition／--icc。
- 測試 96 → 107（+11）。

### 已知限制（詳 GAPS.md）

- veraPDF 僅驗 PDF/A／UA、不支援 PDF/X（官方文件實查），本機 preflight＝自寫機械檢查＋pdffonts；Acrobat／印廠認證級 preflight 未跑（#18 新開，#15 關閉）。
- KNOWN_PRINT_CONDITIONS 為 registry 常用子集，未列名的 registry 條目需擴充名單或附 ICC。
- 鏡像依書頁號（#16）、PNG 缺字警告（#17）、齊行（#9）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/chapter1.pdf＋chapter1-p1.pdf（本機，重生成）：自寫 preflight 12/12 全綠、pdffonts 六款全綠；pdf-render-x1a-001/006.png 已 AI 目檢與 Sprint 9 版面一致，待 Owner 以閱讀器實開，另若有 Acrobat Pro 可跑官方 preflight 對照（GAPS #18）。

## v0.4.0（2026-07-11，Sprint 9）字元樣式 run 模型＋md 行內強調

### 新增

- [實作] document@2：段內 run（text＋char_style），Paragraph 正規化不變式（text＝runs 串接）；@1 相容照載、@1 帶 runs 明確拒絕；save 一律寫 @2。
- [實作] 引擎與雙後端 run 支援：Cell 帶字元樣式、PNG／PDF per-cell 覆寫字型與級數（字槽網格仍依段落樣式）、layout 與 CLI 對未知字元樣式快速失敗。
- [實作] md 行內強調：**strong**／*em* 對映模版 md_inline_mapping（v1 皆映內文強調-明體W9）；相鄰同樣式合併、未閉合保留字面。
- [實作] 抽取工具：body 欄明體 W9 強調 span 標 **…**；控制字元（Cc）源頭剔除並列計數。
- 測試 83 → 96（+13）。

### 已知限制（詳 GAPS.md）

- md 行內標記 v1 不支援嵌套；em 與 strong 同映強調樣式（原書無斜體慣例）。
- 發言人標籤自動指派（訪談章黑體標籤）屬 Phase 3 AI 指派範圍。
- X-1a 收尾（#15）、鏡像依書頁號（#16）、PNG 缺字警告（#17）未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機，重生成）：強調頁（書頁 25）page-006.png 與 pdf-render-strong.png，真書整句強調＋對談發言標籤以宋 Heavy 呈現，已 AI 目檢雙後端一致，待 Owner 過目。

## v0.3.0（2026-07-11，Sprint 8）PDF 寫出層第一片

### 新增

- [實作] PDF 寫出層（cjkfolio/pdf_writer）：自寫 PDF 1.4，盒框依 PLAN §9（MediaBox 154×216mm／TrimBox 148×210 置中／BleedBox＝MediaBox）、文字 DeviceCMYK 單 K92、右翻閱讀方向（/Direction /R2L）、逐字顯式 Tm（禁則與斷行在排版層烘焙）。
- [實作] 字型子集嵌入：CFF（思源）不保留 GID、原 CID 走 charset 對映（探針實證小 30 倍）；TTF（辰宇／粉圓）retain_gids＋CIDToGIDMap /Identity；皆帶 ToUnicode（可抽取）與 CIDSet（X-1a 要求）；子集前綴可重現。
- [實作] 共用字形佈局層（cjkfolio/placement）：與 PNG 渲染同一套 pen 數學（直排字槽／縱中橫／旋轉拉丁／頁腳字條）。
- [實作] CLI export-pdf：--page（單頁完稿）／--first-page／--no-footer，回報禁則與每款子集大小。
- 測試 74 → 83（+9）。

### 變更

- engine.normalize 剝除控制字元（Cc）：真章 md 素材在發言標籤後殘留 U+0007 的實測缺陷修正。
- 缺字（gid 0）於 PDF 匯出改為警告＋.notdef 輸出，不沉默、不中斷。

### 已知限制（詳 GAPS.md）

- 尚非完整 PDF/X-1a：缺 OutputIntent／XMP 識別／preflight 全綠驗證（#15），不得對外宣稱 X-1a。
- 鏡像與頁腳奇偶以版面頁號判定，偶數起頁（--first-page 20）側別與真書相反（#16，PNG/PDF 一致）。
- PNG 渲染缺字仍沉默（#17）；齊行（#9）、橫排（#13）、行內強調 run 模型未動。

### 待 Owner 真實素材驗收

- out/chapter1-md/chapter1.pdf（本機，23 頁）＋ chapter1-p1.pdf（單頁完稿）：pdffonts 六款全綠、PyMuPDF 渲染 pdf-render-001/002.png 已 AI 目檢，待 Owner 以 PDF 閱讀器實開過目（右翻方向、選字複製、縮放銳利度）。

## v0.2.0（2026-07-11，Sprint 7）md 匯入＋主版頁腳＋字型組

### 新增

- [實作] Markdown 匯入（import-md）：block 級標題／引文／清單直接對映模版樣式（md_mapping），§4.4 設計修正 1 落地。
- [實作] 主版頁腳與書眉：頁碼（全頁）＋書名書眉（奇數頁），foot_elements 實測座標、奇偶頁鏡像；CLI --first-page／--no-footer。
- [實作] 字型組入庫：思源黑體 TC Medium/Bold、辰宇落雁體、jf open 粉圓（皆驗 GSUB vert；GAPS #12 縮至全字庫兩款）。
- 抽取工具 --format md（級數→標題層級、仿宋→引文）；手寫／裝飾字型不入正文流。
- 測試 61 → 74（+13）。

### 變更

- 渲染改以 FT_LOAD_NO_HINTING 載入字形（修辰宇／粉圓 TTF hinting bytecode 使 FreeType 拋錯；印刷級柵格不需 hinting）。

### 已知限制（詳 GAPS.md）

- 行內強調需字元樣式 run 模型（document@2），未實作；左頁章節副標書眉與 Case 編號待章節結構。
- 楷書／仿宋樣式仍 fallback（#12）；齊行未實作（#9）；橫排未支援（#13）。

### 待 Owner 真實素材驗收

- out/chapter1-md/（本機）：第一章 md 樣式化 23 頁（章名 Heavy／個案大標黑體／小標黑體／內文宋體＋頁腳），page-001／002 已 AI 目檢，待 Owner 過目。

## v0.1.0（2026-07-10，Sprint 6）Phase 1 第一片：核心排版管線

### 新增

- [實作] cjkfolio 套件：文件模型（cjkfolio/document@1）、三層樣式讀取（cjkfolio/template@1）、字型解析（fallback＋警告）、直排引擎（斷行／禁則／縱中橫，自 Spike 1 產品化）、樣式驅動流排、單頁 A5 PNG 渲染（鏡像版心）、txt 匯入、CLI（import-txt／render）。
- [實作] 《內在整理》起始模版 templates/neizai-zhengli.json：15 段落樣式＋9 字元樣式＋7 主版，參數取自全書 (font,size) 掃描（A 級）。
- [實作] tools：全書樣式掃描、章節抽取（輸出僅本機 assets/reference/，版權紅線）。
- 測試新增 46 項（合計 61），typecheck 0 error。

### 變更

- 產品管線字型：PMingLiU → 思源宋體 TC（GAPS #3 關閉）。
- 基線指令擴充至 cjkfolio 與 tools（PLAN §10 決議）。

### 已知限制（詳 GAPS.md）

- 字型組僅思源宋體 TC 兩檔，黑體／楷書／仿宋／手寫樣式 fallback 並警告（#12）。
- B〜G 主版版心承 A 未逐頁實測；橫排（版權頁）渲染未支援，遇之明確報錯（#13）。
- 齊行與約物擠壓未實作，等距網格（#9）；頁腳三件組與書眉未進場。
- txt 抽取 v1 對談段合併為單段（本機驗證素材限制，#14）。

### 待 Owner 真實素材驗收

- out/chapter1/（本機）：第一章 79 段 5,408 字 → 23 頁 A5 PNG，禁則 0 違規；page-001／002 已 AI 目檢（網格、鏡像、標點、縮排），待 Owner 過目。
- GAPS #10（Spike 1 對比圖 spread_comparison.png）仍待 Owner 抽檢，與本項可一併看。
