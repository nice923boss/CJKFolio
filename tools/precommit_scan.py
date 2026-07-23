"""提交前字串掃描：擋住 `.gitignore` 擋不住的那一層（Sprint 114，丁類開源釋出項）。

由來（PLAN §10 Sprint 97 的流程教訓）：紅線稽核發現真書逐字內容已進了 11 個已追蹤
檔案，清洗後留下一句「`.gitignore` 只擋檔案層級，擋不住字串層級，同類洩漏會再發生，
pre-commit 字串掃描列入後續」。本檔就是那道守門。

守的三條紅線：

  GAPS #6  AI 金鑰與私有 endpoint 只存 local/ai-config.local.json
  GAPS #63 未出版私人書稿不入 repo，工具原始碼不得內含本機路徑
  GAPS #1  參考書《內在整理》逐字內容永不入 repo

**設計上的兩個約束，不是偷懶**：

  1. 規則的比對字串本身不得是紅線內容。參考書逐字字串清單若寫進本檔，本檔就成了新的
     洩漏源，故該規則的比對字串一律外置於 `local/reference-strings.txt`（`.gitignore`
     擋下 `local/`）。清單不存在時據實印出「略過」，不當成通過。
  2. 同理，書名字面量不寫進本檔（本檔位於 `tools/`，會被
     `tests/test_long_book_tool.py` 的素材外置守門測試掃到）。書名那一格由該測試守，
     本檔只守本機使用者路徑，兩者互補不重疊。

用法：

    python tools/precommit_scan.py --staged   # 掃已 stage 的檔案內容（hook 預設）
    python tools/precommit_scan.py --all      # 掃全部已追蹤檔案（稽核與 CI）

命中則 exit 1 並列出 `路徑:行號:規則`，命中片段一律遮蔽後才印（掃描報告本身不得成為
第二個外洩管道）。
"""
import argparse
import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_LIST_PATH = ROOT / "local" / "reference-strings.txt"


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: str
    why: str
    scope: tuple = ()      # 空＝全部檔案；否則為 fnmatch 樣式
    exempt: tuple = ()     # 豁免路徑（守方，例如以字面量斷言「不存在」的測試）


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    rule: str
    excerpt: str
    why: str


@dataclass(frozen=True)
class ReferenceStatus:
    available: bool
    count: int
    message: str
    needles: tuple = field(default=())


RULES = (
    Rule("key-sk", r"sk-[A-Za-z0-9_-]{20,}",
         "GAPS #6：AI 金鑰只存 local/ai-config.local.json"),
    Rule("key-google", r"AIza[0-9A-Za-z_-]{35}",
         "GAPS #6：AI 金鑰只存 local/ai-config.local.json"),
    Rule("key-github", r"gh[pousr]_[A-Za-z0-9]{36}",
         "GAPS #6：存取權杖不入 repo"),
    Rule("net-tailscale", r"[A-Za-z0-9-]+\.ts\.net",
         "GAPS #6：私有 Tailscale endpoint 不入 repo"),
    Rule("net-cgnat",
         r"(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])"
         r"\.\d{1,3}\.\d{1,3}(?![\d.])",
         "GAPS #6：CGNAT 私有網段（100.64 起算的 /10）位址不入 repo"),
    Rule("path-local", r"C:[\\/]Users",
         "GAPS #63：素材一律由呼叫端顯式指定，原始碼不得內含本機路徑",
         scope=("*.py",),
         exempt=("tests/test_long_book_tool.py",
                 "tests/test_font_naming_license.py")),
)

REFERENCE_RULE = Rule("reference-verbatim", "",
                      "GAPS #1：參考書《內在整理》逐字內容永不入 repo")


def mask(text: str) -> str:
    """遮蔽命中片段：只留前三字，其餘以長度交代。"""
    return f"{text[:3]}…（共 {len(text)} 字）"


def _in_scope(path: str, rule: Rule) -> bool:
    if any(fnmatch.fnmatch(path, pat) for pat in rule.exempt):
        return False
    if not rule.scope:
        return True
    return any(fnmatch.fnmatch(path, pat) for pat in rule.scope)


def scan_text(path: str, text: str, extra: tuple = ()) -> list:
    """掃一份文字內容，回傳命中清單。`extra` 為外置的參考書逐字字串。"""
    rules = [(r, re.compile(r.pattern)) for r in RULES if _in_scope(path, r)]
    if extra:
        joined = "|".join(re.escape(s) for s in extra)
        rules.append((REFERENCE_RULE, re.compile(joined)))
    hits = []
    for no, line in enumerate(text.splitlines(), start=1):
        for rule, rx in rules:
            for m in rx.finditer(line):
                hits.append(Hit(path, no, rule.name, mask(m.group(0)), rule.why))
    return hits


def reference_rule_status(list_path: Path = REFERENCE_LIST_PATH) -> ReferenceStatus:
    """讀外置的參考書逐字字串清單；不存在時據實回報略過，不沉默當成通過。"""
    if not list_path.exists():
        return ReferenceStatus(
            False, 0,
            f"reference-verbatim 規則略過：本機清單不存在（{list_path}）。"
            "此規則的比對字串本身即版權內容，故不入 repo，見本檔 docstring。")
    needles = tuple(
        s for s in (raw.strip() for raw in
                    list_path.read_text(encoding="utf-8").splitlines())
        if s and not s.startswith("#"))
    return ReferenceStatus(True, len(needles),
                           f"reference-verbatim 規則啟用：本機清單 {len(needles)} 則",
                           needles)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def _tracked_paths(root: Path) -> list:
    return [p for p in _git(root, "ls-files").splitlines() if p]


def _staged_paths(root: Path) -> list:
    out = _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACM")
    return [p for p in out.splitlines() if p]


def _read_working(root: Path, path: str):
    f = root / path
    try:
        return f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _read_staged(root: Path, path: str):
    r = subprocess.run(["git", "show", f":{path}"], cwd=root, capture_output=True)
    if r.returncode != 0:
        return None
    try:
        return r.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_paths(root: Path, paths: list, reader, extra: tuple) -> list:
    hits = []
    for path in paths:
        text = reader(root, path)
        if text is not None:
            hits.extend(scan_text(path, text, extra))
    return hits


def scan_tracked_files(root: Path = ROOT, extra: tuple = ()) -> list:
    """掃全部已追蹤檔案的工作區內容。"""
    return _scan_paths(root, _tracked_paths(root), _read_working, extra)


def scan_staged_files(root: Path = ROOT, extra: tuple = ()) -> list:
    """掃已 stage 的檔案內容（取 index 的版本，不是工作區的版本）。"""
    return _scan_paths(root, _staged_paths(root), _read_staged, extra)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")   # hook 與 CI 取管道時不落回 CP950
    ap = argparse.ArgumentParser(description="提交前紅線字串掃描")
    ap.add_argument("--all", action="store_true", help="掃全部已追蹤檔案（稽核）")
    ap.add_argument("--staged", action="store_true", help="掃已 stage 的檔案（預設）")
    args = ap.parse_args(argv)

    status = reference_rule_status()
    print(status.message)

    if args.all:
        hits = scan_tracked_files(ROOT, status.needles)
        scope = f"已追蹤檔案 {len(_tracked_paths(ROOT))} 份"
    else:
        hits = scan_staged_files(ROOT, status.needles)
        scope = f"已 stage 檔案 {len(_staged_paths(ROOT))} 份"

    print(f"掃描範圍：{scope}　規則 {len(RULES) + (1 if status.available else 0)} 條")
    if not hits:
        print("結果：0 命中")
        return 0
    print(f"結果：{len(hits)} 命中，提交已擋下")
    for h in hits:
        print(f"  {h.path}:{h.line}　[{h.rule}] {h.excerpt}")
        print(f"    {h.why}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
