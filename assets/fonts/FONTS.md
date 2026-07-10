# 字型資產說明

> .otf 二進位不入 git（見根目錄 .gitignore），以下載指令重現。授權全文見同目錄 LICENSE.txt（SIL OFL 1.1）。

## 已下載（2026-07-10，Phase 1 前置）

| 檔案 | 來源 | 授權 | 用途 |
| --- | --- | --- | --- |
| SourceHanSerifTC-Regular.otf | adobe-fonts/source-han-serif release 2.003R（10_SourceHanSerifTC.zip） | SIL OFL 1.1 | 內文（對映參考書明體 W3），已驗 GSUB 含 vert |
| SourceHanSerifTC-Heavy.otf | 同上 | SIL OFL 1.1 | 章名大標（對映明體 W9），已驗 GSUB 含 vert |

## 重現下載

```
curl -sL -o shs-tc.zip https://github.com/adobe-fonts/source-han-serif/releases/download/2.003R/10_SourceHanSerifTC.zip
# 解出 OTF 內的 SourceHanSerifTC-Regular.otf 與 SourceHanSerifTC-Heavy.otf 及 LICENSE.txt
```

注意：raw.githubusercontent.com 的 SubsetOTF 舊路徑已失效（回 404 文字），一律走 Releases 資產。

## 待補（PLAN §8 預設字型組）

思源黑體（標題）、全字庫正楷體 TW-Kai（題詞）、辰宇落雁體（手寫圖注）、jf open 粉圓（拉丁／頁碼替代），於 Phase 1〜3 依樣式對映需求進場。
