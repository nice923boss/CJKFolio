"""PDF 寫出層第一片（PLAN Phase 1，向 PDF/X-1a DoD 推進）。

範圍（Sprint 8 決議）：
- 盒框依 PLAN §9：MediaBox 154×216mm、TrimBox 148×210mm 置中、BleedBox＝MediaBox。
- 文字一律 DeviceCMYK 單 K92（§9 內文 K90〜92 區間，v1 定 0.92）。
- 字型子集嵌入：CFF（思源，CID-keyed）不保留 GID、內容流用原 CID 走 charset
  對映（InDesign 同款形態）；TTF（辰宇／粉圓）retain_gids＋CIDToGIDMap /Identity。
  皆帶 ToUnicode 與 CIDSet（PDF/X-1a 對子集 CID 字型的要求）。
- 幾何與 PNG 渲染同源（placement 層），逐字顯式 Tm 定位；禁則與斷行已在
  排版層完成並烘焙（§9：PDF/X 只忠實嵌入已排好的結果）。
- PDF/X-1a 剩餘（OutputIntent／XMP 識別／preflight 全綠）列 GAPS，後續 Sprint。
"""
import hashlib
import zlib
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from fontTools import subset as ft_subset
from fontTools.ttLib import TTFont

from .fonts import DEFAULT_FONT_DIR, FontError, FontRegistry
from .layout import layout_document, style_advance_pt, style_line_slots
from .placement import (
    horizontal_placements,
    rotated_latin_placements,
    run_width_pt,
    tcy_placements,
    ttb_char_placements,
)
from .render import Shaper, line_axis_x_pt, mm_to_pt

BLEED_MM = 3.0
TEXT_K = 0.92  # 內文單 K92（§10 決議：§9 K90〜92 區間取 92）


def page_boxes_pt(template, bleed_mm: float = BLEED_MM):
    """(MediaBox, TrimBox)，皆 pt；BleedBox＝MediaBox（§9）。"""
    w, h = mm_to_pt(template.page_width_mm), mm_to_pt(template.page_height_mm)
    b = mm_to_pt(bleed_mm)
    return (0.0, 0.0, w + 2 * b, h + 2 * b), (b, b, b + w, b + h)


def subset_tag(name: str, cids) -> str:
    """子集前綴（6 大寫字母）：由字型名＋碼位集決定，可重現。"""
    digest = hashlib.sha1(
        (name + ":" + ",".join(map(str, sorted(set(cids))))).encode("utf-8")
    ).digest()
    return "".join(chr(ord("A") + b % 26) for b in digest[:6])


def _fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _pdf_text_string(s: str) -> str:
    return "<FEFF" + s.encode("utf-16-be").hex().upper() + ">"


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

    def stream(self, extra_dict: str, data: bytes) -> int:
        if self.compress:
            data = zlib.compress(data)
            extra_dict += " /Filter /FlateDecode"
        return self.add(
            f"<< /Length {len(data)}{extra_dict} >>\nstream\n".encode("latin-1")
            + data + b"\nendstream"
        )

    def build(self, root_num: int, info_num: int) -> bytes:
        out = BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
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


# ---------- 字型子集嵌入 ----------

def _to_unicode_stream(code_chars: dict) -> bytes:
    pairs = "\n".join(
        f"<{code:04X}> <{''.join(f'{ord(c):04X}' for c in ch)}>"
        for code, ch in sorted(code_chars.items()) if ch
    )
    n = sum(1 for ch in code_chars.values() if ch)
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        f"{n} beginbfchar\n{pairs}\nendbfchar\n"
        "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode("latin-1")


def _cidset_bytes(cids) -> bytes:
    top = max(cids)
    buf = bytearray(top // 8 + 1)
    for cid in cids:
        buf[cid // 8] |= 0x80 >> (cid % 8)
    return bytes(buf)


class _EmbeddedFont:
    """單一字型檔的使用收集與 PDF 字型物件組產出。

    code（內容流 2 byte 碼）＝CID：CFF 取原字型 charset 的 cidNNNNN（思源
    CID==GID，Sprint 8 探針實證）；TTF 取 GID（retain_gids 子集後不變）。
    """

    def __init__(self, path: Path, res_name: str):
        self.path = Path(path)
        self.res_name = res_name
        self._font = TTFont(str(self.path), lazy=True)
        self.is_cff = "CFF " in self._font
        self._order = self._font.getGlyphOrder()
        if self.is_cff and not hasattr(self._font["CFF "].cff[0], "ROS"):
            raise FontError(f"{self.path.name} 非 CID-keyed CFF，v1 寫出層不支援")
        self._gid_code: dict = {}
        self._used_gids: set = set()
        self.code_chars: dict = {}

    def _code_for(self, gid: int) -> int:
        if gid == 0:
            return 0  # .notdef 的 CID 依定義為 0
        if gid not in self._gid_code:
            if self.is_cff:
                name = self._order[gid]
                if not name.startswith("cid"):
                    raise FontError(
                        f"{self.path.name} glyph {gid} 名稱 {name!r} 非 cidNNNNN，無法取 CID"
                    )
                self._gid_code[gid] = int(name[3:])
            else:
                self._gid_code[gid] = gid
        return self._gid_code[gid]

    def use(self, gid: int, ch: str) -> int:
        code = self._code_for(gid)
        self._used_gids.add(gid)
        if ch and not self.code_chars.get(code):
            self.code_chars[code] = ch
        return code

    def _subset_data(self) -> bytes:
        font = TTFont(str(self.path))
        opts = ft_subset.Options()
        opts.retain_gids = not self.is_cff
        opts.notdef_outline = True
        opts.drop_tables += ["GSUB", "GPOS", "GDEF", "BASE", "JSTF", "MATH"]
        subsetter = ft_subset.Subsetter(opts)
        subsetter.populate(gids=sorted(self._used_gids | {0}))
        subsetter.subset(font)
        if self.is_cff:
            return font["CFF "].compile(font)
        buf = BytesIO()
        font.save(buf)
        return buf.getvalue()

    def emit(self, pdf: _PdfBuilder):
        """產出 Type0 字型物件組，回傳（物件號, 統計 dict）。"""
        font = self._font
        upem = font["head"].unitsPerEm
        scale = 1000.0 / upem
        ps_name = font["name"].getDebugName(6) or self.path.stem
        hmtx = font["hmtx"]
        widths = {
            self._code_for(g): round(hmtx[self._order[g]][0] * scale)
            for g in sorted(self._used_gids)
        }
        head = font["head"]
        bbox = [round(v * scale) for v in (head.xMin, head.yMin, head.xMax, head.yMax)]
        hhea = font["hhea"]
        ascent, descent = round(hhea.ascent * scale), round(hhea.descent * scale)
        cap_height = 700
        if "OS/2" in font and getattr(font["OS/2"], "sCapHeight", 0):
            cap_height = round(font["OS/2"].sCapHeight * scale)

        data = self._subset_data()
        tag = subset_tag(ps_name, widths)
        base = f"{tag}+{ps_name}"
        if self.is_cff:
            file_num = pdf.stream(" /Subtype /CIDFontType0C", data)
            file_key, subtype, cid_extra = "FontFile3", "CIDFontType0", ""
        else:
            file_num = pdf.stream(f" /Length1 {len(data)}", data)
            file_key, subtype, cid_extra = "FontFile2", "CIDFontType2", " /CIDToGIDMap /Identity"
        cidset_num = pdf.stream("", _cidset_bytes(set(widths) | {0}))
        desc_num = pdf.add(
            f"<< /Type /FontDescriptor /FontName /{base} /Flags 4 "
            f"/FontBBox [{bbox[0]} {bbox[1]} {bbox[2]} {bbox[3]}] /ItalicAngle 0 "
            f"/Ascent {ascent} /Descent {descent} /CapHeight {cap_height} /StemV 80 "
            f"/CIDSet {cidset_num} 0 R /{file_key} {file_num} 0 R >>"
        )
        w_arr = " ".join(f"{c} [{w}]" for c, w in sorted(widths.items()))
        cid_num = pdf.add(
            f"<< /Type /Font /Subtype /{subtype} /BaseFont /{base} "
            f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
            f"/FontDescriptor {desc_num} 0 R /DW 1000 /W [{w_arr}]{cid_extra} >>"
        )
        tounicode_num = pdf.stream("", _to_unicode_stream(self.code_chars))
        type0_num = pdf.add(
            f"<< /Type /Font /Subtype /Type0 /BaseFont /{base} /Encoding /Identity-H "
            f"/DescendantFonts [{cid_num} 0 R] /ToUnicode {tounicode_num} 0 R >>"
        )
        stats = {
            "base": base,
            "file": self.path.name,
            "glyphs": len(self._used_gids),
            "bytes": len(data),
        }
        return type0_num, stats


# ---------- 內容流 ----------

class _Content:
    def __init__(self):
        self.ops = ["q", f"0 0 0 {_fmt(TEXT_K)} k", "BT"]
        self._cur = None

    def show(self, res_name: str, code: int, x: float, y: float,
             size_pt: float, rotated: bool) -> None:
        key = (res_name, round(size_pt, 4))
        if key != self._cur:
            self.ops.append(f"/{res_name} {_fmt(size_pt)} Tf")
            self._cur = key
        tm = f"0 -1 1 0 {x:.3f} {y:.3f}" if rotated else f"1 0 0 1 {x:.3f} {y:.3f}"
        self.ops.append(f"{tm} Tm <{code:04X}> Tj")

    def finish(self) -> bytes:
        return "\n".join(self.ops + ["ET", "Q"]).encode("latin-1")


# ---------- 頁面寫出 ----------

class _PdfPageWriter:
    """把 LayoutPage 轉為內容流；幾何與 render.PageRenderer 同源（placement 層）。"""

    def __init__(self, template, master_name: str, font_dir=None):
        self.template = template
        self.master = template.masters[master_name]
        self.registry = FontRegistry(font_dir or DEFAULT_FONT_DIR)
        self._shapers: dict = {}
        self._fonts: dict = {}
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

    def _font_for(self, key) -> _EmbeddedFont:
        if key not in self._fonts:
            self._fonts[key] = _EmbeddedFont(Path(key[0]), f"F{len(self._fonts) + 1}")
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

    def _footer(self, content: _Content, page, footer_texts: dict) -> None:
        master, template = self.master, self.template
        page_w = mm_to_pt(template.page_width_mm)
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
            key, shaper = self._shaper_for(style)
            width = run_width_pt(shaper, text, style.size_pt)
            if odd:  # 書口在右：文字右緣對齊 outer_offset
                pen_x = page_w - item.outer_offset_pt - width
            else:
                pen_x = item.outer_offset_pt
            self._emit(content, key, horizontal_placements(
                shaper, text, pen_x, item.baseline_from_top_pt, style.size_pt))

    def build_page(self, page, footer_texts=None) -> bytes:
        master, template = self.master, self.template
        content = _Content()
        top_pt = mm_to_pt(master.margins.top_mm)
        for placed in page.placed:
            style = template.paragraph_styles[placed.style]
            if style.writing_mode != "vertical-rl":
                raise ValueError(
                    f"樣式「{style.name}」writing_mode={style.writing_mode}，"
                    "Phase 1 寫出層僅支援 vertical-rl（橫排於後續 Sprint）"
                )
            key, shaper = self._shaper_for(style)
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
                    use_key, use_shaper = self._shaper_for(cstyle)
                    use_size = cstyle.size_pt
                else:
                    use_key, use_shaper, use_size = key, shaper, style.size_pt
                if cell.kind == "cjk":
                    pls = ttb_char_placements(use_shaper, cell.text, axis, cell_top, use_size)
                elif cell.kind == "tcy":
                    pls = tcy_placements(use_shaper, cell.text, axis, cell_top, use_size, advance)
                elif cell.kind == "latin":
                    pls = rotated_latin_placements(use_shaper, cell.text, axis, cell_top, use_size)
                else:
                    pls = []
                self._emit(content, use_key, pls)
                slot_i += cell.width
        if footer_texts:
            self._footer(content, page, footer_texts)
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


def export_pdf(doc, template, out_path, *, pages=None, footer: bool = True,
               first_page: int = 1, font_dir=None, compress: bool = True) -> PdfResult:
    """文件＋模版 → PDF。pages=None 全頁；否則為版面頁號清單（1 起算）。"""
    layout = layout_document(doc, template)
    writer = _PdfPageWriter(template, doc.master, font_dir=font_dir)
    selected = list(layout.pages)
    if pages is not None:
        wanted = set(pages)
        missing = wanted - {p.number for p in selected}
        if missing:
            raise ValueError(f"文件排版共 {len(selected)} 頁，無第 {sorted(missing)} 頁")
        selected = [p for p in selected if p.number in wanted]
    contents = []
    for page in selected:
        texts = None
        if footer and writer.master.footer:
            texts = {"number": str(page.number + first_page - 1), "title": doc.title}
        contents.append(writer.build_page(page, footer_texts=texts))

    pdf = _PdfBuilder(compress=compress)
    embedded = []
    font_refs = []
    for key in sorted(writer._fonts, key=lambda k: int(writer._fonts[k].res_name[1:])):
        emb = writer._fonts[key]
        num, stats = emb.emit(pdf)
        font_refs.append(f"/{emb.res_name} {num} 0 R")
        embedded.append(stats)
    resources_num = pdf.add(f"<< /Font << {' '.join(font_refs)} >> >>")
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
    catalog_num = pdf.add(
        f"<< /Type /Catalog /Pages {pages_num} 0 R "
        f"/ViewerPreferences << /Direction /R2L >> >>"
    )
    info_parts = [f"/Producer (CJKFolio)", f"/Creator (CJKFolio)"]
    if doc.title:
        info_parts.insert(0, f"/Title {_pdf_text_string(doc.title)}")
    info_parts.append(f"/CreationDate (D:{datetime.now().strftime('%Y%m%d%H%M%S')})")
    info_num = pdf.add(f"<< {' '.join(info_parts)} >>")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf.build(catalog_num, info_num))
    return PdfResult(
        path=out,
        page_count=len(contents),
        violations=list(layout.violations),
        fonts_used=sorted(writer.fonts_used),
        font_warnings=list(writer.registry.warnings) + list(writer.notdef_warnings),
        embedded_fonts=embedded,
    )
