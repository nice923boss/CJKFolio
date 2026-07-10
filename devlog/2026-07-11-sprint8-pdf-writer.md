# Sprint #8（2026-07-11）PDF 寫出層第一片：單頁完稿＋字型子集嵌入，已完成

**範圍**：自寫 PDF 寫出層（向 Phase 1 DoD 的 PDF/X-1a 推進）：§9 盒框、單 K 文字、六款字型子集嵌入、右翻閱讀方向、CLI export-pdf（--page 單頁完稿）；幾何與 PNG 渲染同源。

**R2 探針（動工前 PoC，兩形態實測）**：
- 成功標準：自組 PDF 能被 PyMuPDF 渲染出正確 vert 字形、pdffonts 全綠（emb/sub/uni、無 Type3）、ToUnicode 抽回原文。
- 形態 A（CFF retain_gids）：可行，但 13 字形子集 raw 258,781 / flate 140,022 bytes（65,535 空槽開銷）。
- 形態 B（CFF 不保留 GID、內容流用原 CID 走 charset）：13 字形 raw 5,234 / flate 4,609 bytes，**小 30 倍**，渲染與抽取結果與 A 一致。前提「思源 CID==GID（ROS=Adobe-Identity-0）」以 fontTools glyph order 實證。
- TTF（粉圓）retain_gids：loca 空槽 Flate 後僅 2,641 bytes，維持最簡形態（CIDToGIDMap /Identity）。
- 定案：CFF 走 B、TTF 走 A（入 PLAN §10）。探針腳本於 session scratchpad（probe_pdf_embed.py／probe_pdf_embed_b.py），其驗證邏輯已固化為 tests/test_pdf_writer.py。

**完成**：
- ✅ cjkfolio/placement.py [實作]：共用字形佈局層（pt 空間、top-down），與 render.py 的 PNG pen 數學同源：直排字槽、縱中橫縮字、旋轉拉丁（順時針 90 度基線幾何）、水平頁腳字條。
- ✅ cjkfolio/pdf_writer.py [實作]：低階 PDF 組裝（物件表＋xref＋Flate）、字型子集嵌入（CIDFontType0C／CIDFontType2、FontDescriptor＋CIDSet＋ToUnicode、子集前綴可重現）、內容流逐字顯式 Tm（旋轉拉丁用 0 -1 1 0 矩陣）、MediaBox 154×216mm／TrimBox 148×210 置中／BleedBox＝MediaBox、DeviceCMYK 單 K92、/Direction /R2L、Info（Title UTF-16BE）。
- ✅ CLI export-pdf [實作]：--page（單頁完稿）／--first-page／--no-footer；回報禁則、字型警告、每款子集字形數與大小。
- ✅ engine.normalize 剝除控制字元（Cc） [實作]：真章素材實測缺陷（見除錯紀錄）。
- ✅ 缺字不沉默 [實作]：gid 0 以 .notdef 輸出並列警告（PDF 端；PNG 端列 GAPS #17）。

**測試成長**：74 → 83（+9：pdf_writer 8〔盒框數學、子集前綴、結構與字型嵌入、單字幾何著墨、頁選擇與頁腳、單 K、橫排拒絕、缺字警告〕、engine 1〔控制字元剝除〕），0 失敗 0 退步。

**驗證**：
- typecheck：python -m py_compile spikes/spike1-vertical-core/\*.py cjkfolio/\*.py tools/\*.py → EXIT_CODE=0
- test：83 passed / 0 failed（python -m pytest spikes tests -q）
- 真實素材驗收（R5）：第一章 md 79 段 → export-pdf 全章 23 頁（383,340 bytes）＋單頁完稿（--page 1），禁則 0 違規；pdffonts 六款全綠（TVEOAI+SourceHanSerifTC-Heavy／HCPQVA+…Regular（834 字形）／QGONIK+SourceHanSansTC-Medium／XIXJJN+…Bold／KNFQVP+jf-openhuninn／MWYKNZ+ChenYuluoyan，emb=yes sub=yes uni=yes、無 Type3）；PyMuPDF（獨立實作，Gate 4）量測 media=436.535×612.283pt、trim=(8.504,8.503,428.031,603.779) 精確，渲染 out/chapter1-md/pdf-render-001/002.png 以 Read 目檢：頁 1 章名 Heavy＋內文＋個案標黑體＋右下頁腳（辰宇書眉＋粉圓頁碼 20）、頁 2 鏡像（頁碼 21 左下、無書眉），與 Sprint 7 PNG 樣張同構圖；文字抽取語序正確（ToUnicode）。
- 除錯紀錄：真章匯出即炸 FontError（glyph 0 非 cidNNNNN）。根因：md 抽取素材在發言人標籤「廖：」「鄧：」後殘留 U+0007（BEL）共 7 處（PyMuPDF 對原書分隔符的抽取殘留），塑形成 .notdef；PNG 路徑一直沉默畫豆腐。修正兩層：engine.normalize 統一剝除 Cc 控制字元（單元測試釘住）；pdf_writer 對真缺字（gid 0）改警告＋.notdef 輸出（單元測試以私用區字元釘住）。GAPS #14 補記、#17 新增。

**代決事項（記入 PLAN §10）**：PDF 寫出層 v1 形態（自寫 PDF 1.4、盒框、單 K92、R2L、逐字 Tm）；字型子集兩形態定案；normalize 剝控制字元與缺字警告。

**落差登記**：GAPS #15（X-1a 剩餘：OutputIntent／XMP 識別／preflight 全綠）、#16（鏡像以版面頁號判定，偶數起頁與真書側別相反，PNG/PDF 一致）、#17（PNG 缺字沉默）。

**下個 Sprint 預定範圍**：字元樣式 run 模型（document@2：段內 run＋字元樣式渲染，md 行內強調對映內文強調-明體W9，發言人標籤樣式為後續受益者），或 PDF/X-1a 收尾片（OutputIntent＋XMP／GTS_PDFXVersion＋veraPDF preflight，關 GAPS #15）；建議先 run 模型（文件模型是多功能前置，X-1a 收尾片依賴 ICC 描述檔選定可與 Owner 抽檢並行）。齊行與約物擠壓（#9）、鏡像依書頁號（#16）列後。
