"""Spike 20 探針二：每字格 sub-slot 字形位移的機制 PoC（A 級證據）。

既有兩條擠壓規則（§3.1.6.1 Sprint 90、§3.1.6.2 規則 2 Sprint 116）都只縮推進量、
不動字形，程式碼裡沒有「單一字格位移」的前例。本探針在**不改動產品程式碼**的前提下，
用既有 `_draw_ttb_char` 直接畫圖量墨，回答兩個問題：

  S2 位移可量：位移 0.5 em 後，PNG 墨跡實測位移量是否等於理論值（±1 px @300dpi）
  S3 不相碰：行首括號位移後，其墨底與次枚字墨頂之間是否仍有正間距

幾何取本專案參考書實測值（PLAN §1）：字級 11.5pt、字距 12.08pt。壓後該行
`used = cap − 0.5`，齊行字距 adv = 12.08 × cap/(cap−0.5)，次枚字槽頂＝
line_top + 0.5 × adv，行首括號字形頂＝line_top − 0.5 × 字級（位移取 em，探針一定案）。

用法：python spikes/spike20-line-head-squeeze/probe_head_offset.py
輸出 PNG 存 spikes/spike20-line-head-squeeze/out/（不入版控）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image  # noqa: E402

from cjkfolio.fonts import FontRegistry  # noqa: E402
from cjkfolio.render import Shaper, _draw_ttb_char  # noqa: E402

DPI = 300
SCALE = DPI / 72.0
SIZE_PT = 11.5
ADVANCE_PT = 12.08
SHIFT_EM = -0.5      # 負值＝往行首（直排的上方）
LINE_TOP_PT = 30.0
AXIS_PT = 20.0
CAPS = (32, 16, 10)
OUT = Path(__file__).resolve().parent / "out"


def ink_span(shaper, ch, cell_top_pt):
    """畫單字於空白圖，回傳墨跡 (top_px, bottom_px)；無墨回 None。"""
    img = Image.new("L", (round(40 * SCALE), round(120 * SCALE)), 255)
    _draw_ttb_char(img, shaper, ch, AXIS_PT, cell_top_pt, SIZE_PT, SCALE, 20)
    box = img.point(lambda v: 255 if v < 128 else 0).getbbox()
    return None if box is None else (box[1], box[3])


def main() -> int:
    OUT.mkdir(exist_ok=True)
    reg = FontRegistry()
    font = reg.resolve("思源宋體 TC", "regular")
    shaper = Shaper(font.path, font.index, dpi=DPI)
    shift_px_theory = abs(SHIFT_EM) * SIZE_PT * SCALE
    ok = True

    print(f"字型 {font.path.name}　{SIZE_PT}pt／{DPI}dpi　scale={SCALE:.4f}")
    print(f"理論位移 {abs(SHIFT_EM)} em ＝ {shift_px_theory:.2f} px\n")

    print("[S2] 位移可量")
    print(f"{'字':<3} {'未位移墨頂':>11} {'位移後墨頂':>11} {'實測位移':>9} {'誤差(px)':>10}")
    for ch in "「（《〈":
        base = ink_span(shaper, ch, LINE_TOP_PT)
        moved = ink_span(shaper, ch, LINE_TOP_PT + SHIFT_EM * SIZE_PT)
        delta = base[0] - moved[0]
        err = delta - shift_px_theory
        if abs(err) > 1:
            ok = False
        print(f"{ch:<3} {base[0]:11d} {moved[0]:11d} {delta:9d} {err:10.2f}")

    print("\n[S3] 位移後與次枚字不相碰（次枚＝『整』，字槽頂 line_top + 0.5 × 齊行字距）")
    print(f"{'cap':>4} {'齊行字距(pt)':>13} {'括號墨底':>9} {'次枚墨頂':>9} {'墨距(px)':>10}")
    for cap in CAPS:
        adv = ADVANCE_PT * cap / (cap - 0.5)
        head = ink_span(shaper, "「", LINE_TOP_PT + SHIFT_EM * SIZE_PT)
        nxt = ink_span(shaper, "整", LINE_TOP_PT + 0.5 * adv)
        gap = nxt[0] - head[1]
        if gap <= 0:
            ok = False
        print(f"{cap:4d} {adv:13.3f} {head[1]:9d} {nxt[0]:9d} {gap:10d}")

    # 併圖存證：左為未套規則（括號留白在上），右為套規則後
    img = Image.new("L", (round(60 * SCALE), round(90 * SCALE)), 255)
    for i, ch in enumerate("「整理"):
        _draw_ttb_char(img, shaper, ch, AXIS_PT, LINE_TOP_PT + i * ADVANCE_PT,
                       SIZE_PT, SCALE, 20)
    adv32 = ADVANCE_PT * 32 / 31.5
    _draw_ttb_char(img, shaper, "「", AXIS_PT + 18, LINE_TOP_PT + SHIFT_EM * SIZE_PT,
                   SIZE_PT, SCALE, 20)
    for i, ch in enumerate("整理"):
        _draw_ttb_char(img, shaper, ch, AXIS_PT + 18,
                       LINE_TOP_PT + (0.5 + i) * adv32, SIZE_PT, SCALE, 20)
    path = OUT / "head-squeeze-compare.png"
    img.save(path)
    print(f"\n對照圖：{path}（左＝未套用，右＝套用後）")
    print("結論：" + ("S2 S3 全數通過 ✅" if ok else "有標準未過 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
