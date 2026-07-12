# Sprint #5（2026-07-10）Spike 4 授權研究＋Phase 0 閘門判定，已完成

**範圍**：Spike 4（Vivliostyle AGPL-3.0 桌面研究）；Phase 0 五 spike 總結與閘門判定。

**完成**：

- ✅ Spike 4 [Doc→關閉]：spikes/spike4-license/report.md。一手證據：官方 FAQ（Core AGPL-3.0、Pub Apache-2.0、「獨立程式可與專有程式並用」原文）、**@vivliostyle/cli v11.0.4 package.json license 欄位 "AGPL-3.0" 實查**、GNU GPL FAQ 臂長準則（pipes／命令列＝分離程式；共享位址空間／複雜內部資料結構＝單一程式）。結論：CLI 子程序＋檔案介面不受傳染，編輯器主體可用自有授權；散布採首次使用隨裝；禁止 in-process import；SaaS 形態下 AGPL §13 義務落在未修改的元件本身。殘餘風險誠實標示（非法律意見、FSF 立場非判例、相依樹授權未逐一盤點）。
- ✅ Phase 0 閘門判定 [Doc]：**條件性通過，可進 Phase 1**。五 spike 全數一手結論（1 直排核心：待 Owner 抽檢；2 輸出後端：2a 達標；3 效能：關閉；4 授權：關閉；5 AI 指派：關閉）。Phase 1 開工前置：下載思源宋體 TC、Owner 抽檢對比圖。判定全文入 PLAN Phase 0 節。

**測試成長**：15 → 15（本 Sprint 為桌面研究與判定，無程式碼變更），0 失敗 0 退步。

**驗證**：
- typecheck：無程式碼變更（維持 EXIT_CODE=0）
- test：15 passed / 0 failed
- 引證驗收（R1）：三個來源皆當日實抓（vivliostyle.org/faq、vivliostyle-cli package.json raw、gnu.org gpl-faq），關鍵句原文引述於報告；證據等級 B。
- 落差：法律覆核未做（報告內標示），不阻擋 Phase 1 工程開工，阻擋「正式散布」。

**留證**：
- 時戳：2026-07-10
- 樣本：spikes/spike4-license/report.md
- commit：78577e9

**下個 Sprint 預定範圍**：Phase 1 核心排版管線 MVP 開工。首個 Sprint 建議切片：文件模型（段落＋樣式參照的最小 JSON schema）＋三層樣式系統讀取＋以《內在整理》起始模版（§4.2）驅動 spike 引擎排版 txt 匯入的第一章，輸出多頁 PNG；PDF/X 寫出層後續 Sprint 進場。前置：思源宋體 TC 下載入 assets/fonts/（OFL，可入 repo）。
