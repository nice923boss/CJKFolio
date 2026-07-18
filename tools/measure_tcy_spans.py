"""量測參考書直排內文中的拉丁／數字排法（縱中橫證據，GAPS #48，Sprint 88）。

直排書把西文塞進字行有三種排法，本工具以「該 span 所在 line 的書寫方向」分類，
全書 179 頁一次掃完，供引擎 tokenize 規則對表：
  正立（upright，line dir≈(1,0)）：字不轉，橫向塞進字槽＝縱中橫（tate-chu-yoko）。
    連續多枚正立 span 若同欄（x 相同）且縱向間距≈字距，即「逐字正立」（每字一槽）。
  旋轉（rotated，line dir≈(0,1)）：整串順時針轉 90 度沿行軸下行，佔多槽。

分類鍵取 span 文字形態（全大寫／含小寫／純數字／數字帶尾點），與排法交叉統計，
即得「哪種內容該正立、哪種該旋轉」的一手判據。註記層（頁碼 GillSans／Case 編號
PepitaMT／目錄頁碼）與內文層分開統計，免小字層淹沒內文樣本。

紅線：只統計字型／級數／幾何與「西文短串本身」（品牌名、列標記等非書中文句），
不抽任何中文內文。輸出 assets/reference/tcy_measurements.json（本機不入 repo）
＋終端摘要。
用法（自 repo 根）：python tools/measure_tcy_spans.py [PDF路徑]
"""
import re
from collections import Counter

import fitz

from _measure_common import reference_pdf, spans, stdout_utf8, write_measurements

ASCII_RE = re.compile(r"[0-9A-Za-z]")
BODY_ADVANCE_PT = 12.08   # §1 實測內文字距（判逐字正立的縱向間距）
NOTE_FONTS = ("GillSans", "PepitaMT")  # 註記層：頁碼、Case 手寫編號
NOTE_MAX_SIZE = 9.5       # 註記層級數上限（內文 11.5、目錄章名 11.5）
SAME_COLUMN_TOL = 1.0     # 同欄容差（pt）：正立字寬各異，取 bbox 中心（＝行軸）比對
ADVANCE_TOL = 1.0         # 逐字正立的縱向間距容差（pt）


def orientation(line) -> str:
    """由 line dir 判排法：正立（橫書方向）vs 旋轉（沿直排行軸下行）。"""
    dx, dy = line.get("dir", (1.0, 0.0))
    return "upright" if abs(dx) > abs(dy) else "rotated"


def shape(text: str) -> str:
    """西文串形態分類（供與排法交叉對表）。"""
    core = text.strip()
    if re.fullmatch(r"\d+\.", core):
        return f"digits{len(core) - 1}+dot"
    if core.isdigit():
        return f"digits{len(core)}"
    if re.fullmatch(r"[A-Z]+", core):
        return f"upper{len(core)}"
    if re.fullmatch(r"[A-Za-z]", core):
        return "lower1"
    if any(c.islower() for c in core):
        return "hasLower"
    return "mixed"


def collect(doc) -> list:
    """全書 ASCII span 攤平：頁碼、排法、字型級數、bbox、形態。"""
    out = []
    for pno in range(doc.page_count):
        page = doc[pno]
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                ori = orientation(line)
                for sp in line["spans"]:
                    if not ASCII_RE.search(sp["text"]):
                        continue
                    bbox = [round(v, 2) for v in sp["bbox"]]
                    font, size = sp["font"], round(sp["size"], 2)
                    out.append({
                        "page": pno,
                        "orientation": ori,
                        "font": font,
                        "size_pt": size,
                        "text": sp["text"],
                        "shape": shape(sp["text"]),
                        "bbox": bbox,
                        "width_pt": round(bbox[2] - bbox[0], 2),
                        "height_pt": round(bbox[3] - bbox[1], 2),
                        "layer": ("note" if font.startswith(NOTE_FONTS)
                                  or size <= NOTE_MAX_SIZE else "body"),
                    })
    return out


def stacked_groups(records: list) -> list:
    """逐字正立偵測：同頁同欄（x 近）且縱向間距≈字距的連續正立 span 併成一組。

    真書把全大寫縮寫（如 IKEA）逐字正立各佔一槽，靠此還原「一串幾個槽」。
    """
    groups = []
    def cx(r) -> float:
        return (r["bbox"][0] + r["bbox"][2]) / 2

    upright = [r for r in records if r["orientation"] == "upright"]
    upright.sort(key=lambda r: (r["page"], round(cx(r), 1), r["bbox"][1]))
    cur: list = []
    for r in upright:
        if cur:
            p = cur[-1]
            same_col = (r["page"] == p["page"]
                        and abs(cx(r) - cx(p)) <= SAME_COLUMN_TOL)
            step = r["bbox"][1] - p["bbox"][1]
            if same_col and abs(step - BODY_ADVANCE_PT) <= ADVANCE_TOL:
                cur.append(r)
                continue
        if len(cur) > 1:
            groups.append(cur)
        cur = [r]
    if len(cur) > 1:
        groups.append(cur)
    return [{
        "page": g[0]["page"],
        "text": "".join(r["text"] for r in g),
        "cells": len(g),
        "font": g[0]["font"],
        "size_pt": g[0]["size_pt"],
        "step_pt": round(g[1]["bbox"][1] - g[0]["bbox"][1], 2),
        "layer": g[0]["layer"],
    } for g in groups]


def main() -> None:
    stdout_utf8()
    doc = fitz.open(reference_pdf())
    records = collect(doc)
    body = [r for r in records if r["layer"] == "body"]
    groups = [g for g in stacked_groups(records) if g["layer"] == "body"]

    cross = Counter((r["shape"], r["orientation"]) for r in body)
    data = {
        "source_pages": doc.page_count,
        "ascii_spans_total": len(records),
        "body_spans": len(body),
        "shape_orientation": {f"{s}／{o}": n for (s, o), n in sorted(cross.items())},
        "body_records": body,
        "stacked_upright_groups": groups,
    }
    path = write_measurements("tcy_measurements.json", data)

    print(f"全書 {doc.page_count} 頁，ASCII span {len(records)}（內文層 {len(body)}）")
    print("--- 形態 × 排法（內文層）---")
    for (s, o), n in sorted(cross.items()):
        print(f"  {s:<14} {o:<8} {n}")
    print("--- 逐字正立群組（內文層）---")
    for g in groups:
        print(f"  p{g['page']} {g['text']!r} {g['cells']} 槽 "
              f"step={g['step_pt']} {g['font']}@{g['size_pt']}")
    print("--- 正立 span 尺寸（內文層，判是否縮字）---")
    for r in body:
        if r["orientation"] == "upright":
            print(f"  p{r['page']} {r['text']!r} {r['font']}@{r['size_pt']} "
                  f"w={r['width_pt']} h={r['height_pt']}")
    print(f"量測寫入 {path}")


if __name__ == "__main__":
    main()
