"""Spike 5 第二輪：以《內在整理》真實章節文字重測 AI 樣式分類（GAPS #7）。

實驗設計：
- 標準答案由「排版真值」機械推導（字型＋級數：明體大級=章名、黑體=小標、
  仿宋/楷=引文、NotoSans=個案大標、內文段首黑體發言標籤=訪談發言、其餘=內文），
  不經人工標注；AI 只看純文字。
- 批次送測（每批 12 段），量測每批耗時與 tokens（PLAN §4.4：長書稿分章批次）。
- 素材僅本機使用（版權紅線）；輸出入 out/（gitignored）。
"""
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import median

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tag_probe import STYLES, call_llm

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "內在整理-20260312.pdf"
OUT = Path(__file__).resolve().parent / "out"
PAGE_RANGE = range(6, 40)  # 跨頁 index（跳過封面與目錄，目錄條目屬另一樣式場景）
BODY_SIZE = 11.5
BATCH = 12
CAP = 72  # 送測上限（分層抽樣：稀有類全收，內文補滿）


def page_items(page):
    """回傳本頁 (標準樣式, 文字, 是否縮排起始) 清單，依直排閱讀序。"""
    d = page.get_text("rawdict")
    chars = []
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for ch in span["chars"]:
                    chars.append({
                        "c": ch["c"], "font": span["font"], "size": span["size"],
                        "x": (ch["bbox"][0] + ch["bbox"][2]) / 2,
                        "y0": ch["bbox"][1],
                    })
    body = [c for c in chars if abs(c["size"] - BODY_SIZE) < 0.3
            and ("DFMingStd" in c["font"] or "PMingLiU" in c["font"]
                 or "DFHei" in c["font"])]
    cols = defaultdict(list)
    for c in body:
        cols[round(c["x"] / 11.5)].append(c)
    merged = defaultdict(list)
    for _, cs in cols.items():
        xc = median(c["x"] for c in cs)
        merged[round(xc, 0)].extend(cs)
    body_cols = []
    for xc in sorted(merged, reverse=True):
        col = sorted(merged[xc], key=lambda c: c["y0"])
        if len(col) >= 2:
            body_cols.append((xc, col))
    top = min((col[0]["y0"] for _, col in body_cols), default=0)

    items = []
    cur, cur_start_indent = [], False
    for _, col in body_cols:
        indented = col[0]["y0"] - top > 12
        if indented and cur:
            items.append(("body", cur, cur_start_indent))
            cur, cur_start_indent = [], True
        elif not cur:
            cur_start_indent = indented
        cur.extend(col)
    if cur:
        items.append(("body", cur, cur_start_indent))

    others = [c for c in chars if c["size"] > 12.6 or
              (abs(c["size"] - BODY_SIZE) < 0.3 and not any(
                  k in c["font"] for k in ("DFMingStd", "PMingLiU", "DFHei",
                                           "GillSans", "HanziPen", "Times")))]
    groups = defaultdict(list)
    for c in others:
        if c["size"] < 9:
            continue
        groups[(c["font"], round(c["size"], 1))].append(c)
    for (font, size), cs in groups.items():
        ys = [c["y0"] for c in cs]
        xs = [c["x"] for c in cs]
        if max(ys) - min(ys) < size * 0.8 and max(xs) - min(xs) > size:
            cs.sort(key=lambda c: c["x"])  # 橫排片段（圖注等）：左至右
            runs = [cs]
        else:
            cs.sort(key=lambda c: (-c["x"], c["y0"]))
            runs = []  # 相鄰欄距過大即切開（避免同頁多個標題被併成一項）
            for c in cs:
                if runs and abs(runs[-1][-1]["x"] - c["x"]) > size * 3 \
                        and c["x"] < runs[-1][-1]["x"] - size * 3:
                    runs.append([c])
                elif runs:
                    runs[-1].append(c)
                else:
                    runs = [[c]]
        for run in runs:
            text = "".join(c["c"] for c in run).strip()
            if len(text) < 2:
                continue
            if "NotoSans" in font:
                label = "個案大標" if size >= 14 else "章節小標"
            elif ("MingStd" in font or "Kai" in font) and size >= 15.5:
                label = "章名大標"
            elif "FangSong" in font or "KaiShu" in font:
                label = "引文"
            elif "Hei" in font:
                label = "章節小標"
            else:
                continue
            items.append((label, text, False))
    return items


def body_label(col_chars):
    if all("DFHei" in c["font"] for c in col_chars):
        return "章節小標"  # 整段黑體 = 獨立小標，非段內發言標籤
    head = col_chars[:4]
    if any("DFHei" in c["font"] for c in head):
        return "訪談發言"
    return "內文"


def collect():
    doc = fitz.open(PDF)
    dataset = []  # (標準樣式, 文字)
    pending = None  # 跨頁未收尾的 body 段
    for pi in PAGE_RANGE:
        for kind, payload, indented in page_items(doc[pi]):
            if kind != "body":
                if pending is not None:
                    dataset.append((body_label(pending), "".join(c["c"] for c in pending)))
                    pending = None
                dataset.append((kind, payload))
                continue
            if not indented and pending is not None:
                pending.extend(payload)  # 續前段
            else:
                if pending is not None:
                    dataset.append((body_label(pending), "".join(c["c"] for c in pending)))
                pending = payload
        # 頁尾不強制收段，讓段落跨頁接續
    if pending is not None:
        dataset.append((body_label(pending), "".join(c["c"] for c in pending)))
    # 修正 others 的資料形狀（(label, text)）
    fixed = []
    for row in dataset:
        if len(row) == 2 and isinstance(row[1], str):
            fixed.append(row)
    return fixed


def stratify(dataset):
    rare = [r for r in dataset if r[0] != "內文"]
    body = [r for r in dataset if r[0] == "內文"]
    take_body = max(0, CAP - len(rare))
    step = max(1, len(body) // max(take_body, 1))
    picked_body = body[::step][:take_body]
    return rare + picked_body


def main():
    dataset = collect()
    by = defaultdict(int)
    for label, _ in dataset:
        by[label] += 1
    print(f"[1] 抽出 {len(dataset)} 段（跨頁 {PAGE_RANGE.start}〜{PAGE_RANGE.stop - 1}），排版真值分布：{dict(by)}")

    test_set = stratify(dataset)
    print(f"[2] 分層抽樣送測 {len(test_set)} 段（稀有類全收）")

    results, timings, usages = [], [], []
    for b in range(0, len(test_set), BATCH):
        batch = test_set[b:b + BATCH]
        t0 = time.perf_counter()
        tagged, usage = call_llm([t[:180] for _, t in batch])
        dt = time.perf_counter() - t0
        timings.append(dt)
        usages.append(usage.get("total_tokens", 0))
        got = {item["index"]: item["style"] for item in tagged}
        for i, (expect, text) in enumerate(batch):
            results.append((expect, got.get(i, "(缺)"), text))
        print(f"    批 {b // BATCH + 1}：{len(batch)} 段 {dt:.1f}s tokens={usage.get('total_tokens')}")

    correct = sum(1 for e, g, _ in results if e == g)
    print(f"[3] 嚴格 6 類正確率：{correct}/{len(results)}（{correct / len(results) * 100:.1f}%）")
    heads = {"章名大標", "章節小標", "個案大標"}
    coarse = sum(1 for e, g, _ in results
                 if (e in heads and g in heads) or (e == g))
    print(f"    粗分類（標題類合併／內文／引文／訪談）：{coarse}/{len(results)}（{coarse / len(results) * 100:.1f}%）")
    per = defaultdict(lambda: [0, 0])
    for e, g, _ in results:
        per[e][1] += 1
        per[e][0] += (e == g)
    for label in STYLES:
        if per[label][1]:
            c, n = per[label]
            print(f"    {label}：{c}/{n}")
    print(f"[4] 批次耗時：中位 {median(timings):.1f}s／批（{BATCH} 段），tokens 中位 {median(usages):.0f}")

    OUT.mkdir(exist_ok=True)
    (OUT / "real_chapter_results.json").write_text(
        json.dumps([{"expect": e, "got": g, "text": t[:60]} for e, g, t in results],
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[5] 明細：{OUT / 'real_chapter_results.json'}（僅本機）")


if __name__ == "__main__":
    main()
