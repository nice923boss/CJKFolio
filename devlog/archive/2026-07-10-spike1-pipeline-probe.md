# 2026-07-10　Spike 1 啟動：直排 shaping 管線驗通

## 本日完成

1. **PLAN 執行層補強**（開源CJK排版編輯器-PLAN.md）：Phase 0 執行細則（spike 語言定為 Python、依賴成本表、素材與字型前置、順序與時間盒、驗收檢核清單、產出物結構）；修正 §5.2 與 §3.1 的先後矛盾；Spike 1 移除 ICU 硬依賴；GAPS 新增參考書版權紅線。
2. **專案結構建立**：spikes/、assets/、devlog/、GAPS.md。
3. **依賴安裝**：uharfbuzz 0.55.0、freetype-py（FreeType 2.13.2）；Python 3.12.10；pymupdf／Pillow／fontTools 原已有。
4. **管線驗通探針**：spikes/spike1-vertical-core/shape_probe.py 跑通。

## 探針實證結果（樣張：spikes/spike1-vertical-core/out/probe_vertical.png）

- PMingLiU（mingliu.ttc face[1]）可被 uharfbuzz 與 freetype 載入。
- TTB 直排 shaping：y_advance 全為負（往下推進），位置數學正確，渲染無重疊錯位。
- vert 字形替代實證：引號「」替代為直排形（gid 748→28812、749→28813）；**逗號句號不替代**。
- 人工抽檢：樣張目視確認，字序由上而下、引號旋轉正確、句逗置中。

## 關鍵發現（回饋進 PLAN）

繁中（台灣）排版句逗置於字面中央，橫直排同形，所以 PMingLiU 的 vert 不替代句逗是正確行為；日文（JLREQ）句逗在右上，規則不同。**禁則與標點擠壓引擎必須以 W3C CLREQ 繁中規則為準，JLREQ 僅參考。** 已修正 PLAN 檢核清單與證據附錄。

## 下一步（Spike 1 時間盒內）

1. 用 PyMuPDF 抽取《內在整理》代表跨頁文字，驗證直排 PDF 抽取順序。
2. 自寫逐字斷行＋禁則表（行首行尾禁則），排出 22 字／行、行距 23.0pt 的單欄。
3. 版心定位＋頁碼書眉，產出跨頁樣張與參考頁並排對比圖。

## 同日追加：Spike 5 AI 樣式指派 PoC（功能擴充評估）

使用者提出三項擴充：匯入 txt／md／docx、AI 自動排版初稿、AI 設定介面（Base URL／Key／Model）。評估結論全數可加，已寫入 PLAN §4.4 與 Phase 0／1／2／3。

- **Endpoint 實測**：私有 Tailscale endpoint（qwen3.6-35b-a3b，位址與埠僅存 local/ai-config.local.json，GAPS #6）當日可達，/v1/models 回 256K context、llama.cpp 後端。
- **PoC 結果**：spikes/spike5-ai-style-tagging/tag_probe.py，8 段自擬書稿段落（章名／小標／內文／引文／訪談發言／個案大標）六類分類 **8/8 全對**，temperature 0.2、共 398 tokens。
- **定位校正**：「AI 自動排版」校正為「AI 輔助樣式指派初稿＋人工校正」；AI 只回段落分類，版面幾何一律由排版引擎計算。
- **金鑰處理**：那組 Base URL／Key／Model 存入 local/ai-config.local.json（永不入 repo，GAPS #6）；產品介面預設空值。
- **未驗項（誠實標示）**：真實整章書稿的正確率與批次耗時（GAPS #7，Spike 5 剩餘時間盒 2 天）。

## 留證

- 時戳：2026-07-10
- 樣本：spikes/spike1-vertical-core/out/probe_vertical.png、spikes/spike5-ai-style-tagging/tag_probe.py（console 輸出 8/8）
- commit：無（專案尚未 git init，見 GAPS #5）
