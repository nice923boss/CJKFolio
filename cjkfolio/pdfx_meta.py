"""PDF/X 中繼資料助手（自 pdf_writer 抽出，Sprint 55 行數上限管理；行為不變）。

XMP packet 與 Info dict 同值（Sprint 10 X-1a 識別形態定案）。
"""


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def xmp_packet(title: str, date_iso: str, version: str, conformance: str) -> bytes:
    """X-1a 識別與文件中繼資料的最小 XMP（與 Info dict 同值）。"""
    t = _xml_escape(title)
    return (
        f'<?xpacket begin="{chr(0xFEFF)}" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '<rdf:Description rdf:about=""\n'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
        ' xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n'
        ' xmlns:pdf="http://ns.adobe.com/pdf/1.3/"\n'
        ' xmlns:pdfx="http://ns.adobe.com/pdfx/1.3/"\n'
        ' xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/">\n'
        f'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{t}</rdf:li></rdf:Alt></dc:title>\n'
        f'<xmp:CreateDate>{date_iso}</xmp:CreateDate>\n'
        f'<xmp:ModifyDate>{date_iso}</xmp:ModifyDate>\n'
        '<xmp:CreatorTool>CJKFolio</xmp:CreatorTool>\n'
        '<pdf:Producer>CJKFolio</pdf:Producer>\n'
        '<pdf:Trapped>False</pdf:Trapped>\n'
        f'<pdfx:GTS_PDFXVersion>{version}</pdfx:GTS_PDFXVersion>\n'
        f'<pdfx:GTS_PDFXConformance>{conformance}</pdfx:GTS_PDFXConformance>\n'
        f'<pdfxid:GTS_PDFXVersion>{version}</pdfxid:GTS_PDFXVersion>\n'
        f'<pdfxid:GTS_PDFXConformance>{conformance}</pdfxid:GTS_PDFXConformance>\n'
        '</rdf:Description>\n</rdf:RDF>\n</x:xmpmeta>\n'
        '<?xpacket end="w"?>'
    ).encode("utf-8")
