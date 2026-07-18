"""字型嵌入授權檢查（Sprint 84，§6 Phase 4「字型嵌入子集化與授權檢查」、GAPS #2）。

以 OpenType OS/2 `fsType` 嵌入權限位元為機器證據（A 級，讀實際字型位元組），於匯出
PDF 時檢查每款嵌入字型可否合法嵌入輪廓子集，不可嵌入或與子集政策衝突者列警告
（不沉默、不擋流程）。此為 PLAN §9「匯出時做授權檢查提示」的機器實作；名義授權
（華康／Monotype 商用）另見 §8 授權表，商用字型使用者須自負授權責任。

fsType 語意（OpenType 規格）：值 0＝Installable（無限制）；bit 1 Restricted License
（不得嵌入）；bit 2 Preview&Print、bit 3 Editable（皆可嵌入）；bit 8 No Subsetting
（不得子集化）；bit 9 Bitmap Only（僅點陣，禁輪廓）。
"""
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

_RESTRICTED = 0x0002    # Restricted License embedding：不得嵌入
_NO_SUBSET = 0x0100     # 不得子集化（本產品一律子集嵌入 → 政策衝突）
_BITMAP_ONLY = 0x0200   # 僅允許點陣嵌入（禁輪廓）


@dataclass(frozen=True)
class LicenseFinding:
    """單款字型的嵌入授權判定。"""
    font: str          # 字型檔名
    fs_type: int       # OS/2 fsType 原值
    embeddable: bool   # 可否合法嵌入輪廓子集（印前 PDF 用途）
    note: str          # 人讀說明（可嵌入原因，或不可嵌入／政策衝突理由）


def embedding_permission(font_path) -> LicenseFinding:
    """讀字型 OS/2 fsType，判定可否嵌入輪廓子集。無 OS/2 表視為 fsType=0。"""
    path = Path(font_path)
    font = TTFont(str(path), lazy=True)
    fs = int(getattr(font["OS/2"], "fsType", 0)) if "OS/2" in font else 0
    reasons = []
    embeddable = True
    if fs & _RESTRICTED:
        embeddable = False
        reasons.append("Restricted License embedding（fsType bit 1：不得嵌入）")
    if fs & _BITMAP_ONLY:
        embeddable = False
        reasons.append("僅允許點陣嵌入（fsType bit 9：禁輪廓）")
    if fs & _NO_SUBSET:
        reasons.append("不得子集化（fsType bit 8：本產品一律子集嵌入）")
    note = "；".join(reasons) if reasons else "可嵌入（fsType Installable/Preview-Print/Editable）"
    return LicenseFinding(font=path.name, fs_type=fs, embeddable=embeddable, note=note)


def license_warnings(font_paths) -> list:
    """彙整不可嵌入或與子集政策衝突字型的警告（可嵌入且無衝突者不列）。

    路徑去重後排序，逐款檢查；同 pdf_writer 字型警告慣例（不沉默、不擋流程）。
    """
    out = []
    for p in sorted({str(fp) for fp in font_paths}):
        f = embedding_permission(p)
        if not f.embeddable or (f.fs_type & _NO_SUBSET):
            out.append(f"字型授權：{f.font} {f.note}")
    return out
