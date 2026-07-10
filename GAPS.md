# GAPS 落差登記簿

> 依 PLAN 第 8 節與 R7 規則建檔。發布前須清空，或在 release note 以「Known Limitations」公開承認。
> 每條含：項目、原因、影響、補完時點、責任人。

| # | 項目 | 原因 | 影響 | 補完時點 | 責任人 |
| --- | --- | --- | --- | --- | --- |
| 1 | 參考書《內在整理》內容版權（紅線） | 出版社版權物，僅限本機 spike 驗證 | 開源 repo 與公開樣張不得含其文字／圖像；公開測試素材須另備自由散布文本 | 開源釋出前備妥替代文本 | 黃政文 |
| 2 | 華康／Monotype 商用字型不可內建 | 商業授權 | 編輯器只內建 OFL／政府開放授權字型；匯出時做授權檢查提示 | Phase 4 授權檢查功能 | 黃政文 |
| 3 | ~~spike 階段用系統新細明體驗管線~~ **已關閉（2026-07-10 Sprint 6）**：Phase 1 產品管線（cjkfolio）全程改用 assets/fonts/ 思源宋體 TC，第一章 23 頁樣張親驗；spike 舊樣張維持 PMingLiU 屬歷史紀錄，不回改 | PMingLiU 隨 Windows 授權，不可隨產品散布 | 產品輸出不再依賴系統字型 | 已完成 | 黃政文 |
| 4 | Spike 2b（TeX Live）暫不安裝 | 數 GB 安裝成本，2a Vivliostyle 不達標才裝 | LuaLaTeX 路線暫無一手驗證數據 | Spike 2a 結果出爐後決定 | 黃政文 |
| 5 | ~~專案尚未 git init~~ **已關閉（2026-07-10）**：依 Owner 全權授權代決，git init 本機 repo（無遠端），.gitignore 落實紅線（local/、assets/reference/、內在整理-*.pdf、spikes/*/out/ 不入 repo） | 使用者授權「需要問的直接代決」 | dev-log 自此含 commit hash | 已完成 | 黃政文 |
| 6 | AI 金鑰與私有 endpoint（紅線） | 私有 Tailscale 位址與金鑰，他人連不到也不可洩漏 | 只存 local/ai-config.local.json，git init 時 local/ 進 .gitignore；產品介面預設空值 | git init 時落實 .gitignore | 黃政文 |
| 7 | ~~Spike 5 僅過第一輪~~ **已關閉（2026-07-10 Sprint 4）**：真書 72 段重測完成（嚴格 50%、粗分 69.4%、吞吐可行），四項設計修正入 PLAN §4.4；AI 指派維持 [Spike]，正式 [實作] 於 Phase 3 依新設計驗收 | 真章重測完成 | 「8/8 全對」不得對外宣稱 | 已完成 | 黃政文 |
| 8 | 樣張頁腳字型替位：Gill Sans MT 代 GillSans-Light、標楷體代華康手札體 | 原字型無授權（GAPS #2 同源） | 頁腳字形風格與參考書不同，位置與級數對位正確 | Phase 1 內建 OFL 字型組時改用可散布字型 | 黃政文 |
| 9 | Spike 1 引擎為等距網格，無 InDesign 式齊行（justification）微調與標點擠壓變寬 | 齊行演算法超出 spike 時間盒，且本書實測無半形擠壓 | 斷行點與參考書偶有 ±1 字漂移（行數與版面結構一致） | Phase 1 直排引擎補齊行與約物擠壓 | 黃政文 |
| 10 | Spike 1 人工抽檢僅 AI 全圖掃描，Owner 未抽檢 | Owner 尚未過目樣張 | R5 真實素材驗收的人類抽檢項未滿足，Spike 1 不得關閉 | Owner 檢視 spikes/spike1-vertical-core/out/spread_comparison.png 後打勾 | 黃政文 |
| 11 | Spike 2a 的 CMYK／PDF-X 後處理未驗證 | 本機無 Ghostscript（vivliostyle --preflight press-ready 依賴其一） | Vivliostyle 直出為 RGB／灰 PDF 1.7，PDF/X-1a 轉換品質無一手數據 | Owner 同意安裝 Ghostscript 後補測，或 Phase 1 自寫 PDF 後端時一併驗 | 黃政文 |
| 12 | 內建字型組尚缺全字庫正楷體 TW-Kai（題詞、目錄條目）與全字庫正宋體（仿宋引文替代）。**2026-07-11 Sprint 7 已入庫**：思源黑體 TC Medium/Bold、辰宇落雁體、jf open 粉圓（皆驗 vert，來源與重現指令見 FONTS.md） | 全字庫下載包大（國發會 Open_Data 整包），對應樣式尚未進渲染驗收 | 楷書／仿宋樣式仍 fallback 思源宋體並列警告（不沉默）；另思源宋體無 Bold 檔，明體 W7 以 Heavy 替（渲染警告） | 題詞／引文樣式驗收 Sprint 一併下載驗證 | 黃政文 |
| 13 | 起始模版 B〜G 主版版心承 A 未逐頁實測；個案中標 11.4/12.9pt 兩變體未定、西文書名-ACaslon 全書掃描未見著字；渲染器未支援橫排（版權頁-CIP） | 扉頁與特殊頁佈局量測超出 Sprint 6 時間盒 | 模版對應頁型的版面幾何未驗證，僅 A-內文版有 A 級證據；橫排樣式渲染會明確報錯（不沉默） | Phase 1〜3 對應功能（主版指派、橫排、從參考萃取）Sprint 逐一量測補齊 | 黃政文 |
| 14 | 第一章 txt 抽取 v1 已知限制：對談發言轉換無縮排訊號，p31〜34 合併為單一 914 字段；扉頁資訊列與正文黏連；圖說單字標籤剔除（34 筆已列 log） | txt 為無結構入口（PLAN §4.4 本就全掛內文）；發言切分需樣式資訊 | 僅影響本機驗證素材的段落粒度，不影響產品程式碼；渲染與禁則驗證不受影響 | md 匯入（結構化入口，Phase 1 後續 Sprint）與 Phase 3 AI 指派後以樣式驅動重驗 | 黃政文 |
