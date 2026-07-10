"""Spike 1 校準分析：從 reference_page.json 逐字座標抽出引擎所需參數。

輸出 assets/reference/calibration.json：
- 字距分布（偵測標點擠壓是否存在）
- 段首縮排深度（段落起始行的首字 y 相對版心頂）
- 每行 x 軸位置（行軸網格）
- 頁腳三件組（頁碼／書名／協力）各字元座標與字型
- 內文全文（依閱讀序重建，供樣張排版輸入）
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REF = Path(__file__).resolve().parents[2] / "assets" / "reference"
BODY_FONT = "DFMingStd-W3"


def load_chars():
    data = json.loads((REF / "reference_page.json").read_text(encoding="utf-8"))
    return data["chars"]


def body_lines(chars):
    body = [c for c in chars if BODY_FONT in c["font"]]
    cols = defaultdict(list)
    for c in body:
        xc = round((c["bbox"][0] + c["bbox"][2]) / 2, 1)
        cols[xc].append(c)
    lines = []
    for xc in sorted(cols, reverse=True):
        lines.append((xc, sorted(cols[xc], key=lambda c: c["bbox"][1])))
    return lines


def main():
    chars = load_chars()
    lines = body_lines(chars)

    print("[1] 字距分布（行內相鄰字 origin y 差，偵測擠壓）：")
    buckets = Counter()
    for _, col in lines:
        for a, b in zip(col, col[1:]):
            dy = b["origin"][1] - a["origin"][1]
            if 0 < dy < 40:
                buckets[round(dy, 1)] += 1
    for dy, n in sorted(buckets.items()):
        print(f"    {dy}pt x {n}")

    print("[2] 各行首字 y 與行字數（偵測段首縮排）：")
    top = min(col[0]["bbox"][1] for _, col in lines)
    first_char_offsets = []
    for xc, col in lines:
        dy = col[0]["bbox"][1] - top
        first_char_offsets.append(round(dy, 1))
        text = "".join(c["c"] for c in col)
        print(f"    x={xc:6.1f} 首字y偏移={dy:5.1f}pt 字數={len(col):2d}  {text[:12]}")

    print("[3] 行軸 x 網格（右至左相鄰差）：")
    xs = [xc for xc, _ in lines]
    print("    " + ", ".join(f"{round(a - b, 2)}" for a, b in zip(xs, xs[1:])))

    print("[4] 頁腳元素（非內文字型）：")
    foot = [c for c in chars if BODY_FONT not in c["font"]]
    for c in foot:
        print(f"    {c['font']:20s} size={c['size']:5.2f} origin={c['origin']} c={c['c']!r}")

    paragraphs = []
    cur = []
    for i, (xc, col) in enumerate(lines):
        starts_new = first_char_offsets[i] > 6  # 首字低於版心頂 = 段首縮排
        if starts_new and cur:
            paragraphs.append("".join(cur))
            cur = []
        cur.extend(c["c"] for c in col)
    if cur:
        paragraphs.append("".join(cur))
    print(f"[5] 依縮排切出段落數：{len(paragraphs)}")

    calib = {
        "advance_distribution": {str(k): v for k, v in sorted(buckets.items())},
        "line_x_centers": xs,
        "first_char_offsets_pt": first_char_offsets,
        "block_top_pt": round(top, 2),
        "foot_elements": foot,
        "paragraphs": paragraphs,
    }
    (REF / "calibration.json").write_text(
        json.dumps(calib, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[6] 產出：{REF / 'calibration.json'}")


if __name__ == "__main__":
    main()
