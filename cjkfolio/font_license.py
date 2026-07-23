"""字型嵌入授權檢查（Sprint 84，§6 Phase 4「字型嵌入子集化與授權檢查」、GAPS #2）。

以 OpenType OS/2 `fsType` 嵌入權限位元為機器證據（A 級，讀實際字型位元組），於匯出
PDF 時檢查每款嵌入字型可否合法嵌入輪廓子集，不可嵌入或與子集政策衝突者列警告
（不沉默、不擋流程）。此為 PLAN §9「匯出時做授權檢查提示」的機器實作；名義授權
（華康／Monotype 商用）另見 §8 授權表，商用字型使用者須自負授權責任。

fsType 語意（OpenType 規格）：值 0＝Installable（無限制）；bit 1 Restricted License
（不得嵌入）；bit 2 Preview&Print、bit 3 Editable（皆可嵌入）；bit 8 No Subsetting
（不得子集化）；bit 9 Bitmap Only（僅點陣，禁輪廓）。

Sprint 112 補第二層「名義授權」（GAPS #43 (a)(b)）：fsType 只答機器允不允許嵌入，
答不了授權允不允許散布（實測 kaiu.ttf 標楷體、mingliu.ttc、arial.ttf、Gill Sans MT
的 fsType 皆為 0x0008 Editable，第一層零警告，但四款都是商用字型）。本模組改讀
name table ID 13（License Description）與 ID 14（License Info URL），即字型檔自己
宣告的授權，屬 A 級機器證據；不比對字型名稱（名稱可改、可缺、可撞名）。
"""
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

_RESTRICTED = 0x0002    # Restricted License embedding：不得嵌入
_NO_SUBSET = 0x0100     # 不得子集化（本產品一律子集嵌入 → 政策衝突）
_BITMAP_ONLY = 0x0200   # 僅允許點陣嵌入（禁輪廓）

_LICENSE_DESC = 13      # name ID 13：License Description（授權條款全文或摘要）
_LICENSE_URL = 14       # name ID 14：License Info URL
_MAX_DECLARATION = 200  # 宣告全文可達數千字（OFL 全文），列示一律截斷

# 已知「可自由嵌入並隨成品散布」的授權標記（比對 ID 13＋ID 14 全文，小寫）。
# 只列授權文本明確允許嵌入散布、且本專案實際遇得到的授權；未列入者一律歸
# declared（須自行確認），不臆測放行。GPL 系需搭字型例外條款才涵蓋成品散布，
# 條件判定超出機器可讀範圍，故不列入（見 GAPS 本 Sprint v1 限制）。
_FREE_LICENSES = (
    ("SIL Open Font License", ("sil open font license", "scripts.sil.org/ofl",
                               "openfontlicense", "opensource.org/licenses/ofl")),
    ("Apache License 2.0", ("apache license, version 2.0",
                            "apache.org/licenses/license-2.0")),
    ("MIT License", ("mit license", "opensource.org/licenses/mit")),
    ("Ubuntu Font Licence", ("ubuntu font licence", "font.ubuntu.com/ufl")),
    ("公眾領域／CC0", ("public domain", "creativecommons.org/publicdomain")),
)

LICENSE_POLICIES = ("warn", "block")  # 匯出授權政策：警告不擋／有警告即不產出


class LicenseBlocked(ValueError):
    """license_policy="block" 攔下匯出（字型授權未通過，未產出任何檔案）。"""


@dataclass(frozen=True)
class LicenseFinding:
    """單款字型的嵌入授權判定。"""
    font: str          # 字型檔名
    fs_type: int       # OS/2 fsType 原值
    embeddable: bool   # 可否合法嵌入輪廓子集（印前 PDF 用途）
    note: str          # 人讀說明（可嵌入原因，或不可嵌入／政策衝突理由）


@dataclass(frozen=True)
class RedistributionFinding:
    """單款字型的名義授權判定（依字型自報的 name ID 13／14）。"""
    font: str           # 字型檔名
    klass: str          # free（表列自由授權）／declared（有宣告待確認）／undeclared（無宣告）
    license_name: str   # 命中的自由授權名稱（未命中為空字串）
    declaration: str    # ID 13 宣告文字（已正規化空白並截斷）
    url: str            # ID 14 授權說明網址
    vendor: str         # 字型自報來源（manufacturer／copyright／achVendID）
    note: str           # 人讀說明


def _open_font(path: Path) -> TTFont:
    """開字型；.ttc 取第 0 款（Windows 系統字型多為 collection，量測工具會遇到）。"""
    return TTFont(str(path), lazy=True, fontNumber=0)


def _clean(text) -> str:
    """正規化空白並截斷（宣告全文可達數千字，直接輸出會淹沒警告行）。"""
    if not text:
        return ""
    out = " ".join(str(text).split())
    return out if len(out) <= _MAX_DECLARATION else out[:_MAX_DECLARATION - 1] + "…"


def embedding_permission(font_path) -> LicenseFinding:
    """讀字型 OS/2 fsType，判定可否嵌入輪廓子集。無 OS/2 表視為 fsType=0。"""
    path = Path(font_path)
    font = _open_font(path)
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


def redistribution_declaration(font_path) -> RedistributionFinding:
    """讀字型 name ID 13／14，判定名義授權可否直接嵌入散布。

    三類：free（宣告命中 _FREE_LICENSES）／declared（有宣告但未命中，須自行確認）
    ／undeclared（兩欄皆缺，無從據字型自身判定）。只讀字型自報內容，不比對檔名或
    字型名稱，故改名不改分類。
    """
    path = Path(font_path)
    font = _open_font(path)
    name = font["name"] if "name" in font else None
    desc = _clean(name.getDebugName(_LICENSE_DESC) if name else "")
    url = _clean(name.getDebugName(_LICENSE_URL) if name else "")
    vendor = _vendor(name, font["OS/2"] if "OS/2" in font else None)
    haystack = f"{desc}\n{url}".lower()
    for license_name, markers in _FREE_LICENSES:
        if any(m in haystack for m in markers):
            return RedistributionFinding(
                font=path.name, klass="free", license_name=license_name,
                declaration=desc, url=url, vendor=vendor,
                note=f"字型宣告為 {license_name}，可隨成品嵌入散布")
    if not desc and not url:
        return RedistributionFinding(
            font=path.name, klass="undeclared", license_name="", declaration="",
            url="", vendor=vendor,
            note="字型未宣告授權（name ID 13／14 皆無），可否散布須查授權來源")
    return RedistributionFinding(
        font=path.name, klass="declared", license_name="", declaration=desc, url=url,
        vendor=vendor,
        note=f"字型自報授權「{desc or url}」非表列自由授權，散布前須自行確認")


def _vendor(name, os2) -> str:
    """取字型自報來源：manufacturer → copyright → designer → achVendID。"""
    for nid in (8, 0, 9):
        value = _clean(name.getDebugName(nid) if name else "")
        if value:
            return value
    vend = str(getattr(os2, "achVendID", "") or "").strip() if os2 else ""
    return vend or "（未標示）"


def license_warnings(font_paths) -> list:
    """彙整字型授權警告：機器層（fsType）與名義層（name ID 13／14）各自成列。

    路徑去重後排序，逐款檢查；同 pdf_writer 字型警告慣例（不沉默、預設不擋流程，
    要擋改走 license_policy="block"）。
    """
    out = []
    for p in sorted({str(fp) for fp in font_paths}):
        f = embedding_permission(p)
        if not f.embeddable or (f.fs_type & _NO_SUBSET):
            out.append(f"字型授權：{f.font} {f.note}")
        r = redistribution_declaration(p)
        if r.klass != "free":
            out.append(f"名義授權：{r.font} {r.note}（來源：{r.vendor}）")
    return out


def license_rows(font_paths) -> list:
    """字型授權表列（狀態, 字型, 明細），供 preflight 面板與量測工具共用。"""
    rows = []
    for p in sorted({str(fp) for fp in font_paths}):
        f = embedding_permission(p)
        r = redistribution_declaration(p)
        if not f.embeddable:
            status, detail = "不可嵌入", f.note
        elif f.fs_type & _NO_SUBSET:
            status, detail = "不可子集", f.note
        else:
            status = {"free": "可散布", "declared": "須確認"}.get(r.klass, "無宣告")
            detail = f"{r.note}（來源：{r.vendor}；fsType 0x{f.fs_type:04X}）"
        rows.append((status, f.font, detail))
    return rows


def enforce_license_policy(policy: str, font_paths) -> tuple:
    """依授權政策檢查字型並回傳警告；policy="block" 時有警告即中止（不產出檔案）。"""
    if policy not in LICENSE_POLICIES:
        raise ValueError(
            f"未知 license_policy {policy!r}，可選 {sorted(LICENSE_POLICIES)}")
    warnings = tuple(license_warnings(font_paths))
    if policy == "block" and warnings:
        raise LicenseBlocked(
            "license_policy=block：以下字型未通過授權檢查，已中止匯出（未產出檔案）\n"
            + "\n".join(warnings))
    return warnings
