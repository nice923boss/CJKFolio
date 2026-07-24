"""畫布預覽畫質（Sprint 133）：縮放感知的底圖解析度分級。

Owner 真視窗回饋：「預覽的畫面字體不夠清晰，改成預覽是非常清楚的字體與圖片
內容才對。」根因由 Spike 24 量測釐清＝底圖固定 150dpi，放大即像素拉伸
（對照圖 out/compare-150x3-vs-450.png 目視差異明顯），非字型或塑形問題。

形態：scene 座標系維持 150dpi 空間不變（互動層字格幾何零改動），底圖改以
較高 dpi 渲染後 setScale 縮回。本檔測 Qt 無關的分級純函式；執行緒調度與
畫面實際更換走 smoke C36。

另含 Sprint 132 漏網的第六處書頁號落點（頁面縮圖）的回歸測試。
"""
import pytest

from editor.canvas_quality import (
    BASE_DPI_LEVELS,
    CANVAS_DPI,
    target_base_dpi,
)


def test_一倍縮放取基準dpi():
    """100%＝底圖像素與 scene 1:1，維持既有 150dpi（零額外成本）。"""
    assert target_base_dpi(1.0) == CANVAS_DPI == 150


def test_縮小時不降到基準以下():
    """縮小只是把同一張底圖畫小，重渲染低 dpi 無畫質收益且徒增一次渲染。"""
    assert target_base_dpi(0.5) == 150
    assert target_base_dpi(0.1) == 150


def test_放大時取足夠的級數():
    """需求 dpi＝150×倍率；取 ≥ 需求的最小級數，使螢幕像素不靠拉伸補。"""
    assert target_base_dpi(1.5) == 225
    assert target_base_dpi(2.0) == 300
    assert target_base_dpi(3.0) == 450
    # 級數之間取上一級（不足即模糊，寧可多渲染）
    assert target_base_dpi(1.1) == 225
    assert target_base_dpi(2.1) == 450


def test_超過最高級時夾住():
    """Spike 24：600dpi 單頁 66MB，對頁 132MB 與長書匯入同量級，故上限 450。"""
    assert target_base_dpi(8.0) == 450
    assert target_base_dpi(100.0) == max(BASE_DPI_LEVELS) == 450


def test_高解析螢幕的裝置像素比乘入需求():
    """HiDPI（Windows 125%／150% 縮放）下 1 邏輯像素＝1.25／1.5 實體像素，
    不乘入即在高解析螢幕上仍然模糊。"""
    assert target_base_dpi(1.0, dpr=1.5) == 225
    assert target_base_dpi(1.0, dpr=2.0) == 300
    assert target_base_dpi(2.0, dpr=2.0) == 450  # 600 需求夾到 450


def test_級數為遞增且含基準():
    """分級而非連續：連續 dpi 會使每次滾輪微調都觸發整頁重渲染。"""
    assert list(BASE_DPI_LEVELS) == sorted(BASE_DPI_LEVELS)
    assert BASE_DPI_LEVELS[0] == CANVAS_DPI


def test_倍率非正數時取基準():
    """視窗尚未 layout 完成時 zoom 可能為 0；不可讓它算出 0 或負 dpi。"""
    assert target_base_dpi(0.0) == 150
    assert target_base_dpi(-1.0) == 150


# ---- Sprint 132 漏網：頁面縮圖的書頁號（Gate 3 第六處落點） ----

def test_縮圖頁腳依書頁號且封面不編頁碼():
    """縮圖執行緒原直接用版面頁號當書頁號（隱含無封面）：帶封面時整份縮圖的
    頁碼會比實際大 1，且封面縮圖會印出頁碼。"""
    from editor.page_panel import thumbnail_footer

    # 無封面（既有行為）：版面頁號＝書頁號
    assert thumbnail_footer(1, cover_pages=0, title="書")["number"] == "1"
    assert thumbnail_footer(3, cover_pages=0, title="書")["number"] == "3"
    # 帶封面：封面不繪頁腳、內文首頁書頁號 1
    assert thumbnail_footer(1, cover_pages=1, title="書") is None
    assert thumbnail_footer(2, cover_pages=1, title="書")["number"] == "1"
    assert thumbnail_footer(3, cover_pages=1, title="書")["number"] == "2"


@pytest.mark.parametrize("zoom,expected", [
    (1.0, 150), (1.4, 225), (2.5, 450), (6.0, 450),
])
def test_分級對映一覽(zoom, expected):
    assert target_base_dpi(zoom) == expected
