# Sprint #4（2026-07-10）Spike 3 後半＋Spike 5 真章重測，已完成（兩 spike 關閉）

**範圍**：Spike 3 後半（自製引擎單章重排延遲）；Spike 5 第二輪（參考書真章 AI 樣式分類重測，GAPS #7）。

**完成**：

- ✅ Spike 3 後半 [Spike→關閉]：perf_probe.py 量測自製引擎。**8,164 字長章：純邏輯重排（normalize＋tokenize＋禁則斷行＋流排）中位 7.67ms（20 輪）；3,140 字短章 2.84ms；首跨頁渲染（shaping＋柵格＋貼圖，150dpi）60ms**；規模化禁則 0 違規（286 行）。結論：Python 原型即達互動級，分章快取即足、無需增量重排；全書 5.7 萬字全重排推估約 60ms 級。與 Sprint 3 的 Vivliostyle 全書 26 秒合併，Spike 3 兩半皆有一手數據，關閉。
- ✅ Spike 5 端點可達性 [實作]：/v1/models 實測可達（qwen3.6-35b-a3b），金鑰全程讀自 local/（Grep 驗證原始碼零金鑰）。
- ✅ Spike 5 真章重測 [Spike→關閉]：real_chapter_test.py。實驗設計：排版真值由字型級數機械推導（明體大級=章名、黑體=小標、NotoSans=個案標、段首黑體標籤=訪談發言），AI 只看純文字；跨頁 6〜39 抽 220 段、分層抽樣 72 段（稀有類全收）、每批 12 段。**結果：嚴格 6 類 50%（36/72）、粗分類（標題類合併）69.4%；批次中位 5.6 秒／420 tokens，全書級約 20 批 2 分鐘，吞吐與成本可行。**
- ✅ 錯誤解剖（Read 兩輪明細 JSON）[實作]：約四成為「標題層級」單段純文字本質不可分（章名／小標／個案標皆短語，模型答案語意合理）；約四成為 6 類分類法涵蓋不了真書樣式（【欄位標籤】、圖注、目錄條目）之真值強塞；真正模型錯誤少數且多為可辯護的引文／訪談混淆。第一輪修正過抽取端兩缺陷（目錄整頁合併、橫排圖注被直排排序反轉）後重跑，結論穩定。
- ✅ 設計修正寫入 PLAN §4.4（四項定案）：結構優先（md/docx 層級不經 AI）、AI 聚焦粗分類、以模版實際樣式清單為候選集、8/8 不得外推宣稱。

**測試成長**：15 → 15（本 Sprint 為量測與實驗，無新增單元測試），0 失敗 0 退步。

**驗證**：
- typecheck：python -m py_compile spikes 全部 .py，EXIT_CODE=0
- test：15 passed / 0 failed
- 真實素材驗收（R5）：Spike 5 用參考書真章 220 段（僅本機）；Read 親驗兩輪 real_chapter_results.json 明細共 72+72 筆逐項比對；效能數據為 20 輪中位數非單次。
- known limitation：真值僅機械推導未經人工全量覆核（抽檢明細時已逐筆目視 72 筆之錯誤項）；模型跨批次對同型段落有不一致（【委託者】兩批分別答小標與內文），溫度 0.2 下仍存在。

**留證**：
- 時戳：2026-07-10
- 樣本：spikes/spike1-vertical-core/perf_probe.py 輸出（console）、spikes/spike5-ai-style-tagging/out/real_chapter_results.json（僅本機）
- commit：eba3b4b

**下個 Sprint 預定範圍**：Spike 4 授權桌面研究（AGPL-3.0 傳染範圍、進程隔離是否成立、對散布／SaaS 形態的約束，產出 spikes/spike4-license/report.md，含引證 URL）。完成後 Phase 0 五個 spike 全數有結論，做閘門判定並更新 PLAN。
