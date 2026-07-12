# Sprint #36（2026-07-12）旁注 9pt／Case 編號 15.9pt 兩「掃描見變體」量測確認為真，已完成

**範圍**：候選 A（Owner「最複雜架構先做」下量測釐清，承 Sprint 34 Gate 3 待查標記清查收尾）＝
`旁注-手札圖注` 9pt 與 `Case編號-手寫拉丁` 15.9pt 兩「掃描見變體」待查標記量測釐清（Sprint 34
Gate 3 掃出，templates note 記「（掃描）」未量測）。依 honest-planning R1／R5 先用臨時探針量測
參考書，確認真實變體或掃描誤植，再處置。

**根因（Sprint 36 A 級量測）**：兩路臨時探針量測參考書《內在整理》交印檔（本機，紅線不入 repo）
179 頁，四問交叉驗證（承 Sprint 35 式，避免同源同錯）。**與 Sprint 34（12.9pt）／35（slot 0
13pt）「掃描見變體＝誤植 0 命中」相反，本次兩變體皆真實存在**：
1. **A：HanziPen（華康手札體）全 size 分布**：8.0pt 主體 173 頁（頁腳書眉副標與旁注同級）；
   **9.0pt（raw 8.955）真實變體＝4 頁（PDF 25／60／61／93）34 字**，位置頁面中上部（top 82~338，
   非頁腳 508）＝圖注旁注大一號。note 原記「9pt 變體掃描 4 頁」，頁數精確吻合。
2. **B：Pepita（Case 編號拉丁）全 size 分布**：9.0pt 頁腳主體 153 頁（top 508.3，Sprint 35 確認）；
   **15.9pt（raw 15.92）真實變體＝10 頁（PDF 19／35／53／69／84／98／115／133／144／156）章扉大號**
   （top 86.2、x0 192.7）；**另揭 10.4pt（raw 10.447）目錄 Case 編號 2 頁（PDF 1／2，top~135）**，
   note 原僅記 15.9pt、漏 10.4pt。
3. **C：全書 8.5~9.5pt 級數反查**：HanziPen 9pt 獨立存在（34 字 4 頁），與 Pepita 9pt 頁腳、楷 W3
   9.5pt 目錄、DFHei 9pt 各自分離，非捨入邊界誤判。
4. **D：全書 15~17pt 級數反查**：Pepita 15.9pt（61 字 10 頁）與辰宇落雁 15.9pt（186 字 31 頁圖說／
   裝飾大字）同級不同字型，二者不可混淆。

結論：兩「掃描見變體」待查標記經一手量測確認為**真實變體，非掃描誤植**。至此 Sprint 34 Gate 3
掃出的「掃描見變體」待查標記全數清查完畢（12.9pt、slot 0 13pt 兩誤植 vs 9pt、15.9pt 兩真實）。

**處置（勘正記錄型，同 Sprint 34／35，不建模）**：變體屬美術／自由佈局層（§8 不生成美術；圖注旁注
自由置放、章扉大號 Case 編號為裝飾），Phase 1 無渲染用例（現有樣張未用），建獨立樣式會是 [Shell]
（介面 done、無真實佈局驗收）。故不建模、登記 GAPS #13 後續專項（需 Owner 決定投入）；本 Sprint 以
勘正 note 升 A 級量測參數＋守門交付。不推翻任何核心決議（僅確認既有 note 之變體標記為真、補強證據
等級），無須 Owner 定案（別於 Sprint 35 推翻 Sprint 25 core slot 0 建模）。

**完成**：
- ✅ tests/test_styles.py [實作]：新增 `test_handwritten_variants_measured_not_conflated` 守門：
  釘旁注主體 8.0pt（!=9.0）、Case 編號主體 9.0pt（!=15.9）與 source_font，且 Pepita 15.9 章扉與
  辰宇落雁 15.9 圖說同 15.9 級不同 source_font（防混淆）。docstring 記 A~D 量測結論。
- ✅ templates/neizai-zhengli.json [實作]：`旁注-手札圖注` 與 `Case編號-手寫拉丁` 兩 note 勘正，
  「（掃描）」待查語氣升 A 級量測參數（raw／頁數／頁碼／位置／處置）；Case 編號 note 補記原漏的
  10.4pt 目錄變體。size／source_font 不動（現狀正確），不新增樣式（status-quo）。
- ✅ 不改渲染／layout 幾何／case-divider 樣張（同 Sprint 34／35 勘正非修碼）：兩後端 parity 不受影響。

**測試成長**：216 → 217（test_styles 29→30，新增手寫變體量測守門）。0 失敗 0 退步。

**驗證**：
- typecheck（py_compile spikes／cjkfolio／tools）EXIT=0；test 217 passed／0 failed。
- 真實素材驗收（R5）：兩路臨時探針 179 頁一手量測（A~D 四問交叉驗證）；探針跑完即刪（scratchpad，
  參考書內容紅線不入 repo）。
- Gate 4 獨立驗證：量測（PyMuPDF get_text span font／size／bbox）與守門測試（模版載入斷言 size_pt／
  source_font）不同方法互證；C／D 級數反查為決定性交叉（HanziPen 9pt 34 字、Pepita 15.9pt 61 字各
  獨立命中，非單點推論），與 A／B 字型分布互證變體真實。
- Gate 3 同類掃描：「掃描見變體」為 Sprint 34 Gate 3 定義的待查類；本 Sprint 釐清最後兩個（旁注 9pt／
  Case 編號 15.9pt），grep 模版確認兩 note 均已勘正，該類待查標記全數清查完畢。
- 繁中標點：grep 本 Sprint 改動檔（模版／test_styles／GAPS／PLAN／devlog／CHANGELOG）無破折號字元殘留。

**代決事項（記入 PLAN §10）**：旁注 9pt（HanziPen raw 8.955、4 頁圖注大一號）／Case 編號 15.9pt
（Pepita raw 15.92、10 頁章扉大號）兩變體量測確認為真（非掃描誤植）＋另揭 Pepita 10.4pt 目錄變體；
勘正 note 升 A 級參數＋守門，變體屬美術層 Phase 1 無渲染用例不建獨立樣式（同 Sprint 34／35 勘正非
修碼）；Sprint 34 Gate 3「掃描見變體」待查標記全數清查完畢。

**落差登記**：GAPS #13「掃描見變體」待查標記子項由「未量測，後續逐一釐清」更新為「Sprint 36 釐清＝
兩變體皆真實」；變體建獨立樣式（旁注 9pt 圖注、Case 編號 15.9pt 章扉大號、10.4pt 目錄）登記後續專項
（需 Owner 決定投入，屬美術／自由佈局層與 Phase 2〜4 圖片置入／圖文繞排相關）。

**下個 Sprint 預定範圍**：「掃描見變體」待查標記已清查完畢，量測釐清型 Sprint 告一段落。後續候選：
黑 W7 欄標樣式建模＋個案中標移資訊區＋資訊區多欄位佈局（Sprint 35 揭露專項，屬定案 C 需 Owner 確認
範圍）；或噪音移除軌（PLAN §6 verbose 收斂，動前向 Owner 確認範圍）；或 GAPS #13 其他剩項（F 版權頁
真實版心 p178 待 Owner 本機量測、目錄摘要層／【結語】變體、部扉裝飾框待向量資產機制）。
