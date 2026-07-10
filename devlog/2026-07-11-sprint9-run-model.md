# Sprint #9（2026-07-11）字元樣式 run 模型（document@2）＋md 行內強調，已完成

**範圍**：文件模型升級 document@2（段內 run＋字元樣式參照）、引擎與雙後端（PNG／PDF）per-cell 字元樣式覆寫、md 行內強調解析（**strong**／*em* → md_inline_mapping）、抽取工具把真書明體 W9 強調 span 標記為 **…**、控制字元源頭剔除。

**完成**：
- ✅ document@2 [實作]：Run（text＋char_style）；Paragraph 正規化不變式（text ＝ runs 串接，__post_init__ 保證）；@1 照載、@1＋runs 明確拒絕；save 一律寫 @2（單一無樣式 run 用 text 捷徑）；unknown_char_style_refs 邊界驗證。
- ✅ 引擎 run 支援 [實作]：Cell 帶 char_style；tokenize 標注；cells_from_runs（run 內正規化、拉丁串不跨 run 合併）；斷行重構為 _break_cells（break_paragraph 公開 API 不變）；ParagraphSpec.runs。禁則檢查跨 run 邊界照常生效（單元測試釘住）。
- ✅ 雙後端 per-cell 覆寫 [實作]：render 與 pdf_writer 對 cell.char_style 解析字元樣式（字型＋級數），字槽網格仍依段落樣式（InDesign 慣例：行內樣式不改網格）；layout 快速失敗驗證未知字元樣式。
- ✅ md 行內強調 [實作]：inline_runs（**strong**／*em*，相鄰同樣式合併、未閉合保留字面、v1 不嵌套）；模版新增 md_inline_mapping（strong／em → 內文強調-明體W9，em v1 同映）；CLI import-md 接上。
- ✅ 抽取工具強調標記 [實作]：body 欄內 DFMingStd-W9 span 包 **…**（欄內閉合、跨欄各自成對）；控制字元（Cc）於 page_chars 剔除並列計數（不沉默）。

**測試成長**：83 → 96（+13：document@2 5、engine 2、md 行內 3、layout 未知字元樣式 1、render 字型切換 1、pdf 嵌入 1），0 失敗 0 退步。

**驗證**：
- typecheck：python -m py_compile spikes/spike1-vertical-core/\*.py cjkfolio/\*.py tools/\*.py → EXIT_CODE=0
- test：96 passed / 0 failed（python -m pytest spikes tests -q）
- 真實素材驗收（R5）：重抽第一章 md（79 段 5,487 字、控制字元 7 筆剔除列報、強調 8 對標記）→ import-md 產出 document@2（強調 run：段 21 整句「過度的擁有，也會讓人喘不過氣。」＋段 78 發言標籤「廖：」「鄧：」7 處）→ 雙後端重排 23 頁、禁則 0 違規。Read 目檢 out/chapter1-md/pdf-render-strong.png（PDF 經 PyMuPDF 渲染，版面頁 6／書頁 25）與 page-006.png（PNG 後端同頁）：強調句以宋 Heavy 明顯加重、行中無縫接續、字槽對齊不亂，兩後端視覺一致。PDF Heavy 子集 11 → 26 字形（強調字進場）。
- 除錯紀錄：測試三筆失敗（@1＋runs 被 schema 守門拒絕）為 make_doc 寫死 @1 所致，升 @2 後全綠；PDF 逐字 Tm 使 get_text 帶換行，跨字搜尋需先剝換行（驗證腳本層，非產品缺陷）。
- 一手發現：第一章對談段的發言標籤「廖：」「鄧：」在原書 PDF 實為 DFMingStd-W9（非 PLAN §1 通則的黑體標籤），抽取如實標為強調；訪談章節（後續章）的黑體標籤樣式維持模版既有定義，屆時另驗。

**代決事項（記入 PLAN §10）**：document@2 形態（正規化不變式、@1 相容、@1 拒 runs）；md_inline_mapping（em v1 同映強調）；run 級數不改字槽網格；抽取工具 W9 span → ** 標記。

**落差登記**：無新增（md 嵌套標記不支援屬 v1 設計範圍，入 CHANGELOG 已知限制；GAPS #14 補記控制字元源頭剔除）。

**下個 Sprint 預定範圍**：PDF/X-1a 收尾片（OutputIntent＋XMP／GTS_PDFXVersion＋Trapped＋veraPDF 或 Acrobat preflight 驗證，關 GAPS #15，Phase 1 DoD 關鍵路徑），或齊行與約物擠壓（GAPS #9，排版品質）；建議先 X-1a 收尾（DoD 路徑短、風險集中在 ICC 描述檔取得）。鏡像依書頁號（#16）、發言人標籤自動指派（訪談章）列後。
