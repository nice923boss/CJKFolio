"""PDF/X 形態宣告與中繼資料助手（自 pdf_writer 抽出；pdf_writer re-export 沿用）。

一致性形態（PdfxProfile／PDFX_PROFILES）、ICC registry 名單與輸出描述檔驗證住此，
XMP packet 與 Info dict 同值（Sprint 10 X-1a 識別形態定案）。
X-4:2010 以 pdfxid:GTS_PDFXVersion=PDF/X-4 識別且不用 GTS_PDFXConformance
（conformance=None 時省略該鍵，X-1a 帶 conformance 者位元不變）（Sprint 82）。
非 PDF/X 的一般 PDF（Sprint 137）以 version=None 表示，不寫任何 X 識別鍵。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PdfxProfile:
    """一種輸出形態（§9 送印：X-1a 預設、X-4 選項；另有非 PDF/X 的一般 PDF）。"""
    key: str                    # CLI 選值："x-1a" | "x-4" | "none"
    version: str | None         # Info／XMP GTS_PDFXVersion（None＝非 PDF/X，不寫）
    conformance: str | None     # Info／XMP GTS_PDFXConformance（X-4 無此鍵＝None）
    header: str                 # PDF header 版本（X-1a:2001＝1.3；X-4:2010＝1.6）
    require_embedded_icc: bool  # X-4 強制嵌 DestOutputProfile（registry 免嵌不足）
    allow_transparency: bool    # X-4 允許實時透明（X-1a 禁止）
    label: str                  # 人讀一致性標籤（CLI 與 PdfResult）

    @property
    def is_pdfx(self) -> bool:
        """是否為 PDF/X 一致性形態（version 是唯一判準，不另立可能矛盾的旗標）。

        False（一般 PDF）時：不寫 X 識別鍵、不寫 OutputIntent、影像可留 RGB。
        """
        return self.version is not None


PDFX_PROFILES = {
    "x-1a": PdfxProfile(
        "x-1a", "PDF/X-1:2001", "PDF/X-1a:2001", "1.3",
        require_embedded_icc=False, allow_transparency=False,
        label="PDF/X-1a:2001"),
    "x-4": PdfxProfile(
        "x-4", "PDF/X-4", None, "1.6",
        require_embedded_icc=True, allow_transparency=True,
        label="PDF/X-4"),
    # 非送印形態（Sprint 137）：全彩置入圖唯一能原樣落地的輸出。header 取 1.4
    # （PDF 1.3 無透明群組語彙，本產品雖不產生透明，仍不宜宣告比內容更舊的版本）。
    # 這不是「更寬鬆的 PDF/X」，是**不是 PDF/X**：拿去送印廠會被退件。
    "none": PdfxProfile(
        "none", None, None, "1.4",
        require_embedded_icc=False, allow_transparency=True,
        label="一般 PDF（非 PDF/X，可含 RGB）"),
}

PDFX_VERSION = PDFX_PROFILES["x-1a"].version       # Info /GTS_PDFXVersion（ISO 15930-1）
PDFX_CONFORMANCE = PDFX_PROFILES["x-1a"].conformance  # Info /GTS_PDFXConformance
REGISTRY_URL = "http://www.color.org"
# ICC 特性化資料登錄名（www.color.org/chardata）常用子集；命中者依 ISO 15930-1
# 可免嵌 DestOutputProfile。未列名（印廠自訂條件）須以 icc_profile 補描述檔。
KNOWN_PRINT_CONDITIONS = frozenset({
    "CGATS TR 001",
    "FOGRA27", "FOGRA39", "FOGRA51", "FOGRA52",
    "IFRA26",
    "JC200103", "JC200104", "JCN2002", "JCW2003",
})


def validate_output_profile(data: bytes, source) -> None:
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


def resolve_output_icc(profile: PdfxProfile, icc_profile,
                       output_condition_identifier: str) -> Optional[bytes]:
    """OutputIntent 要嵌的描述檔位元組；免嵌或不寫 OutputIntent 時回 None。

    三種形態的嵌入條款集中在此（自 pdf_writer.export_pdf 抽出，Sprint 139）：
    一般 PDF 無 OutputIntent，ICC 沒有地方放，收下卻不寫＝沉默丟棄，故快速失敗；
    X-1a 的識別命中 KNOWN_PRINT_CONDITIONS 者免嵌，自訂識別須補描述檔；
    X-4 一律強制嵌（ISO 15930-7，registry 免嵌不足）。
    回傳的位元組另有第二個用途（Sprint 139）：色彩轉換的目標描述檔即這一份，
    故「轉換目標」與「PDF 宣告的輸出條件」必然是同一個檔。
    """
    if not profile.is_pdfx:
        if icc_profile is not None:
            raise ValueError(
                f"{profile.label} 不寫 OutputIntent，icc_profile 無處可嵌："
                "要嵌輸出描述檔請選 PDF/X-1a 或 PDF/X-4")
        return None
    if icc_profile is not None:
        data = Path(icc_profile).read_bytes()
        validate_output_profile(data, icc_profile)
        return data
    if profile.require_embedded_icc:
        raise ValueError(
            f"{profile.label} 要求嵌入 DestOutputProfile（registry 識別不足）："
            "請以 icc_profile 提供 CMYK 輸出 ICC 描述檔")
    if output_condition_identifier not in KNOWN_PRINT_CONDITIONS:
        raise ValueError(
            f"印刷條件識別 {output_condition_identifier!r} 不在已知 ICC registry 名單，"
            f"{profile.label} 要求嵌入 DestOutputProfile：請以 icc_profile 提供 ICC 描述檔")
    return None


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def xmp_packet(title: str, date_iso: str, version: Optional[str],
               conformance: Optional[str]) -> bytes:
    """X 識別與文件中繼資料的最小 XMP（與 Info dict 同值）。

    conformance=None（X-4）時省略 GTS_PDFXConformance 兩鍵；
    帶 conformance（X-1a）時輸出與 Sprint 10 形態位元不變。
    version=None（一般 PDF，Sprint 137）時四個 GTS 鍵全省：不是 PDF/X 就不宣稱是。
    """
    t = _xml_escape(title)
    gts_lines = []
    if version is not None:
        gts_lines.append(f'<pdfx:GTS_PDFXVersion>{version}</pdfx:GTS_PDFXVersion>\n')
        if conformance is not None:
            gts_lines.append(
                f'<pdfx:GTS_PDFXConformance>{conformance}</pdfx:GTS_PDFXConformance>\n')
        gts_lines.append(
            f'<pdfxid:GTS_PDFXVersion>{version}</pdfxid:GTS_PDFXVersion>\n')
        if conformance is not None:
            gts_lines.append(
                f'<pdfxid:GTS_PDFXConformance>{conformance}</pdfxid:GTS_PDFXConformance>\n')
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
        + "".join(gts_lines)
        + '</rdf:Description>\n</rdf:RDF>\n</x:xmpmeta>\n'
        '<?xpacket end="w"?>'
    ).encode("utf-8")
