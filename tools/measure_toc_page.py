"""量測參考書目錄頁「篇名嵌線斷開＋條目縮退」幾何（GAPS #13 (b)，Sprint 21）。

掃描前數個 PDF 頁找含 dash 虛線的目錄頁，對每個含虛線的半頁輸出：
虛線各段 x 範圍（斷開區間）、部名行 x 範圍與首字頂、條目起點、斷開端點與
部名字墨的間隙、縮退量。
輸出：assets/reference/toc_measurements.json（本機，不入 repo）＋終端摘要。
用法（自 repo 根）：python tools/measure_toc_page.py [PDF路徑]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
SCAN_PAGES = 6    # 目錄在書前，掃 PDF 索引 0〜5
HALF_W = 419.53   # 148mm，跨頁半寬（pt）
PT_PER_MM = 72.0 / 25.4


def _dash_lines(page):
    """含 dash 的水平線 draws：[(x0, x1, y, width, color, dashes)]。"""
    out = []
    for d in page.get_drawings():
        if not d.get("dashes") or d["dashes"] in ("[] 0", "[ ] 0"):
            continue
        for it in d["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 0.5:
                x0, x1 = sorted((it[1].x, it[2].x))
                out.append({"x0": x0, "x1": x1, "y": (it[1].y + it[2].y) / 2,
                            "width_pt": d.get("width"), "color": d.get("color"),
                            "dashes": d.get("dashes")})
    return sorted(out, key=lambda s: s["x0"])


def _half(v, left):
    return v if left else v - HALF_W


def _entry_columns(spans: list, left: bool) -> list:
    """把半頁 spans 按直排列（字中心 x 相近）聚成條目列。

    直排書目錄每條目為一直列（字由上而下），列由右至左為閱讀序。
    每列標主 CJK 字型／級數（排除拉丁頁碼字型後取眾數）與是否帶頁碼數字。
    """
    buckets: list = []
    for sp in sorted(spans, key=lambda s: (-(s["bbox"][0] + s["bbox"][2]) / 2, s["bbox"][1])):
        cx = (sp["bbox"][0] + sp["bbox"][2]) / 2
        if buckets and abs(buckets[-1][0] - cx) < 8:
            buckets[-1][1].append(sp)
        else:
            buckets.append((cx, [sp]))
    cols = []
    for cx, sps in buckets:
        sps = sorted(sps, key=lambda s: s["bbox"][1])
        cjk = [s for s in sps if not s["font"].startswith(("Times", "Pepita"))]
        counts = Counter((s["font"], round(s["size"], 2)) for s in cjk)
        head = counts.most_common(1)[0][0] if counts else (sps[0]["font"], round(sps[0]["size"], 2))
        cols.append({
            "text": "".join(s["text"] for s in sps),
            "font": head[0], "size": head[1],
            "cx": round(_half(cx, left), 2),
            "top_y": round(min(s["bbox"][1] for s in sps), 2),
            "bottom_y": round(max(s["bbox"][3] for s in sps), 2),
            "has_page_no": any(s["font"].startswith("Times") for s in sps),
        })
    return cols


def measure_half(page, idx, left):
    """量一個半頁（left=True 左半＝偶數書頁）。無虛線回 None。"""
    lo, hi = (0.0, HALF_W) if left else (HALF_W, HALF_W * 2)
    segs = [s for s in _dash_lines(page) if lo - 30 <= s["x0"] and s["x1"] <= hi + 30]
    if not segs:
        return None
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for sp in line["spans"]:
                bx = fitz.Rect(sp["bbox"])
                if lo <= (bx.x0 + bx.x1) / 2 <= hi:
                    spans.append(sp)
    rule_y = segs[0]["y"]
    # 穿線字（字墨 y 範圍蓋過虛線 y 者）依 x 聚成行
    crossing = [sp for sp in spans
                if sp["bbox"][1] < rule_y < sp["bbox"][3]]
    cross_rows: list = []
    for sp in sorted(crossing, key=lambda s: s["bbox"][0]):
        if cross_rows and sp["bbox"][0] - cross_rows[-1][-1]["bbox"][2] < 8:
            cross_rows[-1].append(sp)
        else:
            cross_rows.append([sp])
    cross_lines = [{
        "text": "".join(sp["text"] for sp in row),
        "font": row[0]["font"], "size": round(row[0]["size"], 2),
        "x0": _half(min(sp["bbox"][0] for sp in row), left),
        "x1": _half(max(sp["bbox"][2] for sp in row), left),
        "top_y": min(sp["bbox"][1] for sp in row),
        "bottom_y": max(sp["bbox"][3] for sp in row),
    } for row in cross_rows]
    # 未穿線內容（條目等）的最高起點
    below = [sp for sp in spans if sp["bbox"][1] >= rule_y]
    fonts = Counter((sp["font"], round(sp["size"], 2)) for sp in spans)
    return {
        "page_index": idx, "half": "left" if left else "right",
        "rule_y_pt": rule_y,
        "rule_segments": [{
            "x0": _half(s["x0"], left), "x1": _half(s["x1"], left),
            "width_pt": s["width_pt"], "color": s["color"], "dashes": s["dashes"],
        } for s in segs],
        "crossing_lines": cross_lines,
        "content_below_top_y": min((sp["bbox"][1] for sp in below), default=None),
        "fonts": {f"{f} {s}pt": n for (f, s), n in fonts.most_common()},
        "entry_columns": _entry_columns(spans, left),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    pdf = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "內在整理-20260312.pdf")
    doc = fitz.open(pdf)
    results = []
    for idx in range(min(SCAN_PAGES, len(doc))):
        page = doc[idx]
        halves = [True, False] if page.rect.width > HALF_W * 1.5 else [True]
        for left in halves:
            r = measure_half(page, idx, left)
            if r:
                results.append(r)
    if not results:
        print("掃描頁內未找到 dash 虛線")
        return 1
    out = ROOT / "assets" / "reference" / "toc_measurements.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in results:
        print(f"== PDF 索引 {r['page_index']} {r['half']} 半頁：虛線 y={r['rule_y_pt']:.2f}pt、"
              f"{len(r['rule_segments'])} 段 ==")
        for s in r["rule_segments"]:
            print(f"  段 x {s['x0']:.2f} → {s['x1']:.2f}（寬 {s['width_pt']}pt、dash {s['dashes']}）")
        for ln in r["crossing_lines"]:
            print(f"  穿線行「{ln['text']}」{ln['font']} {ln['size']}pt："
                  f"x {ln['x0']:.2f}〜{ln['x1']:.2f}、字頂 y {ln['top_y']:.2f}")
        print(f"  線下內容最高起點 y={r['content_below_top_y']}")
        groups: dict = defaultdict(list)
        for c in r["entry_columns"]:
            groups[(c["font"], c["size"])].append(c)
        for (f, s), cs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            withpg = sum(c["has_page_no"] for c in cs)
            sample = next((c["text"] for c in cs if len(c["text"]) > 2), cs[0]["text"])[:16]
            print(f"  列層 {f} {s}pt：{len(cs)} 列、{withpg} 帶頁碼、"
                  f"cx {min(c['cx'] for c in cs):.1f}〜{max(c['cx'] for c in cs):.1f}｜例「{sample}」")
    print(f"量測 JSON → {out}（本機，不入 repo）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
