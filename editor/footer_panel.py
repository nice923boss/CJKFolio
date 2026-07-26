"""書眉／頁碼對話框（Sprint 142）：改字面文字、挪位置、批次挪位置。

Owner 回饋：右下角固定呈現的書名要能改文字、移動位置、批次移動位置，
「避免指派錯誤還可以手動修改」。

單位刻意用 mm（對齊「成品尺寸…」對話框，Owner 量書用的是 mm），模版內部存 pt，
本檔負責換算。為了讓「開起來什麼都沒動就按確定」＝真的什麼都沒發生（不推 undo 步），
values() 只回**真的被改過**的欄位，故 mm↔pt 的小數位換算誤差不會被當成一次變更。

文字覆寫只對書名（source＝title）開放：頁碼是逐頁計算出來的，寫死字面會讓每頁都印
同一個字，那不是「改書眉」而是壞掉的頁碼，故該欄位在選到頁碼時停用並就地說明。

只收數值，不做語意判定；套用與 undo 在 cjkfolio.style_editing.set_footer_item
與 EditSession.update_footer_item（Qt 無關、pytest 已驗）。
"""
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from cjkfolio.primitives import PT_PER_MM

#: 位置欄上限（mm）：頁腳落在紙上即可，給足大開本的餘裕，不必逐模版算。
MAX_OFFSET_MM = 2000.0


def _mm_spin(pt_value: float) -> QDoubleSpinBox:
    """由 pt 建 mm 數值欄（小數兩位＝0.01mm，遠細於印刷可辨的位移）。"""
    spin = QDoubleSpinBox()
    spin.setRange(0.0, MAX_OFFSET_MM)
    spin.setDecimals(2)
    spin.setSingleStep(1.0)
    spin.setSuffix(" mm")
    spin.setValue(pt_value / PT_PER_MM)
    return spin


class FooterItemDialog(QDialog):
    """改指定主版的書眉／頁碼元素：文字、距上緣、距書口，可批次套到其他主版。"""

    def __init__(self, template, master_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"書眉與頁碼（主版 {master_name}）")
        self._template = template
        self._master_name = master_name
        self._items = dict(template.masters[master_name].footer)

        self._picker = QComboBox()
        for name, item in self._items.items():
            label = "書名" if item.source == "title" else "頁碼"
            self._picker.addItem(f"{name}（{label}）", name)
        self._picker.currentIndexChanged.connect(self._load_item)

        self._text = QLineEdit()
        self._baseline = _mm_spin(0.0)
        self._outer = _mm_spin(0.0)
        self._batch = QCheckBox(  # 勾了連文字一起套，故標籤據實寫兩者
            "這次的變更同時套到其他主版（批次移動位置／批次改字）")
        self._batch_note = QLabel()
        self._batch_note.setStyleSheet("color:#555; font-size:11px;")
        self._batch_note.setWordWrap(True)

        notice = QLabel(
            "文字：留空＝印文件的書名（AI 指派或匯入時帶進來的那個）；填字＝這個主版"
            "一律改印你填的字。頁碼逐頁計算，不開放寫死字面。\n"
            "距上緣＝文字基線到紙張上緣；距書口＝文字靠書口那一邊到紙張書口邊。"
            "書口在左還在右，依主版鏡像設定逐頁換邊，你只需給一個距離。\n"
            "書眉屬模版設定，不隨文件檔儲存，要留存請用「樣式 > 另存模版…」。")
        notice.setStyleSheet("color:#555; font-size:11px;")
        notice.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow("元素", self._picker)
        form.addRow("文字", self._text)
        form.addRow("距上緣", self._baseline)
        form.addRow("距書口", self._outer)
        form.addRow("", self._batch)
        form.addRow("", self._batch_note)
        form.addRow(notice)
        form.addRow(buttons)
        self._load_item()

    # ---------- 逐元素載入 ----------

    def _load_item(self) -> None:
        """切換元素時重載欄位；同時記下初值，供 values() 只回真的改過的欄位。"""
        item = self._items[self.item_name()]
        self._text.setText(item.text or "")
        self._text.setEnabled(item.source == "title")
        self._text.setPlaceholderText(
            "留空＝印文件書名" if item.source == "title"
            else "頁碼由頁數計算，不可寫死")
        self._baseline.setValue(item.baseline_from_top_pt / PT_PER_MM)
        self._outer.setValue(item.outer_offset_pt / PT_PER_MM)
        self._initial = (self._text.text(), self._baseline.value(),
                         self._outer.value())
        others = [n for n, m in self._template.masters.items()
                  if n != self._master_name and self.item_name() in m.footer]
        self._batch.setEnabled(bool(others))
        self._batch_note.setText(
            "其他含此元素的主版：" + "、".join(others) if others
            else "沒有其他主版宣告這個元素，批次與只改本主版結果相同")
        if not others:
            self._batch.setChecked(False)

    # ---------- 收值 ----------

    def item_name(self) -> str:
        return self._picker.currentData()

    def values(self) -> dict:
        """只回真的被改過的欄位（沒動就按確定＝空 dict＝no-op，不佔 undo 步）。"""
        text, baseline, outer = self._initial
        changes = {}
        if self._text.isEnabled() and self._text.text() != text:
            changes["text"] = self._text.text()  # 空字串由純層正規化回「無覆寫」
        if self._baseline.value() != baseline:
            changes["baseline_from_top_pt"] = self._baseline.value() * PT_PER_MM
        if self._outer.value() != outer:
            changes["outer_offset_pt"] = self._outer.value() * PT_PER_MM
        return changes

    def all_masters(self) -> bool:
        return self._batch.isChecked()
