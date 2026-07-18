"""PDF/X-1a 機械 preflight（Phase 1 收尾片，GAPS #15 的本機驗證）。

定位：以 PyMuPDF 獨立解析（與 pdf_writer 不同實作，Gate 4），對 X-1a:2001
的機械可驗項逐條檢查。veraPDF 僅驗 PDF/A 與 PDF/UA、不支援 PDF/X
（2026-07-11 官方文件實查），故本機 preflight＝本檢查器＋pdffonts；
Acrobat／印廠認證級驗證不在此範圍，未涵蓋項誠實列於 NOT_COVERED。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz

from .images import MIN_IMAGE_PPI, effective_ppi, meets_ppi
from .pdf_writer import KNOWN_PRINT_CONDITIONS, PDFX_PROFILES

RULE_IDS = (
    "header-version",       # %PDF-1.3（X-1a:2001 基於 PDF 1.3）
    "trailer-id",           # trailer /ID 兩組字串
    "no-encrypt",           # 禁加密
    "info-identification",  # Title／CreationDate／ModDate／Trapped／GTS 兩鍵
    "output-intent",        # 恰一個 GTS_PDFX；registry 識別或嵌 CMYK prtr ICC
    "page-boxes",           # 每頁 TrimBox（無 ArtBox），盒框巢狀
    "fonts-embedded",       # 全嵌入、無 Type3
    "color-cmyk-only",      # 無 DeviceRGB／CalRGB／CalGray／Lab／ICCBased、無 rg/RG
    "no-lzw",               # 禁 LZWDecode
    "no-transparency",      # 無 SMask（/None 除外）／Transparency 群組
    "no-interactive",       # 無 Annots／AcroForm／JavaScript／OpenAction／AA
    "xmp-metadata",         # XMP 存在且含 X 識別（:2001 為建議項，CJKFolio 管線必寫）
)

NOT_COVERED = (
    "疊印與 ExtGState 細節",
    "影像解析度 PPI（非 ISO 15930-1 條款故不入本規則集，另由 check_image_resolution "
    "依 §9 300ppi 下限檢查；置入嵌原生解析度、不重採樣；"
    "影像色彩空間由 color-cmyk-only 涵蓋，DeviceGray 合法、DeviceRGB 判失敗）",
    "油墨總量 TAC",
    "字型授權嵌入旗標",
    "視覺內容正確性（人工抽檢）",
    "Acrobat／印廠認證級 preflight",
)


@dataclass(frozen=True)
class Finding:
    rule: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    path: Path
    findings: tuple
    not_covered: tuple = field(default=NOT_COVERED)

    @property
    def ok(self) -> bool:
        return all(f.ok for f in self.findings)


def _obj(doc, xref: int) -> str:
    try:
        return doc.xref_object(xref, compressed=True) or ""
    except Exception:
        return ""


def _parse_pdf_string(tok: str) -> str:
    if tok.startswith("("):
        body = tok[1:-1]
        return body.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
    data = bytes.fromhex(tok[1:-1].strip())
    if data[:2] == b"\xfe\xff":
        return data[2:].decode("utf-16-be", "replace")
    return data.decode("latin-1", "replace")


def _brief(problems, limit: int = 6) -> str:
    extra = f"；等共 {len(problems)} 項" if len(problems) > limit else ""
    return "；".join(problems[:limit]) + extra


def _contains(outer, inner, eps: float = 0.02) -> bool:
    return (outer.x0 - eps <= inner.x0 and outer.y0 - eps <= inner.y0
            and inner.x1 <= outer.x1 + eps and inner.y1 <= outer.y1 + eps)


def _check_output_intent(doc, catalog: str, require_icc: bool = False):
    blob = None
    m = re.search(r"/OutputIntents\s*\[(.*?)\]", catalog, re.S)
    if m:
        blob = m.group(1)
    else:
        m = re.search(r"/OutputIntents\s+(\d+)\s+0\s+R", catalog)
        if m:
            blob = _obj(doc, int(m.group(1)))
    candidates = []
    if blob:
        refs = re.findall(r"(\d+)\s+0\s+R", blob)
        candidates = [_obj(doc, int(r)) for r in refs] if refs else (
            [blob] if "/S" in blob else [])
    x_ois = [c for c in candidates if re.search(r"/S\s*/GTS_PDFX(?![A-Za-z])", c)]
    if len(x_ois) != 1:
        return False, f"GTS_PDFX OutputIntent 數量 {len(x_ois)}（PDF/X 須恰為 1）"

    oi, problems = x_ois[0], []
    ident_m = re.search(r"/OutputConditionIdentifier\s*(\([^)]*\)|<[0-9A-Fa-f\s]+>)", oi)
    ident = _parse_pdf_string(ident_m.group(1)) if ident_m else ""
    if not ident:
        problems.append("缺 /OutputConditionIdentifier")
    dest = re.search(r"/DestOutputProfile\s+(\d+)\s+0\s+R", oi)
    if not dest:
        if require_icc:  # X-4：registry 免嵌不足，須嵌 DestOutputProfile
            problems.append("X-4 須嵌 DestOutputProfile（registry 識別不足）")
        elif ident not in KNOWN_PRINT_CONDITIONS:
            problems.append(f"識別 {ident!r} 非已知 registry 條目且未嵌 DestOutputProfile")
    if dest:
        icc_x = int(dest.group(1))
        try:
            icc = doc.xref_stream(icc_x) or b""
        except Exception:
            icc = b""
        if len(icc) < 132 or icc[12:16] != b"prtr" or icc[16:20] != b"CMYK":
            problems.append("DestOutputProfile 非 CMYK 輸出裝置（prtr）ICC")
        if not re.search(r"/N\s*4(?![0-9])", _obj(doc, icc_x)):
            problems.append("DestOutputProfile /N 非 4")
    if problems:
        return False, "；".join(problems)
    return True, f"OutputIntent {ident}" + ("（嵌 ICC）" if dest else "（registry 識別，免嵌）")


def check_pdfx(path, profile: str = "x-1a") -> PreflightReport:
    """對單一 PDF 跑指定 PDF/X 形態的機械規則，回傳逐條 PASS／FAIL 報告。

    profile="x-1a"（預設）或 "x-4"。X-4 header 為 1.6、GTS_PDFXVersion=PDF/X-4
    且無 GTS_PDFXConformance、OutputIntent 須嵌 DestOutputProfile、且允許透明
    （故不列 no-transparency 規則）。
    """
    if profile not in PDFX_PROFILES:
        raise ValueError(
            f"未知 preflight profile {profile!r}，可選 {sorted(PDFX_PROFILES)}")
    prof = PDFX_PROFILES[profile]
    path = Path(path)
    findings = []

    def add(rule: str, ok, detail: str) -> None:
        findings.append(Finding(rule, bool(ok), detail))

    header_bytes = f"%PDF-{prof.header}".encode("latin-1")
    with path.open("rb") as f:
        head = f.read(9)
    add("header-version", head.startswith(header_bytes),
        f"header {head[:8].decode('latin-1', 'replace')}"
        f"（{prof.label} 須 %PDF-{prof.header}）")

    doc = fitz.open(str(path))
    try:
        objs = [(x, _obj(doc, x)) for x in range(1, doc.xref_length())]
        trailer = _obj(doc, -1)
        catalog = _obj(doc, doc.pdf_catalog())

        # /ID 兩組非空字串；PyMuPDF 讀回時，解碼後全可列印的字串會被重序列化為
        # (literal) 而非 <hex>，故兩式皆須接受（空 <> 或 () 仍判失敗）。
        _idstr = r"(?:<[0-9A-Fa-f]+>|\((?:[^()\\]|\\.)+\))"
        add("trailer-id",
            re.search(rf"/ID\s*\[\s*{_idstr}\s*{_idstr}\s*\]", trailer),
            "trailer /ID 兩組字串" if "/ID" in trailer else "trailer 無 /ID")

        add("no-encrypt", not doc.is_encrypted and "/Encrypt" not in trailer,
            "未加密" if not doc.is_encrypted else "檔案加密（X-1a 禁止）")

        m = re.search(r"/Info\s+(\d+)\s+0\s+R", trailer)
        info = _obj(doc, int(m.group(1))) if m else ""
        problems = []
        for key, pat in (("/Title", r"/Title\s*[<(]"),
                         ("/CreationDate", r"/CreationDate\s*[<(]"),
                         ("/ModDate", r"/ModDate\s*[<(]")):
            if not re.search(pat, info):
                problems.append(f"缺 {key}")
        if not re.search(r"/Trapped\s*/(True|False)(?![A-Za-z])", info):
            problems.append("缺 /Trapped（須 /True 或 /False）")
        if not re.search(r"/GTS_PDFXVersion\s*\(" + re.escape(prof.version) + r"\)", info):
            problems.append(f"GTS_PDFXVersion 非 ({prof.version})")
        if prof.conformance is not None:
            if not re.search(
                    r"/GTS_PDFXConformance\s*\(" + re.escape(prof.conformance) + r"\)", info):
                problems.append(f"GTS_PDFXConformance 非 ({prof.conformance})")
        elif re.search(r"/GTS_PDFXConformance", info):
            problems.append("X-4 不得帶 GTS_PDFXConformance")
        add("info-identification", not problems,
            "Info 識別齊備" if not problems else "；".join(problems))

        add("output-intent",
            *_check_output_intent(doc, catalog, require_icc=prof.require_embedded_icc))

        problems = []
        for page in doc:
            raw, label = _obj(doc, page.xref), f"頁 {page.number + 1}"
            if "/TrimBox" not in raw:
                problems.append(f"{label} 無 TrimBox")
                continue
            if "/ArtBox" in raw:
                problems.append(f"{label} TrimBox 與 ArtBox 並存（X-1a 擇一）")
            if not _contains(page.mediabox, page.trimbox):
                problems.append(f"{label} TrimBox 超出 MediaBox")
            if "/BleedBox" in raw and not _contains(page.bleedbox, page.trimbox):
                problems.append(f"{label} TrimBox 超出 BleedBox")
        add("page-boxes", not problems,
            f"{doc.page_count} 頁 TrimBox 齊備且巢狀正確" if not problems else _brief(problems))

        problems, seen = [], set()
        for page in doc:
            for f_ in page.get_fonts(full=True):
                xref, ftype, basefont = f_[0], f_[2], f_[3]
                if xref in seen:
                    continue
                seen.add(xref)
                if ftype == "Type3":
                    problems.append(f"{basefont or '(未名)'} 為 Type3（X-1a 禁止）")
                    continue
                try:
                    buf = doc.extract_font(xref)[3]
                except Exception:
                    buf = b""
                if not buf:
                    problems.append(f"{basefont} 未嵌入")
        add("fonts-embedded", not problems,
            (f"{len(seen)} 款字型皆嵌入" if seen else "無字型資源")
            if not problems else _brief(problems))

        problems = []
        cs_pat = re.compile(r"/(DeviceRGB|CalRGB|CalGray|Lab|ICCBased)(?![A-Za-z0-9])")
        for x, s in objs:
            hit = cs_pat.search(s)
            if hit:
                problems.append(f"obj {x} 含 /{hit.group(1)}")
        op_pat = re.compile(rb"(?:^|[\s\]>])(rg|RG)(?:$|[\s/%])")
        for page in doc:
            data = b""
            for cx in page.get_contents():
                try:
                    data += (doc.xref_stream(cx) or b"") + b"\n"
                except Exception:
                    problems.append(f"頁 {page.number + 1} 內容流無法解碼")
            if op_pat.search(data):
                problems.append(f"頁 {page.number + 1} 內容流含 rg/RG（DeviceRGB 著色）")
        add("color-cmyk-only", not problems,
            "無 RGB／裝置無關色彩" if not problems else _brief(problems))

        lzw = [x for x, s in objs if "/LZWDecode" in s]
        add("no-lzw", not lzw,
            "無 LZWDecode" if not lzw else f"obj {lzw[:6]} 用 LZWDecode（X-1a 禁止）")

        if not prof.allow_transparency:  # X-4 允許實時透明，不列此規則
            tr_pat = re.compile(r"/(SMask|Transparency)(?![A-Za-z0-9])")
            trans = [x for x, s in objs if tr_pat.search(re.sub(r"/SMask\s*/None", "", s))]
            add("no-transparency", not trans,
                "無透明" if not trans else f"obj {trans[:6]} 含 SMask／Transparency")

        ia_pat = re.compile(r"/(Annots|AcroForm|JavaScript|OpenAction|AA)(?![A-Za-z0-9+])")
        inter = [x for x, s in objs if ia_pat.search(s)]
        add("no-interactive", not inter,
            "無註解與互動項" if not inter else f"obj {inter[:6]} 含註解／表單／動作")

        has_meta = re.search(r"/Metadata\s+(\d+)\s+0\s+R", catalog)
        xmp = doc.get_xml_metadata() if has_meta else ""
        if not has_meta:
            xmp_detail = "無 XMP metadata（:2001 為建議項，CJKFolio 管線必寫）"
        elif "GTS_PDFXVersion" not in xmp:
            xmp_detail = "XMP 存在但無 GTS_PDFXVersion 識別"
        else:
            xmp_detail = "XMP 存在且含 X 識別"
        add("xmp-metadata", has_meta and "GTS_PDFXVersion" in xmp, xmp_detail)
    finally:
        doc.close()
    return PreflightReport(path=path, findings=tuple(findings))


def check_pdfx1a(path) -> PreflightReport:
    """X-1a:2001 機械 preflight（check_pdfx 的相容包裝，既有呼叫端維持不變）。"""
    return check_pdfx(path, profile="x-1a")


def preflight_summary(report: PreflightReport) -> str:
    """一行結論摘要（CLI 與 editor 面板共用）：「全數通過（N/M）」或「未通過（N/M）」。"""
    passed = sum(1 for f in report.findings if f.ok)
    verdict = "全數通過" if report.ok else "未通過"
    return f"{verdict}（{passed}/{len(report.findings)}）"


# ---------- 影像解析度（§9 印廠條件，非 X-1a 標準條款故獨立規則集） ----------

@dataclass(frozen=True)
class ImageFinding:
    """PDF 內單次影像置入的解析度判定（自 PDF 反算，不看產出側中間值）。"""
    page: int          # PDF 頁碼（1 起算）
    xref: int          # 影像 XObject 物件號
    px_w: int
    px_h: int
    draw_w_pt: float
    draw_h_pt: float
    ppi: float
    ok: bool


@dataclass(frozen=True)
class ImageResolutionReport:
    path: Path
    min_ppi: float
    findings: tuple

    @property
    def ok(self) -> bool:
        return all(f.ok for f in self.findings)


def check_image_resolution(path, min_ppi: float = MIN_IMAGE_PPI) -> ImageResolutionReport:
    """以 PyMuPDF 獨立解析 PDF，逐次影像置入反算實效 PPI（Gate 4）。

    PPI 不屬 ISO 15930-1（X-1a）條款，故不入 check_pdfx 規則集：低解析度不使
    PDF 失去 X-1a 合規性，只是印刷品質風險（§9 連續調 300〜350ppi）。同一影像
    XObject 置入多次則各記一筆（各自繪製尺寸不同）。

    v1 只驗連續調下限：§9「點陣線稿 1200ppi」需知該圖為線稿（內容語意，機器不可判），
    不在此檢查（誠實記錄於 GAPS）。
    """
    p = Path(path)
    findings = []
    doc = fitz.open(p)
    try:
        for page in doc:
            for info in page.get_image_info(xrefs=True):
                bbox = fitz.Rect(info["bbox"])
                px_w, px_h = int(info["width"]), int(info["height"])
                ppi = min(effective_ppi(px_w, bbox.width),
                          effective_ppi(px_h, bbox.height))
                findings.append(ImageFinding(
                    page=page.number + 1, xref=int(info.get("xref", 0)),
                    px_w=px_w, px_h=px_h,
                    draw_w_pt=bbox.width, draw_h_pt=bbox.height,
                    ppi=ppi, ok=meets_ppi(ppi, min_ppi)))
    finally:
        doc.close()
    return ImageResolutionReport(path=p, min_ppi=min_ppi, findings=tuple(findings))


def image_resolution_summary(report: ImageResolutionReport) -> str:
    """一行結論摘要（CLI 與後續面板共用，同 preflight_summary 慣例）。"""
    if not report.findings:
        return "無置入影像"
    low = [f for f in report.findings if not f.ok]
    if not low:
        return (f"全數達標（{len(report.findings)}/{len(report.findings)} "
                f"≥ {report.min_ppi:.0f}ppi）")
    worst = min(f.ppi for f in low)
    return (f"解析度不足 {len(low)}/{len(report.findings)} 張"
            f"（最低 {worst:.0f}ppi < {report.min_ppi:.0f}ppi）")
