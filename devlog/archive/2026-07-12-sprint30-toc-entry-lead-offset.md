# Sprint #30（2026-07-12）目錄章名條目 inline 偏移＋Gate 4 出血座標框勘正，已完成

**範圍**：延續引擎 pt 精度模型（Sprint 29 `lead_offset_pt`）第二軸「目錄章名條目」。
交接兩件：(1) 接 `lead_offset_pt` 進 layout `_toc_marks` 與 `_rule_breaks`（Sprint 29 刻意
延後，本 sprint 正題）；(2) 以 pt 偏移貼真書章名首字墨頂（GAPS #13 (b) 已知整數槽差）。
honest-planning R1 證據先行、R8 正確性優先（Gate 4 抽驗發現既有比對口徑錯配，先勘正再定值）。

**機制與勘正**：
- Sprint 29 的 lead_offset_pt 只套直排 body；目錄條目 body 偏移須同步引導線起點
  （`title_end` → `leader_y0`）與穿線判定（`rule_break` 的 `line_top`），否則條目下移但引導線
  起點／穿線與否失步。兩後端 render／pdf_writer 消費同一 `TocEntryMark`／`RuleBreak`，改
  layout 兩式即自動 parity；頁碼底錨 `page_no_top`／線終 `leader_y1` 為頁面固定列不隨條目。
- **Gate 4 抽驗發現**：交接目標 (b)「墨頂 137.42 vs 真書 135.15、差 +2.27」為出血座標框
  錯配（GAPS #21／Sprint 25 同型）。三段一手複核：
  1. 真書 PDF 本機實測無出血（media ＝ trim ＝ bleed，頂部 padding 0.000pt），故真書墨頂
     135.15 為 trim 頂算起。
  2. model export PDF 有 3mm 出血（media 154×216），PyMuPDF span top 137.42（與 Sprint 24
     記錄吻合 0.005pt）含出血 8.504pt。
  3. Sprint 24 拿 model 含出血 137.42 直接比真書無出血 135.15，未扣出血，得假差 +2.27。
     數學自洽：+2.27 ＝ 真實 trim 差（-6.24）＋ 出血（8.504）。
  扣出血後同口徑（PyMuPDF span top，trim）model 128.91 vs 真書 135.15，正確 `lead_offset_pt`
  ＝ **+6.24（下移）**，方向與原記 -2.27（上移）相反。+6.24 使 model trim 墨頂精確 135.15，
  正是交接授權「絕對值比對真書 135.15」的正確達成（-2.27 僅在錯誤 media 口徑下貼合）。

**完成**：
- ✅ cjkfolio/layout.py [實作]：`_toc_marks` 的 `title_end` ＋ `pl.lead_offset_pt`（引導線起點
  跟隨條目 body）、`_rule_breaks` 的 `line_top` ＋ `pl.lead_offset_pt`（穿線判定跟隨 body 實位）。
- ✅ templates/neizai-zhengli.json [實作]：目錄-篇章條目 `lead_offset_pt` 6.24（墨頂扣出血貼
  真書 135.15）；note 記 Gate 4 出血勘正，移除舊「框頂 132.12 vs 135.15、-3.03」混口徑記述。
- ✅ tests/test_lead_offset.py [實作]：機制（font-free：leader_y0 同移、頁碼底錨不動、穿線
  同步）＋絕對值（PyMuPDF span top 扣出血 → trim 貼 135.15）＋兩後端兩渲染差分（6.24）。
  既有 3 toc/rule 測試（test_layout_render.py）預期式同步加 `lead_offset_pt`。
- ✅ 測試 209 → 214（+5）。

**測試成長**：209 → 214（+5：目錄機制 2＋真書絕對值 1＋PDF/PNG 兩渲染差分 2），0 失敗 0 退步。

**驗證**：
- typecheck：EXIT_CODE=0；test：214 passed / 0 failed
- 真實素材驗收（R5，samples/toc.doc.json 自擬，紅線不取真書文字）：
  - render PNG（out/toc30/page-001.png，300dpi）**Read 親驗**：部名「把日子放回原位」明體
    粗大標穿線、虛線在部名處斷開兩側續畫、4 章名條目黑體縮退在虛線下、引導線接直排頁碼
    17／63／109／155 底對齊、黑體條目與明體部名字族區隔，與目錄設計語言一致，無異常。
  - export PDF preflight **12/12** 全綠、render violations 空。
  - **Gate 4 閉環抽驗**：條目首字墨頂（PyMuPDF span top 扣出血 → trim）＝ **135.15pt** 精確
    貼真書；真書頁盒 probe 確證無出血（padding 0.000pt），坐實 Sprint 24 未扣出血之錯配。
- 除錯紀錄：驗收腳本初版 `min(tops)` 誤取部名（明 16pt 穿線在天頭）而非條目，過濾改 font
  含 Sans（條目黑體）後得條目墨頂 135.15；產品無誤（測試 `_toc_doc` 純條目已綠），僅驗收
  腳本量測範圍 bug。

**代決事項（記入 PLAN §10）**：Gate 4 自行勘正 Sprint 24 出血座標框錯配（循 Sprint 26 勘正
Sprint 25 之先例，自行勘正並詳記、不停工）；lead_offset_pt +6.24 為 PyMuPDF 同口徑扣出血
對齊，殘留思源／華康 ascent 度量差（§3.3 已接受，位置偏移無法消除）。另釐清：交接 (a)
「目錄條目縮退 29.93 vs 27.04」為 Sprint 21 舊狀態（head_offset 3、楷 9.5pt），Sprint 24 已
勘誤併入「目錄-篇章條目」（head_offset 2、黑 11.5pt），當前僅此一縮退樣式；(a)(b) 之
lead_offset 需求方向相反（+2.88 vs +6.24），可證非並列兩目標，本 sprint 對單一樣式定案。

**落差登記**：GAPS #13 目錄章名 +2.27pt 子項以 +6.24 出血勘正關閉；殘留字型 ascent 度量差
與 para_gap block 軸誠實記錄。

**下個 Sprint 預定範圍**：para_gap block 軸精度（Sprint 25 個案中標相鄰，需 block 軸 pt 偏移
新機制，別於 inline 軸）；或轉噪音移除軌（measure_*.py 共用模組抽出、test 檔近 800 行分檔）。
Owner 抽檢項累計新增：out/toc30 目錄條目 lead_offset 貼真書 135.15。
