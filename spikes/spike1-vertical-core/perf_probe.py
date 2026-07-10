"""Spike 3 後半：自製引擎單章重排延遲量測。

量測兩層（PLAN Spike 3：決定是否需增量重排與分章快取）：
1. 純邏輯重排（normalize + tokenize + 斷行禁則 + 頁面流排）：編輯時每鍵觸發的層
2. 全頁渲染（HarfBuzz shaping + FreeType 柵格 + 貼圖）：顯示層，可背景化

素材：參考跨頁 5 段 628 字重複至約一章量（3,000 與 8,000 字兩檔）。僅本機。
"""
import statistics
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_spread import (
    CHARS_PER_LINE, LEFT_BASE_X_PT, LINE_PITCH_PT, MING_INDEX, MING_TTC,
    PAGE_H_PT, PAGE_W_PT, RIGHT_BASE_X_PT, S, SLOTS_PER_PAGE, Shaper,
    draw_line, rebuild_paragraphs,
)
from vertical_engine import check_kinsoku, flow_pages

sys.stdout.reconfigure(encoding="utf-8")


def time_layout(paragraphs, rounds=20):
    samples = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        pages = flow_pages(paragraphs, CHARS_PER_LINE, SLOTS_PER_PAGE,
                           indent=2, para_gap_slots=1)
        samples.append((time.perf_counter() - t0) * 1000)
    return pages, samples


def time_render(pages):
    shaper = Shaper(MING_TTC, MING_INDEX)
    t0 = time.perf_counter()
    img = Image.new("L", (round(PAGE_W_PT * S), round(PAGE_H_PT * S)), 255)
    for page_idx, base_x in ((0, RIGHT_BASE_X_PT), (1, LEFT_BASE_X_PT)):
        if page_idx >= len(pages):
            break
        for slot, line in pages[page_idx]:
            draw_line(img, shaper, line, base_x - slot * LINE_PITCH_PT)
    return (time.perf_counter() - t0) * 1000


def main():
    base, _ = rebuild_paragraphs()
    for mult, label in ((5, "約3,140字（一短章）"), (13, "約8,164字（一長章）")):
        paragraphs = base * mult
        total = sum(len(p) for p in paragraphs)
        pages, samples = time_layout(paragraphs)
        n_lines = sum(len(p) for p in pages)
        violations = check_kinsoku([l for p in pages for _, l in p])
        med = statistics.median(samples)
        print(f"[{label}] 實際 {total} 字 → {len(pages)} 頁 {n_lines} 行，禁則 {len(violations)} 違規")
        print(f"    純邏輯重排：中位 {med:.2f}ms（20 輪，min {min(samples):.2f} / max {max(samples):.2f}）")
        render_ms = time_render(pages)
        print(f"    首跨頁渲染（150dpi，shaping+柵格+貼圖）：{render_ms:.0f}ms")


if __name__ == "__main__":
    main()
