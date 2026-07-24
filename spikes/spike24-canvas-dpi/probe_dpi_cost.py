"""Spike 24（Sprint 133）：畫布底圖的解析度與耗時，決定「清晰預覽」的架構。

要回答的三個問題（架構取決於數字，不是取決於想像）：

  1. 單頁底圖在 150／225／300／450／600dpi 各要多久？
     → 若某級數在互動可察閾值（≈100ms）內，該級可同步重繪；超過就必須背景執行緒。
  2. 記憶體：一頁 pixmap 在各 dpi 佔多少？
     → 決定 clamp 上限（畫布同時最多持兩頁＝對頁檢視）。
  3. 高 dpi 底圖縮回 150dpi 的 scene 尺寸後，畫面上真的更清晰嗎？
     → 產出對照圖供 Gate 1 目視：同一區域在「150dpi 放大 3 倍」與
       「450dpi 縮放顯示」下的墨跡邊緣。

素材一律自擬（版權紅線）：samples/paiban-xiaoji-ch1.doc.json。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from cjkfolio.document import load_document  # noqa: E402
from cjkfolio.render import PageRenderer  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from cjkfolio.wrap import layout_with_wrap  # noqa: E402

DPI_LEVELS = (150, 225, 300, 450, 600)
OUT = Path(__file__).resolve().parent / "out"


def main() -> int:
    template = load_template(ROOT / "templates" / "neizai-zhengli.json")
    doc = load_document(ROOT / "samples" / "paiban-xiaoji-ch1.doc.json")
    layout = layout_with_wrap(doc, template)
    page = layout.pages[1]  # 第二頁＝滿版內文（字最多，是最壞情況）
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"素材：《排版小記》第一章，取版面頁 {page.number}"
          f"（滿版內文 {len(page.placed)} 行）")
    print(f"{'dpi':>6} {'像素':>13} {'首次':>9} {'重繪中位':>10} {'RGBA MB':>9}")
    rows = []
    for dpi in DPI_LEVELS:
        renderer = PageRenderer(template, doc.master, dpi=dpi)
        footer = {"number": str(page.number), "title": doc.title}
        t0 = time.perf_counter()
        img = renderer.render_page(page, footer_texts=footer,
                                   book_number=page.number)
        first = time.perf_counter() - t0
        times = []
        for _ in range(3):  # 字型已載入後的穩態耗時（真實互動情境）
            t = time.perf_counter()
            renderer.render_page(page, footer_texts=footer,
                                 book_number=page.number)
            times.append(time.perf_counter() - t)
        times.sort()
        mb = img.width * img.height * 4 / 1024 / 1024  # QPixmap 以 32 位元存
        rows.append((dpi, img.size, first, times[1], mb))
        print(f"{dpi:>6} {img.width}x{img.height:>7} {first * 1000:>8.0f}ms"
              f" {times[1] * 1000:>9.0f}ms {mb:>8.1f}")
        img.save(OUT / f"page-{dpi}dpi.png")

    # 對照圖：同一段落區域，150dpi 放大 3 倍 vs 450dpi 原生（縮至同尺寸比較）
    from PIL import Image

    crop_pt = (300, 90, 420, 260)  # 版心右上一塊（pt）
    lo = Image.open(OUT / "page-150dpi.png")
    hi = Image.open(OUT / "page-450dpi.png")
    s_lo, s_hi = 150 / 72.0, 450 / 72.0
    box_lo = tuple(round(v * s_lo) for v in crop_pt)
    box_hi = tuple(round(v * s_hi) for v in crop_pt)
    c_lo = lo.crop(box_lo).resize(
        (box_hi[2] - box_hi[0], box_hi[3] - box_hi[1]), Image.BILINEAR)
    c_hi = hi.crop(box_hi)
    pair = Image.new("L", (c_lo.width + c_hi.width + 12, c_lo.height), 255)
    pair.paste(c_lo, (0, 0))
    pair.paste(c_hi, (c_lo.width + 12, 0))
    pair.save(OUT / "compare-150x3-vs-450.png")
    print(f"\n對照圖：{OUT / 'compare-150x3-vs-450.png'}"
          f"（左＝150dpi 放大 3 倍、右＝450dpi 原生，同一區域同尺寸）")

    print("\n判定門檻：互動可察 ≈100ms（Sprint 110 實測長書單字插入重排中位 103ms）")
    for dpi, _size, _first, median, mb in rows:
        verdict = "同步可行" if median * 1000 <= 100 else "須背景執行緒"
        print(f"  {dpi}dpi：重繪中位 {median * 1000:.0f}ms、{mb:.1f}MB → {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
