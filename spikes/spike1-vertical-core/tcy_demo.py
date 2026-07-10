"""Spike 1 縱中橫示範條：2 位數直立橫排（tcy）、長串數字與拉丁旋轉 90 度。

文字為自擬內容（無版權疑慮），驗收檢核清單「縱中橫」項的視覺證據。
輸出：out/tcy_demo.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_spread import (
    BODY_SIZE_PT, CHAR_ADV_PT, LINE_PITCH_PT, MING_INDEX, MING_TTC, S, Shaper,
    draw_rotated_latin, draw_tcy, draw_ttb_char,
)
from vertical_engine import break_paragraph, check_kinsoku

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(__file__).resolve().parent / "out"
TEXT = "第12章：直排引擎於2026年以HarfBuzz驗證，縱中橫共8項規則通過。"
CHARS_PER_LINE = 14
TOP_PT = 30.0


def main():
    lines = break_paragraph(TEXT, CHARS_PER_LINE, indent=0)
    violations = check_kinsoku(lines)
    print(f"[1] 斷行 {len(lines)} 行，禁則：{'0 違規' if not violations else violations}")
    for l in lines:
        print("    " + "".join(c.text for c in l.cells))

    w_pt = LINE_PITCH_PT * (len(lines) + 1) + 20
    h_pt = TOP_PT * 2 + CHAR_ADV_PT * (CHARS_PER_LINE + 1)
    img = Image.new("L", (round(w_pt * S), round(h_pt * S)), 255)
    shaper = Shaper(MING_TTC, MING_INDEX)
    base_x = w_pt - 20 - LINE_PITCH_PT / 2
    for li, line in enumerate(lines):
        axis_x = base_x - li * LINE_PITCH_PT
        slot = line.start_slot
        for cell in line.cells:
            cell_top = TOP_PT + slot * CHAR_ADV_PT
            if cell.kind == "cjk":
                draw_ttb_char(img, shaper, cell.text, axis_x, cell_top, BODY_SIZE_PT)
            elif cell.kind == "tcy":
                draw_tcy(img, shaper, cell.text, axis_x, cell_top, BODY_SIZE_PT)
            elif cell.kind == "latin":
                draw_rotated_latin(img, shaper, cell.text, axis_x, cell_top, BODY_SIZE_PT)
            slot += cell.width
    d = ImageDraw.Draw(img)
    label = ImageFont.truetype(MING_TTC, 20, index=MING_INDEX)
    d.text((10, img.height - 30), "縱中橫示範：12、8 直立橫排；2026、HarfBuzz 旋轉 90 度",
           font=label, fill=0)
    OUT.mkdir(exist_ok=True)
    img.save(OUT / "tcy_demo.png")
    print(f"[2] 輸出：{OUT / 'tcy_demo.png'}")


if __name__ == "__main__":
    main()
