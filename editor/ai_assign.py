"""AI 樣式指派校正對話框（Sprint 79，§4.4「逐段確認與批次改派」介面承諾）。

表格逐段列出：段序／段首文字／現行樣式／建議樣式（下拉＝模版實際段落樣式
候選集，預選 AI 建議）／採用勾選（預設勾「有建議且異於現行」者）。確定後
只回報「勾選且異於現行」的 {para_idx: 樣式名}，套用走 session.apply_para_styles
單一 undo 步（app 回呼執行）。AI 建議為初稿定位（§4.4：不宣稱全自動），
無建議段（該批降級）維持原樣式並於頂部警告列不沉默。

目次欄（Sprint 135）：另三欄「採用目次／目次標題／層級」與樣式欄各持一組採用
語意（同一段可只採樣式或只採目次）。底部勾「生成目次頁」＝套用後於書首生成
目錄節。**頁碼欄不存在**：頁碼由排版引擎兩趟分頁算出，AI 一個數字都不出，
使用者也不手填（同 cjkfolio/toc.py 的分工鐵律）。模版未宣告 auto_toc 時該勾選
停用並於標籤說明原因。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_PREVIEW_CHARS = 18
_BASE_LEVELS = (1, 2, 3)
_HEADERS = ("採用", "段首文字", "現行樣式", "建議樣式", "採用目次", "目次標題", "層級")
_COL_ADOPT, _COL_STYLE, _COL_TOC, _COL_TITLE, _COL_LEVEL = 0, 3, 4, 5, 6


class AssignReviewDialog(QDialog):
    """逐段確認與批次改派（離屏可驗：程式化改勾選／下拉後呼 _assignments）。"""

    def __init__(self, doc, template, assignments, on_apply,
                 warnings=(), toc_entries=(), parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 樣式指派校正（初稿請人工確認）")
        self._doc = doc
        # callable(assignments, toc_entries, generate_toc) -> 錯誤訊息或 None
        self._on_apply = on_apply
        candidates = sorted(template.paragraph_styles)

        box = QVBoxLayout(self)
        head = QLabel("逐段確認 AI 建議（§4.4 初稿＋人工校正）："
                      "勾選＝採用該列建議；可先改下拉再採用。"
                      "目次頁碼由排版引擎計算，不在此填。")
        head.setWordWrap(True)
        box.addWidget(head)
        self._notice = QLabel("；".join(warnings))
        self._notice.setStyleSheet("color:#b00; font-size:11px;")
        self._notice.setWordWrap(True)
        box.addWidget(self._notice)

        self.table = QTableWidget(len(doc.paragraphs), len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self._combos = []
        self._levels = []
        suggested_toc = 0
        for i, para in enumerate(doc.paragraphs):
            suggested = assignments[i] if i < len(assignments) else None
            toc = toc_entries[i] if i < len(toc_entries) else None
            suggested_toc += toc is not None
            self._set_check(i, _COL_ADOPT,
                            suggested is not None and suggested != para.style)
            preview = QTableWidgetItem(para.text[:_PREVIEW_CHARS])
            preview.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 1, preview)
            current = QTableWidgetItem(para.style)
            current.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 2, current)
            combo = QComboBox()
            combo.addItems(candidates)
            combo.setCurrentText(suggested if suggested is not None else para.style)
            self.table.setCellWidget(i, _COL_STYLE, combo)
            self._combos.append(combo)
            self._add_toc_cells(i, para, toc)
        self.table.resizeColumnsToContents()
        box.addWidget(self.table)

        self._generate = QCheckBox("生成目次頁（置於書首，頁碼由排版引擎計算）")
        if getattr(template, "auto_toc", None) is None:
            self._generate.setChecked(False)
            self._generate.setEnabled(False)
            self._generate.setText(
                "生成目次頁（本模版未宣告 auto_toc，無目錄主版與條目樣式可用）")
        else:
            has_entry = suggested_toc or any(p.toc_title for p in doc.paragraphs)
            self._generate.setChecked(bool(has_entry))
        box.addWidget(self._generate)

        all_on = QPushButton("全部採用")
        all_off = QPushButton("全部不採")
        all_on.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        all_off.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton(all_on, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(all_off, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_confirm)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def _set_check(self, row: int, col: int, on: bool) -> None:
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.table.setItem(row, col, item)

    def _add_toc_cells(self, row: int, para, toc) -> None:
        """目次三欄：採用勾選、可編輯標題、層級下拉（層級只收既有選項＝免解析）。"""
        current = (para.toc_title, para.toc_level) if para.toc_title else None
        self._set_check(row, _COL_TOC, toc is not None and toc != current)
        title = toc[0] if toc is not None else (para.toc_title or "")
        self.table.setItem(row, _COL_TITLE, QTableWidgetItem(title))
        level = (toc[1] if toc is not None
                 else (para.toc_level if para.toc_level is not None else 1))
        combo = QComboBox()
        combo.addItems([str(v) for v in sorted({*_BASE_LEVELS, level})])
        combo.setCurrentText(str(level))
        self.table.setCellWidget(row, _COL_LEVEL, combo)
        self._levels.append(combo)

    def _set_all(self, state) -> None:
        for i in range(self.table.rowCount()):
            self.table.item(i, _COL_ADOPT).setCheckState(state)
            self.table.item(i, _COL_TOC).setCheckState(state)

    def _assignments(self) -> dict:
        """勾選且異於現行樣式的 {para_idx: 樣式名}（批次改派載荷）。"""
        out = {}
        for i, para in enumerate(self._doc.paragraphs):
            if self.table.item(i, _COL_ADOPT).checkState() != Qt.CheckState.Checked:
                continue
            style = self._combos[i].currentText()
            if style != para.style:
                out[i] = style
        return out

    def _toc_entries(self) -> dict:
        """勾選且異於現行條目的 {para_idx: (標題, 層級) 或 None}；空標題＝清除該段條目。"""
        out = {}
        for i, para in enumerate(self._doc.paragraphs):
            if self.table.item(i, _COL_TOC).checkState() != Qt.CheckState.Checked:
                continue
            title = self.table.item(i, _COL_TITLE).text().strip()
            entry = (title, int(self._levels[i].currentText())) if title else None
            current = (para.toc_title, para.toc_level) if para.toc_title else None
            if entry != current:
                out[i] = entry
        return out

    def _on_confirm(self) -> None:
        err = self._on_apply(self._assignments(), self._toc_entries(),
                             self._generate.isChecked())
        if err:
            self._notice.setText(err)  # 套用錯誤：留在對話框修正
            return
        self.accept()
