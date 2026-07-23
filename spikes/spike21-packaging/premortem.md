# Spike 21 Pre-mortem：wheel 建置與安裝後行為

日期：2026-07-24　對應 README 誠實範圍表「pip 安裝散布：未做」與 GAPS #71（打包 Sprint）

`pyproject.toml` 自 Sprint 98 存在，但它的用途一直是「授權錨點」而非「可安裝宣告」：
沒有 `[build-system]`、沒有套件宣告、沒有資料檔宣告，README 也據實寫著
「安裝後的行為從未驗證過，故不提供也不宣稱 pip 安裝」。本 spike 要量的就是
「從未驗證」這四個字底下實際藏了什麼。

## 1. 最可能失敗的方式

**裝得起來，但跑不動，而且是安靜地跑不動。** 兩個資源錨點都綁 repo 根：

- `cjkfolio/cli.py:50` `ROOT = Path(__file__).resolve().parents[1]` → 預設模版 `templates/neizai-zhengli.json`
- `cjkfolio/fonts.py:9` `DEFAULT_FONT_DIR = ... parents[1] / "assets" / "fonts"`

裝進 site-packages 後 `parents[1]` 指到 site-packages 本身，模版與字型都不在那裡。
更糟的形態是「在 repo 目錄下測試安裝版」：cwd 剛好有 `templates/`，測試看起來全過，
一換到別的目錄就壞。這種假通過比直接爆炸危險。

## 2. 失敗機率

**高（>90%）**。這不是押注，是幾乎確定會發生的事，spike 的目的不是賭它會不會失敗，
而是**量出失敗的確切形態與修復成本**。次高風險是連 wheel 都建不起來：扁平佈局下
setuptools 自動發現會看到 `cjkfolio`、`editor`、`tools`、`tests`、`spikes`、`hooks`
等多個頂層目錄而拒絕猜測。

## 3. 早期訊號

- `python -m build --wheel` 直接報 `Multiple top-level packages discovered`
- wheel 內只有 `cjkfolio/*.py`，`templates/*.json` 不在裡面
- 安裝後在 repo 外的目錄跑 CLI，第一個錯誤來自模版或字型路徑
- 在 repo 內跑安裝版卻「正常」（＝證實假通過確實會發生）

## 4. 對策

1. **先量再改**：探針一建 wheel 並逐檔列出內容，探針二裝進 venv 後**刻意在 repo 外的
   臨時目錄**執行 CLI，把每一個錯誤逐字記下，不先改任何產品碼
2. 模版屬程式資產（純文字、進得了 wheel）→ 走套件內資料 `importlib.resources`
3. 字型屬使用者資產（二進位不入 repo，見 #12／FONTS.md）→ **不可能進 wheel**，
   只能改為可設定並在缺漏時明確報錯，不沉默 fallback 到不存在的路徑
4. 兩個錨點都保留「repo 內執行」路徑優先，避免破壞現行唯一支援形態與 1217 測試
5. venv 用 `--system-site-packages` 加 `pip install --no-deps`：本 spike 要驗的是
   **本專案自己的檔案佈局**，不是 PyPI 相依解析；重下 PySide6 與 PyMuPDF 數百 MB
   對這個問題零資訊量。此限制寫進報告，不假裝驗過相依解析

## 5. 放棄條件

- 修復需動到 3 個以上模組的資源查找、或需改變 `editor/` 的載入模型
  → 本 Sprint 只交付 spike 報告與版本策略對齊（#71），可安裝性入 GAPS
- 修復會讓「repo 內執行」形態的任一既有測試退步 → 停工重議，現行形態優先

## 6. 替代方案

**不做 wheel，把「自 repo 執行」定為唯一支援形態並在 README 寫死。** 這個選項不劣：
本專案的真實使用形態是 clone 後跑 CLI 與編輯器，而 `editor/` 本就不是套件
（無 `__init__.py`，`app.py:27` 自行 `sys.path.insert`）。若量出的修復成本偏高，
這是誠實且省事的收斂。判準是資料，不是意願。

## 7. 預估誤差範圍

wheel 建置設定小（`[build-system]` 加套件宣告，10 行內）。真正的不確定在資源查找：
若模版與字型各只有 1 處錨點（已 grep 確認 `cjkfolio/` 內僅 2 處 `Path(__file__)`），
改動小；但 `editor/`、`tools/`、`tests/` 另有各自的 ROOT 假設，若它們也被牽動，
範圍會擴大一級。估半天，誤差 ±半天。
