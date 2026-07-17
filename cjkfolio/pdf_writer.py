"""PDF 寫出層第一片（PLAN Phase 1，向 PDF/X-1a DoD 推進）。

範圍（Sprint 8 決議）：
- 盒框依 PLAN §9：MediaBox 154×216mm、TrimBox 148×210mm 置中、BleedBox＝MediaBox。
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
- 圖片置入（Sprint 50）：DeviceGray 影像 XObject（§9 灰階單 K），置入主版 figure
  保留區、contain 等比置中，幾何與 render 同源（figure_slot_rect＋fit_image_rect）。
"""
import hashlib
import zlib
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from .fonts import DEFAULT_FONT_DIR, FontRegistry
from .frames import resolve_text_frames
from .images import EmbeddedImage, resolve_placed_images
from .pdf_fonts import EmbeddedFont
from .pdfx_meta import xmp_packet
from .layout import (
    layout_document,
    line_justified_advance,
    style_advance_pt,
    style_line_slots,
)
from .placement import (
    horizontal_cell_advance_pt,
    horizontal_placements,
    rotated_latin_placements,
    run_width_pt,
    tcy_placements,
    ttb_char_placements,
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
    horizontal_baseline_y_pt,
    horizontal_left_x_pt,
    is_right_page,
    line_axis_x_pt,
    mm_to_pt,
    rule_break_ranges,
)
from .styles import DEFAULT_TEXT_CMYK, resolve_text_cmyk

BLEED_MM = 3.0
TEXT_K = DEFAULT_TEXT_CMYK[3]  # 內文單 K92（§10 決議：§9 K90〜92 區間取 92；styles 單一來源）

PDFX_VERSION = "PDF/X-1:2001"       # Info /GTS_PDFXVersion（ISO 15930-1）
PDFX_CONFORMANCE = "PDF/X-1a:2001"  # Info /GTS_PDFXConformance
REGISTRY_URL = "http://www.color.org"
# ICC 特性化資料登錄名（www.color.org/chardata）常用子集；命中者依 ISO 15930-1
# 可免嵌 DestOutputProfile。未列名（印廠自訂條件）須以 icc_profile 補描述檔。
KNOWN_PRINT_CONDITIONS = frozenset({
    "CGATS TR 001",
    "FOGRA27", "FOGRA39", "FOGRA51", "FOGRA52",
    "IFRA26",
    "JC200103", "JC200104", "JCN2002", "JCW2003",
})


def page_boxes_pt(template, bleed_mm: float = BLEED_MM):
    """(MediaBox, TrimBox)，皆 pt；BleedBox＝MediaBox（§9）。"""
    w, h = mm_to_pt(template.page_width_mm), mm_to_pt(template.page_height_mm)
    b = mm_to_pt(bleed_mm)
    return (0.0, 0.0, w + 2 * b, h + 2 * b), (b, b, b + w, b + h)


def _fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _fill_op(cmyk) -> str:
    """DeviceCMYK 文字填色算符（小寫 k）。"""
    c, m, y, k = cmyk
    return f"{_fmt(c)} {_fmt(m)} {_fmt(y)} {_fmt(k)} k"


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


def _validate_output_profile(data: bytes, source) -> None:
    """X-1a DestOutputProfile 須為 CMYK 輸出裝置（prtr）ICC。"""
    name = Path(source).name
    if len(data) < 132:
        raise ValueError(f"ICC 描述檔 {name} 過短（{len(data)} bytes），非有效 ICC")
    if data[12:16] != b"prtr":
        raise ValueError(
            f"ICC 描述檔 {name} 裝置類別 {data[12:16]!r} 非輸出裝置 prtr，"
            "X-1a 的 DestOutputProfile 須為印刷輸出描述檔"
        )
    if data[16:20] != b"CMYK":
        raise ValueError(
            f"ICC 描述檔 {name} 色彩空間 {data[16:20]!r} 非 CMYK（PLAN §9：全文 CMYK）"
        )


# ---------- 低階 PDF 組裝（物件表＋xref） ----------

class _PdfBuilder:
    def __init__(self, compress: bool = True):
        self.compress = compress
        self._bodies = [b""]  # 物件 1 起算，index 0 佔位

    def add(self, body) -> int:
        if isinstance(body, str):
            body = body.encode("latin-1")
        self._bodies.append(body)
        return len(self._bodies) - 1

    def reserve(self) -> int:
        return self.add(b"")

    def set(self, num: int, body) -> None:
        if isinstance(body, str):
            body = body.encode("latin-1")
        self._bodies[num] = body

    def stream(self, extra_dict: str, data: bytes, compress=None) -> int:
        if compress is None:
            compress = self.compress
        if compress:
            data = zlib.compress(data)
            extra_dict += " /Filter /FlateDecode"
        return self.add(
            f"<< /Length {len(data)}{extra_dict} >>\nstream\n".encode("latin-1")
            + data + b"\nendstream"
        )

    def build(self, root_num: int, info_num: int, version: str = "1.4") -> bytes:
        out = BytesIO()
        out.write(f"%PDF-{version}\n".encode("latin-1") + b"%\xe2\xe3\xcf\xd3\n")
        offsets = [0] * len(self._bodies)
        for i, body in enumerate(self._bodies[1:], 1):
            offsets[i] = out.tell()
            out.write(f"{i} 0 obj\n".encode("latin-1"))
            out.write(body)
            out.write(b"\nendobj\n")
        xref = out.tell()
        out.write(f"xref\n0 {len(self._bodies)}\n".encode("latin-1"))
        out.write(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
        fid = hashlib.md5(b"".join(self._bodies)).hexdigest().upper()
        out.write(
            f"trailer\n<< /Size {len(self._bodies)} /Root {root_num} 0 R "
            f"/Info {info_num} 0 R /ID [<{fid}> <{fid}>] >>\n"
            f"startxref\n{xref}\n%%EOF\n".encode("latin-1")
        )
        return out.getvalue()


# ---------- 內容流 ----------

class _Content:
    def __init__(self):
        self.prologue: list = []  # 圖形（path／影像）算符，置於文字塊（BT／ET）之前
        self.ops = ["q", _fill_op(DEFAULT_TEXT_CMYK), "BT"]
        self._cur = None
        self._fill = DEFAULT_TEXT_CMYK  # 現行文字填色（預設暖黑 K92）

    def set_fill(self, cmyk) -> None:
        """切換文字填色（Sprint 76 色票）：與現行相同不發算符（預設輸出形態不變）；
        `k` 為 DeviceCMYK 填色算符，於文字物件（BT 內）合法且不觸 preflight rg/RG。"""
        cmyk = tuple(cmyk)
        if cmyk != self._fill:
            self.ops.append(_fill_op(cmyk))
            self._fill = cmyk

    def stroke_rect(self, cmyk, line_width_pt: float,
                    x_ll: float, y_ll: float, w: float, h: float) -> None:
        """DeviceCMYK 描邊矩形（獨立 q…Q 狀態塊，狀態隔離；`K` 不觸 preflight rg/RG）。"""
        c, m, y, k = cmyk
        self.prologue += [
            "q",
            f"{_fmt(c)} {_fmt(m)} {_fmt(y)} {_fmt(k)} K",
            f"{_fmt(line_width_pt)} w",
            f"{x_ll:.3f} {y_ll:.3f} {_fmt(w)} {_fmt(h)} re",
            "S",
            "Q",
        ]

    def stroke_line(self, cmyk, line_width_pt: float,
                    x0: float, y0: float, x1: float, y1: float,
                    dash_on_pt: float = 0.0, dash_off_pt: float = 0.0) -> None:
        """DeviceCMYK 描邊線段（獨立 q…Q 狀態塊）。dash_on_pt>0 時掛 `d` dash 陣列，
        dash 狀態隨 Q 還原不外洩（spike8 實證）；`d`/`m`/`l` 不觸 preflight rg/RG。"""
        c, m, y, k = cmyk
        ops = [
            "q",
            f"{_fmt(c)} {_fmt(m)} {_fmt(y)} {_fmt(k)} K",
            f"{_fmt(line_width_pt)} w",
        ]
        if dash_on_pt > 0:
            ops.append(f"[ {_fmt(dash_on_pt)} {_fmt(dash_off_pt)} ] 0 d")
        ops += [
            f"{x0:.3f} {y0:.3f} m",
            f"{x1:.3f} {y1:.3f} l",
            "S",
            "Q",
        ]
        self.prologue += ops

    def draw_image(self, res_name: str, w: float, h: float,
                   x_ll: float, y_ll: float) -> None:
        """置入影像 XObject（獨立 q…Q，置文字塊 BT／ET 前）：cm 縮放單位方陣至 w×h、
        平移到左下角 (x_ll, y_ll)。影像首列在上（PIL tobytes 語意），cm h>0 使影像正立。"""
        self.prologue += [
            "q",
            f"{_fmt(w)} 0 0 {_fmt(h)} {x_ll:.3f} {y_ll:.3f} cm",
            f"/{res_name} Do",
            "Q",
        ]

    def show(self, res_name: str, code: int, x: float, y: float,
             size_pt: float, rotated: bool) -> None:
        key = (res_name, round(size_pt, 4))
        if key != self._cur:
            self.ops.append(f"/{res_name} {_fmt(size_pt)} Tf")
            self._cur = key
        tm = f"0 -1 1 0 {x:.3f} {y:.3f}" if rotated else f"1 0 0 1 {x:.3f} {y:.3f}"
        self.ops.append(f"{tm} Tm <{code:04X}> Tj")

    def finish(self) -> bytes:
        return "\n".join(self.prologue + self.ops + ["ET", "Q"]).encode("latin-1")


# ---------- 頁面寫出 ----------

class _PdfPageWriter:
    """把 LayoutPage 轉為內容流；幾何與 render.PageRenderer 同源（placement 層）。"""

    def __init__(self, template, master_name: str, font_dir=None):
        self.template = template
        self.master = template.masters[master_name]
        self.registry = FontRegistry(font_dir or DEFAULT_FONT_DIR)
        self._shapers: dict = {}
        self._fonts: dict = {}
        self._images: dict = {}  # 解析後路徑 → EmbeddedImage（跨頁去重）
        self.fonts_used: set = set()
        self.notdef_warnings: list = []
        self.bleed_pt = mm_to_pt(BLEED_MM)
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
                label = f"字元 {pl.ch!r}（U+{ord(pl.ch):04X}）" if pl.ch else "未知字元"
                msg = f"{label} 在 {Path(key[0]).name} 無字形，以 .notdef 輸出"
                if msg not in self.notdef_warnings:
                    self.notdef_warnings.append(msg)
            code = font.use(pl.gid, pl.ch)
            x = self.bleed_pt + pl.x_pt
            y = self.page_h_pt + self.bleed_pt - pl.y_pt  # top-down → y-up
            content.show(font.res_name, code, x, y, pl.size_pt, pl.rotated)

    def _footer(self, content: _Content, book_number: int, footer_texts: dict) -> None:
        master, template = self.master, self.template
        page_w = mm_to_pt(template.page_width_mm)
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
            key, shaper = self._shaper_for(style)
            width = run_width_pt(shaper, text, style.size_pt)
            if outer_right:  # 書口在右：文字右緣對齊 outer_offset
                pen_x = page_w - item.outer_offset_pt - width
            else:
                pen_x = item.outer_offset_pt
            content.set_fill(resolve_text_cmyk(template, style))
            self._emit(content, key, horizontal_placements(
                shaper, text, pen_x, item.baseline_from_top_pt, style.size_pt))

    def _vertical_body(self, content: _Content, page, book_number: int) -> None:
        master, template = self.master, self.template
        top_pt = mm_to_pt(master.margins.top_mm)
        for placed in page.placed:
            style = template.paragraph_styles[placed.style]
            key, shaper = self._shaper_for(style)
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
                    use_key, use_shaper = self._shaper_for(cstyle)
                    use_size = cstyle.size_pt
                else:
                    cstyle = None
                    use_key, use_shaper, use_size = key, shaper, style.size_pt
                if cell.kind == "cjk":
                    pls = ttb_char_placements(use_shaper, cell.text, axis, cell_top, use_size)
                elif cell.kind == "tcy":
                    pls = tcy_placements(use_shaper, cell.text, axis, cell_top, use_size, adv)
                elif cell.kind == "latin":
                    pls = rotated_latin_placements(use_shaper, cell.text, axis, cell_top, use_size)
                else:
                    pls = []
                content.set_fill(resolve_text_cmyk(template, cstyle, style))
                self._emit(content, use_key, pls)
                content_i += cell.width

    def _horizontal_body(self, content: _Content, page, book_number: int) -> None:
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
            pen_x = horizontal_left_x_pt(master, book_number) + placed.line.start_slot * char_adv
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

    def _frame(self, content: _Content, page, book_number: int) -> None:
        """主版向量框（v1 橫排 CIP 細框）：與 render._draw_frame 幾何同源，CMYK 描邊。"""
        n_lines = max(pl.slot for pl in page.placed) + 1
        rect = cip_frame_rect(
            self.master, horizontal_left_x_pt(self.master, book_number),
            n_lines, self.master.frame,
        )
        x_ll = self.bleed_pt + rect.x0
        y_ll = self.page_h_pt + self.bleed_pt - rect.y1  # top-down 下緣 → y-up 左下角
        content.stroke_rect(rect.cmyk, rect.line_width_pt, x_ll, y_ll,
                            rect.x1 - rect.x0, rect.y1 - rect.y0)

    def _rule(self, content: _Content, rule_breaks, book_number: int) -> None:
        """主版向量線（v1 目錄天頭水平虛線）：篇名嵌線處斷開，
        與 render._draw_rule 幾何同源（rule_break_ranges＋toc_rule_segments），CMYK 描邊。"""
        gaps = rule_break_ranges(self.template, self.master, rule_breaks, book_number)
        for line in toc_rule_segments(mm_to_pt(self.template.page_width_mm),
                                      self.master.rule, gaps):
            y_up = self.page_h_pt + self.bleed_pt - line.y0  # top-down → y-up（水平線 y0=y1）
            content.stroke_line(line.cmyk, line.line_width_pt,
                                self.bleed_pt + line.x0, y_up,
                                self.bleed_pt + line.x1, y_up,
                                line.dash_on_pt, line.dash_off_pt)

    def _figure(self, content: _Content, book_number: int) -> None:
        """主版圖框保留區佔位框（v1 G 圖文版照片區）：承版心四邊淡虛線，與
        render._draw_figure 幾何同源（figure_slot_rect＋edges），CMYK 描邊；
        top-down → y-up 逐端點加出血偏移。有置入圖時改由 _image 畫實際照片取代。"""
        page_w = mm_to_pt(self.template.page_width_mm)
        rect = figure_slot_rect(page_w, self.master, is_right_page(book_number),
                                self.master.figure)
        for edge in figure_slot_edges(rect, self.master.figure):
            content.stroke_line(
                edge.cmyk, edge.line_width_pt,
                self.bleed_pt + edge.x0, self.page_h_pt + self.bleed_pt - edge.y0,
                self.bleed_pt + edge.x1, self.page_h_pt + self.bleed_pt - edge.y1,
                edge.dash_on_pt, edge.dash_off_pt)

    def _image(self, content: _Content, entry, book_number: int) -> None:
        """置入圖：等比縮放置中（contain）DeviceGray 影像，與 render._draw_image
        幾何同源（fit_image_rect）；top-down 下緣 → y-up 左下角。
        entry＝(解析後路徑, PIL "L" 影像, rect|None)；rect＝任意圖框（trim pt、
        top-down，Sprint 54，可溢出版心入出血）、None＝主版 figure 保留區；
        同路徑跨頁共用單一 XObject。"""
        path, gray, rect = entry
        if path not in self._images:
            self._images[path] = EmbeddedImage(gray, f"Im{len(self._images) + 1}")
        emb = self._images[path]
        if rect is None:
            page_w = mm_to_pt(self.template.page_width_mm)
            slot = figure_slot_rect(page_w, self.master, is_right_page(book_number),
                                    self.master.figure)
            rect = (slot.x0, slot.y0, slot.x1, slot.y1)
        box = fit_image_rect(rect[0], rect[1], rect[2], rect[3], emb.width, emb.height)
        content.draw_image(
            emb.res_name, box.x1 - box.x0, box.y1 - box.y0,
            self.bleed_pt + box.x0, self.page_h_pt + self.bleed_pt - box.y1)

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

    def _toc_marks(self, content: _Content, marks, book_number: int) -> None:
        """目錄條目記號：行軸垂直引導線（實線）＋直排逐位頁碼（底錨），
        幾何取 layout.TocEntryMark，與 render._draw_toc_marks 同源。"""
        toc = self.master.toc
        for m in marks:
            axis = line_axis_x_pt(self.template, self.master, m.slot, book_number,
                                  line_slots=m.line_slots)
            if m.leader_y1_pt > m.leader_y0_pt:  # 重疊守護（violations 已列不沉默）
                content.stroke_line(
                    toc.leader_cmyk, toc.leader_width_pt,
                    self.bleed_pt + axis, self.page_h_pt + self.bleed_pt - m.leader_y0_pt,
                    self.bleed_pt + axis, self.page_h_pt + self.bleed_pt - m.leader_y1_pt,
                )
            cstyle = self.template.character_styles[m.char_style]
            key, shaper = self._shaper_for(cstyle)
            content.set_fill(resolve_text_cmyk(self.template, cstyle))
            for i, digit in enumerate(m.digits):
                cell_top = m.page_no_top_pt + i * m.digit_advance_pt
                self._emit(content, key, tcy_placements(
                    shaper, digit, axis, cell_top, m.digit_size_pt, m.digit_advance_pt))

    def build_page(self, page, footer_texts=None, book_number=None,
                   vertical: bool = True, toc_marks=(), rule_breaks=(),
                   images=(), frames=()) -> bytes:
        if getattr(page, "master", ""):  # 逐頁主版（節式主版指派，Sprint 51）
            self.master = self.template.masters[page.master]
        if book_number is None:  # 預設書頁號＝版面頁號（first_page=1）
            book_number = page.number
        content = _Content()
        # 主版向量框（v1 cip-box 為橫排原件，幾何依橫排網格盒；底層裝飾先 emit）
        if not vertical and self.master.frame and page.placed:
            self._frame(content, page, book_number)
        # 主版向量線（v1 toc-rule 為直排目錄原件，篇名嵌線處斷開；底層裝飾先 emit）
        if vertical and self.master.rule and page.placed:
            self._rule(content, rule_breaks, book_number)
        # 主版圖框保留區（photo-slot）：槽式圖取代佔位框；佔位框只看槽是否仍空
        # （rect 任意圖框不填槽，InDesign 空框導引語意，Sprint 54）
        slot_filled = any(rect is None for _p, _g, rect in images)
        if vertical and self.master.figure and page.placed and not slot_filled:
            self._figure(content, book_number)
        for entry in images:  # 文件序＝繪製序
            self._image(content, entry, book_number)
        if vertical:
            self._vertical_body(content, page, book_number)
        else:
            self._horizontal_body(content, page, book_number)
        if toc_marks:  # 目錄條目頁碼＋引導線（marks 僅目錄主版產生）
            self._toc_marks(content, toc_marks, book_number)
        for placement in frames:  # 獨立文字框（自由佈局層，body 之上）
            self._text_frame(content, placement)
        if footer_texts:
            self._footer(content, book_number, footer_texts)
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
    output_condition_identifier: str
    icc_embedded: bool
    justify_stats: dict
    images_placed: int = 0  # 嵌入的 DeviceGray 影像 XObject 數（同路徑去重；灰階單 K）


def export_pdf(doc, template, out_path, *, pages=None, footer: bool = True,
               first_page: int = 1, font_dir=None, compress: bool = True,
               output_condition_identifier: str = "JC200103",
               output_condition: str = "Japan Color 2001 Coated",
               icc_profile=None, image_base_dir=None) -> PdfResult:
    """文件＋模版 → PDF/X-1a:2001。pages=None 全頁；否則為版面頁號清單（1 起算）。

    output_condition_identifier 命中 KNOWN_PRINT_CONDITIONS（ICC registry 名）時
    免嵌描述檔；自訂識別必須以 icc_profile 提供 CMYK 輸出 ICC。
    置入圖（doc.images）以 DeviceGray XObject 嵌入，路徑相對 image_base_dir 解析。
    """
    if not doc.title:
        raise ValueError("PDF/X-1a 要求 Info /Title：文件 meta.title 不可為空")
    icc_bytes = None
    if icc_profile is not None:
        icc_bytes = Path(icc_profile).read_bytes()
        _validate_output_profile(icc_bytes, icc_profile)
    elif output_condition_identifier not in KNOWN_PRINT_CONDITIONS:
        raise ValueError(
            f"印刷條件識別 {output_condition_identifier!r} 不在已知 ICC registry 名單，"
            "X-1a 要求嵌入 DestOutputProfile：請以 icc_profile 提供 ICC 描述檔"
        )
    layout = layout_document(doc, template)
    writer = _PdfPageWriter(template, doc.master, font_dir=font_dir)
    masters_by_page = {p.number: template.masters[p.master] for p in layout.pages}
    images_by_page = resolve_placed_images(
        doc, masters_by_page, base_dir=image_base_dir)
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
        book_number = page.number + first_page - 1  # 書頁號（鏡像與頁腳奇偶依此）
        texts = None
        if footer and masters_by_page[page.number].footer:  # 頁腳依該頁主版 gate
            texts = {"number": str(book_number), "title": doc.title}
        contents.append(writer.build_page(
            page, footer_texts=texts, book_number=book_number,
            vertical=page.vertical,  # 逐頁方向（節式混向，Sprint 53）
            toc_marks=layout.toc_marks.get(page.number, ()),
            rule_breaks=layout.rule_breaks.get(page.number, ()),
            images=images_by_page.get(page.number, ()),
            frames=frames_by_page.get(page.number, ())))

    pdf = _PdfBuilder(compress=compress)
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
    media, trim = page_boxes_pt(template)
    box = lambda b: f"[{_fmt(b[0])} {_fmt(b[1])} {_fmt(b[2])} {_fmt(b[3])}]"  # noqa: E731
    pages_num = pdf.reserve()
    kids = []
    for content in contents:
        content_num = pdf.stream("", content)
        kids.append(pdf.add(
            f"<< /Type /Page /Parent {pages_num} 0 R /MediaBox {box(media)} "
            f"/TrimBox {box(trim)} /BleedBox {box(media)} "
            f"/Resources {resources_num} 0 R /Contents {content_num} 0 R >>"
        ))
    pdf.set(pages_num,
            f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>")
    # --- PDF/X-1a:2001 識別（§9 預設 X-1a；形態依 ISO 15930-1）---
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
                   PDFX_VERSION, PDFX_CONFORMANCE),
        compress=False,  # metadata stream 不壓縮，外部工具可直讀
    )
    catalog_num = pdf.add(
        f"<< /Type /Catalog /Pages {pages_num} 0 R "
        f"/Metadata {xmp_num} 0 R /OutputIntents [{oi_num} 0 R] "
        f"/ViewerPreferences << /Direction /R2L >> >>"
    )
    date = _pdf_date(now)
    info_num = pdf.add(
        f"<< /Title {_pdf_text_string(doc.title)} "
        f"/Producer (CJKFolio) /Creator (CJKFolio) "
        f"/CreationDate ({date}) /ModDate ({date}) /Trapped /False "
        f"/GTS_PDFXVersion ({PDFX_VERSION}) /GTS_PDFXConformance ({PDFX_CONFORMANCE}) >>"
    )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf.build(catalog_num, info_num, version="1.3"))
    return PdfResult(
        path=out,
        page_count=len(contents),
        violations=list(layout.violations) + frame_violations,
        fonts_used=sorted(writer.fonts_used),
        font_warnings=list(writer.registry.warnings) + list(writer.notdef_warnings),
        embedded_fonts=embedded,
        output_condition_identifier=output_condition_identifier,
        icc_embedded=icc_bytes is not None,
        justify_stats=dict(layout.justify_stats),
        images_placed=len(writer._images),
    )
