"""量測參考書個案扉頁（C 主版）大標置位幾何（GAPS #13，Sprint 25）。

掃全 PDF 找個案扉頁：右半頁（偶數＝右頁）頂部含個案大標
（NotoSansCJKtc-Medium 17.9pt，首字 top < 115pt）者。對每頁量大標列逐字
行軸／字距、內文首字（版心天頭驗證承 A）、Case 編號（PepitaMT 頁腳）、
資訊列 span 數。輸出 assets/reference/case_measurements.json（本機不入 repo）
＋終端摘要，供 C 主版大標行軸推導（比照 Sprint 20 部扉）。
用法（自 repo 根）：python tools/measure_case_page.py [PDF路徑]
"""
import json
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
HALF_W = 419.53          # 148mm，跨頁半寬（pt）
PT_PER_MM = 72.0 / 25.4
TITLE_SIZE = 17.9        # 個案大標 NotoSansCJKtc-Medium（§4.2）
TITLE_TOP_MAX = 115.0    # 扉頁大標起於頁頂（濾除內頁中段大標）


def _spans(page) -> list:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                out.append(s)
    return out


def measure_case(page, idx: int) -> dict | None:
    sp = _spans(page)
    title = [s for s in sp if abs(s["size"] - TITLE_SIZE) < 0.5
             and not s["font"].startswith(("Times", "Pepita"))]
    if not title:
        return None
    # 大標須在右半（右頁）且起於頁頂（扉頁，非內頁中段大標）
    title = [s for s in title if (s["bbox"][0] + s["bbox"][2]) / 2 > HALF_W]
    if not title:
        return None
    tcol = sorted(title, key=lambda s: s["bbox"][1])
    if tcol[0]["bbox"][1] > TITLE_TOP_MAX:
        return None

    def h(v: float) -> float:
        return v - HALF_W

    t0 = tcol[0]
    tops = [s["bbox"][1] for s in tcol]
    pitch = round((tops[-1] - tops[0]) / (len(tops) - 1), 2) if len(tops) > 1 else None
    body = [s for s in sp if s["font"].startswith("DFMingStd") and 11 < s["size"] < 12]
    body_top = min((s["bbox"][1] for s in body), default=None)
    pep = [s for s in sp if s["font"].startswith("Pepita")]
    info = [s for s in sp if s["font"].startswith("NotoSans") and 11 < s["size"] < 12]
    return {
        "page_index": idx,
        "title_text": "".join(s["text"] for s in tcol),
        "title_chars": len(tcol),
        "title_size": round(t0["size"], 2),
        "title_first_top": round(t0["bbox"][1], 2),
        "title_cx_half": round(h((t0["bbox"][0] + t0["bbox"][2]) / 2), 2),
        "title_x0_full": round(t0["bbox"][0], 2),
        "title_pitch_pt": pitch,
        "body_first_top": round(body_top, 2) if body_top is not None else None,
        "case_no": [{"t": s["text"], "x0_full": round(s["bbox"][0], 1),
                     "top": round(s["bbox"][1], 1), "size": round(s["size"], 1)}
                    for s in pep],
        "info_span_count": len(info),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    pdf = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "內在整理-20260312.pdf")
    doc = fitz.open(pdf)
    results = []
    for idx in range(len(doc)):
        page = doc[idx]
        if page.rect.width < HALF_W * 1.5:   # 單頁（首末）跳過
            continue
        r = measure_case(page, idx)
        if r:
            results.append(r)
    if not results:
        print("未找到個案扉頁大標")
        return 1
    out = ROOT / "assets" / "reference" / "case_measurements.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in results:
        top_mm = r["title_first_top"] / PT_PER_MM
        print(f"== PDF {r['page_index']}　大標「{r['title_text'][:14]}」"
              f"{r['title_size']}pt × {r['title_chars']} 字 ==")
        print(f"   首字 top={r['title_first_top']}（{top_mm:.2f}mm）cx(半)={r['title_cx_half']} "
              f"整頁 x0={r['title_x0_full']} pitch={r['title_pitch_pt']}")
        print(f"   內文首字 top={r['body_first_top']}（A 天頭 92.09pt）"
              f"　資訊 span={r['info_span_count']}　Case={[c['t'] for c in r['case_no']]}")
    print(f"共 {len(results)} 個案扉頁　量測 JSON → {out}（本機，不入 repo）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
