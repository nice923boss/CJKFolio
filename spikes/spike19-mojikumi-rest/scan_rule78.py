"""Spike 19 探針三：CLREQ 規則 7／8（間隔號緊鄰括注符號）在真實素材的出現次數。

規則原文（W3C CLREQ WD-20150723 §3.1.6.1，逐字，B 級）：

  7. 當間隔號出現於結束括注符號之後，縮減其間四分之一個漢字大小的空白。
  8. 當間隔號出現於開始括注符號之前，縮減其間四分之一個漢字大小的空白。

`probe_rule78_ink.py` 已證明墨跡層面可壓（48 組配對全數不碰墨）。本探針回答另一
半：這個情境在真實稿件裡到底出現幾次。R5 要求真實素材驗收，出現 0 次的規則寫了
也無從驗收。

用法：`python scan_rule78.py <素材路徑>...`（.txt／.md 直讀，.pdf 走 PyMuPDF）。
repo 內 `samples/*.md` 自動納入。**本檔不內含任何本機書稿路徑**（素材外置紅線，
同 `tests/test_long_book_tool.py`，GAPS #63）。

間隔號候選取 U+00B7 ·、U+2027 ‧、U+30FB ・（三者皆有實務使用）。括注符號沿用
engine 的擠壓字集，不另立新集。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

from cjkfolio.engine import SQUEEZE_CLOSERS, SQUEEZE_OPENERS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INTERPUNCT = "·‧・"
OPENERS = "".join(sorted(SQUEEZE_OPENERS))
CLOSERS = "".join(sorted(SQUEEZE_CLOSERS))
RULE7 = re.compile(f"[{re.escape(CLOSERS)}][{re.escape(INTERPUNCT)}]")
RULE8 = re.compile(f"[{re.escape(INTERPUNCT)}][{re.escape(OPENERS)}]")
# 對照組：連 ASCII 半形括號也算，確認 0 是「情境不存在」而非「括號形態不同」
RULE7_ASCII = re.compile(f"[)\\]][{re.escape(INTERPUNCT)}]")
RULE8_ASCII = re.compile(f"[{re.escape(INTERPUNCT)}][(\\[]")


def read_material(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        import fitz
        with fitz.open(p) as pdf:
            return "\n".join(page.get_text() for page in pdf)
    return p.read_text(encoding="utf-8")


def scan(name: str, text: str) -> dict:
    return {
        "素材": name,
        "字元數": len(text),
        "間隔號": sum(text.count(c) for c in INTERPUNCT),
        "規則7": len(RULE7.findall(text)),
        "規則8": len(RULE8.findall(text)),
        "規則7(ASCII括號)": len(RULE7_ASCII.findall(text)),
        "規則8(ASCII括號)": len(RULE8_ASCII.findall(text)),
    }


def main() -> int:
    print(f"開始括注符號集：{OPENERS}")
    print(f"結束括注符號集：{CLOSERS}")
    print(f"間隔號候選：{INTERPUNCT}\n")

    rows = []
    for md in sorted((ROOT / "samples").glob("*.md")):
        if md.name == "README.md":
            continue
        rows.append(scan(f"samples/{md.name}", md.read_text(encoding="utf-8")))
    for i, arg in enumerate(sys.argv[1:], 1):   # 外置素材：只取數字，內容不入 repo
        p = Path(arg)
        if not p.exists():
            print(f"外置素材 {i} 不存在，略過：{arg}")
            continue
        rows.append(scan(f"外置素材 {i}（{p.suffix}）", read_material(p)))

    print(f"{'素材':<24}｜{'字元數':>8}｜{'間隔號':>6}｜{'規則7':>5}｜{'規則8':>5}｜"
          f"{'7(ASCII)':>8}｜{'8(ASCII)':>8}")
    print("-" * 88)
    for r in rows:
        print(f"{r['素材']:<24}｜{r['字元數']:>8}｜{r['間隔號']:>6}｜{r['規則7']:>5}｜"
              f"{r['規則8']:>5}｜{r['規則7(ASCII括號)']:>8}｜{r['規則8(ASCII括號)']:>8}")

    tot = sum(r["字元數"] for r in rows)
    print(f"\n合計 {tot} 字元：規則 7 情境 {sum(r['規則7'] for r in rows)} 次、"
          f"規則 8 情境 {sum(r['規則8'] for r in rows)} 次"
          f"（ASCII 括號對照組：{sum(r['規則7(ASCII括號)'] for r in rows)}／"
          f"{sum(r['規則8(ASCII括號)'] for r in rows)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
