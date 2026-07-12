# Sprint #39（2026-07-12）Phase 1 骨架收尾定案（honest review＋Known Limitations 彙整，Owner 定案收尾轉 Phase 2），已完成

**範圍**：Sprint 38 完成 C 個案扉頁資訊區欄位卡片，「最複雜架構先做」線程收束，Phase 1 已無需新引擎機制的大型建模。Owner 經 AskUserQuestion 於三選項（收尾轉 Phase 2／續建小型變體／建目錄摘要層）定案**收尾轉 Phase 2**。本 Sprint 為 [Doc] 收尾整併：honest review 確認 Phase 1 骨架完成、彙整 Known Limitations、正式關 Phase 1、標記 Owner-only sign-off 待辦。無程式碼／測試變更。

**honest review（A 級實查，非橡皮圖章）**：
1. **模版實查**：`grep` templates/neizai-zhengli.json 命中 A〜G 七 master id（A-內文版／B-部扉／C-個案扉頁／D-目錄／E-序文版／F-版權頁／G-圖文版）；`json.load` 計數段落樣式 18、字元樣式 9（與 Sprint 37 段落樣式 17→18、§4.2 字元樣式 9 種一致）。
2. **引擎能力**：直排版面（禁則／約物擠壓／齊行擠入／縱中橫／橫排／依書頁號鏡像）＋自寫 PDF/X-1a:2001 匯出（OutputIntent／XMP／GTS 兩鍵／子集嵌入）＋機械 preflight 12 規則＋txt／md 匯入＋兩後端（PNG／PDF）幾何同源，皆有前 Sprint A 級一手驗證與現存測試涵蓋。
3. **基線**：`pytest spikes tests` 218 passed / 0 failed、typecheck（py_compile spikes／cjkfolio／tools）EXIT=0。
4. **結論**：Phase 1 §6 骨架機制級 DoD 達成。

**完成**：
- ✅ 開源CJK排版編輯器-PLAN.md [Doc]：§6 新增「Phase 1 收尾判定（Sprint 39）」子節（鏡像 Phase 0 閘門判定體例，含機制清單／Owner sign-off 待辦／剩項四類處置／下個 Sprint）；§10 新增 Sprint 39 決議列。
- ✅ GAPS.md [Doc]：新增 #22（Phase 1 收尾 Known Limitations 彙整，甲 細項延後／乙 需新機制／丙 §8 美術不生成／丁 後續 Phase）、#23（斷行逐行一致率比對待 Owner sign-off）。
- ✅ CHANGELOG.md [Doc]：v0.34.0 條目。
- ✅ devlog/2026-07-12-sprint39-phase1-closure.md [Doc]：本檔。

**測試成長**：218 → 218（[Doc] Sprint 無程式碼／測試變更）。0 失敗 0 退步。

**驗證**：
- typecheck（py_compile spikes／cjkfolio／tools）EXIT=0；test 218 passed / 0 failed（[Doc] Sprint，基線不動）。
- honest review 獨立方法：模版樣式數與主版 id 以 `grep`＋`json.load` 實查（非引用宣稱）；基線以實跑 pytest／py_compile 確認。
- 繁中標點：grep 本 Sprint 改動檔（PLAN／GAPS／CHANGELOG／devlog）無破折號殘留。

**正式 sign-off 待 Owner（R5 人類抽檢，執行工程師不代行）**：
- GAPS #10：Spike 1 對比圖 spikes/spike1-vertical-core/out/spread_comparison.png 抽檢（Phase 0 正式通過前提）。
- GAPS #23：斷行逐行一致率比對（Phase 1 DoD 一致度抽檢的斷行維度）。
- 排版機制級品質已 A 級驗證且樣張 0 禁則違規，但「無重大排版瑕疵」與「逐行一致率」屬人類品質判斷，執行工程師不代行。

**代決事項（記入 PLAN §10）**：Phase 1 骨架機制級 DoD 達成、收尾轉 Phase 2；剩項全數彙整 GAPS #22 Known Limitations（四類）並登記 #23 斷行 sign-off；均為證據驅動的非紅線收尾決策，git commit 隔離供 Owner 事後檢視。Owner 已於 AskUserQuestion 定案收尾轉 Phase 2。

**落差登記**：GAPS #13 逐項量測審計軌保留（不改寫），本 Sprint 於 #22 彙整轉場前 Known Limitations 清單、#23 formalize 斷行一致率 sign-off（前此散於 Sprint 11〜16 prose、無編號，R7 補齊）。

**下個 Sprint 預定範圍**：Phase 2 開工首項＝Qt 畫布 IME 直排輸入真視窗實測（GAPS #19），§5.2 選 Qt 的關鍵理由（IME 一等公民）本機未實測、§7 Pre-mortem 未退場最大產品風險＝畫布與排版核心同步（僅 Spike 10 初驗）。GAPS #19 註明需真視窗 demo＋Owner 鍵盤實測（Owner-hands-on），執行工程師先備 PySide6 demo 骨架（承 Spike 10 雙層畫布），Owner 到位再實測 IME。
