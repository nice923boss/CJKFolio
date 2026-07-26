"""標點快捷列（Sprint 146）：常用書冊標點一鍵送進文字輸入欄。

Owner 需求：「要有所有書冊會常用標點符號的快捷按鈕，點選就能輸入該標點符號。」

三個設計決定：

一、按鈕送進「文字輸入欄」而非直接改文件。提交仍是 Enter，走既有
    session.insert／insert_frame／replace_span，故一步 undo、全文 reflow、游標跟隨
    通通沿用，不新增第二條變更文件的程式路徑（也因此標點可以先跟打好的字接在一起
    再一次提交）。

二、按鈕不吃鍵盤焦點（NoFocus），回呼裡把焦點交回輸入欄。否則按完標點焦點停在
    按鈕上，接著按 Enter 是再觸發同一顆按鈕，不是提交。

三、成對標點一次插入兩枚並把游標放中間：按「」就直接在引號內接著打字。

字表以 cjkfolio/engine.py 的既有標點常數為界（LINE_START_FORBIDDEN 收尾類、
LINE_END_FORBIDDEN 起頭類、_DASHES 破折號），表內每一枚都已走過行首行尾禁則、
約物擠壓與直排字形三條既有路徑，不是新字集（smoke C44 逐字核對）。表外的標點
（如【】）刻意不放：點得到卻沒有禁則規則管它，等於做出一顆會排錯的按鈕；要放得先
量真書再補進引擎禁則表，屬引擎工程（GAPS #105）。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QWidget

SINGLES = (
    ("。", "句號"),
    ("，", "逗號"),
    ("、", "頓號"),
    ("：", "冒號"),
    ("；", "分號"),
    ("？", "問號"),
    ("！", "驚嘆號"),
    ("·", "間隔號"),
    ("……", "省略號（六點，佔兩格）"),
    ("——", "破折號（兩枚，引擎成對塑形為連字）"),
)

PAIRS = (
    ("「", "」", "引號"),
    ("『", "』", "雙引號（引號內再引）"),
    ("（", "）", "圓括號"),
    ("〔", "〕", "方括號"),
    ("《", "》", "書名號"),
    ("〈", "〉", "篇名號"),
    ("｛", "｝", "花括號"),
    ("〖", "〗", "空心方頭括號"),
)


def _label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("color:#666; font-size:11px;")
    return label


class PunctBar(QWidget):
    """標點快捷列：點按鈕 → on_insert(left, right)（單枚者 right＝空字串）。

    buttons＝{按鈕字面: QPushButton}，供 smoke 以字面直接點按（離屏無滑鼠）。
    """

    def __init__(self, on_insert, parent=None) -> None:
        super().__init__(parent)
        self._on_insert = on_insert
        self.buttons: dict = {}

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(2)
        grid.setVerticalSpacing(2)
        grid.addWidget(_label("單枚"), 0, 0)
        grid.addWidget(_label("成對"), 1, 0)
        for col, (mark, name) in enumerate(SINGLES, start=1):
            grid.addWidget(self._make_button(mark, "", name), 0, col)
        for col, (left, right, name) in enumerate(PAIRS, start=1):
            grid.addWidget(self._make_button(left, right, name), 1, col)
        grid.setColumnStretch(len(SINGLES) + 1, 1)  # 按鈕靠左，剩餘寬度留白

    def _make_button(self, left: str, right: str, name: str) -> QPushButton:
        face = left + right
        btn = QPushButton(face)
        btn.setToolTip(
            f"{name}：送進文字輸入欄"
            f"{'（游標落在兩枚之間）' if right else ''}，按 Enter 插入文件"
        )
        btn.setFixedHeight(26)
        btn.setMinimumWidth(40)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 見檔頭設計決定二
        btn.clicked.connect(lambda: self._on_insert(left, right))
        self.buttons[face] = btn
        return btn


__all__ = ["PAIRS", "SINGLES", "PunctBar"]
