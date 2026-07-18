# 第三方授權清單

CJKFolio 本身採 **AGPL-3.0-or-later**（見根目錄 `LICENSE`）。本檔列出所用第三方元件的授權。

## 本清單的證據等級與邊界（先說限制）

- 授權字串**逐字取自 2026-07-18 本機 Python 3.12.10 環境**各套件 `dist-info` 的 `METADATA`、`COPYING`、`LICENSE` 檔案，非取自記憶或第二手整理。
- **未涵蓋**：各套件自身的傳遞相依（transitive dependencies）未展開稽核。
- **未查證**：`freetype-py` 的 wheel 夾帶編譯好的 `libfreetype.dll`，但 FreeType C 函式庫本身的授權（FTL 或 GPLv2 二選一）在該 wheel 內查無任何條款檔案，無法從本機一手檔案確認。純原始碼散布階段風險低（該 DLL 由使用者自 PyPI 取得，非由本專案散布），但**製作含二進位的安裝檔前必須先查證**。
- **會漂移**：版本升級可能改變授權。PyMuPDF 在 1.24.x 之前為 GPL v3 而非 AGPL v3，即為實例。`pyproject.toml` 的相依宣告是本清單的錨點，升版時須重查。
- 本清單陳述讀到的授權事實，**不構成法律意見**。正式公開釋出前建議由具開源授權經驗者複核。

## 產品相依（隨產品散布，`cjkfolio/` 與 `editor/` 直接 import）

| 套件 | 版本 | 授權（逐字） | 一手證據 |
| --- | --- | --- | --- |
| PyMuPDF（import 名 `fitz`） | 1.27.2.3 | `Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License` | `pymupdf-1.27.2.3.dist-info/COPYING` 全檔僅此一行；`METADATA` L8 同字串 |
| PySide6 | 6.11.0 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | `pyside6-6.11.0.dist-info/METADATA` L6 |
| Pillow（import 名 `PIL`） | 12.2.0 | `MIT-CMU` | `pillow-12.2.0.dist-info/METADATA` L6（PEP 639 `License-Expression`） |
| fontTools | 4.62.1 | `MIT` | `fonttools-4.62.1.dist-info/METADATA` L10 |
| freetype-py（import 名 `freetype`） | 2.5.1 | BSD-3-Clause | `METADATA` 無 License 欄；`LICENSE.txt` 首行「freetype-py is licensed under the terms of the new or revised BSD license」 |
| uharfbuzz | 0.55.0 | `Apache License 2.0` | `uharfbuzz-0.55.0.dist-info/METADATA` L8 |

PySide6 另有三個必要相依，授權字串相同（各自 `dist-info/METADATA` L6 已逐一複讀）：`shiboken6` 6.11.0、`PySide6-Essentials` 6.11.0、`PySide6-Addons` 6.11.0。

## 開發與測試相依（不隨產品散布）

| 套件 | 版本 | 授權 | 一手證據 |
| --- | --- | --- | --- |
| pytest | 9.0.2 | `MIT` | `pytest-9.0.2.dist-info/METADATA` L6 |
| python-docx | 1.2.0 | `MIT` | `python_docx-1.2.0.dist-info/METADATA` L6 |

`python-docx` 只用於測試中的獨立驗證路徑。產品的 docx 匯入（`cjkfolio/docx_import.py`）以標準函式庫 `zipfile` 加 `xml` 自行解析 OOXML，不依賴它。

## 為什麼是 AGPL：PyMuPDF 決定了這件事

CJKFolio 採 AGPL 不是偏好，是相依鎖死的結果，這點必須對下游講明白。

`PyMuPDF` 是 AGPL-3.0，且被 `cjkfolio/preflight.py:12` 與 `cjkfolio/reference_extract.py:14` 以模組方式 import 進同一個行程。只要 CJKFolio 以結合物形式散布，AGPL 的傳染性即擴及整個專案，MIT、Apache-2.0、BSD、MPL-2.0、LGPL 全部不可選。

其餘相依與 AGPL-3.0 皆相容：Apache-2.0 單向相容 GPLv3 系；MIT、BSD-3-Clause、MIT-CMU 皆可併入，只需保留其著作權聲明。

**PySide6 的三選一授權，本專案取 GPL-3.0-only 臂**，理由是實查發現的一件事：`PySide6-Addons` 夾帶的 Qt 模組（Qt Quick3D、Qt VirtualKeyboard、Qt HttpServer、Qt Graphs、Qt Charts、Qt DataVisualization 等）在 Qt 官方的開源側**只有 GPL-3.0 沒有 LGPL 臂**，`PySide6-Essentials` 亦含屬 Qt tools 的 `Qt6Designer.dll`。因此籠統宣稱「本專案走 LGPL 臂」對實際安裝的內容並不成立。取 GPL-3.0-only 臂則涵蓋全部模組，且 GPLv3 §13 與 AGPLv3 §13 互相授權，與 AGPL-3.0 相容。**GPL-2.0-only 臂與 AGPL-3.0 不相容，本專案明確不選。**

## 授權標示的精確寫法

- CJKFolio **自有程式碼**：`AGPL-3.0-or-later`。
- **結合散布物的實效授權**：`AGPL-3.0`。因為 PyMuPDF 的一手檔案只寫「GNU AFFERO GPL 3.0」未載明 or-later，而 PySide6 與 shiboken6 明寫 `-only`。下游行使 or-later 時只及於 CJKFolio 自有程式碼的部分。

## 本專案必須履行的義務

- **§5（修改標註）**：本 repo 的 git 歷史即為修改紀錄，每次變更含日期與內容。
- **§13（網路互動）**：CJKFolio 目前是桌面 GUI 與 CLI 工具，不與使用者透過網路互動（`cjkfolio/` 與 `editor/` 全域無 socket、http.server、flask、fastapi、uvicorn；唯一對外連線是 `cjkfolio/ai_style.py` 以 client 身分呼叫使用者自填的 AI endpoint），故 §13 不觸發。**但若任何人日後以網路服務形式提供 CJKFolio，必須向服務使用者提供含修改的完整對應原始碼。** 這一條先寫在這裡，不等到有人架站才發現。
- **保留第三方著作權聲明**：Pillow（HPND 風格）、fontTools（Copyright (c) 2017 Just van Rossum）、freetype-py（Copyright (c) 2011-2014 Nicolas P. Rougier，含 BSD 第三條不得背書條款）。uharfbuzz 若上游有 NOTICE 須一併保留，日後若修改其原始碼須標註變更。

## 字型資產

內建字型的授權檔在 `assets/fonts/`，字型二進位本身不入 repo（見 `.gitignore`，取得方式見 `assets/fonts/FONTS.md`）。

- 思源宋體 TC、思源黑體 TC：SIL Open Font License 1.1（`assets/fonts/LICENSE.txt`、`assets/fonts/LICENSE-SourceHanSansTC.txt`）
- 辰宇落雁體、jf open 粉圓：OFL 1.1（**全文尚未收入 repo**，`FONTS.md` 目前只外指上游 repo。現況因字型二進位不隨 repo 散布而未觸發 OFL 第 2 條的隨附義務，**但一旦製作含字型的安裝檔或容器映像即構成違約，打包前必須補齊**）
- 全字庫正楷體 TW-Kai、全字庫正宋體：`FONTS.md` 僅記「國發會開放授權」，**條款名稱與版本尚未查證、全文不在 repo**，而模版已宣告其為部分樣式的 `font_family`。此項列於 GAPS #12，查證完成前不宣稱已完成授權查核。

**一件對使用者有利、值得講清楚的事**：以 OFL 字型排版產出的 PDF **不受 OFL 拘束**。依 OFL 1.1 第 5 條末句（`assets/fonts/LICENSE.txt`），授權要求不適用於使用該字型軟體製作的文件。使用者不需隨自己的 PDF 附上 OFL 全文。

## 商標與名稱指涉

模版的 `source_font` 欄記錄了華康、Monotype、Adobe、Apple 等商用字型名稱（DFMingStd、DFHeiStd、PepitaMT、GillSans-Light、ACaslonPro 等），這些是量測參考書時的技術對映紀錄。**這些名稱多為各自權利人的註冊商標，本專案未散布其任何字型檔案。**

## 未安裝但須警惕的同名套件

稽核發現本機環境另有 `pymupdf-layout` 1.27.2.3，其授權為 `Dual Licensed - Polyform Noncommercial or Artifex Commercial License`。**Polyform Noncommercial 不是 OSI 開源授權，與 AGPL-3.0 不相容。** 本專案目前零 import（已全庫驗證），但因名稱與 PyMuPDF 相近，極易被誤裝誤用。任何人要為表格擷取之類的需求引入它之前，必須先解決授權衝突。
