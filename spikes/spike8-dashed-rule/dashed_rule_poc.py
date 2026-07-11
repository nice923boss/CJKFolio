"""Spike 8 PoC：虛線原件（目錄水平虛線）最小驗證（honest-planning R2）。

只驗新交互點（premortem 風險 1〜3），不驗成熟部分：
- 風險 A：PDF dash 算符（`[ 3 2 ] 0 d`）＋灰 K 描邊（`0 0 0 0.57 K`）能被 PyMuPDF
  獨立解析（get_drawings 回報 dashes）並渲染出「斷續」線段像素（on 段有墨、off 段
  無墨），且 content 不觸發既有 preflight 的 `(rg|RG)` 內容流檢查。
- 風險 B：dash 狀態置於獨立 q…Q 塊（BT／ET 之外），不洩漏到後續文字狀態。
- 風險 C：PIL "L" 模式手動分段虛線的 on/off 像素節奏與灰值（255×(1−k)）。

紅線：樣線幾何自擬（dash 節奏 [3 2] 為參考書量測「參數」，可用）。輸出 out/（gitignore）。
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
    """把單一 content stream 包成最小 PDF 1.3（手算 xref offset，同 spike7）。"""
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


def probe_pdf_dash_line() -> None:
    # 自擬水平虛線：y=100、x 20〜180，灰 K57 描邊 1pt，dash [3 2]，BT／ET 之外
    content = (
        b"q\n0 0 0 0.57 K\n1 w\n[ 3 2 ] 0 d\n20 100 m\n180 100 l\nS\nQ\n"
    )
    pdf_bytes = _min_pdf(content)
    path = OUT / "dash-line.pdf"
    path.write_bytes(pdf_bytes)

    doc = fitz.open(str(path))
    stream = doc.xref_stream(4) or b""
    assert b" d\n" in stream and b" m\n" in stream and b" l\n" in stream, "content 缺 d/m/l 算符"
    assert b" K" in stream, "content 缺 CMYK 描邊算符 K"
    assert not RG_PAT.search(stream), "content 誤觸 (rg|RG) DeviceRGB 檢查"
    for x in range(1, doc.xref_length()):
        assert not CS_PAT.search(doc.xref_object(x) or ""), f"obj {x} 含 RGB 色彩空間"

    # 獨立解析：dashes 應被回報
    draws = doc[0].get_drawings()
    assert len(draws) == 1, f"預期 1 條 draw，得到 {len(draws)}"
    dashes = draws[0].get("dashes")
    assert dashes and "3" in dashes and "2" in dashes, f"dashes 未解析：{dashes!r}"

    # 渲染（4x）：線上 on 段有墨、off 段無墨（斷續）；灰值非黑非白
    mat = fitz.Matrix(4, 4)
    pix = doc[0].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    # PDF y-up 100 → 影像 y=(200−100)×4=400；掃該列 x 20×4〜180×4
    row = [img.getpixel((x, 400)) for x in range(80, 720)]
    ink = [v for v in row if v < 250]
    white_runs = sum(1 for a, b in zip(row, row[1:]) if a >= 250 and b < 250)
    assert ink, "虛線未渲染出任何像素"
    assert white_runs >= 10, f"線段未斷續（white→ink 轉換僅 {white_runs} 次，dash 沒生效）"
    gray = sorted(ink)[len(ink) // 2]
    assert 60 <= gray <= 180, f"灰值 {gray} 不在灰域（預期 ≈255×(1−0.57)≈110）"
    doc.close()
    print(f"[A] PDF dash 線：d/m/l/K 齊備、無 rg/RG、dashes={dashes!r}、"
          f"斷續 {white_runs} 段、中位灰值 {gray} → {path.name}")


def probe_pdf_dash_isolated() -> None:
    # 風險 B：dash 在 q…Q 內，Q 之後再畫第二條「無 dash」線，應為連續實線
    content = (
        b"q\n0 0 0 1 K\n1 w\n[ 3 2 ] 0 d\n20 120 m\n180 120 l\nS\nQ\n"
        b"q\n0 0 0 1 K\n1 w\n20 80 m\n180 80 l\nS\nQ\n"
    )
    path = OUT / "dash-isolated.pdf"
    path.write_bytes(_min_pdf(content))
    doc = fitz.open(str(path))
    mat = fitz.Matrix(4, 4)
    pix = doc[0].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    row_dash = [img.getpixel((x, (200 - 120) * 4)) for x in range(80, 720)]
    row_solid = [img.getpixel((x, (200 - 80) * 4)) for x in range(80, 720)]
    runs_dash = sum(1 for a, b in zip(row_dash, row_dash[1:]) if a >= 250 and b < 250)
    runs_solid = sum(1 for a, b in zip(row_solid, row_solid[1:]) if a >= 250 and b < 250)
    assert runs_dash >= 10, f"dash 線未斷續（{runs_dash}）"
    assert runs_solid <= 1, f"q…Q 後實線被 dash 汙染（斷續 {runs_solid} 段）"
    doc.close()
    print(f"[B] dash 狀態隔離：q…Q 內斷續 {runs_dash} 段、Q 後實線連續（{runs_solid} 轉換）")


def probe_pil_dash_line() -> None:
    # 風險 C：PIL "L" 手動分段虛線（on 3px 畫、off 2px 空，灰值 110）
    img = Image.new("L", (200, 200), 255)
    draw = ImageDraw.Draw(img)
    y, x0, x1, on, off, gray = 100, 20, 180, 3, 2, 110
    x = x0
    while x < x1:
        draw.line([(x, y), (min(x + on - 1, x1), y)], fill=gray, width=1)
        x += on + off
    path = OUT / "pil-dash.png"
    img.save(path)
    row = [img.getpixel((x, y)) for x in range(x0, x1 + 1)]
    ink = [v for v in row if v < 250]
    runs = sum(1 for a, b in zip(row, row[1:]) if a >= 250 and b < 250)
    assert ink and runs >= 10, f"PIL 虛線節奏異常（ink={len(ink)}、轉換 {runs}）"
    assert all(v == gray for v in ink), f"PIL 灰值不一致：{sorted(set(ink))}"
    print(f"[C] PIL 'L' 分段虛線：{len(ink)} ink px、斷續 {runs} 段、灰值 {gray} → {path.name}")


if __name__ == "__main__":
    probe_pdf_dash_line()
    probe_pdf_dash_isolated()
    probe_pil_dash_line()
    print("Spike 8 PoC 全數通過：dash 虛線原件（PDF d 算符＋PIL 分段）可行，color 檢查不退步。")
