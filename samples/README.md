# samples／自擬公開樣張

本目錄的內容**全部自擬**（虛構書目與資料），可隨開源 repo 散布。

**紅線**：不得放入參考書《內在整理》的任何文字或圖像（版權物，僅限本機驗證，
見 PLAN §8 與 GAPS #1）。

| 檔案 | 用途 |
| --- | --- |
| `cip-copyright.doc.json` | 橫排版權頁-CIP 樣張（虛構書目）。示範 Sprint 13 的橫排版面軸（horizontal-tb）與 Sprint 14 的 CIP 細框向量原件（cip-box，兩後端 CMYK 描邊）。 |
| `toc.doc.json` | 直排目錄樣張（虛構條目）。示範 Sprint 15 的目錄天頭水平虛線（toc-rule，灰 K57、dash [3 2]，貫穿頁寬含出血）與 Sprint 16 的條目頁碼＋引導線（page_no 直排逐位底錨對齊＋行軸垂直引導線 0.1pt K92），兩後端同源。 |

重現：

```
python -m cjkfolio.cli render samples/cip-copyright.doc.json -o out/cip --dpi 300 --no-footer
python -m cjkfolio.cli export-pdf samples/cip-copyright.doc.json -o out/cip/cip.pdf --no-footer
python -m cjkfolio.cli preflight out/cip/cip.pdf

python -m cjkfolio.cli render samples/toc.doc.json -o out/toc --dpi 300 --no-footer
python -m cjkfolio.cli export-pdf samples/toc.doc.json -o out/toc/toc.pdf --no-footer
python -m cjkfolio.cli preflight out/toc/toc.pdf
```
