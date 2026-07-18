"""量測參考書「內文內嵌小圖」頁的圖文關係（Phase 4 圖文繞排 R1，Sprint 89）。

Sprint 27（measure_figure_page.py）分類出兩種含圖頁型，其中 Type 2「內文內嵌小
圖」被標為「屬 Phase 4 圖文繞排」留待本 Sprint 取證。本工具對真書全書掃描，對每
個「同頁既有圖又有內文流」的半頁，量測圖 rect 與該頁直排文字欄（行）的幾何關係，
判定真書實際採用的圖文關係形態：

  wrap-partial  某些欄與圖的行軸區間重疊，且該欄有字並避開圖的縱向範圍
                （＝真正的繞排：行被圖截短）
  column-block  與圖重疊的欄完全無內文（＝圖佔整欄，文字整欄避開，非行級繞排）
  disjoint      圖與內文欄的行軸區間完全不重疊（＝上下／左右分區，無繞排關係）

紅線：只量幾何與字數，不抽圖像像素、不存真書內文字句。輸出 assets/reference/
wrap_measurements.json（本機不入 repo）＋終端摘要。
用法（自 repo 根）：python tools/measure_wrap_pages.py [PDF路徑]
"""
import sys

import fitz

from _measure_common import (
    HALF_W,
    reference_pdf,
    spans,
    stdout_utf8,
    write_measurements,
)

BODY_SIZE = 11.5          # 內文級數（§1 實測）
SIZE_TOL = 0.6            # 級數容差（同級變體視為內文）
COLUMN_TOL = 3.0          # 同欄 x 中心容差（pt）
MIN_BODY_CHARS = 40       # 該半頁內文字數下限（少於此＝非內文流頁）
MIN_IMG_FRAC = 0.02       # 圖面積占比下限（濾掉裝飾細碎物件）


def _half_side(cx: float) -> str:
    return "R" if cx >= HALF_W else "L"


def _local(x: float, side: str) -> float:
    return x - HALF_W if side == "R" else x


def image_rects(page) -> list:
    out = []
    for im in page.get_images(full=True):
        try:
            out.extend(page.get_image_rects(im[0]))
        except Exception:
            pass
    return out


def body_columns(page, side: str) -> list:
    """該半頁的內文欄（直排行）：依 span x 中心分群，回傳 [{axis,top,bottom,chars}]。"""
    items = []
    for sp in spans(page):
        if abs(sp["size"] - BODY_SIZE) > SIZE_TOL:
            continue
        x0, y0, x1, y1 = sp["bbox"]
        cx = (x0 + x1) / 2
        if _half_side(cx) != side:
            continue
        text = sp["text"].strip()
        if not text:
            continue
        items.append((_local(cx, side), y0, y1, len(text)))
    items.sort(key=lambda it: -it[0])          # 直排右起
    cols: list = []
    for cx, y0, y1, n in items:
        if cols and abs(cols[-1]["axis"] - cx) <= COLUMN_TOL:
            col = cols[-1]
            col["top"] = min(col["top"], y0)
            col["bottom"] = max(col["bottom"], y1)
            col["chars"] += n
        else:
            cols.append({"axis": round(cx, 2), "top": y0, "bottom": y1, "chars": n})
    for col in cols:
        col["top"] = round(col["top"], 2)
        col["bottom"] = round(col["bottom"], 2)
    return cols


def gap_spans(page, side: str, img: dict, cols: list) -> list:
    """圖與內文之間空隙內的其他 span 摘要（判斷間隙成因＝圖說或純留白）。

    只取行軸落在圖區間內、且縱向落在「圖與最近內文邊界之間」的 span，回傳字型／
    級數／字數／bbox（不含字句內容，守版權紅線）。
    """
    overlapping = [c for c in cols
                   if img["x0"] - COLUMN_TOL <= c["axis"] <= img["x1"] + COLUMN_TOL]
    if not overlapping:
        return []
    body_top = min(c["top"] for c in overlapping)
    body_bottom = max(c["bottom"] for c in overlapping)
    lo, hi = (body_bottom, img["y0"]) if img["y0"] >= body_bottom else (img["y1"], body_top)
    out = []
    for sp in spans(page):
        x0, y0, x1, y1 = sp["bbox"]
        cx = (x0 + x1) / 2
        if _half_side(cx) != side:
            continue
        axis = _local(cx, side)
        if not (img["x0"] - COLUMN_TOL <= axis <= img["x1"] + COLUMN_TOL):
            continue
        if y1 <= lo or y0 >= hi:
            continue
        text = sp["text"].strip()
        if not text:
            continue
        out.append({
            "font": sp["font"],
            "size": round(sp["size"], 2),
            "chars": len(text),
            "axis": round(axis, 2),
            "y0": round(y0, 2),
            "y1": round(y1, 2),
        })
    return out


def classify(cols: list, img: dict) -> str:
    """圖與內文欄的關係分類（見模組 docstring）。"""
    overlapping = [c for c in cols
                   if c["axis"] >= img["x0"] - COLUMN_TOL
                   and c["axis"] <= img["x1"] + COLUMN_TOL]
    if not overlapping:
        return "disjoint"
    with_text = [c for c in overlapping if c["chars"] > 0]
    if not with_text:
        return "column-block"
    # 有字的重疊欄：其字是否避開圖的縱向範圍（＝行被截短）
    for c in with_text:
        if c["top"] < img["y1"] and c["bottom"] > img["y0"]:
            return "overlap-ink"        # 字與圖直接重疊（襯底或量測異常）
    return "wrap-partial"


def measure_page(page, idx: int) -> list:
    rects = image_rects(page)
    if not rects:
        return []
    out = []
    for side in ("R", "L"):
        cols = body_columns(page, side)
        chars = sum(c["chars"] for c in cols)
        if chars < MIN_BODY_CHARS:
            continue
        side_imgs = [r for r in rects if _half_side((r.x0 + r.x1) / 2) == side]
        for r in side_imgs:
            frac = ((r.x1 - r.x0) * (r.y1 - r.y0)) / (HALF_W * page.rect.height)
            if frac < MIN_IMG_FRAC:
                continue
            img = {
                "x0": round(_local(r.x0, side), 2),
                "x1": round(_local(r.x1, side), 2),
                "y0": round(r.y0, 2),
                "y1": round(r.y1, 2),
                "frac": round(frac, 3),
            }
            out.append({
                "pdf_index": idx,
                "side": side,
                "img": img,
                "body_chars": chars,
                "columns": cols,
                "relation": classify(cols, img),
                "gap_spans": gap_spans(page, side, img, cols),
            })
    return out


def main() -> None:
    stdout_utf8()
    doc = fitz.open(reference_pdf())
    findings: list = []
    for idx, page in enumerate(doc):
        findings.extend(measure_page(page, idx))
    counts: dict = {}
    for f in findings:
        counts[f["relation"]] = counts.get(f["relation"], 0) + 1
    print(f"掃描頁數：{len(doc)}；含圖且有內文流的圖例：{len(findings)}")
    for rel, n in sorted(counts.items()):
        print(f"  {rel}：{n}")
    for f in findings:
        img = f["img"]
        overlapping = [c for c in f["columns"]
                       if img["x0"] - COLUMN_TOL <= c["axis"] <= img["x1"] + COLUMN_TOL]
        print(f"\nPDF {f['pdf_index']} {f['side']} 半頁：{f['relation']}"
              f"（內文 {f['body_chars']} 字、共 {len(f['columns'])} 欄）")
        print(f"  圖 rect x {img['x0']}〜{img['x1']}／y {img['y0']}〜{img['y1']}"
              f"（占比 {img['frac']}）")
        print(f"  行軸落在圖區間的欄：{len(overlapping)}")
        for c in overlapping:
            print(f"    axis {c['axis']}：{c['chars']} 字，y {c['top']}〜{c['bottom']}")
        if f["gap_spans"]:
            print(f"  圖文間隙內其他 span：{len(f['gap_spans'])}")
            for g in f["gap_spans"]:
                print(f"    {g['font']} {g['size']}pt {g['chars']} 字"
                      f"，axis {g['axis']}，y {g['y0']}〜{g['y1']}")
        else:
            print("  圖文間隙內其他 span：無（純留白）")
    path = write_measurements("wrap_measurements.json", {
        "counts": counts,
        "findings": findings,
    })
    print(f"\n已寫出：{path}")


if __name__ == "__main__":
    main()
