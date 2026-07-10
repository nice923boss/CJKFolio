"""單頁 PNG 渲染後端：HarfBuzz vert 塑形 ＋ FreeType 柵格，樣式驅動。

自 Spike 1 render_spread.py 產品化：跨頁改為單頁 A5（PLAN §9 單頁完稿），
幾何由主版（Margins＋Grid）推導，字型由樣式經 FontRegistry 解析。
奇數頁＝右頁（右翻書），書口（outer）在右；偶數頁鏡像，行軸自訂口推。
PNG 為 Phase 1 視覺驗收後端；PDF/X 寫出層於後續 Sprint 進場。
"""
from dataclasses import dataclass
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image

from .fonts import DEFAULT_FONT_DIR, FontRegistry
from .layout import layout_document, style_advance_pt, style_line_slots
from .styles import MasterPage, Template

PT_PER_MM = 72.0 / 25.4


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM


def line_axis_x_pt(
    template: Template,
    master: MasterPage,
    slot: int,
    page_number: int,
    line_slots: int = 1,
) -> float:
    """第 slot 行槽的行軸（欄中心）x 座標，pt。奇數頁書口在右。"""
    page_w = mm_to_pt(template.page_width_mm)
    outer_side = (page_number % 2 == 1) or not master.mirror
    margin_mm = master.margins.outer_mm if outer_side else master.margins.inner_mm
    axis0 = page_w - mm_to_pt(margin_mm) - master.grid.base_size_pt / 2
    return axis0 - (slot + (line_slots - 1) / 2) * master.grid.line_pitch_pt


class Shaper:
    """單一字型檔的 HarfBuzz 塑形 ＋ FreeType 柵格。"""

    def __init__(self, path, index: int = 0, dpi: int = 150):
        blob = hb.Blob.from_file_path(str(path))
        self.hb_font = hb.Font(hb.Face(blob, index))
        self.upem = self.hb_font.face.upem
        self.ft = freetype.Face(str(path), index)
        self.dpi = dpi

    def shape(self, text: str, direction: str):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.direction = direction
        buf.script = "Hani"
        buf.language = "zh-tw"
        hb.shape(self.hb_font, buf, {})
        return buf.glyph_infos, buf.glyph_positions

    def set_size(self, size_pt: float) -> float:
        self.ft.set_char_size(int(size_pt * 64), 0, self.dpi, self.dpi)
        return size_pt * (self.dpi / 72.0) / self.upem  # font unit -> px

    def glyph_tile(self, gid: int):
        # NO_HINTING：印刷級柵格不需 hinting，且部分手寫 TTF（辰宇、粉圓）的
        # bytecode 會使 FreeType 拋 too many function definitions
        self.ft.load_glyph(gid, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
        g = self.ft.glyph
        bmp = g.bitmap
        if bmp.width == 0 or bmp.rows == 0:
            return None, g
        data = bytes(bmp.buffer)
        rows = [data[r * bmp.pitch: r * bmp.pitch + bmp.width] for r in range(bmp.rows)]
        return Image.frombytes("L", (bmp.width, bmp.rows), b"".join(rows)), g


def _draw_ttb_char(img, shaper, ch, axis_x_pt, cell_top_pt, size_pt, scale):
    """單一 CJK 字以 TTB 塑形置於字槽（行軸置中、槽頂對齊）。"""
    sf = shaper.set_size(size_pt)
    infos, poss = shaper.shape(ch, "ttb")
    pen_x, pen_y = axis_x_pt * scale, cell_top_pt * scale
    for info, pos in zip(infos, poss):
        tile, g = shaper.glyph_tile(info.codepoint)
        if tile is not None:
            gx = round(pen_x + pos.x_offset * sf) + g.bitmap_left
            gy = round(pen_y - pos.y_offset * sf) - g.bitmap_top
            img.paste(0, (gx, gy), tile)
        pen_x += pos.x_advance * sf
        pen_y += -pos.y_advance * sf


def _render_horizontal_strip(shaper, text, size_pt, scale):
    """LTR 塑形渲染成灰階條（供縱中橫與旋轉拉丁用）。"""
    sf = shaper.set_size(size_pt)
    infos, poss = shaper.shape(text, "ltr")
    asc = size_pt * scale * 0.88
    desc = size_pt * scale * 0.32
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


def _draw_tcy(img, shaper, text, axis_x_pt, cell_top_pt, size_pt, advance_pt, scale):
    """縱中橫：短數字串橫排塞進一個字槽，行軸置中。"""
    strip = _render_horizontal_strip(shaper, text, size_pt * 0.92, scale)
    em_px = round(size_pt * scale)
    if strip.width > em_px:  # 塞不下就等比縮
        strip = strip.resize((em_px, round(strip.height * em_px / strip.width)))
    x = round(axis_x_pt * scale - strip.width / 2)
    y = round(cell_top_pt * scale + (advance_pt * scale - strip.height) / 2)
    img.paste(0, (x, y), strip)


def _draw_rotated_latin(img, shaper, text, axis_x_pt, cell_top_pt, size_pt, scale):
    """長串拉丁／數字：橫排塑形後順時針轉 90 度，沿行軸向下。"""
    strip = _render_horizontal_strip(shaper, text, size_pt, scale)
    rot = strip.transpose(Image.Transpose.ROTATE_270)
    x = round(axis_x_pt * scale - rot.width / 2)
    y = round(cell_top_pt * scale)
    img.paste(0, (x, y), rot)


class PageRenderer:
    def __init__(self, template: Template, master_name: str, dpi: int = 150, font_dir=None):
        self.template = template
        self.master = template.masters[master_name]
        self.dpi = dpi
        self.scale = dpi / 72.0
        self.registry = FontRegistry(font_dir or DEFAULT_FONT_DIR)
        self._shapers: dict = {}
        self.fonts_used: set = set()

    def _shaper_for(self, style) -> Shaper:
        resolved = self.registry.resolve(style.font_family, style.font_weight)
        key = (str(resolved.path), resolved.index)
        if key not in self._shapers:
            self._shapers[key] = Shaper(resolved.path, resolved.index, self.dpi)
        self.fonts_used.add(str(resolved.path))
        return self._shapers[key]

    def _draw_footer(self, img, page, footer_texts: dict) -> None:
        """頁腳三件組（頁碼＋書眉）：水平文字，錨定書口側，奇偶頁鏡像。"""
        master, template = self.master, self.template
        page_w_pt = mm_to_pt(template.page_width_mm)
        odd = (page.number % 2 == 1) or not master.mirror
        for item in master.footer.values():
            if item.pages == "odd" and not odd:
                continue
            if item.pages == "even" and odd:
                continue
            text = footer_texts.get(item.source, "")
            if not text:
                continue
            style = template.character_styles[item.style]
            shaper = self._shaper_for(style)
            strip = _render_horizontal_strip(shaper, text, style.size_pt, self.scale)
            ascent_px = style.size_pt * self.scale * 0.88
            y = round(item.baseline_from_top_pt * self.scale - ascent_px)
            if odd:  # 書口在右：文字右緣對齊 outer_offset
                x = round((page_w_pt - item.outer_offset_pt) * self.scale) - strip.width
            else:
                x = round(item.outer_offset_pt * self.scale)
            img.paste(0, (x, y), strip)

    def render_page(self, page, footer_texts=None) -> Image.Image:
        master, template = self.master, self.template
        size_px = (
            round(mm_to_pt(template.page_width_mm) * self.scale),
            round(mm_to_pt(template.page_height_mm) * self.scale),
        )
        img = Image.new("L", size_px, 255)
        top_pt = mm_to_pt(master.margins.top_mm)
        for placed in page.placed:
            style = template.paragraph_styles[placed.style]
            if style.writing_mode != "vertical-rl":
                raise ValueError(
                    f"樣式「{style.name}」writing_mode={style.writing_mode}，"
                    "Phase 1 渲染僅支援 vertical-rl（橫排於後續 Sprint）"
                )
            shaper = self._shaper_for(style)
            advance = style_advance_pt(style, master.grid)
            axis = line_axis_x_pt(
                template, master, placed.slot, page.number,
                line_slots=style_line_slots(style, master.grid),
            )
            slot_i = placed.line.start_slot
            for cell in placed.line.cells:
                cell_top = top_pt + slot_i * advance
                if cell.char_style:  # run 覆寫字型與級數；字槽網格仍依段落樣式
                    cstyle = template.character_styles[cell.char_style]
                    use_shaper, use_size = self._shaper_for(cstyle), cstyle.size_pt
                else:
                    use_shaper, use_size = shaper, style.size_pt
                if cell.kind == "cjk":
                    _draw_ttb_char(img, use_shaper, cell.text, axis, cell_top, use_size, self.scale)
                elif cell.kind == "tcy":
                    _draw_tcy(img, use_shaper, cell.text, axis, cell_top, use_size, advance, self.scale)
                elif cell.kind == "latin":
                    _draw_rotated_latin(img, use_shaper, cell.text, axis, cell_top, use_size, self.scale)
                slot_i += cell.width  # space 留白即可
        if footer_texts:
            self._draw_footer(img, page, footer_texts)
        return img


@dataclass(frozen=True)
class RenderResult:
    paths: list
    violations: list
    fonts_used: list
    font_warnings: list


def render_document(doc, template: Template, out_dir, dpi: int = 150,
                    basename: str = "page", font_dir=None,
                    footer: bool = True, first_page: int = 1) -> RenderResult:
    layout = layout_document(doc, template)
    renderer = PageRenderer(template, doc.master, dpi=dpi, font_dir=font_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for page in layout.pages:
        texts = None
        if footer and renderer.master.footer:
            texts = {
                "number": str(page.number + first_page - 1),
                "title": doc.title,
            }
        img = renderer.render_page(page, footer_texts=texts)
        path = out / f"{basename}-{page.number:03d}.png"
        img.save(path)
        paths.append(path)
    return RenderResult(
        paths=paths,
        violations=list(layout.violations),
        fonts_used=sorted(renderer.fonts_used),
        font_warnings=list(renderer.registry.warnings),
    )
