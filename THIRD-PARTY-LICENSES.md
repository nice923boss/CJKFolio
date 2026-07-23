# 第三方授權清單

CJKFolio 本身採 **AGPL-3.0-or-later**（見根目錄 `LICENSE`）。本檔列出所用第三方元件的授權。

## 本清單的證據等級與邊界（先說限制）

- 授權字串**逐字取自 2026-07-18 本機 Python 3.12.10 環境**各套件 `dist-info` 的 `METADATA`、`COPYING`、`LICENSE` 檔案，非取自記憶或第二手整理。
- **傳遞相依已展開**（2026-07-24 Sprint 118）：`tools/audit_licenses.py` 由 `pyproject.toml` 的宣告出發，用 `importlib.metadata` 遞迴展開，marker 依當前環境求值且不取任何 extra。產品側 6 枚宣告展開為 **9 枚**、併計開發相依為 **18 枚**，逐枚判定見下方「傳遞相依稽核」。
- **稽核的判定是字串比對，不是法律意見**：比對已知 SPDX 識別碼與一份人工複核過的字串表，比不到就標「須確認」並以 exit 1 擋下，不預設通過。授權字串一改（升版換授權），複核表的鍵即對不上而落回「須確認」。
- **仍未涵蓋**：夾帶原生二進位者，其上游 C 函式庫的條款只逐枚人工查證（見下方「夾帶的原生二進位」），工具本身只回報「有幾個二進位、dist-info 有哪些授權檔」，不判讀上游條款。
- **會漂移**：版本升級可能改變授權。PyMuPDF 在 1.24.x 之前為 GPL v3 而非 AGPL v3，即為實例。`pyproject.toml` 的相依宣告是本清單的錨點，升版時須重查。
- 本清單陳述讀到的授權事實，**不構成法律意見**。正式公開釋出前建議由具開源授權經驗者複核。

## 產品相依（隨產品散布，`cjkfolio/` 與 `editor/` 直接 import）

| 套件 | 版本 | 授權（逐字） | 一手證據 |
| --- | --- | --- | --- |
| PyMuPDF（import 名 `fitz`） | 1.27.2.3 | `Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License` | `pymupdf-1.27.2.3.dist-info/COPYING` 全檔僅此一行；`METADATA` L8 同字串 |
| PySide6 | 6.11.0 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | `pyside6-6.11.0.dist-info/METADATA` L6 |
| Pillow（import 名 `PIL`） | 12.2.0 | `MIT-CMU` | `pillow-12.2.0.dist-info/METADATA` L6（PEP 639 `License-Expression`） |
| fontTools | 4.62.1 | `MIT` | `fonttools-4.62.1.dist-info/METADATA` L10 |
| freetype-py（import 名 `freetype`） | 2.5.1 | BSD-3-Clause（binding 自身）＋夾帶 FreeType 2.13.2 取 FTL 臂 | `METADATA` 無 License 欄；`LICENSE.txt` 首行「freetype-py is licensed under the terms of the new or revised BSD license」；夾帶二進位見下節 |
| uharfbuzz | 0.55.0 | `Apache License 2.0` | `uharfbuzz-0.55.0.dist-info/METADATA` L8 |

PySide6 另有三個必要相依，授權字串相同（各自 `dist-info/METADATA` L6 已逐一複讀）：`shiboken6` 6.11.0、`PySide6-Essentials` 6.11.0、`PySide6-Addons` 6.11.0。

## 開發與測試相依（不隨產品散布）

| 套件 | 版本 | 授權 | 一手證據 |
| --- | --- | --- | --- |
| pytest | 9.0.2 | `MIT` | `pytest-9.0.2.dist-info/METADATA` L6 |
| python-docx | 1.2.0 | `MIT` | `python_docx-1.2.0.dist-info/METADATA` L6 |
| packaging | 26.0 | `Apache-2.0 OR BSD-2-Clause` | `packaging-26.0.dist-info/METADATA` 的 `License-Expression`；`licenses/` 下兩份全文各自在 |

`python-docx` 只用於測試中的獨立驗證路徑。產品的 docx 匯入（`cjkfolio/docx_import.py`）以標準函式庫 `zipfile` 加 `xml` 自行解析 OOXML，不依賴它。`packaging` 只被 `tools/audit_licenses.py` 用來對 `Requires-Dist` 的 marker 求值。

## 傳遞相依稽核（2026-07-24 Sprint 118 首次展開）

重跑方式（結論可複驗，非一次性人工整理）：

```
python tools/audit_licenses.py                # 產品側
python tools/audit_licenses.py --include-dev  # 併計開發側
```

產品側 6 枚宣告展開為 9 枚：上表六項，加上由 `PySide6` 帶入的 `shiboken6`、`PySide6-Essentials`、`PySide6-Addons`（授權字串三者相同）。**產品側沒有任何未宣告的第四層相依**：`PyMuPDF`、`freetype-py`、`uharfbuzz` 的 `Requires-Dist` 皆為空，`pillow` 與 `fonttools` 的相依全部掛在 extra 上（本專案不取任何 extra），故不安裝。

併計開發側為 18 枚，多出的 9 枚全部來自 `pytest`（`colorama` BSD-3-Clause、`iniconfig` MIT、`packaging` Apache-2.0 OR BSD-2-Clause、`pluggy` MIT、`Pygments` BSD-2-Clause）與 `python-docx`（`lxml` BSD-3-Clause、`typing_extensions` PSF-2.0）。**18 枚全部標示為相容，0 枚須確認。**

兩枚判定不是直接讀 SPDX 識別碼而來，已開授權檔逐字確認後寫入工具的複核表：`freetype-py` 與 `colorama` 的 `METADATA` 只有 `License :: OSI Approved :: BSD License` 這個分類器（不分二款與三款），兩者的 `LICENSE` 全文都含「不得背書」條款，故為 BSD-3-Clause。

## 夾帶的原生二進位（wheel 內的 `.dll` 與 `.pyd`）

**這一節是 GAPS #55 (d) 的教訓一般化。** wheel 裡的授權檔講的是「這個 Python 套件自身」的授權，不必然涵蓋它靜態連結或並排夾帶的 C 函式庫。`freetype-py` 就是實例：套件是 BSD-3-Clause，夾帶的 FreeType 是完全不同的一套條款。

| 套件 | 二進位數 | 夾帶的上游 | 上游條款 | 一手證據 |
| --- | --- | --- | --- | --- |
| PyMuPDF | 3 | MuPDF（`mupdfcpp64.dll`） | AGPL-3.0 或 Artifex 商業授權 | `COPYING` 那一行同時涵蓋 MuPDF 與 binding（同屬 Artifex） |
| Pillow | 8 | 12 個上游元件（逐字取自分段標題）：`brotli-1.2.0`、`freetype-2.14.3`、`harfbuzz-13.2.1`、`lcms2-2.18`、`libavif-1.4.1`、`libjpeg-turbo-3.1.4.1`、`libpng-1.6.56`、`libwebp-1.6.0`、`openjpeg-2.5.4`、`tiff-4.7.1`、`xz-5.8.3`、`zlib-ng-2.3.3` | 各自條款**全文已隨附** | `pillow-12.2.0.dist-info/licenses/LICENSE` 共 76,408 字元、1,618 行，以 `===== 元件-版本 =====` 分段逐段附上全文 |
| fontTools | 6 | 無第三方 C 函式庫（六個 `.pyd` 的路徑即 fontTools 自身模組：`cu2qu`、`feaLib/lexer`、`misc/bezierTools`、`pens/momentsPen`、`qu2cu`、`varLib/iup`，皆為 Cython 加速版） | MIT（同套件本體） | 檔案清單逐枚列出；`licenses/LICENSE.external` 內容為測試用字型的 OFL，與二進位無關 |
| freetype-py | 1 | FreeType 2.13.2（`libfreetype.dll`） | FTL 或 GPLv2 二選一，**本專案取 FTL 臂** | 見下節 |
| uharfbuzz | 2 | HarfBuzz（靜態連結進 `_harfbuzz.pyd`） | Old MIT（HarfBuzz 上游）；**wheel 內未隨附** | `licenses/LICENSE` 全 11,357 字元為純 Apache-2.0 全文，全檔搜不到 harfbuzz 字樣 |
| shiboken6 | 12 | Qt binding 執行期，**外加 Microsoft VC++ 可轉散布元件**（`concrt140.dll`、`msvcp140*.dll`、`vcruntime140*.dll`） | Qt 側同 PySide6；VC++ 執行期屬 Microsoft 自有條款，**不在 LGPL／GPL 涵蓋範圍內** | `dist-info/licenses/` 僅一份 `LicenseRef-Qt-Commercial.txt`（462 字元，指向 qt.io 條款頁） |
| PySide6-Essentials | 210 | Qt 6 核心模組 | 同 PySide6（本專案取 GPL-3.0-only 臂） | 同上 |
| PySide6-Addons | 177 | Qt 6 附加模組 | 同 PySide6 | 同上 |

**尚未解決的兩項**（已入 GAPS #74）：uharfbuzz 未隨附 HarfBuzz 上游條款；shiboken6 夾帶的 VC++ 可轉散布元件之轉散布條件未查證。兩者在純原始碼散布階段皆不觸發（二進位由使用者自 PyPI 取得，非由本專案散布），**製作安裝檔前必須先解決**。

## FreeType：夾帶版本與授權臂（2026-07-24 查證，關 GAPS #55 (d)）

Sprint 98 記的「wheel 內查無條款檔案、無法確認」已解除，方法是不再只找條款檔，改為先釘版本再取上游條款：

- **版本＝FreeType 2.13.2**（A 級一手證據，兩路互證）：`libfreetype.dll` 的 Windows 版本資源為 `ProductName: FreeType`、`FileVersion: 2.13.2`、`CompanyName: The FreeType Project`、`LegalCopyright: © 2000-2023 The FreeType Project`；執行期 `freetype.version()` 回 `(2, 13, 2)`。
- **二進位內確實沒有條款文字**（複驗 Sprint 98 的說法）：全檔 1,500,160 位元組掃可列印字串，命中 license 或 copyright 關鍵字者僅 4 筆，皆為 API 名稱與字符名，無條款段落。
- **上游條款為二選一**（B 級官方 + A 級本機）：FreeType 官方授權頁載明可選 `docs/FTL.TXT` 的 FreeType License 或 `docs/GPLv2.TXT` 的 GPLv2，且**FTL 相容於 GPLv3、不相容於 GPLv2**。本機另有一份一手全文：`pillow-12.2.0.dist-info/licenses/LICENSE` 的 `===== freetype-2.14.3 =====` 段落即 FTL 全文（Pillow 自己也夾帶 FreeType）。
- **本專案取 FTL 臂**：GPLv2 臂與本專案的 AGPL-3.0 不相容（同 PySide6 明確不選 GPL-2.0-only 的理由），FTL 臂則相容於 GPLv3 系。

FTL 的義務有二，皆屬文件層而非程式碼層：

1. **致謝**：散布文件中須說明本軟體部分內容基於 FreeType Team 的成果。本專案以下列文字履行，附上官網連結（官方鼓勵但不強制）：

   > Portions of this software are copyright © 2023 The FreeType Project (https://freetype.org). All rights reserved.

2. **不得以對方名稱做廣告或背書**：FreeType 作者群與使用者雙方，未經書面同意皆不得以對方名稱作商業、廣告或推廣用途。本專案指涉時一律用「FreeType Project」或「FreeType library」等中性寫法。

**若日後製作含二進位的安裝檔**，除上述致謝外，還須把 FTL 全文一併收入散布物（同 OFL 字型的處置，見下方「字型資產」）。

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
- **FreeType（FTL 臂）的文件致謝與名稱使用限制**：見上方「FreeType：夾帶版本與授權臂」，致謝文字已寫入本檔。此義務隨夾帶的 `libfreetype.dll` 而來，不是本專案自行加碼。

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
