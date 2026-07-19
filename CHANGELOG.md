# CHANGELOG

> Phase 0（Spike 1〜5）歷程見 devlog/；自 Phase 1 產品碼進場（Sprint 6）起立此檔。

## v0.102.0（2026-07-19，Sprint 108）多層目錄階層與章內小節

### 問題

自動目錄（Sprint 85）只有一層。兩件事因此做不到，而第二本書《街角慢行》正好兩件都需要：

其一，條目樣式單一（`generate_toc.entry_style`），所以部、章、節在目錄上長得一模一樣，讀者看不出階層。

其二，只列 `path` 章的章首頁，章內小節無從列入。《街角慢行》三章各有兩個 `小節標-黑體`，六個小節在目錄上完全不存在，讀者翻目錄找不到「把速度調慢一點」在第 3 頁。

### 新增

- [實作] `document@2` 相容擴充 `paragraphs[].toc_title`／`toc_level`：章內小節以段落自身宣告列入目錄。標題語意屬使用者（§4.4 分工鐵律），故一律顯式宣告，引擎不從樣式名、字型或字級反推階層。`toc_level` 未宣告者承所屬章層級 +1；不得單獨出現（無標題即不列入目錄，單給層級是無效宣告，快速失敗）。
- [實作] `book@1` 相容擴充 `chapters[].toc_level`（選配，預設 1）與 `generate_toc.entry_styles`（第二層起的逐層條目樣式）。第一層恆由既有 `entry_style` 宣告，故 `entry_styles` 的鍵須 ≥2（宣告 `"1"` 即雙源，快速失敗）。
- [實作] `TocItem.level`：條目層級進入回傳值，呼叫端（CLI、測試、日後的目錄 UI）不需自行推斷。
- [實作] `templates/jiejiao-manxing.json` 加 `目錄-小節條目`（第二層：9.0pt 對章條目 10.5pt、天頭再縮退 2 字格、色票淡墨 K55）。
- [實作] `tests/test_toc_levels.py`：17 測試。

### 修正

- [實作] **編輯段落不再讓它從目錄消失**（Gate 3 同類掃描）：`editing.py` 有 7 處以列舉欄位重建 `Paragraph`，新增欄位會被靜默丟掉，即改一個字就把該小節移出目錄。改以 `dataclasses.replace` 保欄位（日後再加欄位亦不重演），並補 `text=""` 以維持「runs 刪空回合法空段」的既有不變式。

### 行為

- **階層縮排是資料層的事**：引擎不認識「層級」，只認識該層條目掛的樣式；縮排走既有 `head_offset_chars` 段級天頭縮退，**零新幾何機制**。
- **用到未宣告樣式的層級即快速失敗**並列出已宣告層級，不沉默落回第一層樣式。
- **兩趟穩定分頁的前提不變**：條目數＝宣告數（列入章＋宣告小節），仍為先驗定值，故目錄頁數與算出的頁碼數字無關。
- **各 `path` 章於 pass 1 前先行載入**（章內小節宣告在章文件裡，須讀過才知條目數）。

### 驗證

- 基線 **986 → 1003 passed（+17）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C22 全過（0 退步）。
- `tests/test_second_book.py` 一處斷言隨樣本擴充改寫：原 `len(items) == 3`，改為分層斷言（章 3 條、小節 6 條、不得出現第三層），為加強非放寬。
- **R5 真實素材驗收**（自撰原創《街角慢行》，非參考書）：CLI 全鏈實跑（`assemble` 7 章 49 段、自動目錄九條 → `render` 13 頁／禁則 0 違規／擠入 6 撐開 0 超容忍 0 → `export-pdf` 5 款字型子集嵌入且授權檢查零警告 → `preflight` 12/12、最高 TAC 92% 在上限內）；目錄頁 PNG 親 Read 目視：九條目右至左依「章 → 其兩小節 → 次章」排列，小節條目明顯小一號、色較淡、起排位置較低，引導線各自落到頁碼 2／3／4／6／7／8／10／11／12。
- **Gate 4 獨立複驗**（PyMuPDF 直讀 PDF，不 import 本專案任何模組）：目錄頁 span 字級分化為 `SourceHanSerifTC-Regular` 10.50pt×26 字（章）與 9.00pt×42 字（小節）；以去空白全文比對各標題在內文頁的實際出現頁，**九條逐條與目錄印出的頁碼相符**；另讀內容流確認 `0 0 0 0.55 k` 填色算符存在（淡墨確實落墨，非只是資料層的色票名）。

### 未做

- 目錄摘要層與部名分組多樣式（GAPS #44 (c) 剩項，摘要層需先下載國發會 TW-Kai，承 #12）。
- 小節宣告只能手寫進 doc.json：`import-md`／`import-txt`／`import-docx` 皆不產 `toc_title`（承 #61 (d) 匯入不產節首標記的同類），故 md 重新匯入會覆蓋掉手加的宣告。
- editor 無任何目錄 UI（書冊組裝仍只有 CLI）；層級深度不設上限但無縮排自動推導，每層都得在模版裡各備一個樣式。

### 待 Owner 真實素材驗收

- 兩層目錄在真視窗與實體打樣上的階層辨識度（9.0pt 對 10.5pt、淡墨對墨黑是否足夠分明）。

## v0.101.0（2026-07-19，Sprint 107）編輯器稿件匯入與匯入端預設值修正

### 問題

兩件事，第二件是查第一件時翻出來的。

其一，三個匯入器（txt／md／docx）自 Phase 1 起只有 CLI 入口。編輯器的選單列是「編輯／樣式／模版／圖片／檢查／設定／說明」，沒有「檔案」。使用者想把自己的稿件放進 APP，得先開終端機跑 `python -m cjkfolio.cli import-txt`，產出 doc.json 再開啟，等於 APP 不能獨立完成「開一本新稿」。

其二，Sprint 105 把「新稿掛哪張主版」從寫死的「A-內文版」搬進 `Template.default_master`，但同一組硬編碼還有一處沒搬：`import_txt` 的 `DEFAULT_BODY_STYLE`＝「內文-明體直排」，是第一本書的樣式名，而 CLI `--style` 的預設值直接指向它。一手實測：

```
$ python -m cjkfolio.cli import-txt 稿.txt -o doc.json --template templates/jiejiao-manxing.json
匯入完成：2 段 → doc.json          ← exit 0
$ python -m cjkfolio.cli render doc.json -o out/ --template templates/jiejiao-manxing.json
錯誤：文件引用模版沒有的樣式：['內文-明體直排']
```

匯入端回報成功、產出的卻是壞文件，錯誤延到渲染才現形。

### 新增

- [實作] `editor/import_core.py`：匯入判定層（Qt 無關，入 pytest 基線，同 Sprint 100 `preflight_core`／104 `ai_assign_core` 的分層）。`import_manuscript` 依副檔名分派 `.txt`／`.md`／`.markdown`／`.docx`，**三個預設值（template_id、master、內文樣式）一律由當前模版推導**，並在回傳前確認 `default_master` 確實存在於該模版的主版清單。可在匯入時判定的錯，不留給下游。
- [實作] `editor/import_actions.py`：呈現層。「檔案 → 匯入稿件…（txt／md／docx）」，換稿後畫布回第一頁重繪，statusBar 報段數、頁數與樣式分布；txt 另提示「可用『樣式 → AI 樣式指派』分派結構」，該提示是純文字入口通往 AI 指派的唯一導引。
- [實作] `cjkfolio/session.py::replace_document`：整份換文件。**游標歸零**（新稿段數與舊稿無關，沿用舊游標會指到不存在的段），入統一 undo 歷史，樣式缺失於套用前重排 KeyError 快速失敗且狀態不變。
- [實作] `tests/test_manuscript_import.py`：25 測試。
- [實作] `editor/smoke_import.py`：離屏 C22。

### 修正

- [實作] **匯入端不再寫死內文樣式**：判定層與 CLI `--style` 兩處同源修正，未指定時取 `template.md_mapping["paragraph"]`；顯式 `--style` 仍優先。守門測試不驗字串相等，而驗「三格式的匯入產物皆須直接 `layout_document` 排得出來」，把這類延遲失敗擋在匯入當下。

### 行為

- **匯入即取代整份文件，不設 modal 確認**。取代的事實與復原方式（一步 Ctrl+Z）寫在 statusBar，且 offscreen 驗證跑不了 modal。與 Sprint 77 套用整份模版一致。
- **AI 金鑰預設值走 `local/ai-config.local.json`，不入程式碼**（Owner 定案，PLAN §10）。AI 設定面板開啟時本就自動帶入既有值，體驗等同「預設已填好」，而程式碼與 repo 零金鑰、§8 金鑰紅線一字不動。原有私有設定備份為 `.bak-tailscale`，不覆蓋丟失。

### 驗證

- 基線 **961 → 986 passed（+25）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C22 全過（0 退步）。
- 新增 25 測試：模版推導三格式各一／《街角慢行》模版下 txt 不得取到第一本書的樣式／大小寫副檔名／**三格式產物皆須直接排得出來**／不支援副檔名訊息含該副檔名與支援清單／缺 `default_master` 明確失敗／CLI 不給 `--style` 取模版內文樣式＋顯式 `--style` 仍優先／`replace_document` 的換稿重排、游標歸零、一步 undo 回原、樣式缺失不入歷史、同物件 no-op。
- 離屏 C22：md 真素材換稿並落到**現行模版**的樣式、回第一頁、畫布重繪、Ctrl+Z 回原稿、txt 全掛內文並提示接 AI、docx 三層對映；不支援格式／缺檔／取消三路皆據實提示且原稿一字不動。
- **R5 真實素材驗收＝使用者情境的完整鏈路**：《街角慢行》第一章剝除全部 markdown 標記為無結構 txt（11 段 613 字）→ 匯入（全掛「內文-宋體直排」、master 甲-內文）→ AI 分析（真 NVIDIA endpoint，1 批 50.9s，建議非空 11/11、**候選集越界建議 0 筆**）→ 與原稿結構一致 **10/11** → 匯出 PDF。
- **Gate 4 獨立複驗**（PyMuPDF 1.27.2 直讀 PDF 物件，不呼叫本專案任何渲染器或檢查器）：3 頁 617 span，內文 `SourceHanSerifTC-Regular` 10.5pt×597 span、小節標 `SourceHanSansTC-Bold` 11.5pt×16 span，與模版宣告（思源宋體 10.5／思源黑體 11.5）逐項吻合。**AI 判出的層級確實在版面上分化為不同字型與字級**，非僅資料層的樣式字串。

### 未做

- **匯入即取代整份文件**，無「插入至游標」「附加至書末」（GAPS #61 (a)）。
- **模版 id 取自 `doc.template` 字串，而 `apply_template` 換模版時不更新該欄位**（既有不一致，非本 Sprint 引入）：套用他本書模版後再匯入，新稿的 `template` 欄位會記成舊模版 id。樣式與主版皆取自現行 `session.template` 故版面正確，受影響的只有 JSON 的 id 欄位與其後的 CLI 再處理（(b)）。
- docx 仍是 Sprint 72 的 v1 解析（表格、圖片、註腳、追蹤修訂不處理，(c)）；匯入不產節首標記（(d)）；真視窗手感待 Owner 批次（(e)、GAPS #19）。
- AI 指派的引文誤判（10/11 的那 1）為 §4.4 修正 2 已定案的層級模糊，由人工校正兜底，不補。

### 待 Owner 真實素材驗收

- 真視窗開啟「檔案 → 匯入稿件…」，以自己的 txt／Word 稿實測對話框與匯入後的畫布觀感。
- 真 Word（中文版「標題 1」）／LibreOffice／Google Docs 匯出的 docx 仍無一手實測（GAPS #35 (a)）。

## v0.100.0（2026-07-18，Sprint 106）效能量測與基線（關 GAPS #56 丙(12)）

### 問題

到此為止，本產品唯一的效能數字是 Spike 3 的「單章純排版邏輯 7.67ms」。排版、渲染、匯出、preflight 四道工序，沒有任何一項在書級規模上量過。「全書重排會不會卡」「匯出一本書要多久」在此之前都是沒有數據的問題。

### 新增

- [實作] `tools/measure_performance.py`：逐規模量四道工序耗時。素材取 repo 內可散布的自撰原創散文 `samples/paiban-xiaoji-ch1.md`，以**段落序列整數倍重複**放大到目標頁數（重複而非隨機生成，斷行與禁則的工作量因此與真實稿件同量級；任何人可從 repo 內容原樣重現，不需參考書）。排版取多次中位數（首次呼叫含字型載入等一次性成本，取平均會被拖偏）。`--scales`／`--repeats`／`--skip-render`／`--layout-only`。
- [實作] `tests/test_performance_tool.py`：7 測試，驗工具本身而非時間數字。

### 基線（本機，171 頁 ≈ 參考書 179 頁規模）

| 頁數 | 排版 | 每頁排版 | 渲染（150dpi） | 匯出 | preflight | PDF | X-1a |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 6ms | 0.55ms | 376ms | 1.52s | 82ms | 222KB | 通過 |
| 43 | 27ms | 0.63ms | 1.52s | 1.89s | 136ms | 285KB | 通過 |
| 86 | 55ms | 0.64ms | 3.04s | 2.04s | 226ms | 368KB | 通過 |
| 171 | 146ms | 0.85ms | 6.38s | 2.35s | 359ms | 535KB | 通過 |

三項判讀：

- **全書重排 146ms**，遠低於人眼可察閾值，故編輯器的全書級重排不需要背景執行緒。
- **匯出的大宗是固定成本**（字型子集化）：11 頁已耗 1.52s，171 頁才 2.35s，多排 160 頁只多 0.83s。Sprint 100 把「匯出＋三項檢查」整包移入背景執行緒的決定，在書級規模上依然成立（171 頁一輪合計約 2.7s）。
- **渲染是最慢一道且與頁數成正比**（約 0.037s/頁），屬每頁一張 PNG 的本質成本。

### 修正

- [實作] **線性度的判讀方法**：初版工具以首末列耗時倍率下結論，得出「頁數放大 15.5 倍、排版 24.8 倍＝超線性，須查演算法」。加 `--layout-only` 隔開匯出與 preflight 的秒級固定成本後細部掃描 9 個規模，**每頁排版在 107〜342 頁區間為 0.71〜0.80ms（末／首 1.05 倍）＝線性**；小規模（64〜86 頁）每頁反而更快（0.55〜0.64ms，快取與暖機優勢），**以小規模當基準算倍率必然把線性讀成超線性**。工具改列「每頁耗時」欄與對應判讀說明，不再以首末倍率下結論。

### 行為

- **效能數字不入自動測試斷言**：耗時隨機器而異，斷言毫秒值等於製造跨機器假失敗。測試只驗工具可跑與放大邏輯正確，基線數字記於 PLAN 進度條與 GAPS #60。

### 驗證

- 基線 **954 → 961 passed（+7）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C21 全過（0 退步）。
- 新增 7 測試：素材與模版皆在 repo 內／放大為整數倍重複且內容順序保留／倍數 1 為恆等／`timed` 取中位數且回最後一次值／`_fmt` 於 1 秒換單位／`layout_only` 確實不跑後三道且頁數隨倍數成長／完整一輪真的匯出 PDF 且 preflight 通過。
- **R5 真實素材驗收**：素材即自撰原創散文（非合成亂數、非參考書），四級規模的 PDF/X-1a 逐級實跑通過，PDF 大小隨頁數單調成長（222／285／368／535KB）。

### 未做

- **只量單機單次**，無跨機器、跨 Python 版本、跨 OS 基線，數字不可移植（GAPS #60 (a)）。
- **未量記憶體峰值**（(b)）、**未量編輯器互動路徑**（單鍵插字的增量重排、畫布重繪，(c)）。
- **未設效能回歸門檻**，數字只記錄不守門（(d)，刻意如此，見上）。
- 放大素材為單章重複，**未含置入影像、圖文繞排、注音 ruby、標點擠壓**等較重路徑，基線是這些功能關閉時的數字（(e)）；渲染僅量 150dpi，未量 300dpi 送印級（(f)）。

## v0.99.0（2026-07-18，Sprint 105）多書專案驗證（關 GAPS #56 丙(11)）

### 問題

到 Sprint 104 為止，本產品排過的書只有一本：參考書《內在整理》，以及從它衍生的自擬單張樣張。所有樣張都用同一份模版、同一個開本、同一組主版名。這種情況下「管線可用」和「管線只對這本書可用」在外觀上完全一樣，分不出來。

### 新增

- [實作] `templates/jiejiao-manxing.json`：第二套模版，**自擬設計**（開本 130×190mm、天頭 24mm、書口 16mm、內文 10.5pt／字距 11.03pt／行距 21.0pt、每行 34 字每頁 13 行）。與參考書模版的開本、版心、字級、行距、主版名（甲-內文／乙-章扉／丙-目錄）、樣式名、色票名**零共用**，交集為空由測試釘死。幾何全部自算，非任何既有書籍的量測。
- [實作] `samples/jiejiao-manxing-ch1.md`〜`-ch3.md`：**自撰原創**散文《街角慢行》三章（1,549 漢字），可隨 repo 散布（版權紅線：不取真書任何文字）。
- [實作] `samples/jiejiao-manxing-open1.doc.json`〜`-open3.doc.json`＋`samples/book-jiejiao-manxing.json`：三張章扉＋書冊清單（自動目錄＋三組「章扉＋內文」共 7 章）。
- [實作] `tests/test_second_book.py`：16 測試，釘死整條管線的**參數化**（見驗證）。

### 變更

- [實作] `cjkfolio/styles.py`：template@1 相容擴充 `Template.default_master`（選配；宣告值不在 `masters` 內即載入快速失敗；`template_to_dict` 未宣告者不寫出空鍵，round-trip 不變形）。
- [實作] `templates/neizai-zhengli.json`：補宣告 `"default_master": "A-內文版"`，即把原本寫死於程式的預設原封搬進資料層，既有行為不變。
- [實作] `cjkfolio/cli.py`：新增 `_import_target`，供 `import-txt`／`import-md`／`import-docx` 三者共用；三個子命令一律加 `--master`（`import-txt` 原本連 `--template` 都沒有，一併補上）。

### 修正

- [實作] **CLI 匯入的 `--template` 只餵樣式對映，文件的 `meta.template`／`meta.master` 仍寫死參考書預設**（`neizai-zhengli`／`A-內文版`）。第二本書用 CLI 匯入時，產出的文件會掛到一個在該模版裡根本不存在的主版名。改為：模版 id 取 `--template` 的檔名（不另猜）、主版取 `--master` 覆寫或模版宣告的 `default_master`，**兩者皆無時快速失敗並列出可選主版**，不沉默套用參考書的主版名。

### 行為

- **模版自行宣告預設主版**，不再由程式常數決定。缺宣告又未給 `--master` 時快速失敗，不猜。
- **未宣告 `color` 的樣式落回 `DEFAULT_TEXT_CMYK` K92**（§10 Sprint 8 為參考書定案的暖黑）。判為資料問題不改程式：第二本書設計取 K90，故其樣式逐一宣告 `color`。不追加 `default_text_color` 模版欄位，理由是色票本就是每個樣式可宣告的欄位，再加一層全域預設只是把同一個決定挪個位置。

### 驗證

- 基線 **938 → 954 passed（+16）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C21 全過（0 退步）。
- 新增 16 測試：模版與參考書零交集／兩份模版各自宣告 `default_master`／目錄主版不設 `rule` 仍合法（驗 `rule` 為選配非必填）／三章匯入掛第二套模版與主版／落檔 doc.json 一致／書冊清單 7 章／章扉與內文的節式主版切換序列／整本頁面幾何逐項由模版推導（行軸與版心寬獨立算一次比對）／整本流排 0 違規且目錄頁碼遞增不超出總頁數／整本 13 頁且章扉落點 2／6／10／匯出盒框與 preflight／素材原創且無破折號／清單為合法 JSON。
- **R5 真實素材驗收**（自撰原創，非參考書）：CLI 全鏈實跑（`import-md` 三章各 11 段 → `assemble` 7 章 43 段、自動目錄「第一章→2、第二章→6、第三章→10」→ `render` **13 頁／禁則 0 違規／擠入 6 撐開 0 超容忍 0**／5 款字型 → `export-pdf` 五款子集嵌入且授權檢查零警告 → `preflight` **12/12**、無置入影像、最高 TAC 92% 在上限內）。PNG 三頁親 Read 目視：頁 1 目錄（「目次」標題＋三條目引導線垂直落到頁碼 2／6／10，本主版無頁腳故無頁碼，與參考書 D-目錄 有虛線的形態不同）、頁 2 章扉（`mirror=false` 兩欄自 outer 側起排、整頁無頁腳、天頭 46mm 留白）、頁 5 內文（奇數＝左頁，頁碼在書口左、無書眉）。
- **Gate 4 獨立驗證**（PyMuPDF 直接讀 PDF，不 import 本專案任何模組）：TrimBox **130.000×190.000mm**、MediaBox 136×196mm（出血每邊 3.000mm）、全書 TrimBox 種類數 1；逐頁側別 **10/10 全對**（偶數頁頁碼落右半且有書眉、奇數頁落左半且無書眉、章扉 2／6／10 無頁腳）；章扉與目錄的文字內容逐頁抽取相符。
- 連帶量到：內容流發出的 K 值為 {0.55, 0.9, 0.92}，但**其後真有繪字算符者只有 {0.55, 0.9}**，即 K92 係 `_Content` prologue 的初始填色恆發出，本書實際未以 K92 落墨（TAC 檢核據實記錄，方向保守不低報）。

### 未做

- **第二本書規模僅 1,549 漢字／13 頁**，非真實書籍長度，未驗長書的分頁穩定性與記憶體行為（GAPS #59 (a)）。
- **仍為直排單欄**，未驗橫排書、多欄版面、表格密集型（(b)；PLAN §8 明列首版鎖定直排書冊利基）。
- 第二本書**無置入影像、無注音、無繞排、無標點擠壓**，這些能力仍只有參考書或自擬單張樣張的驗收（(c)）。
- **效能量測與基線未做**（(d)，GAPS #56 丙(12) 為下一項）。

### 待 Owner 真實素材驗收

- 送印刷廠打樣與人類校色（Phase 5 DoD），依賴 Owner 與印刷廠。

## v0.98.0（2026-07-18，Sprint 104）AI 指派背景執行緒（關 GAPS #36 (b)、#56 甲(5)）

### 問題

AI 樣式指派的核心（Sprint 73）與逐段校正 UI（Sprint 79）都完備，但呼叫一直跑在 GUI 執行緒上。全書級指派是數分鐘的網路往返，期間整個視窗無回應：拖不動、打不了字、連捲動都停住。Gate 4 實測（20ms 心跳計時器）：同步呼叫的 25.59 秒內，主執行緒心跳跳了 **0** 次。

### 新增

- [實作] `editor/ai_assign_core.py`：AI 指派的判定層（Qt 無關，故背景執行緒與 pytest 皆可跑，同 Sprint 100 `preflight_core` 的分層）。`paragraph_texts` 取送檢當下的逐段文字快照；`assignments_still_apply` 逐段比對現行文件是否仍對得上。
- [實作] `editor/ai_actions.py`：`AiAssignThread`（QThread 子類，跑不吃外部可變狀態的無參呼叫）＋`AiActionsMixin`（`_show_ai_config`／`_run_ai_assign`／`_apply_assignments` 自 `app.py` 搬入，同 StyleActionsMixin 慣例控管行數）；`_ai_assign_wait` 供離屏驗證等待派送；`closeEvent` 關窗前收掉 worker。
- [實作] `editor/smoke_ai.py`：C21 離屏煙霧驗證（抽為獨立模組，同 Sprint 101／102 的行數紀律）。

### 變更

- [實作] `editor/app.py`：`EditorWindow` 加繼承 `AiActionsMixin`（置於 `PreflightActionsMixin` 前，`closeEvent` 鏈為 AiActionsMixin → PreflightActionsMixin → QWidget）；移除搬走的三個方法與隨之成為孤兒的 `QDialog`／`AiConfigDialog`／`AssignReviewDialog`／`load_ai_config`／`suggest_styles` import。

### 修正

- [實作] **真呼叫路徑 `load_ai_config()` 漏傳 `path` 參數**（自 Sprint 79 起即存在）：`load_ai_config` 是必填位置參數，故 editor 內不注入替身的 AI 指派一觸即 `TypeError`，從未真正連過線。因 smoke 一律注入 `suggest` 替身而從未走到這條路徑。改為 `load_ai_config(DEFAULT_CONFIG_PATH)`（設定面板寫的同一份本機檔），並於 smoke C21 (5) 以間諜攔在送出前釘死真路徑（不外連 endpoint、不輸出欄位值）。**流程教訓：注入式離屏驗證未覆蓋真路徑的參數組裝。**

### 行為

- **建議索引繫於送檢當下的段落文字**：`suggest_styles` 回的是位置列（第 i 項＝第 i 段），位置只在文字序列不變時有意義。改跑背景後使用者可邊等邊編輯，故送檢前取文字快照，回來時逐段比對；增刪、改寫或對調即**不套用**並據實請重跑，不猜對映。照索引硬套會把建議安到別的段落上，屬沉默的錯派。
- **只改樣式不使快照失效**：建議只依段落文字得出，校正對話框逐列讀的是現行樣式。
- **不提供取消**：底層為 urllib 阻塞請求，無可中斷點。v1 取「等待期間可繼續編輯」而非「可喊停」。
- **單輪執行**：執行中再觸發只提示「AI 指派進行中，請稍候…」，不起第二輪（同 Sprint 100 不重入處置）。
- **失敗據實提示不擋流程**：連線或解析失敗於 statusBar 列出原因，不 crash（同 CLI `assign-styles` 誠實失敗語意）。

### 驗證

- 基線 **931 → 938 passed（+7）/ 0 failed**、typecheck（含 editor）EXIT_CODE=0、smoke C1〜C21 全過（C1〜C20 0 退步）。
- 新增 7 測試（`tests/test_ai_assign_core.py`，Qt 無關）：快照為有序不可變 tuple／未變放行／只改樣式仍放行／段落改寫不放行／插入不放行／刪除不放行／順序對調不放行（文字集合相同但位置已異，比對須依序）。
- smoke 擴 C21（真實執行緒探針，非假時序）：呼叫跑於非 GUI 執行緒（tid 相異）→ 執行中再觸發不重入 → 等待期間主執行緒完成一次插字編輯 → 段序失效不開對話框且 0 段樣式被改、statusBar 據實聲明 → 文件未變照常開且建議帶進下拉 → 連線失敗據實提示不 crash → 真設定路徑讀得到本機檔。
- **R5 真實素材驗收**（自撰原創 `samples/paiban-xiaoji-ch1.md` 41 段＋使用者私有 endpoint，位址與金鑰零輸出＝PLAN §8 紅線）：走 editor 真路徑（`_run_ai_assign()` 不注入替身）→ 29.05 秒回傳、校正對話框開出 41 列、5 種樣式建議、預設勾選 4 段（其餘與 md 匯入既有樣式相同故不勾）、0 降級警告。
- **Gate 4 獨立驗證**（不呼叫本專案任何斷言或探針；A/B 為同一份真實呼叫各跑一次）：主執行緒 20ms QTimer 心跳計次，**背景執行緒版跳 1452 次**（29.05 秒），**同步呼叫版跳 0 次**（25.59 秒），即改動前的行為確實整段凍住 GUI 執行緒。另獨立複驗 MRO 與資源收尾：`closeEvent` 定義於 AiActionsMixin／PreflightActionsMixin／QWidget，關窗後兩條 worker 皆為 `None`。
- 回歸：本 Sprint 零排版程式碼改動（新增模組皆為 editor 層與 Qt 無關判定層），938 全綠涵蓋既有版面與輸出測試。

### 未做

- **無取消鈕**：等待期間可繼續編輯，但無法喊停（GAPS #58 (a)）。
- **段序失效即整批作廢**：不做文字比對重新對映到新段序，使用者須重跑。長呼叫後被作廢的代價由使用者承擔，換得的是絕不錯派（(b)）。
- **單輪執行，不排隊不並行**（(c)）。

### 待 Owner（真視窗，離屏測不了）

- 背景指派期間繼續編輯的順暢度。
- 段序失效訊息的可讀性（使用者是否看得懂為何白等一場、該怎麼辦）。

### 待 Owner 真實素材驗收

- 真視窗（非離屏）走一次完整 AI 指派並抽檢建議品質，屬 GAPS #19 批次。

## v0.97.0（2026-07-18，Sprint 103）文繞圖參數 UI 與畫布繞排（關 GAPS #49 (e)、#56 甲(4)）

### 問題

圖文繞排核心自 Sprint 89 就完備並驗收，但兩件事讓它在編輯器裡等於不存在：`wrap`／`wrap_margin_mm` **只能手寫 JSON**，而且 **editor 畫布不套繞排**（會談層的重排走 `layout_document`，兩個渲染後端走 `layout_with_wrap`），所以就算手寫了 JSON，畫布上看到的斷行也不是匯出會得到的斷行。

### 新增

- [實作] `cjkfolio/image_editing.py`：`set_image_wrap(doc, idx, *, wrap, margin_mm)`＝繞排參數的判定層（不可變、Qt 無關）。兩個欄位皆選配，未指定者保持現值；等值變更回原文件物件供上層判 no-op。
- [實作] `cjkfolio/session.py`：`EditSession.set_image_wrap` 經 `_commit_pair` 入**與文字、樣式、置圖編輯同一條 undo 歷史**。
- [實作] `editor/image_actions.py`：`WrapDialog`（繞排開關＋圖文間隙，內嵌警示列）與 `_edit_image_wrap`／`_apply_image_wrap` 回呼。
- [實作] `editor/app.py`：「圖片」選單加「選取圖片的文繞圖設定…」。

### 變更

- [實作] **會談層與編輯層的重排入口統一為 `layout_with_wrap`**（`cjkfolio/editing.py` 10 處、`cjkfolio/session.py` 4 處），與 `render.py`／`pdf_writer.py` 同一入口，故**編輯器畫布所見的斷行就是匯出所得**。無 `wrap` 圖時 `layout_with_wrap` 原樣回傳 `layout_document` 的結果，既有輸出零變更（`wrap=False` 為預設）。
- [實作] `cjkfolio/toc.py`：自動目錄的兩趟分頁改走 `layout_with_wrap`（Gate 3 同類掃描抓出）。書冊帶 `wrap` 圖時，繞排把內文往後推，用不繞排的分頁定條目頁碼會**印出比實際早的頁**（自擬雙章書冊實測：目錄印「第二章 第 5 頁」，實際排在第 6 頁）。
- [實作] `editor/app.py::_rebuild` 先把 `self.page` 換成新版面中同頁號的頁物件。`self.page` 是頁物件快照，重排後不換就以舊幾何重繪＝**畫面看不到這次重排**；繞排開關與樣式改動皆屬此類。重排後頁數縮減時夾到末頁。

### 行為

- **對話框按確定才提交一步 undo**（同 Sprint 102「放開左鍵才提交」的取捨）：開關與間隙兩欄位一起提交，調一次參數只留一步歷史。
- **間隙以 mm 表達**（同 `wrap_margin_mm` 與模版所有邊距的單位，不另立 pt 欄位）；非數字輸入擋在對話框內，文件不動。
- **未選取圖時據實提示**「先點選一張置入圖」，不猜使用者指的是哪張。
- **槽式圖不可開繞排**（無座標即無排除區可算），快速失敗而非默默忽略；與 `document.py` 解析層「`wrap` 需搭 `rect`」同一條規則。

### 驗證

- 基線 **921 → 931 passed（+10）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C20 全過（0 退步）。
- 新增 9 測試（`tests/test_image_editing.py`）：判定層 6（開關與間隙、未指定欄位保持現值、等值 no-op、槽式圖守門、負間隙守門、索引越界）＋session 3（開關使畫布版面重排且一步 undo 回原、加大間隙使排除區外擴、no-op 不入歷史）；另 `tests/test_toc.py` +1（帶 wrap 圖的書冊條目頁碼須依繞排後分頁；還原修正後該測試確實 RED，非空測試）。
- smoke 擴 C20：畫布確實套繞排（被圖擋住的欄行長 ≤ 半行、互動層字格數同步）→ UI 關繞排使內文回滿行、加大間隙使排除區外擴，兩者各一步 undo 回原 → 對話框預填現值且非數字間隙擋在對話框內 → 未選取圖據實提示。
- **R5 真實素材＋Gate 4 獨立驗證**：以參考書送印稿內的**真實影像**（1757×2391，本機抽出轉灰階至暫存目錄，**不入 repo**）配自撰原創散文《排版小記》第一章（41 段），走完整 UI 路徑（拖放置入 → 拖角等比縮小到 119pt 寬 → 拖曳移到版心下段 → 文繞圖對話框開繞排並設間隙 3.5mm），首頁互動層字格 183 → 152。再以 PyMuPDF **自行解析最終 PDF 的逐字落點與影像 XObject 落點**（不呼叫本專案任何渲染、排版或檢查器）複驗：影像四邊對 UI 圖框最大差異 **0.000136pt**；首頁 152 字**落入「圖框＋3.5mm 間隙」排除區者 0 字**。另 render PNG 親 Read 目視：圖框內無字、受影響欄的字在圖上方收住、頁碼在左下（奇數＝左頁），禁則 0 違規（產出全留暫存目錄，不入 repo）。

### 未做

- **繞排仍只直排 body**（橫排頁不繞排，承 GAPS #49 (a)）、**矩形排除區非輪廓繞排**（(b)）、**同欄不跨圖續排**（(c)）：皆為核心層既有限制，本 Sprint 只接 UI 未改規則。
- **畫布不畫排除區的視覺提示**：使用者看得到文字讓開，但看不到「讓開多少」的輔助框。
- **間隙為四周等距單值**（`wrap_margin_mm` 的模型），無上下左右分別設定。
- **無「圖文繞排 off 時的疊放順序」UI**：關繞排時圖恆疊在文字上，不能讓文字壓在圖上。

### 待 Owner（真視窗，離屏測不了）

- 文繞圖對話框的欄位是否好懂（「內文繞開這張圖」的措辭、間隙單位是否清楚）。
- 開關繞排後畫布重排的視覺跳動是否可接受（整頁重繪，非局部更新）。

## v0.96.0（2026-07-18，Sprint 102）畫布拖放與縮放置圖 UI（關 GAPS #29 (d)、#56 甲(3)）

### 問題

置圖核心自 Sprint 50〜54 就完備（`PlacedImage.rect` 任意圖框、兩後端幾何同源、灰階與 CMYK 分流、PPI 與墨量檢核），但**只能靠手寫 JSON 的座標置入**：editor 畫布既不顯示置入圖，也沒有拖放、拖曳、縮放的任何入口。

### 新增

- [實作] `cjkfolio/image_editing.py`：置圖編輯的判定層（Qt 無關，pytest 可離屏驗）。`place_image`／`move_image`／`resize_image`／`remove_image` 四個不可變文件編輯函式，`default_image_rect`（拖放預設尺寸）、`image_at_point`（命中）、`handle_rects`／`handle_at_point`（角控制點）、`resize_rect`（縮放幾何）。
- [實作] `cjkfolio/session.py`：`place_image`／`move_image`／`resize_image`／`remove_image` 四個會談方法，**與文字、樣式編輯共用同一條 undo 歷史**（Ctrl+Z 的回退順序即使用者實際操作順序）。
- [實作] `editor/canvas.py`：`page_images`（逐頁置入圖解析）與 `iter_image_rects`；`build_page_scene` 收 `images` 參數使**底圖畫出置入圖**，互動層加圖框 `("image", idx)` z=2 與四角控制點 `("image-handle", idx, 角名)` z=5。
- [實作] `editor/image_actions.py`：`ImageActionsMixin`＝拖放置入、選取、拖曳移動、拖角縮放、Delete 移除。
- [實作] `editor/canvas_view.py`：`CanvasView` 加 `on_move`／`on_release`／`on_drop` 三個回呼與拖放事件處理。
- [實作] `editor/app.py`：「圖片」選單（置入圖片、移除選取的圖片）；`_on_pick` 分流圖框、Delete 鍵在選圖時吃圖不吃字。

### 行為

- **拖曳途中只畫虛線預覽框，放開左鍵才提交一步**。拖一次圖只留一步 undo，不讓每個 `mouseMove` 各成一步歷史。
- **預設置入尺寸取 §9 下限 300ppi 的原生尺寸**（仍合印前規格時能放到的最大尺寸），超出頁面時等比縮到整頁可容；落點即圖框中心。
- **拖角縮放為等比**（框恆貼合來源影像比例），拖多少放大多少，不產生 `fit_image_rect` 的 contain 留白。
- **圖檔讀不到時據實提示並照常顯示無圖版面**，不讓一張缺圖使編輯器打不開，也不把缺圖默默移出文件。
- 拖放只接受 `.png`／`.tif`／`.tiff`／`.jpg`／`.jpeg` 的本機檔案，其餘在 `dragEnter` 即拒絕。
- 槽式圖（`rect` 為 `None`，由主版 figure 保留區定位）**不可拖放或縮放**，快速失敗而非默默改寫成 rect 圖。

### 重構

- [實作] `CanvasView` 自 `editor/app.py` 抽為 `editor/canvas_view.py`（app.py 加入置圖接線後將逾 800 行）。搬移部分為**純機械搬移**，三個既有回呼行為逐字不變；新增的是置圖需要的三個回呼與拖放事件。
- [實作] C19 抽為 `editor/smoke_images.py`（`smoke_check.py` 已逼近 800 行上限，同 Sprint 101 `smoke_preflight` 處置）。

### 驗證

- 基線 **895 → 921 passed（+26）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C19 全過（0 退步）。
- 新增 26 測試（`tests/test_image_editing.py`）：正規化與退化守門 2＋預設尺寸 3＋文件層編輯與不可變性 7＋命中與控制點 4＋縮放幾何 7＋session undo／redo 接線 3。
- smoke 擴 C19：**真 `QDropEvent` 拖放**真圖檔入畫布（非影像檔拒收）→ 300ppi 預設框置於落點＋**底圖確有墨跡**＋互動層圖框與四角控制點（字格 48 格不退步）→ 拖曳移動（途中文件不動）→ 拖角等比縮放（比例守恆、對角固定）→ Delete 移除，三者各一步 undo 回原；缺圖不炸且據實提示。
- **R5 真實素材＋Gate 4 獨立驗證**：以參考書送印稿內的**真實影像**（1757×2391 灰階，本機抽出至暫存目錄，**不入 repo**）走完整 UI 路徑（拖放 → 移動 → 等比縮放），再以 PyMuPDF **自行解析最終 PDF 的影像 XObject 落點**（不呼叫本專案任何渲染或檢查器）複驗：四邊與 UI 提交的圖框最大差異 **0.000508pt**、繪製比 0.734840 對來源像素比 0.734839、實效 632.5ppi。另 render PNG 親 Read 目視確認圖確實落在拖到的位置且內文 0 違規（out 不入 repo）。

### 未做

- **繞排參數無 UI**（`wrap`／`wrap_margin_mm` 仍須手寫 JSON），且 editor 畫布不套繞排（承 GAPS #49 (e)，為 #56 甲(4) 的範圍）。
- **無等比／自由拉框的切換鍵**：拖角一律等比。自由拉框的幾何已在 `resize_rect(aspect=None)` 實作並測試，只是沒有 UI 開關。
- **無鍵盤微調、無對齊輔助線、無多選**：移動與縮放只有滑鼠拖曳一種方式。
- **槽式圖無 UI**：主版 figure 保留區的槽式置入仍只能寫 JSON。
- 拖放置入的圖檔在文件目錄外時存絕對路徑（**不擅自複製檔案進專案目錄**），文件搬移後該圖會失連。

### 待 Owner（真視窗，離屏測不了）

- 拖曳與縮放的手感（跟手程度、控制點是否好抓、預覽框是否清楚）。
- 自檔案總管拖圖進畫布的實際體感與游標回饋。
- 選取外框（藍實線）與拖曳預覽（紅虛線）在真視窗的可辨識度。

## v0.95.0（2026-07-18，Sprint 101）X-4 preflight 與 ICC 選取器（關 GAPS #47 (a)、#56 甲(2)）

### 問題

匯出層自 Sprint 82 起就支援 PDF/X-4:2010，但 editor 的 preflight 面板只驗預設 X-1a。X-4 強制嵌 DestOutputProfile，registry 名不足，而 editor 沒有任何選 ICC 的入口。

### 新增

- [實作] `editor/preflight_core.py`：`run_preflight_checks` 與 `preflight_cache_key` 收 `pdfx` 與 `icc_profile` 兩個具名參數；`PreflightResults` 加 `profile` 欄位供呈現層標示規則集。
- [實作] `editor/preflight_actions.py`：`_ensure_preflight_icc()` 以 `QFileDialog` 選 CMYK 輸出 ICC，選過的路徑留在本視窗沿用；`_run_preflight("x-4")` 入口。
- [實作] `editor/preflight_panel.py`：`PreflightDialog` 收 `profile_label`，視窗標題與首分頁標籤據實標示是 X-1a 還是 X-4（兩份結論規則集不同，不讓它們看起來同名）。
- [實作] `editor/app.py`：「檢查」選單加「PDF/X-4 preflight（需輸出 ICC）…」。

### 行為

- 取消選 ICC：statusBar 說明「未選輸出 ICC，PDF/X-4 preflight 未執行（X-4 須嵌輸出色彩描述檔）」，**不默默改跑 X-1a 再宣稱通過**。
- 快取鍵納入形態與 ICC 檔指紋，**X-1a 的快取不會被 X-4 誤命中**（規則集不同，結論不可互代）。
- X-4 規則集 11 條（不列 `no-transparency`，X-4 允許透明）；X-1a 仍 12 條。

### 重構

- [實作] `editor/smoke_check.py` 逾單檔 800 行上限，preflight 三項驗證（C16〜C18）抽為 `editor/smoke_preflight.py`。**純機械搬移，驗證項與輸出逐字不變**（同 Sprint 93 `pdf_writer` → `pdf_objects` 的處置）。

### 驗證

- 基線 **891 → 895 passed（+4）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C18 全過（0 退步）。
- 新增 4 測試：形態不同即換鍵、ICC 換檔或改內容即換鍵、X-4 嵌 ICC 後 11 規則全過且不列 `no-transparency`、**X-4 未給 ICC 時快速失敗**（不得沉默降級）。
- smoke 擴 C18：取消選 ICC 不執行 → 選取器回傳 ICC 後背景跑出 X-4 11/11 → 面板標題與分頁標 X-4、ICC 留給下次沿用 → 改跑 X-1a 不命中 X-4 快取。
- **R5 真實素材＋Gate 4 獨立驗證**：改用 Windows 內建的**真 CMYK 印表機描述檔 `RSWOP.icm`**（prtr/CMYK，218,103 bytes，只讀不入 repo）跑完整 X-4 匯出，再以 PyMuPDF **直接讀 PDF 物件複驗**（不呼叫 `check_pdfx`，避免同一支檢查器自我背書）：header `%PDF-1.6`、Info 有 `GTS_PDFXVersion (PDF/X-4)` 且無 `GTS_PDFXConformance`、catalog 有 `/OutputIntents`、**DestOutputProfile 串流 218,103 bytes 與 ICC 原檔逐位元組相同**。

### 未做

- **ICC 選取無內容驗證**：只要是可讀檔就送進匯出，是否為合法 CMYK prtr 描述檔由匯出層與印廠判斷（機械 preflight 檢查 header 欄位，不做色彩引擎級解析）。以結構最小的假 ICC 測試時 MuPDF 會在 stderr 印 `cmsOpenProfileFromMem failed`，真 ICC 則無此訊息。
- **形態切換即重跑**：快取仍只留最近一次鍵值，X-1a 與 X-4 交替檢查會互相擠掉（承 GAPS #47 (f)）。
- ICC 路徑不隨文件存檔，換視窗須重選。

### 待 Owner

- 真視窗的 ICC 選檔手感、印廠實際指定的 ICC 檔是否被本管線接受，待 Owner 與印廠實測（#19、#18 批次）。

## v0.94.0（2026-07-18，Sprint 100）preflight 背景執行緒與快取（關 GAPS #47 (d)、#56 甲(1)）

### 問題

`_run_preflight` 過去在 GUI 執行緒上做「匯出臨時 PDF → 三項檢查」，實測**單一樣張就凍住視窗約 816 ms**，文件愈大愈久；且每次觸發都重跑一次完整匯出，即使文件一個字都沒改。

### 新增

- [實作] `editor/preflight_core.py`（Qt 無關，故背景執行緒與 pytest 都能跑）：
  - `run_preflight_checks(doc, template, image_base_dir)`：匯出臨時 PDF/X-1a → `check_pdfx`／`check_image_resolution`／`check_ink_coverage`，回 `PreflightResults` 三份報告。這是把原本的判定層原樣搬出，**判定邏輯仍全在 `cjkfolio.preflight`**（已 pytest 驗），本層只管執行順序。
  - `preflight_cache_key(doc, template, image_base_dir)`：sha256 指紋，涵蓋文件內容、模版、影像基準目錄、每張置入圖檔的大小與修改時間。快取的正確性全繫於此鍵，故逐項以測試釘死。
- [實作] `editor/preflight_actions.py` 改為背景執行：`PreflightThread`（QThread 子類，跑不可變的 doc／template 快照）＋快取命中路徑＋重入守門＋關窗前收執行緒。

### 行為

- 首次檢查：statusBar 顯示「preflight 檢查中（背景執行，可繼續編輯）…」，**視窗不凍**，完成後才開面板。
- 文件未變的二次檢查：直接沿用上次報告，statusBar 據實標「沿用上次結果（文件未變）」，**實測 816 ms 降到 2.6 ms**。
- 文件在檢查期間被改動：報告照常呈現，但 statusBar 標「本報告為送檢當下的快照，其後的編輯未納入」，不假裝是最新結論。
- 檢查進行中再次觸發：提示「preflight 檢查進行中，請稍候…」，不起第二輪。

### 驗證

- 基線 **884 → 891 passed（+7）/ 0 failed**、typecheck EXIT_CODE=0、smoke C1〜C17 全過（0 退步）。
- 新增 `tests/test_preflight_cache.py` 7 測試：快取鍵決定性、文件改一字換鍵、模版改字級換鍵、基準目錄換鍵、置入圖檔位元組改變換鍵、缺圖仍算得出鍵、判定層回三份報告且 X-1a 12/12。
- smoke 擴 C17：以**包住真檢查的探針**記錄實際執行緒 id 與呼叫次數，證明檢查跑在非 GUI 執行緒（tid 相異）、快取命中 0 次重跑、插字後重跑（2 次）、執行中再觸發不起第二輪。
- **Gate 4 獨立驗證**（與 C17 不同方法）：主執行緒掛 20ms 心跳計時器，檢查期間心跳跳了 **40 次**（若凍住則為 0），檢查耗時 815.7 ms、X-1a 12/12、二次呼叫 2.6 ms 回同一份報告物件。

### 未做

- **快取只留最近一次**（單筆鍵值）。undo 回到上一版後再檢查會重跑，非命中。依真實用例再議，記於 GAPS #47 (f)。
- **快取鍵不含字型檔案指紋**。會話中途在磁碟換掉字型檔會讓快取失效判斷失準，v1 以重啟編輯器處理，記於 GAPS #47 (f)。
- 匯出仍是每輪重做一份完整 PDF（未做增量匯出或分章快取）。

### 待 Owner

- 真視窗手感（背景檢查期間繼續編輯的實際順暢度、statusBar 三種聲明的可讀性）待 Owner 實測，離屏只能驗執行緒與快取的行為（#19 批次）。

## v0.93.0（2026-07-18，Sprint 98）開源授權定案 AGPL-3.0-or-later（關 GAPS #55）

### 結論先講：授權是被相依鎖死的，不是偏好

`PyMuPDF` 是 **AGPL-3.0**，而且被 `cjkfolio/preflight.py:12` 與 `cjkfolio/reference_extract.py:14` **in-process import 進產品碼**。只要 CJKFolio 以結合物散布，AGPL 的傳染性即擴及整個專案，MIT、Apache-2.0、BSD、MPL-2.0、LGPL 全部不可選。

一手證據：`pymupdf-1.27.2.3.dist-info/COPYING` 全檔僅一行「Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License」，`METADATA` L8 同字串。

### 新增

- [實作] 根目錄 `LICENSE`：AGPL-3.0 條款全文（34,523 bytes）。取自本機已安裝套件的既有副本，並以另一份獨立副本比對驗證，**條款正文第 0〜17 節逐位元組相同**，唯一差異在附錄的範例聲明換行處，且採用與 gnu.org 一致的變體。
- [實作] `THIRD-PARTY-LICENSES.md`：六項產品相依的逐字授權字串與一手證據路徑、必須履行的義務（§5 修改標註、§13 網路互動的預先聲明、第三方著作權聲明保留）、字型資產授權與缺口、商標名稱聲明、以及本清單的證據邊界。
- [實作] `pyproject.toml`：相依宣告與**授權錨點**。每個相依旁註記其授權，因為授權事實只對特定版本成立（PyMuPDF 在 1.24.x 之前是 GPL v3 而非 AGPL v3，即為漂移實例）。

### 定案要點

- **與 Spike 4 的關係已釐清**：§10（Sprint 5）記載的「禁止 in-process import」決議**明文限定於 Vivliostyle 整合形態**，而該路線未被採用（Sprint 8 定案自寫 PDF 寫出層），且 PLAN 全文從未承諾本專案採寬鬆條款。故本定案不推翻任何已定案承諾。**但誠實記錄**：spike4 報告 :34 的通則「不深度整合 AGPL 元件」在引入 PyMuPDF 時未被重新檢視，屬未察覺的漂移。
- **否決「子程序隔離改採 Apache-2.0」**：即使做隔離，本專案仍須散布一個 `import fitz` 的 worker，該檔本身即為 AGPL 結合物。只換到混合授權的複雜度，換不到下游的實質自由，還會加重 preflight 面板的凍視窗（承 GAPS #47 (d)）。
- **PySide6 取 GPL-3.0-only 臂，不取 LGPL 臂**：稽核發現 `PySide6-Addons` 夾帶的 Qt Quick3D、VirtualKeyboard、HttpServer、Graphs、Charts、DataVisualization 等模組在 Qt 開源側**只有 GPL-3.0 沒有 LGPL 臂**，籠統宣稱「走 LGPL 臂」對實際安裝的內容並不成立。GPL-3.0 與 AGPL-3.0 經 GPLv3 §13 互相授權故相容。**GPL-2.0-only 臂與 AGPL-3.0 不相容，明確不選。**
- **標示分兩層**：自有程式碼 `AGPL-3.0-or-later`；結合散布物實效 `AGPL-3.0`（PyMuPDF 未寫 or-later，PySide6 與 shiboken6 明寫 `-only`）。

### 驗證

- 授權事實經**多代理人稽核**（六路平行實查、判定、四名 skeptic 對抗驗證）產出，其中 **2 名 skeptic 推翻了初版建議**，促成本次的 Spike 4 釐清與 PySide6 臂別修正。所有決定性事實另經本人一手複驗：`COPYING` 全文、產品碼 `import fitz` 落點、spike4 報告原文、PLAN 全文無寬鬆條款承諾、六項相依的 `METADATA` License 欄。
- 基線 **884 passed / 0 failed**、typecheck EXIT_CODE=0。新增 `pyproject.toml` 後另複驗 `python -m pytest`（無參數）亦為 884，確認測試探索行為未被改變。

### 未做與待辦

- **根目錄 README 尚未寫**（下個 Sprint）。故 `pyproject.toml` 不宣告 `readme` 欄，避免指向不存在的檔案。
- **未經法律專業複核**。spike4 報告 :38 亦自記此點，正式公開釋出前應安排。
- `freetype-py` 夾帶的 `libfreetype.dll` 上游授權（FTL 或 GPLv2）無法自 wheel 查證，純原始碼散布風險低，**製作含二進位的安裝檔前必須查證**。
- 傳遞相依未展開稽核。
- **警惕**：本機環境另有 `pymupdf-layout`（Polyform Noncommercial，非開源、與 AGPL 不相容），目前零 import，名稱與 PyMuPDF 近似，極易誤裝誤用。

## v0.92.0（2026-07-18，Sprint 97）真書逐字內容清洗（紅線違反修復，關 GAPS #1）

### 背景：這是一次紅線違反，不是一般整理

開源授權稽核期間對全庫做字串掃描，發現**專案自訂的版權紅線已被違反**：GAPS #1、`.gitignore:1`、`samples/README.md:5` 都明文寫「開源 repo 與公開樣張不得含參考書的任何文字」，但 11 個已追蹤檔案含真書《內在整理》的逐字頁面內容，共 91 處。

洩漏內容為個案扉頁 slot 0 的黑 W7 欄標原文 5 種與資訊區欄位標籤原文 2 種，皆為量測過程引用的短標籤。**誠實界定嚴重度**：著作權風險低（極短欄位標籤），且涉及的姓名是已出版書籍的作者與受訪者，屬一般書目指涉而非個資外洩。真正的問題是**專案違反了自己訂的驗收標準**，而這個專案的全部價值建立在「說到做到」的紀律上。

### 變更

- [實作] 91 處逐字內容全數改為匿名代號：`欄標甲〜戊`（個案扉頁 slot 0 欄標原文 5 種，甲〜丁屬資訊頁 11.5pt×26 頁、戊屬訪談頁 10.5pt×7 頁）、`【欄位甲】【欄位乙】`（資訊區欄位標籤原文 2 種）。
- [實作] 涵蓋 11 檔：`templates/neizai-zhengli.json`（17）、`samples/punct-squeeze.template.json`（17）、`CHANGELOG.md`（12）、`tests/test_styles.py`（11）、PLAN（9）、`GAPS.md`（8）、`devlog/archive/` 四份（15）、`tests/test_layout_render.py`（2）。**範圍含歷史檔**：紅線對 repo 全域適用，不因是歷史紀錄而豁免。
- [實作] 採「代號取代」而非「刪整段」：代號保留「有幾種、屬哪個頁型、哪個級數」的量測語意，Sprint 34〜38 的釐清審計軌跡不失效。GAPS #1 內加代號對照說明。

### 驗證

- Gate 4 換工具獨立複驗：清洗用 Python 正規式（允許字元間夾換行，因 docstring 斷行會把詞拆開），複驗改用 `git grep` 掃 7 個字串 → **0 命中**。
- 基線 **884 passed / 0 failed**、typecheck EXIT_CODE=0（含 editor）、離屏 smoke C1〜C16 全過，皆不退步。守門測試不受影響的原因已查證：`test_styles.py` 與 `test_layout_render.py` 的斷言全為數值與樣式名，原文只出現在 docstring。
- 兩份模版 JSON 清洗後合法性複驗：`neizai-zhengli.json` 18 段落樣式／7 主版、`punct-squeeze.template.json` 19 段落樣式／7 主版。
- 清洗腳本本身的缺陷已抓到並修：首版用 `git ls-files` 逐檔開啟，PLAN 檔名為非 ASCII 被 git 輸出為跳脫字串，`open()` 拋 OSError 後被靜默跳過，導致 PLAN 的 9 處漏改。改用 `git -c core.quotepath=false ls-files` 後補齊。**這正是「靜默跳過」的典型案例，記於此供後續腳本引以為戒。**

### 待 Owner 決定

- **git 歷史仍含原文**：`git log -S` 可追至 Sprint 35 起的多個 commit，且承載檔就是 CHANGELOG 與 devlog 這類「歷史本身」。repo 無遠端故未外流，現在處理成本最低，但重寫歷史屬破壞性操作，不代決。

### 未做

- pre-commit 字串掃描未建。`.gitignore` 只擋檔案層級、擋不住字串層級，**同類洩漏會再發生**，列為後續。

## v0.91.0（2026-07-18，Sprint 96）自由散布替代文本（Phase 5 開源釋出首項，關 GAPS #1 子項）

### 新增

- [實作] `samples/paiban-xiaoji-ch1.md`：**自撰原創**散文《排版小記》第一章（2,210 漢字，本專案著作，可隨開源 repo 散布）。GAPS #1 原訂「開源釋出前備妥替代文本」的落地：真書《內在整理》為出版社版權物僅限本機，公開的端到端驗證自此有可散布的章節級來源。**不取公有領域古籍**（無法逐字校對來源，轉錄誤差會成為 repo 的長期錯誤），**不含真書任何文字**（紅線）。
- [實作] 素材設計原則＝刻意涵蓋既有排版路徑而非湊字數：全大寫縮寫逐字正立（`CMYK`／`RGB`／`PDF`）與含小寫西文整串旋轉（`11.5pt`／`12.08pt`）兩種縱中橫形態（Sprint 88 兩條規則）、行內強調的發言人標籤（Sprint 9 慣例）、引文段落、章名與小節標三層結構、左右頁鏡像與書眉頁碼（Sprint 22 側別）。
- [實作] `tests/test_public_sample.py`（6 測試）：素材存在與規模、繁中標點無破折號、md 匯入 41 段與樣式對映（且所用樣式屬模版）、排版 11 頁與禁則 0 違規與 `beyond` 0、縱中橫兩形態涵蓋釘死、匯出 PDF/X-1a 機械檢查 12 規則全過。素材改寫即測試失敗，強制同步 `samples/README.md`。

### 變更

- `samples/README.md` 新增本素材一列與重現指令，並列出預期輸出（11 頁、禁則 0 違規、preflight 12/12、最高 TAC 92%）與兩則預期字型警告（承 GAPS #12，非本素材缺陷）。順帶修掉樣張表中間一個把表格切成兩段的空行（`punct-squeeze` 那列原本脫離表格）。

### 驗證

- 基線 **884 passed / 0 failed**（878→884，+6）；typecheck EXIT_CODE=0（含 editor/*.py）。繁中標點 grep 無破折號。
- R2 判定：無新外部依賴、無新機制（走既有 `import-md` → `layout` → `export_pdf` → `check_pdfx` 管線），無需 spike。R1 證據＝本產品管線對本素材的端到端實測（A 級）。
- R5 真實素材驗收（本素材即公開素材，可完整重現）：CLI 全鏈實跑（`import-md` 41 段 → `render` 11 頁／禁則 0 違規／擠入 7 行撐開 0 行 → `export-pdf` 5 款字型子集嵌入且授權檢查零警告 → `preflight` 12/12、無置入影像、最高 TAC 92% 在上限內）。
- Gate 1 親 Read PNG 三頁目視：頁 1 章名大標與段落節奏正確、頁碼在左下（奇數＝左頁）；頁 3 三處西文串沿行軸旋轉；頁 8 發言標籤「師傅：」「我：」以粗體區隔，右下有書名書眉與書口右頁碼（偶數＝右頁）；頁 9 `CMYK` 與 `RGB` 逐字正立各佔一槽。

### 誠實範圍（honest-planning R3／R5／R7）

- **紅線不因本 Sprint 解除**：開源 repo 與公開樣張仍不得含真書文字或圖像，GAPS #1 只關「替代文本」子項。
- 本素材為**公開端到端驗證來源**，**不取代真書作為 §1 品質標竿**（標竿仍是真書的 A 級量測數據，量測數據本身非版權內容）；規模約真書第一章之半（11 頁 vs 22 頁）。
- 引文段落因內建字型缺全字庫正宋體而 fallback 思源宋體（承 GAPS #12），與內文字形無視覺區別。
- `samples/README.md` 的樣張表原就未涵蓋目錄下全部檔案，本 Sprint 只補本素材一列，未補全該表。

### 下個 Sprint 預定範圍

- 開源釋出文件其餘半邊：根目錄 README（專案定位、能力範圍、快速開始、限制）＋ LICENSE ＋ Known Limitations 公開承認（R7）。**授權條款的選擇屬 Owner 決定**，動工前需定案。

## v0.90.0（2026-07-18，Sprint 95）Phase 4 收尾判定（[Doc]，收尾轉 Phase 5）

### 收尾判定（honest review，無程式碼變更）

- **Phase 4 可自主項全數收口，Owner AskUserQuestion 定案收尾轉 Phase 5。** honest review 實查 §6 Phase 4 交付逐項收口（Sprint 82〜94）：
  - 印刷級輸出：PDF/X-1a 預設（Sprint 10）＋X-4 選項（`pdf_writer.PDFX_PROFILES` 形態表、CLI `--pdfx`）、CMYK 與單 K 文字（`styles.DEFAULT_TEXT_CMYK`）、出血 3mm（`BLEED_MM`／`page_boxes_pt`）、裁切標記（`primitives.crop_mark_lines`、CLI `--crop-marks`）、輸出色彩描述檔（`KNOWN_PRINT_CONDITIONS`＋X-4 強制嵌 ICC、CLI `--icc`）、字型子集化（`pdf_fonts`）與授權檢查（`font_license.embedding_permission`／`license_warnings`）。
  - 進階排版：禁則與約物擠壓（`engine.squeeze_punctuation`／`ParagraphStyle.punct_squeeze`）、目錄自動生成（`toc.assemble_book_with_toc`／`toc_items`）、圖文繞排（`engine.line_window`／`wrap.layout_with_wrap`）、注音 ruby（`placement.ruby_axis_and_top`／`Run.ruby`）、縱中橫精修（`engine._flush_latin`／`placement.TCY_SIZE_RATIO`）。
  - preflight 面板：`preflight.preflight_summary`／`image_rows`／`ink_rows`＋`editor/preflight_panel.PreflightDialog`＋`preflight_actions.PreflightActionsMixin`（Sprint 87 建立、Sprint 94 三分區）。
- §9 印前輸出硬條件逐條落地複查：盒框與單頁完稿、出血全出與裁切標記、全 CMYK 或 Grayscale 無殘留 RGB、OutputIntent 與印廠鎖定、總墨量 ≤ 320〜340%（Sprint 93）、字型 100% 嵌入子集化、直排硬條件、連續調影像 300〜350ppi（Sprint 91）、預設 X-1a 提供 X-4。**唯「點陣線稿 1200ppi」不驗**（線稿與連續調之別屬內容語意，機器不可判；#51 (a)）。
- Phase 4 機制級 DoD 達成：印刷級輸出鏈與進階排版皆有可執行實作與機械驗證，preflight 結果於 editor 面板三分區呈現。

### 驗證

- honest review 實查（非橡皮圖章）：Sprint 82〜94 各檔關鍵函式逐一 grep 皆真實定義（非空殼）；模版 `templates/neizai-zhengli.json` 命中 **18 段落／9 字元樣式＋7 主版（A〜G）＋3 色票**，不退步。
- 基線複驗：`pytest spikes tests` **878 passed / 0 failed**；typecheck EXIT_CODE=0（`py_compile` 含 editor/*.py）；離屏 smoke **C1〜C16 全過**。工作樹乾淨、Sprint 94 已提交。
- Phase 4 專項測試檔逐檔複跑：crop_marks 12／font_license 8／toc 14／ruby 9／tcy 16／wrap 26／punct_squeeze 35／image_ppi 31／cmyk_image 18／ink_coverage 40／preflight 9／pdf_writer 27，全綠。
- 剩項全數彙整 **GAPS #54** Phase 4 Known Limitations（甲 Owner hands-on 與實體打樣、乙 UI 延伸與後續片、丙 需外部條件或認證級工具、丁 Phase 5 既定），均不阻擋轉場。

### 誠實範圍（honest-planning R3／R5／R7）

- [Doc]：無程式碼變更；本 Sprint 僅 honest review＋文件收尾（PLAN §6 Phase 4 收尾判定小節＋§10 決議紀錄＋GAPS #54＋本條）。
- 誠實差異：Phase 4 多項功能的 R5 素材為自擬樣張而非真書（注音 ruby、標點擠壓、目錄自動生成、圖文繞排、裁切標記），各 Sprint 已明示不宣稱真書驗證；真書不採注音亦不採擠壓（§1 實測），標點擠壓對此書系實效有限（真書內文開啟擠壓 5351 字格僅 17 處命中，0.16%）。

### 待 Owner 真實素材驗收（R5，執行工程師不代行）

- **Phase 4 DoD 的「實檔送印刷廠打樣，色彩與直排品質人類驗收通過」未達成**：需實體打樣與人類校色，本 Sprint 不宣稱達成，轉為 Phase 5 第一件事。
- GAPS #19 真視窗批次（Phase 4 新增項＝preflight 面板三分區手感、紅與橘兩類顏色語意是否可辨）；連同 #10（Spike 1 對比圖）／#23（斷行逐行一致率）同批可做。

### 下個 Sprint 預定範圍

- Phase 5 首項待 Owner 定案。打樣校色依賴 Owner 與印刷廠；執行工程師可自主者為多書專案素材、效能量測、開源釋出文件（含 GAPS #1 自由散布替代文本備妥）。

## v0.89.0（2026-07-18，Sprint 94）preflight 面板三分區（關 GAPS #51 (d)、#53 (d)）

### 新增

- [實作] `cjkfolio/preflight.image_rows`／`ink_rows` 純函式：把兩份印廠條件報告攤成逐筆列 `(狀態, 項目, 明細)`，**CLI 與 editor 面板共用同一組列**（承 Sprint 87 `preflight_summary` 的 DRY 慣例）。CLI 每行即該列以「｜」與「：」串接，故兩處呈現不可能分歧；油墨總量的 `unchecked` 接於末尾、狀態列「未判讀」（不當作通過，與報告語意一致）。
- [實作] `editor/preflight_panel.PreflightDialog` 擴為三分區：**三行摘要**（PDF/X-1a 結論＋影像解析度＋油墨總量，後兩者標註「§9，非 X-1a 條款」）＋**三分頁明細表**（欄位統一為 狀態／項目／明細）＋未涵蓋誠實聲明。摘要與列的顏色語意區分兩類判定：X-1a 不過為紅（`#b00000`＝不合規），影像與墨量未達標為警示橘（`#b06000`＝印廠條件風險，不影響 X 合規），未判讀為灰。
- [實作] `editor/preflight_actions._run_preflight` 於同一份臨時 PDF 加跑 `check_image_resolution` 與 `check_ink_coverage`；statusBar 結論後附未達標的印廠條件摘要（達標時不贅字）。回傳值仍為 X-1a report（statusBar 與判定語意依 X-1a 不變），影像與墨量報告掛於面板 `dlg.image_report`／`dlg.ink_report`。

### 變更

- CLI `cmd_preflight` 的影像與墨量逐筆列改呼叫 `image_rows`／`ink_rows`（**輸出逐字不變**，既有 CLI 測試釘死），去除與面板的重複格式化。

### 驗證

- 基線 **878 passed / 0 failed**（871→878，+7：`image_rows` 空報告／狀態與明細／與 CLI 逐行相符 3＋`ink_rows` 空報告／狀態與明細／未判讀接尾／與 CLI 逐行相符 4）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C16 全過 0 退步。繁中標點 grep 無破折號。
- R2 判定：無新外部依賴、無新機制（判定邏輯全在 Sprint 91／93 已 pytest 驗的兩支檢查器，本 Sprint 只做呈現層與入口），無需 spike（先例 Sprint 87 面板本身）。R1 證據＝既有 `check_image_resolution`／`check_ink_coverage`（A 級，Sprint 91／93 已對真書送印稿實測）＋離屏面板實測（A 級）。
- smoke C16 擴為三分區：**無圖樣張**（case-divider）→ X-1a 12/12、影像區 0 列且摘要據實報「無置入影像」、墨量區列內文著色且皆在上限內；**低解析度樣張**（wrap-demo 置入 218ppi 佔位圖）→ 影像區 1 列判「不足」、摘要報不足、statusBar 附影像警示，而 **X-1a 仍 12/12**（印廠條件不影響合規結論）；**合成不過報告** → 三區各列「不過」「不足」「超標」與末尾「未判讀」。
- R5 真實素材驗收（真書為本機素材，紅線不入 repo；out/ 已於 .gitignore）：抽真書送印稿 `DeviceCMYK` 影像（xref 156，881×588，解碼 2,072,112 bytes 與 `881×588×4` 相符）→ 本產品 G-圖文版槽式置入 → **editor 離屏開面板**：X-1a 全數通過（12/12）、影像區「不足｜頁 1 obj 7 881×588px 繪 287.5×191.9pt ＝ 221ppi」、墨量區「達標｜著色 頁 1 k 0 0 0 0.92 最高 TAC 92%」與「超標｜影像 頁 1 obj 7 881×588px 最高 TAC 349%」、statusBar 三段皆列。
- Gate 4 獨立路徑對照：同一文件另走 CLI（`export-pdf` → `preflight`，另一份 PDF、另一次檢查）→ 逐筆列與面板**逐字相同**（221ppi、92%、349%），X-1a 亦 12/12；精確值 TAC **348.62745098%**、PPI **220.6407ppi**，其中 TAC 與 Sprint 93 記錄的 348.6275% 到小數四位一致（跨 Sprint 一致性複驗）。
- 誠實差異（GAPS #47 更新、#51 (d) 與 #53 (d) 關閉）：三分區皆為唯讀呈現，不提供修正建議或自動修復；仍只驗預設 X-1a（X-4 需 ICC 選取器，後續）；認證級 preflight 不涵蓋（承 #18）；三項檢查同步跑於單次匯出，文件大時凍視窗時間較 Sprint 87 更長（背景執行緒後續，承 #47 (d)）。

### 待 Owner 真實素材驗收

- 真視窗手感（三分頁切換、表格可讀性、摘要三行的視覺層次是否分得出「不合規」與「印廠條件風險」兩類）僅離屏驗過邏輯，未經人眼實看（GAPS #19 批次）。

## v0.88.0（2026-07-18，Sprint 93）油墨總量 TAC 檢核（§9 最後一項未實作硬條件）

### 新增

- [實作] `tools/measure_ink_coverage.py`：真書 179 頁送印稿墨量分佈量測（R1，A 級一手；只取聚合統計，不抽像素內容）。結果：**影像最大 TAC 357%**（逐列跳讀取樣值）、最大 TAC 逾 320% 者 9 張、逾 340% 者 7 張；**向量／文字著色 15 種，最高為手繪路徑富黑 `0.929 0.878 0.889 0.799`＝TAC 349.5%**（8 頁、91 次，後續算符皆為 path 非文字）；內文與其餘著色皆單 K（≤ 100%）。**即真實付印的書本身局部超出 §9 的 320〜340% 區間**，此為本 Sprint「只警告不擋流程」的一手依據。
- [實作] `cjkfolio/ink.py`（墨量領域層）：`MAX_TAC=320.0`（§9「總墨量 ≤ 320〜340%」取保守下限）＋`TAC_TOLERANCE=0.5`（報告顯示精度，同 `PPI_TOLERANCE` 理由）＋`tac_percent`（四分量→百分比，分量數與值域快速失敗）＋`meets_tac`（兩側共用判定，門檻語意不分歧）＋`image_max_tac`（**取最高單點墨量非平均**：一枚重墨像素即構成風險；`L` 走 `(255−最暗)/2.55` 上限 100%，`CMYK` 走 PIL ImageMath 四分量相加不飽和截斷）＋`InkUse`／`tac_warnings`。
- [實作] 產出側（匯出期）：`_Content.cmyk_used` 記錄實際發出的 DeviceCMYK 著色（`set_fill`／`stroke_rect`／`stroke_line` 三入口）、`_PdfPageWriter._image_inks` 記每張獨立影像最高墨量；`PdfResult.ink_uses`（依 TAC 降序）／`tac_warnings`（**不沉默、不擋流程**，同 Sprint 84 授權與 91 解析度慣例）；CLI `export-pdf` 列墨量行。
- [實作] 驗證側（Gate 4）：`preflight.check_ink_coverage`／`InkFinding`／`InkCoverageReport`／`ink_coverage_summary`，以 PyMuPDF 自**已寫出的 PDF** 反算兩類來源：內容流 `k`／`K` 算符＋影像 XObject 經 Pixmap 解碼為裝置色（故 `DeviceN` 單黑版與 `Indexed` 亦還原得出墨量），同色值與同影像跨頁去重；無法判讀者列 `unchecked` **不計為通過**。CLI `preflight` 加 `--max-tac` 與墨量分區。

### 變更

- **規則集分離**（承 Sprint 91 PPI 定案）：TAC 非 ISO 15930-1 條款而是紙張吸墨與乾燥的印廠條件，故**不入 `check_pdfx` 規則集**（維持 12 規則）：超墨量的 PDF 仍是合規 PDF/X，併入會使合規檔被誤判不合規。`NOT_COVERED` 的「油墨總量 TAC」條目改為指向 `check_ink_coverage`（誠實聲明不失效，測試釘死）。
- `cjkfolio/pdf_objects.py`（新檔）：低階 PDF 組裝（物件表／串流／xref／trailer）自 `pdf_writer` 抽出為 `PdfBuilder`。純機械搬移，**PDF 輸出位元組零變更**；動機為 `pdf_writer` 逾單檔 800 行上限，取此層為切點（不認識版面、字型或色彩，與排版寫出層無雙向依賴）。

### 驗證

- 基線 **871 passed / 0 failed**（835→871，+36：`tac_percent` 6＋`meets_tac` 5＋`image_max_tac` 5＋`tac_warnings` 4＋匯出整合 5＋`check_ink_coverage` 7〔含外來 PDF 非數值符記不崩潰〕＋Gate 4 交叉 1＋規則集分離與誠實聲明 2＋CLI 2）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C16 全過 0 退步。繁中標點 grep 無破折號。
- R1 證據＝真書 179 頁送印稿逐張墨量實測（A 級，工具入 repo 可重現）＋PLAN §9 條文（B 級）。R2 判定：無新外部依賴（復用既有 PIL 與 fitz），為既有能力擴充無需 spike（先例 Sprint 84／91）。R6 pre-mortem 三風險（取平均而漏判局部重墨／把 TAC 併入 X-1a 規則集使合規檔被誤判／著色正則誤抓非色彩運算元）分別以最大值語意測試、規則集分離測試、值域 `>1` 守門解消。
- R5 真實素材驗收（真書為本機素材，紅線不入 repo；out/ 已於 .gitignore）：
  - **驗證側對真書送印稿**：`check_ink_coverage` 直接檢查真書交印檔 → 94 筆判定、**超標 10 筆**（9 張影像＋富黑著色 349.5%）、0 筆未判讀、最高 359.6%；與 R1 量測工具（不同實作：逐列跳讀取樣＋整數化）的 9 張影像逐張對應，全掃較取樣多抓到峰值（357→359.6）為預期且方向正確。
  - **產出側到驗證側同值**：取真書 DeviceCMYK 影像（xref 156，881×588）置入本產品 → CLI 匯出報「油墨總量：影像 book.tif 最高 TAC 349% 超過 320%」且 PDF 照常寫出（不擋流程）→ 本產品檢查器讀該 PDF 得 **348.6275%**，與產出側自來源檔算得值、與檢查器讀真書原檔同一張影像所得值**三者到小數四位完全相同**（印證 Sprint 92 的分量逐位元組保真）；同檔 X-1a 仍 **12/12 全數通過**（證超墨量不影響 X 合規判定）。

## v0.87.0（2026-07-18，Sprint 92）彩色 CMYK 影像置入（關 GAPS #29 (c)）

### 新增

- [Spike] `spikes/spike18-cmyk-image/`：CMYK 影像自來源檔到 PDF 的分量往返驗證。`probe_cmyk_roundtrip.py` 三組樣本（合成極值圖、真書 DeviceCMYK 影像的 TIFF 與 JPEG 兩容器）逐位元組往返皆相等；並以 PyMuPDF 的 DCT 解碼為獨立基準，實測**真實世界的 Adobe YCCK CMYK JPEG 經 PIL 讀出為負片**（兩張真書樣本反相假設誤差 3.14／5.69，對墨量假設 221.45／193.14）。
- [實作] `tools/measure_cmyk_images.py`：真書 179 頁全書影像色彩空間形態量測（R1，A 級一手）。94 次置入結果：`DeviceN(1,DeviceCMYK,Black)` 67、**`DeviceCMYK` 16**（與 §1「16 張 CMYK」逐數吻合）、`Indexed(*,DeviceCMYK)` 11；8bpc 全數；**DeviceCMYK 影像無 `/Decode` 反相陣列**；帶 `/SMask` 14（真書交印檔本就非 PDF/X，本產品不比照）。
- [實作] 彩色 CMYK 影像置入（§9「全文 CMYK 或 Grayscale」）：
  - `cjkfolio/images.py`：`open_placed`（置入用開圖，依**來源檔自帶的色彩空間**分流：CMYK 保持 CMYK、其餘轉 8-bit 灰階）；`IMAGE_COLORSPACES` 對照表；`EmbeddedImage` 改依 PIL mode 決定 `/ColorSpace`（`L`→`/DeviceGray`、`CMYK`→`/DeviceCMYK`），不支援的 mode 快速失敗。
  - `cjkfolio/pdf_writer.py`：`PdfResult.image_colorspaces`（各色彩空間張數，供 CLI 據實回報）。
  - `cjkfolio/render.py`：`_draw_image` 於貼入前轉灰階（PNG 畫布為 "L"，彩色只在 PDF 完稿呈現，同 Sprint 15 起的灰階預覽慣例）。

### 變更

- **行為變更（誠實記錄）**：CMYK 來源檔過去一律被轉為灰階置入，自本版起保持 CMYK。既有文件若置入 CMYK 檔，輸出由 DeviceGray 變為 DeviceCMYK（§9 兩者皆合法；沉默降級使用者素材本非正確行為）。灰階與 RGB 來源輸出形態不變。
- **CMYK JPEG 拒收**：`open_placed` 對 CMYK JPEG 快速失敗並提示轉存 TIFF。理由見 spike18：判別依據只存在於函式庫層的容器細節（`adobe_transform`），猜錯的後果是整批送印成負片，而使用者規避成本只是另存一次檔。RGB JPEG 不受影響。
- CLI 訊息改為據實回報，不再寫死色彩空間：`export-pdf` 列各色彩空間張數（原寫死「DeviceGray 影像 XObject，灰階單 K」）；`render` 明示 PNG 預覽一律灰階畫布。
- `preflight.NOT_COVERED` 影像條目補列 `DeviceCMYK` 為合法色彩空間（規則數維持 12，判定邏輯未動）。
- `tools/_measure_common.py`：參考檔預設路徑兼探 `local/`（Windows 繁中環境含中文的命令列參數會被 mbcs 轉碼損壞，原預設路徑已不存在）。

### 驗證

- 基線 **835 passed / 0 failed**（817→835，+18：`open_placed` 分流 5＋CMYK JPEG 拒收與 RGB JPEG 不誤傷 2＋`EmbeddedImage` DeviceCMYK 形態與未反相 3＋端到端匯出／preflight／灰階不變 3＋PNG 預覽 1＋PPI 交互 1＋`image_colorspaces` 2＋內容流無 rg／RG 1）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C16 全過 0 退步。繁中標點 grep 無破折號。
- R1 證據：PLAN §9 條文（B 級）＋真書 179 頁全書影像形態實測（A 級，工具入 repo 可重現）＋輸出探針實測（A 級）。R2：spike18 條件性通過（TIFF 走、JPEG 拒收）。R6 pre-mortem 三風險（分量反相成負片／PNG 預覽掩蓋 PDF 缺陷／污染既有灰階輸出）分別以 spike 往返驗證、PDF 光柵化目視、灰階形態回歸測試解消。
- R5 真實素材驗收（真書為本機素材，紅線不入 repo；out/ 已於 .gitignore）：抽真書送印稿 DeviceCMYK 影像（881×588，原始四分量非經 RGB 轉換）→ 本產品置入 → CLI 匯出報「DeviceCMYK 1 張」→ **Gate 4** PyMuPDF 獨立解析：`/ColorSpace /DeviceCMYK`、8bpc、無 `/Decode`、無 `/SMask`、分量 **2,072,112 bytes 逐位元組相等且非反相**、內容流無 rg／RG、preflight **12/12**；PDF 光柵化親 Read 目視正相（非負片）；較小圖框變體（200×133.5pt）報「實效 PPI 皆達 §9 300ppi 下限」（槽式置入 221ppi 則正確列警告，證 Sprint 91 檢核對 CMYK 影像同樣運作）。
- 回歸：真書第一章 render 22 頁、禁則 0 違規、齊行擠入 10／撐開 2，與 Sprint 11／88／89／90／91 記錄逐項一致；灰階來源匯出仍為 `/DeviceGray`（測試釘死）。

### 誠實範圍（honest-planning R1／R2／R5）

- [實作]：影像層與 PDF 寫出層；[Spike]：spike18（條件性通過，結論即「JPEG 不做」）。
- **未涵蓋**（GAPS #52）：CMYK JPEG 不支援（拒收，非靜默降級）；不做 RGB→CMYK 換算（色彩轉換屬印廠 ICC 範疇）；無來源 ICC 感知（DeviceCMYK 為裝置相依，色彩正確性依 OutputIntent 與印廠條件）；PNG 預覽不顯示彩色；`DeviceN` 單黑版與 `Indexed` 等真書所用的最佳化形態不產生；圖片置入 UI 未接線（承 #29 (d)）。

## v0.86.0（2026-07-18，Sprint 91）影像解析度 PPI 檢核（關 GAPS #29 (b)）

### 新增

- [實作] 影像實效解析度檢核（§9「連續調影像 300〜350ppi」）。產出側與驗證側兩條獨立路徑（Gate 4 紀律）：
  - `cjkfolio/images.py`：常數 `PT_PER_INCH`／`MIN_IMAGE_PPI=300.0`／`PPI_TOLERANCE=0.5`；`effective_ppi`（實效 PPI＝像素數 ÷ 繪製英吋數，**影像自身 DPI metadata 不參與**）；`ImageResolution`（來源像素＋`fit_image_rect` 繪製尺寸，`ppi` 取兩軸較差者）；`meets_ppi`（兩側共用判定，門檻語意不分歧）；`resolution_warnings`。
  - `cjkfolio/pdf_writer.py`：`_PdfPageWriter._image` 逐次置入記錄解析度（同圖多次置入各記一筆），`PdfResult.image_resolutions`／`ppi_warnings`（不沉默、不擋流程，同 Sprint 84 授權檢查慣例）。
  - `cjkfolio/preflight.py`：`check_image_resolution`／`ImageResolutionReport`／`ImageFinding`／`image_resolution_summary`，以 PyMuPDF `get_image_info(xrefs=True)` 自已寫出 PDF 反算，不看產出側任何中間值。
  - `cjkfolio/cli.py`：`export-pdf` 列解析度警告行（零警告時明確報達標）；`preflight` 加 `--min-ppi` 與影像分區列印。

### 變更

- `preflight.NOT_COVERED` 的影像解析度條目改為指向獨立檢查器（PPI 非 ISO 15930-1 條款故不入 X-1a 規則集，**規則數維持 12**；併入會使合規 PDF 被誤判不合規，並混淆標準合規與印廠品質條件）。誠實聲明不失效，測試釘死。
- `samples/README.md`：註記 `wrap-photo.png`（幾何佔位圖 218ppi）匯出時會列解析度警告屬預期行為（示範檔非送印稿）。

### 修正

- 恰足門檻的送印圖被判「不足」卻顯示 300ppi 的假陽性：真書 p138 送印圖實效 299.999996ppi（PDF 座標浮點誤差 4e-6）。加 `PPI_TOLERANCE=0.5`（＝報告顯示精度，四捨五入至整數 ppi），使「顯示 300ppi 卻判不足」的自相矛盾不可能出現；四項邊界測試釘死。修正後真書複驗 85/94 達標。

### 驗證

- 基線 **817 passed / 0 failed**（789→817，+28：`effective_ppi` 4＋`ImageResolution.ppi` 2＋`resolution_warnings` 5＋浮點容差 4＋匯出整合 3＋獨立檢查 4＋交叉驗證與規則集守門 4＋CLI 2）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C16 全過 0 退步。繁中標點 grep 無破折號。
- R1 證據：PLAN §9 條文（B 級）＋**真書送印稿逐張實測（A 級）**＋輸出探針實測（A 級）。
- R5 真實素材驗收（真書《內在整理》為本機素材，紅線不入 repo；out/ 已於 .gitignore）：
  - 以本產品檢查器解析真書送印稿 179 頁 94 次影像置入：**中位數恰 300ppi、連續調照片零不足**（§9 門檻與真實印廠實務對齊的一手佐證）；9 筆不足全屬點陣圖示類（出版社標章 186×71px 三次置入 138／206／255ppi、版權頁 3×3〜16×16px 小圖示 141ppi）。
  - 抽真書 300ppi 印刷級照片（1757×2391px）經本產品 G-圖文版槽式置入：CLI 匯出報「實效 PPI 皆達 §9 300ppi 下限」、獨立 `check_image_resolution` 判 477ppi 達標、preflight **12/12**、render PNG 親 Read 目視（照片 contain 置中落 photo-slot、圖說直排在右）。
  - 反例（既有 samples/wrap-demo，218ppi）：匯出列警告、preflight 影像區判不足而 X-1a 仍 12/12 通過（證 PPI 不影響合規判定）。
- Gate 4（PyMuPDF 獨立解析，與產出側不同實作）：wrap-demo 手算 217.78ppi 與檢查器 218 吻合；測試釘死兩側同值（abs 0.5）。
- 回歸：真書第一章 render 22 頁、禁則 0 違規、齊行擠入 10／撐開 2，與 Sprint 11／88／89／90 記錄逐項一致。

### 誠實範圍（honest-planning R1／R2／R5）

- [實作]：純邏輯層＋檢查器，兩後端繪圖與 editor 畫布零改動。
- **未涵蓋**（GAPS #51）：§9「點陣線稿 1200ppi」不驗（線稿與連續調之別屬內容語意，機器不可判）；不重採樣（影像編修非排版，設計行為）；上限 350ppi 不檢；editor preflight 面板未列影像區（承 #47）；PNG 預覽無 PPI 語意故不檢。

## v0.85.0（2026-07-18，Sprint 90）標點擠壓（Phase 4 末項，關 GAPS #45）

### 新增

- [Spike] `spikes/spike17-mojikumi/`（新，GAPS #45 的 R2 退回條件）：
  - `probe_punct_ink.py`：以 ttb（直排 vert）塑形量測內建思源宋體 TC 全部 34 枚約物在字身框內的墨跡邊界。**括號類有明確空邊**（開括號墨在下半、上留白 0.52〜0.71；閉括號墨在上半、下留白 0.52〜0.71）；**句逗類墨跡置中**（上下留白各 0.33〜0.44、墨高僅 0.25〜0.29）故無單一可移除的半邊；`：；！？…` 墨高 0.63〜0.79 近乎滿框。
  - `probe_squeeze_pairs.py`：以上述墨跡邊界驗算 CLREQ 各條規則的擠壓後墨距。規則 2〜6 共 15 個字對全數 > 0（最小 `》」` 0.060 em）；**規則 1 三對皆碰墨（−0.07〜−0.12 em），與條文明文「繁體中文標點不適用此規則」獨立吻合**。
  - `premortem.md`／`report.md`：判定條件性通過（規則 2〜6 做；規則 1、規則 7／8、行首行尾字面調整不做）。
- [實作] 標點擠壓（§6 Phase 4「禁則／約物擠壓微調」；CLREQ WD-20150723 §3.1.6.1 規則 2〜6）：
  - `cjkfolio/engine.py`：新增 `SQUEEZE_STOPS`／`SQUEEZE_OPENERS`／`SQUEEZE_CLOSERS`（沿用既有禁則字集，不另立新集）＋`SQUEEZE_WIDTH=0.5`＋`_squeezes`（規則判定）＋`_squeezable`＋`squeeze_punctuation`（純函式：讓出半形者字身框 1→0.5、**字形位置不變**，故兩後端零改動）；`Cell.width` int→float；`ParagraphSpec.punct_squeeze`，`flow_pages` 於直排時套用。
  - `cjkfolio/styles.py`：`ParagraphStyle.punct_squeeze`（預設 False）入 `PARAGRAPH_STYLE_FIELDS`（繼承級聯／declared 序列化／StyleEditDialog 自動涵蓋，同 Sprint 76 color 慣例）；新增 `_bool` 轉換器（不用 Python 真值判定，`bool("False")` 為真會把使用者的關閉讀成開啟；無法辨識者 TemplateError 快速失敗）。
  - `cjkfolio/layout.py`：`ParagraphSpec` 帶入樣式的 `punct_squeeze`。
  - `samples/punct-squeeze.doc.json`＋`samples/punct-squeeze.template.json`（新，自擬內文；模版為內建模版加一款 `based_on` 子樣式，由 `save_template` 產出）。

### 驗證

- 基線 **789 passed / 0 failed**（754→789，+35：CLREQ 六條規則逐條 18＋純函式邊界 5＋流排整合 4＋樣式與模版層 7＋兩後端 parity 1）；typecheck EXIT=0（含 editor/*.py 與新 spike）；editor 離屏 smoke C1〜C16 全過 0 退步。繁中標點 grep 無破折號。
- R1 證據：W3C CLREQ WD-20150723 §3.1.6.1 條文原文（B 級；PLAN §10 2026-07-10 已定案標點擠壓以 CLREQ 為準）＋內建字型墨跡一手量測（A 級，工具入 repo 可重現）＋兩者交叉驗算。
- R5 真實素材驗收（**真書《內在整理》不採擠壓故自擬 samples/punct-squeeze，不宣稱真書驗證**，同 Sprint 86 注音 ruby 處置）：CLI render PNG 親 Read 目視（同一句排兩次，`」（`／`）「`／`」「` 空隙可見收窄，已擠壓段首欄多排 3 字＝30→33）；CLI export PDF → preflight **12/12**；模版另存重載 round-trip 保真（`declared=('note','punct_squeeze')`、其餘參數承基底）。
- Gate 4（PyMuPDF 獨立解析，與寫出層不同實作）：規則 4 `」（`／規則 2 `），`／規則 5 `（「`／規則 6 `」）` 擠壓後 Δy 比值 0.492、規則 4 `」「` 為 0.500（0.492 者係該行齊行實效字距 11.88 之半，非幾何偏差）；**規則 1 的 `，」` 比值 1.000 確認未擠壓**；兩段首字墨頂 y 皆為 121.645／97.485（縮排不受擠壓影響）。
- 回歸：真書第一章（本機素材，預設關閉）22 頁、禁則 0 違規、齊行擠入 10／撐開 2，與 Sprint 11／88／89 記錄逐項一致。另以真書內文開啟擠壓實測機制量級：5351 字格僅 17 處命中（省 8.5 格＝0.16%；形態 `。「`8／`，「`4／`」，`3／`」。`2，全屬規則 2、3），頁數仍 22、0 違規。

### 誠實範圍（honest-planning R1／R2／R5）

- [Spike]：spike17-mojikumi 為 GAPS #45 明列的 R2 退回條件，先量測後立規，不憑 CJK 排版通則寫表。
- [實作]：engine 純邏輯層＋樣式欄位，兩後端與 editor 畫布零改動（`Cell.width` 消費點 15 處全為算術累加）。
- GAPS #45 原判兩點經一手證據修正：規則來源不缺（CLREQ 條文為既定 B 級來源，真書無樣本只影響 R5 素材）；float 寬成本被高估（全鏈實為零改動）。
- 誠實差異（GAPS #50）：規則 1（條文明文繁體不適用＋量測碰墨）與規則 7／8 不實作；行首行尾字面調整不做（與斷行互為因果需迭代收斂）；只直排 body（橫排與文字框未接）；連續開括號情境前枚墨溢縮後字身框 0.44〜0.47 em（不碰墨但畫布字格 rect 與墨跡不再重合）；擠壓集不含【】（既有禁則字集本就未收）；三枚以上連續約物逐對套用。
- 實效誠實記錄：本功能對《內在整理》這類繁中置中標點書系命中率僅 0.16%，價值在採緊排慣例的其他書稿。

### 待 Owner 真實素材驗收

- 採緊排（aki）慣例的真實書稿以補 R5 真素材（#50 (h)）；真視窗手感與樣式面板新欄位（#19 批次）；印廠打樣色彩與直排品質（Phase 4 DoD，#18／#41）。

### 下個 Sprint 預定範圍

- Phase 4 §6 清單可自主項自此全數收口（PDF/X-1a 預設與 X-4 選項、CMYK 單 K、出血、裁切標記、輸出色彩描述檔、字型子集化與授權檢查、禁則／約物擠壓微調、目錄自動生成、圖文繞排、注音 ruby、縱中橫精修、preflight 面板）。次個 Sprint 依前三 Phase 慣例（#22／#33／#40）做 **Phase 4 收尾 Known Limitations 彙整**，逐項一手複驗後提請 Owner 定案轉 Phase 5。

## v0.84.0（2026-07-18，Sprint 89）圖文繞排（Phase 4 續項）

### 新增

- [實作] 圖文繞排（§6「圖文繞排」；直排內文避讓置入圖框，規則對表真書 179 頁全掃）：
  - `tools/measure_wrap_pages.py`（新）：對真書全書掃「同頁既有圖又有內文流」的半頁，量測圖 rect 與直排文字欄的幾何關係並分類（wrap-partial／column-block／disjoint），另列圖文間隙內的其他 span（判斷間隙成因）。輸出 assets/reference/wrap_measurements.json（本機不入 repo）。
  - `cjkfolio/engine.py`：新增 `Exclusion`（行槽區間＋字軸 pt 區間）與 `line_window` 純函式（排除區把可用字格切成前後兩段，取較長者＝同欄不跨圖續排）；`_break_one_line` 自 `_break_cells` 抽出（斷行與逐行流排共用）；`flow_pages` 加 `exclusions`／`page_offset`，改逐行取窗（行首推移或行尾縮短；行槽被圖佔滿則留白續下一槽，整頁無處排字快速失敗）。
  - `cjkfolio/wrap.py`（新）：`image_exclusion`（rect→排除區換算，含 wrap_margin 外擴與版心行槽夾取）、`page_exclusions`（逐頁；橫排頁略過）、`layout_with_wrap`（兩趟：Pass 1 取逐頁主版與方向、Pass 2 帶排除區重排；主版於重排後位移列入 violations 不沉默）。
  - `cjkfolio/document.py`：document@2 相容擴充 `PlacedImage.wrap`／`wrap_margin_mm`（預設 False／0＝既有輸出零變更；wrap 須搭 rect 圖框、margin 須 ≥0，序列化只寫非預設值）。
  - `cjkfolio/primitives.py`：`is_right_page`／`line_axis_x_pt` 自 `render.py` 下放（wrap 與兩後端同一行軸事實來源；render／pdf_writer re-export，既有呼叫端不變）。
  - `cjkfolio/render.py`／`pdf_writer.py`：`render_document`／`export_pdf` 改用 `layout_with_wrap`（帶 first_page，鏡像側別正確）。
  - `samples/wrap-demo.doc.json`＋`samples/wrap-photo.png`（新，自擬內文＋程式生成灰階佔位圖）。

### 驗證

- 基線 **754 passed / 0 failed**（728→754，+26：排除區幾何與 line_window 純函式 11＋document wrap 欄位 5＋flow_pages 排除區流排 4＋layout_with_wrap 端到端 5＋PDF 端到端 1）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C16 全過 0 退步。繁中標點 grep 無破折號。
- R1 一手證據（A 級，`python tools/measure_wrap_pages.py`）：真書 179 頁中「含圖且有內文流」11 個圖例＝wrap-partial 8、disjoint 3，形態一致＝圖矩形跨數欄、受影響欄內文避開圖的字軸範圍、同欄不跨圖續排（無「圖上下同欄皆有字」樣本）；受影響欄字軸起訖同頁一致（矩形排除區，非輪廓繞排）；圖文間隙 1〜3 字格不等且間隙內無圖說 span（純留白）＝作者自由放置，非排版規則。
- 模型對表（A 級）：真書 PDF 53 R 半頁圖 rect 經本產品換算得 slot 7〜12，與量測 6 欄行軸 193.25〜78.25 逐欄吻合（A-內文版 `354.25−23s`）；`wrap_margin` 一字格時可用字格 [0,15)，與真書該 6 欄末字落 cell 14 逐格吻合。
- R5 真實素材驗收（紅線自擬 samples/wrap-demo）：CLI render 兩頁 PNG 親 Read 目視（照片上方數欄提前收尾留一字格、照片區無字、其餘欄滿排至地腳、續頁接排、書頁 3＝左頁頁碼在左下）；CLI export PDF → preflight **12/12**；Gate 4 以量測真書的**同一支分類器**獨立解析本產品輸出，判定 `relation=wrap-partial`（與真書 8 樣本同形），受影響 5 欄末字墨底 274.63 對表模型推導 273.29（差＝字型 bearing），圖實際落點 y 333.65〜422.91 符合 contain 等比置中於宣告框（非缺陷）。
- 回歸：真書第一章（本機素材）重排 22 頁、禁則 0 違規、齊行擠入 10／撐開 2（與 Sprint 11／88 記錄一致）；`flow_pages` 逐行改寫以「有無 exclusions 參數輸出逐行相同」與既有 54 個 engine／layout 測試守門。

### 誠實範圍（honest-planning R1／R2／R5）

- [實作]：排版引擎層新增排除區機制＋文件模型相容擴充，兩後端共用既有繪製路徑。R2：無新外部依賴、無新機制（復用既有斷行與置入圖層），無需 spike（先例 Sprint 57 框串接、Sprint 85 兩趟分頁）。R1 證據＝真書 179 頁全掃（A 級一手，工具入 repo 可重現）＋輸出探針實測（A 級）。
- 行為變更（誠實記錄）：`render_document`／`export_pdf` 改走 `layout_with_wrap`，無 wrap 圖的文件仍為單趟流排、輸出零變更（測試釘死）；`is_right_page`／`line_axis_x_pt` 實作搬至 primitives，render／pdf_writer re-export 故既有 import 與行為不變。
- 誠實差異（GAPS #49）：v1 只直排 body（橫排頁不繞排）；矩形排除區非輪廓繞排；同欄不跨圖續排（圖落字軸中段時另一段留白）；節式多主版文件若因繞排位移致主版改變，列 violations 不自動再迭代；editor 畫布不顯示繞排（畫布本就不繪置入圖）；拖放置圖與繞排參數 UI 未接線。

### 待 Owner 真實素材驗收

- 真視窗手感與圖文繞排的版面美感判斷（#19 批次）；印廠打樣色彩與直排品質（Phase 4 DoD，#18／#41）。

### 下個 Sprint 預定範圍

- Phase 4 §6 清單本輪可自主項至此收口（PDF/X-1a／X-4、CMYK 與單 K、出血、裁切標記、輸出色彩描述檔、字型嵌入與授權檢查、目錄自動生成、圖文繞排、注音 ruby、縱中橫精修、preflight 面板皆 [實作]；禁則／約物擠壓微調依 GAPS #45 順延待 R2 spike＋R5 素材）。下個 Sprint 提請 Owner 定案：續攻 GAPS 乙類後續片（PPI 重採樣、彩色 CMYK 影像、X-4 ICC 選取器等），或收尾轉 Phase 5。

## v0.83.0（2026-07-18，Sprint 88）縱中橫精修（Phase 4 續項）

### 新增

- [實作] 縱中橫（tate-chu-yoko）排法精修（§6「縱中橫精修」；規則對表真書 179 頁全掃）：
  - `tools/measure_tcy_spans.py`（新）：以「span 所在 line 的書寫方向」分類真書全部西文 span（正立 vs 旋轉），交叉統計文字形態，並偵測「逐字正立」群組（同欄且縱向間距≈字距）。輸出 assets/reference/tcy_measurements.json（本機不入 repo）。
  - `cjkfolio/engine.py`：`_flush_ascii`→`_flush_latin`（改吃 offsets／start，逐字 cell 各得自身 span）。直排新增兩條正立規則：數字列標記 `\d{1,2}\.?`（「1.」）走單一 tcy 格；全大寫縮寫逐字正立各佔一槽（`IKEA` 4 格、`DM` 2 格）。`_is_run_char` 直排改收「拉丁字母（含重音，新增 `_is_latin_letter`）＋半形數字＋句點」：重音不再拆斷西文詞（`Hermès`／`Céline` 整詞一串旋轉），句點併入使小數（`2.0`）整串旋轉而非拆成三格。
  - `cjkfolio/placement.py`：`TCY_SIZE_RATIO` 0.92→**1.0**（真書內文級 11.5pt 的「1.」span size 亦為 11.5，不縮字；墨寬超 1em 時仍等比壓縮）；`cjkfolio/render.py` `_draw_tcy` 改用此常數（原硬寫 0.92，兩後端自此單一事實來源）。
  - `samples/tcy-forms.doc.json`（新，自擬）：四種形態示範樣張。

### 驗證

- 基線 **728 passed / 0 failed**（712→728，+16：tokenize 正立 4＋旋轉 4＋provenance 2＋橫排不受影響 1＋幾何純函式 2＋端到端 PDF／PNG 2＋雙位數回歸 1）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C16 全過 0 退步。繁中標點 grep 無破折號。
- R1 一手證據（A 級，`python tools/measure_tcy_spans.py`）：真書 179 頁 ASCII span 669（內文層 39），形態 × 排法**零反例**：正立＝單數字 9、列標記「1.」3、單一大寫字母 9；旋轉＝含小寫詞 16、四位數 1、小數 1。逐字正立群組實測 `DM` 2 槽、`IKEA` 4 槽，縱向間距 12.07≈§1 字距 12.08。不縮字證據＝「1.」span size 11.5＝內文級、墨寬 9.2 < 1em。
- R5 真實素材驗收（真書第一章本機素材，紅線不入 repo）：render 22 頁、禁則 0 違規（頁數與 Sprint 11 記錄一致）；export PDF preflight 12/12；Gate 4 以量測真書的**同一分類器**獨立解析本產品輸出，`Hermès`／`Chanel`／`Céline` 各為單一旋轉 span（2.95〜3.65 槽，對表真書 2.72〜3.20 槽，字型不同故墨高略長），先前重音會把詞拆成三段的情形消失。
- R5 自擬樣張（samples/tcy-forms）：輸出分類表與真書逐類同形（列標記正立 3、單字母正立 6、`IKEA` 4 槽＋`DM` 2 槽逐字正立、`podcast`／`Chanel`／`Céline` 旋轉、`1966`／`2.0` 旋轉）；preflight 12/12；PNG 親 Read 目視四種形態皆正確。逐字正立 step 實測 11.69 經同欄探針複驗＝該行齊行擠入後的行級字距（同欄 CJK 字步距亦 11.69），非 tcy 幾何偏差。

### 誠實範圍（honest-planning R1／R2／R5）

- [實作]：規則層與幾何常數修正，兩後端共用既有繪製路徑。R2：無新外部依賴、無新機制，無需 spike。R1 證據＝真書 179 頁全掃（A 級一手，工具入 repo 可重現）＋輸出探針實測（A 級）。
- 行為變更（誠實記錄）：既有測試兩處以大寫「AB」當旋轉拉丁樣本，改小寫「ab」以保留原意（逐字正立 span 由 test_tcy 覆蓋）；真書第一章齊行統計撐開 1→2 行（重音併串使 `Hermès` 由 4 格縮為 3 格，行內容量改變），超容忍仍 0、頁數仍 22。
- 誠實差異（GAPS #48）：全大寫夾數字（`MP3`／`A1`）走旋轉、單一小寫字母走旋轉（真書皆無樣本）；`IKEA` 這類逐字正立串可在字間斷行（真書樣本未跨行，未驗）；列標記上限 2 位數字帶點。

### 下個 Sprint 預定範圍

- Phase 4 續項：圖文繞排（§6 清單最後一項可自主者；約物擠壓微調待 R2 spike＋R5 素材，見 GAPS #45）。

## v0.82.0（2026-07-18，Sprint 87）preflight 面板（Phase 4 續項）

### 新增

- [實作] preflight 面板（§6「preflight 面板」；editor 內 PDF/X 機械檢查結果呈現，判定邏輯全在既有 check_pdfx）：
  - `cjkfolio/preflight.py`：新增純函式 `preflight_summary`（一行結論摘要，CLI 與 editor 面板共用）；`cjkfolio/cli.py` cmd_preflight 改用之（DRY，輸出不變）。
  - `editor/preflight_panel.py`：`PreflightDialog`（唯讀顯示結論摘要＋逐規則通過／不過表＋未涵蓋誠實聲明）。
  - `editor/preflight_actions.py`：`PreflightActionsMixin._run_preflight`（匯出當前文件為臨時 PDF/X-1a → check_pdfx → 開面板；匯出／檢查失敗以 statusBar 提示不 crash）。抽為 mixin 同 `StyleActionsMixin` 慣例，控管 app.py 行數。
  - `editor/app.py`：「檢查」選單「PDF/X-1a preflight…」入口；存 `self._doc_path`（置入圖 image_base_dir 基準）。

### 驗證

- 基線 **712 passed / 0 failed**（711→712，+1：preflight_summary 純函式通過／不過／空）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke **C1〜C16 全過**（C16 新＝真 export → check_pdfx 12/12 → 面板列 12 規則＋全數通過摘要＋未涵蓋聲明＋合成不過報告紅字摘要與「不過」列）。繁中標點 grep 無破折號。
- R5 真實素材驗收（自擬 samples/case-divider）：C16 以真實文件離屏走完「匯出臨時 PDF → 機械 preflight 12/12 → 面板呈現」全鏈；CLI preflight 重構後輸出複驗「結論：全數通過（12/12）」不變。

### 誠實範圍（honest-planning R1／R2／R5）

- [實作]：呈現層＋入口，判定邏輯復用已驗 check_pdfx。R2：無新外部依賴，無需新 spike。R1 證據＝既有 check_pdfx 12 規則（Sprint 10／28，A 級）＋離屏面板實測（A 級）。
- 誠實差異（GAPS #47）：v1 只驗預設 X-1a（X-4 需 ICC 選取器，後續）；面板唯讀不提供修正建議／自動修復（機械檢查器非修復器）；認證級 preflight 不涵蓋（承 #18）；同步匯出檢查短暫凍視窗（背景執行緒後續）；真視窗手感待 Owner（#19）。

### 下個 Sprint 預定範圍

- Phase 4 續項（依 §6 清單：圖文繞排、縱中橫精修；約物擠壓微調待 R2 spike＋R5 素材，見 GAPS #45）。

## v0.81.0（2026-07-18，Sprint 86）注音 ruby（Phase 4 續項）

### 新增

- [實作] 注音 ruby（§6「注音 ruby」；直排 mono-ruby 標注層，注音典型形態＝每漢字右側一組注音）：
  - `cjkfolio/placement.py`：新增純函式 `ruby_axis_and_top`（ruby 置 base 右側鄰欄＋垂直置中於字槽，兩後端共用幾何）＋常數 `RUBY_SIZE_RATIO=0.5`。
  - `cjkfolio/document.py`：`Run` 相容擴充 `ruby`（@2，非空字串、base text 須恰單一字守門＝v1 mono-ruby）；序列化帶 ruby 者不用 text 捷徑。
  - `cjkfolio/engine.py`：`Cell` 加 `ruby`；`cells_from_runs` 相容 2／3 元組、ruby 掛單字 cjk cell（不影響 width／斷行禁則）。`cjkfolio/layout.py` runs 傳 ruby。
  - `cjkfolio/render.py`／`cjkfolio/pdf_writer.py`：直排 body 於 cjk cell 後復用 `_draw_ttb_char`／`ttb_char_placements`（多字 ttb 串）繪 ruby，同字型同填色。ruby 為標注層，base 字流與整數槽寬模型不變。

### 驗證

- 基線 **711 passed / 0 failed**（702→711，+9：幾何純函式 2＋解析序列化驗證 4＋engine cell 1＋端到端 PDF／PNG 2）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C15 0 退步。繁中標點 grep 無破折號。
- R5 真實素材驗收（真書《內在整理》無注音故自擬 samples/ruby-annotation.doc.json，不宣稱真書驗證）：CLI export-pdf → 注音 30 字形進子集、0 缺字警告、preflight 12/12、base「整理生活」＋注音「ㄓㄥˇㄌㄧˇㄕㄥㄏㄨㄛˊ」PyMuPDF 皆可抽取；CLI render PNG 親 Read 目視：直排右起首欄四字注音繪於字右側垂直置中、其餘句子無 ruby（base 流不變）。

### 誠實範圍（honest-planning R1／R2／R5）

- [實作]：直排 mono-ruby 標注層，pytest 基線＋端到端 PDF／PNG 驗證。R2：無新外部依賴（復用既有塑形與繪字），無需新 spike。R1 證據＝W3C CLREQ 直排 ruby 置右（B 級）＋思源宋體注音字形實測（A 級）＋渲染幾何實測（A 級）。
- 誠實差異（GAPS #46）：v1 只 mono 單字 base（無 group／jukugo／拼音詞 ruby）；直排 only（無橫排 ruby）；無 ruby 驅動 base 間距調整（ruby 較長溢欄溝、緊行距可能與鄰欄重疊）；無注音符號組字精修（聲調位置依字型塑形）；ruby 同字型同填色。

### 下個 Sprint 預定範圍

- Phase 4 續項（依 §6 清單：圖文繞排、縱中橫精修、preflight 面板；約物擠壓微調待 R2 spike＋R5 素材，見 GAPS #45）。

## v0.80.0（2026-07-18，Sprint 85）目錄自動生成（Phase 4 續項）

### 新增

- [實作] 目錄自動生成（§6「目錄自動生成」；關 GAPS #31 (c) 目錄頁碼手填痛點）：
  - `cjkfolio/toc.py`：新增 `TocItem`／`assemble_book_with_toc`／`toc_items`。以兩趟穩定分頁自動計算列入章起始書頁號並填入目錄條目（無 fixpoint：目錄條目數＝列入章數為先驗定值，`page_no` 為掛段末行的非流排載體，回填不改分頁）。Pass 1 以 `page_no=None` 占位條目組裝＋流排定分頁、取各列入章章首版面頁號；Pass 2 回填書頁號（＝版面頁號＋first_page−1，同 render／pdf_writer）。
  - `cjkfolio/book.py`：book@1 相容擴充 `chapters[].toc_title`（列入標題）＋ `generate_toc` 章（`entry_style`／`master` 必填、`heading`／`heading_style` 選配）；新增 `TocSpec`、`ChapterRef` 擴充 `toc_title`／`toc_spec`；抽出 `_resolve_chapter`（與 auto-TOC 共用章載入與驗證）；`assemble_book` 遇自動目錄章快速失敗導向 toc 模組（純 path 書冊行為不變）。
  - CLI `assemble` 加 `--template`（含自動目錄章時必填，用以計算頁碼）／`--first-page`（須與最終 render／export 一致）；缺 `--template` 以 exit 2 明確報錯。

### 驗證

- 基線 **702 passed / 0 failed**（688→702，+14：解析與快速失敗 4＋頁碼計算與穩定性 4＋heading 選配／空目錄 3＋CLI 2＋端到端 1）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C15 0 退步。繁中標點 grep 無破折號。
- R5 真實素材驗收（紅線自擬 samples/book-auto-toc.json）：CLI `assemble --template` → 自動頁碼「第一章→2、個案速寫→4、客廳一景→5」；獨立 layout 對照各主版首頁 3/3 吻合（B-部扉 2／C-個案扉頁 4／G-圖文版 5）；export PDF → PyMuPDF 獨立讀目錄頁（頁 1）含數字 2/4/5＋部名首字＋preflight 12/12。組裝產出 JSON 親 Read 確認條目 `page_no`＝'2'／'4'／'5'、部名 `page_no`＝None。

### 誠實範圍（honest-planning R1／R2／R5／R7／R8）

- [實作]：auto-TOC 資料流，pytest 基線＋端到端 PDF 驗證。R2：無新外部依賴（純邏輯承 book@1／layout），無需新 spike（先例 Sprint 52 組裝）。R1 證據＝目錄頁型 A 級量測（Sprint 21/24）＋輸出探針實測（A 級）。
- 排序決策（R7／R8，登記 GAPS #45）：PLAN §6 清單本項前之「禁則／約物擠壓微調」依 R1／R2／R5 順延（真書 §1 實測句逗置中無半形擠壓〔#9〕、通用 opt-in 需 mojikumi 擠壓表 spike＋整數槽 vs float 寬模型評估、且缺採用 aki 的真實 R5 素材），改做本項先行，非沉默跳過。
- 誠實差異（GAPS #44）：目錄標題來自 manifest `toc_title` 顯式宣告（非章首自動抽取）；first_page 須與 render 手動對齊；條目樣式單一、無多層目錄縮排階層／摘要層；只列 path 章章首頁，章內小節不列入。

### 下個 Sprint 預定範圍

- Phase 4 續項（依 §6 清單：圖文繞排、注音 ruby、縱中橫精修、preflight 面板；約物擠壓微調待 R2 spike＋R5 素材備妥後專項，見 GAPS #45）。

## v0.79.0（2026-07-18，Sprint 84）字型嵌入授權檢查（Phase 4 續項）

### 新增

- [實作] 字型嵌入授權檢查（§6「字型嵌入子集化與授權檢查」＋GAPS #2；§9「匯出時做授權檢查提示」機器實作）：
  - `cjkfolio/font_license.py`：以 OpenType OS/2 `fsType` 嵌入權限位元為機器證據（A 級，讀實際字型位元組）。`embedding_permission` 判 Restricted License（bit 1）與 Bitmap Only（bit 9）不可嵌入輪廓、No Subsetting（bit 8）與本產品一律子集政策衝突（無 OS/2 表視為 fsType=0）。`license_warnings` 去重排序彙整不可嵌入／衝突字型警告，可嵌入者不列。
  - `cjkfolio/pdf_writer.py`：`export_pdf` 於收集 `writer.fonts_used` 後跑檢查，加 `PdfResult.license_warnings`（不沉默、不擋流程，同 font_warnings 慣例）。
  - CLI `export-pdf` 列印授權檢查行（零警告時明確報「皆可合法嵌入子集」）。

### 驗證

- 基線 **688 passed / 0 failed**（680→688，+8：純函式 embedding_permission 4＋license_warnings 3＋匯出整合 1）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C15 0 退步。繁中標點 grep 無破折號。
- R5 真實素材驗收：內建六款字型（思源宋／黑、辰宇、粉圓）fsType 皆＝0x0000（Installable）→ CLI 匯出零授權警告親驗；受限字型路徑以 fontTools 改 fsType 再存獨立驗證（Restricted 0x0002／Bitmap 0x0200 判不可嵌入、No-subset 0x0100 判政策衝突，3 警告排序正確），不散布任何商用字型（紅線）。

### 誠實範圍（honest-planning R1／R2／R3／R5）

- [實作]：fsType 機器嵌入權限檢查，pytest 基線驗＋內建字型實測＋受限字型 fixture 獨立驗證。
- R2：無新外部依賴（復用既有 fontTools TTFont），既有能力擴充無需新 spike。R1 證據＝OpenType OS/2 fsType 規格（B 級）＋fsType 實測（A 級）。
- 誠實差異（GAPS #43）：v1 只驗 fsType 機器位元＝fsType 允許嵌入不等於商用授權允許散布；名義授權分類（§8 表商用字型名稱比對）與匯出前攔阻選項未做，使用者用商用字型仍自負授權責任。

### 下個 Sprint 預定範圍

- Phase 4 續項（依 §6 清單：目錄自動生成、圖文繞排、注音 ruby、縱中橫精修、preflight 面板等，擇一 TDD）。

## v0.78.0（2026-07-18，Sprint 83）裁切標記（trim marks，Phase 4 續項）

### 新增

- [實作] 裁切標記（§9「裁切標記置於出血外 offset 約 3mm」；opt-in，擴充既有向量原件層）：
  - `cjkfolio/primitives.py`：新增 `crop_mark_lines` 純函式（8 條角標：4 角各 2 條延伸該角相交的裁切邊、內端距 trim＝出血〔落 BleedBox 邊、不侵入活區〕、外端達 MediaBox 邊；標記色與線寬由呼叫端傳入）。
  - `cjkfolio/pdf_writer.py`：常數 `MARK_LENGTH_MM=3.0`／`MARK_CMYK=(0,0,0,1)`（單 K registration，§9 全 CMYK、避高 TAC）／`MARK_WIDTH_PT=0.25`（hairline）。`page_boxes_pt` 回傳擴為 `(media, trim, bleed)`＋`mark_margin_mm` 參數：無標記（=0）時 BleedBox＝MediaBox（向後相容），有標記時 MediaBox 於 BleedBox 外各邊擴 `MARK_LENGTH_MM`、BleedBox 縮回 trim＋出血、TrimBox 恆置中。`_PdfPageWriter` 加 `origin_pt`（＝出血＋標記餘裕，取代內容座標偏移，外擴 MediaBox 不位移內文相對 trim）＋`_crop_marks`（復用 `stroke_line` 獨立 q…Q，不觸 preflight rg/RG）。`export_pdf` 加 `crop_marks` 參數（預設 False）＋`PdfResult.crop_marks`。
  - CLI `export-pdf` 加 `--crop-marks`。

### 驗證

- 基線 **680 passed / 0 failed**（668→680，+12：crop_mark_lines 純函式 3＋page_boxes 2＋匯出盒框／8 段／幾何 parity／內文不位移／preflight／CLI／預設無標記 7）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C15 0 退步。繁中標點 grep 無破折號。
- R5 真實素材驗收（紅線自擬 samples/chapter-opening，out/ 不入 repo）：CLI `export-pdf --crop-marks` → PyMuPDF 獨立解析（Gate 4）：MediaBox 160×222mm／BleedBox 154×216mm／TrimBox 148×210mm 巢狀正確、8 條 m/l/S 角標、單 K `0 0 0 1 K`、無 rg/RG、preflight **12/12**；渲染整張 MediaBox 為 PNG 親 Read：四角 L 形角標落於裁切邊延伸線、內端貼 BleedBox 邊外端達 MediaBox 邊、與裁切角留出血間隙（放大左上角複驗兩垂直交會線）。
- 回歸：預設無標記匯出 BleedBox＝MediaBox、內容流 **0** 角標線段，680 全綠。

### 誠實範圍（honest-planning R1／R2／R3／R5／R6）

- [實作]：裁切標記匯出，pytest 基線驗＋PyMuPDF 獨立解析＋PNG 親驗。
- R2：無新外部依賴（復用向量原件與盒框），為既有能力的幾何擴充，無需新 spike（先例 Sprint 14／15 向量原件）。R1 證據＝印前完稿慣例（B 級）＋輸出探針實測（A 級）。
- 誠實差異：§9「BleedBox＝MediaBox」僅無標記時成立；有標記時 BleedBox=trim+出血、MediaBox 外擴（正確印前設定）。

### 待 Owner 真實素材驗收（R5，執行工程師不代行）

- 認證級 preflight 與實檔送印刷廠打樣＝Phase 4 DoD（Owner hands-on，同 GAPS #11／#18／#41／#42）。

### 下個 Sprint 預定範圍

- Phase 4 續項（依 §6 清單：字型授權檢查、目錄自動生成、圖文繞排、注音 ruby、縱中橫精修、preflight 面板等，擇一 TDD）。

## v0.77.0（2026-07-18，Sprint 82）PDF/X-4:2010 匯出選項（Phase 4 首項）

### 新增

- [實作] PDF/X-4:2010 匯出選項（§9「X-4 選項」；擴充既有自寫 PDF/X-1a:2001 後端）：
  - `cjkfolio/pdf_writer.py`：新增 `PdfxProfile` 形態表 `PDFX_PROFILES`（x-1a／x-4：version／conformance／header／require_embedded_icc／allow_transparency／label）；`export_pdf` 加 `pdfx` 參數（預設 x-1a 向後相容）＋ `PdfResult.pdfx_label`。X-4 相對 X-1a＝header 升 1.6、Info 與 XMP `GTS_PDFXVersion=PDF/X-4` 且**無 `GTS_PDFXConformance`**、**強制嵌 DestOutputProfile ICC**（registry 免嵌不足，未給 `icc_profile` 快速失敗）；未知 pdfx 形態快速失敗。
  - `cjkfolio/pdfx_meta.py`：`xmp_packet` 的 `conformance` 支援 None（X-4 省略 GTS_PDFXConformance 兩鍵；X-1a 帶 conformance 者輸出位元不變）。
  - `cjkfolio/preflight.py`：`check_pdfx1a`→`check_pdfx(path, profile)`（相容包裝保留）；X-4 規則集依形態調整 header 1.6／GTS_PDFXVersion PDF/X-4／無 Conformance／OutputIntent 須嵌 ICC，且**排除 no-transparency**（X-4 允許實時透明）＝11 規則。
  - CLI `export-pdf` 與 `preflight` 加 `--pdfx x-1a|x-4`。

### 驗證

- 基線 **668 passed / 0 failed**（659→668，+9：X-4 匯出 6＋X-4 preflight 3）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C15 0 退步。繁中標點 grep 無破折號。
- R5 真實素材驗收（紅線自擬 samples/case-divider＋真 CMYK ICC，out/ 不入 repo）：CLI `export-pdf --pdfx x-4 --icc RSWOP.icm`（Windows 內建 218KB CMYK prtr 輸出描述檔）→ PyMuPDF 獨立解析（Gate 4）：header `%PDF-1.6`、Info `GTS_PDFXVersion PDF/X-4` 且**無** Conformance、DestOutputProfile 嵌入 218103 bytes（class prtr／space CMYK／N 4）、XMP 含 PDF/X-4 且無 Conformance；`preflight --pdfx x-4` **11/11 全過**。
- 回歸：預設 X-1a 複驗 header `%PDF-1.3`、registry 免嵌、`preflight` **12/12** 不退步。

### 誠實範圍（honest-planning R1／R2／R3／R5／R6）

- [實作]：X-4 匯出選項＋X-4 規則集 preflight，pytest 基線驗＋PyMuPDF 獨立解析＋真 CMYK ICC。
- R2：無新外部依賴（復用 PDF 寫出層＋fitz），X-4 為已實作 X-1a 的格式變體，無需新 spike（先例 Sprint 10 直接做 X-1a）。R1 證據＝ISO 15930-7:2010 規格（B 級）＋輸出探針實測（A 級）。
- 誠實差異：X-4 允許的透明／圖層（OCG）／ICC-based 色彩，本產品全 device CMYK/gray 內容不產生（X-4 匯出＝X-1a 內容的形態變體，非缺陷＝§9 全 CMYK 鐵律）。

### 待 Owner 真實素材驗收（R5，執行工程師不代行）

- 認證級 preflight（Acrobat／印廠）與實檔送印刷廠打樣＝Phase 4 DoD（Owner hands-on，同 GAPS #11／#18／#41）；內建自由散布 CMYK ICC 未備，使用者自備 `--icc`。

### 下個 Sprint 預定範圍

- Phase 4 續項（依 §6 清單：裁切標記、CMYK 深化、目錄自動生成、圖文繞排、注音 ruby、縱中橫精修、preflight 面板等，擇一 TDD）。

## v0.76.0（2026-07-18，Sprint 81）Phase 3 收尾判定（[Doc]，收尾轉 Phase 4）

### 收尾判定（honest review，無程式碼變更）

- **Phase 3 可自主項全數收口，Owner AskUserQuestion 定案收尾轉 Phase 4。** honest review 實查 §6 Phase 3 交付逐項收口（Sprint 67〜80）：
  - 樣式修改核心（style_editing.set_paragraph_style／set_character_style）＋繼承（styles._resolve_styles 載入期扁平化＋編輯期級聯）＋新增／刪除（add_／remove_）＋改名（rename_ 模版與文件雙層 _commit_pair 單一 undo）＋另存（template_to_dict／save_template round-trip 相等）。
  - docx 匯入（docx_import.import_docx，stdlib OOXML 三層標題鏈）＋AI 輔助指派（ai_style.suggest_styles／apply_suggestions）＋參考萃取（reference_extract.scan_pdf／map_font／propose_styles／extract_draft）＋色票管理（ColorSwatch／resolve_text_cmyk 兩後端同源）＋模版庫（template_library＋session.apply_template／merge_draft）。
  - UI：樣式管理（StyleEditDialog）＋改名入口＋色票面板＋AI 指派校正表格（AssignReviewDialog）＋模版庫面板（library_panel）。
- Phase 3 機制級 DoD 達成：「從零建立一套新書樣式模版」資料面完備（新增／繼承／修改／刪除／改名／另存）＋UI，「套用成書」走 session.apply_template＋book@1 組裝，「txt／md／docx 匯入經 AI 指派＋人工校正」全鏈可跑。

### 驗證

- honest review 實查（非橡皮圖章）：模版 templates/neizai-zhengli.json 命中 **18 段落／9 字元樣式＋7 主版（A〜G）＋3 色票**（結構化 cmyk）；Sprint 67〜80 各檔關鍵函式 grep 皆真實定義（非空殼）。
- 基線複驗：`pytest spikes tests` **659 passed / 0 failed**；typecheck EXIT=0（`py_compile` 含 editor/*.py）；離屏 smoke **C1〜C15 全過**。工作樹乾淨、Sprint 80 已提交。
- 剩項全數彙整 **GAPS #40** Phase 3 Known Limitations（甲 Owner hands-on sign-off、乙 UI 延伸與後續片、丙 後續 Phase 既定），均不阻擋轉場。

### 誠實範圍（honest-planning R3／R5／R7）

- [Doc]：無程式碼變更；本 Sprint 僅 honest review＋文件收尾（PLAN §6 Phase 3 收尾判定小節＋§10 決議紀錄＋GAPS #40＋本條）。
- 誠實差異：docx 匯入無真 Word（中文）／LibreOffice 一手實測（手工 OOXML＋python-docx 產生器路徑驗，#35 (a)）；AI 指派真 endpoint 於 CLI 已實測（Sprint 73），editor 內真視窗連線屬 Owner hands-on。

### 待 Owner 真實素材驗收（R5，執行工程師不代行）

- GAPS #19 真視窗批次（Phase 3 新增 UI 手感：樣式管理／色票面板／AI 指派校正表格／模版庫面板／docx 真檔匯入；說明選單十項）；連同 #10（Spike 1 對比圖）／#23（斷行逐行一致率）同批可做。

### 下個 Sprint 預定範圍

- Phase 4 開工首項＝PDF/X-4 匯出選項（擴充既有自寫 PDF/X-1a:2001 後端，§9「X-4 選項」）。

## v0.75.0（2026-07-17，Sprint 80）模版庫面板 UI（清單套用＋草稿併入入口）

### 新增

- [實作]／[Shell] 模版庫面板（§4.3「模版庫」UI 半邊，關 GAPS #39 (a)；核心 Sprint 77 已入基線）：
  - 新檔 editor/library_panel.py（77 行）`TemplateLibraryDialog`：list_templates 清單（壞檔標註 error 且套用守門警示）、「套用選取模版」＝session.apply_template 一步 undo（文件引用缺樣式擋下、錯誤留內嵌警示列）。
  - app 新「模版」選單：「模版庫（套用整份模版）…」（v1 目錄＝內建 templates/）＋「併入萃取草稿…」（session.merge_draft 一步 undo，added／skipped 列 statusBar）。

### 驗證

- 核心基線 **659 passed / 0 failed**（UI 層不變 0 退步）；typecheck EXIT=0（含 editor/*.py）；smoke 擴 **C15**（草稿併入 2 樣式列報 → 另存演進模版 → 庫清單 2 項與壞檔套用守門 → 套用整份模版 → 一步 undo 回原），C1〜C15 全過。app.py 774／library_panel.py 77 行守 800。繁中標點 grep 無破折號。
- R5＝smoke C15 即席全回路（真視窗手感 Owner-hands-on 不代行）。

### 誠實範圍（honest-planning R3／R7）

- [實作]：庫對話框＋套用＋併入入口（離屏全回路）。
- [Shell]／待 Owner：真視窗選單與對話框手感（GAPS #19 批次）。
- 未做：使用者模版庫目錄慣例（#39 (b)）、併入「覆蓋」選項（#39 (c)）、樣式繼承視覺化。
- **Phase 3 可自主項至此全數收口**；收尾判定待 Owner（先例 Sprint 39／66 AskUserQuestion 定案）。

### 待 Owner 真實素材驗收（R5）

- 「模版」選單試模版庫套用與草稿併入；連同 v0.66.0 起 hands-on 批次（說明選單九項）。

### 下個 Sprint 預定範圍

- 待 Owner：Phase 3 收尾判定（轉 Phase 4 或補 Phase 3 細項）；hands-on 批次（GAPS #19／#10／#23）。

## v0.74.0（2026-07-17，Sprint 79）AI 指派校正 UI（逐段確認與批次改派，單一 undo 步）

### 新增

- [實作] 多段批次改派核心（入 pytest 基線；關 GAPS #24「多段單一 undo API」子項＝AI 校正與跨段套段落樣式共同地基）：
  - editing.`change_paragraph_styles`（多段純文件層：逐段委派單段版、全等值 no-op、越界／空名快速失敗）。
  - session.`apply_para_styles`（批次入**單一 undo 步**＝復用 _commit_pair；未知樣式名重排 KeyError 快速失敗）。
- [實作]／[Shell] AI 指派校正 UI（§4.4「逐段確認與批次改派」介面承諾，關 #36 (a)(b)）：
  - 新檔 editor/ai_assign.py（104 行）`AssignReviewDialog`：逐段表格（採用勾選〔預設勾「有建議且異於現行」〕／段首文字／現行樣式／建議下拉〔候選集＝模版實際段落樣式〕）＋全部採用／不採＋批次降級警告列不沉默；確定只回報勾選且異於現行載荷。
  - app `_run_ai_assign`（suggest 注入離屏可驗；真呼叫 load_ai_config＋suggest_styles，未設定顯示訊息不擋流程）＋「樣式」選單「AI 樣式指派…」＋說明實測步驟九項。

### 驗證

- 核心基線 **659 passed / 0 failed**（655→659，+4，新檔 tests/test_edit_multi_para_style.py）；typecheck EXIT=0（含 editor/*.py）；smoke 擴 **C14**（注入建議 2 段→預設勾選正確→人工否決＋改建議→批次改派 1 段單步整批回退→空載荷 no-op→警告顯示），C1〜C14 全過。app.py 719／ai_assign.py 104 行守 800。繁中標點 grep 無破折號。
- R5＝smoke C14 即席全回路＋核心 4 測試；UI 與 CLI 同 suggest_styles 核心（私有 endpoint 已於 Sprint 73 實測）。

### 誠實範圍（honest-planning R3／R7）

- [實作]：批次改派核心＋校正對話框＋入口（離屏全回路）。
- [Shell]／待 Owner：真視窗表格手感＋真 endpoint 連線操作（GAPS #19 批次）。
- 未做：背景執行緒（v1 同步呼叫凍視窗誠實記錄）、md／docx 後的 AI 補充建議（#36 (c)）。

### 待 Owner 真實素材驗收（R5）

- 說明選單第 8 項：設定 AI 三欄位後跑「AI 樣式指派…」，逐段勾選採用，確認一步 Ctrl+Z 整批回退。

### 下個 Sprint 預定範圍

- 候選：模版庫面板 UI（#39 (a)）、樣式繼承視覺化、Phase 3 收尾判定。

## v0.73.0（2026-07-17，Sprint 78）樣式 UI 補全批次（改名入口＋色票面板）

### 新增

- [實作]／[Shell] 樣式 UI 補全（關 GAPS #34 改名 UI 子項＋#38 (a)；核心 Sprint 75〜76 已入基線，本版為 UI 接線）：
  - editor/style_panel.py：`SwatchEditDialog`（cmyk 逗號分隔／hex／note，只送有改動欄位、錯誤留內嵌警示列；值驗證一律由核心 COLOR_FIELDS 執行）＋StylePanel 色票清單（標籤帶 cmyk 值、雙擊改值＝全書變色）＋select_style／selected_swatch／select_swatch（程式化選取）。
  - 「樣式」選單五項→九項：重新命名段落／字元樣式（Sprint 75 成對單一 undo）、新增色票（K100 起始，雙擊改值）、刪除選取色票（引用守門）。
  - 行數紀律：app.py 樣式選單域回呼抽 editor/style_actions.py mixin（166 行，搬移行為不變；app.py 741→673）。說明選單實測步驟七→八項。

### 驗證

- 核心基線 **655 passed / 0 failed**（UI 層不變 0 退步）；typecheck EXIT=0（含 editor/*.py）；smoke 擴 **C13**（選單改名全書同步〔面板＋文件段落參照＋衝突守門〕＋色票新增→樣式掛色→雙擊改值 0.4 全書變色〔越界留警示不污染〕→引用中刪除守門→解引用刪除＋面板同步＋六步 undo 回原），C1〜C13 全過。app.py 673／style_panel.py 256／style_actions.py 166 行守 800。繁中標點 grep 無破折號。
- R5＝smoke C13 即席全回路（真視窗對話框與選單手感 Owner-hands-on 不代行，承 Sprint 71 慣例）。

### 誠實範圍（honest-planning R3／R7）

- [實作]：改名入口＋色票面板（離屏可驗全回路）。
- [Shell]／待 Owner：真視窗手感（GAPS #19 批次）。
- 未做：模版庫面板 UI（#39 (a)）、AI 指派 editor 入口與校正 UI（#36）、樣式繼承視覺化。

### 待 Owner 真實素材驗收（R5）

- 說明選單八項實測步驟（新增第 7 項：雙擊色票改值看全書變色、選單新增／刪除色票）。

### 下個 Sprint 預定範圍

- 候選：AI 指派 editor 入口與逐段校正 UI（#36 (a)(b)）、模版庫面板（#39 (a)）。

## v0.72.0（2026-07-17，Sprint 77）模版庫管理面資料層（清單＋草稿一鍵併入＋套用模版）

### 新增

- [實作] 模版庫管理面資料層（§4.3「模版庫」／§6 Phase 3「書系模版匯入」半邊；GAPS #37 (b) 一鍵併入關閉、新 #39）：
  - 新檔 cjkfolio/template_library.py（82 行）：`list_templates`（目錄掃 *.json 淺讀 schema 與 name 成清單、檔名排序；壞 JSON／非模版 schema 列 entry.error 不沉默不擋清單）＋`merge_draft_styles`（reference_extract 草稿逐條 add_paragraph_style；同名跳過列 skipped 不覆蓋＝既有定義優先、全跳過 no-op、缺鍵 TemplateError）。
  - session：`apply_template`（整模版替換入統一 undo＝§4.3「套用到新書」；文件引用缺樣式重排 KeyError 快速失敗）＋`merge_draft`（併入入 undo，回 (result, report)）。
  - CLI `merge-styles`（extract-styles → merge-styles 全鏈：草稿到可用模版一鍵，added／skipped 列報不沉默）。

### 驗證

- 核心基線 **655 passed / 0 failed**（642→655，+13，新檔 tests/test_template_library.py：清單 3／併入 5／session 3／CLI 2）；typecheck EXIT=0（含 editor/*.py）；smoke C1〜C12 全過 0 退步。template_library.py 82／session.py 379／cli.py 333 行守 800。繁中標點 grep 無破折號。
- 真實素材驗收（R5，真書 PDF 本機紅線、產物 out/ 不入 repo）：真書 179 頁 extract-styles 20 提案 → merge-styles 全數併入內建模版（含衝突序號 -2 命名者）→ list_templates 清單（merged 讀出模版名、draft.json 列 schema 錯誤不沉默）→ 掛「內文候選-宋11.5pt」（57,536 字＝§1 交叉命中）自擬文件 render 親 Read（與既有內文同模版共存、0 違規）＋export preflight 12/12。

### 誠實範圍（honest-planning R3／R7，GAPS #39）

- [實作]：庫清單／草稿併入／套用模版資料層＋CLI 全鏈。
- 未做：庫面板 UI（清單／開啟／套用入口）、使用者模版目錄慣例、併入「覆蓋」選項、樣式級選擇性匯入。

### 待 Owner 真實素材驗收（R5）

- 以自己的參考 PDF 走 extract-styles → merge-styles 看併入品質；其餘同 v0.66.0 hands-on 批次。

### 下個 Sprint 預定範圍

- 候選：editor UI 批次（庫面板／色票面板／改名入口／AI 指派入口）、AI 指派校正介面（#36 (a)）。

## v0.71.0（2026-07-17，Sprint 76）色票管理核心（結構化色票＋樣式文字色引用＋雙後端同源）

### 新增

- [實作] 色票管理資料面＋渲染鏈（§4.3／§6 Phase 3「色票管理」，GAPS #37 (e) 關閉、新 #38）：
  - styles.py：`ColorSwatch`（名稱→cmyk 印刷值〔4 元素 0〜1〕＋hex 螢幕參考〔#RRGGBB〕＋note；舊形態 hex 字串照載為純記錄）＋段落／字元樣式選配 `color` 欄位（入欄位表＝繼承級聯／declared 序列化／樣式編輯對話框自動涵蓋）＋`check_color_ref`（引用未知或無 cmyk 色票 TemplateError，載入編輯雙層守門）＋`resolve_text_cmyk`（文字填色單一事實來源：字元 > 段落 > 預設暖黑 K92）＋色票序列化 round-trip（舊字串形另存單向升級結構化）。
  - style_editing.py：`add_color`／`set_color`／`remove_color`（衝突／空名／全空值／越界拒、等值 no-op、被樣式引用不可刪）；session：`update_color`／`add_color`／`remove_color` 入統一 undo（「改色票值即全書變色」）。
  - 兩後端文字色同源：pdf_writer `_Content.set_fill`（BT 內 `k` 算符切色，與現行同值不發＝無 color 文件內容流形態不變）五寫出點全接；render `_ink_gray`（灰值 255×(1−k) 只取 k）五繪製路徑全接。
  - 內建模版 colors 結構化：暖黑（cmyk 0,0,0,0.92＋hex #231f20＝§1 量測）、紙白、虛線灰（K57＝p003 Sprint 15），皆帶出處 note。
- 行數紀律分檔：pdf_writer 逾 800 行，字型子集嵌入抽 `cjkfolio/pdf_fonts.py`（`EmbeddedFont`＋`subset_tag` 公名；pdf_writer 812→672，行為不變，test import 站點同步）。

### 行為變更（誠實記錄）

- PNG 預設文字自純黑 0 改 K92 灰值 20（兩後端同一色彩解析鏈；視覺近黑，墨跡斷言門檻不受影響）。

### 驗證

- 核心基線 **642 passed / 0 failed**（617→642，+25，新檔 tests/test_colors.py：載入 7／解析 1／序列化 2／樣式 color 編輯 4／色票 CRUD 3／session 2／兩後端 3＋test_styles 色票斷言同步）；typecheck EXIT=0（含 editor/*.py）；smoke C1〜C12 全過 0 退步。styles.py 673／pdf_writer.py 672／pdf_fonts.py 159 行守 800。繁中標點 grep 無破折號。
- Gate 4 雙路：PDF 內容流算符逐值（0.92／0.57／0.3 `k`）＋PyMuPDF texttrace 獨立回報三種填色暗序；PNG 帶內最深墨值＝20（K92）／110（K57）精確。
- 真實素材驗收（R5，自擬色票示範 out/color-demo/）：session 全鏈（add_color 淡墨 K57＋點灰 K30 → add_para_style 註記-淡墨 → update_char_style 強調掛點灰）→ render＋export＋preflight 12/12；PNG 親 Read（段落色全段 K57、run 覆寫「安放選擇」K30、文字框同走色票、頁碼預設近黑）；update_color K57→K30 全書變色重渲染親 Read（僅引用者變淡）、undo 回 K57。

### 誠實範圍（honest-planning R3／R7，GAPS #38）

- [實作]：色票資料面＋樣式引用＋雙後端＋session undo。§6 Phase 3「色票管理」核心落地。
- 未做：色票管理面板 UI（清單／新增／改值入口；樣式對話框 color 欄位已自動出現）、主版 spec cmyk 引用色票、色票改名、PNG c/m/y 分量表達（灰階預覽限制）。

### 待 Owner 真實素材驗收（R5）

- 同 v0.66.0 hands-on 批次（本 Sprint 為核心層；樣式編輯對話框多 color 欄位可順手試）。

### 下個 Sprint 預定範圍

- 候選：模版庫管理面（清單／匯入／萃取草稿一鍵併入）、改名與 AI 指派的 editor UI 批次、色票面板。

## v0.70.0（2026-07-17，Sprint 75）樣式改名核心（模版＋文件雙層同步，成對單一 undo 步）

### 新增

- [實作] 樣式改名資料面（§4.3「可修改」改名半邊，關 GAPS #34 (a) 改名子項）：
  - 模版層 cjkfolio/style_editing.py：`rename_paragraph_style`／`rename_character_style`（樣式鍵**原位**改名＋樣式物件自身 name＋子樣式 based_on 跟隨；段落名同步 md_mapping、字元名同步 md_inline_mapping＋主版 footer 元素樣式＋toc.page_no_style；未知 KeyError、空名／衝突 TemplateError、同名 no-op）。
  - 文件層 cjkfolio/editing.py：`rename_paragraph_style_refs`（段落＋文字框）／`rename_char_style_refs`（run 級；正規化不變式自然保持；無參照回原物件）。
  - session：`rename_para_style`／`rename_char_style` 走新 `_commit_pair`＝文件與模版**成對單一 undo 步**（先重排快速失敗再入歷史、雙 no-op 不入 undo；快照三元組 Sprint 67 已備，快照層零變更）。

### 驗證

- 核心基線 **617 passed / 0 failed**（602→617，+15，新檔 tests/test_style_rename.py：模版層 7＋文件層 4＋session 4）；typecheck EXIT=0（含 editor/*.py）；smoke C1〜C12 全過 0 退步。style_editing.py 265／editing.py 609／session.py 342 行守 800。繁中標點 grep 無破折號。
- 真實素材驗收（R5，committed 樣張 chapter-opening＋內建模版全鏈探針）：session 雙改名（內文段落＋頁碼字元）→ save_template 另存 → load_template 重載（**交叉引用驗證**：footer／toc 指到缺樣式即 TemplateError，重載成功＝同步完整）→ 重排幾何逐行等價（頁數 2→2、樣式名還原後完全相等）→ undo 兩步回原（模版與文件同步）。

### 誠實範圍（honest-planning R3／R7）

- [實作]：改名資料面（模版＋文件＋session）。§4.3 樣式管理（新增／修改／繼承／刪除／改名／另存）資料面至此全備。
- 未做：改名 UI（面板重新命名入口，承 GAPS #19 真視窗批次模式）。

### 待 Owner 真實素材驗收（R5）

- 同 v0.66.0 hands-on 批次（本 Sprint 為核心層，無新 UI 面）。

### 下個 Sprint 預定範圍

- 候選：模版庫管理面（清單／匯入／萃取草稿一鍵併入）、色票管理、改名與 AI 指派的 editor UI 批次。

## v0.69.0（2026-07-17，Sprint 74）從參考 PDF 萃取起始樣式（§4.3 從參考萃取產品化）

### 新增

- [實作] cjkfolio/reference_extract.py（173 行，§1 分析流程產品化；版面幾何不從掃描推測＝§4.4 分工鐵律）：
  - `scan_pdf`：(font, size) 分布＋用色統計（只聚合，不留 PDF 文句＝版權紅線）。
  - `map_font`：§8 可散布字型組對映（仿宋先於宋判、字重 W3〜W9／Bold／Medium／Heavy 就近收斂家族可用集、未識別暫映思源宋體 TC 警告不沉默）。
  - `propose_styles`：主力＝內文候選、≥1.1 倍標題候選、≤0.85 小字候選、其餘同級候選；名稱衝突加序號；門檻／上限濾除列 skipped 不沉默。
  - `extract_draft`：草稿 paragraph_styles 片段與模版欄位五欄同形（font_family／font_weight／size_pt／source_font／note），可逐條經樣式管理 UI 新增。
- CLI `extract-styles`（--min-chars 預設 60／--max-styles 預設 20，列印提案表＋濾除數＋用色統計）。

### 驗證

- 核心基線 **602 passed / 0 failed**（580→602，+22，新檔 tests/test_reference_extract.py：map_font 參數化 12＋提案純邏輯 6＋fitz 造 PDF 掃描整合 3〔Gate 4 獨立路徑：fitz 寫、本模組掃〕＋CLI 1）；typecheck EXIT=0（含 editor/*.py）；smoke C1〜C12 全過 0 退步。reference_extract.py 173 行、cli.py 305 行守 800。繁中標點 grep 無破折號。
- 真實素材驗收（R5，真書 PDF 本機紅線、草稿 out/ 不入 repo）：179 頁 → 20 提案＋30 skipped，與歷史**獨立工具**量測逐字吻合五處（內文 DFMingStd-W3 11.5pt **57,536 字**＝§1 原始數字、PepitaMT 9pt **153 頁**＝Sprint 36、NotoSans 17.9pt **42 頁**＝Sprint 33、辰宇 15.9pt **31 頁**＝Sprint 27、用色 **#231f20**）；草稿親驗零書中文句（6 字以上連續中文串全為系統詞彙）；部扉 W9 21.9pt（21 字）落 skipped 明細（不沉默、--min-chars 可撈回）。

### 誠實範圍（honest-planning R3／R7，GAPS #37）

- [實作]：萃取核心＋CLI（§6 Phase 3「從參考 PDF 萃取起始模版」的樣式清單半邊；§4.3 承諾原文即「提出起始段落樣式清單供使用者命名與調整」）。
- 未做：一鍵併入模版（草稿逐條經樣式管理 UI 新增）、字元樣式／主版／色票命名萃取（角色語意命名屬使用者＝設計行為）、色票管理（另片）。

### 待 Owner 真實素材驗收（R5）

- 以自己的其他參考 PDF 跑 extract-styles 看提案品質；其餘同 v0.66.0 hands-on 批次。

### 下個 Sprint 預定範圍

- 候選：模版庫管理面（清單／匯入／一鍵併入草稿）、色票管理、樣式改名。

## v0.68.0（2026-07-17，Sprint 73）AI 輔助樣式指派（txt 初稿建議，防禦降級不擋流程）

### 新增

- [實作] cjkfolio/ai_style.py（148 行，§4.4 分工鐵律照章：AI 只回「段落 → 樣式名」，版面幾何零採用）：
  - `suggest_styles`：OpenAI 相容 chat/completions（stdlib urllib，transport 可注入＝基線零網路）；候選集＝模版實際段落樣式清單（修正 3）、prompt 引導不確定選預設內文（修正 2 粗分類）；長稿分批（單批預設 3000 字，段落不跨批）。
  - 回應防禦鏈：剝 `<think>` 殼 → 抽 JSON 陣列 → index 越界與非候選集樣式忽略列警告（幻覺守門）；批次失敗（網路／解析）該批降級 None 維持原樣式，警告不沉默、不擋流程；警告訊息金鑰值遮蔽（紅線）。
  - `apply_suggestions`：不可變套回（None 維持原樣式、runs／page_no／master 保留、長度不符快速失敗）。
- CLI `assign-styles`（--config 預設 local/ai-config.local.json；AI 未設定明確訊息 exit 2＝顯式呼叫誠實失敗；列印改派數、樣式分布與「初稿請人工校正」定位提醒）。

### 驗證

- 核心基線 **580 passed / 0 failed**（566→580，+14，新檔 tests/test_ai_style.py 全離線 transport 注入：對映／剝殼／幻覺守門／壞 JSON 與網路錯誤降級／金鑰不入警告／分批全域索引／CLI 2）；typecheck EXIT=0（含 editor/*.py）；smoke C1〜C12 全過 0 退步。ai_style.py 148 行、cli.py 274 行守 800。繁中標點 grep 無破折號。
- 真實素材驗收（R5，自擬 10 段無結構 txt＋使用者私有 endpoint 實測）：import-txt 全內文 → assign-styles（1 批、改派 6 段）→ **嚴格 8/10、粗分類 10/10**（錯 2 段皆標題層級混淆＝Spike 5 錯誤解剖複現、§4.4「初稿＋人工校正」設計預期；訪談發言標籤 2/2 全對）→ render 2 頁 0 違規親 Read（樣式落位、偶右奇左正確）。

### 誠實範圍（honest-planning R3／R7，GAPS #36）

- [實作]：AI 指派核心＋CLI（§6 Phase 3「docx 匯入與 AI 輔助樣式指派整合」至此兩半皆落地；Phase 3 DoD「匯入 txt／md／docx 經 AI 指派＋人工校正產出排版初稿」的管線面完備，人工校正走編輯器樣式面板）。
- 未做：編輯器內「逐段確認與批次改派」校正 UI、editor 內 AI 指派入口（面板僅設定）、md／docx 的 AI 補充建議（結構優先＝設計行為）。
- 誠實宣稱：正確率數字僅適用自擬素材（嚴格 8/10），不外推為產品宣稱（§4.4 修正 4）。

### 待 Owner 真實素材驗收（R5）

- 以自己的真實書稿 txt 跑 assign-styles（層級混淆屬預期，重點驗粗分類與訪談標籤實用性）；其餘同 v0.66.0 hands-on 批次。

### 下個 Sprint 預定範圍

- 候選：從參考 PDF 萃取起始模版（§4.3，scan_reference_styles 產品化）、模版庫管理面（清單／匯入）、樣式改名、色票管理（§6 Phase 3）。

## v0.67.0（2026-07-17，Sprint 72）docx 匯入（OOXML 結構直接對映，stdlib 零新依賴）

### 新增

- [實作] cjkfolio/docx_import.py（163 行）：stdlib（zipfile＋ElementTree）解析 OOXML，不依賴 Word COM、產品碼零新依賴（§4.4 設計修正 1：標題層級由結構直接對映，不經 AI）：
  - 標題偵測三層鏈：段落直掛 pPr/outlineLvl → pStyle 樣式鏈（basedOn 遞迴＋循環守門）outlineLvl → 樣式名（heading N／標題 N）；outlineLvl 0〜8 有效、9＝正文（Spike 11 TOC Heading 一手實測，鏈上首見即定）。
  - 引文＝樣式名或 styleId 含 quote／引文；粗體→strong、斜體→em、粗斜並用→strong（md v1 不嵌套同構）；相鄰同樣式 run 併合；`w:val="0"/"false"` 關閉寫法正判；hyperlink 內 run 深走不漏；空段跳過；壞 zip／缺 document.xml 快速失敗。
  - 對映復用模版 md_mapping／md_inline_mapping（h4+ 未對映退內文＝md 同構）＝零新模版 schema。
- CLI `import-docx`（同 import-md 形：--template／--title，列印段數與對映樣式）。
- [Spike] Spike 11（spikes/spike11-docx-import/：premortem＋probe_ooxml＋report）：PoC 通過（python-docx 產檔 stdlib 解析 8 段全對、三層鏈於樣式鏈層命中、TOCHeading lvl 9 邊界揭露）。

### 驗證

- 核心基線 **566 passed / 0 failed**（544→566，+22，新檔 tests/test_docx_import.py：python-docx 產生器路徑 9〔Gate 4 獨立路徑：python-docx 1.2.0 寫、stdlib 讀〕＋手工 OOXML 邊界 12〔val 關閉／直掛優先／lvl 9 正文／中文樣式名／循環守門／缺 styles.xml／壞檔〕＋CLI 1）；typecheck EXIT=0（含 editor/*.py）；離屏 smoke C1〜C12 全過 0 退步。docx_import.py 163 行、cli.py 232 行守 800。繁中標點 grep 無破折號。
- 真實素材驗收（R5，自擬章節書稿，紅線不取參考書內容）：python-docx 產 8 段 docx → import-docx（章名／個案／小標／引文／內文五樣式對映）→ render 2 頁親 Read（h1 明體 Heavy、h2 黑 Medium、h3 黑 Bold、粗體與斜體 run 皆映內文強調-明體W9、跨頁強調 run 延續、偶右奇左頁碼書眉正確）→ export PDF preflight **12/12**。

### 誠實範圍（honest-planning R3／R7，GAPS #35）

- [實作]：docx 結構匯入核心＋CLI。
- 未做：真 Word（中文「標題 1」）／LibreOffice 產檔一手實測（名稱 fallback 以手工 OOXML 模擬）；表格／圖片／註腳／追蹤修訂／w:br／tab；AI 指派整合（§4.4，另片）；節首標記（同 GAPS #30 (c)）。
- 依賴誠實：python-docx 1.2.0（本機既裝）僅作測試素材產生器，非產品依賴。

### 待 Owner 真實素材驗收（R5）

- 若有真 Word／WPS／LibreOffice 書稿 docx：import-docx 實測標題層級與粗斜強調對映（GAPS #35 (a)）；其餘同 v0.66.0 hands-on 批次。

### 下個 Sprint 預定範圍

- 候選：AI 輔助樣式指派整合（§4.4 txt 粗分類＋樣式清單候選集，Phase 3 DoD 後半）、從參考 PDF 萃取起始模版、模版庫管理面（清單／匯入）、樣式改名。

## v0.66.0（2026-07-17，Sprint 71）樣式管理 UI（雙擊編輯／新增／刪除／另存模版接線）

### 新增

- [實作]（離屏 smoke C12 驗）樣式管理 UI（§4.3「雙擊編輯」＋另存 UI 半邊，關 GAPS #34 (d) 可自主子項）：
  - editor/style_panel.py：`StyleEditDialog`（欄位表驅動、預填現行效值、只送有改動欄位、選配欄位空字串清 None、非法值錯誤留對話框警示列不污染現態）＋`StylePanel.refresh`（清單隨模版變更與 undo 同步）＋雙擊編輯回呼。
  - editor/app.py：`EditorWindow.template` 改委派 session（樣式編輯後畫布與面板恆用現行模版）；「樣式」選單＝新增段落／字元樣式（基於面板選取為基底）、刪除選取樣式（守門訊息化）、另存模版（QFileDialog；核心 `_save_template_to` 可離屏驗）；皆走 session 統一 undo。
- 說明選單 Owner 實測步驟更新為七項（增樣式管理）。

### 驗證

- 核心基線 **544 passed / 0 failed**（不變＝UI 層，核心已於 Sprint 67〜70 入基線）；typecheck EXIT=0（含 editor/*.py）；離屏 smoke C1〜C12 全過，新增 **C12**：雙擊編輯內文 16pt 全書重排（非法值「十六」留對話框警示、現態不變）＋新增／刪除（文件使用中守門、面板清單同步）＋另存模版重載 16pt＋三步 undo 回原。app.py 741 行守 800。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]：樣式管理 UI 接線（離屏全回路驗證）。至此 §4.3 樣式面板全鏈（列出／點選套用／雙擊編輯／改樣式即全書套用）與模版另存可自主項收口。
- [Shell]／待 Owner（GAPS #19）：真視窗對話框與選單手感。
- 未做：樣式繼承視覺化（樹狀清單）、模版庫管理面（清單／匯入）、樣式改名。

### 待 Owner 真實素材驗收（R5）

- 真視窗雙擊面板樣式項編輯（內文 16pt 看全書重排）、「樣式」選單新增／刪除／另存；其餘同 v0.60.0 批次（說明選單七項）。

### 下個 Sprint 預定範圍

- 候選：docx 匯入（§4.4，Phase 3 §6；先查 python-docx 級依賴＋R2）、從參考 PDF 萃取起始模版、模版庫管理面、樣式改名。

## v0.65.0（2026-07-17，Sprint 70）模版序列化落檔（save_template，「從零建立模版」資料面全備）

### 新增

- [實作] cjkfolio/styles.py：`template_to_dict`（template_from_dict 的逆）＋`save_template`（utf-8／ensure_ascii=False／indent=1，承 Sprint 23 慣例）：
  - 樣式只寫 declared 欄位＋based_on＝繼承宣告保真（重載後級聯仍活，Sprint 68 declared 簿記兌現）。
  - 主版 margins／grid／mirror／footer／frame／rule／toc／figure／evidence／note 全欄位鏡射載入層；round-trip 相等鐵律（內建模版全 A〜G 主版覆蓋＋to_dict 冪等）。

### 驗證

- 核心基線 **544 passed / 0 failed**（537→544，+7，新檔 tests/test_template_io.py）；typecheck EXIT=0（含 editor/*.py）；smoke C1〜C11 全過 0 退步；styles.py 559 行守 800。繁中標點 grep 無破折號。
- 真實素材驗收（R5）：內建模版 save_template 落檔（23KB）→ load_template 重載相等 True；落檔親 Read（人類可讀、繁中不轉義、declared 欄位齊備）。

### 誠實範圍（honest-planning R3／R7，GAPS #34）

- [實作]：模版序列化與落檔核心。至此「從零建立一套新書樣式模版」資料面完備（新增／繼承／修改／刪除／另存）。
- 未做：另存 UI 與模版庫管理面（命名／清單／匯入，§4.3「模版庫」）、樣式改名、樣式管理 UI（#34 (d)）。

### 待 Owner 真實素材驗收（R5）

- 同 v0.61.0 hands-on 批次（本 Sprint 為核心層，無新 UI 面）。

### 下個 Sprint 預定範圍

- 候選：樣式管理 UI（面板新增／編輯／刪除／另存接線，收口 #34 (d) 可自主半邊）、docx 匯入（Phase 3 §6）、從參考 PDF 萃取起始模版。

## v0.64.0（2026-07-17，Sprint 69）樣式新增／刪除核心（§4.3 可新增，「從零建立模版」資料面補齊）

### 新增

- [實作] cjkfolio/style_editing.py：
  - `add_paragraph_style`／`add_character_style`：宣告形同模版 JSON（選配 based_on 承基底現值再覆寫＝載入層同構；根樣式必填守門；名稱空／衝突 TemplateError；新子樣式自動參與級聯）。
  - `remove_paragraph_style`／`remove_character_style`：模版內參照守門（子樣式承基底、md_mapping／md_inline_mapping、主版頁腳與 toc 頁碼樣式引用即拒）；未知樣式 KeyError。
- [實作] cjkfolio/session.py：`add_para_style`／`add_char_style`／`remove_para_style`／`remove_char_style` 入統一 undo 歷史；刪除文件仍用的樣式由全文重排 KeyError 快速失敗（狀態不變、不入歷史，承 Sprint 67 先重排再入歷史紀律）。

### 驗證

- 核心基線 **537 passed / 0 failed**（521→537，+16，新檔 tests/test_style_add_remove.py：add 7／remove 6／session 3）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C11 全過 0 退步。繁中標點 grep 無破折號。
- 真實素材驗收（R5，自擬）：session 新增子樣式「內文-小字註記」（based_on 內文、9pt）→ 套用至段落 → render PNG 親 Read（9pt 與 11.5pt 同頁對照、直排括號正確、0 違規）；雙 undo 回原（樣式消失、段落回內文）。

### 誠實範圍（honest-planning R3／R7，GAPS #34）

- [實作]：新增／刪除樣式核心（含繼承整合與參照守門）。至此樣式資料面新增／繼承／修改／刪除全備。
- 未做：樣式改名（需全書段落參照同步）、save_template 落檔（#34 (c)，「從零建立模版」最後資料面缺口）、樣式管理 UI（#34 (d)）。

### 待 Owner 真實素材驗收（R5）

- 同 v0.61.0 hands-on 批次（本 Sprint 為核心層，無新 UI 面）。

### 下個 Sprint 預定範圍

- 候選：save_template 模版序列化落檔（書系模版另存半邊，關 #34 (c)）、樣式管理 UI 面板（新增／編輯／刪除接線）、docx 匯入（Phase 3 §6）。

## v0.63.0（2026-07-17，Sprint 68）樣式繼承（based_on 基底＋子樣式覆寫，改基底即級聯全書）

### 新增

- [實作] 載入期繼承解析（cjkfolio/styles.py）：
  - 樣式宣告帶 `based_on` 即繼承基底有效欄位、自身宣告欄位覆寫（鏈式傳遞）；效值於 template_from_dict 扁平化＝消費端（layout／render／pdf／frames／canvas）讀平面欄位零變更。
  - `declared`（自身宣告欄位）＋`based_on` 簿記欄位（供編輯級聯與後續 save_template 只寫宣告欄位）。
  - 循環（含自指）／未知基底 TemplateError 快速失敗；子樣式可全承免必填、根樣式必填守門不變；schema 維持 template@1 相容擴充。
  - 欄位型別轉換表（PARAGRAPH_STYLE_FIELDS／CHARACTER_STYLE_FIELDS）上收 styles.py 單一來源（style_editing 改引用）。
- [實作] 編輯期級聯（cjkfolio/style_editing.py）：set_paragraph_style／set_character_style 改樣式後依 based_on 依賴序刷新傳遞子孫的未覆寫欄位（覆寫欄位不動）；被編輯欄位併入 declared＝自此成覆寫（InDesign 慣例）；based_on 不可經 set_* 編輯。session 零變更（update_* 自動級聯、快照三元組承 Sprint 67）。

### 驗證

- 核心基線 **521 passed / 0 failed**（506→521，+15，新檔 tests/test_style_inheritance.py：載入解析 7／編輯級聯 5／守門 1／session 端到端 1／內建模版回歸 1）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C11 全過 0 退步。繁中標點 grep 無破折號。
- 真實素材驗收（R5，自擬）：子樣式（based_on 內文、覆寫 indent 0）段落與基底段落同頁，session 改基底 11.5→16pt → 子樣式級數級聯放大、縮排覆寫保留（頂格 vs 縮 2 字對照清晰）render 前後 PNG 親 Read、0 違規、undo 回原。

### 誠實範圍（honest-planning R3／R7，GAPS #34）

- [實作]：繼承解析＋編輯級聯核心（載入與編輯兩層，消費端零變更）。
- 未做：繼承 UI 與「新增子樣式」入口（承 #34 (a)(d)）、改基底（based_on 結構變更）、修改後模版落檔（save_template，#34 (c)）。

### 待 Owner 真實素材驗收（R5）

- 同 v0.61.0 hands-on 批次（本 Sprint 為核心層，無新 UI 面）。

### 下個 Sprint 預定範圍

- 候選：樣式新增／刪除＋save_template 落檔（書系模版另存半邊，補 Phase 3 DoD「從零建立模版」）、樣式編輯 UI 面板、docx 匯入。

## v0.62.0（2026-07-17，Sprint 67）樣式修改核心（Phase 3 首片：改樣式即全書套用＋統一 undo）

### 新增

- [實作] `cjkfolio/style_editing.py`（純模版層，入 pytest 基線）：
  - `set_paragraph_style`／`set_character_style`：改既有樣式參數回傳新 Template（不可變、其他樣式物件共享）；未知樣式 KeyError、不可編輯欄位（含改名）TemplateError、空與等值變更 no-op 回原物件、型別轉換同載入層；值語意（writing_mode、字型）由 layout_document／FontRegistry 守門（承既有分層慣例）。
- [實作] `cjkfolio/session.py`：EditSession 依行數紀律自 editing.py 分檔（783→577 行守 800，先例 images／pdfx_meta／frame_editing；7 個 import 站點同步改）：
  - undo／redo 快照擴為三元組 (document, template, cursor)＝樣式定義編輯與文件編輯共用同一歷史（快照層只存不解釋）。
  - `update_para_style`／`update_char_style`：改樣式即全書重排入統一 undo；先重排快速失敗再入歷史（非法值不污染狀態）、樣式編輯不改文件游標保持、現態為框游標時回 FrameEditResult、打斷連續輸入合併序列；no-op 回 None 不記步。
  - `_state_result` 自 `_restore` 抽共用（雙游標型別結果構造單一事實來源）。

### 驗證

- 核心基線 **506 passed / 0 failed**（491→506，+15：純模版層 7＋session 整合 8，新檔 tests/test_style_editing.py）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke C1〜C11 全過 0 退步。繁中標點 grep 無破折號。
- 真實素材驗收（R5，自擬 samples/chapter-opening）：session 改「內文-明體直排」11.5→16pt → 全書重排（斷行移位、字級放大）render 前後 PNG 親 Read；頁腳（字元樣式）不受影響；undo 回 11.5、行數回原、0 違規。

### 誠實範圍（honest-planning R3／R7，GAPS #34）

- [實作]：修改既有樣式參數的核心回路（模版層＋session 統一歷史）。
- 未做：樣式改名／新增／刪除（需全書參照與面板、md_mapping 聯動）、樣式繼承（§4.3 基底＋覆寫，需解析層設計）、修改後模版落檔（save_template 屬「書系模版另存」半邊，session 內有效）、樣式編輯 UI（雙擊編輯參數面板，真視窗批次）。

### 待 Owner 真實素材驗收（R5）

- 同 v0.61.0 hands-on 批次（本 Sprint 為核心層，無新 UI 面）。

### 下個 Sprint 預定範圍

- 候選（依「最複雜架構先做」）：樣式繼承（基底＋覆寫，需 R2 評估動 template schema）、樣式新增／刪除＋save_template 落檔（書系模版另存半邊）、樣式編輯 UI 面板。

## v0.61.0（2026-07-17，Sprint 66）Phase 2 收尾判定（Owner 定案收尾轉 Phase 3）[Doc]

### 定案

- Owner AskUserQuestion 定案「收尾轉 Phase 3」：honest review 實查 §6 Phase 2 交付清單逐項收口（文字框建立／串接、主版指派、樣式面板含選取範圍、圖片置入任意矩形多圖、即時預覽 reflow 回路、IME 輸入區提交入 body 與框、復原重做統一歷史、鍵盤編輯換頁、拖曳範圍選取、AI 設定面板、製作者標示 footer 灰字實查命中），對照 Sprint 40〜65 一手驗證記錄。
- 剩餘項彙整 GAPS #33 Phase 2 Known Limitations（同 #22 為 Phase 1 之例）：**甲** Owner hands-on sign-off（#19 真視窗批次連同 Phase 1 遺留 #10／#23，不阻擋轉場＝Phase 1 先例）；**乙** UI 延伸工程（內嵌 IME 即點即打、拖放置圖、頁面面板、橫排互動層、拉線串框、跨段選取套段落樣式）；**丙** 後續 Phase 既定（PPI／彩色影像／目錄自動生成／圖文繞排 Phase 4、book 增量 Phase 3 再議）。
- 誠實差異：§6「Qt＋Skia 畫布」實作為 PySide6＋QGraphicsView＋自寫 PNG 渲染底圖（Sprint 40 定案；兩後端同源紀律延伸，Skia 不採用）；IME 真視窗組字順暢度（§5.2 選 Qt 關鍵理由）屬 Owner hands-on。

### 驗證

- [Doc] 無程式碼變更；基線複驗 **491 passed / 0 failed**、typecheck EXIT=0（含 editor/*.py）、離屏 smoke C1〜C11 全過、模版實查 7 主版＋18 段落／9 字元樣式。繁中標點 grep 無破折號。

### 待 Owner 真實素材驗收（R5）

- hands-on 批次：啟動編輯器.bat 照說明選單六項實測；連同 GAPS #10（Spike 1 對比圖 spikes/spike1-vertical-core/out/spread_comparison.png）、#23（斷行逐行一致率）同批。

### 下個 Sprint 預定範圍

- Phase 3 開工首項：樣式系統（樣式新增／修改／繼承，§4.3）。

## v0.60.0（2026-07-17，Sprint 65）拖曳範圍選取 UI（跨段選取 → 刪除／套字元樣式／IME 替換）

### 新增

- [實作]（離屏 smoke C11 驗）editor/app.py 拖曳範圍選取（GAPS #24 拖曳子項與 #28 選取拖曳 UI 關閉）：
  - CanvasView 左鍵按住拖曳回呼（mouseMoveEvent）；按下 body 字格＝拖曳起點，拖曳過字格＝`DocSpan` 選取（起訖文件序正規化＝反向拖曳等價；拖回起點退回單游標；重新按下清選取）。
  - 選取 shading：文件序半開區間相交判定該頁 body 字格（cell.span 為錨，與 provenance 同座標系），藍色半透明、取代單格高亮。
  - 選取操作入統一 undo 歷史：Backspace／Delete 刪選取（session.delete_span）、字元樣式面板同回呼改吃選取範圍（session.apply_style_span，套後保留選取）、IME 提交替換選取（session.replace_span）、Enter 選取中不分段提示；換頁與重繪清選取。
  - 框字格不設拖曳起點（框選取 v1 不支援）；說明選單 Owner 實測步驟更新為六項（增拖曳選取）。
- **Phase 2 可自主項至此含拖曳選取全數收口**：剩 Owner hands-on 批次（GAPS #19）；Phase 2 收尾判定與轉 Phase 3 需 Owner 定案（同 Sprint 39 先例）。

### 驗證

- 核心基線 **491 passed / 0 failed**（不變＝UI 層，DocSpan 核心已於 Sprint 48〜49 入基線）；typecheck EXIT=0（含 editor/*.py）；離屏 smoke C1〜C11 全過，新增 **C11**：跨段選取 19 格 shading（同格退回單游標、反向拖曳正規化）＋Backspace 刪選取併段（undo 回原）＋字元樣式套選取（跨段生效、選取保留）＋IME 替換選取（undo 回原）＋框拖曳不選取。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]：拖曳選取與選取編輯接線（離屏全回路驗證）。
- [Shell]／待 Owner（GAPS #19）：真視窗拖曳手感與 shading 視覺。
- v1 限制：跨段選取套段落樣式未支援（套拖曳起點所在段，多段一次套用需核心單一 undo 多段 API）、框內拖曳選取不支援。

### 待 Owner 真實素材驗收（R5）

- 真視窗按住左鍵拖曳選取（跨段、反向），試 Backspace 刪除、字元樣式套用、組字 Enter 替換；其餘同 v0.59.0 批次（說明選單六項）。

### 下個 Sprint 預定範圍

- Phase 2 可自主項全數收口。Phase 2 收尾判定與轉 Phase 3 由 Owner 定案（同 Sprint 39 先例）；候選：Phase 3 開工首項（樣式新增／修改／繼承）、Owner hands-on 批次（GAPS #19）先行。

## v0.59.0（2026-07-17，Sprint 64）樣式面板 UI（段落／字元樣式點選套用，Phase 2 可自主項全收口）

### 新增

- [實作]（離屏 smoke C10 驗）editor/style_panel.py＝`StylePanel` 段落／字元樣式雙清單（§4.3「點選即套用」Phase 2 半邊；GAPS #26／#27 面板子項關閉）：
  - 段落樣式：點選套用至 body 游標所在段（session.apply_para_style，入統一 undo 歷史）。
  - 字元樣式：點選套用至游標字（單字 DocRange，session.apply_style；「（清除字元樣式）」＝套 None 回段落預設）；拖曳範圍選取落地後同回呼改吃選取範圍。
  - 框游標提示不套（文字框單一樣式為框屬性）；app.py 右側 QDockWidget 接線。
- **Phase 2 §6 可自主收口項至此全數完成**：畫布、文字框建立／串接、主版指派、樣式面板套用、圖片置入、IME 插入（body＋框）、復原重做、鍵盤編輯、換頁、AI 設定面板。剩 Owner hands-on 批次（GAPS #19）與拖曳範圍選取（#24）。

### 驗證

- 核心基線 **491 passed / 0 failed**（不變＝UI 層，核心 API 已於 Sprint 45〜46 入基線）；typecheck EXIT=0（含 editor/*.py）；離屏 smoke C1〜C10 全過，新增 **C10**：內文段套「引文-仿宋語錄」全段換名、游標字套「內文強調-明體W9」再清除、三步 undo 回原。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]：樣式面板點選套用（離屏全回路驗證）。
- [Shell]／待 Owner（GAPS #19）：真視窗面板手感。
- 註：雙擊編輯樣式參數、樣式繼承、模版庫屬 Phase 3（§4.3）。

### 待 Owner 真實素材驗收（R5）

- 真視窗右側樣式面板點選實測；其餘同 v0.58.0 批次（說明選單五項）。

### 下個 Sprint 預定範圍

- Phase 2 可自主項已收口。候選：Phase 2 收尾判定（honest review 後轉 Phase 3，需 Owner 定案同 Sprint 39 先例）、圖說相對位置樣式化置放（R1 量測）、拖曳範圍選取（真視窗批次）。建議：本場次收工，Phase 2 收尾判定與轉場由 Owner 定案後新場次開工。

## v0.58.0（2026-07-17，Sprint 63）AI 設定面板 UI（§4.4 三欄位面板，金鑰紅線 UI 落實）

### 新增

- [實作]（離屏 smoke C9 驗）editor/ai_panel.py（79 行）＝`AiConfigDialog` 三欄位面板（Base URL／API Key／Model）：
  - 載入既有本機設定帶入欄位；儲存走 cjkfolio.ai_config 資料面（單一事實來源），只寫 local/ai-config.local.json。
  - 金鑰紅線 UI 落實：API Key 欄遮罩（QLineEdit Password）；載入／儲存錯誤以面板內嵌警示列顯示（非 modal＝離屏可驗，訊息不含欄位值）；statusBar 儲存訊息不含值。
  - app.py「設定」選單接線（AI 設定…）。
- Phase 2 §6 可自主收口項至此全數完成；剩 Owner hands-on 批次（GAPS #19）與拖曳範圍選取（#24）。

### 驗證

- 核心基線 **491 passed / 0 failed**（不變＝UI 層，資料面已於 Sprint 56 入基線）；typecheck EXIT=0（含 editor/*.py）；離屏 smoke C1〜C9 全過，新增 **C9**：tmp 路徑三欄位儲存 round-trip、既有值帶入、金鑰遮罩、壞檔空值開啟＋警示訊息不含欄位值。
- 真實素材驗收（R5）：使用者既有本機設定檔實載（3/3 欄位非空、值零輸出＝金鑰紅線）。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]：面板 UI 與資料面接線（離屏全回路驗證）。
- [Shell]／待 Owner（GAPS #19）：真視窗面板外觀與輸入手感。
- 註：面板僅管理設定；LLM 呼叫端（AI 樣式指派整合）屬 Phase 3（§4.4）。

### 待 Owner 真實素材驗收（R5）

- 真視窗開「設定 → AI 設定…」確認欄位帶入與遮罩；其餘同 v0.57.0 批次。

### 下個 Sprint 預定範圍

- 候選：圖說與照片相對位置樣式化置放（真書 R1 量測）、目錄摘要層（需先問 Owner 同意下載全字庫 TW-Kai 大包）、拖曳範圍選取 UI（真視窗批次）、Phase 3 開工首項（樣式新增／修改／繼承）。

## v0.57.0（2026-07-17，Sprint 62）畫布鍵盤編輯接線＋頁面切換（Backspace／Delete／Enter／PgUp・PgDn）

### 新增

- [實作]（離屏 smoke C8 驗）editor/app.py 畫布鍵盤編輯（GAPS #24 鍵盤子項關閉）：
  - CanvasView 加 `keyPressEvent` 回呼；游標語意＝點選字格之後（與 IME 插入一致）。
  - Backspace＝刪游標字、Delete＝刪其後一字（段末／框文末提示不刪）；body 與框皆走 session 入統一 undo 歷史；框刪空 ValueError 顯示訊息不 crash。
  - Enter＝body 游標處分段（session.split）；文字框單段提示不分（設計行為）。
  - PgUp／PgDn 換頁（首末頁停留、換頁清游標）；demo 自此可瀏覽多頁文件。
  - 抽 `_follow_body_address`（IME 提交／undo redo／鍵盤刪除共用游標跟隨，消三處重複）。

### 修正

- PLAN 結構勘誤：Sprint 61 編輯時誤吞「- AI 設定面板」行首標籤（內容併入 Sprint 61 進度行），本版修復並以錨行掃描確認 §6 結構完整。

### 驗證

- 核心基線 **491 passed / 0 failed**（不變＝UI 接線層，核心 API 已於 Sprint 42／43／59／60 入基線）；typecheck EXIT=0（含 editor/*.py）；離屏 smoke C1〜C8 全過，新增 **C8**：body Backspace 刪字（undo 可回）、Enter 分段（段數 +1）、框 Backspace 刪鏈首字（undo 可回）、chapter-opening 兩頁樣張 PgDn／PgUp 換頁與首末頁停留。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]：鍵盤編輯與換頁接線（離屏全回路驗證）。
- [Shell]／待 Owner（GAPS #19）：真視窗鍵盤手感與焦點行為（畫布需先點選取得焦點）。
- 剩（GAPS #24）：拖曳範圍選取 UI（真視窗工程）。

### 待 Owner 真實素材驗收（R5）

- 真視窗五項實測（說明選單已更新，含鍵盤編輯與換頁）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 候選：圖說與照片相對位置樣式化置放（真書 R1 量測）、目錄摘要層（需先問 Owner 同意下載全字庫 TW-Kai 大包）、拖曳範圍選取 UI（真視窗批次）。

## v0.56.0（2026-07-17，Sprint 61）app 真視窗接線批次（session＋IME 入框＋Ctrl+Z／Y）

### 新增

- [實作]（離屏 smoke C7 驗）editor/app.py（337 行）接線 Sprint 58〜60 核心：
  - EditorWindow 改持 `EditSession`（編輯狀態單一事實來源；doc／layout_result 轉 property 委派，既有介面不變）。
  - 點框字格設框游標（與 body 游標互斥＝最後點選者為 IME 目標）；IME 提交分流：body → `session.insert`（全文 reflow）、框 → `session.insert_frame`（框鏈重佈局，body 版面不重排），游標跨框跟隨＋高亮。
  - 「編輯」選單 Ctrl+Z／Ctrl+Y（QKeySequence 標準鍵）→ `session.undo()`／`redo()`；`_apply_history` 依還原態型別（EditResult／FrameEditResult）分流游標高亮跟隨。
  - 說明選單 Owner 實測步驟更新為四項（body IME、框 IME、快捷鍵、對位）。

### 驗證

- 核心基線 **491 passed / 0 failed**（不變＝UI 接線層，核心已於 Sprint 58〜60 入基線）；typecheck EXIT=0（含 editor/*.py）；離屏 smoke C1〜C7 全過，新增 **C7**：IME 提交入框（插「新」於鏈首字位 19 → 文字入框、游標跟隨續框＋高亮）＋undo／redo 統一歷史（body「好」、框「新」依序回退）＋既有 C5 body 回路走 session 0 退步。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]：session 接線＋IME 入框＋快捷鍵（離屏全回路驗證）。
- [Shell]／待 Owner（GAPS #19）：真視窗鍵盤實測（IME 直排組字、候選字窗、快捷鍵手感、視覺對位），啟動編輯器.bat 開任一含框文件即可測。
- 決策：橫排框 v2 本輪不做（R1 證據弱＝參考書無「橫排文字框」用例，依 R8 不為無用例功能建介面）。

### 待 Owner 真實素材驗收（R5）

- 真視窗四項實測（說明選單有步驟）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 候選：圖說與照片相對位置樣式化置放（真書 R1 量測）、目錄摘要層（需先下載全字庫 TW-Kai，宜先問 Owner 下載授權）、框編輯 UI 後續（Backspace 刪框字、拖曳選取）。

## v0.55.0（2026-07-17，Sprint 60）EditSession 框編輯整合（body 與框統一 undo／redo 歷史）

### 新增

- [實作] `EditSession.insert_frame`／`delete_frame`（cjkfolio/editing.py，783 行守 800）：框編輯與 body 編輯共用同一 undo／redo 堆疊。
  - undo／redo 快照 cursor 容 DocCursor 與 FrameCursor（快照層只存不解釋）；`_restore` 依游標型別分流＝FrameCursor → resolve_text_frames＋locate_frame_cell 回 FrameEditResult、DocCursor → locate_cell 回 EditResult（undo／redo 回傳型別隨還原態）。
  - 輸入序列鍵一般化：`_pending_insert` 存（鍵, 尾 caret, 時戳），鍵＝("body", para_idx) 或 ("frame", source_idx)；框連續前進打字併單一 undo 單元（同 Sprint 47 body 慣例），body 與框輸入互為序列邊界（鍵不同即起新單元）。
  - `_commit` duck-type 收 FrameEditResult（其 layout＝原物件＝框編輯不重排 body，現態 layout 不變）。

### 驗證

- 核心基線 `pytest spikes tests` **491 passed / 0 failed**（486→491，+5，test_edit_frames.py session 段：框 undo／redo 往返（redo 回框態 FrameEditResult＋address 反查）／body 框交錯歷史依序回退／框連續輸入合併單一單元／body 輸入打斷框序列／delete_frame undo）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5）：Sprint 57 真實示範 out/thread-demo 建 session → 框插「而」＋body 插「快」交錯 → 兩段 undo 回初始（不可再退）→ redo 回框態（FrameEditResult、address＝框 1 首格「而」），往返全對。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋R5 驗）：統一編輯歷史（純邏輯層）。
- 剩（GAPS #32 (d)）：框全刪空（「空框」schema 演進）；IME 入框、框編輯與 undo／redo（Ctrl+Z／Y）UI 接線（真視窗批次）。

### 待 Owner 真實素材驗收（R5）

- Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on；真視窗批次（GAPS #19：IME 直排輸入、點框字格、undo／redo 快捷鍵）。

### 下個 Sprint 預定範圍

- 候選：橫排框 v2（shaper 度量介面）、圖說與照片相對位置樣式化置放（真書 R1 量測）、目錄摘要層（需先下載全字庫 TW-Kai）、app.py 真視窗接線批次（框游標＋IME 入框＋Ctrl+Z／Y，離屏可先建、鍵盤待 Owner）。

## v0.54.0（2026-07-17，Sprint 59）框內編輯核心（insert／delete 入框，GAPS #32 (d) 後半）

### 新增

- [實作] `cjkfolio/frame_editing.py`（入 pytest 基線；editing.py 735 行近上限依行數紀律分檔，先例 images.py／pdfx_meta.py）：
  - `FrameCursor`（source_idx＋來源 text 半開座標 caret，與 Sprint 58 框 span 同座標系閉環）；`FrameCellAddress`／`FrameEditResult`。
  - `insert_frame_text`／`delete_frame_range`：鏈首 text 不可變字串切接（框單段單一樣式無 runs）；續框無文字編輯（引導對鏈首）、全刪空（框 text 非空為 document@2 不變式）、越界皆快速失敗。
  - `apply_frame_insert`／`apply_frame_delete`：改鏈首 text → `resolve_text_frames` 框鏈重佈局（**body layout 不重排**，原物件傳回＝框編輯不影響流排）→ `locate_frame_cell` span 反查新框游標落點；插字跨框流動游標自動跟隨。
- frames.py 抽 `masters_for_layout`（masters_by_page 標準構造單一事實來源）；editor/canvas.py `page_frame_placements` 同步改用。

### 驗證

- 核心基線 `pytest spikes tests` **486 passed / 0 failed**（478→486，+8，新檔 tests/test_edit_frames.py：insert 不可變與守門 2／delete 與守門 2／apply 回路 3（含插字流入續框跨框游標跟隨）／locate 1）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5）：Sprint 57 真實示範 out/thread-demo 圖說 caret 8 插「而」→ 16 字恰滿兩框、「而」流入續框成首字、游標落點框 1 欄 0 格 0、佈局 0 違規；render（out/thread-demo/edited）親 Read 與編輯前樣張對照逐項正確。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋R5 驗）：框內插刪核心與 apply 回路（純邏輯層）。
- 剩（GAPS #32 (d)）：EditSession 整合（框編輯入 undo／redo，cursor 型別容 DocCursor 與 FrameCursor）；框全刪空（「空框」schema 演進）；IME 入框與框編輯 UI 接線（真視窗批次）。

### 待 Owner 真實素材驗收（R5）

- 編輯前後樣張 out/thread-demo/page-001.png 與 edited/page-001.png 對照抽檢；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 候選：EditSession 框編輯整合（undo／redo 統一歷史，「最複雜架構」項）、橫排框 v2、圖說與照片相對位置樣式化置放（真書 R1 量測）、目錄摘要層（需先下載全字庫 TW-Kai）。app.py 真視窗 UI 接線待 Owner 真視窗回報批次。

## v0.53.0（2026-07-17，Sprint 58）框 provenance＋畫布框字格反查（GAPS #32 (d) 前半）

### 新增

- [實作] 框 provenance（框版的 Sprint 18＋Sprint 40 資料鏈）：
  - frames.py 佈局改帶 offsets（`normalize_with_offsets`＋`tokenize(offsets=)` 對齊 body 慣例）：框 cells span＝來源 text（normalize 前）座標，Cc 剝除位移精確、latin／tcy 整串。
  - `FramePlacement` 加 `frame_idx`（自身框的 doc.text_frames 索引）／`source_idx`（文字來源框＝串接鏈首；獨立框＝自身）＝span 座標的錨；`resolve_text_frames` 填、兩後端不讀（零影響）。
  - editor/canvas.py：`page_frame_placements`（逐頁框 placements 單一事實來源）＋`iter_frame_cell_rects`（框字格矩形，與 render `_draw_text_frame` 逐項同源）＋`FrameCellHit`／`resolve_frame_hit`（點框字格 → 框游標）；`build_page_scene` 框字格入互動層（item data＝("frame", fi, li, ci)，body 鍵形不變）。
  - editor/app.py：`_on_pick` 分流＝點框字格顯示框游標與來源切片（串接續框切鏈首 text）、不設 body 插入游標（IME 不入框）。

### 驗證

- 核心基線 `pytest spikes tests` **478 passed / 0 failed**（475→478，+3：Cc 位移與 latin span／串接鏈 span 錨鏈首 text／resolve frame_idx＋source_idx 雙索引）；typecheck EXIT=0（含 editor/*.py）；editor 離屏 smoke_check EXIT=0。
- 離屏 smoke 新增 C6：自擬「串接雙框＋獨立框」文件 → 框字格 hit-test **28/28 全對**、FrameCellHit round-trip 28 格（續框首格 span＝(18, 19) 錨鏈首 text）、app 點框字格分流顯示框游標且不設 body 游標。
- 真實素材驗收（R5）：以 Sprint 57 真實示範 out/thread-demo/demo.doc.json 逐格 round-trip **15 格全對**（框 1 續框 span (8, 9)＝接鏈首第 9 字）。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋smoke＋R5 驗）：框 provenance 資料鏈（span／frame_idx／source_idx）＋畫布框字格反查全回路。
- [Shell]／待 Owner（GAPS #19／#32 (d)）：真視窗點框字格視覺對位（離屏測不了）；框內插刪改（editing 游標入框）、拉線串框 UI 待框編輯專項。

### 待 Owner 真實素材驗收（R5）

- 真視窗點框字格實測（啟動編輯器.bat 開任一含框文件）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 候選：框內編輯操作（insert／delete 入框＝GAPS #32 (d) 後半，串接鏈重佈局游標跟隨）、橫排框 v2、圖說與照片相對位置樣式化置放（真書 R1 量測）、目錄摘要層（需先下載全字庫 TW-Kai）。app.py 真視窗 UI 接線待 Owner 真視窗回報批次。

## v0.52.0（2026-07-17，Sprint 57）文字框串接（thread 跨框續排，§6「文字框建立／串接」補齊）

### 新增

- [實作] 文字框串接（§6 Phase 2「文字框建立／串接」的**串接半邊**，關 GAPS #32 (a)；承 Sprint 55 建立半邊）：
  - document@2 相容擴充 `TextFrame.thread`（選配串接鏈名）：同 thread 框依文件序成鏈、文字掛鏈首；解析層守門＝續框帶 text 雙源快速失敗、續框 style 須與鏈首一致、thread 空字串拒絕；序列化續框不寫空 text。
  - `cjkfolio/frames.py` `layout_thread`：鏈文字一次 tokenize 成 cells，逐框以該框頁主版網格換算容量斷行、取前欄數容量欄、以已消費 cell 數切出剩餘 cells 續排下一框；切點＝合法行邊界（`_break_cells` 行序列 cells 連續無增刪且每行行首行尾禁則已解消）＝框邊界禁則自然正確；中間框排滿即續流、鏈尾仍剩列違規掛鏈尾（不沉默）；跨頁串接逐框取該頁網格（節式主版指派一致）。
  - `resolve_text_frames`：鏈框統一佈局後放回各自頁；頁內繪製序＝文件序（Sprint 54 rect 圖慣例）。
  - engine 加公開 `break_cells`（cells 級斷行入口；`break_paragraph` 委派，行為不變）。
  - 兩後端與 editor canvas 零變更（FramePlacement 介面不動）。

### 變更

- `layout_text_frame` 內部改用共用助手（`_frame_style`／`_frame_metrics`／`_place_lines`，與 `layout_thread` 共用），單框行為與溢出訊息不變。

### 驗證

- 核心基線 `pytest spikes tests` **475 passed / 0 failed**（463→475，+12，tests/test_text_frames.py：thread schema 解析與 round-trip／守門快速失敗 2、跨框續排／框邊界禁則／逐框幾何／鏈尾溢出／單框鏈等價／跨頁逐框網格 6、resolve 文件序與鏈成員頁守門 2、兩後端串接幾何 2）；typecheck EXIT=0；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5，自擬）：「雙照片＋一段圖說流過上下兩框」示範（out/thread-demo/demo.doc.json）→ render PNG 親 Read（上框「改造前雜物滿地，」句逗收框尾不落下框行首、下框「改造後留白生光」接續）、export PDF **preflight 12/12 全綠**、禁則 0 違規。
- Gate 4 獨立驗證：PyMuPDF rawdict 串接守恆（框 A 8 字＋框 B 7 字＝原文 15 字無重複無遺漏）、兩框字墨 cx＝各框行軸（356.1＝框右緣−半欄距）。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋R5 驗）：串接全管線（schema 守門／逐框續排佈局／resolve 分組）。
- v1 已知限制（GAPS #32）：鏈序＝文件序（無顯式序欄位）；無框內強制斷點原語（InDesign 框斷字元同義項）；只直排、單一樣式（全鏈一致）、框無 provenance 承 Sprint 55；拉線串框／框編輯 UI 屬真視窗批次。

### 待 Owner 真實素材驗收（R5）

- 串接示範 out/thread-demo/page-001.png 與 demo.pdf 抽檢；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 候選：框編輯（provenance＋游標入框，畫布互動地基）、橫排框 v2（shaper 度量介面）、圖說與照片相對位置樣式化置放（真書 R1 量測）、目錄摘要層（需先下載全字庫 TW-Kai，GAPS #12／#22 甲類）。app.py 真視窗 UI 接線待 Owner 真視窗回報批次。

## v0.51.0（2026-07-17，Sprint 56）AI 設定檔層（§4.4 三欄位本機設定，金鑰紅線）

### 新增

- [實作] `cjkfolio/ai_config.py`（§6 Phase 2「AI 設定面板」的資料面半邊）：`AiConfig`（base_url／api_key／model，預設全空）＋`load_ai_config`（缺檔＝空預設不擋流程；壞 JSON／欄位型別不符明確錯誤，**錯誤訊息不回帶欄位值**＝金鑰不入 log；未知鍵容忍向前相容）＋`save_ai_config`（建父目錄、只序列化三欄位）。慣例路徑 local/ai-config.local.json（local/ 已入 .gitignore，GAPS #6 紅線複核）。

### 驗證

- 核心基線 `pytest spikes tests` **463 passed / 0 failed**（457→463，+6，新檔 tests/test_ai_config.py）；typecheck EXIT=0；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5）：以使用者既有本機設定檔實載，三欄位皆載入成功（值零輸出＝金鑰紅線）；金鑰紅線測試釘死（錯誤訊息不含祕密值）。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]：設定檔讀寫資料面。[Shell]／待 Owner：三欄位面板 UI（真視窗批次，GAPS #19）；LLM 呼叫端（Phase 3 AI 指派整合）尚未接此設定。

### 下個 Sprint 預定範圍

- 文字框串接（threading，§6「文字框建立／串接」的串接半邊，schema 演進型架構題，建議新場次開工）；或框編輯 provenance、圖說相對位置 R1 量測。app.py 真視窗 UI 接線待 Owner 真視窗回報批次。

## v0.50.0（2026-07-17，Sprint 55）獨立文字框 v1（任意矩形直排文字框：圖說自由位置等自由手排項的機制載體）

### 新增

- [實作] 獨立文字框（Owner「最複雜架構先做」下，§6 Phase 2「文字框建立／串接」的**建立半邊**；threading 屬串接半邊後續專項）：
  - document@2 相容擴充 `TextFrame`（text／style／page／rect；rect 同 PlacedImage 座標系＝trim pt top-down、可溢出版心；@1 拒絕、schema 驗證快速失敗）。
  - `cjkfolio/frames.py`（兩後端同源單一幾何層）：`layout_text_frame`（欄容量＝floor(框高/字距)、欄距＝級數×(網格行距/基準級數) §10 同構、欄自框右緣右至左、框內不齊行；斷行禁則復用 engine break_paragraph〔擠入追出同 body〕；溢出框寬欄不繪並列違規不沉默；未知樣式／橫排樣式快速失敗）＋`resolve_text_frames`（逐頁主版 grid；框頁超出流排頁快速失敗＝不為框造頁，同 images 規則）。
  - 兩後端 `_draw_text_frame`（render）／`_text_frame`（pdf_writer）：復用直排 cell 繪製助手（cjk／tcy／latin 旋轉）；frame violations 併入 RenderResult／PdfResult（不沉默）。
  - editor canvas 底圖繪框（build_page_scene 傳 frames；框字格互動層待框 provenance）。
  - book.py 章級 text_frames 組裝拒絕（頁號章內語意同 images；框於組裝後全書文件加入）。

### 變更

- pdf_writer 行數上限管理：XMP 助手抽出至 `cjkfolio/pdfx_meta.py`（`xmp_packet`，純搬移行為不變；pdf_writer 796 行守住 800 上限）。
- render_page／build_page 加 `frames=()` 參數（FramePlacement 序列，由 resolve_text_frames 提供）。

### 驗證

- 核心基線 `pytest spikes tests` **457 passed / 0 failed**（446→457，+11，新檔 tests/test_text_frames.py：TextFrame 解析與序列化／驗證快速失敗／@1 拒絕／欄容量與行軸／折欄禁則／溢字違規／橫排與未知樣式快速失敗／PDF 框幾何／PNG 框內墨跡框外紙白／框頁超出快速失敗）；typecheck EXIT=0；editor 離屏 smoke_check EXIT=0（canvas 繪框後複驗）。
- 真實素材驗收（R5，自擬）：雙照片＋雙直排辰宇圖說貼照片側（框位溢出版心＝真書 G 頁「照片＋自由圖說」形態）→ render PNG 親 Read（圖說直排落位、body 旁注照排）、export PDF **preflight 12/12 全綠**、禁則 0 違規。
- Gate 4 獨立驗證：PyMuPDF rawdict 框字墨 cx＝frames 行軸（abs≤1.2pt）、框緣 bearing 容忍 3pt（字墨可略超字框＝字型度量差，Sprint 37 同性質）；PNG crop 框內有墨、框下方紙白。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋R5 驗）：文字框建立全管線（document／frames／兩後端／canvas 底圖）。
- v1 已知限制（GAPS #32）：不串接（threading 後續專項）；只直排（橫排框 v2）；單一段落樣式、無 runs、不齊行；框無 provenance（畫布互動層與 editing 游標不入框，框編輯專項）；章級 text_frames 組裝拒絕（設計行為）。

### 待 Owner 真實素材驗收（R5）

- 圖說示範 out/rect-demo/page-001.png 與 demo.pdf 抽檢；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 候選：文字框串接（threading，§6「串接」半邊）、框編輯（provenance＋游標）、圖說與照片相對位置樣式化置放（真書 R1 量測）、AI 設定檔層。app.py 真視窗 UI 接線待 Owner 真視窗回報批次。

## v0.49.0（2026-07-17，Sprint 54）多圖／任意矩形置入模型（PlacedImage.rect 任意圖框，畫布置圖模型地基）

### 新增

- [實作] 影像模型一般化（Owner「最複雜架構先做」下，GAPS #29 (a)；零新技術＝復用 fit_image_rect／paste／XObject）：
  - document@2 相容擴充 `PlacedImage.rect`（選配任意圖框＝[x0, y0, x1, y1] trim 空間 pt、top-down；形狀驗證 x0<x1、y0<y1 快速失敗；**允許溢出版心**＝真書照片略溢 1〜4pt 特徵〔GAPS #13 一手記錄〕與出血照片正當用法）。
  - rect 圖每頁多張（文件序＝繪製序＝疊放 z 序確定性）；槽式（無 rect）維持 figure 保留區每頁一張守門。
  - `resolve_placed_images` 改列表模型 {頁: ((路徑, 影像, rect|None), ...)}；rect 圖不需 figure 槽（A 內文頁亦可置圖）、槽式仍需；同路徑 XObject 去重不變。
  - 兩後端 `_draw_image`／`_image` 收 rect（None＝figure 槽既有語意）；佔位虛線框改「槽仍空即畫」（rect 圖不填槽＝InDesign 空框導引）；PNG 溢出框於 trim 畫布自然裁切、PDF 置入出血區。

### 變更

- render／pdf `render_page`／`build_page` 參數 `image=` 改 `images=()`（每頁多張）；`RenderResult.images_placed`＝置入張數、`PdfResult.images_placed`＝去重後 XObject 數（原有語意差明文化）；CLI 置入圖訊息措辭同步（「槽式與 rect 任意圖框」）。
- tests/test_images.py 去重測試隨 resolve 列表模型同步取值形狀。

### 驗證

- 核心基線 `pytest spikes tests` **446 passed / 0 failed**（436→446，+10，新檔 tests/test_image_rects.py：rect 解析與序列化／形狀快速失敗／槽式守門與 rect 多張放行／resolve 不需 figure 槽／順序與去重／PDF 多框幾何與溢出／PNG 兩框像素／佔位框槽 gate／節式主版共存）；typecheck EXIT=0；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5，自擬 G 頁雙照片示範＝真書雙照片形態）：兩 rect 圖框（改造前暗／改造後亮）疊放照片區 → render PNG 親 Read（框位精確、contain 等比、佔位框標示空槽）、export PDF **preflight 12/12 全綠**、禁則 0 違規。
- Gate 4 獨立驗證：PyMuPDF get_image_rects 驗置入 bbox＝rect＋出血（fitz top-down 同向、abs≤0.3pt）、同路徑三框單一 XObject、溢出框右緣跨入出血；PNG getpixel 兩框中心值＋框外紙白。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋R5 驗）：rect 任意圖框全管線（document／resolve／兩後端）、每頁多張、溢出版心／出血置圖。
- [Shell]／待 Owner（GAPS #29 (d)／#19）：畫布拖放／縮放置圖 UI 未接線（app.py 真視窗工程）。
- v1 已知限制：只灰階 DeviceGray（彩色 CMYK Phase 4，#29 (c)）；PPI 未強制重採樣（#29 (b)／#18）；rect 圖不參與文字繞排（圖文繞排 Phase 4）。

### 待 Owner 真實素材驗收（R5）

- 雙照片示範 out/rect-demo/page-001.png 與 demo.pdf 抽檢；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- Sprint 51 預定餘項：圖說與照片相對位置的樣式化置放（需先 R1 量測真書圖說幾何）；或 §6 Phase 2 其餘純邏輯項（AI 設定面板本機設定檔層）。app.py 真視窗 UI 接線待 Owner 真視窗回報批次。

## v0.48.0（2026-07-17，Sprint 53）節式混向文件（直排內文＋橫排版權頁同冊，F 入冊全書單一 PDF/X）

### 新增

- [實作] 書寫方向降到節層級（Owner「最複雜架構先做」下，關 GAPS #30 (b)／#31 (b)；零新排版機制＝方向參數本就逐 flow_pages 傳遞，「全文件單向」係單一 flow 時代遺留）：
  - layout：`_section_is_vertical`（同一節混向仍快速失敗，訊息引導以節首標記分節）＋`LayoutPage.vertical` 逐頁方向載體；`LayoutResult.vertical` 改義＝首節方向（相容欄位，逐頁以 LayoutPage.vertical 為準）；`page_is_vertical` 保留為全文件單向相容 util。
  - 齊行統計逐頁 gate（橫排頁短行左齊、不入統計）；rule 斷線逐頁 gate（直排目錄原件）。
  - 兩後端 render_document／export_pdf 逐頁傳方向；frame（橫排原件）與 rule（直排原件）既有 gate 自動逐頁正確。
  - editor canvas：底圖逐頁方向；橫排頁互動層未建（僅底圖，iter_cell_rects 為直排 body 幾何，入 GAPS #30 (b) 註記待真視窗批次）。
  - samples/book.json 加第六章 cip-copyright.doc.json：F 版權頁入冊，全書單一 PDF/X（原「F 另出一份」解除）。

### 驗證

- 核心基線 `pytest spikes tests` **436 passed / 0 failed**（428→436，+8，新檔 tests/test_direction_sections.py：逐頁方向／首節橫排／單向不變／同節混向仍 raise／齊行統計對照／混向 PDF 幾何／render 混向兩頁／book 含 F 章端到端）；typecheck EXIT=0；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5，自擬全書樣張）：assemble 6 章 → 28 段（7 節首標記）→ render 7 頁（禁則 0 違規）＋export 單一 PDF **preflight 12/12 全綠**；親 Read 頁 7（F 版權頁：橫排 CIP 七行左起、細框四邊閉合、ISBN 拉丁串完整、無頁腳），直排 6 頁特徵不變。
- Gate 4 獨立驗證：PyMuPDF rawdict 混向幾何（頁 1 直排＝同欄字墨 cx 一致且 y 遞增；頁 2 橫排＝同行基線 y 一致且 x 遞增）＋get_drawings 驗 CIP 細框 `re` 只在 F 頁＋齊行統計混向對照（加橫排節統計不變）。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋R5 驗）：節式混向全管線（layout 逐頁方向＋兩後端＋齊行統計）、F 版權頁入冊。
- v1 已知限制：同一節混向快速失敗（版面軸不同、slot 幾何不相容，設計行為）；橫排頁畫布互動層未建（僅底圖，GAPS #30 (b) 註記，真視窗批次）。

### 待 Owner 真實素材驗收（R5）

- 全書樣張 out/book/*.png 七頁與 out/book.pdf 抽檢（重現：assemble → render → export-pdf → preflight）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- Sprint 51 預定餘項擇一：圖說與照片相對位置樣式化置放、多圖／任意矩形置入模型；或 §6 Phase 2 其餘純邏輯項。app.py 真視窗 UI 接線（頁面面板／橫排互動層）待 Owner 真視窗回報批次。

## v0.47.0（2026-07-17，Sprint 52）全書組裝管線（book@1 多章串接為單一多主版文件，直向全書級 PDF/X）

### 新增

- [實作] 書冊組裝 `cjkfolio/book.py`（cjkfolio/book@1；Owner「最複雜架構先做」下，Sprint 51 預定三選項取最重）：
  - 書冊清單 JSON：meta.title（全書題名，PDF /Title 與書眉用）／meta.template（各章必須一致）／`chapters` 章序即節序（每章＝{path, master?}）／選配書冊層級 `images`（page＝全書版面頁號）。
  - `assemble_book`：串接為**普通 document@2 文件**，組裝層零新排版機制（章首段掛 `Paragraph.master` 節首標記＝Sprint 51 節式主版指派，render／export／editing 照既有管線）；主版解析優先序＝chapters[].master 顯式覆寫 ＞ 章首段既有標記 ＞ 章文件 meta.master；章內既有節照搬；page_no 透傳。
  - 快速失敗：schema 不合、空章、template 不一致、章層級 images（其 page 為章內排版頁號、組裝後即失效，改列書冊層級）、章檔缺失。
  - CLI `assemble` 子命令（章路徑相對書冊清單目錄；輸出 doc.json 可直接 render／export-pdf／編輯）。
  - 樣張 `samples/book.json`（自擬全書：E 序文＋D 目錄＋B/A 章首＋C 個案扉頁＋G 圖文版五章六頁）。

### 修正

- samples/figure-page.doc.json 補缺漏的 meta.template（Sprint 27 起缺、載入時默認空字串；組裝器 template 一致性檢查抓到＝快速失敗設計自證）。

### 驗證

- 核心基線 `pytest spikes tests` **428 passed / 0 failed**（413→428，+15，新檔 tests/test_book.py：schema 驗證／assemble 章首標記與覆寫優先序／章內節照搬／page_no 透傳／template 不一致／空章／缺檔／章級 images 拒絕／書冊級 images 透傳／組裝後 layout 節序／save round-trip／CLI／五章全書端到端）；typecheck EXIT=0；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5，自擬全書樣張，非參考書內容）：CLI assemble samples/book.json → 5 章 21 段（6 節首標記）→ render 6 頁（禁則 0 違規、齊行擠入 1）＋export PDF 6 頁 **preflight 12/12 全綠**；親 Read 三跨主版代表頁：D 目錄頁（篇名嵌線斷開＋條目縮退＋引導線＋頁碼底錨對齊）、A 內文頁（頁碼跨節連續＝書頁 4 偶右頁、書眉採全書題名）、G 圖文頁（辰宇圖說＋photo-slot 佔位框），與各單頁樣張特徵逐項一致。
- Gate 4 獨立驗證：五章端到端測試以 PyMuPDF 驗頁序（D→B→A→C→G）、部扉大標逐字抽取、目錄頁碼記號、G 頁影像 XObject；組裝與 layout 斷言互證（paragraphs master 序列 vs pages master 序列）。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋R5 驗）：book@1 組裝全管線、CLI assemble、全書級單一 PDF/X 直向產出。
- v1 已知限制（GAPS #31）：images 僅書冊層級；直排橫排不可混（F 版權頁另出一份 PDF，承 #30 (b)）；目錄頁碼作者手填（自動生成 Phase 4）；單向產出（改章文件後重跑 assemble，無增量同步）。

### 待 Owner 真實素材驗收（R5）

- 全書樣張 out/book/*.png 六頁與 out/book.pdf 抽檢（本機重現：`python -m cjkfolio.cli assemble samples/book.json -o out/book.doc.json` → render／export-pdf）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 純邏輯離屏可驗項擇一：節式混向文件（per-section 書寫方向，讓 F 版權頁入冊、關 GAPS #30 (b)／#31 (b)）、圖說與照片相對位置樣式化置放、或多圖／任意矩形置入模型。app.py 真視窗 UI 接線待 Owner 真視窗回報批次。

## v0.46.0（2026-07-17，Sprint 51）Phase 2 主版指派核心（節式多主版文件：一份文件部扉＋內文跨主版成書）

### 新增

- [實作] 節式主版指派（Owner「最複雜架構先做」下，§6 Phase 2「主版指派」，Sprint 50 預定三選項取最複雜架構項；對標 InDesign 主版體系，採內容錨定節式而非頁鍵式，PLAN §10 Sprint 51 決議）：
  - `cjkfolio/document.py`：document@2 相容擴充 `Paragraph.master`（節首標記選配欄位：自本段起新頁並改用該主版，同名亦強制分頁＝顯式分頁原語；@1 使用即拒、非空字串驗證、序列化保留）；`doc.master` 降為首節預設主版（無標記文件＝單節，行為與現況完全一致）。
  - `cjkfolio/layout.py`：`_sections` 依節首標記切節、每節獨立 `flow_pages`（用該節主版網格，樣式行容量逐節換算；flow_pages 本體不動）、頁號跨節連續、節間段後空槽歸零（承跨頁歸零慣例）、`first_para_continues` 僅首節；`LayoutPage.master` 載體、未知主版快速失敗；`_toc_marks`／`_rule_breaks`／齊行統計改逐頁主版。
  - 兩後端逐頁主版：render `render_page`／pdf_writer `build_page` 依 `page.master` 解析主版，頁腳／frame／rule／figure 逐頁 gate（B 部扉頁自然無頁腳、A 頁頁碼書眉照常）。
  - `cjkfolio/editing.py`：七類操作（insert／delete／replace／apply_char_style／change_paragraph_style／split／merge，含 span 系列共用路徑）保留 `master`；split head 承節首身分（同 page_no 慣例）tail None、merge 前段存活（節首標記隨併入消失＝節合併語意）。
  - `editor/canvas.py`：互動層字格幾何依該頁主版（與 render 同源）。
  - 樣張 `samples/chapter-opening.doc.json`（自擬章首文件）：單一文件頁 1＝B 部扉＋頁 2＝A 內文。

### 變更

- `cjkfolio/images.py` `resolve_placed_images` 簽名改 `(doc, masters_by_page, base_dir)`（{版面頁號: MasterPage}，逐頁 figure 驗證）：G 節照片頁與 A 節內文同文件可置入，圖落無 figure 頁快速失敗（呼叫端 render／pdf_writer／tests 同步更新）。
- `LayoutPage` 註解勘正：「奇數＝右頁」為 Sprint 22 側別勘誤前殘留（正確為偶數書頁＝右頁），改為中性描述（版面頁號；書頁號另計）。

### 驗證

- 核心基線 `pytest spikes tests` **413 passed / 0 failed**（393→413，+20，新檔 tests/test_master_assign.py：document 欄位 3／layout 節式 8／editing 保留 4／兩後端 5）；typecheck EXIT=0；editor 離屏 smoke_check EXIT=0。
- 真實素材驗收（R5，自擬章首樣張，非參考書內容）：render 兩頁 PNG 親 Read 目檢（頁 1 B 部扉：篇序小標＋大標兩直行、大標首字頂低 6.02pt 特徵、無頁腳；頁 2 A 內文：3 段縮排段間正確、句逗置中、頁腳頁碼 2＋書眉「整理練習」＝書頁 2 偶右頁側別）；export PDF preflight **12/12 全綠**、禁則 0 違規。
- Gate 4 獨立驗證：PyMuPDF rawdict 字墨 cx 逐頁比對（頁 1 對 B 行軸 228.49／194.12〔Sprint 20 A 級量測值直接進斷言〕、頁 2 三行逐槽對 A 行軸，abs≤0.5pt）；頁腳 gate 以 PDF 文字抽取驗（B 頁無頁碼書眉、A 頁有）；直排逐字抽取逐字檢查。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋離屏＋R5 驗）：節式主版指派全管線（document／layout／兩後端／images／editing／canvas）、單一文件多主版成書、逐頁頁腳與 figure gate。
- [Shell]／待 Owner（GAPS #30／#19，離屏測不了）：選頁套主版的頁面面板 UI 未接線（app.py 真視窗工程）。
- v1 已知限制（GAPS #30）：節式內容錨定（頁鍵式指派屬編輯 UI）；直排橫排仍不可混一文件（F 版權頁分文件）；md／txt 匯入不產節首標記（章節結構屬 Phase 3）；節首＝強制分頁（頁級幾何本質，與 InDesign 同語意）。

### 待 Owner 真實素材驗收（R5）

- 真視窗多主版文件的畫布切頁與視覺對位（GAPS #19 批次）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 純邏輯離屏可驗項擇一：全書組裝管線（多章文件串接＝部扉＋內文＋目錄跨節成冊，直向產出全書級 PDF）、圖說與照片相對位置樣式化置放、或多圖／任意矩形置入模型。app.py 真視窗 UI 接線（含主版面板）待 Owner 真視窗回報批次。

## v0.45.0（2026-07-12，Sprint 50）Phase 2 圖片置入（灰階照片置入 G 圖文版 figure 保留區，兩後端 DeviceGray）

### 新增

- [實作] 圖片置入核心（Owner「最複雜架構先做」下編輯引擎完備後轉 §6 Phase 2「圖片置入」，承 Sprint 27 G-圖文版 photo-slot 保留區地基，PLAN §4.2／§9 灰階單 K）：
  - `cjkfolio/images.py`（影像領域單一事實來源）：`open_grayscale`（開圖轉 8-bit 灰階「L」＝§9 灰階單 K，缺檔／非影像快速失敗）、`resolve_placed_images`（doc.images → {版面頁號: (解析路徑, PIL)}，兩後端共用；主版無 figure／page 越界快速失敗；同路徑只載一次＝XObject 去重鍵）、`EmbeddedImage`（DeviceGray 影像 XObject 形態，emit 經 pdf builder duck-type stream 壓縮）。
  - `cjkfolio/primitives.py`：`fit_image_rect`／`ImageBox`（contain 等比縮放置中純幾何，scale=min(sw/w, sh/h)、四周留白置中、像素非正快速失敗）。
  - `cjkfolio/document.py`：document@2 相容擴充 `PlacedImage`（path＋版面頁號 1 起算）＋`Document.images`（序列化選配、同 page_no 慣例；path 空／page 非 ≥1 整數／page 重複快速失敗）。
  - render PNG `_draw_image`（figure_slot_rect＋fit_image_rect → 灰階 resize＋paste，取代 photo-slot 佔位框）＋`RenderResult.images_placed`＋`render_document(image_base_dir=)`。
  - pdf_writer `_image`＋`_Content.draw_image`（DeviceGray 影像 XObject：`cm` 縮放單位方陣＋`Do`，置 BT／ET 前獨立 q…Q 不觸文字塊；`/XObject` 進 Resources；同路徑跨頁去重單一 XObject）＋`PdfResult.images_placed`＋`export_pdf(image_base_dir=)`。
  - CLI render／export 加 `image_base_dir`（相對 doc 目錄解析）＋印置入圖數。

### 變更

- pdf_writer 逾 800 行上限（file-organization），`EmbeddedImage` 移入 `cjkfolio/images.py`（影像領域，emit duck-type `pdf.stream` 無循環 import），pdf_writer 787 行。
- preflight NOT_COVERED 同類更新（Gate 3，與 render／pdf 的「尚無影像置入」同步）：「影像色彩空間與解析度（v1 尚無影像置入）」→「影像解析度 PPI（Sprint 50 置入嵌原生解析度、未重採樣至 §9 300-350ppi；色彩空間由 color-cmyk-only 涵蓋，DeviceGray 合法、DeviceRGB 判失敗）」。

### 驗證

- 核心基線 `pytest spikes tests` **393 passed / 0 failed**（359→393，+34，新檔 tests/test_images.py：fit 幾何／灰階載入／document round-trip 與守門／resolve／EmbeddedImage／PNG 置入與方向／PDF XObject 去重 preflight bbox pixmap 方向）；typecheck EXIT=0（含 cjkfolio/images.py）；editor 離屏 smoke_check EXIT=0（render.py 僅追加、未改既有）。
- preflight 12/12 全綠不退步：DeviceGray 非 color-cmyk-only 禁列（DeviceRGB／CalRGB／CalGray／Lab／ICCBased 才禁）、灰階無 alpha 不觸 no-transparency。
- 真實素材驗收（R5，自擬灰階「照片」TOP/BOT 標記＋外框＋左上黑角，非參考書內容）：G 圖文版單頁置入 → PNG（render）與 PDF 獨立渲染（PyMuPDF，Gate 4 不同實作）兩後端目視完全一致、方向未翻轉（TOP 在上、黑角左上、漸層上暗下亮）、contain 等比置中、0 違規、preflight 12/12；執行工程師親 Read 兩渲染確認。
- Gate 4 獨立驗證：tests/test_images.py 以 PyMuPDF 獨立解析 XObject（/DeviceGray /Width /Height）、get_image_bbox 幾何≈fit_image_rect、get_pixmap 方向（上暗下亮）；PNG getpixel 影像中心值＋letterbox 背景白；兩後端置入矩形皆源自 fit_image_rect（同源）。繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3／R7）

- [實作]（基線＋離屏＋R5 驗）：灰階影像置入 figure 保留區、contain 置中、兩後端 DeviceGray 同源、跨頁去重、preflight 不退步。
- [Shell]／待 Owner（GAPS #29／#19，離屏測不了）：畫布拖放／縮放置入 UI 未接線（app.py 真視窗工程）。
- v1 已知限制（GAPS #29）：只置入主版 figure 保留區、每頁一張（任意矩形／多圖屬畫布 UI）；PPI 未強制重採樣（嵌原生解析度，§9 300-350ppi 未檢核，Phase 4／#18）；只灰階 DeviceGray（彩色 CMYK Phase 4）。

### 待 Owner 真實素材驗收（R5）

- 真視窗畫布拖放／縮放置入圖片的手感與視覺對位（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- 其他純邏輯離屏可驗項：圖說（辰宇落雁體）與照片相對位置的樣式化置放、或多圖／任意矩形置入模型；或 §6 Phase 2「主版指派」（per-page master）核心。app.py 真視窗 UI 接線（含圖片置入拖放）待 Owner 真視窗回報批次。

## v0.44.0（2026-07-12，Sprint 49）Phase 2 編輯引擎跨段字元樣式套用（apply_char_style over DocSpan）

### 新增

- [實作] cjkfolio/editing.py（**入 pytest 基線**）跨段字元樣式套用，承 Sprint 45 段內 apply_char_style 與 Sprint 48 DocSpan 跨段範圍機制，關 GAPS #26「跨段選取套字元樣式」子項（對標 InDesign 跨段選取套字元樣式，PLAN §4.1）：
  - `apply_char_style_span`（純文件層）：對跨段選取 [start, end) 逐段套（或清 None）字元樣式，段界不併（字元樣式不改段落數量，別於 delete_span）；頭段套 [start, len)、中間段整段、尾段套 [0, end)，各段委派段內 apply_char_style（逐 run 切割＋相鄰同樣式併合）；同段退化為段內 apply_char_style；空範圍 no-op；越界／逆序快速失敗（復用 _validate_span）。
  - `apply_style_span`（回路層，對稱 apply_style）：apply_char_style_span → layout_document 全文重排 → locate_cell 反查；新 caret＝span.end（游標停選取尾）；未知字元樣式名由 layout_document 守門（raise KeyError）。
  - `EditSession.apply_style_span`：委派統一經 _commit 入 undo／redo（同 delete_span／replace_span／apply_style）。

### 驗證

- 核心基線 `pytest spikes tests` **359 passed / 0 failed**（346→359，+13，新檔 tests/test_edit_style_span.py：apply_char_style_span 10／apply_style_span 2／EditSession 1）；typecheck EXIT=0（含 cjkfolio/editing.py）。
- 循 tests/ 分檔慣例（test_edit_style／test_edit_span 先例）：跨段字元樣式測試獨立為 tests/test_edit_style_span.py（自帶 fixture／helper，不建共享 conftest）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen`）EXIT=0：C1-C5 全過（editing.py 僅追加新函式與 EditSession 方法、未改既有函式與 editor/）。
- 真實素材驗收（R5，自擬多段內文樣張）：段 0「三房兩廳」到段 1「採光良好」跨段套「內文強調-明體W9」→ 段 0「兩廳」＋段 1「採光」掛強調、段界不併（仍 2 段）、範圍外保留原樣式；reflow 0 違規、游標停選取尾、端到端字格 char_style 流入渲染層（強調字＝「約三十坪採光」）、undo 清回原、redo 復原，皆基線斷言。
- Gate 4 獨立驗證：pytest 走狀態機斷言（runs／char_style／段數／堆疊），另寫獨立 probe 以不同路徑（直接印出觀察＋直接檢視 session._undo 深度）互證：跨段套樣式段界不併、中間段整段、同段退化＝段內 apply_char_style 等價、None 跨段清除、相鄰同樣式併合、apply reflow violations 空＋端到端強調字、session undo 清回 redo 復原、逆序 ValueError／未知樣式 KeyError 守門，probe 跑完即刪（scratchpad 不入 repo）；繁中標點 grep 無破折號。

### 誠實範圍（honest-planning R3）

- [實作]（基線＋離屏驗）：跨段字元樣式套用（逐段套段界不併＋相鄰同樣式併合）、apply_style_span 回路 reflow 與游標反查、EditSession undo／redo 整合。
- [Shell]／待 Owner（GAPS #28／#26／#19，離屏測不了）：app.py 尚未接線樣式面板（選取範圍→套字元樣式 UI，含跨段選取拖曳為真視窗工程）。

### 待 Owner 真實素材驗收（R5）

- 真視窗滑鼠跨段框選後套字元樣式的手感與視覺回饋（GAPS #19，離屏測不了）；Spike 1 對比圖抽檢（#10）、斷行逐行一致率（#23）Owner-hands-on。

### 下個 Sprint 預定範圍

- Phase 2 核心編輯 API（插入／刪除／替換／分裂／合併／undo-redo／字元樣式／段落樣式，段內與跨段）至此完備；後續為編輯 UI 接線（選取拖曳／樣式面板／Enter／Backspace／undo／redo app.py 真視窗工程，待 Owner 真視窗回報批次），或其他純邏輯離屏可驗項（如選取複製／貼上片段模型）。

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

- 10.5pt 訪談頁欄標變體（7 頁「欄標戊」）以主流 11.5pt 建模、未建獨立樣式。
- 資訊區多欄位動態列數以真書內容驅動；自擬 case-divider 示範兩欄位，機制不限欄位數。
- 續留 #13 其他剩項：F 版權頁真實版心 p178、目錄摘要層／【結語】變體、部扉裝飾框（美術資產）、B~G 其他扉頁逐頁量測。

## v0.32.0（2026-07-12，Sprint 37）C 個案扉頁 slot 0 黑 W7 欄標樣式建模（Owner 定案升級 C）

### 決策（honest-planning R1／R5 先量測再動工；Owner AskUserQuestion 定案升級 C）

- Owner 於 Sprint 36 收尾定案「升級定案 C」（完整重定 C 主版，推翻 Sprint 35「選 B 不重定模型」），啟動 GAPS #13 黑 W7 欄標專項。依 R1 先量測 33 個案扉頁完整幾何，找到真實目標才建模。**架構判定**：slot 0 欄標與 slot 1 大標自 inline 天頭起、block 軸相鄰堆疊，現有單欄線性流排（engine.flow_pages）可表達，本 Sprint 建模；資訊區（slot 5+ 欄位標籤／內文交替、slot 2~4 空欄）為空間分區超出線性堆疊，拆 Sprint 38（與 Owner 建議吻合）。

### 量測（A 級一手證據，本機紅線不入 repo）

- slot 0 欄標（cx 354.6）：DFHeiStd-W7、首字頂 92.1＝天頭 92.09（承 A）、縱向 4~6 字佔 block slot 0 一行；11.5pt×26 頁（資訊頁「欄標甲」等）主流、10.5pt×7 頁（訪談頁「欄標戊」）變體。字框頂天頭、墨頂差為字型 bearing（lead_offset 0，同部扉／大標先例）。
- slot 1 大標（cx 331.6）：NotoSans 17.9pt、首字頂 98.0（33 頁齊一）＝天頭＋bearing 5.9pt。
- 資訊區（cx 93~231＝slot 5~11）：欄位標籤 NotoSans 11.4pt（「【欄位甲】【欄位乙】」天頭 92.3）＋內文 DFMingStd 11.5pt（縮排 top 116.5）＋13pt DFHeiStd 中標交替；slot 2~4 空欄；列數 4~7（衆數 6）。

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
- 10.5pt 訪談頁欄標變體（7 頁「欄標戊」）以主流 11.5pt 建模、變體 note 記錄，未建獨立樣式。
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

- Q1 slot 0（cx 354.25±8）跨 33 頁：DFHeiStd-W7 11.5pt×26 頁／10.5pt×7 頁欄標「欄標甲／欄標乙／欄標丙／欄標丁／欄標戊」，33 頁全覆蓋、0 個 NotoSans 11.4、0 個 13pt。
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

- 33 個案扉頁（右頁頂 17.9pt 大標）右半頁頂 NotoSans 級數分布：全數僅 11.4pt（資訊列副標「【欄位甲】…」）＋17.9pt（大標），12.9pt 0 命中。
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
