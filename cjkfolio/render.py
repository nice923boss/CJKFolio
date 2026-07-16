"""單頁 PNG 渲染後端：HarfBuzz vert 塑形 ＋ FreeType 柵格，樣式驅動。

自 Spike 1 render_spread.py 產品化：跨頁改為單頁 A5（PLAN §9 單頁完稿），
幾何由主版（Margins＋Grid）推導，字型由樣式經 FontRegistry 解析。
奇數書頁＝右頁（右翻書），書口（outer）在右；偶數書頁鏡像，行軸自訂口推。
鏡像依書頁號（first_page 位移後），非版面頁號（GAPS #16）。
PNG 為 Phase 1 視覺驗收後端；PDF/X 寫出層於後續 Sprint 進場。
"""
from dataclasses import dataclass
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image, ImageDraw

from .fonts import DEFAULT_FONT_DIR, FontRegistry
from .images import resolve_placed_images
from .layout import (
    layout_document,
    line_justified_advance,
    style_advance_pt,
    style_line_slots,
)
from .placement import ASCENT_RATIO, horizontal_cell_advance_pt
from .primitives import (
    StrokeLine,
    cip_frame_rect,
    figure_slot_edges,
    figure_slot_rect,
    fit_image_rect,
    toc_rule_segments,
)
from .styles import MasterPage, Template

PT_PER_MM = 72.0 / 25.4


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM


def is_right_page(book_number: int) -> bool:
    """右頁（書口在右）＝偶數書頁。

    真書《內在整理》三向互證（Sprint 22，A 級）：頁碼側（偶頁頁碼書口右）、
    書眉側（書名書眉皆偶頁）、版心側（偶頁右邊距 21mm＝outer 精確）。
    右翻直排書 spread＝（偶右、奇左），讀序右→左＝頁碼小→大。
    """
    return book_number % 2 == 0


def line_axis_x_pt(
    template: Template,
    master: MasterPage,
    slot: int,
    page_number: int,
    line_slots: int = 1,
) -> float:
    """第 slot 行槽的行軸（欄中心）x 座標，pt。傳入書頁號，偶數＝右頁書口在右；
    mirror=false 恆以 outer 槽為起排側（B 部扉先例）。"""
    page_w = mm_to_pt(template.page_width_mm)
    outer_side = is_right_page(page_number) or not master.mirror
    margin_mm = master.margins.outer_mm if outer_side else master.margins.inner_mm
    axis0 = page_w - mm_to_pt(margin_mm) - master.grid.base_size_pt / 2
    return axis0 - (slot + (line_slots - 1) / 2) * master.grid.line_pitch_pt


def horizontal_left_x_pt(master: MasterPage, book_number: int) -> float:
    """橫排頁文字左起 x（pt）：偶數（右頁）左側＝訂口內推；奇數（左頁）左側＝書口；
    mirror=false 恆以 outer 槽為起排側（p178 版權頁＝左頁，左側書口 25.81mm）。"""
    if not master.mirror or not is_right_page(book_number):
        left_mm = master.margins.outer_mm
    else:
        left_mm = master.margins.inner_mm
    return mm_to_pt(left_mm)


def horizontal_baseline_y_pt(master: MasterPage, slot: int, size_pt: float,
                             line_slots: int = 1) -> float:
    """橫排第 slot 行（由上而下）的基線 y（pt）。v1 CIP 皆 line_slots=1。"""
    top = mm_to_pt(master.margins.top_mm)
    return top + slot * master.grid.line_pitch_pt + size_pt * ASCENT_RATIO


def rule_break_ranges(template: Template, master: MasterPage, breaks,
                      book_number: int) -> tuple:
    """穿線行的虛線斷開 x 區間（頁座標 pt，兩後端同源，Sprint 21）。

    區間＝行槽範圍（行軸中心±行槽半寬）向兩側加斷開邊距：行前方（直排讀序
    x 大側）加 rule.break_before_pt、行後方加 break_after_pt（p002／p003 量測）。
    """
    rule = master.rule
    out = []
    for b in breaks:
        axis = line_axis_x_pt(template, master, b.slot, book_number,
                              line_slots=b.line_slots)
        half = master.grid.line_pitch_pt * b.line_slots / 2
        out.append((axis - half - rule.break_after_pt,
                    axis + half + rule.break_before_pt))
    return tuple(sorted(out))


class Shaper:
    """單一字型檔的 HarfBuzz 塑形 ＋ FreeType 柵格。"""

    def __init__(self, path, index: int = 0, dpi: int = 150):
        self.path = str(path)
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


def _missing_chars(text: str, infos) -> list:
    """回傳塑形結果中缺字（gid 0）對應的來源字元（供 PNG 端不沉默警告）。"""
    return [text[i.cluster] for i in infos if i.codepoint == 0 and i.cluster < len(text)]


def _draw_ttb_char(img, shaper, ch, axis_x_pt, cell_top_pt, size_pt, scale):
    """單一 CJK 字以 TTB 塑形置於字槽（行軸置中、槽頂對齊）。回傳缺字來源字元。"""
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
    return _missing_chars(ch, infos)


def _render_horizontal_strip(shaper, text, size_pt, scale):
    """LTR 塑形渲染成灰階條（供縱中橫與旋轉拉丁用）。回傳（strip, 缺字來源字元）。"""
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
    return strip, _missing_chars(text, infos)


def _draw_tcy(img, shaper, text, axis_x_pt, cell_top_pt, size_pt, advance_pt, scale):
    """縱中橫：短數字串橫排塞進一個字槽，行軸置中。回傳缺字來源字元。"""
    strip, missing = _render_horizontal_strip(shaper, text, size_pt * 0.92, scale)
    em_px = round(size_pt * scale)
    if strip.width > em_px:  # 塞不下就等比縮
        strip = strip.resize((em_px, round(strip.height * em_px / strip.width)))
    x = round(axis_x_pt * scale - strip.width / 2)
    y = round(cell_top_pt * scale + (advance_pt * scale - strip.height) / 2)
    img.paste(0, (x, y), strip)
    return missing


def _draw_rotated_latin(img, shaper, text, axis_x_pt, cell_top_pt, size_pt, scale):
    """長串拉丁／數字：橫排塑形後順時針轉 90 度，沿行軸向下。回傳缺字來源字元。"""
    strip, missing = _render_horizontal_strip(shaper, text, size_pt, scale)
    rot = strip.transpose(Image.Transpose.ROTATE_270)
    x = round(axis_x_pt * scale - rot.width / 2)
    y = round(cell_top_pt * scale)
    img.paste(0, (x, y), rot)
    return missing


def _draw_stroke_rect(img, rect, scale):
    """描邊矩形（PIL "L" 模式，outline=0 純黑）：top-down pt × scale → px。

    PNG 為灰階預覽，不表達 CMYK（描邊 CMYK 差異只在 PDF 後端）；框線純黑同文字。
    """
    draw = ImageDraw.Draw(img)
    w_px = max(1, round(rect.line_width_pt * scale))
    box = [round(rect.x0 * scale), round(rect.y0 * scale),
           round(rect.x1 * scale), round(rect.y1 * scale)]
    draw.rectangle(box, outline=0, width=w_px)


def _draw_stroke_line(img, line, scale):
    """描邊線段（PIL "L" 模式）：top-down pt × scale → px，dash_on_pt>0 時分段畫。

    PNG 為灰階預覽：描邊灰值以 255×(1−k) 近似（只取 k 分量，c/m/y 不表達；
    CMYK 忠實表達只在 PDF 後端）。分段節奏與 pdf 端 `d` 算符同源（同一 StrokeLine）。
    """
    draw = ImageDraw.Draw(img)
    gray = max(0, min(255, round(255 * (1.0 - line.cmyk[3]))))
    w_px = max(1, round(line.line_width_pt * scale))
    x0, y0 = line.x0 * scale, line.y0 * scale
    x1, y1 = line.x1 * scale, line.y1 * scale
    if line.dash_on_pt <= 0:  # 實線
        draw.line([(x0, y0), (x1, y1)], fill=gray, width=w_px)
        return
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if length <= 0:
        return
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    on, off = line.dash_on_pt * scale, line.dash_off_pt * scale
    t = 0.0
    while t < length:
        seg = min(on, length - t)
        draw.line([(x0 + ux * t, y0 + uy * t),
                   (x0 + ux * (t + seg), y0 + uy * (t + seg))], fill=gray, width=w_px)
        t += on + off


def _draw_horizontal_cell(img, shaper, text, pen_x_pt, baseline_y_pt, size_pt, scale):
    """橫排一個 cell：LTR 塑形直接落在頁面 (pen_x, baseline)。回傳缺字來源字元。

    與 pdf_writer 橫排路徑同源：字形擺放走 hb ltr，頁面 pen 推進由 layout 決定
    （cjk 走 em 格、latin 走自然寬，見 placement.horizontal_cell_advance_pt）。
    """
    sf = shaper.set_size(size_pt)
    infos, poss = shaper.shape(text, "ltr")
    pen_x, base_y = pen_x_pt * scale, baseline_y_pt * scale
    for info, pos in zip(infos, poss):
        tile, g = shaper.glyph_tile(info.codepoint)
        if tile is not None:
            gx = round(pen_x + pos.x_offset * sf) + g.bitmap_left
            gy = round(base_y - pos.y_offset * sf) - g.bitmap_top
            img.paste(0, (gx, gy), tile)
        pen_x += pos.x_advance * sf
    return _missing_chars(text, infos)


class PageRenderer:
    def __init__(self, template: Template, master_name: str, dpi: int = 150, font_dir=None):
        self.template = template
        self.master = template.masters[master_name]
        self.dpi = dpi
        self.scale = dpi / 72.0
        self.registry = FontRegistry(font_dir or DEFAULT_FONT_DIR)
        self._shapers: dict = {}
        self.fonts_used: set = set()
        self.notdef_warnings: list = []

    def _note_missing(self, shaper: Shaper, chars) -> None:
        """缺字不沉默：以 .notdef 輸出並警告（訊息格式與 pdf_writer 一致）。"""
        for ch in chars:
            label = f"字元 {ch!r}（U+{ord(ch):04X}）" if ch else "未知字元"
            msg = f"{label} 在 {Path(shaper.path).name} 無字形，以 .notdef 輸出"
            if msg not in self.notdef_warnings:
                self.notdef_warnings.append(msg)

    def _shaper_for(self, style) -> Shaper:
        resolved = self.registry.resolve(style.font_family, style.font_weight)
        key = (str(resolved.path), resolved.index)
        if key not in self._shapers:
            self._shapers[key] = Shaper(resolved.path, resolved.index, self.dpi)
        self.fonts_used.add(str(resolved.path))
        return self._shapers[key]

    def _draw_footer(self, img, book_number: int, footer_texts: dict) -> None:
        """頁腳三件組（頁碼＋書眉）：水平文字，錨定書口側，依書頁號奇偶鏡像。"""
        master, template = self.master, self.template
        page_w_pt = mm_to_pt(template.page_width_mm)
        page_odd = book_number % 2 == 1  # 奇偶 gate（pages 配置語意）
        outer_right = is_right_page(book_number) or not master.mirror  # 書口側別
        for item in master.footer.values():
            if item.pages == "odd" and not page_odd:
                continue
            if item.pages == "even" and page_odd:
                continue
            text = footer_texts.get(item.source, "")
            if not text:
                continue
            style = template.character_styles[item.style]
            shaper = self._shaper_for(style)
            strip, missing = _render_horizontal_strip(shaper, text, style.size_pt, self.scale)
            self._note_missing(shaper, missing)
            ascent_px = style.size_pt * self.scale * 0.88
            y = round(item.baseline_from_top_pt * self.scale - ascent_px)
            if outer_right:  # 書口在右：文字右緣對齊 outer_offset
                x = round((page_w_pt - item.outer_offset_pt) * self.scale) - strip.width
            else:
                x = round(item.outer_offset_pt * self.scale)
            img.paste(0, (x, y), strip)

    def _draw_vertical_body(self, img, page, book_number: int) -> None:
        master, template = self.master, self.template
        top_pt = mm_to_pt(master.margins.top_mm)
        for placed in page.placed:
            style = template.paragraph_styles[placed.style]
            shaper = self._shaper_for(style)
            advance = style_advance_pt(style, master.grid)
            axis = line_axis_x_pt(
                template, master, placed.slot, book_number,
                line_slots=style_line_slots(style, master.grid),
            )
            # 齊行：非段末行行首行尾雙錨定（縮排偏移用網格字距，內容用實效字距）
            adv, _status = line_justified_advance(placed.line, advance)
            line_top = top_pt + placed.line.start_slot * advance + placed.lead_offset_pt
            content_i = 0
            for cell in placed.line.cells:
                cell_top = line_top + content_i * adv
                if cell.char_style:  # run 覆寫字型與級數；字槽網格仍依段落樣式
                    cstyle = template.character_styles[cell.char_style]
                    use_shaper, use_size = self._shaper_for(cstyle), cstyle.size_pt
                else:
                    use_shaper, use_size = shaper, style.size_pt
                if cell.kind == "cjk":
                    missing = _draw_ttb_char(img, use_shaper, cell.text, axis, cell_top, use_size, self.scale)
                elif cell.kind == "tcy":
                    missing = _draw_tcy(img, use_shaper, cell.text, axis, cell_top, use_size, adv, self.scale)
                elif cell.kind == "latin":
                    missing = _draw_rotated_latin(img, use_shaper, cell.text, axis, cell_top, use_size, self.scale)
                else:
                    missing = []
                self._note_missing(use_shaper, missing)
                content_i += cell.width  # space 留白即可

    def _draw_horizontal_body(self, img, page, book_number: int) -> None:
        """橫排 body（版權頁-CIP）：行由上而下、字由左而右，不齊行。"""
        master, template = self.master, self.template
        for placed in page.placed:
            style = template.paragraph_styles[placed.style]
            shaper = self._shaper_for(style)
            char_adv = style_advance_pt(style, master.grid)
            baseline_y = horizontal_baseline_y_pt(
                master, placed.slot, style.size_pt,
                style_line_slots(style, master.grid),
            )
            pen_x = horizontal_left_x_pt(master, book_number) + placed.line.start_slot * char_adv
            for cell in placed.line.cells:
                if cell.char_style:  # run 覆寫字型與級數
                    cstyle = template.character_styles[cell.char_style]
                    use_shaper, use_size = self._shaper_for(cstyle), cstyle.size_pt
                else:
                    use_shaper, use_size = shaper, style.size_pt
                if cell.kind != "space":
                    missing = _draw_horizontal_cell(
                        img, use_shaper, cell.text, pen_x, baseline_y, use_size, self.scale)
                    self._note_missing(use_shaper, missing)
                pen_x += horizontal_cell_advance_pt(use_shaper, cell, use_size, char_adv)

    def _draw_frame(self, img, page, book_number: int) -> None:
        """主版向量裝飾框（v1：橫排 CIP 細框）：圍住內容網格盒，與 pdf_writer 同源。"""
        n_lines = max(pl.slot for pl in page.placed) + 1
        rect = cip_frame_rect(
            self.master, horizontal_left_x_pt(self.master, book_number),
            n_lines, self.master.frame,
        )
        _draw_stroke_rect(img, rect, self.scale)

    def _draw_rule(self, img, rule_breaks, book_number: int) -> None:
        """主版向量裝飾線（v1：目錄天頭水平虛線）：貫穿頁寬、在穿線行（篇名嵌線）
        處斷開，與 pdf_writer 同源。"""
        gaps = rule_break_ranges(self.template, self.master, rule_breaks, book_number)
        for seg in toc_rule_segments(mm_to_pt(self.template.page_width_mm),
                                     self.master.rule, gaps):
            _draw_stroke_line(img, seg, self.scale)

    def _draw_figure(self, img, book_number: int) -> None:
        """主版圖框保留區佔位框（v1：G 圖文版照片區）：承版心的淡虛線四邊，與
        pdf_writer._figure 幾何同源；有置入圖時改由 _draw_image 畫實際照片取代。"""
        page_w = mm_to_pt(self.template.page_width_mm)
        rect = figure_slot_rect(page_w, self.master, is_right_page(book_number),
                                self.master.figure)
        for edge in figure_slot_edges(rect, self.master.figure):
            _draw_stroke_line(img, edge, self.scale)

    def _draw_image(self, img, gray, book_number: int) -> None:
        """置入圖到主版 figure 保留區（v1：G 圖文版照片）：等比縮放置中（contain），
        以灰階（§9 單 K）貼入畫布、取代佔位框。幾何與 pdf_writer._image 同源
        （figure_slot_rect＋fit_image_rect）；gray 為 PIL "L" 影像。"""
        page_w = mm_to_pt(self.template.page_width_mm)
        slot = figure_slot_rect(page_w, self.master, is_right_page(book_number),
                                self.master.figure)
        box = fit_image_rect(slot.x0, slot.y0, slot.x1, slot.y1, gray.width, gray.height)
        w_px = max(1, round((box.x1 - box.x0) * self.scale))
        h_px = max(1, round((box.y1 - box.y0) * self.scale))
        resized = gray.resize((w_px, h_px))
        img.paste(resized, (round(box.x0 * self.scale), round(box.y0 * self.scale)))

    def _draw_toc_marks(self, img, marks, book_number: int) -> None:
        """目錄條目記號：行軸垂直引導線（實線）＋直排逐位頁碼（底錨），
        幾何取 layout.TocEntryMark，與 pdf_writer 同源。"""
        toc = self.master.toc
        for m in marks:
            axis = line_axis_x_pt(self.template, self.master, m.slot, book_number,
                                  line_slots=m.line_slots)
            if m.leader_y1_pt > m.leader_y0_pt:  # 重疊守護（violations 已列不沉默）
                _draw_stroke_line(img, StrokeLine(
                    x0=axis, y0=m.leader_y0_pt, x1=axis, y1=m.leader_y1_pt,
                    cmyk=toc.leader_cmyk, line_width_pt=toc.leader_width_pt,
                ), self.scale)
            cstyle = self.template.character_styles[m.char_style]
            shaper = self._shaper_for(cstyle)
            for i, digit in enumerate(m.digits):
                cell_top = m.page_no_top_pt + i * m.digit_advance_pt
                missing = _draw_tcy(img, shaper, digit, axis, cell_top,
                                    m.digit_size_pt, m.digit_advance_pt, self.scale)
                self._note_missing(shaper, missing)

    def render_page(self, page, footer_texts=None, book_number=None,
                    vertical: bool = True, toc_marks=(),
                    rule_breaks=(), image=None) -> Image.Image:
        template = self.template
        if getattr(page, "master", ""):  # 逐頁主版（節式主版指派，Sprint 51）
            self.master = template.masters[page.master]
        if book_number is None:  # 預設書頁號＝版面頁號（first_page=1）
            book_number = page.number
        size_px = (
            round(mm_to_pt(template.page_width_mm) * self.scale),
            round(mm_to_pt(template.page_height_mm) * self.scale),
        )
        img = Image.new("L", size_px, 255)
        # 主版向量框（v1 cip-box 為橫排原件，幾何依橫排網格盒；底層裝飾先畫）
        if not vertical and self.master.frame and page.placed:
            self._draw_frame(img, page, book_number)
        # 主版向量線（v1 toc-rule 為直排目錄原件，篇名嵌線處斷開；底層裝飾先畫）
        if vertical and self.master.rule and page.placed:
            self._draw_rule(img, rule_breaks, book_number)
        # 主版圖框保留區（v1 photo-slot）：有置入圖畫實際照片取代佔位框，否則畫淡虛線骨架
        if image is not None:
            _path, gray = image
            self._draw_image(img, gray, book_number)
        elif vertical and self.master.figure and page.placed:
            self._draw_figure(img, book_number)
        if vertical:
            self._draw_vertical_body(img, page, book_number)
        else:
            self._draw_horizontal_body(img, page, book_number)
        if toc_marks:  # 目錄條目頁碼＋引導線（marks 僅目錄主版產生）
            self._draw_toc_marks(img, toc_marks, book_number)
        if footer_texts:
            self._draw_footer(img, book_number, footer_texts)
        return img


@dataclass(frozen=True)
class RenderResult:
    paths: list
    violations: list
    fonts_used: list
    font_warnings: list
    justify_stats: dict
    images_placed: int = 0  # 置入 figure 保留區的照片數（v1 灰階單 K）


def render_document(doc, template: Template, out_dir, dpi: int = 150,
                    basename: str = "page", font_dir=None,
                    footer: bool = True, first_page: int = 1,
                    image_base_dir=None) -> RenderResult:
    layout = layout_document(doc, template)
    renderer = PageRenderer(template, doc.master, dpi=dpi, font_dir=font_dir)
    masters_by_page = {p.number: template.masters[p.master] for p in layout.pages}
    images_by_page = resolve_placed_images(
        doc, masters_by_page, base_dir=image_base_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for page in layout.pages:
        book_number = page.number + first_page - 1  # 書頁號（鏡像與頁腳奇偶依此）
        texts = None
        if footer and masters_by_page[page.number].footer:  # 頁腳依該頁主版 gate
            texts = {
                "number": str(book_number),
                "title": doc.title,
            }
        img = renderer.render_page(page, footer_texts=texts, book_number=book_number,
                                   vertical=page.vertical,  # 逐頁方向（節式混向，Sprint 53）
                                   toc_marks=layout.toc_marks.get(page.number, ()),
                                   rule_breaks=layout.rule_breaks.get(page.number, ()),
                                   image=images_by_page.get(page.number))
        path = out / f"{basename}-{page.number:03d}.png"
        img.save(path)
        paths.append(path)
    return RenderResult(
        paths=paths,
        violations=list(layout.violations),
        fonts_used=sorted(renderer.fonts_used),
        font_warnings=list(renderer.registry.warnings) + list(renderer.notdef_warnings),
        justify_stats=dict(layout.justify_stats),
        images_placed=len(images_by_page),
    )
