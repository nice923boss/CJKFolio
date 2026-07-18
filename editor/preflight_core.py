"""preflight 判定層與快取鍵（Sprint 100，Qt 無關故可在背景執行緒與 pytest 中跑）。

從 PreflightActionsMixin 抽出的兩件事：

- run_preflight_checks：匯出臨時 PDF/X-1a → 三項機械檢查（判定邏輯仍全在
  cjkfolio.preflight，本層只負責「匯出一份、三支檢查器各跑一次」的順序）。
  抽出的理由是 GUI 執行緒不得阻塞：同一組呼叫要能在 worker 執行緒裡跑。
- preflight_cache_key：文件內容、模版、置入圖檔位元組任一改動即換鍵。
  快取的正確性全繫於此，漏算一項就會把舊報告當成當前輸出的結論。

字型檔案本身不入鍵（見 GAPS #47 (f)）：會話中途在磁碟換掉字型檔屬邊界情形，
v1 以「重啟編輯器」處理，不為此每次算鍵掃描字型目錄。
"""
import hashlib
import json
import tempfile
from pathlib import Path
from typing import NamedTuple

from cjkfolio.document import Document, document_to_dict
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.preflight import (
    ImageResolutionReport,
    InkCoverageReport,
    PreflightReport,
    check_image_resolution,
    check_ink_coverage,
    check_pdfx,
)
from cjkfolio.styles import Template, template_to_dict


class PreflightResults(NamedTuple):
    """三份機械檢查報告（PDF/X 合規；影像解析度與油墨總量為 §9 印廠條件）。

    profile＝送檢的 PDF/X 形態鍵（"x-1a" 或 "x-4"），供呈現層標示是哪一套規則集。
    """
    report: PreflightReport
    image_report: ImageResolutionReport
    ink_report: InkCoverageReport
    profile: str = "x-1a"


def run_preflight_checks(doc: Document, template: Template, image_base_dir, *,
                         pdfx: str = "x-1a", icc_profile=None) -> PreflightResults:
    """匯出臨時 PDF/X → 三項機械檢查，回三份報告。

    pdfx="x-4" 須以 icc_profile 提供 CMYK 輸出 ICC（X-4 強制嵌 DestOutputProfile，
    registry 名不足）；未給時 export_pdf 快速失敗，不在此降級成 X-1a。
    匯出或檢查失敗時照樣拋出（呼叫端負責提示，不在此吞掉）。
    """
    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "preflight.pdf"
        export_pdf(doc, template, pdf_path, image_base_dir=image_base_dir,
                   pdfx=pdfx, icc_profile=icc_profile)
        path = str(pdf_path)
        return PreflightResults(
            check_pdfx(path, profile=pdfx),
            check_image_resolution(path),
            check_ink_coverage(path),
            pdfx,
        )


def _file_fingerprint(path) -> list:
    """檔案指紋：路徑、大小、修改時間（缺檔記 missing，算鍵不失敗）。"""
    full = Path(path)
    try:
        st = full.stat()
    except OSError:
        return [str(full), "missing"]
    return [str(full), st.st_size, st.st_mtime_ns]


def _image_fingerprint(image_base_dir, rel_path: str) -> list:
    """置入圖的指紋（相對路徑亦入鍵：同內容不同來源仍屬不同輸出）。"""
    return [rel_path] + _file_fingerprint(Path(image_base_dir) / rel_path)[1:]


def preflight_cache_key(doc: Document, template: Template, image_base_dir, *,
                        pdfx: str = "x-1a", icc_profile=None) -> str:
    """當前輸出的指紋：文件、模版、基準目錄、置入圖檔、PDF/X 形態與輸出 ICC。

    同鍵代表匯出的 PDF 會逐位元組相同，故可沿用上次的報告。形態與 ICC 入鍵，
    X-1a 的快取才不會被 X-4 誤命中（兩者規則集不同，結論不可互代）。
    """
    payload = {
        "document": document_to_dict(doc),
        "template": template_to_dict(template),
        "image_base_dir": str(Path(image_base_dir)),
        "images": [_image_fingerprint(image_base_dir, img.path) for img in doc.images],
        "pdfx": pdfx,
        "icc": _file_fingerprint(icc_profile) if icc_profile else None,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
