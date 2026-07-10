"""Spike 1 管線驗通探針。

驗證三件事（PLAN 第 6 節 Phase 0 執行細則的第一步）：
1. mingliu.ttc 的 PMingLiU face 可被 uharfbuzz 與 freetype 載入
2. TTB 直排 shaping 對中文標點（，。「」）發生 vert 字形替代（與橫排 gid 對比）
3. 依 HarfBuzz 位置資料 + FreeType 柵格逐字形組圖，輸出直排 PNG：
   字由上而下、逗號句號位於字面右上、引號為直排形
"""
import sys
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

FONT_PATH = r"C:\Windows\Fonts\mingliu.ttc"
TARGET_FAMILY = "PMingLiU"
TEXT = "直排驗證「縱書」，內文之美。"
SIZE_PX = 48
OUT_DIR = Path(__file__).parent / "out"


def pick_face_index():
    probe = freetype.Face(FONT_PATH, 0)
    for i in range(probe.num_faces):
        f = freetype.Face(FONT_PATH, i)
        name = f.family_name.decode("ascii", errors="replace")
        print(f"  face[{i}] = {name}")
        if name == TARGET_FAMILY:
            return i
    raise SystemExit(f"找不到 {TARGET_FAMILY}")


def shape(index, vertical):
    blob = hb.Blob.from_file_path(FONT_PATH)
    face = hb.Face(blob, index)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(TEXT)
    buf.direction = "ttb" if vertical else "ltr"
    buf.script = "Hani"
    buf.language = "zh-tw"
    hb.shape(font, buf, {})
    return face.upem, buf.glyph_infos, buf.glyph_positions


def bmp_to_image(bmp):
    if bmp.width == 0 or bmp.rows == 0:
        return None
    data = bytes(bmp.buffer)
    rows = [data[r * bmp.pitch : r * bmp.pitch + bmp.width] for r in range(bmp.rows)]
    return Image.frombytes("L", (bmp.width, bmp.rows), b"".join(rows))


def render_vertical(index, out_png):
    upem, infos, poss = shape(index, vertical=True)
    sf = SIZE_PX / upem
    ft = freetype.Face(FONT_PATH, index)
    ft.set_pixel_sizes(0, SIZE_PX)
    width = SIZE_PX * 3
    height = round(sum(-p.y_advance for p in poss) * sf) + SIZE_PX * 2
    img = Image.new("L", (width, height), 255)
    pen_x, pen_y = width // 2, SIZE_PX  # 行軸中心、上邊距
    for info, pos in zip(infos, poss):
        ft.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        g = ft.glyph
        tile = bmp_to_image(g.bitmap)
        if tile is not None:
            gx = pen_x + round(pos.x_offset * sf) + g.bitmap_left
            gy = pen_y - round(pos.y_offset * sf) - g.bitmap_top
            img.paste(0, (gx, gy), tile)
        pen_x += round(pos.x_advance * sf)
        pen_y += round(-pos.y_advance * sf)  # HarfBuzz y 向上為正，TTB 的 y_advance 為負
    img.save(out_png)
    return out_png


def main():
    print("[1] 列舉 TTC faces：")
    index = pick_face_index()
    print(f"    選用 face[{index}] {TARGET_FAMILY}")

    print("[2] 橫排 vs 直排 gid 對比（驗 vert 替代）：")
    _, h_infos, _ = shape(index, vertical=False)
    _, v_infos, v_poss = shape(index, vertical=True)
    assert len(h_infos) == len(v_infos), "橫直排 glyph 數不一致"
    substituted = 0
    for ch, hi, vi in zip(TEXT, h_infos, v_infos):
        mark = "vert替代" if hi.codepoint != vi.codepoint else ""
        if mark:
            substituted += 1
        print(f"    {ch}  h_gid={hi.codepoint:5d}  v_gid={vi.codepoint:5d}  {mark}")
    print(f"    共 {substituted} 個字形發生直排替代")

    neg_adv = all(p.y_advance < 0 for p in v_poss)
    print(f"[3] TTB y_advance 全為負（往下推進）：{neg_adv}")

    OUT_DIR.mkdir(exist_ok=True)
    out = render_vertical(index, OUT_DIR / "probe_vertical.png")
    print(f"[4] 直排樣張輸出：{out}")


if __name__ == "__main__":
    main()
