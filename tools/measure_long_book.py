"""長書匯入驗收與記憶體量測（Sprint 110，GAPS #63；補 #60 (b) 記憶體峰值）。

與 `measure_performance.py` 的分工：那支量的是 repo 內可散布素材**整數倍重複**放大
後的耗時曲線（任何人可重現，但內容是同一章重複）；本支跑的是**一份真實多章長書**
的完整 CLI 鏈（逐章 txt 匯入 → 書冊組裝 → 自動目錄 → 排版 → 匯出 → 機械 preflight），
量的是真實稿件的分頁穩定性、耗時與記憶體峰值。

素材一律由呼叫端顯式指定（`--chapters` 逐檔列出，順序即章序），本工具**不內含任何
書稿路徑、不猜章序、不掃描目錄**：長書多為未出版私人稿件，路徑與順序屬呼叫端的事。
產出物一律寫 `--out` 指定的目錄。

記憶體兩個來源，缺一不可（PoC 實測，見 Sprint 110 dev-log）：
- **peak working set**（Windows psapi，含 native 配置）：字型、影像、PDF 光柵在
  C 擴充端配置，tracemalloc 完全看不到（實測 99.6MB 的 pixmap 只被記為 17.9MB）。
  它是**進程生命週期的歷史最大值且不可重置**，故只有整鏈一個數字，無法逐工序拆分。
- **tracemalloc 峰值**（跨平台，只含 Python 端配置）：可逐工序重置，用來看哪一道
  最吃 Python 端記憶體。

非 Windows 平台取不到 peak working set 時據實回報「不可得」，不以 tracemalloc 頂替。

用法（自 repo 根執行）：

    python tools/measure_long_book.py --chapters 第一章.txt 第二章.txt ... \\
        --template templates/neizai-zhengli.json --out out/long-book \\
        --title 書名 --heading-style 章名大標-明體W7 --toc-heading 目次 \\
        --toc-entry-style 目錄-篇章條目 --toc-heading-style 目錄-部名 --toc-master D-目錄

數字隨機器與稿件而異，故**不入自動測試斷言**（測試只驗工具邏輯與可跑）。
"""
import argparse
import ctypes
import json
import sys
import time
import tracemalloc
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cjkfolio.book import assemble_book, load_book  # noqa: E402
from cjkfolio.document import save_document  # noqa: E402
from cjkfolio.pdf_writer import export_pdf  # noqa: E402
from cjkfolio.preflight import (  # noqa: E402
    check_image_resolution,
    check_ink_coverage,
    check_pdfx,
    image_resolution_summary,
    ink_coverage_summary,
    preflight_summary,
)
from cjkfolio.render import render_document  # noqa: E402
from cjkfolio.styles import load_template  # noqa: E402
from cjkfolio.toc import assemble_book_with_toc  # noqa: E402
from cjkfolio.wrap import layout_with_wrap  # noqa: E402
from editor.import_core import import_manuscript  # noqa: E402


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def peak_working_set() -> Optional[int]:
    """本進程的 peak working set（bytes，含 native 配置）；取不到回 None。

    Windows 專屬（psapi）。**歷史最大值且不可重置**，故整個進程只有一個有意義的
    數字：分段呼叫得到的是「到此為止的最大值」，不是該段的用量。
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
                k32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None
        return counters.PeakWorkingSetSize
    except (OSError, AttributeError):  # 非預期的平台或 API 不可用：據實回 None
        return None


def timed_step(name: str, fn):
    """純計時（不開 tracemalloc），回傳 (結果, {工序, 耗時, Python峰值: None})。"""
    t0 = time.perf_counter()
    out = fn()
    return out, {"工序": name, "耗時": time.perf_counter() - t0, "Python峰值": None}


def traced_step(name: str, fn):
    """量該工序的 Python 端峰值（開 tracemalloc），回傳 (結果, 紀錄)。

    **耗時在此趟不可信**：tracemalloc 本機實測讓 PDF 匯出慢 5.8 倍（1.30s → 7.54s），
    故計時與記憶體必須分兩趟跑，這也是 `run_pipeline` 收 step_runner 的理由。
    """
    tracemalloc.start()
    t0 = time.perf_counter()
    out = fn()
    elapsed = time.perf_counter() - t0
    py_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return out, {"工序": name, "耗時": elapsed, "Python峰值": py_peak}


def chapter_documents(paths, template, template_id: str, heading_style: Optional[str]):
    """逐章匯入；heading_style 非 None 時把每章首段改掛該樣式。

    匯入走 editor 的 `import_manuscript` 判定層（Sprint 107）＝與編輯器「檔案 →
    匯入稿件」同一個入口，故本驗收量到的預設值推導行為就是使用者在 APP 內得到的。

    首段即章標題行是呼叫端的宣告（`--heading-style` 給了就是這個意思），本工具不從
    文字內容反推標題（§4.4 分工鐵律：標題語意屬使用者，引擎不猜）。
    """
    docs = []
    for path in paths:
        doc = import_manuscript(path, template, template_id)
        if not doc.paragraphs:
            raise ValueError(f"章檔無任何段落：{path}")
        if heading_style is not None:
            head = replace(doc.paragraphs[0], style=heading_style)
            doc = replace(doc, paragraphs=(head, *doc.paragraphs[1:]))
        docs.append(doc)
    return docs


def write_manifest(docs, out_dir: Path, args) -> Path:
    """章文件落檔並寫出 book@1 清單，回傳清單路徑。"""
    chapters = []
    if args.toc_heading is not None:
        chapters.append({"generate_toc": {
            "heading": args.toc_heading,
            "heading_style": args.toc_heading_style,
            "entry_style": args.toc_entry_style,
            "master": args.toc_master,
        }})
    for doc in docs:
        name = f"ch{len(chapters):02d}.doc.json"
        save_document(doc, out_dir / name)
        ref = {"path": name}
        if args.toc_heading is not None:
            ref["toc_title"] = doc.paragraphs[0].text
        chapters.append(ref)
    manifest = out_dir / "book.json"
    manifest.write_text(json.dumps({
        "schema": "cjkfolio/book@1",
        "meta": {"title": args.title, "template": args.template_id},
        "chapters": chapters,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def run_pipeline(paths, template, args, out_dir: Path, step_runner):
    """跑完整 CLI 鏈一趟，回傳 (工序紀錄列, 組裝後文件, 排版結果, preflight 報告, PDF 路徑)。

    step_runner 決定這一趟量什麼（`timed_step` 純計時／`traced_step` 量 Python 峰值）。
    兩趟走的是同一段程式碼，故記憶體趟與計時趟量的確實是同一件事。
    """
    steps = []

    def step(name, fn):
        out, record = step_runner(name, fn)
        steps.append(record)
        return out

    docs = step("匯入（逐章）", lambda: chapter_documents(
        paths, template, args.template_id, args.heading_style))
    manifest = step("落檔＋清單", lambda: write_manifest(docs, out_dir, args))
    book = load_book(manifest)
    # 有無自動目錄章決定走哪個組裝入口：`assemble_book_with_toc` 要求書冊含
    # generate_toc 章（無則快速失敗），故不給 --toc-heading 時走純 path 組裝。
    if any(ch.toc_spec for ch in book.chapters):
        doc = step("組裝＋自動目錄", lambda: assemble_book_with_toc(
            book, template, base_dir=manifest.parent, first_page=args.first_page))
    else:
        doc = step("組裝", lambda: assemble_book(book, base_dir=manifest.parent))
    result = step("排版", lambda: layout_with_wrap(
        doc, template, first_page=args.first_page))
    if not args.skip_render:
        step("渲染 PNG", lambda: render_document(
            doc, template, out_dir / "png", dpi=args.dpi, first_page=args.first_page))
    pdf = out_dir / "book.pdf"
    step("匯出 PDF", lambda: export_pdf(
        doc, template, pdf, first_page=args.first_page))
    reports = step("機械 preflight", lambda: (
        check_pdfx(str(pdf)), check_image_resolution(str(pdf)), check_ink_coverage(str(pdf))))
    return steps, doc, result, reports, pdf


def _fmt_s(v: float) -> str:
    return f"{v * 1000:.0f}ms" if v < 1 else f"{v:.2f}s"


def _fmt_mb(v) -> str:
    return "不可得" if v is None else f"{v / 1024 / 1024:.1f}MB"


def main(argv=None) -> int:
    # Windows 繁中主控台預設 cp950，編不出 preflight 摘要裡的 ≤（U+2264）會直接
    # UnicodeEncodeError，中文亦顯示為亂碼（同 cli.py 的處置）。
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="長書匯入驗收與記憶體量測（Sprint 110）")
    ap.add_argument("--chapters", nargs="+", required=True,
                    help="章 txt 檔（順序即章序；本工具不掃描目錄、不猜章序）")
    ap.add_argument("--template", required=True, help="模版 JSON 路徑")
    ap.add_argument("--out", required=True, help="產出目錄（章 JSON／書冊清單／PDF）")
    ap.add_argument("--title", default="長書", help="書名")
    ap.add_argument("--heading-style", default=None,
                    help="每章首段改掛的樣式（不給＝全掛內文，亦不產目錄條目）")
    ap.add_argument("--toc-heading", default=None, help="自動目錄標題（不給＝不產目錄）")
    ap.add_argument("--toc-heading-style", default=None)
    ap.add_argument("--toc-entry-style", default=None)
    ap.add_argument("--toc-master", default=None)
    ap.add_argument("--first-page", type=int, default=1)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--skip-render", action="store_true", help="略過 PNG 渲染（最慢一道）")
    args = ap.parse_args(argv)

    if args.toc_heading is not None and not all(
            (args.toc_heading_style, args.toc_entry_style, args.toc_master)):
        ap.error("--toc-heading 需搭 --toc-heading-style／--toc-entry-style／--toc-master")

    paths = [Path(p) for p in args.chapters]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        ap.error(f"章檔不存在：{missing}")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    template_path = Path(args.template)
    args.template_id = template_path.stem

    template = load_template(template_path)

    # 趟 1：純計時。
    steps, doc, result, reports, pdf = run_pipeline(
        paths, template, args, out_dir, timed_step)
    # peak working set 必須在 tracemalloc 趟**之前**取：追蹤器自身的配置會推高它，
    # 而它是不可重置的歷史最大值，一旦被污染就回不去了。
    process_peak = peak_working_set()
    # 趟 2：量 Python 端逐工序峰值（此趟耗時不採用，見 traced_step docstring）。
    mem_steps = run_pipeline(paths, template, args, out_dir, traced_step)[0]
    py_peaks = {s["工序"]: s["Python峰值"] for s in mem_steps}

    print(f"書名：{args.title}　章數：{len(paths)}　模版：{template_path.name}")
    print(f"段數：{len(doc.paragraphs)}　頁數：{len(result.pages)}　"
          f"PDF：{pdf.stat().st_size / 1024:.0f}KB")
    print()
    print(f"{'工序':<16}｜{'耗時':>9}｜{'Python 端峰值':>13}")
    for s in steps:
        print(f"{s['工序']:<16}｜{_fmt_s(s['耗時']):>9}｜"
              f"{_fmt_mb(py_peaks.get(s['工序'])):>13}")
    print(f"{'合計':<16}｜{_fmt_s(sum(s['耗時'] for s in steps)):>9}｜{'':>13}")
    print()
    print("耗時取純計時趟；Python 端峰值取 tracemalloc 趟（兩趟分開跑，因 tracemalloc")
    print("本身讓匯出慢約 5.8 倍，同趟量會把耗時全數污染）。")
    print(f"進程 peak working set（含 native 配置，整鏈歷史最大值，"
          f"於 tracemalloc 趟前取）：{_fmt_mb(process_peak)}")
    print()

    print(f"禁則違規：{len(result.violations)}　齊行統計：{result.justify_stats}")
    print(f"X-1a：{'通過' if reports[0].ok else '不過'}")
    print(preflight_summary(reports[0]))
    print(image_resolution_summary(reports[1]))
    print(ink_coverage_summary(reports[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
