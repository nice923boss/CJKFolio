"""Spike 19 探針一：CLREQ §3.1.6.2 行首行尾標點擠壓的墨跡可行性（A 級證據）。

規則原文（W3C CLREQ WD-20150723 §3.1.6.2「行首行尾標點擠壓」，逐字，B 級）：

  1. 當行首出現開始括注符號，可以縮減該符號始側二分之一個漢字大小的空白。
  2. 當行尾出現結束括注符號時，可以縮減其末側二分之一個漢字大小的空白。
  3. 簡體中文排版中，當行尾出現頓號、逗號、句號時，可以縮減該符號末側二分之一
     個漢字大小的空白。

第 3 條明文限簡體中文，繁中排除（同 §3.1.6.1 規則 1 的處置，見 GAPS #50 (a)）。
故本探針只量前兩條。

Sprint 90 定下的採用門檻是「規範條文＋內建字型墨跡量測」雙重證據。本探針量的是
第二半：縮減的那半格裡到底有沒有墨。直排 ttb 語意下「始側」＝字身框上緣、「末側」
＝字身框下緣，故判準為：

  行首開括號：墨頂 ≥ 0.5 em（上半格空白）→ 縮減始側半格不切墨
  行尾閉括號：墨底 ≤ 0.5 em（下半格空白）→ 縮減末側半格不切墨

量測方法沿用 spike17 probe_punct_ink.py：100pt 大級數減少柵格量化誤差，
座標以字身框頂為 0、向下為正（同 render 的 ttb pen 語意）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

from cjkfolio.engine import SQUEEZE_CLOSERS, SQUEEZE_OPENERS  # noqa: E402
from cjkfolio.fonts import FontRegistry  # noqa: E402
from cjkfolio.render import Shaper  # noqa: E402

SIZE_PT = 100.0
DPI = 72
SQUEEZE = 0.5  # §3.1.6.2 的縮減量（二分之一漢字）


def ink_box(shaper, ch):
    """回傳 (墨頂, 墨底, ttb 推進)，單位 em 比例；無墨跡回 None。"""
    sf = shaper.set_size(SIZE_PT)
    infos, poss = shaper.shape(ch, "ttb")
    pen_y = 0.0
    top = bottom = None
    advance = 0.0
    for info, pos in zip(infos, poss):
        tile, g = shaper.glyph_tile(info.codepoint)
        if tile is not None:
            gy = pen_y - pos.y_offset * sf - g.bitmap_top
            t, b = gy, gy + tile.size[1]
            top = t if top is None else min(top, t)
            bottom = b if bottom is None else max(bottom, b)
        pen_y += -pos.y_advance * sf
        advance += -pos.y_advance * sf
    if top is None:
        return None
    return top / SIZE_PT, bottom / SIZE_PT, advance / SIZE_PT


def main() -> int:
    reg = FontRegistry()
    results = {}
    for family in ("思源宋體 TC", "思源黑體 TC"):
        try:
            font = reg.resolve(family, "regular")
        except Exception as exc:  # 內建字型缺一不影響另一款的量測
            print(f"{family}：無法解析（{exc}）")
            continue
        shaper = Shaper(font.path, font.index, dpi=DPI)
        print(f"\n字型：{family}　{font.path.name}　upem={shaper.upem}　"
              f"量測 {SIZE_PT}pt/{DPI}dpi　縮減量 {SQUEEZE} em")

        print(f"\n[規則 1] 行首開始括注符號：縮減始側（上半格）"
              f"　判準 墨頂 ≥ {SQUEEZE}")
        print(f"{'字':<3} {'碼位':<8} {'墨頂':>7} {'墨底':>7} {'始側留白':>9} {'判定':>6}")
        rows_open = []
        for ch in sorted(SQUEEZE_OPENERS):
            r = ink_box(shaper, ch)
            if r is None:
                print(f"{ch:<3} U+{ord(ch):04X} （無墨跡）")
                continue
            slack = r[0]  # 始側留白＝墨頂距字身框頂
            verdict = "可壓" if slack >= SQUEEZE else "切墨"
            rows_open.append((ch, slack, verdict))
            print(f"{ch:<3} U+{ord(ch):04X} {r[0]:7.3f} {r[1]:7.3f} "
                  f"{slack:9.3f} {verdict:>6}")

        print(f"\n[規則 2] 行尾結束括注符號：縮減末側（下半格）"
              f"　判準 墨底 ≤ {1 - SQUEEZE}")
        print(f"{'字':<3} {'碼位':<8} {'墨頂':>7} {'墨底':>7} {'末側留白':>9} {'判定':>6}")
        rows_close = []
        for ch in sorted(SQUEEZE_CLOSERS):
            r = ink_box(shaper, ch)
            if r is None:
                print(f"{ch:<3} U+{ord(ch):04X} （無墨跡）")
                continue
            slack = 1.0 - r[1]  # 末側留白＝字身框底距墨底
            verdict = "可壓" if slack >= SQUEEZE else "切墨"
            rows_close.append((ch, slack, verdict))
            print(f"{ch:<3} U+{ord(ch):04X} {r[0]:7.3f} {r[1]:7.3f} "
                  f"{slack:9.3f} {verdict:>6}")

        results[family] = (rows_open, rows_close)

    print("\n" + "=" * 64)
    for family, (rows_open, rows_close) in results.items():
        for label, rows in (("規則 1 行首開括號", rows_open),
                            ("規則 2 行尾閉括號", rows_close)):
            bad = [r for r in rows if r[2] == "切墨"]
            worst = min(rows, key=lambda r: r[1]) if rows else None
            line = f"{family}　{label}：{len(rows)} 枚，切墨 {len(bad)} 枚"
            if worst:
                line += f"，最小留白 {worst[1]:.3f} em（{worst[0]}）"
            if bad:
                line += "　→ " + "、".join(f"{r[0]} {r[1]:.3f}" for r in bad)
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
