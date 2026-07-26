"""對頁配對純函式 spread_pages（Sprint 129 甲4）：右翻書偶右奇左的頁別配對。

SSOT＝Sprint 22 側別：偶數書頁＝右頁（書口在右）、奇數書頁＝左頁（書口在左）；
右翻直排書 spread＝（偶右、奇左），讀序右→左＝頁碼小→大（右頁號 < 左頁號）。
故一組 spread＝(偶 E, 奇 E+1)：右＝E、左＝E+1。頁1（奇）恆單邊在左（右夥伴
頁0不存在）；末頁若為偶亦單邊在右（左夥伴 E+1 不存在）。

本檔為 editor/canvas.py::spread_pages 的獨立語意守門（pytest 基線），與真視窗
smoke C32（editor/smoke_spread.py）互為不同方法驗證（Gate 4）。
"""
from editor.canvas import spread_pages


def test_page_one_is_solo_left() -> None:
    # 頁1 奇＝左，右夥伴頁0不存在 → 單邊在左
    assert spread_pages(1, 11) == (1, None)
    assert spread_pages(1, 2) == (1, None)
    assert spread_pages(1, 1) == (1, None)


def test_even_page_pairs_with_next_odd_on_left() -> None:
    # 偶 E＝右、奇 E+1＝左：spread_pages 回 (left, right)
    assert spread_pages(2, 11) == (3, 2)
    assert spread_pages(4, 11) == (5, 4)
    assert spread_pages(10, 11) == (11, 10)


def test_odd_page_shares_spread_with_previous_even() -> None:
    # 導航到 spread 內任一頁都得同一組 (left, right)：頁3 與頁2 同 spread
    assert spread_pages(3, 11) == spread_pages(2, 11) == (3, 2)
    assert spread_pages(5, 11) == spread_pages(4, 11) == (5, 4)
    assert spread_pages(11, 11) == spread_pages(10, 11) == (11, 10)


def test_trailing_even_page_is_solo_right() -> None:
    # 末頁為偶（右）時左夥伴 E+1 不存在 → 單邊在右
    assert spread_pages(2, 2) == (None, 2)
    assert spread_pages(4, 4) == (None, 4)


def test_帶封面配對不特例_Sprint145紙面奇偶():
    """側別由紙面決定，配對公式與封面無關（Sprint 145，Owner 實體書模型）：
    紙面 1（封面）＝闔上的書，單邊；翻開封面即見紙面 2（目次）在右、紙面 3 在左；
    末偶紙面＝翻完闔上書的單頁封底畫面。136＝《成名之路》帶封面補頁後的總紙面。"""
    assert spread_pages(1, 136) == (1, None)
    assert spread_pages(2, 136) == (3, 2)
    assert spread_pages(3, 136) == (3, 2)
    assert spread_pages(136, 136) == (None, 136)


def test_side_and_reading_order_invariants() -> None:
    # 左頁恆奇（或 None）、右頁恆偶（或 None）；兩者皆在時 left == right + 1
    # 且右頁號 < 左頁號（讀序右→左＝頁碼小→大）
    for total in (1, 2, 3, 4, 11, 128):
        for n in range(1, total + 1):
            left, right = spread_pages(n, total)
            assert left is None or left % 2 == 1, (n, total, left)
            assert right is None or right % 2 == 0, (n, total, right)
            assert left is None or 1 <= left <= total
            assert right is None or 1 <= right <= total
            if left is not None and right is not None:
                assert left == right + 1
                assert right < left  # 右頁號較小
            # 目前頁必為 spread 兩側之一（不會兩側皆非本頁）
            assert n in (left, right)
