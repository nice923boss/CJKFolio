"""參考書章節文字抽取（本機驗證素材，版權紅線：輸出僅入 assets/reference/）。

直排 PDF 的閱讀流重建：字元依 x 中心聚欄（右至左）、欄內依 y 排序；
欄首縮排（> 1.5 字距）視為新段落；欄中位級數 > 內文帶視為標題欄，獨立成段。
段間空 1 行槽的版式（跨頁實測）保證段落一定從欄頂開始，per-欄判斷即完備。
縮排基準用「該頁 body 欄頂眾數桶」而非全書版心天頭：對談／反思等版心內縮頁
（欄頂整體下移）才不會逐欄誤判為新段。

限制（v1，txt 匯入本來就不帶樣式）：
- 級數 < 10.3pt 的旁注／標籤／頁腳不入流。
- 多欄長標題會拆成多段；由人工核對輸出確認。

用法：python tools/extract_chapter.py --start 19 --end 34 --out assets/reference/chapter1.txt
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "內在整理-20260312.pdf"

BODY_MIN_PT, BODY_MAX_PT = 10.3, 12.7   # 內文帶（含仿宋引文、楷書題詞、NotoSans 資訊列）
BLOCK_TOP_PT = 92.09  # 版心天頭（measurements.json），僅作無 body 欄頁的縮排基準備援
# 注意：不設 y 界過濾。題詞、對談等內縮版塊會超出內文版心底界（實測 p19 題詞至
# y≈523），以 y 界過濾會靜默截字。頁腳三件組全部 ≤9pt 或裝飾字型，級數帶已擋。
INDENT_THRESHOLD_PT = 18.0  # 段首縮排 2 字 = 24.16pt，門檻取 1.5 字距
COLUMN_TOL_PT = 7.0         # 行距 23pt，聚欄容差
MIN_HEADING_CHARS = 3       # 標題帶碎欄門檻（圖旁單字標籤剔除，剔除量入 log）
# 裝飾性頁面元素字型（Case 編號、頁碼），非章節正文，不入流
DECOR_FONTS = {"PepitaMT", "GillSans-Light"}


def page_chars(page) -> list:
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["font"] in DECOR_FONTS:
                    continue
                for ch in span["chars"]:
                    c = ch["c"]
                    if not c.strip():
                        continue
                    x0, y0, x1, _ = ch["bbox"]
                    chars.append(
                        {"c": c, "size": span["size"], "x": (x0 + x1) / 2, "y0": y0}
                    )
    return chars


def cluster_columns(chars: list) -> list:
    """依 x 中心聚欄，回傳右至左的欄清單。"""
    columns: list = []
    for ch in sorted(chars, key=lambda c: -c["x"]):
        for col in columns:
            if abs(col["x"] - ch["x"]) <= COLUMN_TOL_PT:
                col["items"].append(ch)
                break
        else:
            columns.append({"x": ch["x"], "items": [ch]})
    return columns


def extract(start: int, end: int):
    doc = fitz.open(PDF)
    paragraphs: list = []
    dropped: list = []
    current: list = []

    def close_paragraph() -> None:
        nonlocal current
        if current:
            paragraphs.append("".join(current))
            current = []

    for pno in range(start, end + 1):
        in_band = [c for c in page_chars(doc[pno]) if c["size"] >= BODY_MIN_PT]
        columns = []
        for col in cluster_columns(in_band):
            items = sorted(col["items"], key=lambda c: c["y0"])
            sizes = sorted(c["size"] for c in items)
            columns.append({"items": items, "median": sizes[len(sizes) // 2]})

        # 該頁縮排基準：body 欄頂眾數桶（6pt 分桶）的最小值
        body_tops = [c["items"][0]["y0"] for c in columns if c["median"] <= BODY_MAX_PT]
        if body_tops:
            mode_bucket = Counter(round(t / 6) for t in body_tops).most_common(1)[0][0]
            page_flow_top = min(t for t in body_tops if round(t / 6) == mode_bucket)
        else:
            page_flow_top = BLOCK_TOP_PT

        for col in columns:
            items = col["items"]
            if col["median"] > BODY_MAX_PT:  # 標題欄 → 獨立段；碎欄剔除
                text = "".join(c["c"] for c in items)
                if len(text) < MIN_HEADING_CHARS:
                    dropped.append(f"p{pno} {text!r}")
                    continue
                close_paragraph()
                paragraphs.append(text)
                continue
            if items[0]["y0"] - page_flow_top > INDENT_THRESHOLD_PT:
                close_paragraph()
            current.extend(c["c"] for c in items)
    close_paragraph()
    return paragraphs, dropped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, required=True, help="起始 PDF 頁（0 起算）")
    parser.add_argument("--end", type=int, required=True, help="結束 PDF 頁（含）")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    paragraphs, dropped = extract(args.start, args.end)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")

    total = sum(len(p) for p in paragraphs)
    print(f"抽取 PDF 頁 {args.start}~{args.end}：{len(paragraphs)} 段、{total} 字 → {out}")
    if dropped:
        print(f"剔除標題帶碎欄 {len(dropped)} 筆（不沉默）：{dropped}")
    print("各段（首 6 字＋字數，供人工核對）：")
    for i, p in enumerate(paragraphs, 1):
        print(f"  段 {i:>2}（{len(p):>4} 字）：{p[:6]}…")


if __name__ == "__main__":
    main()
