"""量測參考書送印稿的油墨總量 TAC（Phase 4 TAC 檢核 R1，Sprint 93）。

§9 印前硬條件「總墨量 ≤ 320〜340%」是印廠條件（紙張吸墨與乾燥上限），不是 ISO
15930-1 條款。實作檢核前必須先確定的三件事，本工具以真書送印稿逐張取一手證據：

  1. 真實送印稿的影像 TAC 實際落在哪（最大值是否真的 ≤ 320？超標像素佔比多少？）
  2. 向量與文字著色的 TAC（內文單 K 有多重、是否有富黑大標）
  3. 哪些色彩空間形態需要換算（DeviceCMYK 直接相加；DeviceN 單黑版與 Indexed
     需經 PyMuPDF 的 tint transform 還原成裝置色）

紅線：只取**聚合統計**（最大值、分位數、超標像素佔比），不抽取、不輸出任何像素
內容或圖像。輸出 assets/reference/ink_coverage_measurements.json（本機不入 repo）
＋終端摘要。

PyMuPDF 為解碼基準（非 PIL）：spike18 已實測 PIL 對 Adobe YCCK CMYK JPEG 讀出負片，
而 PyMuPDF 的 DCT 解碼正確，故真書 DCT 影像的墨量須由 PyMuPDF 解。

用法（自 repo 根）：python tools/measure_ink_coverage.py [PDF路徑]
"""
import collections
import re

import fitz

from _measure_common import reference_pdf, stdout_utf8, write_measurements

# 取樣上限：逐張全像素相加對 179 頁送印稿約數億像素，統計意義上不需要全掃。
# 以 Pixmap 縮圖取樣會經內插而改變極值，故不縮圖，改逐列跳讀（步長 STRIDE）。
STRIDE = 3


def _tac_stats(pix: fitz.Pixmap) -> dict:
    """單張影像的 TAC 聚合統計（百分比）。回傳 None 表示色彩空間不可判墨量。"""
    n = pix.n - pix.alpha
    samples = pix.samples
    w, h, stride = pix.width, pix.height, pix.stride
    if n not in (1, 4):
        return {"colorspace_n": n, "supported": False}

    hist = collections.Counter()          # TAC 百分比（整數）→ 像素數
    for y in range(0, h, STRIDE):
        row = samples[y * stride: y * stride + w * pix.n]
        for x in range(0, w, STRIDE):
            base = x * pix.n
            if n == 4:                    # DeviceCMYK：四分量即墨量
                total = row[base] + row[base + 1] + row[base + 2] + row[base + 3]
            else:                          # DeviceGray：0＝全黑，墨量＝255−值
                total = 255 - row[base]
            hist[round(total / 2.55)] += 1

    counted = sum(hist.values())
    ordered = sorted(hist)
    cumulative, quantiles = 0, {}
    for q in (0.5, 0.99, 0.999):
        target = counted * q
        acc = 0
        for value in ordered:
            acc += hist[value]
            if acc >= target:
                quantiles[str(q)] = value
                break
    cumulative = sum(count for value, count in hist.items() if value > 320)
    over_340 = sum(count for value, count in hist.items() if value > 340)
    return {
        "colorspace_n": n,
        "supported": True,
        "sampled_px": counted,
        "max_tac": ordered[-1] if ordered else 0,
        "median_tac": quantiles.get("0.5", 0),
        "p99_tac": quantiles.get("0.99", 0),
        "p999_tac": quantiles.get("0.999", 0),
        "px_over_320": cumulative,
        "px_over_340": over_340,
    }


def _vector_colors(doc: fitz.Document) -> list:
    """全書內容流的 CMYK 著色運算子（k 填色／K 描邊）與其 TAC。"""
    pat = re.compile(
        rb"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(k|K)(?:$|[\s/\[])")
    counts: collections.Counter = collections.Counter()
    for page in doc:
        data = b""
        for cx in page.get_contents():
            data += (doc.xref_stream(cx) or b"") + b"\n"
        for m in pat.finditer(data):
            cmyk = tuple(round(float(m.group(i)), 4) for i in range(1, 5))
            counts[(cmyk, m.group(5).decode())] += 1
    return [
        {"cmyk": list(cmyk), "op": op, "uses": uses,
         "tac": round(sum(cmyk) * 100, 1)}
        for (cmyk, op), uses in counts.most_common()
    ]


def main() -> None:
    stdout_utf8()
    path = reference_pdf()
    doc = fitz.open(path)

    images, seen = [], {}
    for pno in range(doc.page_count):
        for info in doc[pno].get_image_info(xrefs=True):
            xref = info.get("xref", 0)
            if xref <= 0 or xref in seen:
                continue
            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception as e:                       # 不可解碼者誠實記錄
                seen[xref] = {"xref": xref, "error": str(e)}
                images.append(seen[xref])
                continue
            stats = _tac_stats(pix)
            stats.update({"xref": xref, "first_pdf_page": pno + 1,
                          "px": [pix.width, pix.height],
                          "colorspace": info.get("cs-name", "")})
            seen[xref] = stats
            images.append(stats)
            pix = None

    vectors = _vector_colors(doc)
    usable = [im for im in images if im.get("supported")]
    by_cs: collections.Counter = collections.Counter(
        im.get("colorspace", "") for im in usable)

    data = {
        "source": path,
        "pages": doc.page_count,
        "unique_images": len(images),
        "measured_images": len(usable),
        "stride": STRIDE,
        "images": images,
        "vector_colors": vectors,
    }
    out = write_measurements("ink_coverage_measurements.json", data)

    print(f"來源：{path}（{doc.page_count} 頁）")
    print(f"獨立影像 {len(images)} 張，可判墨量 {len(usable)} 張：{dict(by_cs)}")
    if usable:
        worst = max(usable, key=lambda im: im["max_tac"])
        over320 = [im for im in usable if im["max_tac"] > 320]
        over340 = [im for im in usable if im["max_tac"] > 340]
        print(f"影像 TAC 最大值：{worst['max_tac']}%"
              f"（xref {worst['xref']} PDF {worst['first_pdf_page']} "
              f"{worst['colorspace']} {worst['px'][0]}×{worst['px'][1]}）")
        print(f"最大 TAC > 320% 的影像：{len(over320)} 張；> 340%：{len(over340)} 張")
        print("逐張（依最大 TAC 降序，前 20）：")
        for im in sorted(usable, key=lambda i: -i["max_tac"])[:20]:
            print(f"  xref {im['xref']:>4} PDF {im['first_pdf_page']:>3} "
                  f"{im['colorspace']:<12} max {im['max_tac']:>3}% "
                  f"p99.9 {im['p999_tac']:>3}% 中位 {im['median_tac']:>3}% "
                  f"超 320 像素 {im['px_over_320']}／{im['sampled_px']}")
    print(f"向量／文字著色 {len(vectors)} 種（依使用次數）：")
    for v in vectors[:12]:
        print(f"  {v['op']} {v['cmyk']} TAC {v['tac']}% ×{v['uses']}")
    if vectors:
        top = max(vectors, key=lambda v: v["tac"])
        print(f"向量最高 TAC：{top['tac']}%（{top['op']} {top['cmyk']}）")
    print(f"量測 JSON：{out}")
    doc.close()


if __name__ == "__main__":
    main()
