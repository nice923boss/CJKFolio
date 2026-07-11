"""量測參考書版權頁（p178）CIP 框與文字幾何（GAPS #13 (a)，Sprint 19）。

輸出：assets/reference/cip_measurements.json（本機，不入 repo）＋終端摘要（數字）。
用法（自 repo 根）：python tools/measure_cip_page.py [PDF路徑]
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
PAGE_INDEX = 177  # PDF 頁 178（跨頁對開：版權頁為其中一半）
HALF_W = 419.53   # 148mm，跨頁半寬（pt）
PT_PER_MM = 72.0 / 25.4


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    pdf = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "內在整理-20260312.pdf")
    page = fitz.open(pdf)[PAGE_INDEX]
    page_h = page.rect.height

    # ---- CIP 細框（get_drawings 獨立解析；p178 實測為 5 段線折線閉合，非 re）----
    frames = []
    for d in page.get_drawings():
        pts = []
        for it in d["items"]:
            if it[0] == "re":
                r = it[1]
                pts += [(r.x0, r.y0), (r.x1, r.y1)]
            elif it[0] == "l":
                pts += [(it[1].x, it[1].y), (it[2].x, it[2].y)]
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            frames.append({
                "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
                "width_pt": d.get("width"), "stroke": d.get("color"),
                "fill": d.get("fill"),
                "items": [it[0] for it in d["items"]],
            })
    if not frames:
        print("未找到框線 drawings")
        return 1
    frame = frames[0]

    # 半邊判定：框中心落左半＝左頁（偶數書頁），右半＝右頁
    cx = (frame["x0"] + frame["x1"]) / 2
    left_half = cx < HALF_W
    x_off = 0.0 if left_half else HALF_W

    # ---- CIP 文字 spans（框內）----
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for sp in line["spans"]:
                bx = fitz.Rect(sp["bbox"])
                if (frame["x0"] - 2 <= bx.x0 and bx.x1 <= frame["x1"] + 2
                        and frame["y0"] - 2 <= bx.y0 and bx.y1 <= frame["y1"] + 2):
                    spans.append(sp)
    sizes = Counter(round(sp["size"], 2) for sp in spans)
    fonts = Counter(sp["font"] for sp in spans)

    # 行分組（origin y 聚類）
    ys = sorted({round(sp["origin"][1], 2) for sp in spans})
    rows: list = []
    for y in ys:
        if rows and abs(y - rows[-1][-1]) < 2.0:
            rows[-1].append(y)
        else:
            rows.append([y])
    baselines = [statistics.mean(r) for r in rows]
    pitches = [round(b - a, 3) for a, b in zip(baselines, baselines[1:])]

    # 字距：主字級同行相鄰 CJK span 難分（span 為串）；以最長 span 的寬/字數估
    main_size = sizes.most_common(1)[0][0]
    adv_samples = []
    for sp in spans:
        text = sp["text"]
        cjk = [ch for ch in text if ord(ch) > 0x2E7F]
        if round(sp["size"], 2) == main_size and len(cjk) >= 4 and len(cjk) == len(text):
            w = fitz.Rect(sp["bbox"]).width
            adv_samples.append(w / len(text))
    x0s = [fitz.Rect(sp["bbox"]).x0 for sp in spans]
    left_text = min(x0s)
    top_text = min(fitz.Rect(sp["bbox"]).y0 for sp in spans)
    bottom_text = max(fitz.Rect(sp["bbox"]).y1 for sp in spans)
    right_text = max(fitz.Rect(sp["bbox"]).x1 for sp in spans)

    result = {
        "page_index": PAGE_INDEX, "left_half": left_half,
        "frame_page_pt": {k: (frame[k] - x_off if k in ("x0", "x1") else frame[k])
                          for k in ("x0", "y0", "x1", "y1")},
        "frame_line_width_pt": frame["width_pt"], "frame_stroke": frame["stroke"],
        "n_frames": len(frames), "n_spans": len(spans), "n_rows": len(rows),
        "sizes_pt": dict(sizes), "fonts": dict(fonts),
        "baseline_pitches_pt": pitches,
        "char_advance_pt": (statistics.mean(adv_samples) if adv_samples else None),
        "pad_pt": {
            "left": left_text - frame["x0"], "right": frame["x1"] - right_text,
            "top": top_text - frame["y0"], "bottom": frame["y1"] - bottom_text,
        },
        "margins_page_pt": {
            "top": frame["y0"], "bottom": page_h - frame["y1"],
            "left": frame["x0"] - x_off, "right": (HALF_W if left_half else 839.06 - x_off) - frame["x1"] + (0 if left_half else x_off) ,
        },
        "spans_raw": [{"text": sp["text"], "size": sp["size"], "font": sp["font"],
                       "bbox": list(sp["bbox"]), "origin": list(sp["origin"])}
                      for sp in spans],
    }
    out = ROOT / "assets" / "reference" / "cip_measurements.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"半邊：{'左（偶數頁）' if left_half else '右（奇數頁）'}；框數 {len(frames)}、spans {len(spans)}、行 {len(rows)}")
    fp = result["frame_page_pt"]
    print(f"框（單頁 pt）：x0={fp['x0']:.2f} y0={fp['y0']:.2f} x1={fp['x1']:.2f} y1={fp['y1']:.2f}"
          f"、線寬 {frame['width_pt']}pt、色 {frame['stroke']}")
    print(f"字級分布 {dict(sizes)}；行距序列 {pitches}")
    print(f"CJK 字距估計 {result['char_advance_pt']}（樣本 {len(adv_samples)}）")
    print(f"框內 pad（pt）：{ {k: round(v, 2) for k, v in result['pad_pt'].items()} }")
    print(f"頁緣（pt）：top {result['margins_page_pt']['top']:.2f}"
          f"、bottom {result['margins_page_pt']['bottom']:.2f}"
          f"、left {result['margins_page_pt']['left']:.2f}")
    print(f"量測 JSON → {out}（本機，不入 repo）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
