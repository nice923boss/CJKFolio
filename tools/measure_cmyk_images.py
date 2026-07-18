"""量測參考書送印稿的置入影像色彩空間形態（Phase 4 彩色 CMYK 影像 R1，Sprint 92）。

§1 逆向分析記「78 張灰階＋16 張 CMYK」，本工具對真書全書逐次置入取一手機器證據，
回答實作彩色影像置入前必須先確定的四件事：

  1. 彩色影像實際用哪個色彩空間（DeviceCMYK？ICCBased？Indexed？）
  2. 每分量位元數（BitsPerComponent）與濾器（Filter）形態
  3. 是否帶 /Decode 反相陣列（Adobe CMYK JPEG 的已知形態，決定本產品寫出時是否需比照）
  4. 是否帶 SMask 透明（X-1a 禁透明，若真書有則需知道其處置）

紅線：只讀影像的結構屬性與尺寸，不抽取像素、不輸出任何圖像內容。輸出
assets/reference/cmyk_image_measurements.json（本機不入 repo）＋終端摘要。
用法（自 repo 根）：python tools/measure_cmyk_images.py [PDF路徑]
"""
import collections

import fitz

from _measure_common import reference_pdf, stdout_utf8, write_measurements


def _image_dict(doc: fitz.Document, xref: int) -> dict:
    """取影像 XObject 的原始字典屬性（不解碼像素）。"""
    keys = ("ColorSpace", "BitsPerComponent", "Filter", "Decode", "SMask",
            "Width", "Height", "DecodeParms")
    out = {}
    for key in keys:
        ok, value = doc.xref_get_key(xref, key)
        if ok != "null":
            out[key] = value
    return out


def main() -> None:
    stdout_utf8()
    path = reference_pdf()
    doc = fitz.open(path)

    placements = []          # 逐次置入（同一 xref 可跨頁多次）
    by_xref: dict = {}
    for pno in range(doc.page_count):
        page = doc[pno]
        for info in page.get_image_info(xrefs=True):
            xref = info.get("xref", 0)
            if xref <= 0:
                continue
            if xref not in by_xref:
                by_xref[xref] = _image_dict(doc, xref)
            attrs = by_xref[xref]
            placements.append({
                "pdf_page": pno + 1,
                "xref": xref,
                "px": [info["width"], info["height"]],
                "colorspace": info.get("cs-name", ""),
                "bpc": info.get("bpc", 0),
                "raw_colorspace": attrs.get("ColorSpace", ""),
                "filter": attrs.get("Filter", ""),
                "decode": attrs.get("Decode", ""),
                "smask": attrs.get("SMask", ""),
            })

    cs_counts = collections.Counter(p["colorspace"] for p in placements)
    raw_counts = collections.Counter(p["raw_colorspace"] for p in placements)
    filter_counts = collections.Counter(p["filter"] for p in placements)
    bpc_counts = collections.Counter(p["bpc"] for p in placements)
    decoded = [p for p in placements if p["decode"]]
    smasked = [p for p in placements if p["smask"]]

    colour = [p for p in placements if p["colorspace"] not in ("DeviceGray",)]
    unique_colour = {p["xref"] for p in colour}

    data = {
        "source": path,
        "pages": doc.page_count,
        "placements": len(placements),
        "unique_images": len(by_xref),
        "colorspace_counts": dict(cs_counts),
        "raw_colorspace_counts": dict(raw_counts),
        "filter_counts": dict(filter_counts),
        "bpc_counts": {str(k): v for k, v in bpc_counts.items()},
        "with_decode": len(decoded),
        "with_smask": len(smasked),
        "colour_placements": len(colour),
        "colour_unique_images": len(unique_colour),
        "colour_detail": colour,
    }
    out = write_measurements("cmyk_image_measurements.json", data)

    print(f"來源：{path}（{doc.page_count} 頁）")
    print(f"置入次數 {len(placements)}、獨立影像 {len(by_xref)} 張")
    print("色彩空間分佈（逐次置入）：")
    for name, count in cs_counts.most_common():
        print(f"  {name or '(未知)'}: {count}")
    print("原始 /ColorSpace 值：")
    for name, count in raw_counts.most_common():
        print(f"  {name or '(無)'}: {count}")
    print("濾器：")
    for name, count in filter_counts.most_common():
        print(f"  {name or '(無)'}: {count}")
    print(f"位元數：{dict(bpc_counts)}")
    print(f"帶 /Decode 反相陣列：{len(decoded)}　帶 /SMask 透明：{len(smasked)}")
    print(f"非灰階置入 {len(colour)} 次（{len(unique_colour)} 張獨立影像）")
    for p in colour[:20]:
        print(f"  PDF {p['pdf_page']:>3} xref {p['xref']:>4} "
              f"{p['px'][0]}×{p['px'][1]} {p['colorspace']} "
              f"bpc={p['bpc']} filter={p['filter'] or '-'} "
              f"decode={p['decode'] or '-'} smask={p['smask'] or '-'}")
    print(f"量測 JSON：{out}")
    doc.close()


if __name__ == "__main__":
    main()
