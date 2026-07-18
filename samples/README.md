# samples／自擬公開樣張

本目錄的內容**全部自擬**（虛構書目與資料），可隨開源 repo 散布。

**紅線**：不得放入參考書《內在整理》的任何文字或圖像（版權物，僅限本機驗證，
見 PLAN §8 與 GAPS #1）。

| 檔案 | 用途 |
| --- | --- |
| `cip-copyright.doc.json` | 橫排版權頁-CIP 樣張（虛構書目）。示範 Sprint 13 的橫排版面軸（horizontal-tb）與 Sprint 14 的 CIP 細框向量原件（cip-box，兩後端 CMYK 描邊）。 |
| `toc.doc.json` | 直排目錄樣張（虛構條目）。示範 Sprint 15 的目錄天頭水平虛線（toc-rule，灰 K57、dash [3 2]，貫穿頁寬含出血）與 Sprint 16 的條目頁碼＋引導線（page_no 直排逐位底錨對齊＋行軸垂直引導線 0.1pt K92），兩後端同源。 |
| `wrap-demo.doc.json` | 圖文繞排樣張（自擬內文＋自擬照片）。示範 Sprint 89 的 `PlacedImage.wrap`：圖框成排除區，受影響行槽的內文避開圖的字軸範圍並留 `wrap_margin_mm` 一字格。搭配 `wrap-photo.png`＝程式生成的灰階漸層佔位圖（幾何形狀，非任何實際攝影或參考書圖像）。此圖為幾何示範用途，360×270px 置入後實效 218ppi，故匯出時會列 Sprint 91 的解析度警告（預期行為，非缺陷；示範檔非送印稿）。 |
| `punct-squeeze.doc.json` | 標點擠壓樣張（自擬內文）。同一句話排兩次：上段走 `內文-明體直排`（未擠壓），下段走 `內文-標點擠壓`（開啟）。示範 Sprint 90 的 `ParagraphStyle.punct_squeeze`＝CLREQ §3.1.6.1 相鄰約物減半形（規則 2〜6）。搭配 `punct-squeeze.template.json`＝內建模版加一款 `based_on: 內文-明體直排` 的子樣式（由 `save_template` 產出，僅 `punct_squeeze` 與 `note` 為自身宣告，其餘承基底）。 |
| `paiban-xiaoji-ch1.md` | **章節級公開素材**（自撰原創散文《排版小記》第一章，2,210 漢字）。GAPS #1 所需的「自由散布替代文本」：真書《內在整理》為版權物僅限本機，本檔可隨 repo 散布，供公開的端到端驗證。經 `import-md` 匯入為 41 段（章名 h1／小節標 h3／引文 blockquote／內文），排版 **11 頁、禁則 0 違規**，匯出 PDF/X-1a 機械檢查 **12/12 全過**。內容刻意涵蓋多條排版路徑：全大寫縮寫逐字正立（`CMYK`／`RGB`／`PDF`）與含小寫西文整串旋轉（`11.5pt`／`12.08pt`）兩種縱中橫形態、行內強調的發言人標籤、引文段落、左右頁鏡像與書眉頁碼。頁數與段數由 `tests/test_public_sample.py` 釘死，改寫本檔須同步更新本表。 |

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

mkdir -p out/public
python -m cjkfolio.cli import-md samples/paiban-xiaoji-ch1.md -o out/public/ch1.doc.json --title "排版小記"
python -m cjkfolio.cli render out/public/ch1.doc.json --out out/public/png
python -m cjkfolio.cli export-pdf out/public/ch1.doc.json -o out/public/ch1.pdf
python -m cjkfolio.cli preflight out/public/ch1.pdf
```

`paiban-xiaoji-ch1.md` 的預期輸出：render 報「11 頁、禁則 0 違規、擠入 7 行、撐開 0 行」，
export 報 5 款嵌入字型與「嵌入字型皆可合法嵌入子集」，preflight 報「全數通過（12/12）」、
「無置入影像」、「皆在上限內（最高 92% ≤ 320%）」。
render 與 export 會列兩則字型警告（明體 W7 以思源宋體 Heavy 替、仿宋以思源宋體替），
屬 GAPS #12 已登記的內建字型缺口，非本素材的缺陷。
