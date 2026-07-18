"""字型嵌入授權檢查測試（Sprint 84，Phase 4；§6「字型嵌入子集化與授權檢查」、
GAPS #2）。

以 OS/2 fsType 嵌入權限位元為機器證據（A 級）：Restricted License（bit 1）與僅點陣
（bit 9）判不可嵌入輪廓；不得子集化（bit 8）與本產品一律子集政策衝突。內建可散布
字型（思源／辰宇／粉圓）fsType=0 應零警告。受限字型 fixture 以 fontTools 改 fsType
再存（不散布任何商用字型，紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.font_license import (
    LicenseFinding,
    embedding_permission,
    license_warnings,
)

fontTools = pytest.importorskip("fontTools")
from fontTools.ttLib import TTFont  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "fonts"
OPEN_TTF = FONT_DIR / "jf-openhuninn-2.1.ttf"

needs_fonts = pytest.mark.skipif(
    not OPEN_TTF.exists(),
    reason="assets/fonts 無可散布字型（依 FONTS.md 指令重現下載）")


def _font_with_fstype(src: Path, fs_type: int, dst: Path) -> Path:
    font = TTFont(str(src))
    font["OS/2"].fsType = fs_type
    font.save(str(dst))
    return dst


# ---------- embedding_permission 純函式 ----------

@needs_fonts
def test_open_font_embeddable():
    f = embedding_permission(OPEN_TTF)
    assert isinstance(f, LicenseFinding)
    assert f.fs_type == 0
    assert f.embeddable is True
    assert "可嵌入" in f.note


@needs_fonts
def test_restricted_font_not_embeddable(tmp_path):
    p = _font_with_fstype(OPEN_TTF, 0x0002, tmp_path / "restricted.ttf")
    f = embedding_permission(p)
    assert f.fs_type == 0x0002
    assert f.embeddable is False
    assert "Restricted" in f.note


@needs_fonts
def test_bitmap_only_font_not_embeddable(tmp_path):
    p = _font_with_fstype(OPEN_TTF, 0x0200, tmp_path / "bitmap.ttf")
    f = embedding_permission(p)
    assert f.embeddable is False
    assert "點陣" in f.note


@needs_fonts
def test_no_subset_font_flags_policy_conflict(tmp_path):
    p = _font_with_fstype(OPEN_TTF, 0x0100, tmp_path / "nosubset.ttf")
    f = embedding_permission(p)
    # 可嵌入輪廓，但與本產品一律子集政策衝突
    assert f.embeddable is True
    assert "子集" in f.note


# ---------- license_warnings 彙整 ----------

@needs_fonts
def test_open_fonts_zero_warnings():
    assert license_warnings([OPEN_TTF]) == []


@needs_fonts
def test_warnings_list_restricted(tmp_path):
    r = _font_with_fstype(OPEN_TTF, 0x0002, tmp_path / "r.ttf")
    warns = license_warnings([OPEN_TTF, r])
    assert len(warns) == 1
    assert "r.ttf" in warns[0] and "Restricted" in warns[0]


@needs_fonts
def test_warnings_dedup_and_sorted(tmp_path):
    r = _font_with_fstype(OPEN_TTF, 0x0002, tmp_path / "r.ttf")
    # 重複路徑只計一次
    assert len(license_warnings([r, r, str(r)])) == 1


# ---------- 匯出整合（內建字型零警告） ----------

@needs_fonts
def test_export_pdf_reports_license_warnings(tmp_path):
    import fitz  # noqa: F401  確保 PyMuPDF 在（export 不需，但保持整合軌一致）
    from cjkfolio.document import document_from_dict
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.styles import load_template

    template = load_template(ROOT / "templates" / "neizai-zhengli.json")
    doc = document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "授權檢查樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": "整理與安放", "style": "內文-明體直排"}],
    })
    result = export_pdf(doc, template, tmp_path / "lic.pdf", footer=False)
    # 內建字型皆 fsType=0（可散布）→ 零授權警告
    assert list(result.license_warnings) == []
    assert result.fonts_used  # 確有嵌入字型被檢查
