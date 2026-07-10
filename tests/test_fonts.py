"""字型解析（cjkfolio.fonts）：家族／字重對映與 fallback 警告。"""
from pathlib import Path

import pytest

from cjkfolio.fonts import FontRegistry

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


@needs_fonts
def test_resolve_serif_regular_exact():
    reg = FontRegistry(FONT_DIR)
    f = reg.resolve("思源宋體 TC", "regular")
    assert f.path.name == "SourceHanSerifTC-Regular.otf"
    assert not f.family_fallback and not f.weight_fallback
    assert reg.warnings == []


@needs_fonts
def test_resolve_serif_heavy_exact():
    reg = FontRegistry(FONT_DIR)
    f = reg.resolve("思源宋體 TC", "heavy")
    assert f.path.name == "SourceHanSerifTC-Heavy.otf"
    assert not f.family_fallback and not f.weight_fallback


@needs_fonts
def test_resolve_missing_weight_falls_back_with_warning():
    reg = FontRegistry(FONT_DIR)
    f = reg.resolve("思源宋體 TC", "bold")  # 無 Bold 檔 → Heavy 替
    assert f.path.name == "SourceHanSerifTC-Heavy.otf"
    assert f.weight_fallback and not f.family_fallback
    assert any("bold" in w for w in reg.warnings)


@needs_fonts
def test_resolve_missing_family_falls_back_with_warning():
    reg = FontRegistry(FONT_DIR)
    f = reg.resolve("思源黑體 TC", "medium")  # 家族未下載 → 思源宋體替
    assert f.path.exists()
    assert f.family_fallback
    assert any("思源黑體" in w for w in reg.warnings)


@needs_fonts
def test_warnings_deduplicated():
    reg = FontRegistry(FONT_DIR)
    reg.resolve("思源黑體 TC", "medium")
    reg.resolve("思源黑體 TC", "medium")
    assert len(reg.warnings) == 1
