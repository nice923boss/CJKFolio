"""Spike 7 PoC：向量原件（CIP 細框）最小驗證（honest-planning R2）。

只驗新交互點（premortem 風險 1〜3），不驗成熟部分：
- 風險 A：DeviceCMYK 描邊矩形（`0 0 0 1 K` + `w` + `re` + `S`）能被 PyMuPDF 獨立
  解析並渲染出框線像素，且 content 不觸發既有 preflight 的 `(rg|RG)` 內容流檢查。
- 風險 B：path ops 置於 BT／ET 文字物件之外（獨立 q…Q 圖形狀態塊）。
- 風險 C：PIL "L"（灰階）模式 ImageDraw 矩形 outline／width 像素行為。

紅線：框幾何全自擬（與參考書 p178 無關）。輸出 out/（gitignore）供目檢。
"""
import re
import sys
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageOps

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

# 既有 preflight.color-cmyk-only 的內容流 pattern（複製驗證，不 import 產品碼）
RG_PAT = re.compile(rb"(?:^|[\s\]>])(rg|RG)(?:$|[\s/%])")
CS_PAT = re.compile(r"/(DeviceRGB|CalRGB|CalGray|Lab|ICCBased)(?![A-Za-z0-9])")


def _min_pdf(content: bytes) -> bytes:
    """把單一 content stream 包成最小 PDF 1.3（手算 xref offset）。"""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]
    out = BytesIO()
    out.write(b"%PDF-1.3\n%\xe2\xe3\xcf\xd3\n")
    offs = []
    for i, body in enumerate(objs, 1):
        offs.append(out.tell())
        out.write(b"%d 0 obj\n%s\nendobj\n" % (i, body))
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offs:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objs) + 1, xref))
    return out.getvalue()


def probe_pdf_cmyk_frame() -> None:
    # 自擬框：左下 (40,40)、寬高 120×120，DeviceCMYK 純黑 0.5pt 描邊，BT／ET 之外
    content = (
        b"q\n0 0 0 1 K\n0.5 w\n40 40 120 120 re\nS\nQ\n"
    )
    pdf_bytes = _min_pdf(content)
    path = OUT / "cmyk-frame.pdf"
    path.write_bytes(pdf_bytes)

    doc = fitz.open(str(path))
    stream = doc.xref_stream(4) or b""
    assert b" re" in stream and b"\nS" in stream, "content 缺 re/S 路徑算符"
    assert b" K" in stream, "content 缺 CMYK 描邊算符 K"
    assert not RG_PAT.search(stream), "content 誤觸 (rg|RG) DeviceRGB 檢查"
    for x in range(1, doc.xref_length()):
        assert not CS_PAT.search(doc.xref_object(x) or ""), f"obj {x} 含 RGB 色彩空間"

    # 渲染：框線四邊應有著墨（灰階反相 bbox 貼近框範圍）
    pix = doc[0].get_pixmap(colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    ink = ImageOps.invert(img).getbbox()
    assert ink is not None, "CMYK 框未渲染出任何像素"
    # PDF y-up：top-down 影像中框約在 [40,40]～[160,160]（200 高，y 翻轉後對稱）
    assert ink[0] <= 42 and ink[1] <= 42 and ink[2] >= 158 and ink[3] >= 158, \
        f"框像素範圍 {ink} 與預期 40～160 不符"
    doc.close()
    print(f"[A] CMYK 描邊框 PDF：re/S/K 齊備、無 rg/RG、渲染框像素 bbox={ink} → {path.name}")


def probe_pil_frame() -> None:
    # 風險 C：PIL "L" 模式畫框（框線 outline=0 純黑、width=2）
    img = Image.new("L", (200, 200), 255)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 160, 160], outline=0, width=2)
    path = OUT / "pil-frame.png"
    img.save(path)
    ink = ImageOps.invert(img).getbbox()
    assert ink is not None, "PIL 框未著墨"
    assert ink[0] <= 41 and ink[3] >= 159, f"PIL 框像素範圍 {ink} 與預期不符"
    # 框內部應留白（中心點為白 255）
    assert img.getpixel((100, 100)) == 255, "框內部不應著墨（描邊非填色）"
    print(f"[C] PIL 'L' 描邊框：bbox={ink}、中心留白 → {path.name}")


if __name__ == "__main__":
    probe_pdf_cmyk_frame()
    probe_pil_frame()
    print("Spike 7 PoC 全數通過：CMYK 描邊向量原件可行，preflight color 檢查不退步。")
