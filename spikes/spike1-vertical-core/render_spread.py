"""Spike 1 跨頁樣張渲染：引擎斷行 + HarfBuzz/FreeType 直排 + 參考頁並排對比。

輸入：assets/reference/（校準與逐字資料，版權紅線目錄）
輸出：spikes/spike1-vertical-core/out/
    spread_sample.png      我方引擎排出的 296x210mm 跨頁（150dpi）
    spread_comparison.png  參考頁（上）與樣張（下）並排對比
字型：內文 PMingLiU（本機驗證用，GAPS #3）；頁腳 Gill Sans MT 與標楷體替位（GAPS #2）。
幾何：全部取自實測 calibration/measurements，不用估計值。
"""
import json
import sys
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vertical_engine import Cell, check_kinsoku, flow_pages, normalize

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "assets" / "reference"
OUT = Path(__file__).resolve().parent / "out"

MING_TTC = r"C:\Windows\Fonts\mingliu.ttc"
MING_INDEX = 1  # PMingLiU
GILL_TTF = r"C:\Windows\Fonts\GIL_____.TTF"
KAI_TTF = r"C:\Windows\Fonts\kaiu.ttf"

DPI = 150
S = DPI / 72.0  # pt -> px

# 實測幾何（measurements.json / calibration.json，2026-07-10）
PAGE_W_PT, PAGE_H_PT = 839.05, 595.28
BLOCK_TOP_PT = 92.09
CHAR_ADV_PT = 12.08
LINE_PITCH_PT = 23.0
CHARS_PER_LINE = 32
SLOTS_PER_PAGE = 13
RIGHT_BASE_X_PT = 773.8  # 右頁第 0 行行軸
LEFT_BASE_X_PT = 342.9   # 左頁第 0 行行軸
BODY_SIZE_PT = 11.5


class Shaper:
    """單一字型的 HarfBuzz 塑形 + FreeType 柵格。"""

    def __init__(self, path: str, index: int = 0):
        blob = hb.Blob.from_file_path(path)
        self.hb_font = hb.Font(hb.Face(blob, index))
        self.upem = self.hb_font.face.upem
        self.ft = freetype.Face(path, index)

    def shape(self, text: str, direction: str):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.direction = direction
        buf.script = "Hani"
        buf.language = "zh-tw"
        hb.shape(self.hb_font, buf, {})
        return buf.glyph_infos, buf.glyph_positions

    def set_size(self, size_pt: float):
        self.ft.set_char_size(int(size_pt * 64), 0, DPI, DPI)
        return size_pt * S / self.upem  # font unit -> px

    def glyph_tile(self, gid: int):
        self.ft.load_glyph(gid, freetype.FT_LOAD_RENDER)
        g = self.ft.glyph
        bmp = g.bitmap
        if bmp.width == 0 or bmp.rows == 0:
            return None, g
        data = bytes(bmp.buffer)
        rows = [data[r * bmp.pitch: r * bmp.pitch + bmp.width] for r in range(bmp.rows)]
        return Image.frombytes("L", (bmp.width, bmp.rows), b"".join(rows)), g


def draw_ttb_char(img, shaper, ch, axis_x_pt, cell_top_pt, size_pt):
    """單一 CJK 字以 TTB 塑形置於字槽（行軸置中、槽頂對齊）。"""
    sf = shaper.set_size(size_pt)
    infos, poss = shaper.shape(ch, "ttb")
    pen_x, pen_y = axis_x_pt * S, cell_top_pt * S
    for info, pos in zip(infos, poss):
        tile, g = shaper.glyph_tile(info.codepoint)
        if tile is not None:
            gx = round(pen_x + pos.x_offset * sf) + g.bitmap_left
            gy = round(pen_y - pos.y_offset * sf) - g.bitmap_top
            img.paste(0, (gx, gy), tile)
        pen_x += pos.x_advance * sf
        pen_y += -pos.y_advance * sf


def render_horizontal_strip(shaper, text, size_pt):
    """LTR 塑形渲染成灰階條（供縱中橫與旋轉拉丁用）。回傳 (mask, 基線px)。"""
    sf = shaper.set_size(size_pt)
    infos, poss = shaper.shape(text, "ltr")
    asc = size_pt * S * 0.88
    desc = size_pt * S * 0.32
    width = round(sum(p.x_advance for p in poss) * sf) + 2
    height = round(asc + desc) + 2
    strip = Image.new("L", (max(width, 1), max(height, 1)), 0)
    pen_x, base_y = 0.0, asc
    for info, pos in zip(infos, poss):
        tile, g = shaper.glyph_tile(info.codepoint)
        if tile is not None:
            gx = round(pen_x + pos.x_offset * sf) + g.bitmap_left
            gy = round(base_y - pos.y_offset * sf) - g.bitmap_top
            strip.paste(255, (gx, gy), tile)
        pen_x += pos.x_advance * sf
    return strip


def draw_tcy(img, shaper, text, axis_x_pt, cell_top_pt, size_pt):
    """縱中橫：短數字串橫排塞進一個字槽，行軸置中。"""
    strip = render_horizontal_strip(shaper, text, size_pt * 0.92)
    em_px = round(size_pt * S)
    if strip.width > em_px:  # 塞不下就等比縮
        strip = strip.resize((em_px, round(strip.height * em_px / strip.width)))
    x = round(axis_x_pt * S - strip.width / 2)
    y = round(cell_top_pt * S + (CHAR_ADV_PT * S - strip.height) / 2)
    img.paste(0, (x, y), strip)


def draw_rotated_latin(img, shaper, text, axis_x_pt, cell_top_pt, size_pt):
    """長串拉丁／數字：橫排塑形後順時針轉 90 度，沿行軸向下。"""
    strip = render_horizontal_strip(shaper, text, size_pt)
    rot = strip.transpose(Image.Transpose.ROTATE_270)  # 順時針 90
    x = round(axis_x_pt * S - rot.width / 2)
    y = round(cell_top_pt * S)
    img.paste(0, (x, y), rot)


def draw_line(img, shaper, line, axis_x_pt):
    slot = line.start_slot
    for cell in line.cells:
        cell_top = BLOCK_TOP_PT + slot * CHAR_ADV_PT
        if cell.kind == "cjk":
            draw_ttb_char(img, shaper, cell.text, axis_x_pt, cell_top, BODY_SIZE_PT)
        elif cell.kind == "tcy":
            draw_tcy(img, shaper, cell.text, axis_x_pt, cell_top, BODY_SIZE_PT)
        elif cell.kind == "latin":
            draw_rotated_latin(img, shaper, cell.text, axis_x_pt, cell_top, BODY_SIZE_PT)
        slot += cell.width  # space 留白即可


def rebuild_paragraphs():
    """從逐字資料重建閱讀流（內文 + PMingLiU 標點併流，排除頁腳與空白）。"""
    data = json.loads((REF / "reference_page.json").read_text(encoding="utf-8"))
    calib = json.loads((REF / "calibration.json").read_text(encoding="utf-8"))
    centers = calib["line_x_centers"]
    offsets = calib["first_char_offsets_pt"]

    flow = [c for c in data["chars"]
            if abs(c["size"] - BODY_SIZE_PT) < 0.2
            and ("DFMingStd" in c["font"] or "PMingLiU" in c["font"])]
    lines = {i: [] for i in range(len(centers))}
    for c in flow:
        xc = (c["bbox"][0] + c["bbox"][2]) / 2
        best = min(range(len(centers)), key=lambda i: abs(centers[i] - xc))
        assert abs(centers[best] - xc) < 9, f"字元 {c['c']!r} 離行軸過遠"
        lines[best].append(c)

    paragraphs, cur, total = [], [], 0
    for i in range(len(centers)):
        col = sorted(lines[i], key=lambda c: c["bbox"][1])
        total += len(col)
        if offsets[i] > 12 and cur:  # 縮排 = 新段落
            paragraphs.append("".join(c["c"] for c in cur))
            cur = []
        cur.extend(col)
    if cur:
        paragraphs.append("".join(c["c"] for c in cur))
    return [normalize(p) for p in paragraphs], total


def draw_foot(img):
    """頁腳三件組：以實測座標繪製（替位字型，取位置對位）。"""
    calib = json.loads((REF / "calibration.json").read_text(encoding="utf-8"))
    gill = ImageFont.truetype(GILL_TTF, round(8 * S))
    kai = ImageFont.truetype(KAI_TTF, round(8 * S))
    d = ImageDraw.Draw(img)
    for c in calib["foot_elements"]:
        if c["c"].strip() == "" or c["size"] > 9:
            continue  # 空白與內文標點（？）不在此畫
        font = gill if "GillSans" in c["font"] else kai
        x, y = c["origin"][0] * S, c["origin"][1] * S
        d.text((x, y), c["c"], font=font, fill=0, anchor="ls")


def main():
    OUT.mkdir(exist_ok=True)
    paragraphs, total = rebuild_paragraphs()
    print(f"[1] 重建段落：{len(paragraphs)} 段，共 {total} 字")
    for i, p in enumerate(paragraphs):
        print(f"    段 {i + 1}（{len(p)} 字）：{p[:16]}…")

    pages = flow_pages(
        paragraphs, CHARS_PER_LINE, SLOTS_PER_PAGE,
        indent=2, para_gap_slots=1, first_para_continues=True,
    )
    all_lines = [l for page in pages for _, l in page]
    violations = check_kinsoku(all_lines)
    lengths = {}
    for l in all_lines:
        used = l.start_slot + sum(c.width for c in l.cells)
        lengths[used] = lengths.get(used, 0) + 1
    print(f"[2] 流排：{len(pages)} 頁、{len(all_lines)} 行；行長分布 {sorted(lengths.items(), reverse=True)}")
    print(f"[3] 禁則檢查：{'0 違規' if not violations else violations}")

    img = Image.new("L", (round(PAGE_W_PT * S), round(PAGE_H_PT * S)), 255)
    shaper = Shaper(MING_TTC, MING_INDEX)
    for page_idx, base_x in ((0, RIGHT_BASE_X_PT), (1, LEFT_BASE_X_PT)):
        if page_idx >= len(pages):
            break
        for slot, line in pages[page_idx]:
            draw_line(img, shaper, line, base_x - slot * LINE_PITCH_PT)
    if len(pages) > 2:
        print(f"    注意：內容溢出跨頁（共 {len(pages)} 頁），僅渲染前 2 頁")
    draw_foot(img)
    img.save(OUT / "spread_sample.png")
    print(f"[4] 樣張輸出：{OUT / 'spread_sample.png'}")

    ref = Image.open(REF / "reference_page.png").convert("L")
    if ref.size != img.size:
        ref = ref.resize(img.size)
    label_h = 56
    combo = Image.new("L", (img.width, (img.height + label_h) * 2), 255)
    label_font = ImageFont.truetype(MING_TTC, 36, index=MING_INDEX)
    d = ImageDraw.Draw(combo)
    d.text((20, 10), "參考頁：內在整理 p.030-031（華康明體、InDesign 原書）", font=label_font, fill=0)
    combo.paste(ref, (0, label_h))
    d.text((20, label_h + img.height + 10),
           "Spike 1 樣張：自製引擎（PMingLiU 替位、等距網格、禁則追出）", font=label_font, fill=0)
    combo.paste(img, (0, label_h * 2 + img.height))
    combo.save(OUT / "spread_comparison.png")
    print(f"[5] 對比圖輸出：{OUT / 'spread_comparison.png'}")


if __name__ == "__main__":
    main()
