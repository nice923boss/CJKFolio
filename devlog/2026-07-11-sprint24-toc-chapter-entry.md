# Sprint #24（2026-07-11）目錄章名條目黑 W5（一手量測勘誤），已完成

**範圍**：GAPS #13 目錄頁型最後剩項「章名條目黑 W5 樣式層補充」。
honest-planning R1 證據先行（先量真書條目字型級數再改）、R2 判定不需新
PoC spike（既有機制參數化＋量測工具擴充，同 Sprint 19/21/23 模式）、R8 正確性
優先（楷 W3 vs 黑 W5 需一手實證，非臆測）。

**一手量測（A 級，p002/p003 兩頁互證）**：
- 量測工具擴充：tools/measure_toc_page.py 加 `_entry_columns`（按字中心 x
  聚直排列，標主 CJK 字型／級數／是否帶頁碼），輸出
  assets/reference/toc_measurements.json（本機不入 repo）。
- 目錄三層分明：
  - **篇名**：明體 W7 16pt（DFMingStd-W7），不帶頁碼、穿線（「目錄-部名」已對）。
  - **章名條目**：**黑體 W5 11.5pt（DFHeiStd-W5），全部帶頁碼**，例「Case 2
    整理，重新賦予舊空間新的意義  071」；6 列章名首字 top_y 平均 135.15
    （134.69〜135.60）。
  - **條目摘要**：楷 W3 9.5pt（DFKaiShuStd-W3），不帶頁碼描述文字，top_y ≈ 166。
  - 另【結語】黑 W5 10pt 帶頁碼（次級變體）。
- 穿線「二」「三」單字（篇序一直列僅中間字跨虛線）證實目錄為直排多列。

**勘誤定性（同 Sprint 23 精神）**：Sprint 21 建「目錄-篇章條目」時**幾何錨對
了**（條目錨 135＝章名列 top_y）但**字型誤設成楷 W3 9.5**（那是摘要層字型），
一如 Sprint 23 把「推薦序大標-楷書W5」勘誤為黑體。真書帶頁碼章名實為黑 W5 11.5。

**完成**：
- ✅ 工具 [實作]：measure_toc_page.py entry_columns 直排列分析。
- ✅ 模版 [實作]：「目錄-篇章條目」勘誤 全字庫正楷體 TW-Kai 9.5 →
  思源黑體 TC Medium 11.5（source DFHeiStd-W5）、head_offset 3→2 槽（黑字距
  12.08×2＝24.16pt，章名首字框頂 132.12 貼真書 135.15）。**副效果：解 GAPS #12
  fallback**（改用已入庫思源黑體 Medium，render 不再 fallback TW-Kai）。
- ✅ 測試 [實作]：勘誤斷言（font／weight／size／head_offset／source＋縮退幾何）。
  TDD：RED 親證現值楷 9.5 failed 後 GREEN。
- ✅ 過時註解更新（test_layout_render「條目縮退 3 槽」→ 2 槽）。

**測試成長**：188 → 189（+1）。0 失敗、0 退步。

**驗證**：
- typecheck：EXIT_CODE=0；test：189 passed / 0 failed
- 真實素材驗收（R5，樣張 samples/toc.doc.json 自擬，紅線不取真書文字）：
  - render PNG（out/toc24/page-001.png，300dpi，--first-page 3）**Read 親驗**：
    4 條章名黑體（無襯線、粗細均勻）與部名明體（襯線）字族區隔、引導線＋直立
    頁碼 17／63／109／155 底對齊、章名縮退在虛線下（書頁 3 奇＝左頁 ✓），與真書
    目錄設計語言一致。
  - render 字型日誌：使用 SourceHanSansTC-Medium.otf（章名黑 W5），**無 TW-Kai
    fallback 警告**（僅存部名思源宋體無 bold＝既有 GAPS #12）。
  - export PDF：嵌 SourceHanSansTC-Medium 38 字形；preflight **12/12**。
  - **閉環獨立抽驗（Gate 4）**：PyMuPDF 抽 toc.pdf，4 列章名全
    SourceHanSansTC-Medium、cx 遞減 303.77→234.77（右至左）列距 23pt＝line_pitch；
    章名首字**墨頂** 137.42 vs 真書同口徑（PyMuPDF bbox top）135.15 差 **+2.27pt**
    （整數槽＋思源／華康字框度量差，同 Sprint 20/21 已知差異）；推導 132.12 為
    layout 字框頂（測試釘死），與墨頂差 5.3pt＝思源字框留白，非位置錯誤。

**代決事項（記入 PLAN §10）**：勘誤即改（名實相符優先，同 Sprint 23）；不新增
樣式層（surgical，保留「目錄-篇章條目」key 不破壞 3 測試檔＋樣張引用，語意由楷
摘要層改為黑章名層）；摘要層／【結語】變體／縱向錯落 v1 不建模。

**落差登記**：GAPS #13 目錄章名條目黑 W5 完成＋三項不建模差異。

**下個 Sprint 預定範圍**：候選：(a) 抽取工具目錄模式（從真書目錄抽結構化條目
素材，本機驗證）；(b) C 個案扉頁量測（個案大標＋Case 編號＋資訊列，本機 PDF
可量）；(c) G 圖文版量測（涉圖框置入，較大，可能屬 Phase 2〜3）；(d) TW-Kai
入庫（**需下載，須 Owner 同意**，未同意不做）。Owner 抽檢項累計：Spike 1 對比圖
（#10）、斷行逐行一致率、Spike 10 對位樣張、out/cip19 與 p178、out/part20 與
真書部扉、out/toc21 與 p003、out/ch1-s22 側別、out/preface23 與 p004、
**out/toc24 與 p002/p003 章名條目黑 W5**。
