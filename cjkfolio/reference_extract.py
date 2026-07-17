"""從參考 PDF 萃取起始樣式（PLAN §4.3「從參考萃取」，§1 分析流程的產品化）。

分析 (font, size) 分布與用色，提出起始段落樣式清單草稿供使用者命名與調整。
分工鐵律（§4.4）：只提案字型對映與級數；行距、版心等版面幾何一律由引擎
與主版確定性計算，不從掃描推測。字型對映依 §8 可散布字型組（source_font
記原字型；未識別家族暫映思源宋體 TC 並於 note 警告不沉默，Sprint 6 慣例）。
版權紅線：參考 PDF 僅本機分析；草稿只含字型名／級數／字數統計（量測參數），
不含 PDF 內文句。
"""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import fitz

_SONG = "思源宋體 TC"
_HEI = "思源黑體 TC"

FAMILY_SHORT = {
    _SONG: "宋",
    _HEI: "黑",
    "全字庫正宋體": "仿宋",
    "全字庫正楷體 TW-Kai": "楷",
    "辰宇落雁體": "手寫",
}

# 家族可用字重（模版詞彙），對映後就近收斂
_FAMILY_WEIGHTS = {
    _SONG: ("regular", "bold", "heavy"),
    _HEI: ("medium", "bold"),
}


def _weight_token(lower: str) -> str:
    if any(t in lower for t in ("heavy", "black", "w8", "w9")):
        return "heavy"
    if any(t in lower for t in ("bold", "w6", "w7")):
        return "bold"
    if any(t in lower for t in ("medium", "w5")):
        return "medium"
    return "regular"


def _clamp_weight(family: str, weight: str) -> str:
    allowed = _FAMILY_WEIGHTS.get(family)
    if allowed is None:
        return "regular"
    if weight in allowed:
        return weight
    if family == _SONG:
        return "regular" if weight == "medium" else "heavy"
    return "bold" if weight == "heavy" else "medium"  # 黑：無 heavy／regular


def map_font(source_font: str):
    """原字型名 → (可散布家族, 字重, 未識別警告)。仿宋先於宋判（名含 song）。"""
    lower = source_font.lower()
    weight = _weight_token(lower)
    if "fangsong" in lower or "仿宋" in source_font:
        return "全字庫正宋體", "regular", False
    if "kai" in lower or "楷" in source_font:
        return "全字庫正楷體 TW-Kai", "regular", False
    if any(t in lower for t in ("pen", "luoyan", "chenyu")) or "辰宇" in source_font:
        return "辰宇落雁體", "regular", False
    if any(t in lower for t in ("hei", "sans", "gothic")) or "黑" in source_font:
        return _HEI, _clamp_weight(_HEI, weight), False
    if any(t in lower for t in ("ming", "sung", "song", "serif", "times", "caslon")) \
            or "明" in source_font or "宋" in source_font:
        return _SONG, _clamp_weight(_SONG, weight), False
    return _SONG, _clamp_weight(_SONG, weight), True


def propose_styles(stats, *, min_chars: int = 60, max_styles: int = 20):
    """(font, size) 統計 → (段落樣式草稿 dict, 濾除清單)；濾除不沉默。

    角色門檻：主力字數＝內文候選；級數 ≥1.1 倍＝標題候選、≤0.85 倍＝小字候選、
    其餘＝同級候選（語意命名屬使用者，§4.3「供使用者命名與調整」）。
    """
    rows = sorted(stats, key=lambda r: -r["chars"])
    kept, skipped = [], []
    for r in rows:
        if r["chars"] < min_chars:
            skipped.append({**r, "reason": f"低於門檻 {min_chars} 字"})
        elif len(kept) >= max_styles:
            skipped.append({**r, "reason": f"超出樣式上限 {max_styles}"})
        else:
            kept.append(r)
    styles: dict = {}
    if not kept:
        return styles, skipped
    body_size = kept[0]["size"]
    for i, r in enumerate(kept):
        family, weight, warn = map_font(r["font"])
        ratio = r["size"] / body_size
        if i == 0:
            role = "內文候選"
        elif ratio >= 1.1:
            role = "標題候選"
        elif ratio <= 0.85:
            role = "小字候選"
        else:
            role = "同級候選"
        base = f"{role}-{FAMILY_SHORT[family]}{r['size']:g}pt"
        name, n = base, 1
        while name in styles:
            n += 1
            name = f"{base}-{n}"
        note = f"自動萃取：{r['chars']:,} 字、{r['pages']} 頁"
        if warn:
            note += "；來源字型未識別，暫映思源宋體 TC，請人工調整"
        styles[name] = {
            "font_family": family,
            "font_weight": weight,
            "size_pt": float(r["size"]),
            "source_font": f"{r['font']} {r['size']:g}pt",
            "note": note,
        }
    return styles, skipped


@dataclass(frozen=True)
class ScanResult:
    page_count: int
    stats: tuple      # ({font, size, chars, pages}, ...) 依字數降冪
    colors: tuple     # ({hex, chars}, ...) 依字數降冪


def scan_pdf(pdf_path) -> ScanResult:
    """PyMuPDF 掃描 (font, size) 分布與用色；只聚合統計，不留文句。"""
    agg: dict = defaultdict(lambda: {"chars": 0, "pages": set()})
    color_chars: dict = defaultdict(int)
    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        for pno in range(page_count):
            for block in doc[pno].get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        n = len(span["text"].strip())
                        if not n:
                            continue
                        entry = agg[(span["font"], round(span["size"], 1))]
                        entry["chars"] += n
                        entry["pages"].add(pno)
                        color_chars[span.get("color", 0)] += n
    stats = tuple(sorted(
        ({"font": f, "size": s, "chars": v["chars"], "pages": len(v["pages"])}
         for (f, s), v in agg.items()),
        key=lambda r: -r["chars"],
    ))
    colors = tuple(sorted(
        ({"hex": f"#{c:06x}", "chars": n} for c, n in color_chars.items()),
        key=lambda r: -r["chars"],
    ))
    return ScanResult(page_count=page_count, stats=stats, colors=colors)


def extract_draft(pdf_path, min_chars: int = 60, max_styles: int = 20) -> dict:
    """掃描＋提案 → 草稿 dict（paragraph_styles 片段與模版欄位同形，可逐條新增）。"""
    result = scan_pdf(pdf_path)
    styles, skipped = propose_styles(
        result.stats, min_chars=min_chars, max_styles=max_styles)
    return {
        "source_pdf": str(pdf_path),
        "pages": result.page_count,
        "paragraph_styles": styles,
        "colors": list(result.colors[:8]),
        "skipped": [
            {"font": r["font"], "size": r["size"], "chars": r["chars"],
             "reason": r["reason"]} for r in skipped
        ],
    }
