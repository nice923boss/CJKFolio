# Sprint #23（2026-07-11）E 序文版頁型（三頁互證量測），已完成

**範圍**：GAPS #13 B〜G 頁型系列：E-序文版（Sprint 22 探測起頭）。
honest-planning R6 pre-mortem（spikes/spike16-preface-master/premortem.md）；
R2 判定不需新 PoC spike（既有機制參數化，同 Sprint 19/20 模式）。

**一手量測（A 級，p004/p007/p009 三頁互證完全同值）**：
- 版心**承 A 由推定升級為驗證**：內文天頭 92.09pt=32.49mm、行距 23.0
  （行軸序列）、字距 12.08（字頂序列，含一處 11.97 齊行微調）、首行縮排
  2 字（116.47=92.09+2×12.08，誤差 0.22pt）。
- 標題＝**NotoSansCJKtc-Medium 12.9pt**（slot 0、行軸 342.16、首字頂 93.65）；
  內文自 slot 5 起（行軸差 114.76pt=4.99 槽）＝標題段後 4 空槽。
- **樣式勘誤**：原「推薦序大標-楷書W5 16.3pt」為 scan_reference_styles
  誤把署名行長橫「─」（楷 W5 16.3 單字元）當標題；改名「推薦序大標-黑體」
  （12.9pt；個案大標 17.9pt 為不同級不共用）。
- 頁腳承 A：p004 頁碼 x 36.85pt 與 A outer_offset 36.8 精確吻合；序文
  偶頁書眉「內在整理」x 741.9 同 A。
- 不建模（自由手排證據）：欄標「推薦序」黑 W5 9pt＝標題行右 16.2pt 肩位
  （非 23 網格）；署名行 y 頂（257.16/299.98/404.91）與 y 底
  （387.79/360.68/477.26）皆隨頁變動（頂錨底錨假說皆否定）。

**完成**：
- ✅ 模版 [實作]：樣式勘誤改名＋para_gap_slots 4；E evidence 全量測數據；
  E footer 承 A。模版 JSON 經 json.dump 統一重排（indent=1），內容等價。
- ✅ 樣張 [實作]：samples/preface.doc.json（自擬標題＋內文兩段，紅線不取
  真書文字）。
- ✅ 測試 [實作]：E 主版量測常數＋標題樣式＋樣張幾何（TDD：RED 親證
  2 failed 後 GREEN）。

**測試成長**：186 → 188（+2）。0 失敗、0 退步。

**驗證**：
- typecheck：EXIT_CODE=0；test：188 passed / 0 failed
- 真實素材驗收（R5，樣張自擬）：
  - render PNG（out/preface23/page-001.png，300dpi，--first-page 7）
    **Read 親驗**：標題右起 slot 0、內文隔 4 槽縮排 2 字、頁碼書口左下
    （書頁 7 奇＝左頁 ✓），與真書 p004 設計語言一致。
  - export PDF preflight **12/12**。
  - **閉環獨立抽驗（Gate 4）**：PyMuPDF 抽標題行軸中心 341.27pt，與 v1
    推導 341.26 重合（0.01pt）；真書 342.16 差 0.9pt（premortem 預記的
    inner 承 A 0.32mm 級差異，誠實入 GAPS）。

**代決事項（記入 PLAN §10）**：樣式勘誤即改（名實相符優先）；欄標肩位與
署名行不建模；模版 JSON 統一重排。

**落差登記**：GAPS #13 E 序文版量測完成＋三項已知差異。

**下個 Sprint 預定範圍**：候選：(a) 抽取工具目錄模式；(b) 目錄「章名條目
黑 W5」樣式層；(c) C 個案扉頁／G 圖文版量測；(d) TW-Kai 入庫（**需下載，
須 Owner 同意**）。Owner 抽檢項累計：Spike 1 對比圖（#10）、斷行逐行
一致率、Spike 10 對位樣張、out/cip19 與 p178、out/part20 與真書部扉、
out/toc21 與 p003、out/ch1-s22 側別、**out/preface23 與 p004 並排比對**。
