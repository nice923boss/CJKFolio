"""Spike 18 探針：CLREQ 規則 7／8（間隔號與括注符號之間縮減 1/4 形）的墨跡可行性。

規則原文（W3C CLREQ WD-20150723 §3.1.6.1，逐字，B 級）：

  7. 當間隔號出現於結束括注符號之後，縮減其間四分之一個漢字大小的空白。
  8. 當間隔號出現於開始括注符號之前，縮減其間四分之一個漢字大小的空白。

Sprint 90 定下的規則採用門檻是「規範條文＋內建字型墨跡量測」雙重證據，只實作兩者
同時支持者（規則 1 即因量測顯示擠壓後碰墨而不採，見 GAPS #50 (a)）。本探針補上
規則 7／8 缺的那一半：以 ttb 塑形量測內建字型的間隔號與括注符號墨跡邊界，計算
縮減 0.25 em 後兩枚墨跡是否相碰。

量測方法沿用 spike17 的 probe_punct_ink.py：100pt 大級數減少柵格量化誤差，
座標以字身框頂為 0、向下為正（同 render 的 ttb pen 語意）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

from cjkfolio.fonts import FontRegistry  # noqa: E402
from cjkfolio.render import Shaper  # noqa: E402

SIZE_PT = 100.0
DPI = 72
SQUEEZE = 0.25  # 規則 7／8 的縮減量（四分之一漢字）

INTERPUNCT = "·‧・"
CLOSERS = "」』）〕》〉｝〗"
OPENERS = "「『（〔《〈｛〖"


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
    font = reg.resolve("思源宋體 TC", "regular")
    shaper = Shaper(font.path, font.index, dpi=DPI)
    print(f"字型：{font.path.name}　upem={shaper.upem}　量測 {SIZE_PT}pt/{DPI}dpi")
    print(f"縮減量：{SQUEEZE} em（CLREQ 規則 7／8 的四分之一漢字）\n")

    boxes = {}
    print(f"{'字':<3} {'碼位':<8} {'墨頂':>7} {'墨底':>7} {'墨高':>7} {'推進':>7}")
    for ch in INTERPUNCT + CLOSERS + OPENERS:
        r = ink_box(shaper, ch)
        if r is None:
            print(f"{ch:<3} U+{ord(ch):04X} （無墨跡）")
            continue
        boxes[ch] = r
        print(f"{ch:<3} U+{ord(ch):04X} {r[0]:7.3f} {r[1]:7.3f} {r[1] - r[0]:7.3f} {r[2]:7.3f}")

    def gaps(first: str, second: str, label: str) -> list:
        """第一枚起於 0、第二枚起於 1.0 em（未壓）或 1.0-SQUEEZE em（壓後）的墨距。"""
        print(f"\n[{label}]　墨距＝第二枚墨頂 減 第一枚墨底（負值＝相碰）")
        print(f"{'配對':<6} {'未壓墨距':>9} {'壓後墨距':>9} {'判定':>6}")
        rows = []
        for a in first:
            for b in second:
                if a not in boxes or b not in boxes:
                    continue
                a_bottom = boxes[a][1]
                b_top = boxes[b][0]
                plain = (1.0 + b_top) - a_bottom
                squeezed = (1.0 - SQUEEZE + b_top) - a_bottom
                verdict = "碰墨" if squeezed < 0 else "可壓"
                rows.append((a + b, plain, squeezed, verdict))
                print(f"{a + b:<6} {plain:9.3f} {squeezed:9.3f} {verdict:>6}")
        return rows

    r7 = gaps(CLOSERS, INTERPUNCT, "規則 7：結束括注符號 → 間隔號")
    r8 = gaps(INTERPUNCT, OPENERS, "規則 8：間隔號 → 開始括注符號")

    for label, rows in (("規則 7", r7), ("規則 8", r8)):
        bad = [r for r in rows if r[3] == "碰墨"]
        worst = min(rows, key=lambda r: r[2]) if rows else None
        print(f"\n{label}：{len(rows)} 組配對，碰墨 {len(bad)} 組"
              + (f"，最小壓後墨距 {worst[2]:.3f} em（{worst[0]}）" if worst else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
