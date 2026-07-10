# Sprint #3（2026-07-10）Spike 2a Vivliostyle 輸出後端驗證＋Spike 3 前半，已完成

**範圍**：Spike 2a（Vivliostyle 直排 PDF：品質、幾何、字型嵌入、preflight）；順做 Spike 3 前半（全書級編譯時間）。

**完成**：

- ✅ 環境與安裝 [實作]：Node 24.13、@vivliostyle/cli 635 packages（40 秒，符合 PLAN「npm 分鐘級」）。除錯紀錄：首跑 spawn UNKNOWN，根因為 puppeteer 快取無瀏覽器（環境假信號，非程式碼問題）；改 --executable-browser 指向系統 Chrome 解決，入決議紀錄。
- ✅ 直排樣本 sample.html [實作]：自擬文字＋公有領域〈桃花源記〉（可散布，版權紅線合規）。A5＋bleed 3mm＋marks、版心 32.5/13/25mm、PMingLiU 11.5pt／行距 2（23pt）、line-break: strict、text-combine-upright 縱中橫、@bottom-center 頁碼。
- ✅ 組版與 preflight [實作]：2 頁 9.9 秒。**pdffonts 全綠：4 字型全部 emb=yes、sub=yes、uni=yes，無 Type3**。pymupdf 驗：TrimBox 148.0×210.0mm 精確、BleedBox 154.0×216.0mm、MediaBox 180×242（含裁切標記）、**Catalog /Direction /R2L（右翻頁序寫入 PDF）**。
- ✅ 目檢（Read 兩頁渲染）[實作]：直排右至左、vert 字形、句逗置中、行首行尾禁則掃描 0 違規、「12」「88」縱中橫直立、HarfBuzz／Vivliostyle 拉丁串旋轉 90 度、楷體引文縮排。**發現並修復一缺陷：@page margin box 繼承 vertical-rl 使頁碼被直排，補 writing-mode: horizontal-tb 後重組版驗證通過**（技術發現入 PLAN 決議紀錄）。
- ✅ Spike 3 前半 [實作]：gen_long_sample.py 產 96 輪長文件，**192 頁編譯 26.0 秒（約 7.4 頁/秒）**，抽檢第 190 頁排版與頁碼正常。結論：Vivliostyle 當匯出路徑的全書時間可接受；互動即時重排仍靠自製引擎（架構不變）。

**測試成長**：15 → 15（本 Sprint 為輸出後端驗證，無新增單元測試；引擎測試 0 退步），0 失敗。

**驗證**：
- typecheck：python -m py_compile spikes 全部 .py，EXIT_CODE=0
- test：15 passed / 0 failed
- 真實素材驗收（R5）：樣本為自擬＋公有領域文本（Spike 2 目標是後端能力，不需參考書文字）；Read 親驗 spike2a_p1.png、spike2a_p2.png、spike3_p190.png 三頁渲染與 pdffonts／preflight_check.py 輸出。
- 未驗項（誠實標示）：CMYK／PDF-X 轉換（無 Ghostscript，GAPS #11）；AGPL 授權影響（Spike 4 未開始）；spike 引擎單章重排延遲（Spike 3 後半）。

**留證**：
- 時戳：2026-07-10
- 樣本：spikes/spike2-output-backend/out/{spike2a-sample.pdf, spike2a_p1.png, spike2a_p2.png, spike3-long.pdf, spike3_p190.png}（自擬＋公有領域，本機保存）
- commit：本篇提交後回填

**下個 Sprint 預定範圍**：Spike 3 後半（自製引擎單章重排延遲量測）＋ Spike 4 授權桌面研究（AGPL-3.0 對散布／SaaS 的約束與進程隔離方案，盒 2 天）＋ Spike 5 真章重測（endpoint 可達才做）。完成後做 Phase 0 閘門判定。
