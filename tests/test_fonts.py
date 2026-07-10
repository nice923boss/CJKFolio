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
    f = reg.resolve("全字庫正楷體 TW-Kai", "regular")  # 家族未下載 → 思源宋體替
    assert f.path.exists()
    assert f.family_fallback
    assert any("全字庫正楷體" in w for w in reg.warnings)


@needs_fonts
def test_warnings_deduplicated():
    reg = FontRegistry(FONT_DIR)
    reg.resolve("全字庫正楷體 TW-Kai", "regular")
    reg.resolve("全字庫正楷體 TW-Kai", "regular")
    assert len(reg.warnings) == 1


@pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSansTC-Bold.otf").exists(),
    reason="assets/fonts 無思源黑體（依 FONTS.md 指令重現下載）",
)
def test_resolve_sans_medium_bold_exact():
    reg = FontRegistry(FONT_DIR)
    assert reg.resolve("思源黑體 TC", "medium").path.name == "SourceHanSansTC-Medium.otf"
    assert reg.resolve("思源黑體 TC", "bold").path.name == "SourceHanSansTC-Bold.otf"
    assert reg.warnings == []


@pytest.mark.skipif(
    not (FONT_DIR / "jf-openhuninn-2.1.ttf").exists(),
    reason="assets/fonts 無粉圓／辰宇（依 FONTS.md 指令重現下載）",
)
def test_resolve_handwriting_families_exact():
    reg = FontRegistry(FONT_DIR)
    assert reg.resolve("辰宇落雁體", "regular").path.name == "ChenYuluoyan-2.0-Thin.ttf"
    assert reg.resolve("jf open 粉圓", "regular").path.name == "jf-openhuninn-2.1.ttf"
    assert reg.warnings == []
