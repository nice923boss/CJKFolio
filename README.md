# CJKFolio

免月費也能做出版級中文直排書冊的開源排版編輯器。

以一本出版社實印的 A5 直排書為品質標竿逐項逆向量測，把出版級直排真正難的那一層（禁則處理、約物擠壓、縱中橫、版心對齊、齊行微調）寫成引擎，並自寫 PDF/X 輸出層，不依賴任何商用排版軟體。

授權：**AGPL-3.0-or-later**（成因見下方「授權」）。

## 為什麼有這個專案

「免費、所見即所得、出版級 CJK 直排」三者的交集，目前沒有任何一個產品同時滿足：

| 工具 | 免費 | 所見即所得 | 出版級 CJK 直排 |
| --- | --- | --- | --- |
| Adobe InDesign | 否（月費制） | 是 | 是（業界標竿） |
| Affinity Publisher | 買斷 | 是 | 否（官方明說無直排計畫） |
| Scribus | 是 | 是 | 否（直排需求票 2005 年立，21 年未動工） |
| Vivliostyle | 是 | 否（要寫 CSS 或 Markdown） | 是 |

技術風險已被 Vivliostyle 證明可控（CSS Paged Media 能做出出版級 CJK 直排書），缺的是把它包進一個免費、視覺化、書冊取向編輯器的人。目標用戶：華文獨立出版、自費出版、ZINE、同人誌，以及被月費勸退又需要直排的創作者。

## 目前狀態（誠實範圍）

本專案依 honest-planning 紀律標記每一項交付物：**[實作]**＝完整可用且有真實素材驗收，**[Shell]**＝介面在但實作是空殼（不算完成、不計入對外承諾），**[Spike]**＝探索性驗證。

| 能力 | 狀態 | 說明 |
| --- | --- | --- |
| 直排版面引擎（禁則、齊行、約物擠壓、縱中橫、圖文繞排） | [實作] | 自寫，不依賴現成排版元件 |
| PDF/X-1a:2001 與 X-4:2010 匯出 | [實作] | 自寫 PDF 寫出層：CMYK 單 K 文字、出血、裁切標記、套準十字與色條灰梯尺、字型子集嵌入 |
| preflight 機械檢查 | [實作] | 自寫規則（12 項），**非 Acrobat 認證級**，不等同印刷廠驗檔 |
| txt／Markdown／docx 匯入與 AI 輔助樣式指派 | [實作] | docx 自行解析 OOXML，不依賴 Word |
| 三層樣式模版、模版庫、樣式繼承、從參考 PDF 萃取樣式 | [實作] | |
| 多主版書冊組裝與自動目錄（含多層階層與章內小節） | [實作] | |
| WYSIWYG 編輯器（雙層畫布、點字格反查文件游標、範圍選取、樣式與模版面板、preflight 面板、稿件匯入、置圖與繞排 UI） | [實作] | 離屏煙霧驗證 C1 至 C24 全過 |
| 直排畫布內嵌 IME 即點即打 | **[Shell]** | 目前以輸入區組字加 Enter 提交代替，見 `editor/README.md` |
| 注音 ruby 的 group／jukugo 與橫排 ruby | 未做 | 缺帶注音的真實稿件，待真實用例（GAPS #46） |
| 印刷廠實體打樣校色 | 未做 | Phase 5 驗收項，待安排 |
| pip 安裝散布 | **[Spike]** | wheel 建得出、裝進 venv 後在 repo 外跑得動 CLI；相依解析與上架未驗，故不宣稱（見「快速開始」） |

已跑過的真實素材驗收：

| 素材 | 結果 |
| --- | --- |
| 公開章節素材 `samples/paiban-xiaoji-ch1.md`（自撰原創 2,210 漢字） | 11 頁、禁則 0 違規、PDF/X-1a 機械檢查 12/12 |
| 第二本書《街角慢行》（自撰三章，另一套零共用模版） | 13 頁、禁則 0 違規、12/12 |
| 一部 13 章 30,437 漢字的長篇書稿（本機素材，不隨 repo 散布） | 135 頁、禁則 0 違規、12/12、目錄頁碼 13/13、左右頁側別 133/133 |
| 效能基線（171 頁全書） | 排版 146ms、匯出 2.35s、preflight 359ms |

未關閉的缺口一律登記在 `GAPS.md`，不靠口頭承諾追蹤。

## 快速開始

需求：Python 3.12（只在 3.12.10 上驗證過，未在其他版本跑過測試故不宣稱相容）。

**1. 安裝相依**

```bash
python -m pip install PyMuPDF PySide6 pillow fonttools freetype-py uharfbuzz
```

**2. 取得內建字型**

字型二進位不入 repo，需依 `assets/fonts/FONTS.md` 的重現下載指令取回六款 SIL OFL 字型放進 `assets/fonts/`，否則渲染會大量缺字。

**3. 跑一次端到端**

```bash
python -m cjkfolio.cli import-md samples/paiban-xiaoji-ch1.md -o out/ch1.doc.json --title "排版小記"
python -m cjkfolio.cli render out/ch1.doc.json -o out/png
python -m cjkfolio.cli export-pdf out/ch1.doc.json -o out/ch1.pdf
python -m cjkfolio.cli preflight out/ch1.pdf
```

預期輸出：render 報「11 頁、禁則 0 違規」，export 報 5 款嵌入字型皆可合法嵌入子集，preflight 報「全數通過（12/12）」。另會出現兩則字型警告（思源宋體 TC 無 bold 檔以 heavy 替、全字庫正宋體未入 `assets/fonts` 以思源宋體 TC 替），屬 GAPS #12 已登記的內建字型缺口，不是這份素材的缺陷。

**4. 開編輯器**（需有顯示器）

```bash
python editor/app.py
```

Windows 可直接雙擊根目錄的 `啟動編輯器.bat`。無視窗環境請改跑離屏煙霧驗證 `python editor/smoke_check.py`。

本專案的支援形態是自 repo 根執行（`python -m cjkfolio.cli ...`），編輯器也只有這個形態（`editor/` 不是套件，不進 wheel）。Sprint 119 首度量過 pip 安裝形態：wheel 建得出、裝進 venv 後在 repo 外跑得完 `import-md` 與 `render`（字型是使用者資產不隨 wheel 走，需以 `--font-dir` 指目錄）。但相依解析未驗（探針以 `--no-deps` 安裝）、sdist 未建、PyPI 未上架，故仍不提供也不宣稱 pip 安裝。實測數據見 `spikes/spike21-packaging/report.md`。

其他 CLI 子命令：`import-txt`、`import-docx`、`assign-styles`、`extract-styles`、`merge-styles`、`assemble`。完整用法見 `python -m cjkfolio.cli --help`，樣張重現指令見 `samples/README.md`。

AI 輔助樣式指派需自備 LLM 端點，設定只讀 `local/ai-config.local.json`（不入 git，產品介面預設空值）。不設定不影響其他功能。

## 專案結構

| 目錄 | 內容 |
| --- | --- |
| `cjkfolio/` | 核心：文件模型、樣式、排版引擎、渲染、PDF 寫出、preflight、匯入、編輯操作 |
| `editor/` | PySide6 編輯器（雙層畫布與各面板），另見 `editor/README.md` |
| `templates/` | 樣式模版（兩套書系模版，含主版、段落與字元樣式、色票） |
| `samples/` | 自擬公開樣張與素材，可隨 repo 散布，另見 `samples/README.md` |
| `tools/` | 逆向量測腳本與紅線掃描器 |
| `spikes/` | Phase 0 可行性驗證與其報告 |
| `tests/` | pytest 測試 |
| `hooks/` | 提交前紅線掃描 git hook，另見 `hooks/README.md` |
| `devlog/` | 逐 Sprint 工作日誌與 spike 報告 |

## 驗證與開發

```bash
python -m pytest tests spikes -q
python editor/smoke_check.py
python tools/precommit_scan.py --all
```

`editor/` 的 GUI 程式不入 pytest 基線（GUI 套件不綁核心測試），驗證走獨立的離屏 `smoke_check.py`。

建議安裝提交前掃描，它擋的是 `.gitignore` 擋不住的字串層級洩漏：

```bash
git config core.hooksPath hooks
```

掃描器守的紅線：AI 金鑰與私有網路位址只存 `local/`、參考書逐字內容永不入 repo、本機素材路徑不得寫進原始碼（素材一律由呼叫端顯式指定）。細節見 `hooks/README.md`。

## 授權

- **程式碼：AGPL-3.0-or-later**（全文見 `LICENSE`）。這不是偏好，是相依鎖死的結果：PyMuPDF 為 AGPL-3.0 且被以同行程 import 使用，MIT、Apache-2.0、BSD、MPL-2.0、LGPL 全部不可選。
- 散布結合物的**實效授權為 AGPL-3.0**（PyMuPDF 未寫 or-later，PySide6 與 shiboken6 明寫 only）。
- 六項產品相依的逐字授權、義務、已知邊界見 `THIRD-PARTY-LICENSES.md`；傳遞相依已展開稽核（產品側 9 枚、併計開發側 18 枚全部相容），可用 `python tools/audit_licenses.py` 複驗。
- **字型**：內建字型皆 SIL OFL 1.1，來源與下載指令見 `assets/fonts/FONTS.md`。華康、Monotype 等商用字型不內建也不隨附，品質標竿書所用的商用字型以開源字型對映替代。
- 上述陳述的是讀到的授權事實，**不構成法律意見**，正式公開釋出前待具開源授權經驗者複核（GAPS #55）。

## 文件

| 檔案 | 內容 |
| --- | --- |
| `開源CJK排版編輯器-PLAN.md` | 規劃 SSOT：技術限制、逆向量測數據、架構決策、里程碑、決議紀錄 |
| `GAPS.md` | 落差登記簿：所有延後、降級、空殼、待決事項與其補完時點 |
| `CHANGELOG.md` | 逐版變更與每版的待驗收項 |
| `THIRD-PARTY-LICENSES.md` | 第三方授權清單與 AGPL 成因 |
