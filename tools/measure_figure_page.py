"""量測參考書圖文版頁（G 主版）版面骨架幾何（GAPS #13，Sprint 27）。

參考書掃描發現兩種含圖頁型，本工具分類並只聚合 Type 1（真正的 G-圖文版）：
  Type 1 全頁圖文版（G）：≥2 張灰階照片填版心（img_frac≳0.2）、該頁無內文流
    （body≈0）、辰宇落雁體 15.9pt 圖說標籤（如「整理前／整理後」）。頁型＝
    房名黑體標題＋前後對照照片＋手寫圖說（本書整理術核心頁型，PDF 47 廚房為例）。
  Type 2 內文內嵌小圖（非 G，屬 Phase 4 圖文繞排）：單張小圖（img_frac≈0.1）
    嵌於大量內文中（body≳130），無辰宇圖說；排除於 G 幾何之外。

手繪／照片本體為美術資產（PLAN §8 不生成）＋需 Phase 2 圖片置入，本工具只量
頁型骨架：圖框保留區 rect（承 A 版心？）、圖說標籤級數與頂錨。紅線：只量幾何
與字型級數，不抽圖像像素、不存真書內文。輸出 assets/reference/
figure_measurements.json（本機不入 repo）＋終端摘要。
用法（自 repo 根）：python tools/measure_figure_page.py [PDF路徑]
"""
import sys

import fitz

from _measure_common import (
    HALF_W,
    PT_PER_MM,
    is_spread,
    reference_pdf,
    spans,
    stdout_utf8,
    write_measurements,
)

PAGE_H = 595.28           # 210mm（pt）
CAPTION_FONT = "ChenYuluoyan"   # 辰宇落雁體＝圖說標籤（§8 可散布 OFL）
FULL_PAGE_FRAC = 0.20     # 圖面積占比≥此＝Type 1 全頁圖文版
INLINE_BODY_MIN = 60      # 內文字數≥此且非全頁圖＝Type 2 內嵌小圖


def _half_local(bbox, side: str):
    dx = HALF_W if side == "R" else 0.0
    return (bbox[0] - dx, bbox[1], bbox[2] - dx, bbox[3])


def measure_page(page, idx: int):
    """回傳該 spread 上含圖那一書頁的骨架量測（含 Type 分類），或 None。"""
    img_rects = []
    for im in page.get_images(full=True):
        try:
            img_rects.extend(page.get_image_rects(im[0]))
        except Exception:
            pass
    if not img_rects:
        return None
    left = [r for r in img_rects if (r.x0 + r.x1) / 2 < HALF_W]
    right = [r for r in img_rects if (r.x0 + r.x1) / 2 >= HALF_W]
    side = "R" if len(right) >= len(left) else "L"
    rects = right if side == "R" else left
    if not rects:
        return None
    area = sum((r.x1 - r.x0) * (r.y1 - r.y0) for r in rects)
    frac = area / (HALF_W * PAGE_H)
    if frac < 0.05:
        return None

    locs = [_half_local((r.x0, r.y0, r.x1, r.y1), side) for r in rects]
    frame = {"x0": round(min(b[0] for b in locs), 2), "y0": round(min(b[1] for b in locs), 2),
             "x1": round(max(b[2] for b in locs), 2), "y1": round(max(b[3] for b in locs), 2)}
    frame["w"] = round(frame["x1"] - frame["x0"], 2)
    frame["h"] = round(frame["y1"] - frame["y0"], 2)

    caps, body_tops = [], []
    for s in spans(page):
        cx = (s["bbox"][0] + s["bbox"][2]) / 2
        if ("R" if cx >= HALF_W else "L") != side:
            continue
        if s["font"].startswith(CAPTION_FONT) and s["size"] > 13:
            caps.append(s)
        elif s["font"].startswith("DFMingStd") and 11 < s["size"] < 12:
            body_tops.append(s["bbox"][1])

    cap_box = None
    if caps:
        cb = [_half_local(s["bbox"], side) for s in caps]
        cap_box = {"x0": round(min(b[0] for b in cb), 2), "y0": round(min(b[1] for b in cb), 2),
                   "x1": round(max(b[2] for b in cb), 2), "y1": round(max(b[3] for b in cb), 2),
                   "size": round(caps[0]["size"], 2), "n_span": len(caps)}

    n_img, body = len(rects), len(body_tops)
    kind = "full" if (frac >= FULL_PAGE_FRAC and body < INLINE_BODY_MIN) else "inline"
    return {"page_index": idx, "side": side, "n_img": n_img, "img_frac": round(frac, 3),
            "kind": kind, "frame": frame, "caption": cap_box, "body_on_page": body}


def _agg(vals):
    return {"min": round(min(vals), 2), "max": round(max(vals), 2),
            "mean": round(sum(vals) / len(vals), 2), "n": len(vals)}


def _report_frame(rows, label):
    print(f"== {label}（half-local pt；mm）==")
    for side in ("L", "R"):
        srows = [r for r in rows if r["side"] == side]
        if not srows:
            continue
        x0, x1 = _agg([r["frame"]["x0"] for r in srows]), _agg([r["frame"]["x1"] for r in srows])
        print(f"   {side} 頁 n={len(srows)}：x0 mean={x0['mean']}（{x0['mean']/PT_PER_MM:.2f}mm）"
              f" x1 mean={x1['mean']}（{x1['mean']/PT_PER_MM:.2f}mm）")
    for k in ("y0", "y1"):
        a = _agg([r["frame"][k] for r in rows])
        print(f"   {k}: min={a['min']} max={a['max']} mean={a['mean']}（{a['mean']/PT_PER_MM:.2f}mm）")


def main() -> int:
    stdout_utf8()
    doc = fitz.open(reference_pdf())
    results = []
    for idx in range(len(doc)):
        page = doc[idx]
        if not is_spread(page):
            continue
        r = measure_page(page, idx)
        if r:
            results.append(r)
    if not results:
        print("未找到含圖頁")
        return 1

    out = write_measurements("figure_measurements.json", results)

    full = [r for r in results if r["kind"] == "full"]
    inline = [r for r in results if r["kind"] == "inline"]
    print(f"含圖頁 {len(results)}：Type 1 全頁圖文版（G）{len(full)}、Type 2 內嵌小圖 {len(inline)}")
    if full:
        _report_frame(full, "Type 1 圖框保留區")
        wc = [r for r in full if r["caption"]]
        if wc:
            print("== Type 1 圖說標籤（辰宇落雁體）==")
            print(f"   size: {_agg([r['caption']['size'] for r in wc])}")
            print(f"   頂錨 y0: {_agg([r['caption']['y0'] for r in wc])}")
    if inline:
        print(f"== Type 2（排除）：img_frac {_agg([r['img_frac'] for r in inline])}、"
              f"body {_agg([r['body_on_page'] for r in inline])} ==")
    print(f"量測 JSON → {out}（本機，不入 repo）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
