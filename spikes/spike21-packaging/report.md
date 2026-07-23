# Spike 21 報告：wheel 建置與安裝後行為

日期：2026-07-24（Sprint 119）　結論：**PoC 通過**　證據等級：A（本機實測）

對應 pre-mortem：`spikes/spike21-packaging/premortem.md`
探針：`probe_wheel_build.py`（建 wheel 並逐檔列內容）、`probe_install_run.py`（裝進
venv 並在 repo 外執行）。兩支都收 argv 指定路徑，不寫死本機位置（GAPS #63）。

## 成功標準（動工前定，事後不改）

1. `python -m build --wheel` 產得出 wheel，且內容可逐檔列出
2. 裝進乾淨 venv 後，**在 repo 外的目錄**跑得完 `import-md` 與 `render`
3. 跑不動的地方要「大聲壞」：錯誤訊息指得出是哪個路徑不存在
4. 「repo 內執行」形態的既有測試 0 退步

四項全數達成。

## 量到什麼

### 探針一之一：現況（無 `[build-system]`、無套件宣告）

```
建置指令 exit=1
error: Multiple top-level packages discovered in a flat-layout:
['out', 'hooks', 'local', 'assets', 'devlog', 'editor', 'spikes', 'samples',
 'cjkfolio', 'templates'].
ERROR Backend subprocess exited when trying to invoke get_requires_for_build_wheel
結果：未產生任何 wheel。
```

pre-mortem §3 第一條早期訊號命中。setuptools 的自動發現在扁平佈局下拒絕猜測，
這是保護不是故障：`local/`（金鑰紅線 #6）與 `out/`（參考書紅線 #1）若被猜進 wheel，
才是真正的事故。

### 探針一之二：加上 10 行宣告後

`pyproject.toml` 加 `[build-system]` 與顯式 `packages`／`package-dir`／`package-data`：

```
產出：cjkfolio-0.112.0-py3-none-any.whl（176,280 bytes，42 個項目）
模版：在 wheel 內（2 個項目）      cjkfolio/templates/{neizai-zhengli,jiejiao-manxing}.json
字型資產：不在 wheel 內（0 個項目）
editor：不在 wheel 內（0 個項目）
授權全文：在 wheel 內（1 個項目）  cjkfolio-0.112.0.dist-info/licenses/LICENSE
```

38 個 `.py` ＋ 2 份模版 ＋ dist-info。`local/`、`out/`、`assets/reference/` 一個都沒進去。

### 探針二之一：裝好之後，在 repo 外執行（修產品碼之前）

```
套件位置： ...\venv\Lib\site-packages\cjkfolio
預設模版： ...\venv\Lib\site-packages\templates\neizai-zhengli.json
預設模版存在： False
預設字型目錄： ...\venv\Lib\site-packages\assets\fonts
預設字型目錄存在： False

=== import-md（cwd 在 repo 外） → exit=1 ===
cjkfolio.styles.TemplateError: 讀取模版失敗
  ...\venv\Lib\site-packages\templates\neizai-zhengli.json：
  [Errno 2] No such file or directory
```

pre-mortem §1 的判斷成立：`parents[1]` 在安裝形態指到 site-packages 本身。
模版明明就在 wheel 裡（`cjkfolio/templates/`），程式卻往上一層找。

### 探針二之二：假通過對照組（本 spike 最該留檔的一筆）

同一個 venv 的同一支 python，只把 cwd 換成 repo 根：

```
=== import-md（cwd 在 repo 根：假通過對照組） → exit=0 ===
  匯入完成：4 段 → ...\work\doc2.json
```

`python -m` 會把 cwd 放進 `sys.path[0]`，所以這一跑載到的是 repo 裡那份原始碼，
不是裝好的那份。**在 repo 目錄下測試安裝版，測起來會全過，什麼都沒驗到。**
任何後續的安裝驗證都必須在 repo 外的目錄執行，這條寫進報告當紀律。

### 探針二之三：修好之後

修的是模版查找一處（`resolve_template_dir`）與 CLI 的字型目錄入口：

```
=== import-md（cwd 在 repo 外） → exit=0 ===
  匯入完成：4 段 → doc.json

=== render（cwd 在 repo 外，未給字型目錄） → exit=1 ===
cjkfolio.fonts.FontError: 找不到可用字型：思源宋體 TC/bold
  （字型目錄 ...\venv\Lib\site-packages\assets\fonts，
    依 assets/fonts/FONTS.md 指令重現下載）

=== render（cwd 在 repo 外，--font-dir <repo>/assets/fonts） → exit=0 ===
  渲染完成：1 頁 → 樣張
  禁則檢查：0 違規
  字型警告：家族「思源宋體 TC」無字重 bold 檔，以 heavy 替代
  使用字型：SourceHanSansTC-Medium.otf、SourceHanSerifTC-Heavy.otf、
            SourceHanSerifTC-Regular.otf、jf-openhuninn-2.1.ttf
  首頁：樣張\page-001.png
```

未給字型目錄那一跑仍是失敗，但這是**設計要的失敗**：字型是使用者資產
（二進位不入 repo，見 GAPS #12 與 `assets/fonts/FONTS.md`），不可能跟著 wheel 走，
所以只能大聲壞並指出實際找過的目錄，不能沉默 fallback 到不存在的路徑。

R5 真實素材驗收：`page-001.png` 已用 Read 工具開圖親驗，直排右起、四段齊備、
兩級標題字級有別、頁碼在左下。素材為本探針自寫的測試短文，不涉參考書（紅線 #1）。

## 改了什麼（三處，皆最小）

| 檔案 | 改動 | 為什麼是最小 |
| --- | --- | --- |
| `pyproject.toml` | `[build-system]` ＋ `packages`／`package-dir`／`package-data` | 扁平佈局下沒有更短的寫法；模版留在 repo 根不搬檔 |
| `cjkfolio/template_library.py` | 新增 `resolve_template_dir()` | 判斷條件只有「套件內 templates/ 在不在」，不猜執行環境 |
| `cjkfolio/cli.py` | `DEFAULT_TEMPLATE` 改走上式；`render`／`export-pdf` 加 `--font-dir` | 核心 API 本就收 `font_dir`，缺的只有 CLI 這一段 |

外加 `cjkfolio/fonts.py` 錯誤訊息補上實際字型目錄一行（安裝形態下沒有這行就無從診斷）。

repo 形態行為完全不變：`cjkfolio/templates/` 在 repo 裡不存在，`resolve_template_dir()`
必然落到 `<repo>/templates`，與改動前同一個路徑。1225 項測試 0 退步即為此背書。

## 誠實邊界（本 spike 沒驗的事）

1. **相依解析沒驗**：venv 用 `--system-site-packages` ＋ `pip install --no-deps`。
   本題要驗的是本專案自己的檔案佈局，不是 PyPI 能不能把 PySide6 與 PyMuPDF 裝好。
   「pip install cjkfolio 會不會裝得起來相依」這件事**未經驗證**。
2. **只在一台機器、一個 Python（3.12.10 Windows）上跑過**，其他平台未驗。
3. **`editor/` 不在 wheel 內**：它不是套件（無 `__init__.py`，`app.py` 自行
   `sys.path.insert`）。pip 安裝形態**沒有圖形編輯器**，只有 CLI。
4. **sdist 未建、未上架**：`python -m build --sdist` 沒跑過，PyPI 帳號與上架流程
   完全未碰。本 spike 證明的是「建得出 wheel 且裝了能跑」，不是「已可散布」。
5. **AI 輔助指派的設定檔預設路徑**（`cli.py` 的 `--config`）在安裝形態指向
   site-packages 內不存在的位置。未改：私有金鑰檔本就不該放進 site-packages
   （紅線 #6），安裝形態請以 `--config` 明給。

以上 1、3、4、5 入 GAPS。
