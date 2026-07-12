# Sprint #41（2026-07-12）Phase 2 編輯引擎 reflow 回路（游標插字→重排→反查新游標），已完成

**範圍**：承 Sprint 40 預告的「下個 Sprint＝Phase 2 編輯引擎（游標插入→局部 reflow→畫布更新）」，Owner 常設定案「最複雜架構先做」（§10 Sprint 29/33/34/35/38 反覆援引）下，本 Sprint 做 Phase 2 最複雜、且可離屏驗證的架構核心：編輯回路的「寫」方向（Sprint 40 只有「讀」方向 resolve_hit）。此回路正對應 §7 Pre-mortem 未退場最大產品風險「畫布與排版核心同步／選取錯位」。順帶清 app.py 一個死 import（Owner 授權的程式碼噪音清理）。

**架構定位**：
- 核心 `cjkfolio/editing.py`（純邏輯，**入 pytest 基線**，與 layout/engine 同層，不碰 Qt）＝DocCursor／CellAddress／EditResult＋insert_text／locate_cell／apply_insert。放核心而非 editor/，因編輯回路是文件＋版面邏輯、GUI 無關；比 Sprint 40 的離屏 smoke 更嚴（進真實測試基線）。
- 游標座標系＝段 text（normalize 前原字串）半開座標，與 Cell.span（Sprint 18 provenance）同座標系；插字與反查全在此座標系閉環。locate_cell 是 resolve_hit 的逆（span 反查），兩者構成畫布↔文件游標雙向映射。
- reflow 走 layout_document **全文重排**（非增量近似）：Spike 3 實測純邏輯重排 7.67ms/章、互動級，結論即「分章快取即足、無需增量重排」，全文重排是 Spike 3 認可路徑，不是偷工的近似。
- app.py 接線：IME 輸入區組字→Enter 提交→於點選游標插字→apply_insert 全文 reflow→畫布重繪（新 scene）→游標跟隨新落點高亮。

**honest-planning R6 pre-mortem／R2 判定（無新 spike）**：
- 最可能失敗＝reflow 後游標落錯格（選取錯位）。對策：locate_cell 對版面**每一格** span 反查 round-trip 測試（caret＝格 span 尾→應反查回本格）；apply_insert 游標跟隨測試（插入後 address 切片回原文＝剛插入最後一字）。
- 次風險＝run 邊界插字破壞字元樣式。對策：邊界左偏承接左 run 樣式＋run 內部插字保樣式兩測試。
- 座標風險＝Cc 剝除／表現形位移。緩解：span 為 normalize 前座標（與 Sprint 18 已驗一致），插入 CJK 無 Cc，不觸位移。
- R2：無新外部技術（復用 layout_document＋Cell.span，皆 Spike 10／Sprint 18 A 級已驗），確定性邏輯，失敗機率 < 30%，依先例（Sprint 16/38）判無需新 spike。

**完成**：
- ✅ cjkfolio/editing.py [實作]：insert_text（不可變、run 邊界左偏承接樣式、越界快速失敗）／locate_cell（span 反查、段內命中唯一、查無回 None）／apply_insert（插字→全文 reflow→反查新游標畫布落點）。
- ✅ tests/test_edit_engine.py [實作]：13 測試（插字 7＋run 邊界 2＋locate_cell 2＋apply_insert 2），素材自擬（C 個案扉頁樣式）。
- ✅ editor/app.py [實作]：IME 提交回路接線（returnPressed→_on_ime_commit→apply_insert→_rebuild 重繪→游標跟隨）；_on_ime 拆為 _on_ime_preview（組字預覽）＋_on_ime_commit（Enter 提交）；docstring／說明對話框誠實範圍更新。**噪音清理**：移除未使用的 `QTransform` import。
- ✅ editor/smoke_check.py [實作]：新增 C5 編輯回路離屏驗（選內文字格→提交「測試」→reflow→游標跟隨到「試」），升級 Sprint 40 的一次性 app 探針為永久回歸。

**測試成長**：核心基線 218 → **231**（+13：insert_text 7、run 邊界 2、locate_cell 2、apply_insert 2），0 失敗 0 退步。editor/ 不入基線（守 Sprint 17），驗證走 smoke_check（C1-C4 48/48＋新 C5）。

**驗證**：
- typecheck：`py_compile spikes/spike1 cjkfolio tools` EXIT=0（含新 cjkfolio/editing.py）；editor/ 三檔 py_compile 亦綠。
- test：`pytest spikes tests` **231 passed / 0 failed**（Read terminal 全綠；新檔 13 測試獨立跑亦 13 passed）。
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen python editor/smoke_check.py`）EXIT=0：C1/C2 雙層 48 格、C3 hit-test 48/48、C4 provenance 一致、**C5 編輯回路：段3內文插入「測試」→reflow（1 頁、0 違規），游標跟隨到「試」**。
- 真實素材驗收（R5）：素材＝samples/case-divider.doc.json（自擬 C 個案扉頁，非參考書紅線）；apply_insert 於段 3 內文「三房兩廳，約三十坪的老公寓。」caret 4 插「大大」→ 文件實變「三房兩廳大大，約…」、原文件不變（不可變）、reflow 0 禁則違規、新游標畫布落點 cell.text＝「大」，皆由基線測試 Read 斷言。
- 獨立方法：核心走 pytest 斷言（文件座標＋span 反查），app 接線走 smoke_check（QMainWindow 離屏建構＋模擬提交），兩路徑不同源互證。
- 繁中標點：本 Sprint 改動檔（editing.py／test_edit_engine.py／app.py／smoke_check.py／PLAN／CHANGELOG／GAPS／本 devlog）grep 無破折號殘留。

**代決事項（記入 PLAN §10）**：編輯引擎核心置 cjkfolio/（非 editor/），入 pytest 基線；游標座標系＝段 text 半開座標（與 Cell.span 同）；插字 run 邊界左偏承接左側字元樣式（輸入法慣例）；reflow 全文重排（Spike 3 認可，非增量）；app 以「輸入區＋Enter 提交」代替畫布內嵌 IME（畫布內嵌即點即打為後續 UI 工程）。皆依 Owner「最複雜架構先做」常設定案與證據驅動，屬 Sprint 40 已定 Phase 2 方向內的實作代決。

**落差登記（R3／R5）**：GAPS #19 更新＝編輯回路「打字→插入→reflow→畫布更新」離屏[實作]完成；**仍待 Owner 真視窗鍵盤實測**（離屏測不了）＝IME 直排組字順暢度、候選字窗、提交後 reflow 視覺流暢與對位；[Shell] 後續 UI 工程＝直排畫布內嵌 IME 即點即打（本 demo 以輸入區＋Enter 代替）、拖曳與範圍選取、刪除／選取範圍編輯（v1 只做插入）。

**下個 Sprint 預定範圍**：續 Phase 2 編輯引擎，兩條路線：刪除與選取範圍編輯（delete_range，locate_cell 已備反查）、或畫布內嵌 IME 即點即打（editor/ UI 工程，待 Owner 真視窗 IME 回報）；並行的 Owner-hands-on＝GAPS #19（真視窗 IME 實測）、#10／#23（Phase 0／1 sign-off 抽檢）。
