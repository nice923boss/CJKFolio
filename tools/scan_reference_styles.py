"""全書樣式掃描：《內在整理》(font, size) 分布與標題頁界探測。

用途：為起始模版（templates/）的樣式參數提供 A 級一手證據（§4.2、§4.3 從參考萃取的原型）。
輸入：repo 根目錄的參考書 PDF（版權紅線：僅本機，不入 repo）。
輸出：assets/reference/style_scan.json（在 .gitignore 的 assets/reference/ 內，僅本機）。
console 摘要僅供本機核對，devlog 不引用書中文字。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "內在整理-20260312.pdf"
OUT = ROOT / "assets" / "reference" / "style_scan.json"

HEADING_MIN_PT = 13.0  # 大於此級數視為標題候選（內文 11.5pt）


def main() -> None:
    doc = fitz.open(PDF)
    stats: dict = defaultdict(lambda: {"chars": 0, "pages": set(), "samples": []})
    headings: list = []

    for pno in range(doc.page_count):
        page = doc[pno]
        data = page.get_text("dict")
        for block in data["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"]
                    if not text.strip():
                        continue
                    key = (span["font"], round(span["size"], 1))
                    entry = stats[key]
                    entry["chars"] += len(text.strip())
                    entry["pages"].add(pno)
                    if len(entry["samples"]) < 3:
                        entry["samples"].append(
                            {"page": pno, "text": text.strip()[:14]}
                        )
                    if span["size"] >= HEADING_MIN_PT:
                        headings.append(
                            {
                                "page": pno,
                                "font": span["font"],
                                "size": round(span["size"], 1),
                                "text": text.strip()[:20],
                                "x": round(span["bbox"][0], 1),
                                "y": round(span["bbox"][1], 1),
                            }
                        )

    rows = [
        {
            "font": font,
            "size": size,
            "chars": v["chars"],
            "page_count": len(v["pages"]),
            "first_page": min(v["pages"]),
            "last_page": max(v["pages"]),
            "samples": v["samples"],
        }
        for (font, size), v in stats.items()
    ]
    rows.sort(key=lambda r: -r["chars"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"pdf_pages": doc.page_count, "styles": rows, "headings": headings},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    print(f"掃描完成：{doc.page_count} 頁、{len(rows)} 種 (font,size) 組合")
    print(f"輸出：{OUT}")
    print("\n字元數前 25 名：")
    for r in rows[:25]:
        print(
            f"  {r['font']:<28} {r['size']:>5}pt  {r['chars']:>6} 字"
            f"  頁 {r['first_page']}~{r['last_page']}（{r['page_count']} 頁）"
        )
    print(f"\n標題候選（>= {HEADING_MIN_PT}pt）共 {len(headings)} 筆，前 40 筆：")
    for h in headings[:40]:
        print(f"  p{h['page']:>3}  {h['size']:>5}pt  {h['font']:<26} {h['text']}")


if __name__ == "__main__":
    main()
