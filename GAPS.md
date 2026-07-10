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
| 14 | 第一章 txt 抽取 v1 已知限制：對談發言轉換無縮排訊號，p31〜34 合併為單一 914 字段；扉頁資訊列與正文黏連；圖說單字標籤剔除（34 筆已列 log）。**2026-07-11 Sprint 8 補**：md 抽取素材在發言人標籤後殘留 U+0007 控制字元 7 處，已由 engine.normalize 統一剝除（Cc 類不進排版流）。**Sprint 9 補**：抽取層同步剔除 Cc 並列計數；對談發言標籤（本章 PDF 實測為明體 W9）已由行內強調標記自動掛「內文強調-明體W9」，視覺區隔恢復 | txt 為無結構入口（PLAN §4.4 本就全掛內文）；發言切分需樣式資訊 | 僅影響本機驗證素材的段落粒度，不影響產品程式碼；渲染與禁則驗證不受影響 | md 匯入（結構化入口，Phase 1 後續 Sprint）與 Phase 3 AI 指派後以樣式驅動重驗 | 黃政文 |
| 15 | ~~PDF 寫出層 v1 尚非完整 PDF/X-1a~~ **已關閉（2026-07-11 Sprint 10）**：OutputIntent（預設 JC200103 registry 識別，依 ISO 15930-1 免嵌 DestOutputProfile；自訂識別強制嵌 CMYK prtr ICC）＋XMP／GTS 兩鍵＋Trapped＋ModDate＋header 1.3 落地；自寫機械 preflight（12 規則）與 pdffonts 全綠 | ICC 授權查證：Adobe profile 散布須轉嫁 EULA 條款（不適合開源 repo），registry 識別路線零授權負擔 | 結構層 X-1a:2001 合規（機械檢查認定）；veraPDF 不支援 PDF/X（實查），認證級佐證轉列 #18 | 已完成 | 黃政文 |
| 18 | Acrobat／印廠認證級 preflight 未跑 | 本機無 Acrobat Pro；veraPDF 僅驗 PDF/A／UA 無 X flavour（2026-07-11 官方文件實查）；自寫檢查器未涵蓋疊印、影像、TAC（NOT_COVERED 誠實列印） | 「preflight 全綠」目前依自寫機械檢查器＋pdffonts；對外宣稱 X-1a 合規前需 Acrobat preflight 或印廠回報佐證 | Phase 4 preflight 面板／首次送印打樣 | 黃政文 |
| 16 | 頁面鏡像與頁腳奇偶以「版面頁號」判定，--first-page 為偶數起頁（如第一章書頁 20）時，左右頁側別與真書相反（PNG 與 PDF 兩後端行為一致） | v1 的 first_page 僅代入頁碼文字，鏡像語意未跟書頁號 | 本機樣張的書眉／頁碼側別與真書鏡像相反；幾何自洽，禁則與版心不受影響 | 章節結構／主版指派 Sprint 定案（鏡像改依書頁號），需同步調整既有測試與樣張 | 黃政文 |
| 17 | PNG 渲染對缺字（gid 0）沉默畫 .notdef；PDF 寫出層已警告不沉默 | Sprint 8 僅在新後端加警告，PNG 路徑未動（外科手術範圍） | 純 PNG 驗證流程可能漏看缺字；PDF 匯出會列警告補位 | 渲染後端統一 placement 層時一併補 PNG 缺字警告 | 黃政文 |
