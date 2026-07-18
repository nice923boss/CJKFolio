# Sprint #34（2026-07-12）個案中標「12.9pt 變體」量測釐清否決，已完成

**範圍**：Sprint 33 預定範圍第一項（GAPS #13 剩項）：`個案中標-NotoSans`（size 11.4pt）
模版 note 末記「另有 12.9pt 變體見掃描」為誤導待查標記。依 honest-planning R1／R5（先量測
再動工，不憑空造 pt 目標），量測參考書確認 12.9pt 究竟是個案中標變體，還是掃描誤植（如
Sprint 23 署名長橫、Sprint 24 摘要層字型、Sprint 30 出血座標框錯配先例）。

**根因（Sprint 34 A 級量測）**：`tools/measure_case_page.py` 的 info 濾波為 NotoSans
11<size<12，只抓 11.4pt 資訊列、看不到 12.9pt，故無法直接回答歸屬。臨時探針兩路量測參考書
《內在整理》交印檔（本機，紅線不入 repo）：
1. 33 個案扉頁（右頁頂 17.9pt 大標者）右半頁頂 NotoSans 級數分布：**全數僅 11.4pt（資訊列
   副標「【欄位甲】…【居住者…」）＋17.9pt（大標），12.9pt 0 命中**。
2. 全書跨頁 81 個 12.9pt NotoSans span：**全落序文頁左半（PDF 3/6/8/12/14/16/174），文字為
   序文標題句（「把自己放回生命的正中央」等）**。交叉檢查：12.9pt 落在 33 個案扉頁的頁數＝0。

結論：個案中標＝單一 11.4pt；12.9pt 是 Sprint 23 已定的「推薦序大標-黑體」（NotoSans Medium
12.9pt，序文標題），與個案中標無關。掃描（scan_reference_styles 全書 font,size 統計）把
NotoSans Medium 多級數（11.4／12.9／17.9）並列，note 作者當時把不確定的 12.9pt 掛在個案中標旁
作待查，現量測證明不屬於此。**無新 pt 目標，誠實否決造變體（同 Sprint 31 para_gap 否決精神）**。

**完成**：
- ✅ tests/test_styles.py [實作]：新增 `test_case_info_size_single_and_distinct_from_preface`
  守門：個案中標 size==11.4、推薦序大標 size==12.9、同 source_font（NotoSansCJKtc-Medium）但
  級數與用途分離（防依誤導 note 把 12.9 併回個案中標）。docstring 記量測結論。
- ✅ templates/neizai-zhengli.json [實作]：個案中標 note 末尾「另有 12.9pt 變體見掃描」勘正為
  Sprint 34 量測釐清結論（33 扉頁 0 命中、81 span 全序文、屬推薦序大標）。size_pt 11.4 不動
  （現狀已正確）。
- ✅ 不改渲染／layout 幾何（同 Sprint 26 勘正非修碼）：個案中標 size 與置位本就正確，無行為
  變更，兩後端 parity 不受影響。

**測試成長**：214 → 215（test_styles 27→28，新增級數分離守門）。0 失敗 0 退步。

**驗證**：
- typecheck（py_compile spikes/cjkfolio/tools）EXIT=0；test 215 passed / 0 failed。
- 真實素材驗收（R5）：measure_case_page 列 33 個案扉頁大標基礎數據；臨時探針兩路量測（頁頂
  級數分布＋全書 12.9pt 落點）＋交叉檢查 0 命中。探針跑完即刪（scratchpad，不入 repo）。
- Gate 4 獨立驗證：量測（PyMuPDF get_text span）與守門測試（模版載入斷言）不同方法互證；交叉
  檢查 12.9pt∩個案扉頁＝∅ 為決定性反證（非單點推論）。
- Gate 3 同類掃描：grep 模版 note「見掃描／變體／待查」，掃出同類「掃描見變體」待查標記兩條
  （旁注-手札圖注 9pt、Case編號-手寫拉丁 15.9pt），屬不同樣式不同級數，依 R1/R5 須各自量測，
  本 Sprint 未量測不動，登記後續。line 155【結語】10pt 變體已充分記錄非誤導。
- 繁中標點：grep 本 Sprint 改動檔（模版／GAPS／PLAN／devlog／CHANGELOG／test_styles）無破折號字元殘留。

**代決事項（記入 PLAN §10）**：個案中標「12.9pt 變體」量測釐清否決；勘正 note＋GAPS 子項＋加
守門，不改 size／幾何（現狀正確，同 Sprint 26）。同類待查標記（旁注 9pt／Case 編號 15.9pt）未
量測不動，登記後續。

**落差登記**：GAPS #13 關「個案中標 11.4/12.9pt 兩變體未定」子項（釐清為單一 11.4pt，12.9pt
屬推薦序大標）。續留 #13 剩項：slot 0 Case 編號黑 W5 13pt 雙元素（v1 只建副標）、雙線菱形框
（美術資產不生成）、旁注 9pt 變體＋Case 編號 15.9pt 變體（Gate 3 新掃出，未量測）、B〜G 其他
扉頁逐頁量測。

**下個 Sprint 預定範圍**：slot 0 Case 編號黑 W5 13pt 雙元素建模（須量測 Case 編號位置，GAPS
#13）；或旁注 9pt／Case 編號 15.9pt 變體量測釐清（Gate 3 新掃出同類待查）；或噪音移除軌（PLAN
§6 Sprint 6〜16 verbose 收斂為指標，動前向 Owner 確認範圍）。
