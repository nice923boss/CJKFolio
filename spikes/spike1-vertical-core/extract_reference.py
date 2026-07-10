"""Spike 1 前置：抽取《內在整理》代表跨頁，驗證直排抽序，量測排版參數。

PLAN 第 6 節 Phase 0 執行細則「素材與字型前置」第 1 步：
- 直排 PDF 的文字抽取順序可能錯亂，先驗證抽序正確再進排版。
- 量測：字距（行內相鄰字 y 差）、行距（相鄰行 x 差）、版心（文字區塊 bbox 與頁緣距離）。
- 產出（僅入 assets/reference/，版權紅線，永不入公開 repo）：
    reference_page.json  代表頁逐字座標與字型
    reference_page.png   代表頁渲染圖（對比圖右半的素材）
    measurements.json    量測參數（引擎輸入）
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "內在整理-20260312.pdf"
OUT_DIR = ROOT / "assets" / "reference"
BODY_FONT_HINT = "DFMingStd-W3"
BODY_SIZE_HINT = 11.5
PT_PER_MM = 72 / 25.4


def page_char_stats(page):
    """回傳 (內文字元數, 是否含 GillSans 頁碼字型)。"""
    body = 0
    has_gill = False
    d = page.get_text("rawdict")
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                font = span["font"]
                if "GillSans" in font:
                    has_gill = True
                if BODY_FONT_HINT in font and abs(span["size"] - BODY_SIZE_HINT) < 0.2:
                    body += len(span["chars"])
    return body, has_gill


def pick_representative(doc):
    """選內文字元數最多且含 GillSans 頁碼的跨頁。"""
    best = None
    for i, page in enumerate(doc):
        body, has_gill = page_char_stats(page)
        if not has_gill:
            continue
        if best is None or body > best[1]:
            best = (i, body)
    if best is None:
        raise SystemExit("找不到含 GillSans 頁碼的內文頁")
    return best


def extract_chars(page):
    """逐字抽取：字元、原始順序、bbox、字型、級數、行方向。"""
    chars = []
    d = page.get_text("rawdict")
    order = 0
    for bi, block in enumerate(d["blocks"]):
        if block["type"] != 0:
            continue
        for li, line in enumerate(block["lines"]):
            for span in line["spans"]:
                for ch in span["chars"]:
                    chars.append(
                        {
                            "c": ch["c"],
                            "order": order,
                            "bbox": [round(v, 2) for v in ch["bbox"]],
                            "origin": [round(v, 2) for v in ch["origin"]],
                            "font": span["font"],
                            "size": round(span["size"], 2),
                            "dir": line["dir"],
                            "block": bi,
                            "line": li,
                        }
                    )
                    order += 1
    return chars


def body_chars(chars):
    return [
        c
        for c in chars
        if BODY_FONT_HINT in c["font"] and abs(c["size"] - BODY_SIZE_HINT) < 0.2
    ]


def group_vertical_lines(chars, pitch_hint=23.0):
    """以 x 中心分群為直排行（右至左），行內依 y 排序（上至下）。"""
    cols = defaultdict(list)
    for c in chars:
        xc = (c["bbox"][0] + c["bbox"][2]) / 2
        cols[round(xc / (pitch_hint / 2))].append(c)
    merged = defaultdict(list)
    for key, items in cols.items():
        xc = median((i["bbox"][0] + i["bbox"][2]) / 2 for i in items)
        merged[round(xc, 1)].extend(items)
    lines = []
    for xc in sorted(merged, reverse=True):  # 右至左
        col = sorted(merged[xc], key=lambda c: c["bbox"][1])  # 上至下
        lines.append((xc, col))
    return lines


def verify_order(chars):
    """驗證原始抽取順序是否等於重建的直排閱讀序。"""
    lines = group_vertical_lines(chars)
    rebuilt = [c for _, col in lines for c in col]
    raw = sorted(chars, key=lambda c: c["order"])
    same = [a["order"] for a in raw] == [b["order"] for b in rebuilt]
    return same, lines


def measure(lines):
    """量測字距、行距、行長、文字區塊 bbox。"""
    char_advances = []
    for _, col in lines:
        for a, b in zip(col, col[1:]):
            dy = round(b["origin"][1] - a["origin"][1], 3)
            if 0 < dy < 40:
                char_advances.append(dy)
    xs = [xc for xc, col in lines if len(col) >= 15]
    line_pitches = [round(a - b, 3) for a, b in zip(xs, xs[1:]) if 5 < a - b < 40]
    lengths = Counter(len(col) for _, col in lines)
    all_boxes = [c["bbox"] for _, col in lines for c in col]
    block = [
        min(b[0] for b in all_boxes),
        min(b[1] for b in all_boxes),
        max(b[2] for b in all_boxes),
        max(b[3] for b in all_boxes),
    ]
    return {
        "char_advance_pt": median(char_advances) if char_advances else None,
        "char_advance_samples": len(char_advances),
        "line_pitch_pt": median(line_pitches) if line_pitches else None,
        "line_pitch_samples": len(line_pitches),
        "chars_per_line_top3": lengths.most_common(3),
        "body_block_bbox": [round(v, 2) for v in block],
    }


def main():
    doc = fitz.open(PDF_PATH)
    page_index, body_count = pick_representative(doc)
    page = doc[page_index]
    rect = page.rect
    print(f"[1] 代表頁：index={page_index}（PDF 第 {page_index + 1} 頁），"
          f"尺寸 {rect.width:.1f}x{rect.height:.1f}pt "
          f"({rect.width / PT_PER_MM:.1f}x{rect.height / PT_PER_MM:.1f}mm)，"
          f"內文字元 {body_count}")

    chars = extract_chars(page)
    body = body_chars(chars)
    fonts = Counter(c["font"] for c in chars)
    print(f"[2] 全頁字元 {len(chars)}，字型分布：")
    for f, n in fonts.most_common():
        print(f"    {f}: {n}")

    same, lines = verify_order(body)
    print(f"[3] 內文原始抽序 == 直排閱讀序（右至左、上至下）：{same}")
    print(f"    內文行數：{len(lines)}")
    preview = "".join(c["c"] for c in lines[0][1])[:30] if lines else ""
    print(f"    第 1 行（最右）前 30 字：{preview}")

    m = measure(lines)
    m["page_index"] = page_index
    m["page_size_pt"] = [round(rect.width, 2), round(rect.height, 2)]
    m["extraction_order_ok"] = same
    tw = rect.width
    bb = m["body_block_bbox"]
    m["margins_mm"] = {
        "top": round(bb[1] / PT_PER_MM, 2),
        "bottom": round((rect.height - bb[3]) / PT_PER_MM, 2),
        "right": round((tw - bb[2]) / PT_PER_MM, 2),
        "left": round(bb[0] / PT_PER_MM, 2),
    }
    print(f"[4] 量測：字距 {m['char_advance_pt']}pt（{m['char_advance_samples']} 樣本）、"
          f"行距 {m['line_pitch_pt']}pt（{m['line_pitch_samples']} 樣本）")
    print(f"    每行字數 top3：{m['chars_per_line_top3']}")
    print(f"    版心 bbox：{bb}，四邊留白 mm：{m['margins_mm']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "reference_page.json").write_text(
        json.dumps({"page_index": page_index, "chars": chars}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (OUT_DIR / "measurements.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pix = page.get_pixmap(dpi=150)
    pix.save(OUT_DIR / "reference_page.png")
    print(f"[5] 產出：{OUT_DIR / 'reference_page.json'}")
    print(f"        {OUT_DIR / 'measurements.json'}")
    print(f"        {OUT_DIR / 'reference_page.png'}（150dpi）")


if __name__ == "__main__":
    main()
