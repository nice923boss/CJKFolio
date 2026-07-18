"""Spike 18：CMYK 影像自來源檔到 PDF 的分量往返驗證（Sprint 92）。

premortem 第 1 條的具體檢驗：PIL 讀 CMYK 影像的分量值，與寫進 PDF
`/DeviceCMYK` 影像 XObject 後由獨立解碼器（PyMuPDF）讀回的值，是否一致。

三組樣本：
  synth-tiff  合成 CMYK TIFF（白／黑／純青／純洋紅四色塊，極值可手算）
  book-tiff   真書送印稿抽出的 DeviceCMYK 影像存為 TIFF（A 級真實印刷素材）
  book-jpeg   同一張影像存為 JPEG（Adobe APP14 容器，反相風險所在）

紅線：真書影像只存於本 spike 的 out/（.gitignore 已含 spikes/*/out/），不入 repo。
用法（自 repo 根）：python spikes/spike18-cmyk-image/probe_cmyk_roundtrip.py
"""
import sys
import zlib
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
sys.path.insert(0, str(ROOT))

REFERENCE_CANDIDATES = (ROOT / "內在整理-20260312.pdf",
                        ROOT / "local" / "內在整理-20260312.pdf")
BOOK_CMYK_XREF = 156      # tools/measure_cmyk_images.py 實測：DeviceCMYK 881×588 /FlateDecode
BOOK_DCT_XREF = 557       # 同上：DeviceCMYK 881×588 /DCTDecode（Adobe 產製 CMYK JPEG）


def _reference_pdf() -> Path:
    for cand in REFERENCE_CANDIDATES:
        if cand.exists():
            return cand
    raise SystemExit("找不到參考書交印檔（本機素材）")


def make_synth() -> Path:
    """合成 CMYK TIFF：四個色塊，值可手算（白 0,0,0,0／黑 0,0,0,255）。"""
    im = Image.new("CMYK", (4, 1))
    im.putpixel((0, 0), (0, 0, 0, 0))          # 白（無墨）
    im.putpixel((1, 0), (0, 0, 0, 255))        # 單 K 黑
    im.putpixel((2, 0), (255, 0, 0, 0))        # 純青
    im.putpixel((3, 0), (0, 255, 0, 0))        # 純洋紅
    path = OUT / "synth.tif"
    im.save(path)
    return path


def extract_book_image() -> tuple:
    """自真書抽一張 DeviceCMYK 影像的**原始四分量位元組**，存 TIFF 與 JPEG 兩容器。

    不用 `extract_image`（它會把 CMYK 轉成 RGB PNG，等於先失真再由本 spike naive
    轉回，量到的是自己的轉換誤差而非寫出正確性）；改讀 `xref_stream`（PyMuPDF 只
    解 FlateDecode 濾器，不動色彩），據 Width/Height 直接組回 PIL CMYK 影像。
    """
    doc = fitz.open(_reference_pdf())
    raw = doc.xref_stream(BOOK_CMYK_XREF)
    w = int(doc.xref_get_key(BOOK_CMYK_XREF, "Width")[1])
    h = int(doc.xref_get_key(BOOK_CMYK_XREF, "Height")[1])
    cs = doc.xref_get_key(BOOK_CMYK_XREF, "ColorSpace")[1]
    doc.close()
    print(f"  真書影像 xref {BOOK_CMYK_XREF}：{cs} {w}×{h}、原始資料 {len(raw)} bytes"
          f"（＝{w * h * 4} 期望值：{len(raw) == w * h * 4}）")
    im = Image.frombytes("CMYK", (w, h), raw)
    tif, jpg = OUT / "book.tif", OUT / "book.jpg"
    im.save(tif)
    im.save(jpg, quality=95)
    return tif, jpg


def write_pdf(pil_cmyk: Image.Image, path: Path) -> None:
    """以本產品的影像 XObject 形態寫一頁 PDF（最小手寫 PDF，與 pdf_writer 同形態）。

    刻意不呼叫產品層：spike 的目的是先確定「PIL 分量 → /DeviceCMYK 位元組」這條
    對映本身正確，再據此決定產品層怎麼寫。
    """
    w, h = pil_cmyk.size
    data = zlib.compress(pil_cmyk.tobytes())
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
        b"/Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>",
        (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
         f"/ColorSpace /DeviceCMYK /BitsPerComponent 8 /Filter /FlateDecode "
         f"/Length {len(data)} >>\nstream\n").encode() + data + b"\nendstream",
        None,   # 內容流稍後填
    ]
    content = b"q 100 0 0 100 0 0 cm /Im1 Do Q"
    objs[4] = f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"

    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(buf)
    buf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n"
            f"{xref_at}\n%%EOF\n").encode()
    path.write_bytes(bytes(buf))


def roundtrip(label: str, src: Path) -> bool:
    """來源檔 → PDF → PyMuPDF 獨立讀回原始分量位元組，逐分量比對。回傳是否一致。

    Gate 4 獨立路徑：比對的是 PDF 影像 XObject 解 Flate 後的四分量位元組，不經任何
    色彩轉換（`extract_image` 會轉 RGB，量到的會是轉換誤差而非寫出正確性）。
    """
    src_im = Image.open(src)
    print(f"  [{label}] 來源容器 {src.suffix}、PIL mode {src_im.mode}")
    if src_im.mode != "CMYK":
        print(f"  [{label}] 來源非 CMYK mode，跳過")
        return False
    pdf_path = OUT / f"{label}.pdf"
    write_pdf(src_im, pdf_path)

    doc = fitz.open(pdf_path)
    xref = doc[0].get_images(full=True)[0][0]
    cs_ok, cs = doc.xref_get_key(xref, "ColorSpace")
    back_raw = doc.xref_stream(xref)
    doc.close()

    src_raw = src_im.tobytes()
    same = src_raw == back_raw
    inverted = bytes(255 - b for b in src_raw) == back_raw
    px = lambda raw: [tuple(raw[i:i + 4]) for i in range(0, min(16, len(raw)), 4)]
    print(f"  [{label}] PDF /ColorSpace＝{cs}（{cs_ok}）、資料 {len(back_raw)} bytes")
    print(f"  [{label}] 來源首四像素 {px(src_raw)}")
    print(f"  [{label}] 讀回首四像素 {px(back_raw)}")
    print(f"  [{label}] 逐分量相等：{same}　整體反相：{inverted}")
    if not same:
        diffs = sum(1 for a, b in zip(src_raw, back_raw) if a != b)
        print(f"  [{label}] 不符分量 {diffs}/{len(src_raw)}")
    return same


def adobe_jpeg_check() -> bool:
    """真書內 Adobe 產製的 CMYK JPEG（/DCTDecode）原封取出交 PIL 讀，驗反相語意。

    premortem 第 1 條的核心風險是「Adobe 寫的 CMYK JPEG 帶 APP14 且分量反相」。
    步驟 2 的 JPEG 由 PIL 自存自讀（自洽不足以證明），本檢查改用真書送印稿裡由
    Adobe PDF Library 寫入的 DCT 串流，且真書恰有同尺寸的 FlateDecode 版本
    （xref 156，未壓縮的原始 CMYK 分量）可作對照組。
    """
    doc = fitz.open(_reference_pdf())
    dct = doc.xref_stream_raw(BOOK_DCT_XREF)      # 不解 DCT，取原始 JPEG 位元組
    # 獨立基準：PyMuPDF 自行解 DCT 並輸出 RGB（同一張影像，非另一張同尺寸照片；
    # 跨 xref 比對會把「不同照片」誤判成「反相」）
    ref_rgb = fitz.Pixmap(doc, BOOK_DCT_XREF)
    if ref_rgb.colorspace.n != 3:
        ref_rgb = fitz.Pixmap(fitz.csRGB, ref_rgb)
    ref_bytes = ref_rgb.samples
    doc.close()

    path = OUT / "book_adobe.jpg"
    path.write_bytes(dct)
    im = Image.open(path)
    has_adobe = b"Adobe" in dct[:4096]
    print(f"  xref {BOOK_DCT_XREF} 原始 JPEG {len(dct)} bytes、含 APP14 Adobe 標記："
          f"{has_adobe}、PIL mode {im.mode}、尺寸 {im.size}")
    if im.mode != "CMYK":
        print("  PIL 未以 CMYK 開啟，僅報告不比對")
        return False

    # 兩個假設各自換算成 RGB，與 PyMuPDF 的 RGB 解碼比對：
    #   墨量語意（ink）  ：R = (255−C)(255−K)/255
    #   反相語意（inverted）：先取 255−值 再套同式
    raw = im.tobytes()
    err_ink = err_inv = 0
    n = len(ref_bytes) // 3
    for i in range(0, n, max(1, n // 20000)):     # 抽樣兩萬點，足夠分辨兩假設
        c, m, y, k = raw[i * 4:i * 4 + 4]
        for chan, ink_v in enumerate((
                (255 - c) * (255 - k) // 255,
                (255 - m) * (255 - k) // 255,
                (255 - y) * (255 - k) // 255)):
            ref = ref_bytes[i * 3 + chan]
            err_ink += abs(ink_v - ref)
            ic, im_, iy, ik = 255 - c, 255 - m, 255 - y, 255 - k
            inv_v = ((255 - (ic, im_, iy)[chan]) * (255 - ik)) // 255
            err_inv += abs(inv_v - ref)
    same = err_ink < err_inv
    total = len(range(0, n, max(1, n // 20000))) * 3
    print(f"  對 PyMuPDF RGB 解碼的平均誤差（墨量語意）：{err_ink / total:.2f}／255")
    print(f"  對 PyMuPDF RGB 解碼的平均誤差（反相語意）：{err_inv / total:.2f}／255")
    print(f"  判定：{'墨量語意（PIL 已正規化 Adobe 反相）' if same else '反相（需自行補正）'}")
    return same


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)

    print("== 1. 合成 CMYK TIFF（極值可手算）==")
    synth_ok = roundtrip("synth-tiff", make_synth())

    print("== 2. 真書 DeviceCMYK 影像（A 級真實印刷素材）==")
    tif, jpg = extract_book_image()
    tif_ok = roundtrip("book-tiff", tif)
    jpg_ok = roundtrip("book-jpeg", jpg)

    print("== 3. 容器語意一致性：同一張圖 TIFF 與 JPEG 兩容器 PIL 讀值是否同義 ==")
    t_raw = Image.open(tif).tobytes()
    j_raw = Image.open(jpg).tobytes()
    mean_abs = sum(abs(a - b) for a, b in zip(t_raw, j_raw)) / len(t_raw)
    mean_inv = sum(abs(255 - a - b) for a, b in zip(t_raw, j_raw)) / len(t_raw)
    print(f"  平均分量差（同義假設）：{mean_abs:.2f}／255")
    print(f"  平均分量差（反相假設）：{mean_inv:.2f}／255")
    print(f"  判定：{'同義（JPEG 僅有失真誤差）' if mean_abs < mean_inv else '反相'}")

    print("== 4. Adobe 產製 CMYK JPEG：真書 /DCTDecode 影像原封取出交 PIL 讀 ==")
    adobe_ok = adobe_jpeg_check()

    print("== 5. 白區極值檢查（CMYK 白＝0,0,0,0，反相則為 255,255,255,255）==")
    white = Image.open(OUT / "synth.tif").getpixel((0, 0))
    print(f"  合成圖白色塊 PIL 讀值 {white}　（期望 (0, 0, 0, 0)）")

    print("== 結論 ==")
    print(f"  合成 TIFF 往返一致：{synth_ok}")
    print(f"  真書 TIFF 往返一致：{tif_ok}")
    print(f"  真書 JPEG 往返一致：{jpg_ok}")
    print(f"  Adobe CMYK JPEG 語意同義（非反相）：{adobe_ok}")


if __name__ == "__main__":
    main()
