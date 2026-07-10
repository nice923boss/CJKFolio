# Spike 4：Vivliostyle AGPL-3.0 授權影響分析（桌面研究）

> 2026-07-10。證據等級 B（官方文件＋一手引用）。**本報告非法律意見**，正式散布前應請律師覆核（見殘餘風險）。

## 一手證據

1. **元件授權盤點**
   - Vivliostyle Core（vivliostyle.js）：AGPL-3.0。官方 FAQ：「Vivliostyle uses AGPLv3 (GNU Affero General Public License, version 3) as its open source license.」（vivliostyle.org/faq）
   - **@vivliostyle/cli v11.0.4：license 欄位 "AGPL-3.0"**（raw.githubusercontent.com/vivliostyle/vivliostyle-cli/main/package.json，2026-07-10 實查）
   - Vivliostyle Pub：Apache-2.0（官方 FAQ）
2. **官方對「獨立程式並用」的立場**（vivliostyle.org/faq）：
   - 「Vivliostyle Viewer and Vivliostyle Print run as an independent program …, and so can be used in combination with server-side programs or other client-side programs **even if they are proprietary**.」
   - 組織內部使用（含修改）不需公開原始碼；「修改並散布（網站使用亦視為散布）才需公開修改後的 Vivliostyle 原始碼」。
3. **GNU GPL FAQ 的程式邊界準則**（gnu.org/licenses/gpl-faq）：
   - 聚合（aggregate）：同媒體收錄 GPL 與非 GPL 程式為「mere aggregation」，允許。
   - 分界：「pipes、sockets、命令列引數是兩個獨立程式間的通常通訊機制」＝分離程式；同一執行檔、共享位址空間、「交換複雜內部資料結構」＝單一程式。
   - 專有系統互動：「自由與非自由程式在臂長距離（arm's length）通訊、不結合成單一程式」即可（編譯器與核心、編輯器與 shell 之比喻）。
   - AGPL §13：修改版軟體須讓所有網路互動使用者可取得原始碼。

## 對本專案三種產品形態的結論

| 形態 | 判定 | 條件 |
| --- | --- | --- |
| A. 桌面編輯器＋Vivliostyle 為「匯出後端子程序」 | **可行，主體可用自有授權（MIT／Apache）** | 以 CLI 子程序呼叫（命令列引數＋檔案進出＝臂長通訊）；不 import 其模組、不共享位址空間、不交換內部資料結構 |
| B. 散布時隨包附帶 vivliostyle-cli | 可行（mere aggregation） | 附 AGPL-3.0 授權全文＋該元件原始碼取得方式；**更乾淨的做法：不隨包，首次使用時 npm 隨裝（使用者機器自 npm 取得，我方只散布自己的程式碼）** |
| C. 未來 SaaS（雲端組版服務） | 可行 | 未修改 Vivliostyle：對網路使用者提供該元件原始碼連結即可（AGPL §13 義務落在 AGPL 元件本身）；我方伺服器程式維持子程序隔離即不受傳染 |

**禁止事項（觸發 AGPL 傳染）**：把 vivliostyle.js 以模組方式 import 進編輯器或伺服器行程內（in-process 嵌入）；或修改 Vivliostyle 原始碼後散布／上線而不公開修改版。

## 架構決策（回填 PLAN）

- 匯出走「vivliostyle-cli 子程序＋檔案介面」，與 Sprint 3 實測路徑一致（HTML/CSS 進、PDF 出、命令列呼叫），天然符合臂長準則。
- Phase 4 自寫 PDF/X 寫出層（PLAN §5 既定）落地後，Vivliostyle 退為選配後端，授權面依賴進一步降低。
- 若未來需要 in-process 深度整合，改走 MIT 的 SILE 或自製引擎路線（PLAN §3.2 既列），不深度整合 AGPL 元件。

## 殘餘風險（誠實標示）

1. 「CLI 輸出的 PDF 不受 AGPL 約束」屬一般見解（GPL FAQ WhatCaseIsOutputGPL 條目方向），本次未逐字引述；正式釋出前連同整體形態請律師覆核。
2. GPL FAQ 是 FSF 立場非判例法；「臂長」認定在極端整合情境有灰區。本專案採「命令列＋標準檔案格式」的最保守形態，灰區風險低。
3. vivliostyle-cli 相依樹中其他套件授權未逐一盤點（npm ls 可查），隨包散布前需做一次授權清單掃描；採「首次使用隨裝」則無此需求。

## 時間盒

盒 2 天，實際約 0.5 天（桌面研究）。Spike 4 關閉。
