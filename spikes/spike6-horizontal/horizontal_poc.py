"""Spike 6 PoC：橫排（horizontal-tb）多行流排最小驗證（honest-planning R2）。

只驗新東西：多行橫排幾何（行由上而下、字由左而右）＋ CJK em 格與行內 latin
自然寬同基線。底層水平字形擺放已由頁腳三件組驗過（Sprint 7〜12），不重驗。

紅線：CIP 樣張資料全自擬（虛構書目），非參考書 p178 內容。

輸出 out/horizontal-poc.png（gitignore），供目檢；並印 pen 座標供對比。
"""
import sys
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / "assets" / "fonts" / "SourceHanSerifTC-Regular.otf"

# 自擬 CIP 樣張（虛構，非參考書內容）
CIP_LINES = [
    "自由排版工作室 出版品預行編目資料",
    "書名：橫排測試範例（自擬）",
    "作者：測試作者　初版　2026 年",
    "ISBN 978-0-00-000000-0（平裝）",
]

SIZE_PT = 8.0
DPI = 300
SCALE = DPI / 72.0
CHAR_ADV_PT = SIZE_PT * 1.05   # CJK em 格（同內文 12.08/11.5 比例）
LINE_PITCH_PT = 14.0           # 自擬行距
LEFT_PT = 60.0                 # 自擬左邊界
TOP_PT = 40.0                  # 自擬上邊界
ASCENT_RATIO = 0.88            # 同 placement.ASCENT_RATIO
PAGE_W_PT, PAGE_H_PT = 300.0, 120.0


class Shaper:
    def __init__(self, path):
        blob = hb.Blob.from_file_path(str(path))
        self.hb = hb.Font(hb.Face(blob))
        self.upem = self.hb.face.upem
        self.ft = freetype.Face(str(path))

    def shape_ltr(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.direction = "ltr"
        buf.script = "Hani"
        buf.language = "zh-tw"
        hb.shape(self.hb, buf, {})
        return buf.glyph_infos, buf.glyph_positions

    def set_size(self, size_pt):
        self.ft.set_char_size(int(size_pt * 64), 0, DPI, DPI)
        return size_pt * (DPI / 72.0) / self.upem

    def tile(self, gid):
        self.ft.load_glyph(gid, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
        g = self.ft.glyph
        b = g.bitmap
        if b.width == 0 or b.rows == 0:
            return None, g
        data = bytes(b.buffer)
        rows = [data[r * b.pitch: r * b.pitch + b.width] for r in range(b.rows)]
        return Image.frombytes("L", (b.width, b.rows), b"".join(rows)), g


def is_ascii_run_char(ch):
    return ch.isascii() and (ch.isalnum() or ch in " -.（）")


def cells(text):
    """簡化 tokenize：連續 ascii（含空格與常見符號）成一個 latin run，其餘逐 CJK。"""
    out, run = [], ""
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch in " -."):
            run += ch
            continue
        if run:
            out.append(("latin", run))
            run = ""
        out.append(("cjk", ch))
    if run:
        out.append(("latin", run))
    return out


def draw_horizontal_line(img, shaper, text, pen_x_pt, baseline_y_pt):
    """一行橫排：cells 由左而右；CJK 走 em 格，latin 走自然寬。回傳終點 pen_x（pt）。"""
    sf = shaper.set_size(SIZE_PT)
    pen_x = pen_x_pt
    positions = []
    for kind, seg in cells(text):
        infos, poss = shaper.shape_ltr(seg)
        seg_x = pen_x
        for info, pos in zip(infos, poss):
            tile, g = shaper.tile(info.codepoint)
            gx_pt = seg_x + pos.x_offset * sf / SCALE
            if tile is not None:
                px = round(gx_pt * SCALE) + g.bitmap_left
                py = round(baseline_y_pt * SCALE) - g.bitmap_top
                img.paste(0, (px, py), tile)
            seg_x += pos.x_advance * sf / SCALE
        positions.append((kind, seg, round(pen_x, 2)))
        if kind == "cjk":
            pen_x += CHAR_ADV_PT            # CJK：em 格推進
        else:
            pen_x = seg_x                   # latin：自然寬推進
    return pen_x, positions


def main():
    shaper = Shaper(FONT)
    img = Image.new("L", (round(PAGE_W_PT * SCALE), round(PAGE_H_PT * SCALE)), 255)
    for i, line in enumerate(CIP_LINES):
        baseline_y = TOP_PT + i * LINE_PITCH_PT + SIZE_PT * ASCENT_RATIO
        end_x, positions = draw_horizontal_line(img, shaper, line, LEFT_PT, baseline_y)
        print(f"行 {i+1} baseline_y={baseline_y:.2f}pt 終點 x={end_x:.2f}pt")
        for kind, seg, x0 in positions[:3]:
            print(f"    {kind:5s} {seg!r:20s} 起 x={x0}")
    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "horizontal-poc.png"
    img.save(path)
    print(f"\n輸出：{path}")


if __name__ == "__main__":
    main()
