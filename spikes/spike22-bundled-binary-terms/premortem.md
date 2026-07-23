# Spike 22 pre-mortem：夾帶原生二進位的上游條款查證（GAPS #74 (e)(f)）

honest-planning R6。動工前先寫，寫完才准開工。

## 要答的題

GAPS #74 把兩項標為「製作安裝檔前的硬性阻擋項」，本 spike 要把它們變成可複查的結論：

- **(e)** uharfbuzz 的 `licenses/LICENSE` 全 11,357 字元是純 Apache-2.0，全檔無 harfbuzz 字樣，但 HarfBuzz 靜態連結進 `_harfbuzz.pyd`。上游條款是什麼？與 AGPL-3.0 相容嗎？散布時要盡什麼義務？
- **(f)** shiboken6 夾帶 10 枚 Microsoft VC++ 可轉散布元件（`concrt140.dll`、`msvcp140*.dll`、`vcruntime140*.dll` 等）。其轉散布條件是什麼？與 AGPL-3.0 的關係如何？

## 1. 最可能失敗的地方

**(f) 取不到 Microsoft 條款的一手文本。** VC++ redistributable 的條款隨 Visual Studio 授權合約走，本機未必裝有 Visual Studio，PySide6／shiboken6 的 dist-info 也未必收錄。沒有正文就沒有可複查的對象，等於 Sprint 118 的 FreeType 困境重演。

**(e) 的風險低但不為零**：HarfBuzz 用的是俗稱 Old MIT 的條款，本機若無任何一份夾帶副本，同樣落到上述困境。

## 2. 失敗機率

- (e)：約 10%（多個常用套件會夾帶 HarfBuzz，取得副本的機會高）
- (f)：約 60%（Microsoft 條款不隨 wheel 走是常態）

## 3. 早期訊號

搜遍本機 site-packages 與 Python 安裝目錄，找不到含 `harfbuzz` 或 `Visual C++` 條款字樣的授權檔。出現此訊號即進對策。

## 4. 對策

**先釘版本再取條款**（Sprint 118 定案的方法，本 spike 沿用）：任何條款陳述都必須綁定一個查得出來的版本號，兩路互證（執行期 API ＋ 二進位版本資源／字串）。

**(f) 拆成兩個獨立子問**，避免整項卡在取不到正文上：

1. **本專案現在有沒有在散布這些 DLL？** 這題用專案事實答，不需 Microsoft 條款：wheel 內容清單與散布形態是本機可查的。
2. **AGPL-3.0 怎麼看待這類元件？** 這題的一手依據就在 repo 根的 `LICENSE`（AGPL-3.0 全文），第 1 節有「系統程式庫」定義。用自家 repo 內的全文答，證據等級 A。

Microsoft 條款正文本身若取不到，如實記為未取得，不臆測其內容。

## 5. 放棄條件

**任一子問需要臆測條款內容才能得出結論時，該子問即停手轉 GAPS，不硬掰。** 具體門檻：

- 本機找不到 HarfBuzz 條款正文 → (e) 只交付「靜態連結事實 ＋ 版本釘死」，條款查證轉 GAPS
- 本機找不到 Microsoft 條款正文 → (f) 只交付上述兩個子問的答案，條款正文查證轉 GAPS

不因為「查不到就先假設寬鬆」而放行任何一項。

## 6. 替代方案

若兩項的條款正文都取不到，本 Sprint 改交付**安裝檔的授權檢查清單**：把「哪些檔案跟著散布、每個檔案要附哪一份條款、附了沒有」寫成機器可查的清單與測試，正文由 Owner 於製作安裝檔時補齊。這仍然把硬阻擋項從「不知道要做什麼」推進到「知道要做什麼、只差正文」。

## 7. 預估與誤差範圍

一個 Sprint（同 Sprint 118 的查證量級）。誤差 ±1 Sprint，變數在 (f) 是否需要額外一輪取得正文。
