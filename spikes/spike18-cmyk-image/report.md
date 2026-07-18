# Spike 18 報告：彩色 CMYK 影像置入

日期：2026-07-18　對應 GAPS #29 (c)　結論：**條件性通過**（CMYK TIFF 走，CMYK JPEG 不走）

## 1. 成功標準與結果

| 標準 | 結果 |
| --- | --- |
| 真書送印稿的彩色影像用哪個色彩空間 | **DeviceCMYK、8bpc、無 /Decode 反相陣列**（16 次置入，與 §1「16 張 CMYK」逐數吻合） |
| PIL 分量 → `/DeviceCMYK` XObject 位元組是否無損 | **是**，三組樣本逐位元組相等（合成極值圖、真書影像 TIFF、真書影像 JPEG） |
| 白區極值是否正確（CMYK 白＝0,0,0,0） | **是**，未反相 |
| Adobe 產製的 CMYK JPEG 是否可安全讀入 | **否**，PIL 讀出反相值（見 §3） |

## 2. 真書全書影像形態（`tools/measure_cmyk_images.py`，A 級一手）

179 頁、94 次置入、83 張獨立影像：

| 色彩空間 | 置入次數 | 說明 |
| --- | --- | --- |
| `DeviceN(1, DeviceCMYK, Black)` | 67 | §1 記的「灰階」實為 CMYK 空間上的單一黑版分色 |
| `DeviceCMYK` | 16 | §1 記的「16 張 CMYK」，逐數吻合 |
| `Indexed(1, DeviceCMYK)` | 10 | 出版社標章等雙色小圖 |
| `Indexed(254, DeviceCMYK)` | 1 | 版權頁小圖示 |

濾器 `/DCTDecode` 73、`/FlateDecode` 21；位元數全為 8；帶 `/Decode` 反相陣列 11
（全屬 Indexed 的索引值域宣告，非 CMYK 分量反相）；**帶 `/SMask` 透明 14**
（與 §1「含 SMask 透明、非 PDF/X」一致，本產品不得比照＝X-1a 禁透明）。

對本產品的意義：**`/DeviceCMYK` + 8bpc + 無 `/Decode`** 即真實印刷檔採用的形態，
本產品照此寫出即與真書同形；`DeviceN` 單黑版與 `Indexed` 為 InDesign 的最佳化形態，
本產品既有的 `DeviceGray` 同為 X-1a 合法灰階表達（`color-cmyk-only` 只禁 RGB 類），
不改。

## 3. 反相風險：premortem 第 1 條成真（`probe_cmyk_roundtrip.py`）

PIL 對 CMYK JPEG **一律**以 `CMYK;I`（反相）解讀（原始碼實查：
`JpegImagePlugin.py:386` 註解「assume adobe conventions」，儲存端 `:625` 對稱）。
但 libjpeg 對 YCCK（`adobe_transform=2`）的 YCCK→CMYK 轉換已先還原一次，PIL 再反相
一次即為雙重翻轉。實測（以 PyMuPDF 自行解 DCT 的 RGB 輸出為獨立基準，比較「墨量
語意」與「反相語意」兩假設的平均分量誤差）：

| 樣本 | adobe_transform | 墨量語意誤差 | 反相語意誤差 | 判定 |
| --- | --- | --- | --- | --- |
| 真書 xref 557（881×588） | 2（YCCK） | 221.45／255 | **3.14／255** | 反相 |
| 真書 xref 950（186×71） | 2（YCCK） | 193.14／255 | **5.69／255** | 反相 |
| PIL 自存的 CMYK JPEG | 0 | 不適用 | 不適用 | 與 TIFF 同義（平均差 0.52／255，反相假設 234.04） |

即：**真實世界的 Adobe CMYK JPEG（YCCK）讀進來是負片**，而 PIL 自己寫的（transform 0）
不是。判別子僅存在於 `adobe_transform` 這個函式庫層的容器細節，不同產製端與不同
Pillow 版本是否恆定，本 spike 無從擔保。

## 4. 定案（採 premortem §6 替代方案）

- **走**：CMYK TIFF（及其他非 JPEG 的 CMYK 容器）→ `/DeviceCMYK` 影像 XObject，
  逐位元組往返驗證無損。
- **不走**：CMYK JPEG → 快速失敗，訊息明示轉存 TIFF。理由：判定依據為函式庫層
  quirk，猜錯的後果是整批送印成負片（本產品最高代價的失效模式），而使用者的
  規避成本只是另存一次檔。此即 premortem「只支援收斂的容器，其餘拒收」。
- RGB 來源維持既有行為（轉灰階單 K）；本產品**不做 RGB→CMYK 換算**（Sprint 76
  色票決議：色彩轉換屬印廠 ICC 範疇；§7 對策亦為「影像外部轉 CMYK 置入」）。

## 5. 限制與可重現性

- 反相判定的獨立基準是 PyMuPDF 的 DCT 解碼；未以第三方色彩管理軟體交叉複核。
- 只驗兩張真書 YCCK 樣本與一張 PIL 自產 transform 0 樣本，未建立跨產製端
  （Photoshop／ImageMagick／Ghostscript）的 CMYK JPEG 樣本庫。
- 重現：`python tools/measure_cmyk_images.py`（全書形態）、
  `python spikes/spike18-cmyk-image/probe_cmyk_roundtrip.py`（往返與反相）。
  兩者皆需本機真書交印檔（紅線不入 repo），輸出寫 `out/` 亦不入 repo。
