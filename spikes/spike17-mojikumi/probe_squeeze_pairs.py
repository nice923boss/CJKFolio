"""Spike 17 探針二：CLREQ §3.1.6.1 各條擠壓規則在內建字型下的墨跡間距驗算。

擠壓模型（候選）：前一枚約物的字身框由 1 em 縮為 0.5 em，字形位置不變
（＝CLREQ「對符號間相鄰的空隙進行調整」，調的是空隙不是字面）。

本探針對每條規則的代表字對，以探針一量得的墨跡邊界計算：
  擠壓前墨間距 = 1 + 後字墨頂 − 前字墨底
  擠壓後墨間距 = 0.5 + 後字墨頂 − 前字墨底
若擠壓後墨間距 ≤ 0 即墨跡相碰（模型不可行）。同時檢查前字墨是否溢出縮後字身框
（溢出不等於相碰，但需記錄）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

from cjkfolio.fonts import FontRegistry  # noqa: E402
from cjkfolio.render import Shaper  # noqa: E402
from probe_punct_ink import ink_box  # noqa: E402

SQUEEZE = 0.5

# CLREQ WD-20150723 §3.1.6.1（繁中適用者；規則 1 規範明文「繁體中文標點不適用」）
RULES = [
    ("規則 1（句逗後接閉括號）繁體不適用", ["，」", "。』", "、）"], False),
    ("規則 2（閉括號後接句逗）", ["」，", "』。", "）、"], True),
    ("規則 3（句逗後接開括號）", ["，「", "。『", "、（"], True),
    ("規則 4（閉括號後接開括號）", ["」「", "』（", "）《"], True),
    ("規則 5（連續開括號）", ["「『", "（〈", "《「"], True),
    ("規則 6（連續閉括號）", ["」』", "）〉", "》」"], True),
]


def main():
    reg = FontRegistry()
    font = reg.resolve("思源宋體 TC", "regular")
    shaper = Shaper(font.path, font.index, dpi=72)
    print(f"字型：{font.path.name}　擠壓量 {SQUEEZE} em\n")
    print(f"{'字對':<5} {'前字墨底':>9} {'後字墨頂':>9} {'壓前墨距':>9} {'壓後墨距':>9} "
          f"{'前字墨溢框':>11} {'判定':>6}")
    worst = None
    for label, pairs, applies in RULES:
        print(f"\n[{label}]{'' if applies else '　← 本產品不實作'}")
        for pair in pairs:
            a, b = ink_box(shaper, pair[0]), ink_box(shaper, pair[1])
            a_bottom, b_top = a[1], b[0]
            before = 1.0 + b_top - a_bottom
            after = SQUEEZE + b_top - a_bottom
            overflow = max(0.0, a_bottom - SQUEEZE)
            ok = "碰墨" if after <= 0 else "可行"
            print(f"{pair:<5} {a_bottom:9.3f} {b_top:9.3f} {before:9.3f} {after:9.3f} "
                  f"{overflow:11.3f} {ok:>6}")
            if applies and (worst is None or after < worst[1]):
                worst = (pair, after)
    print(f"\n本產品實作範圍（規則 2〜6）最小擠壓後墨距：{worst[0]} = {worst[1]:.3f} em")
    print("結論：" + ("全數 > 0，模型可行" if worst[1] > 0 else "有碰墨，模型不可行"))


if __name__ == "__main__":
    main()
