# Spike 22 報告：夾帶原生二進位的上游條款查證

**日期**：2026-07-24（Sprint 120）
**對應缺口**：GAPS #74 (e)(f)，兩項皆被登記為「製作安裝檔前的硬性阻擋項」
**結論**：**PoC 通過**。兩項的條款皆取得一手依據並寫入 `THIRD-PARTY-LICENSES.md`，義務逐條可執行，四條文件漂移鎖已上測試。殘留兩個誠實邊界，見文末。
**證據等級**：A（四份一手來源全部在本機，探針可重跑）

## 成功標準（動工前定，逐條回填）

| # | 標準 | 結果 |
| --- | --- | --- |
| 1 | HarfBuzz 版本兩路互證，不靠單一來源 | **達成**：執行期 API 與二進位字串皆為 14.2.1 |
| 2 | 取得 HarfBuzz 上游條款的一手全文 | **達成**：Pillow 隨附副本（版本邊界見文末） |
| 3 | 取得 Microsoft 轉散布條件的一手文字 | **達成**：CPython 3.12 的 `LICENSE.txt` |
| 4 | 答出兩項與 AGPL-3.0 的關係，依據為條款正文而非推測 | **達成**：依 repo 根 `LICENSE` 第 1 節系統程式庫定義 |
| 5 | 結論的前提被機器守住，不靠人記得 | **達成**：6 條測試，其中 4 條經 RED 驗證 |

## 探針與逐字輸出

### 探針一：`probe_harfbuzz.py`

```
uharfbuzz 發行版本 : 0.55.0
路徑一 執行期 API  : uharfbuzz.version_string = 14.2.1
路徑二 二進位字串  : _harfbuzz.pyd 內出現 '14.2.1' 共 1 處
           首處鄰近 : b'er verify error: text was: %s.\x00\x00\x00\x00\x00\x00invalid\x00C\x00\x00\x0014.2.1\x00\x00\x00\x00\x00\x00HB_FONT_FUNCS\x00\x00\x00start table kern\x00\x00\x00\x00'
互證結果           : 一致
```

鄰近位元組是 `HB_FONT_FUNCS`、`start table kern`，都是 HarfBuzz 自身的符號與訊息，可排除「湊巧撞到別的版本號」。

連結形態（17 枚 DLL 名稱中無任何 harfbuzz）：

```
外部 harfbuzz DLL  : 無
判定               : 靜態連結（HarfBuzz 編進 .pyd）
```

uharfbuzz 自己隨附的條款檔複驗，與 Sprint 118 的記載一致：

```
uharfbuzz-0.55.0.dist-info/licenses/LICENSE：11357 字元
   含 'harfbuzz' : False
   含 'apache'   : True
```

全機掃描 1,079 份授權文字檔，命中 `harfbuzz` 的只有 3 份，其中唯一含條款正文者是 `pillow-12.2.0.dist-info/licenses/LICENSE`（76,408 字元）的 `===== harfbuzz-13.2.1 =====` 段落。

### 探針二：`probe_msvc_runtime.py`

10 枚 VC++ 執行期元件逐枚版本（略，全表已寫入 `THIRD-PARTY-LICENSES.md`）。三個關鍵對照：

```
2. 同名元件是否隨 Python 自身安裝
   vcruntime140.dll         有　...\Python312\vcruntime140.dll　檔案版本 14.42.34438.0
   vcruntime140_1.dll       有　...\Python312\vcruntime140_1.dll　檔案版本 14.42.34438.0
3. 同名元件是否已存在於 System32
   十枚全部有，版本皆 14.44.35211.0
5. 本專案 wheel 目前有沒有夾帶任何原生二進位
   wheel：cjkfolio-0.113.0-py3-none-any.whl　項目 42 筆
   原生二進位：無
   判定：本專案未散布任何原生二進位
```

條款正文掃描命中 8 筆，其中唯一相關者是 `Python312\LICENSE.txt`（36,235 字元）的「Additional Conditions for this Windows binary build」段落，內含四條轉散布限制，並明載那些限制只及於 Microsoft Distributable Code 本身。

## 三個子問的答案（pre-mortem 對策的落地）

pre-mortem 判斷 (f) 有 60% 機率取不到 Microsoft 條款正文，對策是把它拆成三個各自可答的子問。實跑結果：**正文確實沒取到 Microsoft 原文，但三個子問全部答出來了**，拆題有效。

1. **本專案現在有沒有在散布？** 沒有。wheel 42 項目零原生二進位，版本控管清單亦無。(f) 目前不觸發。
2. **條款是什麼？** 四條限制，一手依據為 CPython 對同一組元件的轉散布聲明。
3. **與 AGPL 是什麼關係？** MSVC 執行期符合 AGPL-3.0 第 1 節的系統程式庫定義（隨編譯器這個 Major Component 正常打包、僅用於使作品能在該平台運行），不計入 Corresponding Source，copyleft 不因它擴及。

## 修的與加的

| 項目 | 內容 |
| --- | --- |
| `THIRD-PARTY-LICENSES.md` | 新增 HarfBuzz、Microsoft VC++ 兩專節；夾帶二進位表兩列更新；義務清單加兩條 |
| `tests/test_license_audit.py` | 新增 6 條測試（29 → 35） |

六條測試的分工：兩條守版本與清單漂移（升版換內容就紅）、一條守條款全文完整（Old MIT 要求聲明隨副本走，刪掉就紅）、一條守四條限制逐條在案、兩條守結論賴以成立的前提（靜態連結、本專案不散布二進位）。

## RED 驗證（不是寫完就宣稱有效）

把 `THIRD-PARTY-LICENSES.md` 換回 Sprint 119 版本（8,806 字元）跑四條文件相關測試：

```
test_document_records_the_installed_harfbuzz_version：紅　本機 _harfbuzz.pyd 夾帶 HarfBuzz 14.2.1，THIRD-PARTY-LICENSES.md 未記載此版本
test_document_carries_the_harfbuzz_notice_verbatim：紅　HarfBuzz 條款全文缺片段：'Copyright © 2005,2006,2020,2021,2022,2023  Behdad Esfahbod'
test_document_records_the_microsoft_redistribution_conditions：紅　文件未記載轉散布條件：'不得更動 Microsoft Distributable Code 中的任何著作權、商標或專利聲明'
test_document_lists_every_msvc_runtime_shiboken_bundles：紅　shiboken6 夾帶但文件未逐枚列出：['msvcp140.dll', ...]
```

四條在舊文件下全紅、在新文件下全綠，漂移鎖確實有效。

## 誠實邊界

1. **HarfBuzz 條款全文取自 13.2.1 而非本機的 14.2.1**。兩版條款文字是否逐字相同未經比對，14.2.1 自身的 `COPYING` 本機無副本。製作安裝檔前應取 14.2.1 原文覆蓋。
2. **Microsoft 條款正文未取得一手副本**。本結論的依據是 CPython 對同一組元件的轉散布聲明，不是 Visual Studio 授權合約原文。
3. **這是讀到的條款事實，不是法律意見**，同 #55 (f)。系統程式庫的判定屬條款文義套用，正式釋出前仍待具開源授權經驗者複核。
4. **只在一台 Windows 11 ＋ Python 3.12.10 上量過**，換平台夾帶的元件組合會不同。
5. **本 spike 不涵蓋 Qt 側**。shiboken6 的 Qt binding 執行期授權沿用 PySide6 的 GPL-3.0-only 臂結論（Sprint 98 定案），本次未重查。

## 可重現

```bash
python spikes/spike22-bundled-binary-terms/probe_harfbuzz.py
python spikes/spike21-packaging/probe_wheel_build.py
python spikes/spike22-bundled-binary-terms/probe_msvc_runtime.py
```

第二支先跑是因為第三支的第 5 節要讀 wheel 內容；未建 wheel 時該節會如實報「尚未建置」，不會假裝有結論。
