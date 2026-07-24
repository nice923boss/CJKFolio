# Spike 23 pre-mortem：sdist 建置與相依解析實測（GAPS #75 (a)(d)）

日期：2026-07-24（Sprint 121 動工前）

## 要驗的問題

Sprint 119（Spike 21）刻意用 `--no-deps` 隔離掉的兩件事：

1. **(d) sdist 建不建得出、裝不裝得起來**：`python -m build --sdist` 從未跑過。
2. **(a) 相依解析**：乾淨 venv 不帶 `--no-deps` 執行 `pip install cjkfolio`，
   pip 會不會把 PyMuPDF／PySide6／pillow／fonttools／freetype-py／uharfbuzz 全部裝好，
   裝好之後在 repo 外跑不跑得完 CLI 全鏈。

PyPI 上架不在本 spike 範圍（對外行為，需 Owner 帳號與授權，PLAN 紅線：未授權的對外行為不得預設開啟）。

## 成功標準（動工前定，過不了就不得列入完成清單）

- S1：`python -m build --sdist` EXIT=0，且 sdist 完整清單經紅線樣式掃描
  （`local/`、`out/`、`assets/`、`內在整理`、`devlog/`、`hooks/`、`.git`）**0 命中**。
- S2：乾淨 venv（不帶 `--system-site-packages`、不帶 `--no-deps`）自 wheel 安裝 EXIT=0，
  `pip check` 乾淨，六枚產品相依全部就位並列出實際解析到的版本。
- S3：安裝版在 **repo 外**（Spike 21 教訓：repo 內測安裝版等於沒測）跑完
  `import-md → render --font-dir → export-pdf → preflight`，preflight 12/12。
- S4：自 sdist 安裝（第二個 venv，驗 build isolation 下建得起來）EXIT=0，repo 外 `import-md` EXIT=0。
- S5：以 venv 的直譯器重跑 `tools/audit_licenses.py`，對「pip 剛解析出來的那組版本」
  複驗授權相容性；有任何一枚落回「須確認」即據實記錄，不假裝通過。

## 最可能失敗的三件事

### 1. 相依下載量大或網路慢，pip install 逾時（機率 40%）

PySide6 Essentials＋Addons 合計約 250〜300MB，`pip cache list` 顯示本機 wheel 快取為空
（HTTP 快取是否命中要實測才知）。

- 早期訊號：pip 下載進度停滯超過數分鐘。
- 對策：安裝跑背景不佔前景逾時；第一個 venv 裝完後 HTTP 快取變熱，第二個 venv（sdist）自然快。
- 放棄條件：網路不可用或 PyPI 不可達 → 據實記入 GAPS「相依解析無法在本機驗證」，
  不用「宣告看起來對」冒充驗過。

### 2. sdist 夾帶紅線內容（機率 20%，影響致命＝紅線 #1／#6）

setuptools 的 sdist 預設清單只含宣告套件＋package-data＋標準檔案，但這是「文件上這麼說」（B 級），
沒親眼列過清單前不算數。若有任何自動發現行為把 `local/`、`out/`、參考書檔案掃進去，
這份 tar 一旦外流就是紅線事故。

- 早期訊號：sdist 檔案大小異常（本專案原始碼＋模版應在數百 KB 級）。
- 對策：建置後逐項列 tar 成員並掃紅線樣式（S1）；宣告層另加前提鎖測試
  （無 MANIFEST.in、build requires 只有 setuptools，杜絕 setuptools-scm 式「git 追蹤即打包」的路徑）。
- 放棄條件：無（此項必須過，過不了就修宣告直到過）。

### 3. 解析到的版本與本機不同，授權結論漂移（機率 50%）

`pyproject.toml` 只釘下限（`>=`），pip 會解析 PyPI 上的最新版；THIRD-PARTY-LICENSES.md 的
授權事實是對本機那組版本成立的（pyproject 檔頭自記）。

- 早期訊號：venv 內 `pip list` 版本號與本機不同。
- 對策：S5 用 venv 直譯器重跑稽核工具（它讀執行中直譯器的 installed metadata，
  故量到的就是新解析集合）；差異逐枚記入報告。
- 放棄條件：無（漂移本身不是失敗，漏記漂移才是）。

## 次要風險

- **探針原始碼不得含使用者目錄字面量**（Sprint 114 掃描規則 6＋`test_long_book_tool.py`
  對 `tools/`＋`spikes/` 全部 .py 的守門）：venv 與工作目錄一律執行期以 `tempfile` 推導。
- **中文與空白路徑**：venv 建在系統 temp（ASCII）而非 repo 下，避免疊加已知的非 ASCII 路徑坑。
- **失敗機率預估誤差**：±20%（網路狀態不可先驗）。
