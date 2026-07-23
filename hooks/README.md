# git hooks（提交前紅線字串掃描）

`.git/hooks/` 不進版本控制，所以 hook 放這裡，用一行設定指向它：

```
git config core.hooksPath hooks
```

設定後每次 `git commit` 會先跑 `python tools/precommit_scan.py --staged`，命中紅線
字串就 exit 1 擋下提交。**這是本機設定，clone 之後要各自設一次**（git 不允許 repo
內容自動改動使用者的 hook 設定，這是刻意的安全設計）。

稽核或 CI 用全庫模式：

```
python tools/precommit_scan.py --all
```

## 擋什麼

| 規則 | 擋的東西 | 紅線出處 |
| --- | --- | --- |
| `key-sk` / `key-google` / `key-github` | AI 金鑰與存取權杖樣式 | GAPS #6 |
| `net-tailscale` / `net-cgnat` | 私有 Tailscale 位址（MagicDNS 名稱與 CGNAT 網段） | GAPS #6 |
| `path-local` | `.py` 原始碼內含本機使用者路徑 | GAPS #63 |
| `reference-verbatim` | 參考書逐字內容 | GAPS #1 |

## 為什麼 `reference-verbatim` 的字串不在 repo 裡

那些字串本身就是要擋的版權內容，寫進 repo 等於把洩漏搬進掃描器。清單放
`local/reference-strings.txt`（`.gitignore` 擋下整個 `local/`），一行一則，`#` 開頭
為註解。清單不存在時掃描器會印出「規則略過」，不會假裝通過。

書名與書稿路徑那一格由 `tests/test_long_book_tool.py` 的素材外置守門測試負責，掃描器
不重複寫入書名字面量（本檔案位於 `tools/`，寫了會被那支測試掃到）。

## 繞過

`git commit --no-verify` 可繞過。**繞過視同紅線變更，需 Owner 顯式同意**，並在
`GAPS.md` 留一列說明繞過原因。
