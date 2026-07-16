"""樣式面板（Sprint 64，§4.3「樣式面板：點選即套用」的 Phase 2 UI 半邊）。

段落樣式：點選套用至游標所在段（session.apply_para_style，Sprint 46 核心）。
字元樣式：點選套用至游標字（單字 DocRange，session.apply_style，Sprint 45 核心；
拖曳範圍選取 UI 未建前的最小可用，範圍套用同一回呼可直接沿用）。
「（清除字元樣式）」項＝套 None 回段落樣式預設。
雙擊編輯樣式參數與樣式繼承屬 Phase 3 樣式系統（§4.3），本面板只做點選套用。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget

CLEAR_CHAR_STYLE = "（清除字元樣式）"


class StylePanel(QWidget):
    """段落／字元樣式雙清單；點選回呼 on_para_style(name)／on_char_style(name|None)。"""

    def __init__(self, template, on_para_style, on_char_style, parent=None) -> None:
        super().__init__(parent)
        self._on_para_style = on_para_style
        self._on_char_style = on_char_style

        self.para_list = QListWidget()
        self.para_list.addItems(sorted(template.paragraph_styles))
        self.para_list.itemClicked.connect(
            lambda item: self._on_para_style(item.text()))
        self.char_list = QListWidget()
        self.char_list.addItem(CLEAR_CHAR_STYLE)
        self.char_list.addItems(sorted(template.character_styles))
        self.char_list.itemClicked.connect(self._pick_char)

        box = QVBoxLayout(self)
        box.setContentsMargins(4, 4, 4, 4)
        para_label = QLabel("段落樣式（點選套用至游標段）")
        char_label = QLabel("字元樣式（點選套用至游標字）")
        for w in (para_label, char_label):
            w.setStyleSheet("font-size:11px; color:#555;")
        box.addWidget(para_label)
        box.addWidget(self.para_list, 3)
        box.addWidget(char_label)
        box.addWidget(self.char_list, 2)

    def _pick_char(self, item) -> None:
        name = item.text()
        self._on_char_style(None if name == CLEAR_CHAR_STYLE else name)

    def pick_para_style(self, name: str) -> None:
        """程式化點選（離屏驗證用），與 itemClicked 同回呼。"""
        matches = self.para_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if not matches:
            raise KeyError(f"面板無此段落樣式：{name}")
        self._on_para_style(name)

    def pick_char_style(self, name) -> None:
        """程式化點選（離屏驗證用）；None＝清除項。"""
        label = CLEAR_CHAR_STYLE if name is None else name
        if not self.char_list.findItems(label, Qt.MatchFlag.MatchExactly):
            raise KeyError(f"面板無此字元樣式：{label}")
        self._on_char_style(name)
