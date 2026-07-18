"""效能量測與基線（Sprint 106，GAPS #56 丙(12)）。

量的是**全書級四道工序的耗時**：排版（layout）、PNG 渲染（render）、PDF 匯出
（export）、機械 preflight。Spike 3 只測過單章的純排版邏輯（7.67ms），沒有任何
一項是在書級規模上量過的，故「全書重排會不會卡」在此之前是沒有數據的。

素材一律取 repo 內可散布的自撰原創散文（`samples/paiban-xiaoji-ch1.md`），以
**整數倍重複**放大到目標頁數，故任何人可從 repo 內容原樣重現，不需參考書。
重複的是段落序列而非隨機生成，斷行與禁則的工作量因此與真實稿件同量級。

用法（自 repo 根執行）：

    python tools/measure_performance.py                 # 預設 1／4／8／16 倍
    python tools/measure_performance.py --scales 1 16   # 只跑指定倍數
    python tools/measure_performance.py --skip-render   # 略過最慢的 PNG 渲染

輸出為表格，數字隨機器而異，故**不入自動測試斷言**（測試只驗工具本身可跑）。
基線數字記於 PLAN §6 Sprint 106 進度條與 GAPS #60。
"""
import argparse
import statistics
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cjkfolio.layout import layout_document  # noqa: E402
from cjkfolio.md_import import import_markdown_file  # noqa: E402
from cjkfolio.pdf_writer import export_pdf  # noqa: E402
from cjkfolio.preflight import (  # noqa: E402
    check_image_resolution,
    check_ink_coverage,
    check_pdfx,
)
from cjkfolio.render import render_document  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402

SAMPLE = ROOT / "samples" / "paiban-xiaoji-ch1.md"
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
DEFAULT_SCALES = (1, 4, 8, 16)


def scaled_document(base, times: int):
    """把基準文件的段落序列重複 times 次（段落為 frozen dataclass，直接複用）。"""
    return replace(base, paragraphs=tuple(base.paragraphs) * times)


def timed(fn, repeats: int = 1):
    """跑 repeats 次取中位數秒數（回傳 (中位數, 最後一次的回傳值)）。

    取中位數而非平均：首次呼叫常含字型載入等一次性成本，平均會被它拖偏。
    """
    samples, out = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples), out


def measure_scale(base, template, times: int, *, skip_render: bool,
                  repeats: int, layout_only: bool = False) -> dict:
    """單一規模的四道工序耗時（render 與 export 寫入暫存目錄，不落 repo）。

    layout_only＝只量排版，用來把排版的規模曲線與匯出／preflight 的固定成本
    （字型子集化等）隔開看，否則細部掃描會被後三道的秒級耗時淹沒。
    """
    doc = scaled_document(base, times)
    row = {"倍數": times, "段數": len(doc.paragraphs)}

    layout_s, result = timed(lambda: layout_document(doc, template), repeats)
    row["頁數"] = len(result.pages)
    row["排版"] = layout_s
    if layout_only:
        row.update({"渲染": None, "匯出": None, "preflight": None,
                    "PDF大小": 0, "X-1a": "未跑"})
        return row

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        if skip_render:
            row["渲染"] = None
        else:
            row["渲染"], _ = timed(
                lambda: render_document(doc, template, td / "png", dpi=150), 1)
        pdf = td / "book.pdf"
        row["匯出"], _ = timed(lambda: export_pdf(doc, template, pdf), 1)
        row["PDF大小"] = pdf.stat().st_size

        def _preflight():
            p = str(pdf)
            return (check_pdfx(p), check_image_resolution(p),
                    check_ink_coverage(p))

        row["preflight"], reports = timed(_preflight, 1)
        row["X-1a"] = "通過" if reports[0].ok else "不過"
    return row


def _fmt(v) -> str:
    if v is None:
        return "略過"
    return f"{v * 1000:.0f}ms" if v < 1 else f"{v:.2f}s"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="全書級效能量測（Sprint 106）")
    ap.add_argument("--scales", type=int, nargs="+", default=list(DEFAULT_SCALES),
                    help="重複倍數（預設 1 4 8 16）")
    ap.add_argument("--repeats", type=int, default=3,
                    help="排版量測的重複次數（取中位數，預設 3）")
    ap.add_argument("--skip-render", action="store_true",
                    help="略過 PNG 渲染（四道工序中最慢的一道）")
    ap.add_argument("--layout-only", action="store_true",
                    help="只量排版（隔開匯出與 preflight 的秒級固定成本，供細部掃描）")
    args = ap.parse_args(argv)

    template = load_template(TEMPLATE)
    base = import_markdown_file(SAMPLE, mapping=template.md_mapping,
                                inline_mapping=template.md_inline_mapping,
                                title="排版小記",
                                template_id="neizai-zhengli",
                                master=template.default_master)
    print(f"素材：{SAMPLE.name}（自撰原創，{len(base.paragraphs)} 段）"
          f"　模版：{TEMPLATE.name}")
    print(f"排版取 {args.repeats} 次中位數；渲染／匯出／preflight 各跑 1 次\n")

    header = ("倍數", "段數", "頁數", "排版", "每頁排版", "渲染", "匯出",
              "preflight", "PDF大小", "X-1a")
    print("｜".join(f"{h:>9}" for h in header))
    rows = []
    for times in args.scales:
        row = measure_scale(base, template, times,
                            skip_render=args.skip_render, repeats=args.repeats,
                            layout_only=args.layout_only)
        rows.append(row)
        per_page = row["排版"] / row["頁數"]
        row["每頁排版"] = per_page
        cells = [str(row["倍數"]), str(row["段數"]), str(row["頁數"]),
                 _fmt(row["排版"]), f"{per_page * 1000:.2f}ms",
                 _fmt(row["渲染"]), _fmt(row["匯出"]), _fmt(row["preflight"]),
                 f"{row['PDF大小'] / 1024:.0f}KB", row["X-1a"]]
        print("｜".join(f"{c:>9}" for c in cells))

    # 線性度看「每頁耗時」而非首末列的倍率：小規模每頁更快（快取與暖機），以它
    # 當基準算倍率會把線性的曲線讀成超線性。每頁耗時持平＝線性，隨規模上升＝惡化。
    if len(rows) >= 2:
        pp = [r["每頁排版"] for r in rows]
        print(f"\n每頁排版：{min(pp) * 1000:.2f}〜{max(pp) * 1000:.2f}ms"
              f"（末列／首列 {pp[-1] / pp[0]:.2f} 倍）")
        print("（持平＝線性；隨頁數單調上升且倍率明顯 > 1 才是演算法惡化）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
