"""preflight 結果面板（Sprint 87 建立；Sprint 94 擴為三分區）。

唯讀顯示三份既有機械檢查的結果，判定邏輯全在 cjkfolio.preflight（已 pytest 驗），
本面板只呈現，逐筆列由 preflight 的 image_rows／ink_rows 產生（與 CLI 同一組列）：

- PDF/X-1a（check_pdfx）：ISO 15930-1 標準合規，不過＝不合規。
- 影像解析度（check_image_resolution）與油墨總量（check_ink_coverage）：§9 印廠
  條件、非 X 條款（Sprint 91／93 規則集分離定案），故摘要以警示色而非不合規紅字，
  且不影響 X-1a 結論。

認證級 preflight（Acrobat／印廠）非本機械檢查涵蓋（GAPS #18），未涵蓋聲明如實列出。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cjkfolio.preflight import (
    image_resolution_summary,
    image_rows,
    ink_coverage_summary,
    ink_rows,
    preflight_summary,
)

WARN_COLOR = "#b06000"   # 印廠條件風險（非 X 不合規），與 X-1a 不合規紅字區別
FAIL_COLOR = "#b00000"
PASS_COLOR = "#008000"


def _rule_rows(report) -> tuple:
    """X-1a 逐規則列，欄位語意與 image_rows／ink_rows 一致（狀態, 項目, 明細）。"""
    return tuple(("通過" if f.ok else "不過", f.rule, f.detail)
                 for f in report.findings)


def _make_table(rows, ok_word: str, fail_color: str) -> QTableWidget:
    """三欄唯讀表：狀態以顏色標示（ok_word 之外皆視為需注意）。"""
    table = QTableWidget(len(rows), 3)
    table.setHorizontalHeaderLabels(["狀態", "項目", "明細"])
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    for i, (status, rule, detail) in enumerate(rows):
        item = QTableWidgetItem(status)
        if status == ok_word:
            item.setForeground(Qt.GlobalColor.darkGreen)
        elif status == "未判讀":
            item.setForeground(Qt.GlobalColor.gray)
        else:
            item.setForeground(QColor(fail_color))
        table.setItem(i, 0, item)
        table.setItem(i, 1, QTableWidgetItem(rule))
        table.setItem(i, 2, QTableWidgetItem(detail))
    table.resizeColumnsToContents()
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _tab(table: QTableWidget) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(table)
    return page


class PreflightDialog(QDialog):
    """唯讀顯示三份檢查報告：三行摘要 ＋ 三分頁明細 ＋ 未涵蓋聲明。"""

    def __init__(self, report, image_report, ink_report, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PDF/X preflight 檢查結果")
        self.report = report
        self.image_report = image_report
        self.ink_report = ink_report

        self.summary_label = QLabel(f"結論：{preflight_summary(report)}")
        self.summary_label.setStyleSheet(
            "font-weight:bold; color:%s;" % (PASS_COLOR if report.ok else FAIL_COLOR))
        self.image_summary_label = QLabel(
            f"影像解析度（§9，非 X-1a 條款）：{image_resolution_summary(image_report)}")
        self.image_summary_label.setStyleSheet(
            "color:%s;" % (PASS_COLOR if image_report.ok else WARN_COLOR))
        self.ink_summary_label = QLabel(
            f"油墨總量（§9，非 X-1a 條款）：{ink_coverage_summary(ink_report)}")
        self.ink_summary_label.setStyleSheet(
            "color:%s;" % (PASS_COLOR if ink_report.ok else WARN_COLOR))

        self.table = _make_table(_rule_rows(report), "通過", FAIL_COLOR)
        self.image_table = _make_table(image_rows(image_report), "達標", WARN_COLOR)
        self.ink_table = _make_table(ink_rows(ink_report), "達標", WARN_COLOR)

        self.tabs = QTabWidget()
        self.tabs.addTab(_tab(self.table), f"PDF/X-1a（{len(report.findings)} 規則）")
        self.tabs.addTab(_tab(self.image_table), "影像解析度")
        self.tabs.addTab(_tab(self.ink_table), "油墨總量")

        self.not_covered_label = QLabel(
            "未涵蓋（誠實聲明）：" + "；".join(report.not_covered))
        self.not_covered_label.setWordWrap(True)
        self.not_covered_label.setStyleSheet("color:#666; font-size:11px;")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.image_summary_label)
        layout.addWidget(self.ink_summary_label)
        layout.addWidget(self.tabs)
        layout.addWidget(self.not_covered_label)
        layout.addWidget(buttons)
