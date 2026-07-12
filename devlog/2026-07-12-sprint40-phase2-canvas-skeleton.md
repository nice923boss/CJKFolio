# Sprint #40（2026-07-12）Phase 2 開工：PySide6 真視窗畫布骨架（技術棧定案＋點字格反查文件游標），已完成

**範圍**：Phase 1 收尾（Sprint 39）後 Owner 定案進 Phase 2，並於 Phase 2 開工方式三選項（建 PySide6 真視窗 demo 骨架／先做 Owner 抽檢／另定範圍）以 AskUserQuestion 選**建 demo 骨架**。本 Sprint＝Phase 2 開工首項：正式定技術棧＋承 Spike 10 離屏驗證落為真視窗產品碼骨架。

**技術棧定案（§5.2「Phase 2 開工定案」條件成就）**：PySide6（Qt 6 官方綁定、LGPL，Spike 10 A 級數據＝雙層畫布回路 37ms、hit 214/214、5,361 item 建立 52ms）。畫布語言 Python，與 Phase 1 管線同語言。

**架構（承 Spike 10，落為 editor/ 產品套件）**：
- 底圖層＝既有 PNG 渲染後端（QGraphicsPixmapItem z=0）；互動層＝layout 幾何直接生成透明字格（QGraphicsRectItem z=1，data=(placed_idx, cell_idx)）。
- 互動層座標**復用 render 直排 body 同一組幾何函式**（line_axis_x_pt／style_advance_pt／line_justified_advance／lead_offset_pt），公式逐項對齊 cjkfolio/render.py::PageRenderer._draw_vertical_body，與雙後端同源紀律一致，不另立幾何。
- resolve_hit 承 Sprint 18 provenance（Cell.span／PlacedLine.para_idx）把點到的字格反查為文件游標（para_idx／span／text）＝Spike 10 顯式暴露的「點字格 → 文件游標」最後一躍。
- editor/ **不入 pytest 基線**（守 Sprint 17：GUI 套件不綁核心 `pytest spikes tests`，避免基線硬依賴 PySide6），驗證走獨立 smoke_check.py。
- demo 文件用 samples/case-divider（自擬 C 個案扉頁，非參考書＝紅線）。

**完成**：
- ✅ editor/canvas.py [實作]：雙層畫布核心（pil_to_qimage／iter_cell_rects／build_page_scene／resolve_hit／CellHit）。
- ✅ editor/app.py [實作]：真視窗 QMainWindow demo（雙層畫布顯示＋點字格反查游標＋高亮＋IME 測試區＋Owner 實測說明對話框＋製作者標示）。
- ✅ editor/smoke_check.py [實作]：離屏 Gate-5 驗證（C1/C2 雙層建構、C3 hit-test 100%、C4 provenance 一致）。
- ✅ editor/README.md [Doc]：執行方式＋誠實範圍表＋Owner IME 實測協議。

**測試成長**：核心基線 218 → 218（editor/ 不入基線，守 Sprint 17；驗證走 smoke_check.py）。0 失敗 0 退步。

**驗證**：
- 離屏 smoke_check（`QT_QPA_PLATFORM=offscreen python editor/smoke_check.py`）：samples/case-divider 雙層畫布建構、hit-test **48/48** 全對、48 cjk 字格 provenance span 切片＝cell.text；樣本 段0 字(0,1)＝「案」樣式 個案欄標-黑W7。EXIT=0。
- app 離屏建構（offscreen 建 EditorWindow＋show）：模擬點選 段5 字(12,13)＝「。」（provenance 讀出正確）＋IME 回呼＋高亮皆驗，無接線錯誤。
- 核心基線 `pytest spikes tests` 218 passed／0 failed（editor/ 未被收集，守 Sprint 17）；typecheck（py_compile spikes／cjkfolio／tools）EXIT=0；editor/ 三 .py 亦 py_compile 全綠。
- 獨立方法：smoke_check（幾何反查＋provenance 切片）與 render 底圖（既有後端）不同路徑；hit-test 用 scene.itemAt 反查 layout 幾何鍵，與 iter_cell_rects 生成互證。
- 繁中標點：grep editor/ 與本 Sprint 改動檔（PLAN／GAPS／CHANGELOG／devlog）無破折號殘留。

**代決事項（記入 PLAN §10）**：技術棧正式定案 PySide6（Spike 10 A 級證據＋§5.2 條件成就）；Phase 2 畫布骨架落 editor/ 套件、不綁核心基線；demo 用自擬樣張守紅線。屬 Owner 已 AskUserQuestion 定案的方向，證據驅動實作。

**落差登記（honest-planning R3／R5）**：GAPS #19 由「Spike 10 未驗 IME」更新為「真視窗骨架已建（Sprint 40），仍待 Owner 鍵盤實測 IME 直排輸入與視覺對位」。誠實邊界：**[實作]**（離屏驗）＝雙層畫布顯示＋點字格反查游標；**[Shell]／待 Owner**（離屏測不了）＝真視窗視覺對位＋IME 直排輸入鍵盤實測；直排畫布內嵌 IME 編輯（打字→游標插入→reflow）與拖曳／選取 UI 為 Phase 2 編輯引擎後續工程，本骨架僅示範「IME 組字 → 已知游標目標」不變更文件、不 reflow。

**下個 Sprint 預定範圍**：待 Owner `python editor/app.py` 真視窗鍵盤實測 IME 直排輸入與視覺對位（GAPS #19 實測協議見 editor/README.md）。回報順暢後進 Phase 2 編輯引擎（游標插入 → 局部 reflow → 畫布更新），或依 Owner 挑出的問題回頭修畫布架構。
