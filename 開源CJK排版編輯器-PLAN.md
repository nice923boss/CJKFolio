# 開源 CJK 直排書冊排版編輯器 PLAN

> 一套對標 InDesign、讓創作者免月費也能做出版級直排書冊的開源編輯器。
> 以出版社印製的《內在整理》（148×210mm A5 直排、CMYK；2026-07-11 實測交印檔無 PDF/X 識別，見 §1）為品質驗收標竿。
>
> 規劃日期：2026-06-16　規劃紀律：證據先行、不浮誇、實作與空殼分清、未驗證項明確標示。
> 修訂：2026-07-10 執行層補強（Phase 0 執行細則、spike 語言與依賴、素材版權紅線、驗收檢核清單）；同日擴充內容匯入與 AI 輔助樣式指派（§4.4、Spike 5，PoC 8/8 已驗證）。
> 修訂沿革（2026-07-12 精簡）：Phase 0 五 spike 條件性通過、Phase 1 各 Sprint（2〜26）進度／代決／勘誤，統一見 §6 里程碑、§10 決議紀錄與 devlog/；逐 Sprint 摘要不再累積於檔頭。

---

## 0. 一句話結論與技術限制（先說限制）

**結論：這個縫隙真實存在，技術上可達成，但這是一個以「年」為單位、需要分階段驗證的系統工程，不是寫一個匯出按鈕就能成的小程式。**

三個必須先講清楚的技術限制：

1. **不要正面複製整個 InDesign。** 已有 Scribus 做開源 DTP 二十多年，它的直排需求票（issue #1778）從 2005 年立、到 2026 年從未動工。要在「全功能」上贏 InDesign 是整個團隊數年的工程量且大概率失敗。正確打法是鎖定 InDesign 收最貴租金、Scribus 又最弱的縫隙：**中文／日文直排書冊**，做到出版級後再橫向擴張。

2. **CJK 直排的難點，90% 不在「選哪個底層函式庫」，而在你必須自寫的「直排版面引擎」這一層。** HarfBuzz 只把字碼變成字形與位置；禁則處理（行首行尾禁則）、標點擠壓（約物詰め）、縱中橫（tate-chu-yoko）、版心對齊這些出版級規則，沒有任何現成開源元件能直接給你，必須自己實作。這既是最大工程量，也是最大的差異化價值。

3. **「與參考書一模一樣」是錯誤目標，要重新定義。** 逐像素一致需要相同的商用字型（華康字型，授權問題）與相同演算法。正確目標是：**出版級等效品質＋相同設計語言＋可複製可修改的樣式模版＋印刷廠 preflight 全綠的 PDF/X**。

---

## 1. 參考書《內在整理》逆向分析（A 級一手證據）

以 PyMuPDF 親自量測、並渲染代表頁視覺確認。這是本 PLAN 的需求地基。

| 項目 | 量測結果 |
| --- | --- |
| 製作軟體 | Adobe InDesign 21.2（Windows）→ Adobe PDF Library 18.0，PDF 1.4 |
| PDF/X 識別 | **無**（2026-07-11 Sprint 10 實測：Info 無 GTS 鍵、無 OutputIntents、含 SMask 透明、TrimBox 與 ArtBox 並存；交印為一般 PDF 1.4。產品仍依 §9 預設輸出 X-1a:2001） |
| 開本 | 148×210mm（A5 直式右翻書），179 頁 |
| PDF 呈現 | 177 頁為 296×210mm 跨頁對開（148×2），僅首末 2 頁單頁 |
| 書寫方向 | **直排（縱書 vertical-rl），右至左頁序與欄序**；側別（2026-07-11 Sprint 22 三向實測）：**偶數頁＝右頁（頁碼書口右＋書名書眉）、奇數頁＝左頁（頁碼書口左＋章節副標）** |
| 內文 | 華康明體 DFMingStd-W3 11.5pt，行距＝欄距精確 23.0pt（200%），滿行 32 字（2026-07-10 逐字實測修正，原記「約 22 字」為每頁行數之誤），字距 12.08pt（字級的 1.05 倍），主力 57,536 字 |
| 版面網格（2026-07-10 逐字實測） | 段首縮排 2 字、段間空 1 行槽、每頁 13 行槽；標點無半形擠壓，句逗置中，僅 ±0.4pt 齊行微調 |
| 版心 | 天頭 32.49mm（實測相符）、地腳 40.5mm、書口 21.0mm（p.030-031 跨頁實測；原記切口 13mm 待多頁複測定案） |
| 文字色 | #231f20（暖黑，非純黑 K100） |
| 影像 | 78 張灰階＋16 張 CMYK，確認 CMYK 印刷流程 |
| 手繪線稿 | 向量路徑（單頁達 252 path），非點陣 |

**完整字型體系（即樣式模版的來源）：** 明體 W3／W7／W9、黑體 W3／W5／W7／W9、仿宋 W4、楷書 W3／W5、手札體 W5、思源黑體 Medium；拉丁字 GillSans-Light、PepitaMT 手寫體、TimesNewRoman、ACaslonPro-Bold、辰宇落雁體、PMingLiU。

**精緻設計細節（使用者所指「頁碼旁的精心排版」）：** 切口下角的書眉頁腳三件組（頁碼 GillSans 8pt ＋ 書名／章節副標 手札體 8pt ＋ 個案頁的 Case N PepitaMT 9pt 手寫編號）、部扉的雙線菱形裝飾框、目錄的水平虛線分隔與直排數字頁碼、版權頁是全書唯一橫排 CIP 細框、訪談對話以黑體發言人標籤（「廖：」「鄧：」）區隔。

---

## 2. 市場定位與縫隙（為什麼是這個利基）

證據顯示「免費 ＋ 所見即所得（WYSIWYG）＋ 出版級 CJK 直排」三者交集，目前**沒有任何一個產品同時滿足**：

| 工具 | 免費 | 所見即所得 | 出版級 CJK 直排 |
| --- | --- | --- | --- |
| Adobe InDesign | 否（月費 $20.99 起） | 是 | 是（業界標竿） |
| Affinity Publisher | 買斷 | 是 | **否（官方明說無計畫加直排）** |
| QuarkXPress | 買斷 $699 | 是 | 是 |
| Scribus | 是 | 是 | **否（直排票 21 年未動工）** |
| Vivliostyle | 是 | **否（要寫 CSS/Markdown）** | 是 |
| LibreOffice／Inkscape | 是 | 部分 | 否（非書冊流排） |

**戰略判讀：** Vivliostyle 已證明「CSS Paged Media 能做出出版級 CJK 直排書」，所以技術風險被降低（有開源前例可借鏡）；缺的不是技術，是把它包進一個免費、視覺化、書冊取向編輯器的人。這就是本專案要佔的位置。目標用戶：華文獨立出版、自費出版、ZINE、同人誌、被 Adobe 月費勸退又需要直排的創作者。

---

## 3. 核心架構決策

### 3.1 三條路線與建議

| 路線 | 互動模型 | 直排品質上限 | 工程量 | 風險 |
| --- | --- | --- | --- | --- |
| A 真 WYSIWYG 自製引擎 | 畫布直接操作（InDesign 模型） | 理論最高 | 最大（等於重寫 InDesign 核心） | 易爛尾 |
| B 樣式標記＋即時預覽 | 編輯標記，引擎渲染 | 中上（受瀏覽器實驗 API 限制） | 最小 | CMYK／PDF-X／出血是瀏覽器弱項 |
| **混合（建議）** | **畫布直接操作，底層呼叫專業排版核心** | **可達高** | 中大，風險分散 | 畫布與核心同步的介面契約難 |

**建議：混合路線。** WYSIWYG 畫布（路線 A 的互動體驗）＋ 專業文字排版核心（路線 B 的排版品質），中間用穩定的「版面盒模型 ↔ 段落排版器」介面隔開。畫布管版面與互動，排版核心管文字流與直排細節，CMYK／PDF-X 走獨立 PDF 後端。**此結論必須先過 Phase-0 spike 才能寫進正式里程碑（見第 6 節）。spike 通過前，本 PLAN 不對「幾個月做到」做任何承諾。**

### 3.2 排版核心選型（含證據評分）

評分 1〜5（5 最佳）。皆有真實引用佐證。

| 核心 | CJK 直排 | 印刷就緒 | 樣式系統 | GUI 整合 | 授權生態 | 一句話定位 |
| --- | --- | --- | --- | --- | --- | --- |
| **LuaLaTeX + luatexja** | 4 | **4** | 4 | 3 | 4 | 直排與印刷品質天花板最高，但編譯式非互動 |
| **Vivliostyle** | 4 | 3 | **5** | 4 | 3 | CSS 直排最完整有商業實績，但 AGPL＋CMYK 靠後處理 |
| **SILE** | 3 | 3 | 2 | 3 | 3 | 直排是引擎級一等公民但半成品，MIT 授權好 |
| **Typst** | **1** | 2 | 4 | **5** | 4 | 直排只在 RFC 階段，近期不能直出直排，但引擎與即時預覽最強 |

**選型建議（分軌）：**

- **PDF 高品質輸出後端**：優先 Vivliostyle（CSS↔樣式模版天然對映、直排成熟、有商業出版實績），或 LuaLaTeX-ja（印刷品質最高）。兩者皆須先過驗收 spike。
- **互動排版核心**：長期走自製直排引擎（HarfBuzz vert/vrt2 ＋ ICU 斷行 ＋ 自製禁則／約物擠壓層），這是產品的護城河，無法外包給現成引擎。
- **Typst** 列為長期觀察：授權（Apache-2.0 可商用內嵌）與即時預覽生態最佳，待其上游直排 RFC（#5908）落地後可重估，或由本專案貢獻直排能力。

### 3.3 誠實校正（對使用者原始假設）

| 原始假設 | 誠實校正 |
| --- | --- |
| 自建一套排版程式 | 自建「編輯器與直排版面引擎」，但 PDF 輸出與字型塑形站在成熟元件上（HarfBuzz／FreeType／LittleCMS／既有排版核心），不重造輪子 |
| 匯出 PDF 就和參考一模一樣 | 目標是出版級等效品質＋相同設計語言＋印刷廠 preflight 全綠，非逐像素一致 |
| 分析字型樣式做成模版 | 此為核心功能（第 4 節），且可從參考 PDF 萃取起始模版、可新增可修改 |

---

## 4. 樣式模版系統設計（核心功能）

這是使用者最在意的需求：分析書的文字類型樣式、做成可選取的模版、未來可新增可修改。對標 InDesign 的段落樣式／字元樣式／物件樣式／色票／主版體系。

### 4.1 三層樣式模型

1. **段落樣式（Paragraph Style）**：字型、級數、行距、對齊、直排／橫排、縮排、段前段後距、禁則等級、標點擠壓規則、首字下沉。套用於整段。
2. **字元樣式（Character Style）**：在段落內局部覆寫字型／級數／色／縱中橫。如發言人標籤、內文強調、職稱括註。
3. **主版（Master Page）**：版心、欄數、書眉頁腳、頁碼規則、出血、對開鏡像。

### 4.2 從《內在整理》萃取的起始模版（已分析，內建範本）

**段落樣式（15 種）：** 內文-明體直排、訪談發言body、引文-仿宋語錄、題詞-楷書、推薦序大標、章節小標-黑體、個案大標-NotoSans、個案中標、部扉大標-明體、章名大標-明體W9、標籤-篇序小標、目錄-篇章條目、版權頁-CIP橫排、旁注-手札圖注等。各帶字型／級數／行距／對齊／場景。

**字元樣式（9 種）：** 發言人標籤-黑體、內文強調-明體W9、角色註記-仿宋小字、頁碼數字-GillSans、Case編號-手寫拉丁、書眉副標-手札體、裝飾大字-辰宇落雁體、拉丁正文-Times、西文書名-ACaslon。

**主版（7 種）：** A-內文版（雙頁書眉頁腳鏡像）、B-部扉、C-個案扉頁、D-目錄、E-序文版、F-版權頁（單頁橫排）、G-圖文版。

**色票：** 暖黑 #231f20（內文，建議印刷轉單 K90-92）、紙白、灰階 K、CMYK 四色、虛線灰。

**實作與修正（2026-07-10 Sprint 6）：** 起始模版落地為 templates/neizai-zhengli.json（cjkfolio/template@1），級數與字型參數取自全書 (font,size) 掃描（tools/scan_reference_styles.py，A 級一手證據）。掃描修正兩處：章名大標為明體 **W7** 21.9pt（原記 W9）、部扉大標為明體 **W9** 21.9pt；另證實原書即用思源黑體 Medium 與辰宇落雁體（皆 OFL，可直接內建）。字型對映採 §8 可散布字型組並以 source_font 記原書字型；未入庫家族 fallback 思源宋體並警告（GAPS #12）。

### 4.3 模版管理（新增／修改／複用）

- **樣式面板**：列出所有段落／字元樣式，點選即套用；雙擊編輯；改樣式即全書套用（與 InDesign 一致）。
- **樣式繼承**：基底樣式 ＋ 子樣式覆寫（類 CSS 但不層疊混亂）。
- **模版庫**：整本書的樣式＋主版＋色票打包成「書系模版」，可另存、匯入、匯出、套用到新書。
- **從參考萃取**：匯入一份 PDF／InDesign 文件，自動分析字型／級數／用色，提出起始段落樣式清單供使用者命名與調整（本 PLAN 第 1 節的分析流程即為此功能的原型）。
- 序列化格式：人類可讀的結構化檔（如 JSON／TOML），利於版本控制與分享。

### 4.4 內容匯入與 AI 輔助樣式指派（2026-07-10 擴充）

書稿的實際入口。匯入原始文稿後由 AI 建議「段落 → 樣式」對映，套用模版庫產生排版初稿，人工校正後定稿。

**匯入格式**：
- txt：按空行切段，先全掛「內文」。
- Markdown：標題層級、引文、強調直接對映段落／字元樣式，是結構資訊最完整的入口。
- docx：解析 OOXML 段落與 run 屬性（python-docx 級的解析，不依賴 Word COM），Word 樣式名與粗斜體轉為樣式建議。

**AI 輔助樣式指派（分工鐵律）**：
- AI 只做內容結構識別（章名／小標／內文／引文／訪談發言／個案標題），輸出「段落 → 樣式名」JSON 對映；版面幾何（行距、版心、斷行、禁則）一律由排版引擎確定性計算，不採用 AI 輸出的任何數字。
- 定位是「初稿＋人工校正」，介面提供逐段確認與批次改派，不宣稱全自動。
- 長書稿（5 萬字級）分章批次送，單批數千字。
- AI 為選配增強：未設定 API 或離線時，核心排版與手動樣式指派完全可用。

**LLM 介接**：OpenAI 相容 API，設定介面三欄位（Base URL／API Key／Model），存本機設定檔。回應解析防禦：剝 `<think>` 推理殼再抽 JSON；失敗即降級為「全部內文＋人工指派」，不擋流程。
- **金鑰紅線**：私有金鑰與內網位址只存使用者本機設定檔（local/，不入 repo），開源程式碼與公開文件零金鑰，產品介面預設空值。

**可行性一手證據（Spike 5，2026-07-10）**：私有 qwen3.6-35b-a3b（llama.cpp、256K context、實測可達）對 8 段自擬書稿段落做六類樣式分類，8/8 全對，共 398 tokens。腳本：spikes/spike5-ai-style-tagging/tag_probe.py。

**真章重測結論（Spike 5 第二輪，2026-07-10 Sprint 4，real_chapter_test.py）**：以參考書跨頁 6〜39 抽 220 段、排版真值（字型級數機械推導）分層抽樣 72 段重測。結果：嚴格 6 類 50%、粗分類（標題類合併）69.4%；批次吞吐 12 段 5.6 秒／約 420 tokens，全書級約 2 分鐘，**吞吐與成本可行**。錯誤解剖：約四成是「標題層級」單段純文字本質不可分（章名／小標／個案標皆為短語，模型答案語意合理）、約四成是 6 類分類法涵蓋不了真書樣式（欄位標籤、圖注、目錄條目）之真值強塞。**設計修正（定案）**：
1. md／docx 匯入時標題層級由結構直接對映，**不經 AI**；純 txt 才用 AI 建議。
2. AI 建議聚焦粗分類（標題類／內文／引文／發言），標題「層級」由使用者在校正介面批次改派（本節「初稿＋人工校正」定位不變）。
3. Phase 3 的 AI 指派須以「該書模版的實際樣式清單」為候選集，非固定 6 類；欄位標籤、圖注等樣式一併納入。
4. 「8/8 全對」僅適用於自擬乾淨段落，不得外推為產品宣稱。

---

## 5. 系統架構與技術棧

### 5.1 分層架構

```
┌─────────────────────────────────────────────┐
│  GUI 編輯器（畫布 + 面板：樣式/主版/色票/圖層/資產）  │
├─────────────────────────────────────────────┤
│  文件模型（語意化內容 + 樣式參照 + 主版指派）        │
├─────────────────────────────────────────────┤
│  直排版面引擎（流排/斷行/禁則/約物擠壓/縱中橫/版心）   │  ← 護城河，自製
├─────────────────────────────────────────────┤
│  字型塑形 HarfBuzz(vert/vrt2) + 柵格 FreeType     │
├─────────────────────────────────────────────┤
│  色彩管理 LittleCMS  │  PDF/X 匯出後端           │
└─────────────────────────────────────────────┘
```

### 5.2 推薦技術棧（兩條路線，依團隊技能擇一；渲染／塑形／色彩／PDF 邏輯共用）

> 執行校正（2026-07-10）：本節技術棧是 Phase 2（編輯器）的候選決策，不是 Phase 0 的起點。Phase 0 spike 一律用 Python 驗證排版規則（見第 6 節執行細則），正式引擎語言待 spike 結論於 Phase 1 再定，避免未驗證前先付 C++／Qt 的建置與迭代成本。

| 層 | 主推（C++ 路線） | 替代（Rust 路線） | 授權 |
| --- | --- | --- | --- |
| GUI 框架 | **Qt 6 ＋ QGraphicsView 畫布** | Slint（royalty-free）或 egui | LGPLv3／MIT |
| 畫布渲染 | **Skia** | Skia／tiny-skia | BSD-3 |
| 文字塑形 | **HarfBuzz** | harfrust／harfbuzz-rs | MIT |
| 字型柵格 | **FreeType** | skrifa＋fontations | FTL／Apache-2.0 |
| 色彩管理 | **Little CMS（lcms2）** | 同（FFI） | MIT |
| PDF/X 匯出 | 自寫寫出層，參考 PoDoFo | 同 | LGPL／MPL |

**為何主推 Qt 6 + QGraphicsView：** 編輯器本質是「畫布上數千個可選取／拖曳／變形的文字框與圖框」，這正是 QGraphicsView 的設計目標（Scribus 本身即 Qt）；Qt 6 LGPLv3 採動態連結即可保持應用自由授權；CJK 輸入法（IME）在 Qt 是一等公民。Rust 路線授權更寬鬆但需避開 IME 有缺陷的框架（Slint／GTK4／fltk 正確處理 IME，Cushy／Floem 有缺陷）。Electron 不推：contenteditable＋直排＋IME 游標定位不穩，且印刷硬需求（CMYK／PDF-X／出血）非瀏覽器原生強項。

---

## 6. 分階段里程碑

> 每階段標示交付物類型：[Spike] 探索驗證、[實作] 完整可用有真實素材驗收、[Doc] 純文件。
> [Shell] 介面在實作空殼，不算完成、不計入對外承諾。
> 時程為估計區間（自啟動起算），Phase-0 通過前不對後續做硬承諾。

### Phase 0：可行性驗證 Spike（4〜6 週）[Spike]　★決策閘門

本專案最大風險集中在此，先驗證再投入。

- **Spike 1 直排版面核心**：用 HarfBuzz vert/vrt2（Python uharfbuzz）＋ 自寫逐字斷行與最小禁則／約物擠壓，排出《內在整理》一個真實跨頁（直排明體 11.5pt 內文 32 字／行、含直排中橫排頁碼、書眉頁腳），依下方執行細則的檢核清單逐項驗收。**進度（2026-07-10 Sprint 2）：檢核清單七項證據齊備（引擎 15 項單元測試、真實跨頁 0 禁則違規、並排對比圖、縱中橫示範條），待 Owner 人工抽檢後關閉。**原規劃的 ICU 斷行降為非必要：CJK 書冊斷行＝逐字可斷＋禁則表調整，無需詞典斷行，僅拉丁連續串不拆（簡單規則即可），避開 PyICU 在 Windows 的安裝成本。
- **Spike 2 輸出後端**：同一份內容分別走 Vivliostyle 與 LuaLaTeX-ja，產 PDF/X，比較直排品質、CMYK、字型嵌入、preflight 結果。**進度（2026-07-10 Sprint 3）：2a Vivliostyle 核心驗證通過：直排（vert 形、句逗置中、strict 禁則 0 違規、縱中橫、拉丁旋轉）、TrimBox 148×210 精確＋BleedBox 154×216＋裁切標記、字型 100% 嵌入子集化（pdffonts 全綠、無 Type3）、PDF Catalog /Direction /R2L 右翻。CMYK／PDF-X 後處理未驗（本機無 Ghostscript，GAPS #11）。2b LuaLaTeX 依 GAPS #4 維持不裝（2a 達標）。**
- **Spike 3 效能**：依賴 Spike 1、2 產出，殿後執行。量測候選輸出後端的全書（179 頁級）編譯時間，與 spike 引擎的單章重排延遲，決定是否需增量重排與分章快取。**進度（2026-07-10 Sprint 3）：Vivliostyle 全書級實測 192 頁 26.0 秒（約 7.4 頁/秒，含瀏覽器啟動），匯出路徑可接受。（Sprint 4）spike 引擎單章重排實測：8,164 字章純邏輯重排中位 7.67ms、首跨頁渲染 60ms（Python 原型即互動級）；結論為分章快取即足、無需增量重排，Phase 2 以背景渲染＋快取設計。Spike 3 關閉。**
- **Spike 4 授權**：釐清 Vivliostyle AGPL-3.0 對產品形態（散布／SaaS）的約束，確認進程隔離或商業授權方案。**完成（2026-07-10 Sprint 5，spikes/spike4-license/report.md）：Core 與 cli 皆 AGPL-3.0（package.json 實查）；官方 FAQ 明言獨立程式可與專有程式並用；GPL FAQ 臂長準則下「CLI 子程序＋檔案介面」不受傳染，編輯器主體可用自有授權；散布採「首次使用隨裝」最乾淨；禁止 in-process import vivliostyle 模組。非法律意見，正式釋出前律師覆核。Spike 4 關閉。**
- **Spike 5 AI 樣式指派（2026-07-10 增）**：私有 LLM 對書稿段落做樣式分類（見 §4.4）。第一輪已完成：8 段自擬段落 8/8 全對。**第二輪（Sprint 4）已完成：真書 72 段重測，嚴格 6 類 50%、粗分類 69.4%、吞吐全書級約 2 分鐘；結論為可行性成立但需 §4.4 四項設計修正（結構優先、AI 粗分、樣式清單為候選集、不外推宣稱）。Spike 5 關閉。**
- **DoD**：真實素材（本書內容）跑過；至少 1 名人類抽檢直排品質；dev-log 留證（時戳、commit、樣本 PDF 路徑）。
- **閘門**：Spike 1＋2 未達可接受品質，不進 Phase 1，須重選架構或核心。

#### Phase 0 閘門判定（2026-07-10 Sprint 5）

**條件性通過，可進 Phase 1。** 五個 spike 全數有一手結論：
- Spike 1 直排核心：檢核清單 7 項中 6 項證據齊備；真實跨頁 0 禁則違規、與參考頁同行數。**唯一未關項＝Owner 人工抽檢（GAPS #10）**，抽檢通過即正式通過；若挑出重大排版瑕疵則回 spike 修正。
- Spike 2 輸出後端：2a Vivliostyle 達標（嵌入子集化全綠、TrimBox 精確、/R2L）；CMYK／PDF-X 深化屬 Phase 4 範圍（GAPS #11）。2b 不裝（條件成就）。
- Spike 3 效能：關閉（引擎重排 7.67ms／章、Vivliostyle 全書 26 秒）。
- Spike 4 授權：關閉（子程序隔離可行，報告見 spikes/spike4-license/report.md）。
- Spike 5 AI 指派：關閉（可行性成立＋四項設計修正入 §4.4）。

**Phase 1 開工前置**：下載思源宋體 TC（GAPS #3，正式樣張與內建字型組）。**並行項（不阻擋開工）**：Owner 抽檢 Spike 1 對比圖（GAPS #10）；若挑出重大排版瑕疵，Phase 1 排版輸出部分回頭修正。

#### Phase 0 執行細則（2026-07-10 補強：從「驗什麼」到「怎麼動手」）

**執行主體現實**：單人＋ AI 輔助開發，Windows 11 主力機。spike 以時間盒控制，不以人月估算。

**Spike 語言**：Phase 0 一律 Python。uharfbuzz／freetype-py／pymupdf 皆 pip 即裝（免 C++ 工具鏈）、迭代最快；Phase 0 驗證的是「排版規則能否達出版級」，不驗效能與產品架構。

**素材與字型前置（Spike 1 先決條件）**：
1. 用 PyMuPDF 抽取代表跨頁（含頁碼＋書眉＋純內文）的文字與座標；直排 PDF 的文字抽取順序可能錯亂，先驗證抽序正確再進排版。
2. 華康字型無授權不可用。spike 字型鏈：先用系統內建新細明體（PMingLiU，含 vert 直排字形）驗通 shaping 管線，正式樣張換思源宋體 TC（OFL 可散布）。比對目標是排版規則等效（禁則／行長／行距／版心），不比字形輪廓。
3. 版權紅線：參考書內容僅限本機驗證，詳見第 8 節。

**依賴與安裝成本**：

| Spike | 依賴 | 成本 |
| --- | --- | --- |
| 1 | Python：uharfbuzz、freetype-py、Pillow、fonttools、pymupdf | pip 分鐘級 |
| 2a | Node.js：@vivliostyle/cli | npm 分鐘級 |
| 2b | TeX Live（LuaLaTeX＋luatexja＋jlreq） | 數 GB、小時級；2a 不達標才裝 |
| 2 驗證 | pdffonts（poppler）、qpdf、veraPDF | preflight 用，選裝 |

**順序與時間盒**：Spike 4（授權桌面研究）隨時可做，盒 2 天；Spike 1 先行，盒 2 週；Spike 2 先跑 2a Vivliostyle，不達標再跑 2b LuaLaTeX，各盒 1 週；Spike 3 殿後，盒 3 天；Spike 5 第一輪已過（2026-07-10），真實素材重測盒 2 天。逾時間盒未達標即觸發第 7 節對策，不無限加班。

**Spike 1 驗收檢核清單（操作化「目視對比」，逐項打勾進 dev-log）**：
- [x] 行長 32 字（2026-07-10 實測修正）、行距＝欄距 23.0pt、版心天頭與第 1 節量測一致（樣張直接以實測行軸座標定位）
- [x] 行首禁則 0 違規（、。！？」』）等）：15 項單元測試＋真實跨頁 runtime 檢查 0 違規
- [x] 行尾禁則 0 違規（「『（等）：同上
- [x] 標點擠壓：連續約物、行末標點依 W3C CLREQ 繁中規則（台灣習慣句逗置中，與日文右上不同；JLREQ 僅作參考，不照抄。已由 2026-07-10 shaping 探針實證：PMingLiU 的 vert 對句逗不替代、僅旋轉引號括號，符合置中慣例；跨頁逐字實測本書無半形擠壓，spike 以等距網格排字）
- [x] 縱中橫：2 位數字直立橫排；長串拉丁旋轉 90 度（out/tcy_demo.png，自擬文字）
- [x] 頁序、行序右至左（跨頁樣張 030 右頁在前，行序右起）
- [ ] 並排對比圖（參考頁渲染 vs spike 樣張）＋人工抽檢記錄：對比圖已產出（out/spread_comparison.png）、AI 全圖掃描記錄於 devlog，**待 Owner 人工抽檢後打勾**

**產出物結構**：

```
CJKFolio/
├── spikes/spike1-vertical-core/     排版器與樣張、對比圖
├── spikes/spike2-output-backend/    Vivliostyle／LuaTeX 樣張與 preflight 報告
├── assets/reference/                參考書抽取素材（版權紅線，永不入公開 repo）
├── assets/fonts/                    OFL 可散布字型
├── devlog/                          時戳＋樣本路徑＋抽檢記錄
└── GAPS.md
```

### Phase 1：核心排版管線 MVP（8〜12 週）[實作]

- 文件模型 ＋ 三層樣式系統 ＋ 主版 ＋ 直排版面引擎 ＋ PDF/X 匯出。
- txt／Markdown 匯入（內容入口，md 結構直接對映樣式）。
- 先支援單一內建模版（《內在整理》風格），命令列或極簡介面驅動。
- **DoD**：以本書真實文字匯出單頁完稿 PDF/X-1a，直排／版心／頁碼／書眉與參考一致度人工抽檢，印刷廠 preflight 全綠。
- **進度（2026-07-10 Sprint 6）**：第一片完成 [實作]：文件模型（cjkfolio/document@1）、三層樣式讀取（template@1：15 段落樣式＋9 字元樣式＋7 主版）、起始模版（templates/neizai-zhengli.json）、txt 匯入、樣式驅動直排引擎（自 Spike 1 產品化，ParagraphSpec 承載每段幾何）、單頁 A5 PNG 渲染（思源宋體 TC，GAPS #3 關閉；奇偶頁鏡像版心）、CLI（import-txt／render）。新增測試 46 項（合計 61）。本機真實素材驗收：第一章（PDF 頁 19〜34）79 段 5,408 字 → 23 頁、禁則 0 違規，page-001/002 目檢通過。
- **進度（2026-07-11 Sprint 7）**：md 匯入 [實作]（block 級：標題層級／引文／清單直接對映樣式，模版帶 md_mapping，§4.4 修正 1 落地）、主版頁腳 [實作]（頁碼全頁＋書名書眉奇數頁，foot_elements 實測座標、奇偶鏡像；左頁章節副標與 Case 編號待章節結構）、字型組入庫（思源黑體 TC Medium/Bold、辰宇落雁體、jf open 粉圓，皆驗 vert；GAPS #12 縮至全字庫兩款）。測試 61→74。真實素材驗收：第一章 md 樣式化實排 4 種樣式同頁（章名 Heavy／個案大標黑 Medium／小標黑 Bold／內文宋 Regular）＋頁腳，23 頁禁則 0 違規，page-001/002 目檢通過。**未完**：字元樣式 run（行內強調）、齊行與約物擠壓（GAPS #9）、橫排、題詞／引文字型（GAPS #12）、PDF/X 寫出層。
- **進度（2026-07-11 Sprint 8）**：PDF 寫出層第一片 [實作]：自寫 PDF 1.4 寫出層（cjkfolio/pdf_writer）＋共用字形佈局層（cjkfolio/placement，與 PNG 同一套 pen 數學）。盒框依 §9（MediaBox 154×216mm、TrimBox 148×210 置中、BleedBox＝MediaBox）、文字 DeviceCMYK 單 K92、Catalog /Direction /R2L、逐字顯式 Tm（禁則與斷行在排版層烘焙）。字型子集嵌入：CFF 原 CID＋charset（探針實證思源 CID==GID，較 retain_gids 小 30 倍）、TTF retain_gids＋CIDToGIDMap Identity，皆帶 ToUnicode＋CIDSet；CLI 新增 export-pdf（--page 單頁完稿）。順手修正：engine.normalize 剝除控制字元（真章素材 U+0007 實測缺陷）、缺字警告不沉默。測試 74→83。真實素材驗收：第一章 md 23 頁全章＋單頁 PDF，pdffonts 六款全綠（emb/sub/uni yes、無 Type3）、PyMuPDF 獨立渲染 page 1/2 目檢通過、禁則 0 違規。**未完**：OutputIntent／XMP 識別／preflight 全綠（GAPS #15）、鏡像依書頁號（#16）、PNG 缺字警告（#17）。
- **進度（2026-07-11 Sprint 9）**：字元樣式 run 模型 [實作]：document@2（Run＋Paragraph 正規化不變式，@1 相容照載、@1 帶 runs 明確拒絕）、Cell 帶字元樣式、雙後端 per-cell 覆寫（字型＋級數；字槽網格仍依段落樣式）、layout 未知字元樣式快速失敗。md 行內強調 [實作]：**strong**／*em* → 模版 md_inline_mapping（v1 皆映內文強調-明體W9；不嵌套、未閉合保留字面）。抽取工具 [實作]：body 欄 DFMingStd-W9 span 標 **…**、控制字元（Cc）源頭剔除列報。測試 83→96。真實素材驗收：重抽第一章（強調 8 對：整句強調 1＋對談發言標籤 7，PDF 實測皆明體 W9）→ 雙後端 23 頁重排 0 違規，強調頁（書頁 25）PNG 與 PDF 渲染目檢一致、Heavy 子集 11→26 字形。**未完**：發言人標籤自動指派（訪談章黑體標籤，Phase 3 AI 指派範圍）、md 嵌套標記（v1 設計外）。
- **進度（2026-07-11 Sprint 10）**：PDF/X-1a:2001 識別 [實作]：header 1.3、Info GTS 兩鍵＋Trapped＋ModDate（Title 必填快速失敗）、OutputIntent（預設 JC200103 registry 識別免嵌 ICC；自訂識別強制嵌 CMYK prtr ICC 並驗 /N 4）、XMP metadata（不壓縮、pdfx＋pdfxid 雙命名空間）。機械 preflight [實作]（cjkfolio/preflight＋CLI preflight）：12 規則 PyMuPDF 獨立解析、未涵蓋項誠實列印、exit 0/1；veraPDF 不支援 PDF/X（實查）故本機 preflight＝自寫檢查器＋pdffonts。CLI export-pdf 加 --output-condition-identifier／--output-condition／--icc。測試 96→107。真實素材驗收：第一章 23 頁全章＋單頁完稿 preflight 12/12 全綠、pdffonts 六款全綠、渲染目檢與 Sprint 9 一致；參考書對照 6/12 未過（實測非 X-1a，§1 修正）。GAPS #15 關閉、新 #18（認證級 preflight）。**未完**：齊行（#9）、鏡像書頁號（#16）、PNG 缺字警告（#17）；Phase 1 DoD 的「印刷廠 preflight 全綠」目前以自寫機械檢查認定，認證級屬 #18。
- **進度（2026-07-11 Sprint 11）**：齊行與禁則擠入 [實作]（GAPS #9 關閉）：行首禁則擠入優先（整串句逗一次決策、溢出 ≤2 槽，超過追出錨字連句逗下移）；非段末行行首行尾雙錨定、內容字距均勻縮放（±1 槽 ≈ ±0.4pt，同 §1 實測；縮排偏移維持網格字距）；偏差超容忍（2 槽）維持網格並入統計不沉默；雙後端同源（layout 層 line_justified_advance），CLI 回報齊行統計。測試 107→112。真實素材驗收：第一章 23→22 頁（擠入縮減行數）、禁則 0 違規、擠入 10 行撐開 1 行超容忍 0；頁 1 擠入行目檢行底貼齊、preflight 12/12 與 pdffonts 全綠不退步。**未完**：鏡像書頁號（#16）、PNG 缺字警告（#17）、橫排（#13）、斷行逐行一致率比對（Owner 抽檢）。
- **進度（2026-07-11 Sprint 12）**：鏡像依書頁號 [實作]（GAPS #16 關閉）：頁面鏡像（行軸書口側）與頁腳奇偶改依書頁號（＝版面頁號＋first_page−1），render 與 pdf_writer 兩後端同源（book_number 同時餵 line_axis_x_pt 與頁腳）；first_page=1 預設不變（向後相容）。PNG 缺字警告 [實作]（GAPS #17 關閉）：PNG 後端四路徑（cjk／縱中橫／旋轉拉丁／頁腳）偵測 gid 0 回報缺字來源字元，PageRenderer.notdef_warnings 訊息格式與 pdf_writer 一致，經 font_warnings 由 CLI 列印。測試 112→115（新增書頁鏡像 PNG／PDF 兩後端＋PNG 缺字警告；翻轉 footer 與 page-selection 既有奇偶頁測試）。真實素材驗收：第一章 --first-page 20 重排，PNG page-001（書頁 20 偶＝左頁）頁碼書口左無書眉、page-002（書頁 21 奇＝右頁）頁碼書口右＋書眉「內在整理」，Read 兩頁親驗與真書右翻一致；22 頁、禁則 0、齊行擠入 10／撐開 1／超容忍 0 不變，preflight 12/12、pdffonts 六款全綠不退步。**未完**：橫排（#13，版權頁-CIP）、斷行逐行一致率比對（Owner 抽檢）。
- **進度（2026-07-11 Sprint 13）**：橫排版面軸 [實作]（GAPS #13 橫排部分關閉）：horizontal-tb 貫通 engine（`tokenize`／`flow_pages` 加 `vertical` 參數，橫排 ascii 整串成 latin run 不縱中橫、不切碎 ISBN，斷行／禁則與方向無關直接復用）／layout（`page_is_vertical` 由樣式判頁面單一方向，混用 vertical-rl 與 horizontal-tb／未知模式快速失敗；橫排 CIP 短行左齊不齊行）／render（`horizontal_left_x_pt`／`horizontal_baseline_y_pt`／`_draw_horizontal_cell`，`render_page` 依方向分派）／pdf_writer（`_horizontal_body` 用既有 `horizontal_placements`＋水平 `1 0 0 1 x y Tm`）。兩後端幾何同源集中 placement `horizontal_cell_advance_pt`（latin 自然寬、cjk em 格）。honest-planning R6 pre-mortem＋R2 spike（spikes/spike6-horizontal/）先行。F-版權頁 grid 改自擬橫排幾何（8pt CIP、字距 8.4pt、行距 14pt）。測試 115→127。真實素材驗收（紅線改自擬）：samples/cip-copyright.doc.json（虛構書目 7 行 CIP）→ render PNG（300dpi）Read 親驗橫排由上而下、字由左而右、CJK 與 latin 同基線；export PDF preflight 12/12 全綠、PyMuPDF 獨立渲染與 PNG 一致、抽字 8 行首字座標與 render 幾何助手推導一致（單元測試 abs≤0.3pt 釘死）。**未完**：F-版權頁真實版心（p178）Owner 本機量測、B〜G 其他扉頁佈局、斷行逐行一致率比對（Owner 抽檢）。
- **進度（2026-07-11 Sprint 14）**：CIP 細框向量原件 [實作]：新 `cjkfolio/primitives`（`StrokeRect`＋`cip_frame_rect`，與 placement 同層、兩後端同源地基）；框幾何由主版 grid（滿行寬×n_lines×行距）＋內容行數確定性推導、四周 pad。styles 加 `FrameSpec`／`KNOWN_FRAME_KINDS`／`MasterPage.frame`（未知 kind／壞 cmyk 快速失敗）。render `_draw_stroke_rect`（PIL "L" outline=0）＋`_draw_frame`；pdf_writer `_Content.prologue`＋`stroke_rect`（DeviceCMYK `K` 描邊、獨立 `q…Q` 置於 BT／ET 外）＋`_frame`（top-down 下緣→y-up 左下角）；兩後端 gate＝`not vertical and master.frame and page.placed`（cip-box 為橫排原件）。F-版權頁加 `frame`（cip-box 純黑 0.5pt、pad 6pt，全自擬）。honest-planning R6 pre-mortem＋R2 spike（spikes/spike7-vector-frame/）先行。測試 127→139。真實素材驗收（紅線自擬）：samples/cip-copyright.doc.json → render PNG（300dpi）Read 親驗四邊閉合細框圍住 7 行 CIP、內部留白、框寬＝版心；export PDF 內容流 `re` 座標與 `cip_frame_rect` 手推一致、CMYK `0 0 0 1 K`、`re` 在 `BT` 前、無 `rg`/`RG`、preflight 12/12 全綠；兩後端框座標同源（單元測試 abs≤0.3pt）。**未完**：F 真實版心（p178）Owner 量測、B（部扉雙線菱形框）／D（目錄水平虛線）等向量裝飾（本原件層為其地基）、斷行逐行一致率比對（Owner 抽檢）。
- **進度（2026-07-11 Sprint 15）**：目錄水平虛線向量原件 [實作]：primitives 加 `StrokeLine`（端點＋cmyk＋線寬＋dash on/off，on=0 實線）＋`toc_rule_line(page_width_pt, rule)`（貫穿頁寬＋兩側出血延伸 3mm，§9 貼邊全出）；styles 加 `RuleSpec`／`KNOWN_RULE_KINDS`／`MasterPage.rule`（未知 kind／壞 cmyk／缺 y 快速失敗）；render `_draw_stroke_line`（PIL 分段 dash，灰值 255×(1−k) 只取 k）＋`_draw_rule`；pdf_writer `_Content.stroke_line`（原生 `[ on off ] 0 d` dash 算符＋灰 `K` 描邊，獨立 `q…Q` 置 BT 前，spike8 實證狀態不外洩）＋`_rule`；兩後端 gate＝`vertical and master.rule and page.placed`（toc-rule 為直排目錄原件）、幾何同源集中 `toc_rule_line`。D-目錄主版加 rule（y 122.46pt、1.0pt、dash [3 2]、灰 K57，皆 p003 一手量測參數；量測參數入模版依 Sprint 7 頁腳先例，內容不入 repo）、天頭 32.49→47.63mm（內容起點 135pt 實測，修正第一輪樣張文字穿線）。標的決策：部扉「雙線菱形框」p069 實測為手繪向量（單 draw 608 段不規則路徑），規則化自擬等效性低且屬美術資產（§8 不生成美術），故先做虛線。honest-planning R6 pre-mortem＋R2 spike（spikes/spike8-dashed-rule/，三探針全過）先行。測試 139→151。真實素材驗收（紅線自擬）：samples/toc.doc.json（虛構部名＋4 條目）→ render PNG（300dpi）Read 親驗虛線橫貫整頁寬、斷續均勻、內容全在虛線下；export PDF 內容流 `m`/`l` 座標與 `toc_rule_line` 手推完全一致（0/436.535/481.32）、`[ 3 2 ] 0 d`＋`0 0 0 0.57 K` 在 BT 前、無 `rg`/`RG`、PyMuPDF `get_drawings` 獨立回報 dashes、preflight 12/12 全綠；兩後端座標同源（單元測試 abs≤0.3pt）。**未完**：目錄頁型（篇名嵌線斷開、條目縮退、垂直引導線、直排數字頁碼）、F 真實版心（p178）Owner 量測、斷行逐行一致率比對（Owner 抽檢）。
- **進度（2026-07-11 Sprint 16）**：目錄條目頁碼＋引導線 [實作]：document@2 相容擴充 `Paragraph.page_no`（選配數字字串，非數字快速失敗）；engine `ParagraphSpec`／`PlacedLine` 純載體傳遞（只掛段末行，不影響斷行禁則）；styles `TocSpec`（頁碼字元樣式＋底錨＋引導線寬/gap/cmyk，模版跨引用驗證未知頁碼樣式即拒）＋`MasterPage.toc`；layout `TocEntryMark`＋`LayoutResult.toc_marks`（頁碼頂＝底錨−位數×字距、線起＝標題末＋gap、線終＝頁碼頂−gap，重疊列 violations 不畫線）；render `_draw_toc_marks`（引導線復用 StrokeLine 實線＋頁碼 `_draw_tcy` 逐位直立）；pdf_writer `_toc_marks`（`stroke_line` 無 dash K92＋`tcy_placements`）。D-目錄 toc 配置（底錨 490pt、線寬 0.1pt 皆 p003 實測；頁碼樣式對映粉圓替 Times）。R2 校正判定無需新 spike（全為既有能力復用，spikes/spike9-toc-entry/premortem.md）。測試 151→164。真實素材驗收（紅線自擬）：samples/toc.doc.json 條目加頁碼 → render PNG Read 親驗四條目引導線＋頁碼底一列對齊（與 p003 設計語言一致）；export PDF preflight 12/12、PyMuPDF 獨立解析 4 引導線（w0.1 無 dash）y 起訖與手推一致、10 個直立數字；兩後端 parity 單元測試釘死。粉圓首次進 PDF 子集（fontTools 丟 Apple meta table，無害紀錄）。**未完**：篇名嵌線斷開、條目縮退、目錄「章名條目黑 W5」樣式層、F 真實版心（p178）Owner 量測、斷行逐行一致率比對（Owner 抽檢）。

#### Phase 1 收尾判定（2026-07-12 Sprint 39，Owner 定案收尾轉 Phase 2）

**Phase 1 骨架機制級 DoD 達成，收尾轉 Phase 2。** honest review 實查（非橡皮圖章）：

- 文件模型（document@2）＋三層樣式（18 段落樣式＋9 字元樣式）＋ A〜G 七主版（templates/neizai-zhengli.json 實查命中 7 master id）＋直排版面引擎（禁則／約物擠壓／齊行擠入／縱中橫／橫排／依書頁號鏡像）＋自寫 PDF/X-1a:2001 匯出（OutputIntent／XMP／GTS 兩鍵／子集嵌入）＋機械 preflight 12 規則＋txt／md 匯入，`pytest spikes tests` 218 綠、typecheck（py_compile 全部）EXIT=0、兩後端（PNG／PDF）幾何同源。
- 《內在整理》內建模版風格：A-內文版 A 級一手驗證，B〜G 扉頁與特殊頁型逐頁量測建模（B 部扉／C 個案扉頁／D 目錄／E 序文版／F 版權頁／G 圖文版骨架），量測參數皆 A 級一手證據。

**正式 sign-off 待 Owner（R5 人類抽檢，執行工程師不代行）**：GAPS #10（Spike 1 對比圖 spikes/spike1-vertical-core/out/spread_comparison.png 抽檢，Phase 0 正式通過前提）、GAPS #23（斷行逐行一致率比對）。二者為 Owner-hands-on；排版機制級品質已 A 級驗證且 0 禁則違規，但「無重大排版瑕疵」與「逐行一致率」屬人類品質判斷。

**剩餘項處置**：全數彙整 GAPS #22 Known Limitations（甲 細項延後＝結語／訪談欄標變體、目錄摘要層；乙 需新機制＝肩注／行距分區／帶起訖，前 Sprint 已誠實判 v1 不建模；丙 §8 美術不生成＝部扉手繪框／署名自由手排／G 房名圖說；丁 後續 Phase＝G 照片 Phase 2、圖文繞排 Phase 4），均不阻擋轉場，開源釋出前以 Known Limitations 公開承認（R7）。

**下個 Sprint**：Phase 2 開工首項＝Qt 畫布 IME 直排輸入真視窗實測（GAPS #19），§7 Pre-mortem 未退場最大產品風險（畫布與排版核心同步，僅 Spike 10 初驗）。

### Phase 2：WYSIWYG 編輯器（12〜16 週）[實作]

- Qt＋Skia 畫布：文字框建立／串接、主版指派、樣式面板套用、圖片置入、即時預覽、IME 直排輸入、復原重做。
- **前置 spike（2026-07-11 Sprint 17，Owner 指示風險前置）**：[Spike] Spike 10 通過（spikes/spike10-canvas-sync/report.md）：PySide6＋QGraphicsScene 雙層畫布（底圖＝PNG 後端輸出、互動層＝layout 幾何同源字格 item）可行性成立；編輯 → 全章重排 → 單頁重渲染 → 畫布更新全回路中位 37.2ms@150dpi（互動閾值 200ms 餘裕 5 倍）、hit-test 反查 214/214、22 頁 5,361 item 建立 52ms（hit 中位 0.90ms）。介面缺口顯式化：PlacedLine／Cell 無文件 provenance（para_idx／char offset），列 Phase 2 首項工程。未驗：IME 直排輸入／拖曳／選取 UI（offscreen 限制，GAPS #19）。
- **進度（2026-07-11 Sprint 18）**：Phase 2 首項工程完成 [實作]：文件 provenance 載體。`Cell.span`（文件段 text 半開區間；`normalize_with_offsets` 索引映射，Cc 剝除位移精確處理、表現形 1:1 不動索引；runs 依 document@2 串接不變式帶 base 位移）＋`ParagraphSpec.para_idx`／`PlacedLine.para_idx`（layout 建 spec 掛段索引）。畫布點選 → (para_idx, char span) 文件游標資料鏈自此補齊；載體不影響斷行禁則齊行與兩後端。測試 164→173；第一章 22 頁 5,361 cells、toc／cip 樣張 round-trip 全 0 錯。
- **進度（2026-07-12 Sprint 40）**：Phase 2 開工首項 [實作]＋真視窗骨架：技術棧正式定案 PySide6（Spike 10 A 級數據，§5.2 Phase 2 開工定案）。新增 editor/ 套件（不入 pytest 基線，守 Sprint 17）＝canvas.py（雙層畫布核心，互動層座標復用 render 直排 body 同源公式＋lead_offset_pt；resolve_hit 點字格反查文件游標 para_idx／span／text，承 Sprint 18 provenance）＋app.py（真視窗 QMainWindow：雙層畫布顯示＋點字格反查游標＋高亮＋IME 測試區）＋smoke_check.py（離屏 Gate-5 驗證）＋README.md。離屏 smoke_check：samples/case-divider（自擬 C 個案扉頁）雙層建構、hit-test 48/48、48 cjk 字格 provenance span 切片＝cell.text；app 離屏建構＋模擬點選（段5 字(12,13)＝「。」）＋IME 回呼＋高亮皆驗。**[Shell]／待 Owner**：真視窗視覺對位與 IME 直排輸入鍵盤實測（離屏測不了，GAPS #19）；直排畫布內嵌 IME 編輯（打字→插入→reflow）為後續工程。
- **進度（2026-07-12 Sprint 41）**：Phase 2 編輯引擎 reflow 回路 [實作]（Sprint 40 預告的「游標插入→局部 reflow→畫布更新」，Owner「最複雜架構先做」下）。新增核心 `cjkfolio/editing.py`（**入 pytest 基線**，純邏輯非 GUI，與 layout/engine 同層）＝DocCursor／CellAddress／EditResult＋insert_text（不可變、run 邊界左偏承接字元樣式、越界快速失敗）／locate_cell（resolve_hit 的逆，Cell.span 反查、段內命中唯一、查無回 None）／apply_insert（插字→layout_document 全文重排→反查新游標畫布落點）。游標座標系＝段 text 半開座標（與 Sprint 18 Cell.span 同一座標系，構成畫布↔文件游標雙向映射）；reflow 走全文重排（Spike 3 認可 7.67ms/章，非增量近似）。app.py 接線 IME 提交回路（returnPressed→_on_ime_commit→apply_insert→_rebuild 畫布重繪→游標跟隨），順帶清死 import QTransform。測試 218→231（+13：插字 7／run 邊界 2／locate_cell 2／apply_insert 2）。真實素材驗收（自擬 samples/case-divider C 個案扉頁）：段 3 內文插「大大」→文件實變且原文件不變、reflow 0 禁則違規、新游標落點 cell.text＝「大」，皆基線斷言；離屏 smoke C5「插入『測試』→reflow（1 頁 0 違規）游標跟隨到『試』」。**[Shell]／待 Owner（GAPS #19，離屏測不了）**：真視窗 IME 直排組字順暢度、提交後 reflow 視覺流暢與對位；直排畫布內嵌 IME 即點即打、拖曳／範圍選取、刪除編輯（v1 只插入）為後續 UI 工程。
- **進度（2026-07-12 Sprint 42）**：Phase 2 編輯引擎段內刪除與範圍替換 [實作]（Owner「最複雜架構先做」下，續 Sprint 41 插入回路）。cjkfolio/editing.py（入 pytest 基線）加 `DocRange`（段索引＋段 text 半開區間 [start, end)，與 DocCursor caret 同座標系）＋`delete_range`（段內多 run 逐 run 切除交集、保留兩端 run 及字元樣式、整個 run 落範圍內連樣式消失、全段刪空回合法空段（text 為空，正規化為單一空 run，守 document@2 不變式）；start==end no-op、越界／start>end 快速失敗）＋`replace_range`（delete_range 後於 start 插入、新字承接左側 run 樣式復用 insert_text 慣例、text 空退化純刪除；全刪再插無需改 insert_text，空段既有 for 迴圈於單一空 run 邊界插入）＋`apply_delete`／`apply_replace`（對稱 apply_insert 完整回路，全段刪空 address=None）。測試 231→250（+19：delete_range 11／replace_range 4／apply_delete／apply_replace 4）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬 samples/case-divider 與 make_doc 樣張）：段內 [4,6) 刪「，約」→reflow 0 違規、游標反查落點 cell.text＝「廳」；範圍 [0,4) 替換「兩房」→reflow 0 違規、游標跟隨「房」；跨 run 刪除保留兩端字元樣式、全刪成空段 address=None，皆基線斷言。**[Shell]／待 Owner（GAPS #19／#24，離屏測不了）**：刪除／範圍選取的鍵盤與拖曳畫布 UI 接線（app.py 未接線）、跨段合併／分裂（改 para_idx 語意需新機制）為後續 UI 工程。
- **進度（2026-07-12 Sprint 43）**：Phase 2 編輯引擎跨段合併與分裂 [實作]（Owner「最複雜架構先做」下，續 Sprint 41 插入／42 段內刪除，補齊改變段落數量的編輯，關 GAPS #24「需新機制」子項）。cjkfolio/editing.py（入 pytest 基線）加 `split_paragraph`（Enter 段中分段：於 cursor 切 head／tail 兩段同承段落樣式、page_no 留 head 保原段身分／tail None、跨 run 切割兩側各保字元樣式、空側正規化單一空 run；越界快速失敗）＋`merge_paragraph`（Backspace 段首併前段：承前段樣式與 page_no、runs 前段＋本段串接濾空 run、全空正規化單一空 run；para_idx 0 無前段可併 raise IndexError）＋`apply_split`／`apply_merge`（對稱 apply_insert 完整回路，split 新游標＝tail 起點 (idx+1,0)、merge 新游標＝合併縫 (idx−1,前段原長)；para_idx 重編由 layout_document 依 enumerate 位置自動指派、cursor 指向新位置）。測試 250→273（+23：split 10／merge 9／apply 4）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬 make_doc C 個案扉頁）：段 1 caret 4 分段→原段 2 順移段 3（para_idx 重編正確）reflow 0 違規、tail 首字反查 cell.text＝「約」；段 2 併段 1→原段 3 順移段 2 reflow 0 違規、合併縫反查前段末字 cell.text＝「廳」；跨 run 分裂／合併保兩側字元樣式、空段 address=None，皆基線斷言。**[Shell]／待 Owner（GAPS #19／#24，離屏測不了）**：Enter／Backspace／刪除／選取的鍵盤與拖曳畫布 UI 接線（app.py 未接線）為後續真視窗工程。
- **進度（2026-07-12 Sprint 44）**：Phase 2 編輯引擎 undo／redo 堆疊 [實作]（Owner「最複雜架構先做」下，承 Sprint 41〜43 編輯核心，補齊 Phase 2「復原重做」）。cjkfolio/editing.py（入 pytest 基線）加 `EditSession` 編輯會談控制器＝現態 (document, cursor, layout)＋undo／redo 兩 (document, cursor) 快照堆疊（標準「回上一提交態」模型：編輯推編輯前態入 undo 清 redo；undo 推現態入 redo、彈回上一態全文重排 Spike 3 認可 7.67ms/章，redo 對稱）；insert／delete／replace／split／merge 委派既有 apply_* 統一經 _commit 記錄歷史、回 EditResult；undo／redo 還原後 locate_cell 反查游標、回 EditResult，無可回退／重做回 None；can_undo／can_redo／document／cursor／layout 屬性。測試 273→284（+11）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬 make_doc／_plain）：插入→undo 回編輯前、can_redo 真、重排 0 違規、游標反查落首字「三」；redo 復原；新編輯清 redo；split／merge／delete／replace 皆經 session 可反向 undo，皆基線斷言。**[Shell]／待 Owner（GAPS #24／#25／#19，離屏測不了）**：app.py 未接線 undo／redo（Ctrl+Z／Y 真視窗工程）；undo 粒度每次 apply 一步（未合併連續輸入）為 v1 已知限制。
- **進度（2026-07-12 Sprint 45）**：Phase 2 編輯引擎字元樣式套用到選取範圍 [實作]（Owner「最複雜架構先做」下，續 Sprint 41〜44 編輯核心，補齊 §4.1 字元樣式套用）。cjkfolio/editing.py（入 pytest 基線）加 `apply_char_style`（純文件層：對段內 DocRange [start, end) 逐字元改掛 char_style（None 清除回段落樣式）、範圍外保留原樣式、切割後連續同樣式併為單一 run 避免碎片、空範圍 no-op、不可變、越界快速失敗；字元樣式名有效性不在此層驗，由 layout_document 守門）＋`apply_style`（對稱 apply_insert 完整回路：套樣式→layout_document 全文重排→locate_cell 反查，新 caret＝drange.end 停選取尾、未知字元樣式 layout_document raise KeyError）＋`EditSession.apply_style`（委派 apply_style 統一經 _commit 入 undo／redo）。測試 284→304（+20：apply_char_style 12／apply_style 4／session 3／R5 1）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬 _plain 內文）：「約三十」套「內文強調-明體W9」→ run 切割三段、reflow 0 違規、游標停 caret 8、layout 字格 span 5-7 char_style＝強調（端到端流入渲染層）、undo 清回原 redo 復原，皆基線斷言。**[Shell]／待 Owner（GAPS #26／#19，離屏測不了）**：app.py 未接線樣式面板（選取範圍→套字元樣式 UI）；DocRange 限段內（跨段選取套樣式需跨段範圍機制）為 v1 已知限制。
- **進度（2026-07-12 Sprint 46）**：Phase 2 編輯引擎段落樣式變更 [實作]（Owner「最複雜架構先做」下，續 Sprint 41〜45 編輯核心，補齊 §4.1 段落樣式套用）。cjkfolio/editing.py（入 pytest 基線）加 `change_paragraph_style`（純文件層：把段 para_idx 的 Paragraph.style 換名、runs（含字元樣式）與 page_no 不變、樣式相同 no-op 回原物件、不可變；para_idx 越界 IndexError、style 空字串 ValueError 守 document@2「段落需非空 style」不變式；段落樣式名有效性不在此層驗，由 layout_document 守門）＋`apply_para_style`（對稱 apply_insert／apply_style 完整回路：改 cursor.para_idx 段樣式→layout_document 全文重排→locate_cell 反查；段落樣式變更不改 text 故游標保持不變、reflow 後畫布落點隨版面更新、文件座標不動；未知段落樣式名 layout_document raise KeyError）＋`EditSession.apply_para_style`（委派統一經 _commit 入 undo／redo）。測試 304→319（+15：change_paragraph_style 8／apply_para_style 3／session 3／R5 1）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬 _plain 內文）：段落樣式「內文-明體直排」→「引文-仿宋語錄」→ placed line.style 換名、reflow 0 違規、游標保持 caret 4、undo 回原 redo 復原，皆基線斷言。誠實記錄：內文與引文版面幾何參數相同（advance 12.08／indent 2，差異僅字型），故證「樣式參照流入 layout＋reflow 乾淨」非斷行幾何改變。**[Shell]／待 Owner（GAPS #27／#19，離屏測不了）**：app.py 未接線段落樣式面板（游標所在段→套段落樣式 UI）為後續真視窗工程。
- **進度（2026-07-12 Sprint 47）**：Phase 2 編輯引擎連續輸入合併為單一 undo 單元 [實作]（Owner「最複雜架構先做」下，續 Sprint 41〜46 編輯核心，補齊 Phase 2「復原重做」的輸入序列合併、關 GAPS #25「連續輸入合併」子項）。cjkfolio/editing.py（入 pytest 基線）EditSession 加連續輸入合併：`insert` 對前進打字（游標接續前一輸入尾 run 尾 caret＋兩次輸入間隔未逾 coalesce_window 秒）併入同一 undo 單元（更新現態但不新增 undo 快照、不動 redo），對標 InDesign／多數編輯器逐字輸入不各成一步；輸入序列邊界＝游標不連續、逾時間窗、或任何非插入操作（delete／replace／split／merge／apply_style／apply_para_style／undo／redo）介入（皆令 `_pending_insert` 歸零、其後起新 undo 單元）；`_can_coalesce` 判定（承前一輸入、游標接續其尾、`now − ts ≤ coalesce_window`）、`_commit`／`_restore` 統一重置序列；clock 預設 `time.monotonic`、coalesce_window 預設 2.0s（keyword-only，既有 `EditSession(doc, template)` 建構不變），測試注入可控假時鐘離屏確定性驗時間邊界。測試 319→326（+7：連續合併／redo 整串／游標不連續起新單元／逾時起新單元／恰達窗合併／刪除打斷／undo 重置序列）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬 _plain 內文）：連續前進打「三房兩」→ undo 堆疊深度只 +1、一步 undo 還原整串「的老公寓」reflow 0 違規；逾 2.0s 窗或刪除介入則起新單元、只退最後一字，皆基線斷言＋獨立 probe 直接檢視 `_undo` 深度互證。**[Shell]／待 Owner（GAPS #25／#19，離屏測不了）**：app.py 未接線 undo／redo（Ctrl+Z／Y 真視窗工程）為後續工程。
- **進度（2026-07-12 Sprint 48）**：Phase 2 編輯引擎跨段選取範圍 [實作]（Owner「最複雜架構先做」下，續 Sprint 41〜47 編輯核心，補齊改變段落邊界的範圍編輯，為 GAPS #26 跨段字元樣式所需的跨段範圍機制地基）。cjkfolio/editing.py（入 pytest 基線）加 `DocSpan`（起訖兩 DocCursor 界定跨段選取，start ≤ end 段索引優先再比 caret；DocRange 段內範圍的一般化，同段退化為段內範圍、start==end 空範圍）＋`delete_span`（同段委派 delete_range；跨段頭段保 start 前、尾段保 end 後併為一段承頭段樣式與 page_no〔頭段存活，同 merge_paragraph 慣例〕、中間整段移除、兩端 run 各保字元樣式、全刪空正規化單一空 run〔守 document@2〕；空範圍 no-op、para_idx 越界 IndexError／caret 越界或起點晚於終點 ValueError）＋`replace_span`（delete_span 後於縫插入承左側 run 樣式、text 空退化純刪除）＋`apply_delete_span`／`apply_replace_span`（對稱 apply_delete／apply_replace 回路：跨段編輯→layout_document 全文重排→locate_cell 反查，delete 新 caret＝縫／replace 新 caret＝縫＋len(text)、全刪空段 address=None）＋`EditSession.delete_span`／`replace_span`（委派 _commit 入 undo／redo、非插入操作打斷連續輸入序列）；內部 `_slice_runs`（run 切片保字元樣式濾空段）／`_validate_span`。循 tests/ 分檔慣例（test_edit_style／test_edit_para_style 先例）獨立新檔 tests/test_edit_span.py（自帶 fixture／helper／_FakeClock，test_edit_engine.py 維持 794 行不撐破 800 上限）。測試 326→346（+20：delete_span 11／replace_span 3／apply 4／session 2）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬多段內文）：段 0「三房兩廳」跨段刪到段 1「採光良好」→ 頭「三房」＋尾「良好」併為單段「三房良好」reflow 0 違規、游標落縫左鄰「廳」；跨段替換「格局」→「三房格局良好」；併段承頭段樣式與 page_no、兩端 run 字元樣式各保，皆基線斷言。**[Shell]／待 Owner（GAPS #28／#19，離屏測不了）**：選取拖曳→跨段刪除／替換的畫布 UI 未接線（app.py 真視窗工程）。**未做（下一 Sprint）**：跨段字元樣式套用（apply_char_style over DocSpan，關 GAPS #26 跨段子項），本 Sprint 只建範圍機制未套字元樣式。
- **進度（2026-07-12 Sprint 49）**：Phase 2 編輯引擎跨段字元樣式套用 [實作]（Owner「最複雜架構先做」下，承 Sprint 45 段內 apply_char_style 與 Sprint 48 DocSpan，關 GAPS #26「跨段選取套字元樣式」子項）。cjkfolio/editing.py（入 pytest 基線）加 `apply_char_style_span`（純文件層：對跨段選取 [start, end) 逐段套或清字元樣式，段界不併〔字元樣式不改段落數量，別於 delete_span〕、頭段 [start, len)／中間段整段／尾段 [0, end) 各委派段內 apply_char_style〔逐 run 切割＋相鄰同樣式併合〕、同段退化段內 apply_char_style、空範圍 no-op、復用 _validate_span 越界／逆序守門）＋`apply_style_span`（對稱 apply_style 回路：套樣式→全文重排→反查，新 caret＝span.end 停選取尾、未知樣式 layout_document raise KeyError）＋`EditSession.apply_style_span`（委派 _commit 入 undo／redo）。循 tests/ 分檔慣例獨立新檔 tests/test_edit_style_span.py。測試 346→359（+13：apply_char_style_span 10／apply_style_span 2／session 1）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（自擬多段內文）：段 0「三房兩廳」跨段套「內文強調-明體W9」到段 1「採光良好」→ 段 0「兩廳」＋段 1「採光」掛強調、段界不併、範圍外保留原樣式、reflow 0 違規、游標停選取尾、端到端字格 char_style 流入渲染層（強調字＝約三十坪採光），皆基線斷言。**[Shell]／待 Owner（GAPS #28／#26／#19，離屏測不了）**：樣式面板 UI 與跨段選取拖曳未接線（app.py 真視窗工程）。至此 Phase 2 核心編輯 API（插入／刪除／替換／分裂／合併／undo-redo／字元樣式／段落樣式，段內與跨段）完備。
- **進度（2026-07-12 Sprint 50）**：Phase 2 圖片置入核心 [實作]（Owner「最複雜架構先做」下編輯引擎完備後，轉 §6 Phase 2「圖片置入」，承 Sprint 27 G-圖文版 photo-slot 保留區地基）。新增 `cjkfolio/images.py`（影像領域單一事實來源：`open_grayscale` 轉 8-bit 灰階＝§9 灰階單 K、`resolve_placed_images` 兩後端共用解析＋去重、`EmbeddedImage` DeviceGray XObject 形態）＋`primitives.fit_image_rect`／`ImageBox`（contain 等比縮放置中純幾何）＋document@2 相容擴充 `PlacedImage`／`Document.images`（path＋版面頁號，序列化選配、page 重複／非法快速失敗，同 page_no 相容慣例）。兩後端置入主版 figure 保留區（`figure_slot_rect`＋`fit_image_rect` 同源）：render PNG 灰階 paste（`_draw_image`，取代佔位框）、pdf_writer DeviceGray 影像 XObject（`_image`＋`_Content.draw_image`：`cm` 縮放單位方陣＋`Do`，置 BT／ET 前獨立 q…Q；`/XObject` 進 Resources；同路徑跨頁去重單一 XObject）。preflight 不退步（DeviceGray 非 color-cmyk-only 禁列、無 SMask 不觸 no-transparency），NOT_COVERED 同類更新（Gate 3：「v1 尚無影像置入」→「PPI 未強制重採樣、色彩空間 color-cmyk-only 涵蓋」）。CLI render／export 加 `image_base_dir`（相對 doc 目錄解析）＋印置入圖數。順帶：pdf_writer 逾 800 行故 `EmbeddedImage` 移入 images.py（影像領域，emit duck-type `pdf.stream` 無循環 import）。測試 359→393（+34，新檔 tests/test_images.py）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5，自擬灰階「照片」TOP/BOT 標記＋外框＋左上黑角）：G 圖文版單頁置入 → PNG 與 PDF 獨立渲染（PyMuPDF）兩後端目視完全一致、方向未翻轉（TOP 在上、黑角左上）、contain 置中、preflight 12/12、0 違規；親 Read 兩渲染確認。R2 判定復用既有能力（figure_slot_rect／placement／PDF 寫出層／PIL 已備）無需新 spike（先例 Sprint 16/38/41-49）。**[Shell]／待 Owner（GAPS #29／#19，離屏測不了）**：畫布拖放／縮放置入 UI 未接線（app.py 真視窗工程）；v1 限制＝只 figure 保留區每頁一張、PPI 未強制重採樣（§9 300-350ppi 屬 #18／Phase 4）、只灰階 DeviceGray（彩色 CMYK Phase 4）。
- **進度（2026-07-17 Sprint 51）**：Phase 2 主版指派核心 [實作]（Owner「最複雜架構先做」下，§6 Phase 2「主版指派」，Sprint 50 預定三選項取最複雜架構項）。節式主版指派＝document@2 相容擴充 `Paragraph.master` 節首標記（自本段起新頁並改用該主版，同名亦強制分頁＝顯式分頁原語；@1 拒絕、空字串快速失敗；`doc.master` 降為首節預設，無標記文件行為完全不變）；layout 節式流排（`_sections` 切節、每節獨立 flow_pages 用該節主版網格〔樣式行容量逐節換算：A 節 32 字/行與 B 節 10 字/行同文件並存〕、頁號跨節連續、節間段後空槽歸零、first_para_continues 僅首節、`LayoutPage.master` 載體、未知主版快速失敗）；toc／rule／齊行統計逐頁主版；兩後端逐頁主版（render_page／build_page 依 page.master 解析，頁腳／frame／rule／figure 逐頁 gate＝B 部扉頁自然無頁腳）；`resolve_placed_images` 改 masters_by_page（逐頁 figure 驗證：G 節照片頁與 A 節內文同文件可置入）；editing 七類操作（insert／delete／replace／char style／para style／split／merge）保留 master（split head 承節首身分同 page_no 慣例、merge 前段存活節首標記隨併入消失）；editor canvas 互動層幾何依該頁主版。測試 393→413（+20，新檔 tests/test_master_assign.py）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5，自擬 samples/chapter-opening.doc.json 章首文件）：單一文件頁 1＝B 部扉（篇序小標＋大標行軸 228.49／194.12、無頁腳）＋頁 2＝A 內文（3 段縮排段間正確、頁腳頁碼 2＋書眉），render PNG 兩頁親 Read 目檢、export PDF preflight 12/12、PDF 字墨 cx 逐頁對 B／A 行軸（測試釘死）。**[Shell]／待 Owner（GAPS #30／#19，離屏測不了）**：選頁套主版的頁面面板 UI 未接線；v1 限制＝節式內容錨定（頁鍵式指派屬編輯 UI）、直排橫排仍不可混（F 版權頁分文件）、md 匯入不產節首標記。
- **進度（2026-07-17 Sprint 52）**：全書組裝管線 [實作]（Owner「最複雜架構先做」下，Sprint 51 預定三選項取最重；多章文件串接跨主版成冊，直向產出全書級 PDF/X）。新增 `cjkfolio/book.py`（cjkfolio/book@1）：書冊清單 JSON（meta.title／template＋chapters 章序即節序＋選配書冊層級 images）→ `assemble_book` 串接為**普通 document@2 文件**（組裝層零新排版機制：章首段掛節首標記復用 Sprint 51 節式主版指派，render／export／editing 照既有管線）；主版解析優先序＝chapters[].master 顯式覆寫 ＞ 章首段既有標記 ＞ 章文件 meta.master；快速失敗＝schema／空章／template 不一致／章層級 images（其 page 為章內排版頁號組裝後失效，置入圖改列書冊層級＝全書版面頁號）。CLI 加 `assemble` 子命令（章路徑相對書冊清單目錄）。順帶修既有樣張缺欄位：samples/figure-page.doc.json 補 meta.template（Sprint 27 起缺漏，組裝器 template 一致性檢查抓到）。測試 413→428（+15，新檔 tests/test_book.py：schema 2／assemble 語意 8／layout 節序與 save round-trip 2／CLI 1／全書端到端 1＋樣張既有守門）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5，自擬 samples/book.json 全書樣張＝E 序文＋D 目錄＋B/A 章首文件＋C 個案扉頁＋G 圖文版五章）：CLI assemble 5 章 → 21 段（6 節首標記）→ render 6 頁（禁則 0 違規）＋export PDF 6 頁 preflight 12/12；親 Read 三跨主版代表頁（D 頁篇名嵌線斷開＋條目引導線頁碼底錨、A 頁頁碼跨節連續書頁 4 偶右＋書眉採全書題名、G 頁圖說＋photo-slot 佔位框），與各單頁樣張特徵逐項一致。**v1 限制（GAPS #31）**：images 僅書冊層級、直排橫排不可混（F 版權頁另出，承 #30 (b)）、目錄頁碼手填（自動生成 Phase 4）、單向產出無增量。
- **進度（2026-07-17 Sprint 53）**：節式混向文件 [實作]（Owner「最複雜架構先做」下，關 GAPS #30 (b)／#31 (b)：F 橫排版權頁與直排內文同冊）。書寫方向自「全文件單向」降到**節層級**：layout `_section_is_vertical`（同一節混向仍快速失敗，訊息引導以節首標記分節；`page_is_vertical` 保留為全文件單向相容 util）＋`LayoutPage.vertical` 逐頁方向載體＋`LayoutResult.vertical` 改義為首節方向（相容欄位，逐頁以 LayoutPage.vertical 為準）；齊行統計逐頁 gate（橫排頁不入統計）、rule 斷線逐頁 gate（直排目錄原件）；兩後端 render_document／export_pdf 改逐頁傳方向（frame 橫排原件與 rule 直排原件的既有 gate 自動逐頁正確）；editor canvas 底圖逐頁方向、橫排頁互動層未建（僅底圖，iter_cell_rects 為直排 body 幾何，誠實入 GAPS #30 (b) 註記）。零新排版機制（方向參數本就逐 flow_pages 傳遞，R2 無需 spike）。測試 428→436（+8，新檔 tests/test_direction_sections.py：layout 逐頁方向 4〔含首節橫排／同節混向仍 raise／齊行統計對照〕＋兩後端混向幾何 2＋book 含 F 章端到端 1＋單向不變 1）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5，自擬）：samples/book.json 加第六章 cip-copyright → 6 章 28 段（7 節首標記）→ 7 頁 render 禁則 0 違規＋export 單一 PDF/X preflight 12/12；親 Read 頁 7（F 版權頁：橫排 CIP 七行左起、細框四邊閉合、ISBN 拉丁串完整、無頁腳），直排 6 頁特徵不變。混向 PDF 幾何測試釘死（頁 1 直排同欄 cx 一致 y 遞增、頁 2 橫排同行基線一致 x 遞增、CIP 細框只在 F 頁）。
- **進度（2026-07-17 Sprint 54）**：多圖／任意矩形置入模型 [實作]（Owner「最複雜架構先做」下，Sprint 53 預定餘項取最重；GAPS #29 (a) 模型一般化＝畫布拖放置圖的模型地基）。document@2 相容擴充 `PlacedImage.rect`（選配任意圖框＝(x0,y0,x1,y1) trim 空間 pt top-down；形狀驗證 x0<x1、y0<y1 快速失敗；**允許溢出版心**＝真書照片略溢 1〜4pt 特徵與出血照片正當用法，不做邊界快速失敗）；rect 圖每頁多張（文件序＝繪製序）、槽式（無 rect）維持每頁一張守門；`resolve_placed_images` 改列表模型 {頁: ((路徑, 影像, rect|None), ...)}，rect 圖不需 figure 槽（A 內文頁也可置圖）、槽式仍需；兩後端 `_draw_image`／`_image` 收 rect（None＝figure 槽既有語意），佔位虛線框改「只看槽是否仍空」（rect 圖不填槽＝InDesign 空框導引語意）；PNG 溢出框由畫布邊界自然裁切（trim 空間預覽）、PDF 置入出血區。測試 436→446（+10，新檔 tests/test_image_rects.py：document rect 驗證與序列化 3／resolve 列表模型 3／兩後端多圖幾何與溢出 2／佔位框槽 gate 1／節式主版共存 1；test_images.py 去重測試隨列表模型同步）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5，自擬 G 頁雙照片示範）：兩 rect 圖框（改造前暗／改造後亮）疊放照片區 → render PNG 親 Read（框位精確、contain 等比、佔位框標示槽區）＋export PDF preflight 12/12＋XObject bbox＝rect＋出血（測試釘死）。**[Shell]／待 Owner（GAPS #29 (d)／#19）**：畫布拖放／縮放置圖 UI 未接線。
- **進度（2026-07-17 Sprint 55）**：獨立文字框 v1 [實作]（Owner「最複雜架構先做」下，§6 Phase 2「文字框建立／串接」的**建立半邊**；圖說自由位置、署名字卡等歷次「自由手排」延後項的機制載體）。document@2 相容擴充 `TextFrame`（text／style／page／rect，rect 同 PlacedImage 座標系可溢出版心；@1 拒絕、schema 驗證快速失敗）；新增 `cjkfolio/frames.py`（兩後端同源單一幾何層）：`layout_text_frame`（欄容量＝floor(框高/字距)、欄距＝級數×(網格行距/基準級數) §10 同構、欄自框右緣右至左、斷行禁則復用 engine break_paragraph〔擠入追出同 body〕、溢出框寬欄不繪並列違規不沉默、未知樣式／橫排樣式快速失敗）＋`resolve_text_frames`（逐頁主版 grid，框頁超出流排頁快速失敗＝不為框造頁）；兩後端 `_draw_text_frame`／`_text_frame`（復用直排 cell 繪製助手；frame violations 併入結果不沉默）；editor canvas 底圖繪框；book.py 章級 text_frames 組裝拒絕（頁號章內語意同 images）。行數上限管理：pdf_writer XMP 助手抽出至 `cjkfolio/pdfx_meta.py`（行為不變，pdf_writer 796 行守住 800）。測試 446→457（+11，新檔 tests/test_text_frames.py：document 3／frames 佈局 5／兩後端 3）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5，自擬）：雙照片＋雙直排辰宇圖說貼照片側（框位溢出版心＝真書 G 頁圖說形態）render 親 Read＋export preflight 12/12＋PDF 框字墨 cx＝frames 行軸（測試釘死）。**v1 限制（GAPS #32）**：不串接（threading 屬「串接」半邊後續專項）、只直排、單一樣式、框無 provenance（畫布互動與編輯待框編輯專項）。
- **進度（2026-07-17 Sprint 56）**：AI 設定檔層 [實作]（§6 Phase 2「AI 設定面板」的資料面半邊；面板 UI 屬真視窗批次）。新增 `cjkfolio/ai_config.py`：`AiConfig`（base_url／api_key／model 三欄位，預設全空）＋`load_ai_config`（缺檔＝空預設不擋流程〔§4.4 AI 為選配增強〕、壞 JSON／欄位型別不符明確錯誤且**錯誤訊息不回帶欄位值**〔金鑰不入 log〕、未知鍵容忍向前相容）＋`save_ai_config`（建父目錄、只序列化三欄位）。金鑰紅線複核：慣例路徑 local/ai-config.local.json 在 .gitignore、預設空值、repo 零金鑰。測試 457→463（+6，新檔 tests/test_ai_config.py：缺檔預設／round-trip／壞 JSON／壞欄位／未知鍵容忍／錯誤訊息不含祕密值）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5）：以使用者既有本機設定檔實載（三欄位皆成功，值零輸出）。
- **進度（2026-07-17 Sprint 57）**：文字框串接 [實作]（§6 Phase 2「文字框建立／串接」的**串接半邊**，關 GAPS #32 (a)；承 Sprint 55 建立半邊）。document@2 相容擴充 `TextFrame.thread`（串接鏈名：同 thread 框依文件序成鏈、文字掛鏈首；解析層守門＝續框帶 text 雙源快速失敗、style 須與鏈首一致、thread 空字串拒絕；序列化續框不寫空 text）；frames.py `layout_thread`（鏈文字一次 tokenize 成 cells、逐框以該框頁主版網格換算容量斷行取欄、以已消費 cell 數切出剩餘續排下一框；切點＝合法行邊界〔_break_cells 行 cells 連續無增刪且行首行尾禁則已解消〕＝框邊界禁則自然正確；中間框排滿即續流、鏈尾仍剩列違規掛鏈尾不沉默）＋`resolve_text_frames` 鏈框統一佈局放回各自頁（頁內繪製序＝文件序，Sprint 54 慣例）；engine 加公開 `break_cells`（cells 級斷行入口，break_paragraph 委派）；兩後端與 canvas 零變更（FramePlacement 介面不動）。測試 463→475（+12，test_text_frames.py：schema 2／佈局 6／resolve 2／兩後端 2）0 退步、typecheck 0、editor 離屏 smoke 0 退步。真實素材驗收（R5，自擬）：「雙照片＋一段圖說流過上下兩框」示範（out/thread-demo）render 親 Read（上框「改造前雜物滿地，」句逗收框尾、下框「改造後留白生光」接續）＋export PDF preflight 12/12＋Gate 4 PyMuPDF 獨立驗串接守恆（15 字無重複無遺漏）與兩框字墨 cx＝各框行軸。**v1 限制（GAPS #32）**：鏈序＝文件序（無顯式序欄位）、無框內強制斷點原語；拉線串框／框編輯 UI 屬真視窗批次。
- **進度（2026-07-17 Sprint 58）**：框 provenance＋畫布框字格反查 [實作]（GAPS #32 (d) 前半；框版的 Sprint 18 provenance＋Sprint 40 畫布反查，框內編輯操作待框編輯專項）。frames.py 佈局改帶 offsets（`normalize_with_offsets`＋`tokenize(offsets=)` 對齊 body 慣例，Sprint 18）＝框 cells span＝來源 text（normalize 前）座標；`FramePlacement` 加 `frame_idx`（自身框文件索引）／`source_idx`（文字來源框＝串接鏈首，span 座標的錨），resolve_text_frames 填、後端不讀（零影響）。editor/canvas.py 加 `page_frame_placements`（逐頁框 placements 單一事實來源）＋`iter_frame_cell_rects`（框字格矩形，幾何與 render `_draw_text_frame` 逐項同源：axis_x_pt 水平中心＋top_pt＋content_i×advance_pt 等距）＋`FrameCellHit`／`resolve_frame_hit`（點框字格 → 框游標：frame_idx／source_idx／span／text）；build_page_scene 框字格入互動層（item data＝("frame", fi, li, ci)，body 字格鍵形不變）；app.py `_on_pick` 分流（點框字格顯示框游標與來源切片、不設 body 插入游標，IME 不入框）。測試 475→478（+3：Cc 位移與 latin span／串接鏈 span 錨鏈首／resolve 雙索引）0 退步、typecheck（含 editor/*.py）0。離屏 smoke 加 C6：自擬串接＋獨立框文件框字格 hit-test 28/28、FrameCellHit round-trip 28 格（續框 span 錨鏈首 (18, 19)）、app 點框分流。真實素材驗收（R5）：以 Sprint 57 真實示範 out/thread-demo/demo.doc.json 逐格 round-trip 15 格全對（續框 span (8, 9) 接鏈首第 9 字）。**[Shell]／待 Owner（GAPS #19／#32 (d)）**：真視窗點框字格視覺對位；框內插刪改（editing 游標入框）與拉線串框待框編輯專項。
- AI 設定面板：Base URL／API Key／Model 三欄位（OpenAI 相容），存本機設定檔；預設空值，金鑰不入程式碼（§4.4 紅線）。**資料面已完成（Sprint 56，cjkfolio/ai_config.py）**；三欄位面板 UI 待真視窗批次。
- 製作者標示「製作者：黃政文」置於關於視窗或 footer 灰色小字。

### Phase 3：樣式模版系統與模版庫（6〜8 週）[實作]

- 樣式新增／修改／繼承；書系模版另存／匯入／匯出；從參考 PDF 萃取起始模版；色票管理。
- docx 匯入與 AI 輔助樣式指派整合（§4.4；依賴樣式系統成形，核心可行性 Spike 5 已驗證）。
- **DoD**：使用者能從零建立一套新書樣式模版並套用成書；匯入一份 txt／md／docx 書稿，經 AI 指派＋人工校正產出排版初稿。

### Phase 4：印刷級輸出與進階排版（8〜12 週）[實作]

- PDF/X-1a 預設、X-4 選項；CMYK 與單 K 文字、出血 3mm、裁切標記、輸出色彩描述檔；字型嵌入子集化與授權檢查；禁則／約物擠壓微調；目錄自動生成；圖文繞排；注音 ruby；縱中橫精修；preflight 面板。
- **DoD**：實檔送印刷廠打樣，色彩與直排品質人類驗收通過。

### Phase 5：出版社驗收與強化（持續）

- 與真實印刷廠多輪打樣校色、多書專案、效能、開源社群釋出與文件。

---

## 7. Pre-mortem（機率 >30% 的最高風險與對策）

| 風險 | 機率 | 早期訊號 | 對策／放棄條件 |
| --- | --- | --- | --- |
| 自製直排引擎的禁則／約物擠壓達不到出版級 | 高 | Spike 1 樣張被人類挑出明顯排版瑕疵 | 先 spike；不達標則改以 Vivliostyle/LaTeX 為排版核心，編輯器退為「結構化編輯＋預覽」 |
| CMYK／PDF-X 色彩在開源鏈上不可控 | 高 | Spike 2 打樣色偏、preflight 不過 | 文字單 K、影像外部轉 CMYK 置入、輸出後處理掛 OutputIntent，與印廠鎖定 ICC |
| Vivliostyle AGPL 授權卡住商業／散布形態 | 中高 | 法務確認傳染條款適用 | 進程隔離（CLI 子程序）、或改用 MIT 的 SILE／LaTeX 路線、或洽商業授權 |
| WYSIWYG 畫布與排版核心同步是長尾工程 | 中高 | Phase 2 即時重排卡頓、選取錯位 | 增量重排、分章快取、雙層回饋（輕量估算＋背景精排） |
| 範圍蔓延，想一次做完整 InDesign | 中 | 里程碑不斷加非利基功能 | 嚴守 CJK 直排利基，非利基功能進落差登記簿延後 |

---

## 8. 已知限制與字型授權策略（GAPS）

發布前須清空或在 release note 以「Known Limitations」公開承認。

- **參考書內容版權（紅線）**：《內在整理》文字與圖像僅限本機 spike 驗證，不進開源 repo、不出現在公開樣張與文件；公開測試素材另備可自由散布文本（維基文庫古籍、青空文庫）。
- **AI 金鑰與私有 endpoint（紅線）**：使用者私有 LLM 位址與金鑰只存 local/ 本機設定檔（git init 時整個 local/ 進 .gitignore），永不入開源 repo；產品介面預設空值。私有 endpoint 在 Tailscale 內網，僅使用者自己可達，不具通用性。
- **不自建字型塑形與柵格引擎**：站在 HarfBuzz／FreeType 上。
- **不保證逐像素一致**：目標為出版級等效品質＋可複製模版。
- **不生成插畫與封面**：手繪格局圖、封面線稿仍需設計師；工具負責排版骨架與置入，不生成美術。
- **首版鎖定直排書冊利基**：橫排雜誌、表格密集型、互動電子書非首版範圍。
- **字型授權（硬限制，法律非工程）：**

| 字型 | 授權 | 編輯器能否內建散布 |
| --- | --- | --- |
| 華康全系列（明體／黑體／仿宋／楷書／手札體） | 商業授權（DynaFont） | **不可**，使用者自備授權 |
| Gill Sans、PepitaMT、Times New Roman | Monotype 商業授權 | **不可**，使用者自備或改 OFL 替代 |
| 思源宋體／黑體（Noto/Source Han） | SIL OFL 1.1 | **可內建** |
| 辰宇落雁體 | SIL OFL 1.1 | **可內建** |
| 全字庫正楷體 TW-Kai／正宋體 | 國發會開放授權 | **可內建** |
| jf open 粉圓 | SIL OFL 1.1 | **可內建** |

**可內建的預設字型組（零授權成本、可隨編輯器散布、可嵌入印前 PDF）：** 思源宋體（內文／章名／引文）＋思源黑體（標題／大標）＋全字庫正楷體 TW-Kai（題詞）＋辰宇落雁體（手寫圖注）＋ jf open 粉圓 或 Noto Sans／Serif（拉丁／頁碼）。匯出時對華康等商用字型做授權檢查並提示使用者自負責任。避免內建 GPL 字型（如王漢宗系列，嵌入需 GPL font exception，且有歷史爭議）。

---

## 9. 印前輸出規格（匯出 PDF 的硬條件）

- 成品 148×210mm，帶出血頁 154×216mm；MediaBox 154×216、TrimBox 148×210 置中、BleedBox＝MediaBox。
- **以單頁完稿交付，禁送 296×210 跨頁對開**（拼版由印刷廠 RIP 處理）。
- 四邊出血 3mm 全出；裁切標記置於出血外 offset 約 3mm。
- 全文 CMYK 或 Grayscale，無殘留 RGB；內文細明體轉單 K90-92，實黑大標可用富黑，灰階照片走單 K。
- OutputIntent 與印廠鎖定（塗布 Japan Color 2001/2011 Coated；非塗布 Uncoated）；總墨量 ≤ 320〜340%。
- 字型 100% 嵌入且子集化；OTF 的 CFF 輪廓走 Type1C 子集；preflight（pdffonts／Acrobat）驗無系統字型替代、無 Type3。
- **直排硬條件**：啟用 OpenType vert/vrt2；半形拉丁縱中橫或正確旋轉；右至左頁序與欄序正確；禁則與約物擠壓在排版層完成並烘焙進 PDF（PDF/X 只負責忠實嵌入已排好的結果，不負責組版）。
- 連續調影像 300〜350ppi、點陣線稿 1200ppi；手繪向量線稿維持向量不光柵化。
- 預設輸出 PDF/X-1a:2001，提供 PDF/X-4:2010 選項，版本與印廠確認。

---

## 10. 決議紀錄（執行期代決與定案，Sprint Runner 讀此段）

| 日期 | 決議 | 依據 |
| --- | --- | --- |
| 2026-06-16 | 鎖定 CJK 直排書冊利基、混合路線（畫布＋專業排版核心）、Phase 0 先驗證 | 規劃版定案 |
| 2026-07-10 | Phase 0 spike 語言一律 Python；ICU 斷行降為非必要 | 執行層補強 |
| 2026-07-10 | AI 只做結構識別，版面幾何一律引擎計算；AI 為選配增強 | §4.4 分工鐵律 |
| 2026-07-10 | 禁則與標點擠壓以 W3C CLREQ 繁中為準，JLREQ 僅參考 | shaping 探針實證 |
| 2026-07-10（Sprint 2，Owner 全權授權代決） | git init 本機 repo、無遠端；.gitignore 排除 local/、assets/reference/、內在整理-*.pdf、spikes/*/out/（版權與金鑰紅線落實），GAPS #5 關閉 | Owner 授權「需要問的直接代決」 |
| 2026-07-10（Sprint 2） | 基線指令定案：typecheck 為 python -m py_compile spikes/spike1-vertical-core/*.py；test 為 python -m pytest spikes -q | PLAN 原未明列，代決補齊 |
| 2026-07-10（Sprint 2） | 滿行字數修正為 32 字（原 22 為每頁行數之誤）；字距 12.08pt；段首縮排 2 字；段間空 1 行槽；每頁 13 行槽 | 逐字座標實測（A 級證據） |
| 2026-07-10（Sprint 2） | 樣張頁腳以 Gill Sans MT／標楷體替位（僅位置對位），入 GAPS #8 | GillSans-Light 與手札體無授權 |
| 2026-07-10（Sprint 3） | Vivliostyle 於本機以系統 Chrome 執行（--executable-browser），不下載 Chrome for Testing | puppeteer 快取無瀏覽器致 spawn UNKNOWN，系統 Chrome 實測可用 |
| 2026-07-10（Sprint 3，技術發現） | @page margin box 會繼承 vertical-rl，頁碼 margin box 必須顯式 writing-mode: horizontal-tb | 樣本頁碼被直排的實測缺陷與修正 |
| 2026-07-10（Sprint 3） | Spike 2b（TeX Live）確認不安裝：2a 已達標，依原閘門條件 | GAPS #4 條件成就 |
| 2026-07-10（Sprint 4） | AI 指派四項設計修正定案（結構優先、AI 粗分、樣式清單候選集、不外推宣稱） | Spike 5 真章重測一手數據 |
| 2026-07-10（Sprint 5） | Vivliostyle 整合形態定案：CLI 子程序＋檔案介面，禁止 in-process import；散布採首次使用隨裝 | Spike 4 報告（官方 FAQ＋GPL FAQ 臂長準則） |
| 2026-07-10（Sprint 5） | Phase 0 閘門條件性通過，可進 Phase 1（唯 Owner 抽檢 GAPS #10 為正式通過前提） | 五 spike 全數有一手結論 |
| 2026-07-10（Sprint 6） | Phase 1 管線語言定 Python：Spike 3 實測純邏輯重排 7.67ms/章已達互動級；Phase 2 GUI／效能語言屆時再議 | §5.2 執行校正原則＋Spike 3 一手數據 |
| 2026-07-10（Sprint 6） | 產品碼結構：cjkfolio/（套件）＋templates/＋tests/＋tools/；out/ 渲染輸出與 assets/reference/ 素材一律本機不入 repo | 版權紅線落實 |
| 2026-07-10（Sprint 6） | 基線指令更新：typecheck 為 python -m py_compile spikes/spike1-vertical-core/\*.py cjkfolio/\*.py tools/\*.py；test 為 python -m pytest spikes tests -q | 產品碼進場 |
| 2026-07-10（Sprint 6） | 樣式幾何換算規則：字距＝級數×(12.08/11.5)、行容量＝floor(欄高／字距)、行槽寬＝ceil(級數／行距)；版面幾何一律引擎確定性計算 | 跨頁實測比例＋§4.4 分工鐵律 |
| 2026-07-10（Sprint 6） | 起始模版字型對映：模版寫 §8 可散布家族、source_font 記原書字型；未入庫家族 FontRegistry fallback 思源宋體並警告 | 字型授權紅線（GAPS #12） |
| 2026-07-10（Sprint 6） | §4.2 修正：章名大標＝明體 W7 21.9pt、部扉大標＝明體 W9 21.9pt；第一章界定為 PDF 頁 19〜34 | 全書 (font,size) 掃描（A 級） |
| 2026-07-11（Sprint 7） | 頁腳 v1 規格：頁碼（全頁，外緣內推 36.8pt、基線 530.43pt）＋書名書眉（奇數頁，齊版心外緣）；鏡像錨定書口側；左頁章節副標待章節結構 | calibration foot_elements 實測 |
| 2026-07-11（Sprint 7） | md 匯入為 block 級（h1→章名、h2→個案大標、h3→章節小標、>→引文），對映表 md_mapping 入模版；行內強調待 run 模型 | §4.4 設計修正 1 |
| 2026-07-11（Sprint 7） | 渲染一律 FT_LOAD_NO_HINTING：辰宇／粉圓 TTF 的 hinting bytecode 使 FreeType 拋 too many function definitions，且印刷級柵格不需 hinting | 實測缺陷與修正 |
| 2026-07-11（Sprint 7） | 抽取工具：手寫／裝飾字型（手札體、辰宇、Pepita、GillSans）不入正文流；md 模式級數對映標題層級、仿宋欄對映引文 | 圖注非結構正文 |
| 2026-07-11（Sprint 8） | PDF 寫出層 v1 形態定案：自寫 PDF 1.4 寫出層（不依賴外部 PDF 函式庫）；盒框依 §9；文字 DeviceCMYK 單 K92（§9 K90〜92 區間取 92）；Catalog /ViewerPreferences /Direction /R2L；逐字顯式 Tm 定位，幾何與 PNG 渲染同源（placement 層） | Sprint 8 探針＋PyMuPDF/pdffonts 獨立驗證（A 級） |
| 2026-07-11（Sprint 8） | 字型子集嵌入形態：CFF（思源，CID-keyed）不保留 GID、內容流用原 CID 走 charset 對映（探針實證思源 CID==GID、體積較 retain_gids 小 30 倍）；TTF（辰宇／粉圓）retain_gids＋CIDToGIDMap /Identity；皆帶 ToUnicode 與 CIDSet（X-1a 對子集 CID 字型要求） | 探針 A/B 兩形態實測比較 |
| 2026-07-11（Sprint 8） | engine.normalize 剝除控制字元（Unicode Cc 類）；缺字（gid 0）PDF 端警告不沉默、仍以 .notdef 輸出 | 真章 md 素材殘留 U+0007 的實測缺陷與修正 |
| 2026-07-11（Sprint 9） | document@2 定案：Paragraph 正規化不變式（text＝runs 串接）、@1 相容照載、@1 帶 runs 拒絕、save 一律寫 @2（單純段用 text 捷徑） | 模型演進與相容策略 |
| 2026-07-11（Sprint 9） | run 覆寫字型與級數，但字槽網格一律依段落樣式（InDesign 慣例：行內樣式不改網格）；md 行內 strong 與 em v1 皆映「內文強調-明體W9」（原書無斜體慣例）；v1 不支援嵌套標記 | 真書強調實排＋排版慣例 |
| 2026-07-11（Sprint 9） | 抽取工具 md 模式把 body 欄 DFMingStd-W9 span 標 **…**（欄內閉合）；控制字元（Cc）於抽取層剔除並列計數 | 第一章實測：整句強調＋對談發言標籤皆 W9（A 級） |
| 2026-07-11（Sprint 10） | X-1a:2001 識別形態定案：header %PDF-1.3；Info GTS_PDFXVersion (PDF/X-1:2001)＋GTS_PDFXConformance (PDF/X-1a:2001)＋Trapped /False＋ModDate 帶時區＋Title 必填；OutputIntent 預設 JC200103（ICC registry 特性化條件，依 ISO 15930-1 免嵌 DestOutputProfile，避開 Adobe ICC 的 EULA 轉嫁義務）；自訂識別強制嵌 CMYK 輸出（prtr）ICC；XMP 不壓縮、pdfx＋pdfxid 雙命名空間 | ISO 15930-1 與 color.org/pdfx.pdf（B 級）＋輸出探針實測（A 級） |
| 2026-07-11（Sprint 10） | 本機 preflight 工具鏈定案：veraPDF 僅驗 PDF/A／UA、不支援 PDF/X（官方文件實查）→ 自寫機械檢查器（cjkfolio/preflight，12 規則、PyMuPDF 獨立解析、未涵蓋項誠實列印）＋pdffonts；Acrobat／印廠認證級列 GAPS #18 | veraPDF 官方 flavour 清單 |
| 2026-07-11（Sprint 10） | 參考書交印檔實測非 PDF/X（無 GTS 識別、無 OutputIntent、含 SMask 透明、TrimBox 與 ArtBox 並存），§0 與 §1 描述據實修正；品質標竿與 §9 硬條件不變 | 探針一手實測（A 級） |
| 2026-07-11（Sprint 11） | 齊行形態定案：行首禁則擠入優先（整串句逗一次決策，溢出 ≤2 槽；超過改追出錨字連句逗下移）、行尾禁則維持退行；非段末行行首行尾雙錨定、內容字距均勻縮放，縮排偏移維持網格字距；偏差 >2 槽維持等距網格並入統計（不沉默）；段末行與滿行不調整 | §1 實測 ±0.4pt＝±1 槽（33 字 −0.37pt／31 字 +0.40pt，A 級推導） |
| 2026-07-11（Sprint 11） | 半形「約物寬度壓縮」（JLREQ 式）不實作：§1 實測本書句逗置中、無半形擠壓，齊行以字距縮放達成 | 跨頁逐字實測（A 級） |
| 2026-07-11（Sprint 12） | 鏡像與頁腳奇偶依「書頁號」（＝版面頁號＋first_page−1）判定，非版面頁號；render 與 pdf_writer 共用同一 book_number 餵行軸（line_axis_x_pt）與頁腳，first_page=1 預設向後相容；版面頁號續作檔名與 --page 選頁鍵 | 「依書頁號」機制正確；惟依據欄原記「偶數頁＝左頁、奇數頁＝右頁＋書眉」為側別誤讀，**Sprint 22 三向實測勘誤為偶右奇左**（GAPS #20） |
| 2026-07-11（Sprint 12） | PNG 缺字不沉默：render 四路徑（cjk／縱中橫／旋轉拉丁／頁腳）偵測 gid 0，回報缺字來源字元，訊息格式與 pdf_writer 一致（Shaper 存 path 供命名）；未統一 placement 層（外科手術範圍，後端統一時再併） | 缺字警告雙後端一致（PUA U+E000 單元測試釘住） |
| 2026-07-11（Sprint 13） | 橫排（horizontal-tb）版面軸形態定案：engine 加 `vertical` 參數復用斷行／禁則（橫排整串 ascii 成一 latin run、不縱中橫、不切碎 ISBN）；layout `page_is_vertical` 由樣式判頁面單一方向，v1 混用 vertical-rl 與 horizontal-tb（slot 幾何不相容）與未知 writing_mode 快速失敗；兩後端幾何同源集中 placement `horizontal_cell_advance_pt`（latin 自然寬、cjk 走 em 格）＋render `horizontal_left_x_pt`（訂口內推、鏡像）／`horizontal_baseline_y_pt`（行由上而下、首行含 ascent）；橫排 CIP 短行左齊不齊行（齊行為直排內文特徵） | honest-planning R2 spike（spikes/spike6-horizontal/）＋頁腳三件組已驗水平 CJK＋latin（Sprint 7〜12）；兩後端位置同源單元測試 abs≤0.3pt 釘死（A 級） |
| 2026-07-11（Sprint 13） | F-版權頁橫排版心為自擬合理幾何（8pt CIP、字距 8.4pt＝×1.05、行距 14pt、滿行 34／每頁 27 行），p178 真實版心未量測留 GAPS #13；公開 CIP 樣張（samples/cip-copyright.doc.json）全自擬虛構書目，不取參考書 p178 內容 | 紅線：參考書內容不入 repo（PLAN §8）；橫排「機制」實作與「參考書逐點版心」分離，後者待 Owner 本機量測 |
| 2026-07-11（Sprint 14） | 向量原件層形態定案：新增 `cjkfolio/primitives`（`StrokeRect`＋`cip_frame_rect`），與 placement 同層、兩後端同源（render PIL 描邊、pdf path ops）；描邊色一律 DeviceCMYK（`K` 算符，維持 §9 全 CMYK 與 preflight color-cmyk-only 不觸 rg/RG）；path ops 以獨立 `q…Q` 狀態塊置於文字塊（BT/ET）之前，狀態隔離不影響文字填色 | honest-planning R2 spike（spikes/spike7-vector-frame/）：手寫 CMYK 描邊框 PDF 經 PyMuPDF 解析 re/S/K 齊備、既有 color pattern 不命中、渲染框像素（A 級）；兩後端框座標同源單元測試 abs≤0.3pt 釘死 |
| 2026-07-11（Sprint 14） | CIP 細框（cip-box）幾何自擬定案：圍住橫排 CIP 內容網格盒（滿行寬×n_lines×行距）四周留 pad 6pt、純黑 0.5pt 描邊；由主版 `frame` 欄位配置（`FrameSpec` kind/cmyk/line_width/pad，未知 kind／非 4 元素 cmyk 快速失敗），v1 只 cip-box、只橫排觸發（gate＝not vertical）；此原件層為後續 B 部扉雙線菱形框、D 目錄水平虛線的地基。p178 真實版心與框未量測續留 GAPS #13 | 紅線：框幾何全自擬、不取參考書 p178；「向量原件機制」與「參考書逐點一致」分離 |
| 2026-07-11（Sprint 15） | 虛線原件形態定案：`StrokeLine`＋`toc_rule_line` 兩後端同源；PDF 用原生 `d` dash 算符（獨立 q…Q 隔離，狀態不外洩）、PNG 分段畫（灰值 255×(1−k) 只取 k 分量，灰階預覽限制）；虛線全頁寬貫穿＋兩側出血延伸 3mm（§9 貼邊全出）；由主版 `rule` 欄位配置（`RuleSpec`，y_from_top_pt 必填、未知 kind／壞 cmyk 快速失敗），v1 只 toc-rule、只直排觸發（gate＝vertical）。虛線幾何參數（y 122.46pt、1.0pt、dash [3 2]、灰 K57）為 p003 一手量測，依 Sprint 7 頁腳先例量測參數入模版 | p003 探針量測（A 級）＋spike8 三探針（dash 解析／狀態隔離／PIL 分段） |
| 2026-07-11（Sprint 15） | 部扉「雙線菱形框」規則化不做：p069 實測為手繪風向量（單 draw 608 段不規則路徑、0.61pt 灰），規則幾何自擬等效性低，屬美術資產（§8 不生成插畫與美術）；部扉頁型後續只做大標置位，裝飾框待「使用者置入向量資產」機制（Phase 2〜3） | p069 get_drawings 一手解析（A 級） |
| 2026-07-11（Sprint 15） | D-目錄天頭修正 47.63mm（＝條目內容起點 135pt，p003 Case 標籤 y 實測；內容一律在虛線之下）；虛線 y 與天頭分離配置（rule.y_from_top_pt 獨立於 margins.top）。參考書「篇名嵌線」（虛線在篇名處斷開）與條目縮退屬目錄頁型工程，v1 不做、入 GAPS #13 | 第一輪樣張 Read 目檢抓到文字穿線的實測缺陷與修正 |
| 2026-07-11（Sprint 15） | 補記 Sprint 13、14 漏更新的 CHANGELOG（v0.8.0、v0.9.0，內容取自 devlog 與 commit message，標明補記）；Sprint Runner 收尾清單此後以 CHANGELOG 為必查項 | R7：落差不沉默 |
| 2026-07-11（Sprint 16） | 目錄條目形態定案：`page_no` 為 document@2 相容擴充選配欄位（僅數字字串）；頁碼掛段末行、直排逐位直立、底錨對齊（p003 實測 490pt）；引導線為行軸垂直實線（0.1pt、單 K92 同文字）自標題末＋2pt 至頁碼頂−2pt；標題頁碼重疊（線長 ≤0）列 violations 不畫線；帶 page_no 落在無 toc 配置主版快速失敗 | p003 條目量測（A 級）＋兩後端 parity 單元測試 |
| 2026-07-11（Sprint 16） | 頁碼字距依 §10 既有換算規則（級數×12.08/11.5），字級由頁碼字元樣式決定（v1 用「頁碼數字-GillSans」8pt 粉圓）；與 p003 實測 Times 9pt 同構不同值，目錄「章名條目黑 W5」樣式層補充留 GAPS #13 | 換算規則一致性優先於逐點復刻 |
| 2026-07-11（Sprint 17，Owner 指示風險前置） | Phase 2 畫布架構前置 spike 定案：PySide6＋QGraphicsScene 雙層畫布（底圖層＝既有 PNG 渲染後端、互動層＝layout 幾何同源透明字格 item）可行性成立；畫布語言候選 Python（PySide6，與 Phase 1 管線同語言）自此有一手數據，正式技術棧於 Phase 2 開工定案；spike 探針不入 pytest 基線（避免基線硬依賴 GUI 套件） | Spike 10（spikes/spike10-canvas-sync/，A 級一手數據：回路 37ms、hit 214/214、5,361 item 52ms） |
| 2026-07-11（Sprint 17） | Phase 2 首項工程定：engine 流排時在 PlacedLine／Cell 掛文件 provenance（para_idx／char offset，與 page_no 同純載體模式），供畫布點選 → 文件游標映射；spike 現以 (page, placed_idx, cell_idx) 為 hit-test 身分屬幾何鍵，非文件鍵 | Spike 10 顯式暴露的介面缺口 |
| 2026-07-11（Sprint 18） | provenance 座標系定案：Cell.span＝文件段 text（normalize 前原字串）半開區間；normalize 分解為 normalize_with_offsets（正規化＋原索引表）單一事實來源；ascii run（latin／tcy）span 覆蓋整串、內含被剝除 Cc 時區間自然涵蓋（選取涵蓋不可見字元）；直呼 tokenize 無 offsets 時 span 為輸入座標 identity（舊 API 相容） | 第一章 5,361 cells＋自擬含 Cc／表現形段 round-trip 全 0 錯（A 級） |
| 2026-07-11（Sprint 19） | F-版權頁版心量測定案：top 以「首行 baseline 錨定」換算（top＝baseline−級數×ASCENT_RATIO＝128.2−5.63×0.88＝123.25pt＝43.48mm，文字位置優先於 bbox 口徑）；框色暖黑同內文 → 產品單 K92；FrameSpec 加 pad_v_pt（選配，None＝同 pad_pt）表達 p178 實測不對稱 pad（水平 5.05／垂直 4.94）；lines_per_page 45 為幾何推導非量測；後段行距分區（12.73／11.73）與框上標題行不擴 v1 模型，入 GAPS #13 誠實記錄 | p178 一手量測（A 級）＋樣張獨立抽驗框 y0=118.31／baseline 128.2 與實測精確重合 |
| 2026-07-11（Sprint 20） | B 部扉頁型定案：文件兩段（段 1 標籤-篇序小標 slot 0 右、段 2 部扉大標 slot 1），行間距全含於 B 行距 34.37pt（標籤樣式 para_gap_slots 1→0）；B 主版 mirror=false、天頭＝部序號首字頂 62.38mm、outer 63.53mm（slot 0 行軸 228.49 反推）；真書大標首字頂比部序號低 6.02pt（0.26 字槽）為 v1 整數槽模型已知差異入 GAPS，不擴段前 pt 偏移模型（Phase 2〜3 樣式系統再議）；y 向 bbox 口徑差（思源 ascender 鬆於華康）屬字型度量差異非位置錯誤（§3.3 不比字形輪廓） | 三部扉一手量測（A 級三頁互證同值）＋樣張行軸抽驗 228.49／194.12 精確重合 |
| 2026-07-11（Sprint 21） | 目錄嵌線與縮退形態定案：穿線判定純幾何（行首字頂 y＝天頭＋start_slot×字距 < 虛線 y 即斷開；「嵌線」本義，非樣式白名單）；條目縮退用段級整數槽 head_offset（engine 揉進 start_slot，首行疊 indent、容量同縮；縮退 3 槽 29.93pt vs 真書 27.04，+2.89pt 差入 GAPS，維持 Sprint 20「不擴 pt 偏移模型」決議）；斷開邊距取行槽緣口徑量測中值（before 28.5／after 3.9，真書手排離散 26.9〜30.1／3.7〜4.1 誠實記錄）；斷開 x 區間由後端 rule_break_ranges 以 slot＋book_number 求（同 TocEntryMark 行軸模式，兩後端同源）；帶起訖（前置條目無線、帶起於首篇名、跨頁延續記號±10mm）與篇序 11pt 密排騎線＋詩句 16pt 同行混排不建模（v1 已知差異入 GAPS）；Sprint 15「貫穿頁寬」修正為設計推定（當時未量 x 起訖），本次量測證實真書分段 | p002/p003 三篇名一手量測（A 級：篇名天頭 107.96 三處同值）＋樣張 PyMuPDF 抽驗兩段端點 0.00pt 重合 |
| 2026-07-11（Sprint 22） | 鏡像側別定案（修正 Sprint 12 決議）：**偶數書頁＝右頁（書口在右）、奇數書頁＝左頁（書口在左）**；右翻直排書 spread＝（偶右、奇左），讀序右→左＝頁碼小→大；Sprint 12「奇右偶左」為西式左翻書慣例誤植，其「與真書右翻一致」比對記錄錯誤（當時測試與實作同源同錯，未被攔截）。實作：render.is_right_page 單一事實來源（line_axis／horizontal_left／兩後端 footer 共 5 判定點收斂）；footer 奇偶 gate（pages 配置）與書口側別拆分；mirror=false 恆以 outer 槽為起排側（直排 B＝右、橫排 F＝左，B/F 幾何皆不變）；A 書名書眉 pages odd→even；F margins outer↔inner 對調（25.81＝p178 左頁書口，名實相符） | 真書三向互證（A 級）：頁碼側（索引 4/12/30/40 四 spread：偶頁頁碼 x 789.5 書口右、奇頁 x 36.9 書口左）＋書眉側（書名皆偶頁）＋版心側（偶頁右邊距 21.00mm＝outer 精確）；第一章 --first-page 20 兩頁 Read 親驗＋CIP 框 0.01pt 複驗 |
| 2026-07-11（Sprint 23） | E 序文版定案：版心與頁腳全承 A（一手驗證非推定）；序文標題樣式勘誤改名「推薦序大標-黑體」（NotoSans Medium 12.9pt；原「楷書W5 16.3pt」為 scan_reference_styles 誤把署名行長橫「─」當標題，個案大標 17.9pt 為不同級不共用）、para_gap_slots 4（內文自 slot 5 起）；欄標「推薦序」肩位（標題行右 16.2pt，非 23 網格）與署名行（楷長橫＋明 W9 混級、y 頂底隨頁變動＝自由手排）v1 不建模；模版 JSON 經 json.dump 統一重排（indent=1），內容等價 | p004/p007/p009 三頁互證完全同值（A 級）＋樣張行軸抽驗 341.27 vs 推導 341.26（重合）、真書 342.16（差 0.9pt 記錄）＋preflight 12/12 |
| 2026-07-11（Sprint 24） | 目錄章名條目定案：帶頁碼章名＝黑體 W5 11.5pt（思源黑體 Medium，勘誤原記楷 W3 9.5pt＝掃描把不帶頁碼摘要層字型誤設為章名層，同 Sprint 23 署名長橫勘誤）；head_offset 3→2 槽（黑字距 12.08×2＝24.16pt，章名首字框頂 132.12／墨頂 137.42 貼真書 135.15，整數槽＋思源華康字框度量差入 GAPS）；不帶頁碼摘要層（楷 W3 9.5）、【結語】黑 W5 10pt 變體、章名摘要縱向錯落與多層列距 v1 不建模；量測工具加 entry_columns 直排列分析（按字中心 x 聚列） | p002/p003 一手量測（A 級：章名黑 W5 全帶頁碼 top_y 135.15、摘要楷 W3 9.5 不帶頁碼 top_y 166、篇名明 W7 16pt 穿線）＋樣張 PyMuPDF 抽驗 4 列 SourceHanSansTC-Medium 列距 23pt＋preflight 12/12 |
| 2026-07-11（Sprint 25） | C 個案扉頁定案：個案大標 NotoSans Medium 17.9pt 置 slot 1、資訊列（Case 編號 DFHeiStd-W5 13pt＋副標 11.4pt）slot 0、內文承 A 自 slot 2（天頭 92.09pt、首行縮排 2 字＝116.47）；大標右頁 line_axis 331.25 貼真書墨欄中心 331.28（差 0.03）；個案中標 para_gap_slots 1→0 勘誤（實測資訊列與大標相鄰，同 Sprint 20 標籤先例）；資訊列雙元素、內文精確 gap、雙線框 v1 不建模。Gate 4 閉環抽驗發現 GAPS #21（直排字墨 cx 系統性偏書口 +8.5pt，全直排既有正確性問題、非本 Sprint 引入、非單一頁型）：不在本 Sprint 硬修（context 保護、避免 Sprint 22 式同源同錯降級），列 Sprint 26 專項 | C 個案扉頁一手量測（A 級，數十頁互證，tools/measure_case_page.py）＋Gate 4 PyMuPDF get_texttrace 抽驗（A 級：大標墨 cx 339.75 偏 line_axis 331.25＋8.5pt，資訊列 11.4pt 同偏＋8.50 與字級無關，真書華康大標墨＝欄中心差 0.03） |
| 2026-07-12（Sprint 26） | GAPS #21 勘正定案：Sprint 25 Gate 4 的「直排字墨偏 +8.5pt」非置中 bug，係量測拿 PDF MediaBox 座標（含 3mm 出血 8.5039pt）比 trim 空間 line_axis 之框錯配（偏移與字級無關＝純出血常數，非隨字級變的置中誤差）；渲染層本就正確，兩後端字墨在各自 trim 框內對準 line_axis 且吻合真書 ink 中心。不修渲染碼（避免反向雙重補償破壞正確置中）；新增 PDF 側置中回歸測試（框一致扣 BLEED_PT，大標＋資訊列＋反例保護）、修正 test 誤導註解、關 GAPS #21 | 實證 probe＋回歸測試（A 級）：大標 17.9pt／資訊列 11.4pt MediaBox cx 各扣出血後＝line_axis 331.25／354.25（Δ+0.00pt）；既有 test_export_glyph_geometry_on_grid 早已用 BLEED_PT 扣出血比對、test_render_single_char_lands_in_first_cell 早已驗 PNG trim 空間置中，Gate 4 手驗漏扣出血常數 |
| 2026-07-12（Sprint 27） | G-圖文版頁型骨架定案（§4.2 主版 7 種完備）：版心承 A 一手驗證（圖框橫向承 A 版心鏡像感知）、圖框保留區（photo-slot，FigureSpec 縱向 top 107.04／bottom 467.62pt、承版心橫向鏡像，淡虛線佔位框四邊兩後端同源 dash [4 3] K30）、圖說標籤段落樣式（辰宇落雁體 15.9pt）。與 B-部扉同型（美術本體延後）：真書照片嵌入為 Phase 2 圖片置入（§9 灰階單 K／300-350ppi）、房名黑體標題＋辰宇自由圖說位置＋裝飾括號為手繪美術（§8 不生成）、前後照片配對與圖文繞排為 Phase 4，皆入 GAPS #13。佔位框為 Phase 1 版面骨架導引（InDesign 空框慣例，真書照片無邊框），Phase 2 圖片置入取代、不留框線；preflight 誠實聲明「v1 尚無影像置入」 | 圖文版頁一手量測（A 級，32 全頁圖文版頁互證，tools/measure_figure_page.py）：分類濾除內文內嵌小圖（Type 2，img_frac≈0.1＋body≳60），只聚合全頁圖文版（Type 1，img_frac≳0.2＋body≈0＋辰宇圖說）；圖框橫向承 A 版心（R 頁 x0=72.51／x1=360.0、L 頁 59.53／347.02 鏡像）、雙照片區 top 107.04／bottom 467.62 一致、辰宇圖說 15.92pt（31 span 同值）；佔位框四邊 m/l 座標＝figure_slot_rect＋出血兩後端同源單元測試 abs≤0.3pt 釘死、preflight 12/12 |
| 2026-07-12（Sprint 28） | preflight trailer-id 規則同認 /ID 兩式（`<hex>` 與 `(literal)`）：PyMuPDF `xref_object` 對「解碼後 16 bytes 全可列印」的 /ID 兩組字串重序列化為 literal `(...)`，原 regex 只認角括號 hex 致基線 `pytest spikes tests` 順序相依假陰性（全套累積使 TocPDF 的 /ID＝`md5(bodies)` 落入可列印區間，單獨執行不觸發）；修檢查器不動渲染／寫出（檔案 /ID 恆為合規兩組非空字串、PDF 無缺陷），空 `<>`／`()` 仍判失敗（方向安全） | probe 手工 PDF＋fitz 讀回實證（可列印→literal＋regex 落空、非可列印→hex＋命中，A 級）＋回歸測試（TDD RED→GREEN）＋完整基線 206 綠 0 退步 |
| 2026-07-12（Sprint 29，Owner 指示「最複雜架構先做」） | 引擎 pt 精度模型首軸落地：段落樣式加 `lead_offset_pt`（段級 inline 軸 sub-slot pt 偏移），純位置微調不改斷行容量（不進 `_break_cells`），載體鏈 style→spec→PlacedLine→兩後端 body inline-start（`top_pt + start_slot×advance + lead_offset_pt`）同源一致式；v1 只套用直排 body（橫排 body 與 toc 引導線／rule 穿線判定無 combined 用例，入 GAPS #13）。**重議 Sprint 20「段前 pt 偏移延後 Phase 2〜3」決議**：Owner 要求最複雜架構正式觸發。部扉大標-明體W9 lead_offset_pt 6.02，大標首字頂 cell_top 176.84→182.86pt 貼真書（部序號維持天頭 176.84），關 GAPS #13 部扉大標 6.02pt 子項 | Sprint 20 三部扉一手量測（A 級 182.86）＋兩後端兩渲染差分（offset 6.02 vs 0，字型 ascent 抵消，PDF get_text／PNG 裁欄 getbbox 皆測得大標下移 6.02、部序號 0 位移，測試 206→209 0 退步） |
| 2026-07-12（Sprint 30） | 目錄章名條目 inline 偏移＋Gate 4 出血座標框勘正：lead_offset_pt 接入 layout `_toc_marks`（title_end→引導線起 leader_y0）與 `_rule_breaks`（穿線判定 line_top），目錄條目 body 偏移時引導線起點與穿線同步跟隨 body 實位（Sprint 29 刻意延後部分，本 sprint 正題；頁碼底錨與線終不隨條目）；目錄-篇章條目 lead_offset_pt 6.24＝條目墨頂扣 3mm 出血後於 trim 空間貼真書 135.15。**勘正 Sprint 24 墨頂比對之出血座標框錯配（GAPS #21 同型）**：原「model 墨頂 137.42 vs 真書 135.15、差 +2.27」係拿 model 含出血 media 比真書無出血 trim（真書 PDF 本機實測 media＝trim＝bleed 無出血），未扣出血 8.504pt；扣後 model trim 128.91 vs 135.15，正確 lead_offset +6.24 下移（非原記 -2.27 上移）。釐清交接 (a)「縮退 29.93 vs 27.04」為 Sprint 21 舊狀態（head_offset 3、楷 9.5pt），Sprint 24 已勘誤併入 (b)（head_offset 2、黑 11.5pt），當前僅此一縮退樣式、非並列兩目標 | 真書頁盒 probe 無出血（頂 padding 0.000pt）＋model media span 137.42 扣出血 128.91（A 級）；數學自洽 +2.27＝真實 trim 差(-6.24)＋出血(8.504)；端到端 samples/toc preflight 12/12＋條目墨頂 trim 135.15 精確＋兩後端 parity＋214 passed 0 退步 |
| 2026-07-12（Sprint 31） | para_gap block 軸 pt 精度主軌否決＋轉替代軌 A（measure 工具共用模組）：honest-planning R1／R8 先量測再動工，三線 A 級證據確認 block 軸（段落堆疊＝水平欄位，slot→line_axis）本就整數槽對齊、無 sub-slot pt 目標（別於 Sprint 29/30 inline 軸 6.02/6.24pt 真實偏移）：(1) C 主版 evidence 明載「大標 para_gap 1 使 body 落 slot 3 vs 真書 slot 2」為整數槽差非 pt；(2) 中標 cx 354.24＝slot 0、大標 331.28＝slot 1（Δ0.03）皆恰整數槽；(3) probe 量 33 頁內文欄 gap/pitch 4.2〜6.0 隨內容變動無固定殘差。釐清 Sprint 30 交接「需 block 軸 pt 偏移」為前提誤讀，硬加無真實偏移的 para_gap_offset_pt 違反 R5 故不建機制。依 Owner 預授權轉替代軌 A：抽 tools/_measure_common.py（HALF_W／PT_PER_MM／spans／is_spread／reference_pdf／write_measurements／stdout_utf8＋BLEED_PT／strip_bleed Gate-4 換算正典），4 measure 工具淨減 15 行重複、清 toc/cip 未用 PT_PER_MM 死碼 | 三線 A 級量測（C evidence＋既有 cx＋33 頁本機 probe）＋跨 sprint 佐證（部扉欄距 34.37＝1 pitch、序文 4.99 槽 0.9pt 歸因 inner margin）；行為保持以 4 工具 JSON 逐字 diff 全 IDENTICAL＋214 passed 0 退步 |
| 2026-07-12（Sprint 32） | 替代軌 B：近 800 行測試檔依頁型分檔。test_layout_render.py（795 行）與 test_pdf_writer.py（791 行）各抽「主版向量裝飾與目錄頁型」連續塊（CIP 細框／目錄虛線／條目頁碼引導線／篇名嵌線＋pdf 的 G 圖文佔位）為新檔 test_render_vectors.py（13 test）／test_pdf_vectors.py（14 test）；核心降至 495／469 行。循 tests/ 既有「各檔自帶 template fixture」慣例（新檔自帶 fixture／helper，不建共享 conftest），測試本體以 sed 逐位元組搬移零轉錄、header 手寫。核心 test_layout_render 補 PT 常數（章名條目留核心）、test_pdf_writer 移除抽出後未用的 primitives import | 純測試重組行為保持：pytest 214 passed 總數不變（39＝26＋13、35＝21＋14 無 test 遺失或重複）＋4 檔 import 皆有使用無孤兒＋py_compile 全綠＋tests/ 無 em-dash |
| 2026-07-12（Sprint 33，Owner「最複雜架構先做」下的真實 Phase 1 剩項） | 個案大標 para_gap 樣式拆分（GAPS #13 剩項）：`個案大標-NotoSans`（para_gap 1）身兼 C 扉頁大標與 md h2／內頁大標（42 頁），扉頁大標後內文應相鄰落 slot 2（Sprint 25 A 級）但 para_gap 1 落 slot 3。承 Sprint 31 診斷（此為整數槽差非 sub-slot pt）以樣式拆分正解：新增 `個案扉頁大標-NotoSans`（para_gap 0）給 C 扉頁、原名保留給 h2／內頁（不改 md_mapping、churn 最小）；InDesign 慣例＝同視覺角色不同段後距屬不同段落樣式。內頁 h2 para_gap 1 為 status-quo 保留（非新量測宣稱，續留 GAPS #13） | Sprint 25 C 扉頁一手量測（A 級：內文承 A 自 slot 2）＋確定性 layout（committed 樣張 case-divider 三段 slot [0,1,2]、0 違規、修正前 slot 3）＋render PNG Read 親驗（三直排列相鄰、內文緊貼大標無空欄、承 A 共頂邊）＋214 passed 0 退步 |
| 2026-07-12（Sprint 34，Owner「最複雜架構先做」下量測釐清） | 個案中標「12.9pt 變體」釐清否決：模版 note 原記「另有 12.9pt 變體見掃描」為誤導待查標記；量測 33 個案扉頁右半頁頂 NotoSans 僅 11.4pt（資訊列副標）＋17.9pt（大標）、12.9pt 0 命中，全書 81 個 12.9pt span 皆序文標題句（PDF 3/6/8/12/14/16/174 左半），屬 推薦序大標-黑體（Sprint 23 定案），非個案中標變體。個案中標＝單一 11.4pt 確認，勘正模版 note＋GAPS #13 子項＋加級數分離守門（個案中標 11.4≠推薦序 12.9）；不改 size／幾何（現狀已正確，同 Sprint 26 勘正非修碼）。Gate 3 掃出同類「掃描見變體」待查標記（旁注 9pt／Case 編號 15.9pt）屬不同樣式，未量測不動，登記後續 | 個案扉頁 33 頁一手量測（A 級：0 命中 12.9pt）＋全書 12.9pt span 落點交叉檢查（81 個全序文頁）＋守門測試 test_styles 27→28＋215 passed 0 退步 |
| 2026-07-12（Sprint 35，Owner「最複雜架構先做」下量測釐清，AskUserQuestion 定案 B） | 個案扉頁 slot 0「Case 編號黑 W5 13pt『01』雙元素」量測否決＋Sprint 25 slot 0 誤讀勘正：候選 A（最複雜架構）依 R1 先量測，兩路探針 33 頁交叉驗證推翻前提。slot 0（cx 354）實為 DFHeiStd-W7 欄標（11.5pt×26 頁「個案資料／廖心筠整理／鄧惠文醫師／心理師訪談」、10.5pt×7 頁「理解與祝福」），非個案中標 11.4pt 亦非 Case 編號 13pt；黑體與大字數字編號「01」全書 0 命中、真書 Case 編號＝頁腳 PepitaMT 9pt「Case N」（top 508.3）；個案中標 11.4pt（【格局】【居住者】）141 span cx 全落 93~231 資訊區非 slot 0；13pt DFHeiStd 為資訊區內文中標（cx 117~240）非 slot 0 編號。Owner 定案 B（勘正記錄＋守門，不重定模型）：勘正 個案中標 note＋C evidence 記量測真相、加字型與級數守門（防依誤導 note 把黑 W7 或 13pt 併入個案中標）、不改 render／樣式模型／case-divider；黑 W7 欄標樣式＋個案中標移資訊區＋多欄位佈局登記 GAPS #13 後續專項。第四例掃描誤讀（承 Sprint 23／24／34），最深（推翻 Sprint 25 C 主版 slot 0 建模） | 個案扉頁 33 頁兩路探針一手量測（A 級）：Q1 slot 0 聚合 DFHeiStd-W7 11.5／10.5pt 全覆蓋、Q2 個案中標 cx 93~231、Q3 13pt cx 117~240、Q4 數字編號 0 命中、頁腳 Pepita「Case N」33 頁齊備；守門 test_styles 28→29；探針跑完即刪（scratchpad 紅線不入 repo）；215→216 passed 0 退步 |
| 2026-07-12（Sprint 36，Owner「最複雜架構先做」下量測釐清，承 Sprint 34 Gate 3 待查標記清查收尾） | 旁注 9pt／Case 編號 15.9pt 兩「掃描見變體」待查標記量測確認：依 R1 先量測，兩路探針（scan_font 字型 size 分布＋scan_size_band 級數反查）交叉驗證。**與 Sprint 34（12.9pt）／35（slot 0 13pt）誤植 0 命中相反，兩變體皆真實存在**：旁注-手札圖注 HanziPenTC-W5 除 8.0pt 主體另有 9.0pt（raw 8.955，4 頁 PDF 25/60/61/93、34 字、頁面中上部 top 82~338 非頁腳）＝圖注大一號；Case編號-手寫拉丁 PepitaMT 除 9.0pt 頁腳主體另有 15.9pt（raw 15.92，10 頁章扉大號 top 86.2 x0 192.7）＋另揭 10.4pt（目錄 Case 編號 PDF 1/2，note 原僅記 15.9pt）；15.9pt Pepita 章扉與辰宇落雁 15.9pt 圖說同級不同字型（守門防混淆）。處置（同 Sprint 34／35 勘正記錄型）：勘正兩 note 升 A 級量測參數（頁數／字數／raw／位置）、補記 Pepita 10.4pt 目錄變體、加守門測試釘主體級數與 source_font；變體屬美術／自由佈局層（§8）Phase 1 無渲染用例不建獨立樣式，建模登記 GAPS #13 後續專項；Sprint 34 Gate 3「掃描見變體」待查標記至此全數清查完畢 | 個案／序文／章扉頁一手探針量測（A 級）：A HanziPen 全 size 分布（8.0pt 173 頁＋9.0pt 4 頁）、B Pepita 全 size 分布（9.0pt 153 頁頁腳＋10.4pt 2 頁目錄＋15.9pt 10 頁章扉）、C 8.5~9.5pt 級數反查（HanziPen 9pt 獨立 34 字）、D 15~17pt 級數反查（Pepita 15.9pt 61 字 vs 辰宇 15.9pt 186 字同級不同字型）；守門 test_styles 29→30、探針跑完即刪（scratchpad 紅線不入 repo）、216→217 passed 0 退步 |
| 2026-07-12（Sprint 37，Owner 定案升級 C＝完整重定 C 主版，AskUserQuestion 於 Sprint 36 收尾定案） | C 個案扉頁 slot 0 黑 W7 欄標樣式建模（推翻 Sprint 35「選 B 不重定模型」，正式進入 C 主版重定）：新增段落樣式 個案欄標-黑W7（思源黑體 Bold 11.5pt、indent 0、para_gap 0、lead_offset 0）建模 slot 0（cx 354，Sprint 35 揭露＝DFHeiStd-W7 欄標非個案中標）。33 個案扉頁一手量測：欄標首字頂 92.1＝天頭 92.09（承 A、字框頂天頭、墨頂差為字型 bearing）、縱向 4~6 字佔 block slot 0 一行、11.5pt×26 頁（資訊頁「個案資料」等）主流建模／10.5pt×7 頁（訪談頁「理解與祝福」）變體記錄；DFHeiStd-W7 對映思源黑體 Bold（§8，思源黑體有 Bold 檔不 fallback，別於章名明 W7 用 heavy＝宋無 Bold）。case-divider 樣張 slot 0 個案中標→欄標（自擬「案例速寫」）、個案中標移出。資訊區多欄位佈局（slot 2~4 空欄＋slot 5~11 欄位標籤／內文／13pt 中標交替）＋個案中標移資訊區為 Sprint 38（線性堆疊不可表達，需新機制） | C 個案扉頁 33 頁一手量測（A 級，臨時探針跑完即刪）：slot 0 欄標 cx 354.6 top 92.1 11.5／10.5pt HeiW7、slot 1 大標 cx 331.6 top 98.0、資訊區 cx 93~231；render PNG 墨跡三直行 trim_cx 354.2／331.2／308.2＝模型 line_axis（差 0.05）、欄標 SourceHanSansTC-Bold 不 fallback、preflight 12/12、兩後端 parity；218 passed（217→218）0 退步 |
| 2026-07-12（Sprint 38，Owner「最複雜架構先做」下 Phase 1 剩項） | C 個案扉頁資訊區欄位卡片建模＋否決「需新機制」前提（承 Sprint 37 交接「線性堆疊不可表達需新機制」）：honest-planning R1 先量測全 33 個案扉頁（scratchpad 探針跑完即刪），首內容 slot 分佈 33/33＝slot 5、空 slot 2~4 為鐵律。資訊區＝相鄰不同 slot 的線性段落（欄位標籤 個案中標-NotoSans 11.4pt indent 0 頂格 top 92.09、欄位內文 內文-明體直排 indent 2 縮排 top 116.25，非同 slot inline 分區），現有線性流排＋既有樣式＋indent／gap_after 即足表達、無需新引擎機制（同 Sprint 31/34/35 量測後否決「需新機制」前提，R2 判定既有能力復用無需新 spike，先例＝E 序文版 Sprint 23）。勘正 Sprint 25「內文自 slot 2（top 145.75）」誤讀＝第五例 C 主版 slot 誤讀（承 Sprint 34/35/36）：真書內容自 slot 5，個案扉頁大標 para_gap 0→3（Sprint 33「gap 0＝內文相鄰 slot 2」前提隨之勘正）。case-divider 升級欄位卡片（自擬「【空間】／【成員】」兩欄位）slot [0,1,5,6,8,9] 空 2~4／7；test_layout_render C 測試與 test_pdf_writer case 置中測試充實為欄位卡片守門（slot 0/5/6/8/9 兩後端字墨對準 line_axis），測試數 218 不變（勘誤＋既有機制建模型 Sprint，同 Sprint 26/31） | 全 33 個案扉頁探針一手量測（A 級：首內容 slot 5 分佈 33/33、空 2~4 鐵律、欄位標籤 top 92.3／內文 top 116.5、13pt 中標屬訪談頁節標題非資訊區）＋E 序文版先例（Sprint 23 推薦序大標 gap 4→內文 slot 5 同機制）＋三方同源驗證（layout slot [0,1,5,6,8,9]／PDF 字墨 cx／PNG 墨跡直列 cx 皆對準 line_axis，PNG 列1→2＝4.00 slot 空 2~4、列3→4＝1.99 slot 空 7）＋render 三字型欄標 Bold 不 fallback＋preflight 12/12＋218 passed 0 退步 |
| 2026-07-12（Sprint 39，Owner AskUserQuestion 定案「收尾轉 Phase 2」） | Phase 1 骨架收尾定案（[Doc] 無程式碼變更）：honest review 實查 §6 Phase 1 交付齊備（文件模型 document@2＋三層樣式 18 段落／9 字元＋A〜G 七主版 templates/neizai-zhengli.json 實查命中＋直排引擎 禁則／約物擠壓／齊行／縱中橫／橫排／依書頁號鏡像＋自寫 PDF/X-1a:2001 匯出＋機械 preflight 12 規則＋txt／md 匯入＋兩後端 PNG/PDF 幾何同源），218 測試綠、typecheck 0，機制級 DoD 達成。剩餘 GAPS #13 項全數彙整入新 #22 Known Limitations（甲 細項延後＝結語／訪談欄標變體、目錄摘要層；乙 需新機制＝肩注／行距分區／帶起訖，前 Sprint 已誠實判 v1 不建模；丙 §8 美術不生成＝部扉手繪框／署名自由手排／G 房名圖說；丁 後續 Phase＝G 照片 Phase 2、圖文繞排 Phase 4），均不阻擋轉場。正式 sign-off（R5 人類抽檢）待 Owner、執行工程師不代行：GAPS #10（Spike 1 對比圖抽檢，Phase 0 正式通過前提）與新 #23（斷行逐行一致率比對）為 Owner-hands-on。下個 Sprint 轉 Phase 2 首項＝Qt 畫布 IME 直排輸入真視窗實測（GAPS #19，§7 未退場最大產品風險＝畫布與排版核心同步，僅 Spike 10 初驗） | honest review 模版 json 實查（7 主版／18＋9 樣式，A 級）＋基線 218 綠 typecheck 0＋Owner AskUserQuestion 定案（收尾轉 Phase 2）＋§7 Pre-mortem＋honest-planning R5／R7（Known Limitations 公開承認、人類抽檢不代行） |
| 2026-07-12（Sprint 40，Owner AskUserQuestion 定案「建 PySide6 真視窗 demo 骨架」） | Phase 2 技術棧正式定案 PySide6（Qt 6 官方綁定，LGPL；Spike 10 A 級數據，§5.2「Phase 2 開工定案」條件成就）＋Phase 2 開工首項真視窗畫布骨架 [實作]／[Shell]：新增 editor/ 套件（canvas.py 雙層畫布核心＋app.py 真視窗 QMainWindow＋smoke_check.py 離屏驗證＋README.md），互動層座標復用 render 直排 body 同源公式（line_axis_x_pt／style_advance_pt／line_justified_advance／lead_offset_pt，公式對齊 _draw_vertical_body），resolve_hit 承 Sprint 18 provenance 點字格反查文件游標。editor/ 不入 pytest 基線（守 Sprint 17：GUI 套件不綁核心，避免基線硬依賴 PySide6），驗證走獨立 smoke_check.py；demo 文件用 samples/case-divider（自擬 C 個案扉頁，非參考書紅線）。[實作]（離屏 smoke_check 驗）＝雙層畫布顯示＋點字格反查游標（hit-test 48/48、48 cjk 字格 span 切片＝cell.text）。[Shell]／待 Owner（GAPS #19，離屏測不了）＝真視窗視覺對位＋IME 直排輸入鍵盤實測；直排畫布內嵌 IME 編輯（打字→插入→reflow）為 Phase 2 編輯引擎後續工程，本骨架僅示範「IME 組字 → 已知游標目標」不變更文件 | Spike 10 報告（A 級：PySide6 6.11 雙層畫布回路 37ms、hit 214/214）＋本 Sprint 離屏 smoke_check（samples/case-divider 雙層建構、hit-test 48/48、provenance 一致，A 級）＋app 離屏建構模擬點選／IME 回呼＋核心基線 218 綠不受 editor 影響＋honest-planning R3（[Shell] 標記）／R5（IME 待人類實測不代行） |
| 2026-07-12（Sprint 41，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | Phase 2 編輯引擎 reflow 回路核心定案：新增 `cjkfolio/editing.py` 置**核心套件**（非 editor/）並**入 pytest 基線**（純文件＋版面邏輯、GUI 無關，比 Sprint 40 離屏 smoke 嚴）；DocCursor.caret＝段 text（normalize 前原字串）半開座標，與 Cell.span（Sprint 18）同一座標系閉環；insert_text run 邊界插字**左偏**併入左側 run 承接其字元樣式（輸入法「新字繼承游標前樣式」慣例）；locate_cell 為 resolve_hit 的逆（Cell.span 反查，段內 span 兩兩不相交遞增故命中唯一）；reflow 走 layout_document **全文重排**（非增量近似，Spike 3 認可 7.67ms/章）；app.py 以「輸入區組字＋Enter 提交」代替直排畫布內嵌 IME（即點即打為後續 UI 工程），提交回路 apply_insert→_rebuild 重繪→游標跟隨；v1 只做插入（刪除／範圍編輯後續）。順帶移除 app.py 死 import QTransform（Owner 授權程式碼噪音清理，只清死碼不動稽核軌） | Spike 10（A 級：回路 37ms、hit 214/214）＋Sprint 18 provenance（span round-trip 0 錯）為既有 A 級地基；本 Sprint 基線 218→231（+13）0 退步、typecheck 0、離屏 smoke C5 編輯回路 reflow 游標跟隨；R2 判定無新技術復用既有能力無需新 spike（先例 Sprint 16/38），R6 pre-mortem 三風險（選取錯位／run 樣式／座標位移）皆有對應測試釘死 |
| 2026-07-12（Sprint 42，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | 段內刪除與範圍替換定案（續 Sprint 41 插入回路）：cjkfolio/editing.py 加 DocRange（段索引＋段 text 半開區間 [start, end)，與 DocCursor caret 同座標系）＋delete_range（段內多 run 逐 run 切除交集、保留兩端 run 及字元樣式、整個 run 落範圍內連樣式消失、全段刪空回合法空段（text 為空，正規化為單一空 run）守 document@2 不變式；start==end no-op、越界／start>end 快速失敗）＋replace_range（delete_range 後於 start 插入、新字承接左側 run 樣式復用 insert_text 慣例、text 空退化純刪除）＋apply_delete／apply_replace（對稱 apply_insert 完整回路，全段刪空 address=None）；replace_range 全刪後再插無需改 insert_text（Paragraph 空段正規化為單一空 run，既有 for 迴圈於該空 run 邊界插入，test_replace_whole_paragraph_then_insert 驗證）。跨段合併／分裂（改 para_idx 語意需新機制）與刪除／選取畫布 UI 接線（app.py 未接線、路線 2 真視窗工程）判為後續，入 GAPS #24 | 既有 A 級地基（Sprint 18 provenance／Sprint 41 insert_text 對稱設計）；本 Sprint 基線 231→250（+19：delete 11／replace 4／apply 4）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（locate_cell 反查已備）無需新 spike（先例 Sprint 16/38），R6 pre-mortem 三風險（多 run 切割錯位／樣式承接／空段邊界）皆有對應測試釘死 |
| 2026-07-12（Sprint 43，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | 跨段合併與分裂定案（續 Sprint 42 段內編輯，補齊改變段落數量的編輯，關 GAPS #24「需新機制」子項）：cjkfolio/editing.py 加 split_paragraph（Enter 段中分段：於 cursor 切 head／tail 兩段同承段落樣式、page_no 留 head 保原段身分／tail None、跨 run 一分為二兩側各保字元樣式、空側正規化單一空 run）＋merge_paragraph（Backspace 段首併前段：採前段樣式與 page_no（前段存活，InDesign 慣例）、runs 前段＋本段串接濾空 run、全空正規化單一空 run；para_idx 0 無前段可併 raise IndexError）＋apply_split／apply_merge（對稱 apply_insert 完整回路：split 新游標＝tail 起點 (idx+1,0)、merge 新游標＝合併縫 (idx−1,前段原長)；para_idx 重編由 layout_document 依 enumerate 位置自動指派，cursor 指向新位置故 locate_cell 反查正確）。GAPS #24 三前提逐一落地：跨段樣式承接（採前段）、para_idx 重編（layout 自動）、游標跨段映射（cursor 指新位置）；刪除／選取／Enter／Backspace 畫布 UI 接線（app.py 未接線、路線 2 真視窗工程）判為後續，續留 GAPS #24 | 既有 A 級地基（Sprint 18 provenance／41 insert_text／42 delete_range 對稱設計）＋layout_document para_idx＝enumerate 位置（實查 layout.py:220）；本 Sprint 基線 250→273（+23：split 10／merge 9／apply 4）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（全文重排＋locate_cell 反查已備）無需新 spike（先例 Sprint 16/38/41/42），R6 pre-mortem 三風險（para_idx 重編 off-by-one／run 切割樣式承接／游標跨段落點）皆有對應測試釘死 |
| 2026-07-12（Sprint 44，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | undo／redo 堆疊定案（承 Sprint 41〜43 編輯核心，補齊 Phase 2「復原重做」）：cjkfolio/editing.py 加 EditSession 可變控制器＝現態 (document, cursor, layout)＋undo／redo 兩 (document, cursor) 快照堆疊，採標準「回上一提交態」模型（非逐操作反函數）：編輯把編輯前態推 undo、清 redo；undo 把現態推 redo、彈回上一態並 layout_document 全文重排（Spike 3 認可 7.67ms/章，非增量），redo 對稱。insert／delete／replace／split／merge 委派既有 apply_*（不重寫編輯邏輯）統一經 _commit；undo／redo 還原後 locate_cell 反查游標畫布落點、回 EditResult，空堆疊回 None（no-op）。初始游標段 0 caret 0，v1 undo 還原上一提交態游標、不追 UI 中途點選；undo 粒度每次 apply 一步（未合併連續輸入為單一 undo 單元）＝v1 已知限制入 GAPS #25。app.py 尚未接線 undo／redo（Ctrl+Z／Y 真視窗工程）續留 GAPS #24／#25 | 既有 A 級地基（Sprint 41〜43 apply_* 對稱設計＋確定性 layout_document）；本 Sprint 基線 273→284（+11）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（apply_* 與 locate_cell 已備）無需新 spike（先例 Sprint 16/38/41/42/43），R6 pre-mortem 三風險（redo 未清致分叉／還原後版面不同步／空堆疊）皆有對應測試釘死 |
| 2026-07-12（Sprint 45，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | 字元樣式套用到選取範圍定案（承 Sprint 41〜44 編輯核心，補齊 §4.1 字元樣式的選取套用）：cjkfolio/editing.py 加 apply_char_style（純文件層：對段內 DocRange [start, end) 逐字元改掛 char_style（None＝清除回段落樣式預設）、範圍外保留原字元樣式、切割後連續同字元樣式併為單一 run（避免碎片，text 與視覺不變，同 InDesign 慣例）；空範圍 no-op、不可變、para_idx／start／end 越界快速失敗；字元樣式名有效性**不在純文件層驗**，同 insert_text／delete_range 慣例由 layout_document 守門）＋apply_style（對稱 apply_insert 完整回路：apply_char_style→layout_document 全文重排→locate_cell 反查，新 caret＝drange.end 停選取尾；套用不改 text 故 Cell.span 座標系不動、字格 char_style 隨 run 模型流入渲染層；未知字元樣式 layout_document raise KeyError）＋EditSession.apply_style（委派統一經 _commit 入 undo／redo，同 insert／delete／replace／split／merge）。DocRange 限段內（跨段選取套樣式需跨段範圍機制）與 app.py 樣式面板 UI 接線（真視窗工程）判為後續，入 GAPS #26 | 既有 A 級地基（Sprint 18 provenance／41 insert_text／42 delete_range 逐 run 切割對稱設計＋Sprint 9 Cell.char_style 渲染層覆寫已驗）；本 Sprint 基線 284→304（+20：apply_char_style 12／apply_style 4／session 3／R5 1）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（逐 run 切割＋locate_cell 反查＋EditSession _commit 已備）無需新 spike（先例 Sprint 16/38/41/42/43/44），Gate 4 pytest 狀態機斷言＋獨立 probe 印出觀察兩路互證（端到端 layout cell.char_style 流入渲染層） |
| 2026-07-12（Sprint 46，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | 段落樣式變更定案（承 Sprint 41〜45 編輯核心，補齊 §4.1 段落樣式的游標所在段套用）：cjkfolio/editing.py 加 change_paragraph_style（純文件層：把段 para_idx 的 Paragraph.style 換名、runs（含字元樣式）與 page_no 不變、樣式相同 no-op 回原物件、不可變；para_idx 越界 IndexError、style 空字串 ValueError 守 document@2「段落需非空 style」不變式；段落樣式名有效性**不在純文件層驗**，同 insert_text／apply_char_style 慣例由 layout_document 守門）＋apply_para_style（對稱 apply_insert／apply_style 完整回路：change_paragraph_style（改 cursor.para_idx 段）→layout_document 全文重排→locate_cell 反查；段落樣式變更不改 text 故游標 para_idx／caret 保持不變、reflow 後畫布落點隨版面更新、文件座標不動；未知段落樣式名 layout_document raise KeyError 同 apply_style 字元樣式守門）＋EditSession.apply_para_style（委派統一經 _commit 入 undo／redo，同 insert／delete／replace／split／merge／apply_style）。誠實記錄幾何 nuance：測試「內文→引文」兩樣式版面幾何參數相同（advance 12.08／cap 32／indent 2，差異僅字型明體 vs 仿宋於渲染層選字），故證「段落樣式參照流入 layout（placed line.style 換名）＋reflow 乾淨」非斷行幾何改變（改「內文→題詞」indent 0 vs 2 則首行起點位移）；app.py 段落樣式面板 UI 接線（真視窗工程）判為後續入 GAPS #27 | 既有 A 級地基（Sprint 18 provenance／41 insert_text／45 apply_char_style／apply_style 對稱設計＋Sprint 9 段落樣式驅動網格已驗）；本 Sprint 基線 304→319（+15：change 8／apply 3／session 3／R5 1）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（layout_document 全文重排＋locate_cell 反查＋EditSession _commit 已備）無需新 spike（先例 Sprint 16/38/41/42/43/44/45），Gate 4 pytest 狀態機斷言＋獨立 probe 印出觀察兩路互證（placed line.style 流入 layout） |
| 2026-07-12（Sprint 47，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | 連續輸入合併為單一 undo 單元定案（承 Sprint 41〜46 編輯核心，補齊 Phase 2「復原重做」的輸入序列合併，關 GAPS #25「連續輸入合併」子項）：cjkfolio/editing.py EditSession `insert` 對前進打字（游標接續前一輸入 run 尾 caret＋兩次輸入間隔 now−ts ≤ coalesce_window 秒）併入同一 undo 單元（更新現態但不新增 undo 快照、不動 redo），對標 InDesign／多數編輯器逐字輸入不各成一 undo 步；輸入序列邊界＝游標不連續、逾時間窗、或任何非插入操作（delete／replace／split／merge／apply_style／apply_para_style／undo／redo）介入（皆令 _pending_insert 歸零、其後起新單元），以 _can_coalesce 判定、_commit／_restore 統一重置序列；EditSession 加 keyword-only 參數 coalesce_window（預設 2.0s）與 clock（預設 time.monotonic，測試注入可控假時鐘離屏確定性驗時間邊界），既有 EditSession(doc, template) 建構相容不變；app.py undo／redo UI 接線（Ctrl+Z／Y 真視窗工程）判為後續，仍留 GAPS #25／#19 | 既有 A 級地基（Sprint 44 EditSession _commit／_restore 提交態模型＋Sprint 18 provenance／41 insert_text 對稱設計）；本 Sprint 基線 319→326（+7：連續合併／redo 整串／游標不連續起新／逾時起新／恰達窗合併／刪除打斷／undo 重置）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（EditSession 提交態堆疊＋游標座標系已備，僅加序列邊界判定）無需新 spike（先例 Sprint 16/38/41/42/43/44/45/46），Gate 4 pytest 狀態機斷言（can_undo／text）＋獨立 probe 直接檢視 _undo 堆疊深度兩路互證 |
| 2026-07-12（Sprint 48，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | 跨段選取範圍與跨段刪除／替換定案（承 Sprint 41〜47 編輯核心，補齊改變段落邊界的範圍編輯，為 GAPS #26 跨段字元樣式所需的跨段範圍機制地基）：cjkfolio/editing.py 加 DocSpan（起訖兩 DocCursor 界定跨段選取，start ≤ end 段索引優先再比 caret；DocRange 段內範圍之一般化，同段 start.para_idx==end.para_idx 退化為段內範圍、start==end 空範圍）＋delete_span（同段委派 delete_range；跨段頭段保 start 前、尾段保 end 後併為一段承頭段樣式與 page_no〔頭段存活，同 merge_paragraph 慣例〕、中間整段移除、兩端 run 各保字元樣式、全刪空正規化單一空 run〔守 document@2〕；空範圍 no-op、para_idx 越界 IndexError／caret 越界或起點晚於終點 ValueError）＋replace_span（delete_span 後於縫〔start.para_idx, start.caret〕插入承左側 run 樣式、text 空退化純刪除）＋apply_delete_span／apply_replace_span（對稱 apply_delete／apply_replace 回路：跨段編輯→layout_document 全文重排→locate_cell 反查，delete 新 caret＝縫／replace 新 caret＝縫＋len(text)、全刪空段 address=None）＋EditSession.delete_span／replace_span（委派 _commit 入 undo／redo、非插入操作打斷連續輸入序列）；內部 _slice_runs（邊界 run 切割保字元樣式濾空段）／_validate_span。循 tests/ 分檔慣例（test_edit_style／test_edit_para_style 先例）獨立新檔 tests/test_edit_span.py（自帶 fixture／helper／_FakeClock 不建共享 conftest），test_edit_engine.py 維持 794 行不撐破 800 上限。跨段字元樣式套用（apply_char_style over DocSpan，GAPS #26 跨段子項）與選取拖曳／刪除 UI 接線（app.py 未接線，路線 2 真視窗工程）判為後續，入 GAPS #28 | 既有 A 級地基（Sprint 18 provenance／41 insert_text／42 delete_range 逐 run 切割／43 merge 頭段存活對稱設計）；本 Sprint 基線 326→346（+20：delete_span 11／replace_span 3／apply 4／session 2）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（delete_range／insert_text／merge 頭段存活／locate_cell 反查／EditSession _commit 已備）無需新 spike（先例 Sprint 16/38/41/42/43/44/45/46/47），Gate 4 pytest 狀態機斷言＋獨立 probe（直接印出＋檢視 session._undo 深度）兩路互證跨段刪除段數收斂／頭段樣式承接／兩端 run 樣式／同段退化等價／reflow 空／undo-redo 堆疊／越界守門 |
| 2026-07-12（Sprint 49，Owner「最複雜架構先做」下 Phase 2 編輯引擎） | 跨段字元樣式套用定案（承 Sprint 45 段內 apply_char_style 與 Sprint 48 DocSpan 跨段範圍機制，關 GAPS #26「跨段選取套字元樣式」子項）：cjkfolio/editing.py 加 apply_char_style_span（純文件層：跨段選取逐段套或清字元樣式，段界不併〔字元樣式不改段落數量，別於 delete_span 併段〕；頭段 [start, len)／中間段整段／尾段 [0, end) 各委派段內 apply_char_style〔逐 run 切割＋相鄰同樣式併合〕、同段 start.para_idx==end.para_idx 退化段內 apply_char_style、空範圍 no-op、復用 _validate_span 越界／逆序守門）＋apply_style_span（對稱 apply_style 回路：apply_char_style_span→layout_document 全文重排→locate_cell 反查，新 caret＝span.end 停選取尾、套用不改 text 故 Cell.span 座標系不動、字格 char_style 隨 run 流入渲染層、未知字元樣式名 layout_document raise KeyError）＋EditSession.apply_style_span（委派 _commit 入 undo／redo）。實作採「逐段委派既有段內 apply_char_style」而非重寫 run 切割（外科手術：不動 Sprint 45 已驗邏輯；套字元樣式不改 text 故段長不變、逐段 DocRange 以原段長構造安全）。循 tests/ 分檔慣例獨立新檔 tests/test_edit_style_span.py。至此 Phase 2 核心編輯 API（插入／刪除／替換／分裂／合併／undo-redo／字元樣式／段落樣式，段內與跨段）完備 | 既有 A 級地基（Sprint 45 apply_char_style 逐 run 切割＋併合／Sprint 48 DocSpan＋_validate_span 對稱設計）；本 Sprint 基線 346→359（+13：apply_char_style_span 10／apply_style_span 2／session 1）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R2 判定復用既有能力（段內 apply_char_style／DocSpan／locate_cell／EditSession _commit 已備）無需新 spike（先例 Sprint 16/38/41-48），Gate 4 pytest 狀態機斷言＋獨立 probe（直接印出＋檢視 session._undo 深度）兩路互證段界不併／中間段整段／同段退化等價／None 跨段清除／相鄰同樣式併合／reflow 空＋端到端字格樣式／undo-redo／逆序＋未知樣式守門 |
| 2026-07-12（Sprint 50，Owner「最複雜架構先做」下編輯引擎完備後轉 Phase 2 圖片置入） | 圖片置入 v1 定案：灰階照片（§9 單 K）置入主版 figure 保留區、contain 等比縮放置中（primitives.fit_image_rect）；文件模型 document@2 相容擴充 PlacedImage（path＋版面頁號，序列化選配、同 page_no 慣例）；影像領域單一事實來源 cjkfolio/images.py（open_grayscale 轉灰階＋resolve_placed_images 兩後端共用解析去重＋EmbeddedImage DeviceGray XObject）；兩後端同源（render PNG paste／pdf_writer cm＋Do XObject，figure_slot_rect＋fit_image_rect），置入取代 photo-slot 佔位框、同路徑跨頁去重單一 XObject。v1 只 figure 保留區每頁一張、只灰階 DeviceGray、PPI 未強制重採樣（GAPS #29）；任意置入與畫布拖放 UI 屬真視窗工程（#19）。pdf_writer 逾 800 行故 EmbeddedImage 移 images.py（影像領域，emit duck-type pdf.stream 無循環 import）；preflight NOT_COVERED 同類更新（Gate 3：「尚無影像置入」→「PPI 未重採樣、色彩空間 color-cmyk-only 涵蓋」） | Sprint 27 G-圖文版 photo-slot 一手量測地基＋§9 灰階單 K 硬條件；本 Sprint 359→393（+34）0 退步、typecheck 0、editor smoke 0 退步；R5 自擬灰階圖兩後端渲染（PNG＋PyMuPDF 獨立）目視一致、方向未翻轉、preflight 12/12；R2 復用既有能力無需新 spike（先例 Sprint 16/38/41-49） |
| 2026-07-17（Sprint 51，Owner「最複雜架構先做」下 Phase 2 主版指派） | 節式主版指派定案：`Paragraph.master` 節首標記（@2 相容擴充選配）＝自本段起新頁並改用該主版（主版屬頁級幾何不可頁中切換；同名主版亦強制分頁＝顯式分頁原語）；`doc.master` 降為首節預設（無標記文件＝單節，行為與現況完全一致向後相容）；採內容錨定（節首跟段落走，編輯重排不失步）而非 InDesign 頁鍵式（「選頁套主版」在流排模型下內容位移即失步，屬編輯 UI 語意層，v1 不採）。layout 節式流排：每節獨立 flow_pages（節首＝強制起新頁故節間無跨頁流，flow_pages 本體不動）、樣式行容量逐節網格換算、頁號跨節連續、節間 gap 歸零（承「段後空槽跨頁歸零」慣例）、first_para_continues 僅首節；LayoutPage.master 載體，toc／rule／齊行統計逐頁主版。兩後端 render_page／build_page 依 page.master 解析主版，頁腳／frame／rule／figure 逐頁 gate；resolve_placed_images 改 {版面頁號: MasterPage}（逐頁 figure 驗證）。editing 七類操作保留 master：split head 承（節首身分同 page_no 慣例）tail None、merge 前段存活（節首標記隨併入消失＝節合併語意）。順帶勘正 LayoutPage 註解「奇數＝右頁」（Sprint 22 前殘留，正確為偶數書頁＝右頁） | Sprint 20 B 主版一手量測（行軸 228.49／194.12 進 parity 測試）＋Sprint 22 側別（書頁 2 偶＝右頁腳位）；本 Sprint 基線 393→413（+20，tests/test_master_assign.py：document 3／layout 8／editing 4／兩後端 5）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R5 自擬章首樣張（samples/chapter-opening.doc.json）兩頁 PNG 親 Read＋PDF preflight 12/12＋PyMuPDF 字墨逐頁對 B／A 行軸；R2 判定復用既有能力（flow_pages 與幾何函式不動）無需新 spike（先例 Sprint 16/38/41-50），R6 pre-mortem 四風險（逐頁主版狀態污染／編輯丟欄位／images 簽名漏呼叫端／單主版回歸）皆有對應測試釘死 |
| 2026-07-17（Sprint 52，Owner「最複雜架構先做」下全書組裝管線） | 書冊組裝定案（cjkfolio/book@1）：組裝輸出＝**普通 document@2 文件**（組裝層零新排版機制：章首段掛節首標記＝Sprint 51 節式主版指派，後續 render／export／editing 完全走既有管線，無「書冊」執行期概念）；書冊清單 schema＝meta.title（PDF Title 用書冊題名，蓋過章文件題名）／meta.template（各章 meta.template 必須一致，不一致快速失敗）／chapters 章序即節序／選配書冊層級 images；主版解析優先序＝chapters[].master 顯式覆寫 ＞ 章首段既有節首標記 ＞ 章文件 meta.master（章內既有節照搬）；章層級 images 快速失敗（其 page 為章內排版頁號、組裝後即失效，書冊層級 images 的 page＝全書版面頁號）；空章快速失敗；CLI `assemble`（章路徑相對書冊清單目錄，輸出可直接 render／export／編輯）。順帶：samples/figure-page.doc.json 補缺漏的 meta.template（Sprint 27 起缺，組裝器一致性檢查抓到＝快速失敗設計自證） | 復用 Sprint 51 節式主版指派（R2 判定零新排版機制無需 spike，先例 Sprint 16/38/41-51）；本 Sprint 基線 413→428（+15，tests/test_book.py）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R5 自擬全書樣張（samples/book.json 五章：E＋D＋B/A＋C＋G）assemble 21 段 6 節首標記 → 6 頁 render 禁則 0 違規＋export preflight 12/12，親 Read 三跨主版代表頁與單頁樣張特徵逐項一致；R6 pre-mortem 三風險（章首標記覆寫語意錯亂／章級 images 頁號失效／template 混用）皆快速失敗＋測試釘死 |
| 2026-07-17（Sprint 53，Owner「最複雜架構先做」下節式混向文件） | 書寫方向降到節層級定案（關 GAPS #30 (b)／#31 (b)）：方向本質屬「節」而非「文件」（Sprint 51 後每節獨立 flow，方向參數本就逐 flow_pages 呼叫傳遞，「全文件單向」限制係單一 flow 時代遺留）；同一節混向仍快速失敗（版面軸不同、slot 幾何不相容，訊息引導以節首標記分節）；`LayoutPage.vertical` 逐頁載體、`LayoutResult.vertical` 改義首節方向（相容欄位）、`page_is_vertical` 保留為全文件單向 util（混向文件不再經它）；齊行統計與 rule 斷線逐頁 gate；兩後端逐頁傳方向（frame「橫排原件」與 rule「直排原件」既有 gate 條件自動逐頁成立）；canvas 橫排頁僅底圖（互動層為直排 body 幾何，橫排互動層併真視窗批次）。F 版權頁自此入冊：全書單一 PDF/X（原「F 另出一份」限制解除） | 零新排版機制（R2 無需 spike，先例 Sprint 16/38/41-52）；本 Sprint 基線 428→436（+8，tests/test_direction_sections.py）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R5 自擬全書樣張加 F 章＝6 章 28 段 7 節首標記 → 7 頁單一 PDF preflight 12/12、親 Read 頁 7 橫排 CIP＋細框＋無頁腳；混向幾何測試（直排欄 cx 一致 y 遞增／橫排行基線一致 x 遞增／re 細框只在 F 頁）＋齊行統計對照（橫排節不入統計）釘死；R6 pre-mortem 三風險（後端漏改致橫排頁用直排軸／同節混向 fast-fail 回歸／齊行統計誤計）皆有對應測試 |
| 2026-07-17（Sprint 54，Owner「最複雜架構先做」下多圖／任意矩形置入模型） | 影像模型一般化定案（GAPS #29 (a)）：`PlacedImage.rect` 任意圖框（trim 空間 pt、top-down，與 figure_slot_rect 同座標系）；**溢出版心不快速失敗**（真書照片略溢 1〜4pt〔GAPS #13 一手記錄〕與出血照片皆正當用法；PNG 於 trim 畫布自然裁切、PDF 置入出血區）；rect 圖每頁多張（文件序＝繪製序＝疊放 z 序確定性）、槽式維持每頁一張守門；rect 圖不需 figure 槽（座標自帶，A 內文頁可置圖）、槽式仍需；佔位虛線框語意改「槽仍空即畫」（rect 圖不填槽＝InDesign 空框導引，G 頁放 rect 圖佔位框仍標示槽區）；resolve_placed_images 改列表模型（兩後端同源）；XObject 同路徑去重跨 rect 條目不變。PdfResult.images_placed＝去重後 XObject 數、RenderResult.images_placed＝置入張數（原有語意差明文化） | 復用 fit_image_rect／paste／XObject（R2 零新技術無需 spike，先例 Sprint 16/38/41-53）；本 Sprint 基線 436→446（+10，tests/test_image_rects.py）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R5 自擬 G 頁雙照片示範（真書雙照片形態）親 Read＋preflight 12/12；Gate 4 PyMuPDF get_image_rects 驗 bbox＝rect＋出血（fitz top-down 同向）＋單一 XObject 去重＋溢出框右緣跨入出血＋PNG 像素兩框中心值；R6 pre-mortem 三風險（座標空間混淆／槽式守門誤鬆／去重回歸）皆有對應測試 |
| 2026-07-17（Sprint 55，Owner「最複雜架構先做」下獨立文字框 v1） | 文字框「建立」半邊定案（§6 Phase 2「文字框建立／串接」拆半：threading 屬串接半邊後續專項）：TextFrame＝任意矩形直排文字（rect 同 PlacedImage 座標系、可溢出版心＝自由佈局層正當用法）；幾何單一來源 frames.py（兩後端同源紀律）＝欄容量 floor(框高/字距)、欄距級數×(網格行距/基準級數)（§10 換算同構、grid 取框落點頁主版網格＝節式主版指派一致）、欄自框右緣右至左、框內不齊行（等距，圖說短文形態）；斷行禁則復用 engine（擠入追出同 body，字墨 bearing 可略超框緣＝字型度量差誠實記錄）；溢出框寬欄不繪並列違規（不沉默，InDesign 溢排紅點同義）；橫排框快速失敗（latin 自然寬需 shaper 度量，frames 純邏輯層不可知，v2）；框頁須落於流排頁（不為框造頁，同 images）；章級 text_frames 組裝拒絕（頁號章內語意）。行數上限管理：pdf_writer 的 XMP 助手抽出 pdfx_meta.py（純搬移行為不變） | 復用 engine break_paragraph 與兩後端 cell 繪製助手（R2 零新技術無需 spike，先例 Sprint 16/38/41-54）；本 Sprint 基線 446→457（+11，tests/test_text_frames.py）0 退步、typecheck 0、editor 離屏 smoke 0 退步（canvas 底圖繪框後複驗）；R5 自擬「雙照片＋雙圖說貼照片側」示範（真書 G 頁形態）親 Read＋preflight 12/12；Gate 4 PyMuPDF rawdict 框字墨 cx＝frames 行軸（abs≤1.2pt）＋框緣 bearing 容忍 3pt＋PNG 框內墨跡框外紙白；R6 pre-mortem 三風險（框幾何與 body 幾何混淆／橫排框度量不可知／溢字沉默）皆有對應測試或快速失敗 |
| 2026-07-17（Sprint 56，AI 設定檔層） | AI 設定資料面定案（§4.4）：AiConfig 三欄位預設全空；缺檔＝空預設不擋流程（AI 為選配增強，核心排版不依賴）；壞檔明確錯誤且錯誤訊息只含欄位名與型別、不回帶欄位值（金鑰不入 log 紅線）；未知鍵容忍（向前相容）；save 只序列化三欄位；慣例路徑 local/ai-config.local.json（local/ 已入 .gitignore，GAPS #6）。面板 UI（真視窗三欄位）為其表現層，待真視窗批次 | 本 Sprint 基線 457→463（+6，tests/test_ai_config.py）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R5 以使用者既有本機設定檔實載（三欄位皆成功、值零輸出）；金鑰紅線測試釘死（錯誤訊息不含祕密值） |
| 2026-07-17（Sprint 57，文字框串接） | 文字框「串接」半邊定案（關 GAPS #32 (a)，§6 Phase 2「文字框建立／串接」兩半邊補齊）：`TextFrame.thread` 選配串接鏈名（@2 相容擴充）＝同 thread 框依文件序成鏈、文字掛鏈首；解析層守門＝續框帶 text 雙源快速失敗、續框 style 須與鏈首一致、thread 空字串拒絕；序列化續框不寫空 text。佈局＝鏈文字一次 tokenize 成 cells，逐框以該框頁主版網格換算容量斷行（engine 新公開 `break_cells`＝cells 級斷行入口、break_paragraph 委派）、取前欄數容量欄、以已消費 cell 數切出剩餘續排下一框：_break_cells 行序列 cells 連續無增刪且每行行首行尾禁則已解消，故任一行邊界皆合法切點＝框邊界禁則自然正確（無需跨框回饋機制）；中間框排滿即續流、鏈尾仍剩列違規掛鏈尾（不沉默）；跨頁串接逐框取該頁網格（節式主版指派一致）。resolve_text_frames 鏈框統一佈局後放回各自頁、頁內繪製序＝文件序（Sprint 54 rect 圖慣例）；兩後端與 canvas 零變更（FramePlacement 介面不動）。v1 限制：鏈序＝文件序（無顯式序欄位）、無框內強制斷點原語、拉線串框／框編輯 UI 屬真視窗批次 | 復用 engine 斷行＋Sprint 55 frames 管線（R2 零新技術無需 spike，先例 Sprint 16/38/41-56）；本 Sprint 基線 463→475（+12，test_text_frames.py：schema 2／佈局 6／resolve 2／兩後端 2）0 退步、typecheck 0、editor 離屏 smoke 0 退步；R5 自擬「雙照片＋一段圖說流過上下兩框」示範（out/thread-demo）親 Read＋preflight 12/12；Gate 4 PyMuPDF 獨立驗串接守恆（框 A「改造前雜物滿地，」8 字＋框 B「改造後留白生光」7 字＝原文 15 字無重複無遺漏）＋兩框字墨 cx＝各框行軸（356.1＝右緣−半欄距）；R6 pre-mortem 三風險（框邊界禁則錯位／width>1 cell 計數錯位／跨頁 grid 混用）皆有對應測試釘死 |
| 2026-07-17（Sprint 58，框 provenance＋畫布框字格反查） | 框 provenance 定案（GAPS #32 (d) 前半＝資料鏈與畫布反查；框內編輯操作待框編輯專項）：frames 佈局帶 offsets（normalize_with_offsets＋tokenize(offsets=)，對齊 body 慣例 Sprint 18）＝框 cells span＝來源 text（normalize 前）座標；FramePlacement 加 frame_idx（自身框文件索引）與 source_idx（文字來源框＝串接鏈首；獨立框＝自身）＝span 座標的錨，由 resolve_text_frames 填（layout 層不知文件索引，單一職責）、兩後端不讀（零影響）。畫布：page_frame_placements 單一事實來源（canvas 內部與 app／smoke 反查共用）＋iter_frame_cell_rects 幾何與 render._draw_text_frame 逐項同源＋FrameCellHit／resolve_frame_hit；框 item data＝("frame", fi, li, ci) 四元組、body 字格 (pi, ci) 鍵形不變（向後相容）；app 點框字格顯示框游標、不設 body 插入游標（IME 不入框，框編輯待專項） | 既有 A 級地基（Sprint 18 span 座標系／Sprint 40 雙層畫布／Sprint 55〜57 frames 管線）；本 Sprint 基線 475→478（+3）0 退步、typecheck（含 editor）0；離屏 smoke C6 框字格 hit-test 28/28＋round-trip 28 格（續框 span 錨鏈首 (18, 19)）＋app 分流；R5 以 Sprint 57 真實示範 thread-demo 逐格 round-trip 15 格全對（續框 (8, 9)）；R2 判定復用既有能力（span 機制＋畫布雙層皆既有）無需新 spike（先例 Sprint 16/38/41-57） |

## 11. 證據附錄（關鍵引用）

- Scribus 直排票 21 年未動工：bugs.scribus.net/view.php?id=1778；CJK metabug：github.com/HOST-Oman/scribus/issues/76
- Affinity 官方無直排計畫：forum.affinity.serif.com（vertical text for CJK）
- Vivliostyle 直排與 RTL 頁序已解、支援清單、CMYK 後處理：github.com/vivliostyle/vivliostyle.js/issues/431；docs.vivliostyle.org/en/reference/supported-css-features；github.com/vivliostyle/vivliostyle-cli/blob/main/CHANGELOG.md；vivliostyle.org/faq
- Typst 直排僅 RFC、無 PDF/X：github.com/typst/typst/issues/5908；typst.app/docs/reference/pdf
- SILE 直排半成品 issue：github.com/sile-typesetter/sile/issues/1226、/918；kinsoku 源碼：languages/ja/init.lua
- LuaLaTeX-ja 直排 experimental、jlreq、pdfx：ctan luatexja-en.pdf；github.com/abenori/jlreq；pdfx.pdf
- 技術棧：QGraphicsView（qt.io/blog/2017/01/19）、Qt LGPL（qt.io/development/open-source-lgpl-obligations）、Skia（skia.org）、HarfBuzz 直排邊界（koharu.rs、harfbuzz.github.io）、W3C JLREQ（w3.org/TR/jlreq）、W3C CLREQ 中文排版需求（w3.org/TR/clreq，繁中句逗置中規則的規範來源）
- 字型授權：華康（dynacw.com.tw/business/licensing_usage）、SIL OFL（openfontlicense.org）、思源（github.com/adobe-fonts/source-han-serif）、jf open 粉圓（github.com/justfont/open-huninn-font）、辰宇落雁體（github.com/Chenyu-otf/chenyuluoyan_thin）、全字庫 TW-Kai（國發會）
- PDF/X 與印前：pdfa.org/technical-side-and-requirements-of-pdfx；prepressure.com/pdf/basics/fonts

---

**驗證報告**
- 驗證方法：以 PyMuPDF 親自量測參考 PDF（頁面尺寸、字型、級數、版心、色彩空間、影像），渲染代表頁以視覺確認；以多代理人並行 WebSearch/WebFetch 查證 4 個排版核心、Scribus 競品、架構決策、技術棧、字型授權，全部附真實 URL。
- 發現的問題：使用者原始假設（自建引擎達逐像素一致）不可行，已於第 0、3 節誠實校正；Vivliostyle AGPL 授權與 CMYK 後處理、自製直排引擎的禁則／約物擠壓、CMYK 色彩可控性為三大高風險，已列入 Phase-0 spike 與 Pre-mortem。
- 信心說明：引擎能力評分與字型授權結論皆有官方文件／原始碼一手佐證；直排出版級品質在開源鏈上「未有逐項公開實證」，已誠實標示為 Phase-0 必驗，未驗證前不寫進對外承諾。

**2026-07-10 執行層補強記錄**
- 補強內容：Phase 0 執行細則（spike 語言定為 Python、依賴與安裝成本表、素材與字型前置、順序與時間盒、驗收檢核清單、產出物結構）；修正 §5.2 技術棧與 §3.1 閘門的先後矛盾；Spike 1 移除 ICU 硬依賴；Spike 3 明確依賴關係；GAPS 新增參考書內容版權紅線。
- 未改動：戰略層（市場定位、架構決策、核心選型、風險、授權分析）維持 2026-06-16 版結論。

**2026-07-10 功能擴充記錄（內容匯入＋AI 輔助）**
- 新增 §4.4：txt／md／docx 匯入、AI 輔助樣式指派（AI 只管結構識別，幾何計算歸引擎）、LLM 介接與金鑰紅線。
- 里程碑對應：Phase 1 加 txt／md 匯入；Phase 2 加 AI 設定面板；Phase 3 加 docx 與 AI 指派整合；Phase 0 加 Spike 5。
- 一手證據：endpoint 實測可達（/v1/models，256K context）；Spike 5 第一輪 PoC 對 8 段自擬書稿段落六類分類 8/8 全對（temperature 0.2、共 398 tokens），腳本與輸出在 spikes/spike5-ai-style-tagging/。
- 誠實標示：PoC 素材為自擬短段落，真實整章書稿的正確率與批次耗時未驗，列 Spike 5 剩餘工作；私有 endpoint 僅 Tailscale 內網可達，不作為產品預設。
