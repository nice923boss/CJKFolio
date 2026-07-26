"""PDF 寫出層第一片（PLAN Phase 1，向 PDF/X-1a DoD 推進）。

範圍（Sprint 8 決議）：
- 盒框依 PLAN §9：MediaBox 154×216mm、TrimBox 148×210mm 置中、BleedBox＝MediaBox
  （無裁切標記時）；crop_marks=True 時 MediaBox 外擴、BleedBox 縮回 trim＋出血。
- 文字一律 DeviceCMYK 單 K92（§9 內文 K90〜92 區間，v1 定 0.92）。
- 字型子集嵌入：CFF（思源，CID-keyed）不保留 GID、內容流用原 CID 走 charset
  對映（InDesign 同款形態）；TTF（辰宇／粉圓）retain_gids＋CIDToGIDMap /Identity。
  皆帶 ToUnicode 與 CIDSet（PDF/X-1a 對子集 CID 字型的要求）。
- 幾何與 PNG 渲染同源（placement 層），逐字顯式 Tm 定位；禁則與斷行已在
  排版層完成並烘焙（§9：PDF/X 只忠實嵌入已排好的結果）。
- X-1a:2001 識別（Sprint 10）：header 1.3、Info GTS 鍵＋Trapped＋ModDate、
  OutputIntent（預設 JC200103 registry 識別，依 ISO 15930-1 免嵌描述檔；
  自訂識別須以 icc_profile 嵌 DestOutputProfile）、XMP metadata stream。
  機械 preflight 見 preflight.py（獨立解析驗證）。
- 圖片置入（Sprint 50）：影像 XObject 置入主版 figure 保留區、contain 等比置中，
  幾何與 render 同源（figure_slot_rect＋fit_image_rect）。色彩空間依來源分流
  （Sprint 92）：灰階單 K 走 DeviceGray、CMYK 來源走 DeviceCMYK（§9 兩者皆合法）。
  RGB 來源（Sprint 137）只在 pdfx="none"（非 PDF/X 的一般 PDF）留得住；PDF/X 形態
  一律轉灰嵌入並記 PdfResult.image_color_warnings，不沉默也不擋流程。
"""
import collections
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .color_convert import DEFAULT_INTENT, convert_placed_images
from .fonts import DEFAULT_FONT_DIR, FontRegistry
from .frames import resolve_text_frames
from .images import (
    PRINT_IMAGE_MODES,
    EmbeddedImage,
    ImageResolution,
    resolution_warnings,
    resolve_placed_images,
)
from .ink import MAX_TAC, InkUse, image_max_tac, tac_percent, tac_warnings
from .pdf_content import _Content, _fmt
from .pdf_fonts import EmbeddedFont
from .pdf_objects import PdfBuilder
from .pdfx_meta import (  # re-export：既有 import 路徑（preflight／editor）不變
    KNOWN_PRINT_CONDITIONS,
    PDFX_CONFORMANCE,
    PDFX_PROFILES,
    PDFX_VERSION,
    REGISTRY_URL,
    PdfxProfile,
    resolve_output_icc,
    xmp_packet,
)
from .layout import (
    line_justified_advance,
    ruby_group_height,
    style_advance_pt,
    style_line_slots,
)
from .placement import (
    horizontal_cell_advance_pt,
    horizontal_placements,
    rotated_latin_placements,
    group_ruby_axis_and_top,
    run_width_pt,
    tcy_placements,
    ttb_char_placements,
)
from .font_license import enforce_license_policy
from .press_marks import (
    MARK_CMYK,
    MARK_LENGTH_MM,
    MARK_WIDTH_PT,
    REG_CMYK,
    REG_SINGLE_K_CMYK,
    emit_marks,
    page_boxes_pt,
    resolve_mark_margin_mm,
)
from .primitives import (
    cip_frame_rect,
    figure_slot_edges,
    figure_slot_rect,
    fit_image_rect,
    toc_rule_segments,
)
from .render import (
    Shaper,
    book_number_for,
    horizontal_baseline_y_pt,
    horizontal_left_x_pt,
    is_right_page,
    line_axis_x_pt,
    mm_to_pt,
    rule_break_ranges,
    sheet_face_for,
)
from .styles import DEFAULT_TEXT_CMYK, resolve_text_cmyk
from .wrap import layout_with_wrap

BLEED_MM = 3.0
TEXT_K = DEFAULT_TEXT_CMYK[3]  # 內文單 K92（§10 決議：§9 K90〜92 區間取 92；styles 單一來源）

# 標記（裁切角標 Sprint 83、印前標記 Sprint 109）的參數、盒框推導與繪製同住
# press_marks 模組；一致性形態（PdfxProfile／PDFX_PROFILES）、ICC registry 名單與
# 輸出描述檔驗證同住 pdfx_meta 模組（Sprint 137 行數上限管理）；本檔 re-export
# 兩者以維持既有 import 路徑。


def _pdf_text_string(s: str) -> str:
    return "<FEFF" + s.encode("utf-16-be").hex().upper() + ">"


def _pdf_string(s: str) -> str:
    """PDF 字串：純 ASCII 走括號字面（跳脫 \\ 與括號），否則 UTF-16 hex。"""
    if all(ord(c) < 128 for c in s):
        esc = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return f"({esc})"
    return _pdf_text_string(s)


def _pdf_date(dt: datetime) -> str:
    off = dt.strftime("%z")  # astimezone() 保證帶時區，如 +0800
    return f"D:{dt.strftime('%Y%m%d%H%M%S')}{off[:3]}'{off[3:]}'"


# ---------- 頁面寫出 ----------

class _PdfPageWriter:
    """把 LayoutPage 轉為內容流；幾何與 render.PageRenderer 同源（placement 層）。"""

    def __init__(self, template, master_name: str, font_dir=None,
                 mark_margin_pt: float = 0.0, reg_cmyk=REG_CMYK,
                 allow_rgb_images: bool = False):
        self.template = template
        # 非 PDF/X 輸出才留 RGB 影像；送印形態轉灰並記 image_color_warnings
        self.allow_rgb_images = allow_rgb_images
        self.image_color_warnings: list = []
        self.master = template.masters[master_name]
        self.registry = FontRegistry(font_dir or DEFAULT_FONT_DIR)
        self._shapers: dict = {}
        self._fonts: dict = {}
        self._images: dict = {}  # 解析後路徑 → EmbeddedImage（跨頁去重）
        # 逐次置入的解析度紀錄（同圖多次置入各記一筆＝各自繪製尺寸不同）
        self._image_resolutions: list = []
        # TAC 檢核產出側（Sprint 93）：全書用過的 DeviceCMYK 著色值、
        # 每張獨立影像的最高墨量（{圖檔名: TAC%}；同圖多次置入墨量相同故只記一次）
        self.cmyk_used: set = set()
        self._image_inks: dict = {}
        self.fonts_used: set = set()
        self.notdef_warnings: list = []
        self.bleed_pt = mm_to_pt(BLEED_MM)
        self.mark_margin_pt = mark_margin_pt  # MediaBox 於 BleedBox 外的標記帶餘裕
        self.reg_cmyk = reg_cmyk  # 套準十字色（樣式值，非語意開關）
        # 印前標記著色值（Sprint 109 分帳；不是豁免，見 _Content.__init__）
        self.mark_cmyk_used: set = set()
        # 內容座標原點偏移（MediaBox 左下 → TrimBox 左下）：無標記時＝出血，
        # 開啟標記時＝出血＋標記餘裕（外擴 MediaBox 不得位移內文相對 trim）
        self.origin_pt = self.bleed_pt + mark_margin_pt
        self.page_h_pt = mm_to_pt(template.page_height_mm)

    def _shaper_for(self, style):
        resolved = self.registry.resolve(style.font_family, style.font_weight)
        key = (str(resolved.path), resolved.index)
        if key not in self._shapers:
            self._shapers[key] = Shaper(resolved.path, resolved.index)
        self.fonts_used.add(str(resolved.path))
        return key, self._shapers[key]

    def _font_for(self, key) -> EmbeddedFont:
        if key not in self._fonts:
            self._fonts[key] = EmbeddedFont(Path(key[0]), f"F{len(self._fonts) + 1}")
        return self._fonts[key]

    def _emit(self, content: _Content, key, placements) -> None:
        font = self._font_for(key)
        for pl in placements:
            if pl.gid == 0:  # 缺字不沉默：以 .notdef 輸出並警告
                # pl.ch 可能是整個 cluster（連字，Sprint 142），取首枚報碼位
                label = f"字元 {pl.ch!r}（U+{ord(pl.ch[0]):04X}）" if pl.ch else "未知字元"
                msg = f"{label} 在 {Path(key[0]).name} 無字形，以 .notdef 輸出"
                if msg not in self.notdef_warnings:
                    self.notdef_warnings.append(msg)
            code = font.use(pl.gid, pl.ch)
            x = self.origin_pt + pl.x_pt
            y = self.page_h_pt + self.origin_pt - pl.y_pt  # top-down → y-up
            content.show(font.res_name, code, x, y, pl.size_pt, pl.rotated)

    def _footer(self, content: _Content, sheet_face: int, footer_texts: dict) -> None:
        master, template = self.master, self.template
        page_w = mm_to_pt(template.page_width_mm)
        page_odd = sheet_face % 2 == 1  # 奇偶 gate（pages 配置語意＝實體左右頁）
        outer_right = is_right_page(sheet_face) or not master.mirror  # 書口側別
        for item in master.footer.values():
            if item.pages == "odd" and not page_odd:
                continue
            if item.pages == "even" and page_odd:
                continue
            text = item.text or footer_texts.get(item.source, "")  # 字面覆寫優先
            if not text:
                continue
            style = template.character_styles[item.style]
            key, shaper = self._shaper_for(style)
            width = run_width_pt(shaper, text, style.size_pt)
            if outer_right:  # 書口在右：文字右緣對齊 outer_offset
                pen_x = page_w - item.outer_offset_pt - width
            else:
                pen_x = item.outer_offset_pt
            content.set_fill(resolve_text_cmyk(template, style))
            self._emit(content, key, horizontal_placements(
                shaper, text, pen_x, item.baseline_from_top_pt, style.size_pt))

    def _vertical_body(self, content: _Content, page, sheet_face: int) -> None:
        master, template = self.master, self.template
        top_pt = mm_to_pt(master.margins.top_mm)
        for placed in page.placed:
            style = template.paragraph_styles[placed.style]
            key, shaper = self._shaper_for(style)
            advance = style_advance_pt(style, master.grid)
            axis = line_axis_x_pt(
                template, master, placed.slot, sheet_face,
                line_slots=style_line_slots(style, master.grid),
            )
            # 齊行：非段末行行首行尾雙錨定（縮排偏移用網格字距，內容用實效字距）
            adv, _status = line_justified_advance(placed.line, advance)
            line_top = top_pt + placed.line.start_slot * advance + placed.lead_offset_pt
            content_i = 0
            cells = placed.line.cells
            for ci, cell in enumerate(cells):
                cell_top = line_top + content_i * adv
                if cell.char_style:  # run 覆寫字型與級數；字槽網格仍依段落樣式
                    cstyle = template.character_styles[cell.char_style]
                    use_key, use_shaper = self._shaper_for(cstyle)
                    use_size = cstyle.size_pt
                else:
                    cstyle = None
                    use_key, use_shaper, use_size = key, shaper, style.size_pt
                cell_top += cell.glyph_offset * use_size  # 字形位移（em×字級，Sprint 117）
                if cell.kind == "cjk":
                    pls = ttb_char_placements(use_shaper, cell.text, axis, cell_top, use_size)
                    if cell.ruby:  # ruby：字右側鄰欄、於 base 群組範圍置中（同 render 同源）
                        rx, rtop, rsize = group_ruby_axis_and_top(
                            axis, cell_top, ruby_group_height(cells, ci, adv),
                            use_size, len(cell.ruby))
                        pls = pls + ttb_char_placements(use_shaper, cell.ruby, rx, rtop, rsize)
                elif cell.kind == "tcy":
                    pls = tcy_placements(use_shaper, cell.text, axis, cell_top, use_size, adv)
                elif cell.kind == "latin":
                    pls = rotated_latin_placements(use_shaper, cell.text, axis, cell_top, use_size)
                else:
                    pls = []
                content.set_fill(resolve_text_cmyk(template, cstyle, style))
                self._emit(content, use_key, pls)
                content_i += cell.width

    def _horizontal_body(self, content: _Content, page, sheet_face: int) -> None:
        """橫排 body（版權頁-CIP）：行由上而下、字由左而右，不齊行。

        幾何與 render._draw_horizontal_body 同源（同一組 left_x／baseline_y／advance）。
        """
        master, template = self.master, self.template
        for placed in page.placed:
            style = template.paragraph_styles[placed.style]
            key, shaper = self._shaper_for(style)
            char_adv = style_advance_pt(style, master.grid)
            baseline_y = horizontal_baseline_y_pt(
                master, placed.slot, style.size_pt,
                style_line_slots(style, master.grid),
            )
            pen_x = horizontal_left_x_pt(master, sheet_face) + placed.line.start_slot * char_adv
            for cell in placed.line.cells:
                if cell.char_style:  # run 覆寫字型與級數
                    cstyle = template.character_styles[cell.char_style]
                    use_key, use_shaper = self._shaper_for(cstyle)
                    use_size = cstyle.size_pt
                else:
                    cstyle = None
                    use_key, use_shaper, use_size = key, shaper, style.size_pt
                if cell.kind != "space":
                    content.set_fill(resolve_text_cmyk(template, cstyle, style))
                    self._emit(content, use_key, horizontal_placements(
                        use_shaper, cell.text, pen_x, baseline_y, use_size))
                pen_x += horizontal_cell_advance_pt(use_shaper, cell, use_size, char_adv)

    def _frame(self, content: _Content, page, sheet_face: int) -> None:
        """主版向量框（v1 橫排 CIP 細框）：與 render._draw_frame 幾何同源，CMYK 描邊。"""
        n_lines = max(pl.slot for pl in page.placed) + 1
        rect = cip_frame_rect(
            self.master, horizontal_left_x_pt(self.master, sheet_face),
            n_lines, self.master.frame,
        )
        x_ll = self.origin_pt + rect.x0
        y_ll = self.page_h_pt + self.origin_pt - rect.y1  # top-down 下緣 → y-up 左下角
        content.stroke_rect(rect.cmyk, rect.line_width_pt, x_ll, y_ll,
                            rect.x1 - rect.x0, rect.y1 - rect.y0)

    def _rule(self, content: _Content, rule_breaks, sheet_face: int) -> None:
        """主版向量線（v1 目錄天頭水平虛線）：篇名嵌線處斷開，
        與 render._draw_rule 幾何同源（rule_break_ranges＋toc_rule_segments），CMYK 描邊。"""
        gaps = rule_break_ranges(self.template, self.master, rule_breaks, sheet_face)
        for line in toc_rule_segments(mm_to_pt(self.template.page_width_mm),
                                      self.master.rule, gaps):
            y_up = self.page_h_pt + self.origin_pt - line.y0  # top-down → y-up（水平線 y0=y1）
            content.stroke_line(line.cmyk, line.line_width_pt,
                                self.origin_pt + line.x0, y_up,
                                self.origin_pt + line.x1, y_up,
                                line.dash_on_pt, line.dash_off_pt)

    def _figure(self, content: _Content, sheet_face: int) -> None:
        """主版圖框保留區佔位框（v1 G 圖文版照片區）：承版心四邊淡虛線，與
        render._draw_figure 幾何同源（figure_slot_rect＋edges），CMYK 描邊；
        top-down → y-up 逐端點加出血偏移。有置入圖時改由 _image 畫實際照片取代。"""
        page_w = mm_to_pt(self.template.page_width_mm)
        rect = figure_slot_rect(page_w, self.master, is_right_page(sheet_face),
                                self.master.figure)
        for edge in figure_slot_edges(rect, self.master.figure):
            content.stroke_line(
                edge.cmyk, edge.line_width_pt,
                self.origin_pt + edge.x0, self.page_h_pt + self.origin_pt - edge.y0,
                self.origin_pt + edge.x1, self.page_h_pt + self.origin_pt - edge.y1,
                edge.dash_on_pt, edge.dash_off_pt)

    def _image(self, content: _Content, entry, sheet_face: int,
               page_number: int) -> None:
        """置入圖：等比縮放置中（contain），與 render._draw_image 幾何同源
        （fit_image_rect）；top-down 下緣 → y-up 左下角。
        entry＝(解析後路徑, PIL 影像, rect|None)；影像色彩空間依來源分流
        （"L"→DeviceGray 單 K、"CMYK"→DeviceCMYK、"RGB"→DeviceRGB，
        images.open_placed）；rect＝任意圖框（trim pt、top-down，Sprint 54，
        可溢出版心入出血）、None＝主版 figure 保留區；同路徑跨頁共用單一 XObject。

        RGB 只在非 PDF/X 輸出留得住（Sprint 137）：送印形態於此轉灰階並記一筆
        image_color_warnings。轉灰不擋流程（同 PPI／TAC／字型授權慣例：據實說，
        由人決定換圖或改形態），但一定要說，因為螢幕上看到的是彩色。"""
        path, pil, rect = entry
        if path not in self._images:
            if pil.mode not in PRINT_IMAGE_MODES and not self.allow_rgb_images:
                self.image_color_warnings.append(
                    f"{Path(path).name}：{pil.mode} 影像已轉灰階嵌入"
                    f"（PDF/X 只收 CMYK 或 Grayscale；要保留彩色請選一般 PDF 輸出，"
                    f"或先於影像軟體轉 CMYK 後置入）")
                pil = pil.convert("L")
            self._images[path] = EmbeddedImage(pil, f"Im{len(self._images) + 1}")
            # 最高單點墨量（TAC 檢核產出側）：同圖多次置入墨量相同，隨去重只算一次。
            # RGB 不記：墨量是印刷色彩空間才有的量（ink.image_max_tac 亦快速失敗）。
            if pil.mode in PRINT_IMAGE_MODES:
                self._image_inks[Path(path).name] = image_max_tac(pil)
        emb = self._images[path]
        if rect is None:
            page_w = mm_to_pt(self.template.page_width_mm)
            slot = figure_slot_rect(page_w, self.master, is_right_page(sheet_face),
                                    self.master.figure)
            rect = (slot.x0, slot.y0, slot.x1, slot.y1)
        box = fit_image_rect(rect[0], rect[1], rect[2], rect[3], emb.width, emb.height)
        self._image_resolutions.append(ImageResolution(
            path=Path(path).name, page=page_number,
            px_w=emb.width, px_h=emb.height,
            draw_w_pt=box.x1 - box.x0, draw_h_pt=box.y1 - box.y0))
        content.draw_image(
            emb.res_name, box.x1 - box.x0, box.y1 - box.y0,
            self.origin_pt + box.x0, self.page_h_pt + self.origin_pt - box.y1)

    def _text_frame(self, content: _Content, placement) -> None:
        """獨立文字框（Sprint 55）：欄幾何取 frames.FramePlacement（與 render
        同源），逐字格 emit 復用直排 placements 助手（框內不齊行、等距）。"""
        style = self.template.paragraph_styles[placement.style]
        key, shaper = self._shaper_for(style)
        content.set_fill(resolve_text_cmyk(self.template, style))
        for fl in placement.lines:
            content_i = 0
            for cell in fl.line.cells:
                cell_top = fl.top_pt + content_i * fl.advance_pt
                if cell.kind == "cjk":
                    pls = ttb_char_placements(shaper, cell.text, fl.axis_x_pt,
                                              cell_top, fl.size_pt)
                elif cell.kind == "tcy":
                    pls = tcy_placements(shaper, cell.text, fl.axis_x_pt, cell_top,
                                         fl.size_pt, fl.advance_pt)
                elif cell.kind == "latin":
                    pls = rotated_latin_placements(shaper, cell.text, fl.axis_x_pt,
                                                   cell_top, fl.size_pt)
                else:
                    pls = []
                self._emit(content, key, pls)
                content_i += cell.width

    def _toc_marks(self, content: _Content, marks, sheet_face: int) -> None:
        """目錄條目記號：行軸垂直引導線（實線）＋直排逐位頁碼（底錨），
        幾何取 layout.TocEntryMark，與 render._draw_toc_marks 同源。"""
        toc = self.master.toc
        for m in marks:
            axis = line_axis_x_pt(self.template, self.master, m.slot, sheet_face,
                                  line_slots=m.line_slots)
            if m.leader_y1_pt > m.leader_y0_pt:  # 重疊守護（violations 已列不沉默）
                content.stroke_line(
                    toc.leader_cmyk, toc.leader_width_pt,
                    self.origin_pt + axis, self.page_h_pt + self.origin_pt - m.leader_y0_pt,
                    self.origin_pt + axis, self.page_h_pt + self.origin_pt - m.leader_y1_pt,
                )
            cstyle = self.template.character_styles[m.char_style]
            key, shaper = self._shaper_for(cstyle)
            content.set_fill(resolve_text_cmyk(self.template, cstyle))
            for i, digit in enumerate(m.digits):
                cell_top = m.page_no_top_pt + i * m.digit_advance_pt
                self._emit(content, key, tcy_placements(
                    shaper, digit, axis, cell_top, m.digit_size_pt, m.digit_advance_pt))

    def build_page(self, page, footer_texts=None, sheet_face=None,
                   vertical: bool = True, toc_marks=(), rule_breaks=(),
                   images=(), frames=(), crop_marks: bool = False,
                   press_marks: bool = False) -> bytes:
        if getattr(page, "master", ""):  # 逐頁主版（節式主版指派，Sprint 51）
            self.master = self.template.masters[page.master]
        if sheet_face is None:  # 預設紙面號＝版面頁號（first_page=1）
            sheet_face = page.number
        content = _Content()
        if crop_marks or press_marks:  # 標記環（trim 外，與內容不重疊；先 emit）
            emit_marks(
                content,
                trim_w_pt=mm_to_pt(self.template.page_width_mm),
                trim_h_pt=mm_to_pt(self.template.page_height_mm),
                bleed_pt=self.bleed_pt, origin_pt=self.origin_pt,
                page_h_pt=self.page_h_pt, mm_to_pt=mm_to_pt,
                crop=crop_marks, press=press_marks, reg_cmyk=self.reg_cmyk)
        # 主版向量框（v1 cip-box 為橫排原件，幾何依橫排網格盒；底層裝飾先 emit）
        if not vertical and self.master.frame and page.placed:
            self._frame(content, page, sheet_face)
        # 主版向量線（v1 toc-rule 為直排目錄原件，篇名嵌線處斷開；底層裝飾先 emit）
        if vertical and self.master.rule and page.placed:
            self._rule(content, rule_breaks, sheet_face)
        # 主版圖框保留區（photo-slot）：槽式圖取代佔位框；佔位框只看槽是否仍空
        # （rect 任意圖框不填槽，InDesign 空框導引語意，Sprint 54）
        slot_filled = any(rect is None for _p, _g, rect in images)
        if vertical and self.master.figure and page.placed and not slot_filled:
            self._figure(content, sheet_face)
        for entry in images:  # 文件序＝繪製序
            self._image(content, entry, sheet_face, page.number)
        if vertical:
            self._vertical_body(content, page, sheet_face)
        else:
            self._horizontal_body(content, page, sheet_face)
        if toc_marks:  # 目錄條目頁碼＋引導線（marks 僅目錄主版產生）
            self._toc_marks(content, toc_marks, sheet_face)
        for placement in frames:  # 獨立文字框（自由佈局層，body 之上）
            self._text_frame(content, placement)
        if footer_texts:
            self._footer(content, sheet_face, footer_texts)
        self.cmyk_used |= content.cmyk_used  # 全書著色值彙整（TAC 檢核產出側）
        self.mark_cmyk_used |= content.mark_cmyk_used  # 標記帳本（來源標示用）
        return content.finish()


# ---------- 匯出入口 ----------

@dataclass(frozen=True)
class PdfResult:
    path: Path
    page_count: int
    violations: list
    fonts_used: list
    font_warnings: list
    embedded_fonts: list  # [{base, file, glyphs, bytes}]
    output_condition_identifier: str  # 寫進 OutputIntent 的識別；一般 PDF 無此鍵＝""
    icc_embedded: bool
    justify_stats: dict
    images_placed: int = 0  # 嵌入的影像 XObject 數（同路徑去重）
    image_colorspaces: dict = field(default_factory=dict)  # {"/DeviceGray": n, ...}
    pdfx_label: str = "PDF/X-1a:2001"  # 一致性形態標籤（X-1a 預設；X-4 選項）
    crop_marks: bool = False  # 是否含裁切標記（opt-in；MediaBox 外擴、BleedBox=trim+出血）
    press_marks: bool = False  # 是否含印前標記（opt-in；套準十字＋色條＋灰梯尺）
    registration_single_k: bool = False  # 套準十字改單 K100（墨量全綠，但不曬在 CMY 版）
    license_warnings: tuple = ()  # 字型授權警告（fsType 機器層＋name 表名義授權層）
    image_resolutions: tuple = ()  # 逐次置入的 ImageResolution（來源像素＋繪製尺寸）
    ppi_warnings: tuple = ()       # 實效 PPI 低於 §9 300ppi 的影像警告（不擋流程）
    ink_uses: tuple = ()           # 著色與影像的最高墨量 InkUse（依 TAC 降序）
    tac_warnings: tuple = ()       # 總墨量超上限（預設 §9 320%）的警告（不擋流程）
    image_color_warnings: tuple = ()  # RGB 影像已轉灰／已依描述檔轉 CMYK 的告知（不擋流程）


def export_pdf(doc, template, out_path, *, pages=None, footer: bool = True,
               first_page: int = 1, font_dir=None, compress: bool = True,
               output_condition_identifier: str = "JC200103",
               output_condition: str = "Japan Color 2001 Coated",
               icc_profile=None, image_base_dir=None,
               pdfx: str = "x-1a", crop_marks: bool = False,
               press_marks: bool = False,
               registration_single_k: bool = False,
               color_convert: bool = False,
               rendering_intent: str = DEFAULT_INTENT,
               license_policy: str = "warn",
               max_tac: float = MAX_TAC) -> PdfResult:
    """文件＋模版 → PDF/X（預設 X-1a:2001；pdfx="x-4" 選 X-4:2010）。

    pdfx="none"（Sprint 137）輸出**非 PDF/X** 的一般 PDF：不寫 X 識別鍵與
    OutputIntent、header 1.4，RGB 置入圖原樣以 DeviceRGB 嵌入（其餘形態一律轉灰並
    記 image_color_warnings）。這是螢幕用途的彩色檔，不是送印稿。
    pages=None 全頁；否則為版面頁號清單（1 起算）。
    X-1a：output_condition_identifier 命中 KNOWN_PRINT_CONDITIONS（ICC registry 名）
    時免嵌描述檔；自訂識別須以 icc_profile 提供 CMYK 輸出 ICC。
    X-4（ISO 15930-7）：強制嵌 DestOutputProfile，故 icc_profile 必填（registry
    免嵌不足），header 升 1.6、GTS_PDFXVersion=PDF/X-4 且無 GTS_PDFXConformance。
    置入圖（doc.images）以影像 XObject 嵌入（色彩空間依來源分流，見 images.open_placed），
    路徑相對 image_base_dir 解析。
    color_convert=True（Sprint 139）把 RGB 置入圖依 icc_profile 轉 CMYK 再嵌（灰階與
    CMYK 來源不動），故須有 icc_profile；rendering_intent 見 color_convert 模組。
    顏色正確性由描述檔與印廠決定，本產品只負責照描述檔換算。
    crop_marks=True 加裁切標記（§9）：MediaBox 於 BleedBox 外擴 MARK_LENGTH_MM、
    BleedBox 縮回 trim＋出血、8 條單 K 角標；預設 False 時輸出與無標記相同（BleedBox
    ＝MediaBox，向後相容）。
    license_policy="warn"（預設）字型授權問題只列 license_warnings 不擋；"block"
    則於寫檔前中止並拋 ValueError，不留半成品檔案。
    max_tac 為總墨量上限（%，預設 §9 保守下限 320）：印廠條件，只影響 tac_warnings
    的判定門檻，不改任何寫出的位元（同 ink 模組「只警告不擋流程」）。
    """
    if pdfx not in PDFX_PROFILES:
        raise ValueError(
            f"未知 pdfx 形態 {pdfx!r}，可選 {sorted(PDFX_PROFILES)}")
    profile = PDFX_PROFILES[pdfx]
    if not doc.title and profile.is_pdfx:
        raise ValueError(
            f"{profile.label} 要求 Info /Title：文件 meta.title 不可為空")
    icc_bytes = resolve_output_icc(profile, icc_profile,
                                   output_condition_identifier)
    if color_convert and not icc_bytes:
        raise ValueError(
            f"color_convert 要求目標 CMYK 輸出描述檔（{profile.label}）："
            "請以 icc_profile 提供，registry 免嵌識別不足以作為轉換目標")
    if registration_single_k and not press_marks:
        raise ValueError(
            "registration_single_k 需搭 press_marks（套準十字只在印前標記中產生）"
        )
    mark_margin_mm = resolve_mark_margin_mm(crop_marks, press_marks)
    layout = layout_with_wrap(doc, template, first_page=first_page)
    writer = _PdfPageWriter(template, doc.master, font_dir=font_dir,
                            mark_margin_pt=mm_to_pt(mark_margin_mm),
                            reg_cmyk=REG_SINGLE_K_CMYK if registration_single_k
                            else REG_CMYK,
                            allow_rgb_images=not profile.is_pdfx)
    masters_by_page = {p.number: template.masters[p.master] for p in layout.pages}
    images_by_page = resolve_placed_images(
        doc, masters_by_page, base_dir=image_base_dir)
    convert_notes = []
    if color_convert:   # 轉在寫出層之前：寫出層看到的已是 CMYK，墨量帳自然接手
        images_by_page, convert_notes = convert_placed_images(
            images_by_page, icc_bytes, rendering_intent, icc_profile)
    frames_by_page = resolve_text_frames(doc, template, masters_by_page)
    frame_violations = [v for pls in frames_by_page.values()
                        for pl in pls for v in pl.violations]
    selected = list(layout.pages)
    if pages is not None:
        wanted = set(pages)
        missing = wanted - {p.number for p in selected}
        if missing:
            raise ValueError(f"文件排版共 {len(selected)} 頁，無第 {sorted(missing)} 頁")
        selected = [p for p in selected if p.number in wanted]
    contents = []
    for page in selected:
        # 頁碼數字＝書頁號（封面翻開後起算）；側別與鏡像＝紙面號（Sprint 145 SSOT）
        book_number = book_number_for(page.number, first_page, layout.cover_pages)
        sheet_face = sheet_face_for(page.number, first_page)
        texts = None  # 頁腳依該頁主版 gate；封面不編頁碼故一律不繪
        if (footer and page.number > layout.cover_pages  # 封面與補頁不編頁碼
                and not page.blank and masters_by_page[page.number].footer):
            texts = {"number": str(book_number), "title": doc.title}
        contents.append(writer.build_page(
            page, footer_texts=texts, sheet_face=sheet_face,
            vertical=page.vertical,  # 逐頁方向（節式混向，Sprint 53）
            toc_marks=layout.toc_marks.get(page.number, ()),
            rule_breaks=layout.rule_breaks.get(page.number, ()),
            images=images_by_page.get(page.number, ()),
            frames=frames_by_page.get(page.number, ()),
            crop_marks=crop_marks, press_marks=press_marks))

    pdf = PdfBuilder(compress=compress)
    embedded = []
    font_refs = []
    for key in sorted(writer._fonts, key=lambda k: int(writer._fonts[k].res_name[1:])):
        emb = writer._fonts[key]
        num, stats = emb.emit(pdf)
        font_refs.append(f"/{emb.res_name} {num} 0 R")
        embedded.append(stats)
    image_refs = []
    for path in sorted(writer._images, key=lambda p: int(writer._images[p].res_name[2:])):
        img_num = writer._images[path].emit(pdf)
        image_refs.append(f"/{writer._images[path].res_name} {img_num} 0 R")
    res_parts = [f"/Font << {' '.join(font_refs)} >>"]
    if image_refs:
        res_parts.append(f"/XObject << {' '.join(image_refs)} >>")
    resources_num = pdf.add(f"<< {' '.join(res_parts)} >>")
    media, trim, bleed = page_boxes_pt(template, mark_margin_mm=mark_margin_mm)
    box = lambda b: f"[{_fmt(b[0])} {_fmt(b[1])} {_fmt(b[2])} {_fmt(b[3])}]"  # noqa: E731
    pages_num = pdf.reserve()
    kids = []
    for content in contents:
        content_num = pdf.stream("", content)
        kids.append(pdf.add(
            f"<< /Type /Page /Parent {pages_num} 0 R /MediaBox {box(media)} "
            f"/TrimBox {box(trim)} /BleedBox {box(bleed)} "
            f"/Resources {resources_num} 0 R /Contents {content_num} 0 R >>"
        ))
    pdf.set(pages_num,
            f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>")
    # --- PDF/X 識別（§9 預設 X-1a:2001／ISO 15930-1；X-4:2010／ISO 15930-7 選項）---
    # 一般 PDF（pdfx="none"）跳過整段：OutputIntent 是 PDF/X 的宣告，不是通用鍵。
    oi_num, oi_id = None, ""   # 識別回報空字串：檔案裡沒有的鍵不對外宣稱
    if profile.is_pdfx:
        oi_id = output_condition_identifier
        oi_parts = [
            "/Type /OutputIntent", "/S /GTS_PDFX",
            f"/OutputConditionIdentifier {_pdf_string(output_condition_identifier)}",
            f"/OutputCondition {_pdf_string(output_condition)}",
            f"/Info {_pdf_string(output_condition)}",
        ]
        if output_condition_identifier in KNOWN_PRINT_CONDITIONS:
            oi_parts.append(f"/RegistryName {_pdf_string(REGISTRY_URL)}")
        if icc_bytes is not None:
            icc_num = pdf.stream(" /N 4", icc_bytes)
            oi_parts.append(f"/DestOutputProfile {icc_num} 0 R")
        oi_num = pdf.add(f"<< {' '.join(oi_parts)} >>")

    now = datetime.now().astimezone()
    xmp_num = pdf.stream(
        " /Type /Metadata /Subtype /XML",
        xmp_packet(doc.title, now.isoformat(timespec="seconds"),
                   profile.version, profile.conformance),
        compress=False,  # metadata stream 不壓縮，外部工具可直讀
    )
    oi_entry = f"/OutputIntents [{oi_num} 0 R] " if oi_num is not None else ""
    catalog_num = pdf.add(
        f"<< /Type /Catalog /Pages {pages_num} 0 R "
        f"/Metadata {xmp_num} 0 R {oi_entry}"
        f"/ViewerPreferences << /Direction /R2L >> >>"
    )
    date = _pdf_date(now)
    gts = ""
    if profile.is_pdfx:
        gts = f" /GTS_PDFXVersion ({profile.version})"
        if profile.conformance is not None:  # X-4 無 GTS_PDFXConformance
            gts += f" /GTS_PDFXConformance ({profile.conformance})"
    info_num = pdf.add(
        f"<< /Title {_pdf_text_string(doc.title)} "
        f"/Producer (CJKFolio) /Creator (CJKFolio) "
        f"/CreationDate ({date}) /ModDate ({date}) /Trapped /False"
        f"{gts} >>"
    )

    # 授權檢查置於寫檔前：block 政策要擋得住就不能先產出檔案再抱怨
    lic_warnings = enforce_license_policy(license_policy, writer.fonts_used)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf.build(catalog_num, info_num, version=profile.header))
    # 總墨量（TAC，§9 ≤ 320〜340%）：著色值與影像各記最高墨量，依 TAC 降序
    # 標記色標明來源（Sprint 109）：同一色值若內容也用到，仍歸「著色」（保守，
    # 不誤標）。這只是判讀依據，不改任何門檻，report.ok 不因此變動。
    ink_uses = tuple(sorted(
        [InkUse(kind="著色", label=" ".join(f"{v:g}" for v in cmyk),
                tac=tac_percent(cmyk))
         for cmyk in writer.cmyk_used]
        + [InkUse(kind="印前標記", label=" ".join(f"{v:g}" for v in cmyk),
                  tac=tac_percent(cmyk))
           for cmyk in writer.mark_cmyk_used if cmyk not in writer.cmyk_used]
        + [InkUse(kind="影像", label=name, tac=tac)
           for name, tac in writer._image_inks.items()],
        key=lambda u: -u.tac))
    return PdfResult(
        path=out,
        page_count=len(contents),
        violations=list(layout.violations) + frame_violations,
        fonts_used=sorted(writer.fonts_used),
        font_warnings=list(writer.registry.warnings) + list(writer.notdef_warnings),
        embedded_fonts=embedded,
        output_condition_identifier=oi_id,
        icc_embedded=icc_bytes is not None,
        justify_stats=dict(layout.justify_stats),
        images_placed=len(writer._images),
        image_colorspaces=collections.Counter(
            emb.colorspace for emb in writer._images.values()),
        pdfx_label=profile.label,
        crop_marks=crop_marks,
        press_marks=press_marks,
        registration_single_k=registration_single_k,
        license_warnings=lic_warnings,
        image_resolutions=tuple(writer._image_resolutions),
        ppi_warnings=tuple(resolution_warnings(writer._image_resolutions)),
        ink_uses=ink_uses,
        tac_warnings=tuple(tac_warnings(ink_uses, max_tac)),
        image_color_warnings=tuple(convert_notes) + tuple(writer.image_color_warnings),
    )
