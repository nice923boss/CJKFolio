# samples／自擬公開樣張

本目錄的內容**全部自擬**（虛構書目與資料），可隨開源 repo 散布。

**紅線**：不得放入參考書《內在整理》的任何文字或圖像（版權物，僅限本機驗證，
見 PLAN §8 與 GAPS #1）。

| 檔案 | 用途 |
| --- | --- |
| `cip-copyright.doc.json` | 橫排版權頁-CIP 樣張（虛構書目）。示範 Sprint 13 的橫排版面軸（horizontal-tb）與 Sprint 14 的 CIP 細框向量原件（cip-box，兩後端 CMYK 描邊）。 |
| `toc.doc.json` | 直排目錄樣張（虛構條目）。示範 Sprint 15 的目錄天頭水平虛線（toc-rule，灰 K57、dash [3 2]，貫穿頁寬含出血）與 Sprint 16 的條目頁碼＋引導線（page_no 直排逐位底錨對齊＋行軸垂直引導線 0.1pt K92），兩後端同源。 |
| `wrap-demo.doc.json` | 圖文繞排樣張（自擬內文＋自擬照片）。示範 Sprint 89 的 `PlacedImage.wrap`：圖框成排除區，受影響行槽的內文避開圖的字軸範圍並留 `wrap_margin_mm` 一字格。搭配 `wrap-photo.png`＝程式生成的灰階漸層佔位圖（幾何形狀，非任何實際攝影或參考書圖像）。 |

| `punct-squeeze.doc.json` | 標點擠壓樣張（自擬內文）。同一句話排兩次：上段走 `內文-明體直排`（未擠壓），下段走 `內文-標點擠壓`（開啟）。示範 Sprint 90 的 `ParagraphStyle.punct_squeeze`＝CLREQ §3.1.6.1 相鄰約物減半形（規則 2〜6）。搭配 `punct-squeeze.template.json`＝內建模版加一款 `based_on: 內文-明體直排` 的子樣式（由 `save_template` 產出，僅 `punct_squeeze` 與 `note` 為自身宣告，其餘承基底）。 |

重現：

```
python -m cjkfolio.cli render samples/cip-copyright.doc.json -o out/cip --dpi 300 --no-footer
python -m cjkfolio.cli export-pdf samples/cip-copyright.doc.json -o out/cip/cip.pdf --no-footer
python -m cjkfolio.cli preflight out/cip/cip.pdf

python -m cjkfolio.cli render samples/toc.doc.json -o out/toc --dpi 300 --no-footer
python -m cjkfolio.cli export-pdf samples/toc.doc.json -o out/toc/toc.pdf --no-footer
python -m cjkfolio.cli preflight out/toc/toc.pdf

python -m cjkfolio.cli render samples/wrap-demo.doc.json --out out/wrap --first-page 2
python -m cjkfolio.cli export-pdf samples/wrap-demo.doc.json -o out/wrap/wrap-demo.pdf --first-page 2
python -m cjkfolio.cli preflight out/wrap/wrap-demo.pdf

python -m cjkfolio.cli render samples/punct-squeeze.doc.json -o out/squeeze --template samples/punct-squeeze.template.json --dpi 300
python -m cjkfolio.cli export-pdf samples/punct-squeeze.doc.json -o out/squeeze/punct-squeeze.pdf --template samples/punct-squeeze.template.json
python -m cjkfolio.cli preflight out/squeeze/punct-squeeze.pdf
```
