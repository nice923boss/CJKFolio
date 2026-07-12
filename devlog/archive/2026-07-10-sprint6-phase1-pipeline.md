# Sprint #6（2026-07-10）Phase 1 開工：核心排版管線第一片，已完成

**範圍**：Phase 1 首個 Sprint（交接切片）：文件模型（段落＋樣式參照 JSON schema）、三層樣式讀取、《內在整理》起始模版（§4.2）、txt 匯入、spike 引擎產品化並排第一章輸出多頁 PNG、引擎字型換思源宋體 TC（GAPS #3 收尾）。

**完成**：

- ✅ 全書樣式掃描 [實作]（44896e1）：tools/scan_reference_styles.py 掃 179 頁 50 種 (font,size) 組合＋標題頁界（輸出 assets/reference/style_scan.json，本機）。定出全部樣式級數（A 級證據）、修正 §4.2 兩處（章名大標＝明體 W7、部扉大標＝明體 W9，皆 21.9pt）、界定第一章＝PDF 頁 19〜34、證實原書即用思源黑體 Medium 與辰宇落雁體（OFL）。
- ✅ cjkfolio 套件 [實作]（44896e1）：document（cjkfolio/document@1 驗證與往返）、styles（template@1 三層載入）、fonts（家族／字重解析，缺項 fallback＋去重警告）、engine（Spike 1 產品化，ParagraphSpec 承載每段行容量／縮排／段距／行槽寬）、layout（樣式幾何換算：字距同比例、行容量 floor、行槽寬 ceil；全頁禁則 runtime 檢查）、render（單頁 A5、奇偶頁鏡像版心、TTB／縱中橫／旋轉拉丁）、txt_import（空行切段全掛內文）、cli（import-txt／render）。
- ✅ 起始模版 [實作]（44896e1）：templates/neizai-zhengli.json，15 段落樣式＋9 字元樣式＋7 主版＋色票；級數與 source_font 全數取自掃描；A-內文版幾何取跨頁實測，B〜G 版心承 A 並以 evidence 欄誠實標示未逐頁量測（GAPS #13）。
- ✅ 第一章實排 [實作]（本機產出，不入 repo）：tools/extract_chapter.py 抽 PDF 頁 19〜34 → 79 段 5,408 字（assets/reference/chapter1.txt）→ CLI 匯入渲染 → out/chapter1/ 23 頁 A5 PNG（150dpi，思源宋體 TC Regular），禁則 0 違規。
- ✅ GAPS：#3 關閉；新增 #12（字型組缺五家族）、#13（B〜G 主版未實測＋橫排未支援）、#14（txt 抽取 v1 段落粒度限制）。

**測試成長**：15 → 61（+46：engine 移植與 ParagraphSpec 擴充 18、document 6、styles 5、fonts 5、txt_import 5、layout/render 7），0 失敗 0 退步。

**驗證**：
- typecheck：python -m py_compile spikes/spike1-vertical-core/\*.py cjkfolio/\*.py tools/\*.py → EXIT_CODE=0
- test：61 passed / 0 failed（python -m pytest spikes tests -q）
- 真實素材驗收（R5）：
  - 抽取正確性：Read assets/reference/chapter1.txt 前 30 行逐句核對，並渲染參考 PDF p19 原頁（本機 ch1_p19.png）Read 目檢比對，章扉題詞逐字吻合（含跨欄的「必須轉」「伴在身」）。
  - 渲染正確性：Read out/chapter1/page-001.png（奇數頁：13 行槽、行序右起、段首縮 2 字、段間空 1 槽、句逗置中、括號直排形、天頭約 32mm、書口約 21mm）與 page-002.png（偶數頁鏡像：行軸自訂口 25.58mm 推）目檢通過；幾何另有純數學單元測試（行軸座標、著墨落點）雙重驗證（Gate 4）。
  - 人類抽檢：**待 Owner 過目 out/chapter1/**（與 GAPS #10 併行，不阻擋下個 Sprint）。
- 除錯紀錄：抽取工具兩個真缺陷當場修正：(1) 以單一內文跨頁的版心底界做 y 過濾，題詞／內縮版塊超出底界的字被靜默截除（p19 實測至 y≈523），改為不設 y 界、靠級數帶＋裝飾字型過濾；(2) 對談頁版心整體內縮使逐欄誤判新段，改用每頁 body 欄頂眾數桶為縮排基準。均以探針腳本定位後修復並重驗。

**代決事項（依 Owner 全權授權，記入 PLAN §10）**：Phase 1 管線語言 Python、產品碼目錄結構、基線指令更新、樣式幾何換算規則、模版字型對映與 fallback 策略、§4.2 字重修正。

**下個 Sprint 預定範圍**：Markdown 匯入（標題層級直接對映樣式，結構化入口，§4.4 設計修正第 1 條）＋頁腳三件組與書眉（主版層，A-內文版）＋補下載字型組（GAPS #12：思源黑體 TC 優先，章節小標／個案大標即可實字重渲染）。PDF/X 寫出層與齊行（GAPS #9）列後。
