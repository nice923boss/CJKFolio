"""PDF 字型子集嵌入（自 pdf_writer 抽出，Sprint 76 行數紀律分檔；行為不變）。

Sprint 8 決議形態：CFF（思源，CID-keyed）不保留 GID、內容流用原字型 charset 的
CID（探針實證思源 CID==GID，體積較 retain_gids 小 30 倍）；TTF（辰宇／粉圓）
retain_gids＋CIDToGIDMap /Identity。皆帶 ToUnicode 與 CIDSet（PDF/X-1a 對子集
CID 字型的要求）。emit 收 PDF 組裝器 duck-type（pdf.add／pdf.stream，同
images.EmbeddedImage 先例，無循環 import）。
"""
import hashlib
from io import BytesIO
from pathlib import Path

from fontTools import subset as ft_subset
from fontTools.ttLib import TTFont

from .fonts import FontError


def subset_tag(name: str, cids) -> str:
    """子集前綴（6 大寫字母）：由字型名＋碼位集決定，可重現。"""
    digest = hashlib.sha1(
        (name + ":" + ",".join(map(str, sorted(set(cids))))).encode("utf-8")
    ).digest()
    return "".join(chr(ord("A") + b % 26) for b in digest[:6])


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


class EmbeddedFont:
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

    def emit(self, pdf):
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
