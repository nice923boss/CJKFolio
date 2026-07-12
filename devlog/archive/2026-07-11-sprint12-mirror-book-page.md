# Sprint #12（2026-07-11）鏡像依書頁號＋PNG 缺字警告，已完成

**範圍**：GAPS #16（頁面鏡像與頁腳奇偶改依書頁號，非版面頁號；render 與 pdf_writer 兩後端同步）、GAPS #17（PNG 渲染後端補缺字 notdef 警告，形態對齊 pdf_writer）。

**完成**：
- ✅ 鏡像依書頁號 [實作]（GAPS #16 關閉）：新增書頁號 `book_number ＝ page.number ＋ first_page − 1`，於 render_document 與 export_pdf 計算後，同時餵入行軸 `line_axis_x_pt`（書口側判定）與頁腳奇偶 `_draw_footer`／`_footer`。舊碼以版面頁號（1 起算流水號）判奇偶，故偶數起頁（如第一章書頁 20）時左右頁側別與真書相反；改依書頁號後 book 20（偶）＝左頁、book 21（奇）＝右頁＋書眉，與真書右翻一致。
- ✅ 向後相容 [實作]：`render_page`／`build_page` 的 `book_number` 預設 None → 退回版面頁號；first_page=1（預設）時 book_number＝版面頁號，行為與 Sprint 11 完全一致。版面頁號續作 PNG 檔名（`page-NNN.png`）與 export-pdf `--page` 選頁鍵，語意不混。
- ✅ PNG 缺字警告 [實作]（GAPS #17 關閉）：`_draw_ttb_char`／`_render_horizontal_strip`（縱中橫與旋轉拉丁與頁腳共用）回報 gid 0 的來源字元；`PageRenderer.notdef_warnings` 去重收集，訊息格式 `字元 'x'（U+XXXX）在 <font> 無字形，以 .notdef 輸出` 與 pdf_writer 逐字一致；`Shaper` 存 `path` 供命名。經 `RenderResult.font_warnings`（併 registry fallback 警告）由 CLI render 列印。
- ✅ 誠實邊界：缺字偵測未統一 placement 層（render 自有塑形迴圈，維持外科手術範圍）；渲染後端統一時再併（記入 §10 決議與 GAPS #17）。

**測試成長**：112 → 115（+3：書頁鏡像 body-axis PNG 後端 1、PDF 後端 1、PNG 缺字警告 1；另翻轉既有 `test_footer_page_number_and_running_title`、`test_export_page_selection_and_footer` 兩奇偶頁測試為書頁號語意，計數不變），0 失敗 0 退步。

**驗證**：
- typecheck：`python -m py_compile spikes/spike1-vertical-core/*.py cjkfolio/*.py tools/*.py` → EXIT_CODE=0
- test：115 passed / 0 failed（`python -m pytest spikes tests -q`）
- 真實素材驗收（R5）：第一章 `assets/reference/chapter1md.doc.json` 以 `--first-page 20` 重排（22 頁）。Read 親驗 out/chapter1-md/：
  - page-001.png（書頁 20，偶＝左頁）：頁碼「20」在左下角（書口左）、無書眉。
  - page-002.png（書頁 21，奇＝右頁）：頁碼「21」在右下角（書口右）＋書眉「內在整理」（辰宇落雁體）。
  - 兩頁左右側別與真書右翻書一致（舊版 page-001 頁碼誤在右下）。
  - chapter1.pdf：preflight 12/12 全綠、pdffonts 六款 emb/sub/uni 全 yes 無 Type3；禁則 0 違規、齊行擠入 10／撐開 1／超容忍 0（與 Sprint 11 一致，鏡像變更不動排版流）。
- 除錯紀錄：無（RED 先行：翻轉 2 測試＋新增 3 測試，5 項如預期失敗〔PDF body-axis 印出 `357.004 > 357.004` 確認舊碼兩起頁行軸相同即為 bug〕；實作後 GREEN 一次通過）。

**代決事項（記入 PLAN §10）**：
- 鏡像與頁腳奇偶依書頁號（＝版面頁號＋first_page−1）；render 與 pdf_writer 共用同一 book_number；first_page=1 向後相容；版面頁號續作檔名與 --page 鍵。
- PNG 缺字不沉默：render 四路徑偵測 gid 0，訊息格式與 pdf_writer 一致；未統一 placement 層（外科手術範圍）。

**落差登記**：#16、#17 關閉。

**下個 Sprint 預定範圍**：橫排（GAPS #13，版權頁-CIP 是全書唯一橫排，渲染器目前明確報錯）；或從參考萃取 Phase 3（樣式面板前置）。斷行逐行一致率 vs 參考書比對仍待 Owner 抽檢（比對工具屬 Phase 3 從參考萃取範圍）。
