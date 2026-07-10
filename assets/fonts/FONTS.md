# 字型資產說明

> .otf 二進位不入 git（見根目錄 .gitignore），以下載指令重現。授權全文見同目錄 LICENSE.txt（SIL OFL 1.1）。

## 已下載

| 檔案 | 來源 | 授權 | 用途 |
| --- | --- | --- | --- |
| SourceHanSerifTC-Regular.otf | adobe-fonts/source-han-serif release 2.003R（10_SourceHanSerifTC.zip） | SIL OFL 1.1 | 內文（對映參考書明體 W3），已驗 GSUB 含 vert |
| SourceHanSerifTC-Heavy.otf | 同上 | SIL OFL 1.1 | 章名／部扉大標（對映明體 W7/W9），已驗 vert |
| SourceHanSansTC-Medium.otf | adobe-fonts/source-han-sans release 2.004R（SourceHanSansTC.zip） | SIL OFL 1.1 | 個案大標／中標（原書即用思源黑體 Medium），已驗 vert |
| SourceHanSansTC-Bold.otf | 同上 | SIL OFL 1.1 | 章節小標、發言人標籤（對映黑體 W7），已驗 vert |
| ChenYuluoyan-2.0-Thin.ttf | Chenyu-otf/chenyuluoyan_thin release v2.0 | SIL OFL 1.1 | 書眉副標、手寫圖注、Case 編號（替華康手札體／Pepita），已驗 vert |
| jf-openhuninn-2.1.ttf | justfont/open-huninn-font release v2.1 | SIL OFL 1.1 | 頁碼數字（替 GillSans-Light），已驗 vert |

授權全文：思源宋體見 LICENSE.txt、思源黑體見 LICENSE-SourceHanSansTC.txt（皆 OFL 1.1）；辰宇與粉圓 OFL 全文見其 repo（下載來源）。

## 重現下載

```
curl -sL -o shs-tc.zip https://github.com/adobe-fonts/source-han-serif/releases/download/2.003R/10_SourceHanSerifTC.zip
# 解出 SourceHanSerifTC-Regular.otf、SourceHanSerifTC-Heavy.otf 及 LICENSE.txt
curl -sL -o shsans-tc.zip https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansTC.zip
# 解出 OTF/TraditionalChinese/ 的 Medium、Bold 及 LICENSE.txt（存為 LICENSE-SourceHanSansTC.txt）
curl -sL -o ChenYuluoyan-2.0-Thin.ttf https://github.com/Chenyu-otf/chenyuluoyan_thin/releases/download/v2.0/ChenYuluoyan-2.0-Thin.ttf
curl -sL -o jf-openhuninn-2.1.ttf https://github.com/justfont/open-huninn-font/releases/download/v2.1/jf-openhuninn-2.1.ttf
```

注意：raw.githubusercontent.com 的 SubsetOTF 舊路徑已失效（回 404 文字），一律走 Releases 資產。
渲染注意：辰宇與粉圓的 TrueType hinting bytecode 會使 FreeType 拋 too many function definitions，渲染器一律以 FT_LOAD_NO_HINTING 載入（cjkfolio/render.py）。

## 待補（PLAN §8 預設字型組）

全字庫正楷體 TW-Kai（題詞、目錄條目）、全字庫正宋體（仿宋引文替代），國發會開放授權，於對應樣式驗收 Sprint 進場（GAPS #12）。
