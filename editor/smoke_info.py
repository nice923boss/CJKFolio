"""editor 文件資訊的離屏煙霧驗證（C31；Sprint 128 丙2，行數紀律自成一檔）。

離屏可驗：純函式 document_stats（合成 doc／layout 釘死總字數、段數、頁數、樣式用量
排序與同量名序）、真樣本 case-divider 統計（48 字、6 段、樣式直方 2／2／1／1）、
工具選單「文件資訊…」項、開啟對話框回填狀態列摘要、DocInfoDialog 用量表列數正確。

由 smoke_check.main() 呼叫，離屏環境（QT_QPA_PLATFORM＝offscreen、QApplication 已建）
由呼叫端備妥。
"""
from types import SimpleNamespace

from PySide6.QtWidgets import QMenu

from editor.info_actions import DocStats, document_stats
from editor.info_panel import DocInfoDialog


def _check_pure() -> None:
    """純函式 document_stats：合成 doc／layout 釘死統計與排序（與 UI 無關）。"""
    doc = SimpleNamespace(paragraphs=[
        SimpleNamespace(text="hello", style="Body"),
        SimpleNamespace(text="world!", style="Body"),
        SimpleNamespace(text="Hi", style="Head"),
    ])
    layout = SimpleNamespace(pages=[object(), object()])  # 2 頁
    stats = document_stats(doc, layout)
    assert isinstance(stats, DocStats)
    assert stats.total_chars == 13, stats.total_chars       # 5＋6＋2
    assert stats.paragraph_count == 3
    assert stats.page_count == 2
    assert stats.style_usage == (("Body", 2), ("Head", 1)), stats.style_usage

    # 同量依樣式名遞增（Alpha 在 Zeta 前）
    doc2 = SimpleNamespace(paragraphs=[
        SimpleNamespace(text="a", style="Zeta"),
        SimpleNamespace(text="b", style="Alpha"),
    ])
    tie = document_stats(doc2, SimpleNamespace(pages=[object()]))
    assert tie.style_usage == (("Alpha", 1), ("Zeta", 1)), tie.style_usage


def check_info(EditorWindow, DOC) -> None:
    """跑 C31 並逐項 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    _check_pure()

    win = EditorWindow(str(DOC))
    try:
        # 真樣本統計：48 字、6 段、頁數＝版面頁數、樣式直方 2／2／1／1
        stats = document_stats(win.doc, win.layout_result)
        assert stats.total_chars == 48, stats.total_chars
        assert stats.paragraph_count == 6, stats.paragraph_count
        assert stats.page_count == len(win.layout_result.pages) >= 1
        usage = dict(stats.style_usage)
        assert usage == {"個案欄標-黑W7": 1, "個案扉頁大標-NotoSans": 1,
                         "個案中標-NotoSans": 2, "內文-明體直排": 2}, usage
        counts = [c for _, c in stats.style_usage]
        assert counts == sorted(counts, reverse=True), f"用量未依遞減排序：{counts}"
        assert sum(counts) == stats.paragraph_count, "樣式段數總和應等於段數"

        # 工具選單「文件資訊…」
        tools_menu = next(
            m for m in win.menuBar().findChildren(QMenu) if m.title() == "工具")
        labels = [a.text() for a in tools_menu.actions() if not a.isSeparator()]
        assert "文件資訊…" in labels, f"工具選單缺文件資訊項：{labels}"

        # 開啟對話框：回填狀態列摘要（exec 替身避免 modal 阻塞）
        orig_exec = DocInfoDialog.exec
        DocInfoDialog.exec = lambda self: None
        try:
            win._show_document_info()
        finally:
            DocInfoDialog.exec = orig_exec
        msg = win.statusBar().currentMessage()
        assert "48 字" in msg and "6 段" in msg and "種段落樣式" in msg, msg

        # DocInfoDialog 用量表列數＝樣式種數，首列為用量最高者
        dlg = DocInfoDialog(stats, parent=win)
        try:
            assert dlg._table.rowCount() == len(stats.style_usage) == 4
            assert dlg._table.item(0, 0).text() == stats.style_usage[0][0]
            assert dlg._table.item(0, 1).text() == str(stats.style_usage[0][1])
        finally:
            dlg.close()
    finally:
        win._shutdown_thumbnails()

    print(
        "C31 文件資訊：純函式 document_stats（總字數／段數／頁數／樣式用量排序與同量"
        "名序）＋真樣本 case-divider 48 字 6 段樣式直方 2／2／1／1＋工具選單文件資訊項"
        "＋開啟回填狀態列摘要＋DocInfoDialog 用量表列數正確"
    )
