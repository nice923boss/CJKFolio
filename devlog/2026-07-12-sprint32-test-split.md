# Sprint #32（2026-07-12）替代軌 B：近 800 行測試檔依頁型分檔，已完成

**範圍**：Sprint 31 替代軌 B（Owner 選定）：test_layout_render.py（795 行／39 test）與
test_pdf_writer.py（791 行／35 test）近 800 行上限，依頁型／主題分檔。純測試重組，行為
保持（pytest 總數不變、全綠）。

**做法（依既有慣例，零轉錄風險）**：
- 全 tests/ 既定慣例：各檔自帶 `template` fixture＋ROOT/TEMPLATE/FONT_DIR＋make_ helper
  （非共享 conftest；8 檔各自持有 template fixture）。分檔循此，新檔自帶 fixture／helper，
  不引入 conftest（避免改動全檔共享模型＝逾分檔範圍）。
- 抽出「主版向量裝飾與目錄頁型」連續塊（CIP 細框 Sprint 14、目錄天頭虛線 Sprint 15、條目
  頁碼引導線 Sprint 16、篇名嵌線斷開 Sprint 21，pdf 另含 G 圖文佔位框 Sprint 27）。此塊
  自帶 make_toc_doc／make_toc_doc_paged／make_toc_doc_with_part（＋pdf 的 make_figure_doc／
  _frame_re／PT）。
- 零轉錄：測試本體以 sed 逐位元組搬移（`sed -n '497,$p'`／`'472,$p'`），Write 只手寫新檔
  header（imports＋fixture＋跨檔引用的 make_doc／make_cip_doc／BLEED_PT）；核心以 head 截斷。

**完成**：
- ✅ tests/test_render_vectors.py [實作]：自 test_layout_render.py 抽 13 test（CIP 框＋目錄
  虛線／頁碼引導線／嵌線 的 layout＋render）。
- ✅ tests/test_pdf_vectors.py [實作]：自 test_pdf_writer.py 抽 14 test（同上＋G 圖文佔位 export）。
- ✅ test_layout_render.py 795→495 行（26 test）：補 1 行 `PT` 常數（章名條目 layout 測試留
  核心，其 PT 定義隨塊移出故補回）。
- ✅ test_pdf_writer.py 791→469 行（21 test）：移除抽出後未用的
  `from cjkfolio.primitives import cip_frame_rect, toc_rule_line`。
- 分檔後最大測試檔 495 行（皆遠低於 800 上限）。

**測試成長**：214 → 214（39＝26＋13、35＝21＋14 重分佈，無新增／刪除，行為保持）。

**驗證**：
- typecheck（py_compile 全部＋4 測試檔）EXIT=0；test 214 passed / 0 failed（總數不變＝零 test
  遺失或重複，分檔行為保持）。
- import 潔淨：4 檔各 import 皆有 body 使用（grep 計數 ≥2）；兩核心檔無孤兒 import（pdf 核心
  cip_frame_rect／toc_rule_line 抽出後為 0 occurrence，import 行已移除）。
- 紅線：tests/ 4 檔 grep 無 em-dash。

**代決事項（記入 PLAN §10）**：分檔依「主版向量裝飾與目錄頁型」主題（非機械對半），新檔循
tests/ 既有「各檔自帶 fixture」慣例（不建共享 conftest／helper 模組，避免改動全檔共享模型＝
逾分檔範圍；helper 跨新舊檔複製與既有 8 檔各自持有 template fixture 一致）。

**落差登記**：無（純測試重組，不涉產品碼與缺口；行為以 pytest 總數不變＋全綠驗證）。

**下個 Sprint 預定範圍**：引擎 pt 精度模型其他真實目標（須先量測找目標，如橫排 body／新頁型，
避免重蹈 Sprint 31 無目標）；或個案大標 para_gap 整數修正（拆 個案扉專用 vs 內頁 h2 兩樣式，
屬設計變更）；或其他噪音移除軌。
