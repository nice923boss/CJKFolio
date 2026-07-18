"""PDF/X preflight 結果面板（Sprint 87，§6 Phase 4「preflight 面板」UI）。

唯讀顯示既有機械 preflight（cjkfolio.preflight.check_pdfx）的結果：逐規則通過／不過、
未涵蓋誠實聲明、結論摘要。判定邏輯全在 check_pdfx（已 pytest 驗），本面板只呈現。
認證級 preflight（Acrobat／印廠）非本機械檢查涵蓋（GAPS #18），未涵蓋聲明如實列出。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from cjkfolio.preflight import preflight_summary


class PreflightDialog(QDialog):
    """唯讀顯示一份 PreflightReport：摘要 ＋ 逐規則表 ＋ 未涵蓋聲明。"""

    def __init__(self, report, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PDF/X preflight 檢查結果")
        self.report = report

        self.summary_label = QLabel(f"結論：{preflight_summary(report)}")
        self.summary_label.setStyleSheet(
            "font-weight:bold; color:%s;" % ("#080" if report.ok else "#b00"))

        self.table = QTableWidget(len(report.findings), 3)
        self.table.setHorizontalHeaderLabels(["狀態", "規則", "說明"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        for i, finding in enumerate(report.findings):
            status = QTableWidgetItem("通過" if finding.ok else "不過")
            status.setForeground(
                Qt.GlobalColor.darkGreen if finding.ok else Qt.GlobalColor.red)
            self.table.setItem(i, 0, status)
            self.table.setItem(i, 1, QTableWidgetItem(finding.rule))
            self.table.setItem(i, 2, QTableWidgetItem(finding.detail))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

        self.not_covered_label = QLabel(
            "未涵蓋（誠實聲明）：" + "；".join(report.not_covered))
        self.not_covered_label.setWordWrap(True)
        self.not_covered_label.setStyleSheet("color:#666; font-size:11px;")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)
        layout.addWidget(self.not_covered_label)
        layout.addWidget(buttons)
