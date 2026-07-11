# Sprint #27（2026-07-12）G-圖文版主版：頁型骨架（§4.2 主版 7 種完備），已完成

**範圍**：GAPS #13 B〜G 頁型系列最後一種：G-圖文版主版。照 Sprint 20/25 一手量測模式：
量參考書圖文版頁 → G evidence 由推定升級一手量測 → 自擬樣張 render/export/preflight →
TDD 加測試、兩後端同源。R1 證據先行、R3 shell 標記、R5 真實素材量測。

**頁型認知（A 級量測＋渲染目視）**：
- 圖文版頁＝整理術 before/after 頁型：房名黑體標題（如「廚房」）＋前後對照兩張灰階
  照片（§1「78 張灰階」）填版心＋辰宇落雁體 15.9pt 手寫圖說（「整理前／整理後」）。
- measure_figure_page.py 分類濾除兩種頁型：Type 1 全頁圖文版（G，img_frac≳0.2＋body≈0
  ＋辰宇圖說，32 頁）；Type 2 內文內嵌小圖（非 G，img_frac≈0.1＋body≳60，Phase 4 圖文繞排，
  11 頁排除）。
- 圖框保留區橫向承 A 版心（鏡像：R 頁 x0=72.51／x1=360.0、L 頁 59.53／347.02，照片略溢
  1〜4pt）、縱向雙照片區 top 107.04／bottom 467.62pt（一致值）；辰宇圖說 15.92pt（31 span
  同值），與既有字元樣式裝飾大字-辰宇落雁體 15.9pt 同構。
- 與 B-部扉同型（Sprint 15/20）：照片本體＋房名黑體＋辰宇自由圖說＋裝飾括號＝手繪美術
  （§8 不生成）＋Phase 2 圖片置入；Phase 1 只做頁型骨架（版心＋圖框保留區＋圖說樣式）。

**完成**：
- ✅ tools/measure_figure_page.py [實作]：分類量測（Type 1/2）＋只聚合 Type 1 圖框保留區
  與辰宇圖說幾何（輸出 assets/reference 本機不入 repo）。
- ✅ FigureSpec＋MasterPage.figure [實作]（styles）：圖框保留區主版欄位（photo-slot，縱向
  top/bottom＋佔位框 dash/cmyk；未知 kind／bottom≤top／壞 cmyk 快速失敗）。
- ✅ figure_slot_rect／figure_slot_edges [實作]（primitives）：承版心鏡像幾何＋四邊虛線
  （reuse 既有 dashed-line 路徑）。
- ✅ render._draw_figure／pdf_writer._figure [實作]：淡虛線佔位框（gate vertical＋master.figure
  ＋page.placed），render PIL 灰值分段／pdf `d` dash＋K 描邊兩後端同源。
- ✅ 段落樣式「圖說-辰宇落雁」15.9pt＋samples/figure-page.doc.json [實作]：自擬圖說標籤
  （改造前／改造後，紅線不取真書文字與照片）。
- ✅ 模版 G evidence [實作]：推定 → 一手驗證（版心承 A＋圖框保留區＋圖說 15.9pt），加 figure。
- ✅ tests [實作]：test_primitives +4（figure_slot_rect 鏡像 L/R＋四邊虛線）、test_styles +7
  （FigureSpec 載入/5 驗證錯誤＋圖說樣式＋計數 15→16）、test_pdf_writer +3（dash 描邊
  d/m/l/S/K30 在 BT 前無 rg/RG＋四邊 m/l 兩後端 parity abs≤0.3pt＋preflight 12/12）。

**測試成長**：191 → 205（+14：primitives +4、styles +7、pdf_writer +3）。0 失敗、0 退步。

**驗證**：
- typecheck：EXIT_CODE=0；test：205 passed / 0 failed
- 真實素材量測（R5）：measure_figure_page.py 實跑參考書 179 頁，Type 1 圖文版 32 頁互證
  （圖框 top 107.04／bottom 467.62 一致、辰宇 15.92pt 31 span 同值）；渲染目視（recon-47
  廚房 before/after 頁，out/ 本機不入 repo）確認頁型認知。
- 自擬樣張端到端（Gate 1/4）：render out/g/page-001.png（Read 親驗：虛線圖框保留區填版心
  ＋辰宇圖說右→左）、export out/g.pdf（辰宇嵌 4 字形、preflight 12/12 誠實聲明 v1 尚無影像
  置入）、PyMuPDF 獨立渲染 out/g-pdf.png 與 PNG 幾何一致＋抽 4 dashed 邊扣出血後＝
  figure_slot_rect（trim x0=59.53／x1=347.02／top=107.04／bottom=467.62，兩後端同源）。
- 破折號掃描：所有異動檔（cjkfolio/*.py、模版、樣張、tools、tests）0 破折號。

**下個 Sprint 預定範圍**：§4.2 主版 7 種（A〜G）已於 Phase 1 骨架層完備。次選：抽取工具
目錄模式（measure_*.py 共用 HALF_W／PT_PER_MM／_spans／半頁判定／JSON 輸出樣板抽出 tools
共用模組）；或 Phase 1 DoD 其他項（如本書真實文字全章匯出完稿 PDF/X-1a 綜合抽檢）。
tests/test_pdf_writer.py 791 行、test_layout_render.py 792 行皆近 800 上限，後續 PDF／layout
測試前需先評估分檔。Owner 抽檢項：out/g/page-001.png 圖框保留區佔位框（Phase 1 骨架導引，
Phase 2 照片置入取代、不留框線）。
