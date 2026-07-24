# Spike 23 報告：sdist 建置與相依解析實測（Sprint 121，GAPS #75 (a)(d)）

日期：2026-07-24。成功標準 S1〜S5 於 premortem.md 動工前定案，本報告逐項對表。

## 結論一句話

**sdist 建得出且裝得起來、乾淨 venv 不帶 `--no-deps` 相依全部解析成功、repo 外 CLI 全鏈
preflight 12/12；但 setuptools 82 的 sdist 預設會把 tests/ 收進去（113 個成員中佔 66 個），
「預設清單很窄」是文件說法不是實況，已以只准縮小的 MANIFEST.in 收束並上實物鎖測試。**

## S1：sdist／wheel 建置與紅線掃描（probe_sdist_build.py）

- 首跑（無 MANIFEST.in）：`python -m build --sdist --wheel` EXIT=0，sdist **113 個檔案**，
  其中 tests/*.py 佔 66 個。刪掉殘留 `cjkfolio.egg-info/` 重建結果相同，
  證實是 **setuptools 82 現行預設行為**，不是舊 SOURCES.txt 種子（probe1.log／probe1b.log）。
- 紅線樣式（local/、out/、assets/、內在整理、.git、devlog/、hooks/）兩輪皆 **0 命中**：
  今日的預設不收這些目錄，但這是實測當下的行為，不是保證。
- 處置：新增 `MANIFEST.in`，只含排除指令（紅線目錄第二道保險＋`prune tests`）。
  tests 不入 sdist 的理由：sdist 裡沒有 conftest.py、samples/ 與字型，收進來的是一包跑不動的測試；
  sdist 的定位＝可安裝的原始碼（與 wheel 對齊）。
- 終態（probe1c.log）：sdist **48 個檔案、162,585 bytes**（cjkfolio 35 支 .py 全進、
  模版 2 份全進、LICENSE／PKG-INFO／pyproject.toml 在）；wheel **42 個檔案**、
  原生二進位 **0 枚**；紅線與非預期 **0 命中**。PASS。

## S2：乾淨 venv 相依解析（probe_clean_install.py + wheel，probe2.log）

venv 不帶 `--system-site-packages`、pip 不帶 `--no-deps`，自 wheel 安裝：

- `pip install` EXIT=0（**29.3s**，PySide6 Essentials 77.5MB＋Addons 168.8MB 等自 PyPI 直下）。
- `pip check` 乾淨；六枚產品相依＋shiboken6 全部就位；import 冒煙
  （cjkfolio、fitz、PySide6、PIL、fontTools、freetype、uharfbuzz）EXIT=0。PASS。

**解析到的版本與本機的漂移**（pre-mortem 風險 3 命中，據實記錄）：

| 套件 | 本機 | venv 解析 | 漂移 |
| --- | --- | --- | --- |
| PyMuPDF | 1.27.2.3 | **1.28.0** | 升版，授權字串逐字不變（見 S5） |
| PySide6（含 Essentials/Addons/shiboken6） | 6.11.0 | **6.11.1** | 升版，授權字串不變 |
| pillow | 12.2.0 | **12.3.0** | 升版；其夾帶二進位上游條款未逐枚重查（Sprint 118 查的是 12.2.0） |
| fonttools | 4.62.1 | **4.63.0** | 升版，MIT 不變 |
| freetype-py | 2.5.1 | 2.5.1 | 不變 → FreeType 2.13.2／FTL 結論（Sprint 118）對新集合成立 |
| uharfbuzz | 0.55.0 | 0.55.0 | 不變 → HarfBuzz 14.2.1／Old MIT 結論（Sprint 120）對新集合成立 |

## S3：repo 外 CLI 全鏈（probe2.log）

工作目錄在系統 temp（repo 外；Spike 21 教訓：repo 內測安裝版等於沒測），素材複製
`samples/paiban-xiaoji-ch1.md`，字型以 `--font-dir` 指回 repo 的 assets/fonts：

- `import-md` 41 段 → `render` **11 頁、禁則 0 違規、擠入 7 撐開 0 超容忍 0** →
  `export-pdf` 5 款字型子集嵌入、授權檢查零警告 → `preflight` **12/12**、最高 TAC 92%。
  與 README 快速開始寫的預期輸出逐項相同。PASS。

## S4：sdist 安裝（probe_clean_install.py + tar.gz，第二個乾淨 venv，probe3.log）

- `pip install cjkfolio-0.115.0.tar.gz` EXIT=0（**48.2s**，含 build isolation 下載 setuptools
  建 wheel），解析到同一組相依版本；`pip check` 乾淨；repo 外同一條 CLI 全鏈 **12/12**。PASS。

## S5：對新解析集合重跑授權稽核（tools/audit_licenses.py，venv 直譯器）

- venv 內補裝 `packaging` 後實跑：**9 枚全部標示為相容、EXIT=0**。
- 漂移鎖未觸發：pymupdf 1.28.0 的授權字串與 1.27.2.3 逐字相同
  （`Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License`），
  pillow 12.3.0 為 `MIT-CMU`、fonttools 4.63.0 為 `MIT`。PASS。

## Gate 4 獨立複驗與 R5 親驗

- **Gate 4**（生產者＝venv 內安裝版 cjkfolio 0.115.0，驗證者＝repo 側 PyMuPDF 1.27.2.3
  直讀 PDF 物件，不經本專案任何檢查器）：11 頁、TrimBox 419.527×595.276pt＝**148×210mm**、
  5 款字型全 **Type0 子集**且子集前綴與匯出日誌逐字相符（BYLRFI／KNFQVP／MQSDKM／NQOQTQ／YYRKDT）、
  `/OutputIntents` 在、header `%PDF-1.3`、首頁文字「第一章 字的呼吸…」。
- **R5**：安裝版渲染的 `page-001.png` 親 Read：直排右起、章名大標與小節標「一、直排的方向」
  字型字級分明、標點置中、行首無禁則字、頁碼「1」在左下（奇數＝左頁），無缺字方框。

## 測試（tests/test_packaging.py 擴 4 項，12 → 16）

- `test_manifest_in_only_narrows`：MANIFEST.in 只准排除指令。
- `test_manifest_in_covers_the_red_line_dirs`：紅線目錄與 tests 的排除逐條在案（只認有效指令行；
  初版用原文子字串比對，RED 驗證時抓到「註解掉的指令也算數」的弱點，當場改掉）。
- `test_build_requires_nothing_beyond_setuptools`：前提鎖，杜絕 setuptools-scm 一類
  「git 追蹤即打包」外掛讓其他鎖全部失效。
- `test_sdist_contents_stay_within_scope`：實物鎖，真建一份 sdist（`--no-isolation` 離線 4.1s）
  逐項驗成員；**RED 驗證**＝抽掉 `prune tests` 後此測試與指令行測試皆確實轉紅，還原後綠。

## 誠實邊界（入 GAPS #77）

1. 單機（Windows 11）單 Python 版本（3.12.10）單次網路狀態的實測，數字不可移植。
2. 相依無上界釘死（`>=`），今日解析到的組合明日可能不同；S5 的稽核對「當下那組」成立。
3. pillow 12.3.0 的夾帶二進位上游條款未逐枚重查（本機仍 12.2.0，Sprint 118 的查證對 12.2.0 成立；
   freetype-py 與 uharfbuzz 版本未動，該兩項結論不受影響）。
4. **PyPI 上架未做**：對外發布行為，需 Owner 帳號與授權（含 #55 (f) 法律複核、#76 條款正文），
  不屬執行工程師可代決。
5. tests 不入 sdist 是取捨不是唯一解（另一路是把 conftest.py＋samples/ 一併打包成自測 sdist，
  但字型永遠不可隨包散布，該路本質上到不了「可跑」，故不取）。
