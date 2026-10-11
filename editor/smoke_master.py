"""smoke C33：主版指派介面（Sprint 130 丁1；自 smoke_check.py 分檔，行數紀律慣例）。

離屏可驗（不含視覺與滑鼠實測）：頁面面板右鍵選單「指派主版（頁 N）」子選單，
八主版依模版著作序（A→H，H-封面 Sprint 132）、勾選跟隨該頁 page.master；指派既有節首頁換節主版
（重排後留在右鍵頁、狀態列據實）；勾選跟隨改派後主版；節內乾淨起頁升為新節首
（狀態列提示「延續至下一節首」）；取消節首併回前節；跨頁續段起頁指派項停用並提示。
真右鍵手感與選單彈出位置待 Owner 真視窗（GAPS #19 批次）。
"""
from PySide6.QtWidgets import QMenu


def _assign_submenu(menu: QMenu) -> QMenu:
    """取右鍵選單內「指派主版」子選單（findChildren：QAction.menu() 不可靠，C26 教訓）。"""
    return next(
        m for m in menu.findChildren(QMenu) if m.title().startswith("指派主版"))


def _master_acts(menu: QMenu):
    """子選單內主版項（濾掉分隔線）。"""
    return [a for a in _assign_submenu(menu).actions() if not a.isSeparator()]


def _checked(acts):
    return [a.text() for a in acts if a.isChecked()]


def _has_cancel(menu: QMenu) -> bool:
    return any(a.text().startswith("取消節首") for a in menu.actions())


def check_master(EditorWindow, chapter_path, paiban_path) -> None:
    # ── 多節樣張 chapter-opening：頁 1 首節 B-部扉、頁 2 節首（段 2）A-內文版 ──
    win = EditorWindow(str(chapter_path))
    pages = [p for p in win.layout_result.pages if not p.blank]  # 補頁不計（S144）
    assert len(pages) == 2, f"樣張應 2 頁內文，得 {len(pages)}"
    masters_order = list(win.template.masters)
    assert len(masters_order) == 8, masters_order  # A〜G＋H-封面（Sprint 132）

    # 頁 1：八主版著作序、皆可勾、勾選＝B-部扉、無「取消節首」（段 0 未帶標記＝首節預設）
    menu1 = win._build_page_menu(1)
    acts1 = _master_acts(menu1)
    assert _assign_submenu(menu1).title() == "指派主版（頁 1）"
    assert [a.text() for a in acts1] == masters_order, [a.text() for a in acts1]
    assert all(a.isCheckable() for a in acts1)
    assert _checked(acts1) == ["B-部扉"], _checked(acts1)
    assert not _has_cancel(menu1), "頁 1 首節不應有取消節首"

    # 頁 2：勾選＝A-內文版、有「取消節首」（段 2 帶節首標記）
    menu2 = win._build_page_menu(2)
    assert _checked(_master_acts(menu2)) == ["A-內文版"]
    assert _has_cancel(menu2), "頁 2 節首應可取消"

    # 指派頁 2 節 → E-序文版：換節主版、重排後留在頁 2、勾選跟隨、狀態據實
    next(a for a in _master_acts(menu2) if a.text() == "E-序文版").trigger()
    assert win.doc.paragraphs[2].master == "E-序文版"
    assert win.layout_result.pages[1].master == "E-序文版"
    assert win.page.number == 2, f"指派後未留在右鍵頁，得頁 {win.page.number}"
    assert "頁 2 起的節改用主版 E-序文版" in win.statusBar().currentMessage()
    assert _checked(_master_acts(win._build_page_menu(2))) == ["E-序文版"]

    win.session.undo()  # 回 A-內文版（供「取消節首」測）
    assert win.doc.paragraphs[2].master == "A-內文版"

    # 取消頁 2 節首：段 2 標記清除、本節併回前節、狀態據實、且可 undo 回原
    menu2b = win._build_page_menu(2)
    next(a for a in menu2b.actions() if a.text().startswith("取消節首")).trigger()
    assert win.doc.paragraphs[2].master is None
    msg = win.statusBar().currentMessage()
    assert "已取消頁 2 節首" in msg and "併回前節" in msg, msg
    win.session.undo()
    assert win.doc.paragraphs[2].master == "A-內文版"

    # ── 單節多頁真稿 paiban-xiaoji-ch1：節內乾淨起頁升節首＋跨頁續段守門 ──
    win2 = EditorWindow(str(paiban_path))

    def body_pages() -> int:
        return sum(1 for p in win2.layout_result.pages if not p.blank)

    assert body_pages() == 11

    # 頁 2 為節內乾淨起頁（起始段 5，非續段、非節首）：升為新節首、延續至下一節首
    assert win2._page_start_para(2) == 5
    menu_p2 = win2._build_page_menu(2)
    assert _checked(_master_acts(menu_p2)) == ["A-內文版"]
    assert not _has_cancel(menu_p2), "節內非節首頁不應有取消節首"
    next(a for a in _master_acts(menu_p2) if a.text() == "B-部扉").trigger()
    assert win2.doc.paragraphs[5].master == "B-部扉"
    msg2 = win2.statusBar().currentMessage()
    assert "段 6" in msg2 and "起新開一節" in msg2 and "延續至下一節首" in msg2, msg2
    assert win2.page.number == 2, f"升節首後未留在右鍵頁，得頁 {win2.page.number}"
    win2.session.undo()
    assert win2.doc.paragraphs[5].master is None
    assert body_pages() == 11, "undo 後未回 11 頁內文"

    # 頁 3 為跨頁續段開頭（起始段延續自前頁）：指派項停用、僅提示、無主版可選、無取消節首
    assert win2._page_start_para(3) is None
    menu_p3 = win2._build_page_menu(3)
    hint_acts = _assign_submenu(menu_p3).actions()
    assert len(hint_acts) == 1 and not hint_acts[0].isEnabled(), hint_acts
    assert "跨頁段落" in hint_acts[0].text(), hint_acts[0].text()
    assert not _has_cancel(menu_p3), "跨頁續段頁不應有取消節首"

    for w in (win, win2):  # 退出安全：縮圖執行緒收工（closeEvent 同路徑）
        w._shutdown_thumbnails()
    print(
        "C33 主版指派介面：右鍵選單八主版著作序（A→H）＋勾選跟隨 page.master、"
        "指派既有節首頁換節主版（留在右鍵頁）、勾選跟隨改派、節內乾淨起頁升新節首"
        "（延續至下一節首）、取消節首併回前節（可 undo）、跨頁續段起頁指派停用並提示"
    )
