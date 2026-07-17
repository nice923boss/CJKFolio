"""樣式面板（Sprint 64 點選套用＋Sprint 71 樣式管理＋Sprint 78 色票，§4.3 UI 半邊）。

段落樣式：點選套用至游標所在段（session.apply_para_style，Sprint 46 核心）。
字元樣式：點選套用至游標字或拖曳選取範圍（session.apply_style／apply_style_span）。
「（清除字元樣式）」項＝套 None 回段落樣式預設。
雙擊樣式項＝開 StyleEditDialog 編輯樣式參數（session.update_*，改樣式即全書套用，
Sprint 67〜68 核心）；雙擊色票項＝開 SwatchEditDialog 改色票值（session.update_color，
改值即全書變色，Sprint 76 核心）。新增／刪除／改名／另存走 app「樣式」選單。
樣式繼承的視覺化（樹狀清單）屬後續；本面板為平面清單。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from cjkfolio.styles import CHARACTER_STYLE_FIELDS, PARAGRAPH_STYLE_FIELDS

CLEAR_CHAR_STYLE = "（清除字元樣式）"


def _fmt_cmyk(cmyk) -> str:
    """色票 cmyk 顯示字串（「c, m, y, k」）；None＝空字串。"""
    if cmyk is None:
        return ""
    return ", ".join(f"{v:g}" for v in cmyk)


def parse_cmyk_text(text: str):
    """「c, m, y, k」字串 → tuple（值驗證由核心 COLOR_FIELDS 執行）；空字串＝None。"""
    if not text.strip():
        return None
    return tuple(part.strip() for part in text.split(","))


class SwatchEditDialog(QDialog):
    """色票值編輯對話框（Sprint 78）：cmyk（逗號分隔）／hex／note 三欄，值預填現行；
    只回報有改動欄位（值轉換與驗證由核心 style_editing.set_color 執行），錯誤以
    內嵌警示列顯示（承 StyleEditDialog 慣例）。"""

    def __init__(self, swatch, on_apply, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"編輯色票：{swatch.name}")
        self._swatch = swatch
        self._on_apply = on_apply  # callable(changes: dict) -> 錯誤訊息 str 或 None

        form = QFormLayout(self)
        head = QLabel(swatch.name)
        head.setStyleSheet("font-weight:bold;")
        form.addRow(head)
        self._notice = QLabel("")
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)
        form.addRow(self._notice)
        self._cmyk = QLineEdit(_fmt_cmyk(swatch.cmyk))
        self._hex = QLineEdit(swatch.hex or "")
        self._note = QLineEdit(swatch.note or "")
        form.addRow("cmyk（c, m, y, k 各 0〜1）", self._cmyk)
        form.addRow("hex（#RRGGBB 螢幕參考）", self._hex)
        form.addRow("note", self._note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _changes(self) -> dict:
        out = {}
        if self._cmyk.text() != _fmt_cmyk(self._swatch.cmyk):
            out["cmyk"] = parse_cmyk_text(self._cmyk.text())
        if self._hex.text() != (self._swatch.hex or ""):
            out["hex"] = self._hex.text() or None
        if self._note.text() != (self._swatch.note or ""):
            out["note"] = self._note.text() or None
        return out

    def _on_save(self) -> None:
        err = self._on_apply(self._changes())
        if err:
            self._notice.setText(err)  # 值驗證錯誤：留在對話框內修正
            return
        self.accept()


class StyleEditDialog(QDialog):
    """樣式參數編輯對話框（Sprint 71）：欄位取自 styles 欄位表，值預填現行效值。

    儲存時只回報「有改動的欄位」（changes dict，值為輸入字串，型別轉換由核心
    style_editing 執行）；套用錯誤（型別／不可編輯）以內嵌警示列顯示（非 modal
    訊息＝離屏可驗，同 AiConfigDialog 慣例）。
    """

    def __init__(self, kind: str, style, on_apply, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"編輯樣式：{style.name}")
        self._style = style
        self._on_apply = on_apply  # callable(changes: dict) -> 錯誤訊息 str 或 None
        fields = PARAGRAPH_STYLE_FIELDS if kind == "para" else CHARACTER_STYLE_FIELDS
        self._optional = {"source_font", "note", "color"}  # 空字串＝清 None
        self._edits = {}

        form = QFormLayout(self)
        head = QLabel(f"{style.name}" + (f"（承 {style.based_on}）" if style.based_on else ""))
        head.setStyleSheet("font-weight:bold;")
        form.addRow(head)
        self._notice = QLabel("")
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)
        form.addRow(self._notice)
        for fname in fields:
            value = getattr(style, fname)
            edit = QLineEdit("" if value is None else str(value))
            self._edits[fname] = edit
            form.addRow(fname, edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _changes(self) -> dict:
        """收集有改動的欄位（與現行效值字串比較；選配欄位空字串＝清為 None）。"""
        out = {}
        for fname, edit in self._edits.items():
            old = getattr(self._style, fname)
            old_text = "" if old is None else str(old)
            new_text = edit.text()
            if new_text == old_text:
                continue
            if fname in self._optional and new_text == "":
                out[fname] = None
            else:
                out[fname] = new_text
        return out

    def _on_save(self) -> None:
        err = self._on_apply(self._changes())
        if err:
            self._notice.setText(err)  # 值型別錯誤等：留在對話框內修正
            return
        self.accept()


class StylePanel(QWidget):
    """段落／字元樣式雙清單＋色票清單；點選回呼 on_para_style(name)／
    on_char_style(name|None)；雙擊回呼 on_edit_style(kind, name)（Sprint 71）／
    on_edit_swatch(name)（Sprint 78 色票值編輯）。"""

    def __init__(self, template, on_para_style, on_char_style,
                 on_edit_style=None, on_edit_swatch=None, parent=None) -> None:
        super().__init__(parent)
        self._on_para_style = on_para_style
        self._on_char_style = on_char_style
        self._on_edit_style = on_edit_style
        self._on_edit_swatch = on_edit_swatch

        self.para_list = QListWidget()
        self.para_list.itemClicked.connect(
            lambda item: self._on_para_style(item.text()))
        self.char_list = QListWidget()
        self.char_list.itemClicked.connect(self._pick_char)
        self.swatch_list = QListWidget()
        if on_edit_style is not None:
            self.para_list.itemDoubleClicked.connect(
                lambda item: self._on_edit_style("para", item.text()))
            self.char_list.itemDoubleClicked.connect(
                lambda item: self._edit_char(item))
        if on_edit_swatch is not None:
            self.swatch_list.itemDoubleClicked.connect(
                lambda item: self._on_edit_swatch(item.text()))
        self.refresh(template)

        box = QVBoxLayout(self)
        box.setContentsMargins(4, 4, 4, 4)
        para_label = QLabel("段落樣式（點選套用至游標段；雙擊編輯）")
        char_label = QLabel("字元樣式（點選套用至游標字／選取；雙擊編輯）")
        swatch_label = QLabel("色票（雙擊改值＝全書變色；樣式 color 欄引用）")
        for w in (para_label, char_label, swatch_label):
            w.setStyleSheet("font-size:11px; color:#555;")
        box.addWidget(para_label)
        box.addWidget(self.para_list, 3)
        box.addWidget(char_label)
        box.addWidget(self.char_list, 2)
        box.addWidget(swatch_label)
        box.addWidget(self.swatch_list, 1)

    def refresh(self, template) -> None:
        """依現行模版重建清單（樣式／色票變更與 undo 後同步，Sprint 71／78）。"""
        self.para_list.clear()
        self.para_list.addItems(sorted(template.paragraph_styles))
        self.char_list.clear()
        self.char_list.addItem(CLEAR_CHAR_STYLE)
        self.char_list.addItems(sorted(template.character_styles))
        self.swatch_list.clear()
        for name in sorted(template.colors):
            cmyk = template.colors[name].cmyk
            label = f"{name}（{_fmt_cmyk(cmyk)}）" if cmyk is not None else f"{name}（僅 hex）"
            self.swatch_list.addItem(label)

    def selected_style(self, kind: str):
        """目前選取的樣式名（無選取或選到清除項回 None）。"""
        lst = self.para_list if kind == "para" else self.char_list
        item = lst.currentItem()
        if item is None or item.text() == CLEAR_CHAR_STYLE:
            return None
        return item.text()

    def select_style(self, kind: str, name: str) -> None:
        """程式化選取樣式項（選單操作與離屏驗證用）。"""
        lst = self.para_list if kind == "para" else self.char_list
        matches = lst.findItems(name, Qt.MatchFlag.MatchExactly)
        if not matches:
            raise KeyError(f"面板無此樣式：{name}")
        lst.setCurrentItem(matches[0])

    def selected_swatch(self):
        """目前選取的色票名（清單標籤含值註記，取「（」前名稱）。"""
        item = self.swatch_list.currentItem()
        return None if item is None else item.text().split("（", 1)[0]

    def select_swatch(self, name: str) -> None:
        """程式化選取色票項（選單操作與離屏驗證用）。"""
        for i in range(self.swatch_list.count()):
            item = self.swatch_list.item(i)
            if item.text().split("（", 1)[0] == name:
                self.swatch_list.setCurrentItem(item)
                return
        raise KeyError(f"面板無此色票：{name}")

    def _pick_char(self, item) -> None:
        name = item.text()
        self._on_char_style(None if name == CLEAR_CHAR_STYLE else name)

    def _edit_char(self, item) -> None:
        if item.text() != CLEAR_CHAR_STYLE:
            self._on_edit_style("char", item.text())

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
