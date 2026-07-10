"""Spike 2a preflight：頁面幾何盒、頁數、閱讀方向、渲染樣張。

檢查項（PLAN 第 9 節印前規格的 spike 子集）：
- 頁面尺寸：成品 148x210mm，出血後 154x216mm，TrimBox 置中
- 頁數與頁碼遞增（跨頁）
- 直排右翻閱讀方向（ViewerPreferences /Direction /R2L，或至少內容右至左）
- 渲染每頁 PNG 供目檢（禁則、縱中橫、頁碼）
"""
import sys
from pathlib import Path

import fitz

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
PDF = HERE / "out" / "spike2a-sample.pdf"
MM = 25.4 / 72


def main():
    doc = fitz.open(PDF)
    print(f"[1] 頁數：{doc.page_count}")
    for i, page in enumerate(doc):
        mb = page.mediabox
        print(f"    p{i + 1} MediaBox {mb.width * MM:.1f}x{mb.height * MM:.1f}mm", end="")
        for name in ("trimbox", "bleedbox", "cropbox"):
            try:
                box = getattr(page, name)
                print(f"  {name} {box.width * MM:.1f}x{box.height * MM:.1f}mm", end="")
            except Exception:
                pass
        print()

    cat_xref = doc.pdf_catalog()
    vp = doc.xref_get_key(cat_xref, "ViewerPreferences")
    direction = "無"
    if vp[0] == "dict":
        direction = vp[1]
    elif vp[0] == "xref":
        vp_xref = int(vp[1].split()[0])
        direction = doc.xref_get_key(vp_xref, "Direction")[1]
    print(f"[2] ViewerPreferences（閱讀方向）：{direction}")

    fonts = set()
    for i in range(doc.page_count):
        for f in doc.get_page_fonts(i):
            fonts.add((f[3], f[4]))
    print(f"[3] 使用字型：{sorted(fonts)}")

    out_dir = HERE / "out"
    for i, page in enumerate(doc):
        png = out_dir / f"spike2a_p{i + 1}.png"
        page.get_pixmap(dpi=150).save(png)
        print(f"[4] 渲染：{png}")


if __name__ == "__main__":
    main()
