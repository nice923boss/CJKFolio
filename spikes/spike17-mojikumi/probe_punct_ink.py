"""Spike 17 探針：直排約物字形的墨跡在字身框（em）內的位置。

問題：標點擠壓（mojikumi aki）把全形約物壓成半形時，字形要畫在壓縮後字身框的
哪一半？答案取決於字型設計（墨跡偏上／偏下／置中），不能憑通則猜。

本探針對內建思源宋體 TC Regular，以 ttb（直排 vert 特性）塑形每個約物，
量測其墨跡邊界在 em 內的相對位置（0＝字身框頂、1＝底），輸出一手數據。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

from cjkfolio.fonts import FontRegistry  # noqa: E402
from cjkfolio.render import Shaper  # noqa: E402

SIZE_PT = 100.0  # 大級數量測，減少柵格量化誤差
DPI = 72  # scale=1 → px 即 pt

# 依 CLREQ 分類的約物（直排形）
GROUPS = {
    "句號類（。．）": "。．",
    "逗頓號類（，、）": "，、",
    "冒號分號（：；）": "：；",
    "驚嘆問號（！？）": "！？",
    "開括號類": "「『（〔《〈｛〖【",
    "閉括號類": "」』）〕》〉｝〗】",
    "中點省略號": "·…‥",
    "對照：漢字": "書中永",
}


def ink_box(shaper, ch):
    """回傳該字直排塑形後的 (墨跡上緣, 下緣, 左緣, 右緣, advance)，單位 em 比例。

    座標：以字身框頂為 0、向下為正（同 render 的 ttb pen 語意）。
    """
    sf = shaper.set_size(SIZE_PT)
    infos, poss = shaper.shape(ch, "ttb")
    pen_x, pen_y = 0.0, 0.0
    box = None
    advance = 0.0
    for info, pos in zip(infos, poss):
        tile, g = shaper.glyph_tile(info.codepoint)
        if tile is not None:
            gx = pen_x + pos.x_offset * sf + g.bitmap_left
            gy = pen_y - pos.y_offset * sf - g.bitmap_top
            b = (gy, gy + tile.size[1], gx, gx + tile.size[0])
            box = b if box is None else (min(box[0], b[0]), max(box[1], b[1]),
                                         min(box[2], b[2]), max(box[3], b[3]))
        pen_x += pos.x_advance * sf
        pen_y += -pos.y_advance * sf
        advance += -pos.y_advance * sf
    if box is None:
        return None
    return tuple(v / SIZE_PT for v in box) + (advance / SIZE_PT,)


def main():
    reg = FontRegistry()
    font = reg.resolve("思源宋體 TC", "regular")
    shaper = Shaper(font.path, font.index, dpi=DPI)
    print(f"字型：{font.path.name}　upem={shaper.upem}　量測級數 {SIZE_PT}pt/{DPI}dpi")
    print(f"{'字':<3} {'墨頂':>7} {'墨底':>7} {'墨高':>7} {'上留白':>7} {'下留白':>7} "
          f"{'ttb推進':>8}")
    for label, chars in GROUPS.items():
        print(f"\n[{label}]")
        for ch in chars:
            r = ink_box(shaper, ch)
            if r is None:
                print(f"{ch:<3} （無墨跡）")
                continue
            top, bottom, _left, _right, adv = r
            print(f"{ch:<3} {top:7.3f} {bottom:7.3f} {bottom - top:7.3f} "
                  f"{top:7.3f} {adv - bottom:7.3f} {adv:8.3f}")


if __name__ == "__main__":
    main()
