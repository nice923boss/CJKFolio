"""Spike 3（前段）：產生全書級長文件，量測 Vivliostyle 編譯時間。

以 sample.html 的內文段落重複至約 179 頁（《內在整理》頁數級），
輸出 long.html，供 vivliostyle build 計時。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
REPEAT = 96  # 每輪約 1.9 頁，96 輪約 180 頁


def main():
    src = (HERE / "sample.html").read_text(encoding="utf-8")
    m = re.search(r"<body>(.*)</body>", src, re.S)
    body = m.group(1)
    # 章標題加序號避免完全相同（模擬章節結構）
    blocks = []
    for i in range(REPEAT):
        blocks.append(body.replace("第<span class=\"tcy\">12</span>章",
                                   f"第<span class=\"tcy\">{i + 1:02d}</span>章"))
    long_html = src.replace(body, "\n".join(blocks))
    out = HERE / "long.html"
    out.write_text(long_html, encoding="utf-8")
    print(f"輸出 {out}（{REPEAT} 輪，約 {REPEAT * 1.9:.0f} 頁）")


if __name__ == "__main__":
    main()
