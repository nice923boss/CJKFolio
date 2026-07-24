"""editor 尋找／取代的離屏煙霧驗證（C30；Sprint 128 丙1，行數紀律自成一檔）。

離屏可驗：純函式 find_matches（合成段落釘死非重疊、大小寫、空 query、CJK 重複字）、
編輯選單「尋找…」Ctrl+F 與「取代…」Ctrl+H、非模態對話框開啟、真樣本檢索命中數與
頁定位高亮（_sel_items 非空＝畫到字格）、找不到據實提示、取代一處＝單一 undo 步
（can_undo 由空轉有、一次 undo 回空）、全部取代 N 處＝N 步復原（GAPS #83 據實）。
真視窗檢索與對話框手感待 Owner（GAPS #83）。

由 smoke_check.main() 呼叫，離屏環境（QT_QPA_PLATFORM＝offscreen、QApplication 已建）
由呼叫端備妥。
"""
from types import SimpleNamespace

from PySide6.QtWidgets import QMenu

from editor.find_actions import FindMatch, find_matches
from editor.find_panel import FindDialog


def _check_pure() -> None:
    """純函式 find_matches：合成段落釘死偏移語意（與 UI 無關）。"""
    paras = [SimpleNamespace(text="abcABCabc"),
             SimpleNamespace(text="重重重"),
             SimpleNamespace(text="")]

    # 預設不分大小寫：三個 abc（含中段 ABC 折疊命中）
    triples = [(m.para_idx, m.start, m.end) for m in find_matches(paras, "abc")]
    assert triples == [(0, 0, 3), (0, 3, 6), (0, 6, 9)], triples

    # 區分大小寫：只命中小寫 abc（0、6）
    cased = [(m.para_idx, m.start, m.end)
             for m in find_matches(paras, "abc", case_sensitive=True)]
    assert cased == [(0, 0, 3), (0, 6, 9)], cased

    # 非重疊：「重重」於「重重重」只命中一次（下一次搜尋自 idx+2 起，無餘位）
    overlap = [(m.para_idx, m.start, m.end) for m in find_matches(paras, "重重")]
    assert overlap == [(1, 0, 2)], overlap

    # CJK 單字重複：逐字命中
    singles = [(m.para_idx, m.start, m.end) for m in find_matches(paras, "重")]
    assert singles == [(1, 0, 1), (1, 1, 2), (1, 2, 3)], singles

    # 空 query 回空清單；回傳型別為 FindMatch
    assert find_matches(paras, "") == []
    assert isinstance(find_matches(paras, "abc")[0], FindMatch)


def check_find(EditorWindow, DOC) -> None:
    """跑 C30 並逐項 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    _check_pure()

    windows = []
    try:
        # 編輯選單「尋找…」Ctrl+F 與「取代…」Ctrl+H
        win = EditorWindow(str(DOC))
        windows.append(win)
        edit_menu = next(
            m for m in win.menuBar().findChildren(QMenu) if m.title() == "編輯")
        acts = [a for a in edit_menu.actions() if not a.isSeparator()]
        labels = [a.text() for a in acts]
        assert "尋找…" in labels and "取代…" in labels, f"編輯選單缺尋找／取代：{labels}"
        keys = {a.text(): a.shortcut().toString() for a in acts}
        assert keys["尋找…"] == "Ctrl+F" and keys["取代…"] == "Ctrl+H", keys

        # 非模態對話框開啟（Ctrl+H 起手聚焦取代欄不炸）
        assert win._find_dialog is None
        win._open_find_dialog(replace=True)
        dlg = win._find_dialog
        assert isinstance(dlg, FindDialog) and not dlg.isModal(), "尋找對話框應為非模態"

        # 真樣本檢索：「三」於 case-divider 段3 命中 2 次，經訊號驅動導航高亮
        dlg._query_edit.setText("三")
        dlg.find_requested.emit()  # 驗 find_requested → _find_next 訊號接線
        assert "第 1／2 個" in dlg._status.text(), dlg._status.text()
        assert win._sel_items, "命中未畫出選取高亮（頁定位或 _set_selection 失效）"
        assert win.page.number == win._page_of_match(
            FindMatch(3, 0, 1)), "命中頁定位與 _page_of_match 不一致"
        dlg.find_requested.emit()  # 前進到第 2 個
        assert "第 2／2 個" in dlg._status.text(), dlg._status.text()

        # 找不到：據實提示、清高亮
        dlg._query_edit.setText("龘")
        win._find_next()
        assert "找不到" in dlg._status.text() and not win._sel_items, "找不到未清高亮"

        # 取代一處＝單一 undo 步：can_undo 由空轉有，一次 undo 回空
        win_r = EditorWindow(str(DOC))
        windows.append(win_r)
        win_r._open_find_dialog()
        dlg_r = win_r._find_dialog
        dlg_r._query_edit.setText("三")
        dlg_r._replace_edit.setText("参")
        assert not win_r.session.can_undo(), "開檔應為空 undo 堆疊"
        win_r._find_next()  # 純導航不提交
        assert not win_r.session.can_undo(), "尋找不應提交 undo 步"
        win_r._replace_one()
        assert win_r.session.can_undo(), "取代後應可復原"
        assert win_r.doc.paragraphs[3].text[0] == "参", "取代未落到段3首字"
        win_r.session.undo()
        assert not win_r.session.can_undo(), "取代一處應恰為單一 undo 步"
        assert win_r.doc.paragraphs[3].text[0] == "三", "undo 應還原段3首字"

        # 全部取代 N 處＝N 步復原（GAPS #83 據實非原子）
        win_a = EditorWindow(str(DOC))
        windows.append(win_a)
        win_a._open_find_dialog()
        dlg_a = win_a._find_dialog
        dlg_a._query_edit.setText("三")
        dlg_a._replace_edit.setText("参")
        assert not win_a.session.can_undo()
        win_a._replace_all()
        assert "已全部取代 2 處" in dlg_a._status.text(), dlg_a._status.text()
        full = "".join(p.text for p in win_a.doc.paragraphs)
        assert "三" not in full and full.count("参") == 2, "全部取代後字面不符"
        win_a.session.undo()
        win_a.session.undo()
        assert not win_a.session.can_undo(), "全部取代 2 處應為 2 步復原（GAPS #83）"
        assert "".join(p.text for p in win_a.doc.paragraphs).count("三") == 2, \
            "兩步 undo 應完全還原"
        for w in windows:
            if w._find_dialog is not None:
                w._find_dialog.close()
    finally:
        for w in windows:
            w._shutdown_thumbnails()

    print(
        "C30 尋找／取代：純函式 find_matches（非重疊／大小寫／空 query／CJK 重複字）"
        "＋編輯選單尋找 Ctrl+F／取代 Ctrl+H＋非模態對話框＋真樣本「三」命中 2 處經訊號"
        "驅動頁定位高亮＋找不到據實提示＋取代一處單一 undo 步＋全部取代 2 處 2 步復原"
        "（GAPS #83 據實）"
    )
