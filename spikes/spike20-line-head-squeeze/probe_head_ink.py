"""Spike 20 探針一：行首開括號縮始側的**位移單位**該取 em 還是字槽（A 級證據）。

Sprint 113（spike19 probe_edge_ink.py）已量出兩款內建字型 16 枚開括號的始側留白，
最小 0.520 em。本探針把該量測推到實作要決定的下一個問題：位移量取多少。

三個候選：

  em     ＝ 0.500 em（條文原文「二分之一個漢字大小」，與字距、齊行無關）
  槽     ＝ 0.5 × 字距／字級（本專案 12.08 / 11.5 ＝ 0.5252 em）
  槽齊行 ＝ 0.5 × 齊行後字距／字級（讓出半格後 adv 放大成 advance × cap/(cap−0.5)）

判準：位移量 ≤ 該字的始側留白（墨頂）才不會讓墨跡越過行首邊界。

用法：python spikes/spike20-line-head-squeeze/probe_head_ink.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "spikes" / "spike19-mojikumi-rest"))
sys.stdout.reconfigure(encoding="utf-8")

from probe_edge_ink import ink_box  # noqa: E402　沿用 Sprint 113 的墨跡量測

from cjkfolio.engine import SQUEEZE_OPENERS  # noqa: E402
from cjkfolio.fonts import FontRegistry  # noqa: E402
from cjkfolio.render import Shaper  # noqa: E402

DPI = 72
SIZE_PT = 11.5       # 參考書內文字級（PLAN §1 A 級量測）
ADVANCE_PT = 12.08   # 參考書內文字距（PLAN §1 A 級量測）
CAPS = (32, 16, 10)  # 直排每行字數：長書正文、窄欄、極窄欄


def candidates():
    """三種位移量（em），含齊行放大後的最壞情形。"""
    slot = 0.5 * ADVANCE_PT / SIZE_PT
    out = [("em 0.5", 0.5), ("槽 0.5", slot)]
    for cap in CAPS:
        adv = ADVANCE_PT * cap / (cap - 0.5)  # 讓出半格後齊行重算字距
        out.append((f"槽齊行 cap={cap}", 0.5 * adv / SIZE_PT))
    return out


def main() -> int:
    reg = FontRegistry()
    slacks = {}
    for family in ("思源宋體 TC", "思源黑體 TC"):
        try:
            font = reg.resolve(family, "regular")
        except Exception as exc:  # 內建字型缺一不影響另一款的量測
            print(f"{family}：無法解析（{exc}）")
            continue
        shaper = Shaper(font.path, font.index, dpi=DPI)
        print(f"\n字型：{family}　{font.path.name}")
        print(f"{'字':<3} {'碼位':<8} {'始側留白(em)':>14}")
        for ch in sorted(SQUEEZE_OPENERS):
            r = ink_box(shaper, ch)
            if r is None:
                print(f"{ch:<3} U+{ord(ch):04X} （無墨跡）")
                continue
            slacks.setdefault(family, []).append((ch, r[0]))
            print(f"{ch:<3} U+{ord(ch):04X} {r[0]:14.3f}")

    print("\n" + "=" * 66)
    print(f"{'位移候選':<16} {'位移量(em)':>11} {'切墨枚數':>9} {'最小餘裕(em)':>13}")
    verdicts = {}
    for name, shift in candidates():
        rows = [(fam, ch, slack - shift)
                for fam, items in slacks.items() for ch, slack in items]
        bad = [r for r in rows if r[2] < 0]
        worst = min(rows, key=lambda r: r[2]) if rows else None
        verdicts[name] = (shift, len(bad), worst)
        tail = f"{worst[2]:13.4f}（{worst[1]} {worst[0]}）" if worst else ""
        print(f"{name:<16} {shift:11.4f} {len(bad):9d} {tail}")
        if bad:
            print("    切墨：" + "、".join(f"{ch}{fam[:2]} {d:+.4f}"
                                          for fam, ch, d in bad))

    ok = verdicts.get("em 0.5", (0, 1, None))[1] == 0
    print("\n結論：位移取 **em 0.5** " + ("不切墨 ✅" if ok else "切墨 ❌（放棄條件觸發）"))
    print("槽制候選只要有一列切墨，即證明位移量不可綁字距或齊行。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
