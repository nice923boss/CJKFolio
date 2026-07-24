"""青空文庫格式 → cjkfolio document@2（Sprint 134，group／jukugo ruby 的真實素材）。

為什麼要這個工具：GAPS #46 的 group／jukugo ruby 補完條件是「依真實用例」，
而本專案至今沒有帶 ruby 的真實稿件（Sprint 110 Gate 0 據此順延）。**青空文庫**
是日本公有領域文學電子圖書館，其文本保留原書排印的振り仮名，正是熟語ルビ
（jukugo ruby）的真實出版用例；繁中注音實務幾乎全是 mono-ruby（Sprint 86 v1
已涵蓋），group ruby 的真實用例本就在日文。

青空文庫的 ruby 記法（https://www.aozora.gr.jp/annotation/）：
  漢字《かんじ》        ruby 附加在其前的連續同字種字串（多為漢字）
  ｜任意文字列《ルビ》  以 ｜ 明確指定 base 的起點（base 含假名或跨字種時用）
  ［＃…］              入力者注（外字說明、傍點位置等），非正文

本工具只取「正文＋ruby」這一層：入力者注與檔頭檔尾的凡例一律剔除，不做傍点、
外字、字下げ等其他注記（那些是另一批機制，本 Sprint 不做，見 GAPS）。

用法（素材一律由呼叫端顯式指定，工具不內含任何書稿路徑）：
    python tools/aozora_to_doc.py 來源.txt -o out.doc.json --template neizai-zhengli \\
        --title 羅生門 --style 內文-明體直排 [--max-paragraphs N]
來源檔編碼預設 Shift_JIS（青空文庫慣例），可以 --encoding 覆寫。
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

RUBY_RE = re.compile(r"《([^》]+)》")
ANNOTATION_RE = re.compile(r"［＃[^］]*］")
SEPARATOR_RE = re.compile(r"^-{10,}$")

# base 自動判定的字種：漢字（含互換符號）與長音等。青空文庫的規則是「往前取
# 同一字種」，本工具取漢字類（CJK 統一漢字、擴充 A、互換漢字）與踊り字 々〆〻。
_KANJI_EXTRA = "々〆〻ヶ"


def _is_kanji(ch: str) -> bool:
    if ch in _KANJI_EXTRA:
        return True
    return unicodedata.category(ch) == "Lo" and (
        "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿"
        or "豈" <= ch <= "﫿")


def strip_header_footer(text: str) -> str:
    """去掉檔頭凡例與檔尾底本資訊（青空文庫以連續 ---- 分隔線包夾凡例）。"""
    lines = text.replace("\r\n", "\n").split("\n")
    seps = [i for i, ln in enumerate(lines) if SEPARATOR_RE.match(ln.strip())]
    if len(seps) >= 2:  # 檔頭凡例在前兩條分隔線之間
        lines = lines[seps[1] + 1:]
    for i, ln in enumerate(lines):  # 檔尾：底本資訊自「底本：」起
        if ln.startswith("底本："):
            lines = lines[:i]
            break
    return "\n".join(lines)


def parse_ruby_runs(line: str) -> list:
    """一行青空文庫文字 → [(text, ruby|None), ...]（ruby 已與其 base 配對）。

    《》前若有 ｜ 則 base 自 ｜ 起；否則往前取連續漢字（青空文庫的自動判定）。
    無漢字可取時（如假名 base 未標 ｜）退為「前一個字」，不吞掉整行。
    """
    line = ANNOTATION_RE.sub("", line)
    runs: list = []
    plain = ""          # 尚未輸出的無 ruby 文字
    pos = 0
    for m in RUBY_RE.finditer(line):
        plain += line[pos:m.start()]
        pos = m.end()
        bar = plain.rfind("｜")
        if bar >= 0:
            base = plain[bar + 1:]
            plain = plain[:bar]
        else:
            i = len(plain)
            while i > 0 and _is_kanji(plain[i - 1]):
                i -= 1
            if i == len(plain):  # 前面不是漢字：退為前一字（不吞整行）
                i = max(0, len(plain) - 1)
            base, plain = plain[i:], plain[:i]
        if not base:  # 沒有 base 可掛（畸形輸入）：ruby 併回正文，不沉默丟棄
            plain += m.group(0)
            continue
        if plain:
            runs.append((plain, None))
            plain = ""
        runs.append((base, m.group(1)))
    plain += line[pos:]
    if plain:
        runs.append((plain.replace("｜", ""), None))
    return runs


def paragraphs_from_text(text: str, style: str) -> list:
    """青空文庫全文 → document@2 段落列（一行一段，空行略過）。"""
    out = []
    for raw in strip_header_footer(text).split("\n"):
        line = raw.strip("　 \t")
        if not line:
            continue
        runs = [{"text": t, **({"ruby": r} if r else {})}
                for t, r in parse_ruby_runs(line) if t]
        if runs:
            out.append({"style": style, "runs": runs})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="青空文庫 txt → document@2 JSON")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", required=True, help="正文段落樣式名")
    ap.add_argument("--master", default="A-內文版")
    ap.add_argument("--encoding", default="shift_jis")
    ap.add_argument("--max-paragraphs", type=int, default=0,
                    help="只取前 N 段（0＝全取）")
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    text = Path(args.input).read_text(encoding=args.encoding, errors="strict")
    paragraphs = paragraphs_from_text(text, args.style)
    if args.max_paragraphs:
        paragraphs = paragraphs[:args.max_paragraphs]
    doc = {
        "schema": "cjkfolio/document@2",
        "meta": {"title": args.title, "template": args.template,
                 "master": args.master},
        "paragraphs": paragraphs,
    }
    Path(args.output).write_text(
        json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    groups = [(r["text"], r["ruby"]) for p in paragraphs for r in p["runs"]
              if r.get("ruby")]
    multi = [g for g in groups if len(g[0]) > 1]
    print(f"轉換完成：{len(paragraphs)} 段 → {args.output}")
    print(f"ruby 標注 {len(groups)} 處，其中多字 base（group／jukugo）"
          f"{len(multi)} 處")
    if multi:
        sample = "、".join(f"{b}《{r}》" for b, r in multi[:8])
        print(f"多字 base 例：{sample}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
