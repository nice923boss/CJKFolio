# CJKFolio 編輯器（Phase 2 骨架）

Phase 2 WYSIWYG 編輯器的真視窗畫布骨架，承 Spike 10（spikes/spike10-canvas-sync/）離屏驗證落為產品碼。技術棧＝PySide6（Qt 6 官方綁定，LGPL；Spike 10 A 級數據，§5.2 Phase 2 開工定案）。

## 執行

**最簡：雙擊 repo 根的 `啟動編輯器.bat`**（自動檢查 PySide6 後開視窗；關視窗即結束；可將 .doc.json 檔拖到 bat 上以開啟指定文件）。

或自 repo 根手動執行（需真視窗環境，有顯示器）：

    python editor/app.py [文件路徑]

預設文件 samples/case-divider.doc.json（C 個案扉頁自擬樣張，非參考書）。

離屏煙霧驗證（無視窗，CI 可跑）：

    python editor/smoke_check.py

## 結構

- **canvas.py**：雙層畫布核心。底圖層＝既有 PNG 渲染後端；互動層＝layout 幾何直接生成透明字格（QGraphicsRectItem，data=(placed_idx, cell_idx)）。互動層座標復用 render 直排 body 同一組幾何函式（與雙後端同源，公式對齊 cjkfolio/render.py::PageRenderer._draw_vertical_body）。`resolve_hit` 把點到的字格反查為文件游標（para_idx／span／text，承 Sprint 18 provenance）。
- **app.py**：真視窗 QMainWindow demo（雙層畫布＋點字格反查游標＋高亮＋IME 測試區）。
- **smoke_check.py**：離屏 Gate-5 驗證（可跑＋雙層建構＋hit-test 100%＋provenance 一致）。

不入 pytest 基線（Sprint 17 決議：GUI 套件不綁核心 `pytest spikes tests`）；驗證走獨立 smoke_check.py。

## 誠實範圍（honest-planning R3）

| 項目 | 狀態 | 驗證 |
| --- | --- | --- |
| 雙層畫布顯示 | [實作] | smoke_check 離屏建構 |
| 點字格 → 文件游標（段／字／樣式） | [實作] | smoke_check hit-test 100%＋provenance 切片一致 |
| IME 輸入區提交插入 reflow（組字→Enter→於游標插入→全文重排→游標跟隨） | [實作] | Sprint 41，smoke_check C5 離屏驗（插「測試」→reflow 0 違規、游標跟到「試」）；真視窗手感待 Owner |
| IME 直排輸入是否順暢、視覺對位 | 待 Owner | 真視窗鍵盤實測（離屏測不了，GAPS #19） |
| 直排畫布內嵌 IME 即點即打、拖曳／範圍選取 | [Shell] | Phase 2 編輯 UI 後續工程；本 demo 以輸入區＋Enter 代替畫布內嵌 IME |

## Owner 實測協議（GAPS #19）

1. 雙擊 repo 根的 `啟動編輯器.bat`（或 `python editor/app.py`）開視窗。
2. 目檢頁面直排字形正常、點一個內文字格看高亮框是否框住字（視覺對位）。
3. 下方 IME 輸入區用注音／倉頡／拼音組字，確認候選字窗與組字正常（§5.2 選 Qt 的關鍵理由＝IME 一等公民，本步為其實測）。
4. 按 Enter 提交：確認頁面即時 reflow、游標跟到剛插入的字（Sprint 41 編輯回路的真視窗手感）。
5. 回報：IME 組字是否順、對位是否準、reflow 是否即時。若挑出問題，回 Phase 2 畫布架構修正。

製作者：黃政文
