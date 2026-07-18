"""低階 PDF 組裝：物件表、串流壓縮、xref 與 trailer（自 pdf_writer 抽出）。

抽出動機（Sprint 93）：pdf_writer 逾單檔 800 行上限，取本層為切點：它不認識版面、
字型或色彩，只把「物件編號→位元組」序列化為合法 PDF 檔案結構，與其上的排版寫出層
無雙向依賴。純機械搬移，行為零變更（既有 PDF 位元組輸出不變）。
"""
import hashlib
import zlib
from io import BytesIO


class PdfBuilder:
    """PDF 物件表：add／reserve／set 累積物件，build 序列化為完整檔案位元組。"""

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
