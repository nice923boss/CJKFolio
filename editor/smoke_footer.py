"""smoke C42：書眉與頁碼的改字、挪位置、批次挪位置（Sprint 142）。

Owner 回饋：右下角固定呈現的書名要能改文字、移動位置、批次移動位置，
「避免指派錯誤還可以手動修改」。

離屏可驗：對話框只回真的被改過的欄位（開起來直接按確定＝空 dict＝不佔 undo 步）、
mm↔pt 換算、頁碼元素停用文字欄、mixin 以目前頁的主版為對象、批次一步 undo、
沒有頁腳的主版（封面）據實拒收並指名有書眉的主版。

真視窗的欄位手感與書眉在紙上的視覺位置待 Owner 真視窗（GAPS #19 批次）；
書眉字面與座標真的印進 PDF 由 tests/test_footer_editing.py 以 PyMuPDF 讀回驗。
"""
from cjkfolio.primitives import PT_PER_MM

from editor.footer_panel import FooterItemDialog

TITLE = "running_title"


def check_footer(EditorWindow, doc_path) -> None:
    win = EditorWindow(str(doc_path))
    master_name = win._current_master_name()
    assert master_name == "A-內文版", master_name
    item0 = win.template.masters[master_name].footer[TITLE]

    # ── 對話框：沒動任何欄位就按確定＝空 dict（no-op，不佔 undo 步）──
    dlg = FooterItemDialog(win.template, master_name, parent=win)
    assert dlg.item_name() in win.template.masters[master_name].footer
    while dlg.item_name() != TITLE:   # 選到書名元素（模版宣告序不保證）
        dlg._picker.setCurrentIndex(dlg._picker.currentIndex() + 1)
    assert dlg.values() == {}, dlg.values()
    assert dlg._text.isEnabled(), "書名元素的文字欄應可編輯"
    assert dlg._outer.value() == round(item0.outer_offset_pt / PT_PER_MM, 2), \
        (dlg._outer.value(), item0.outer_offset_pt)

    # 只改文字＝只回文字欄（位置的 mm↔pt 換算誤差不被當成一次變更）
    dlg._text.setText("自擬手記")
    assert dlg.values() == {"text": "自擬手記"}, dlg.values()
    dlg._outer.setValue(dlg._outer.value() + 10.0)   # 再挪 10mm
    vals = dlg.values()
    assert set(vals) == {"text", "outer_offset_pt"}, vals
    assert abs(vals["outer_offset_pt"]
               - (item0.outer_offset_pt + 10.0 * PT_PER_MM)) < 0.05, vals

    # 頁碼元素：文字欄停用（逐頁計算，寫死字面不是「改書眉」而是壞掉的頁碼）
    for i in range(dlg._picker.count()):
        dlg._picker.setCurrentIndex(i)
        if dlg._picker.currentData() == "page_number":
            break
    assert dlg._picker.currentData() == "page_number"
    assert not dlg._text.isEnabled(), "頁碼元素的文字欄應停用"
    dlg._text.setText("寫死的頁碼")
    assert dlg.values() == {}, "停用的文字欄不得產生變更"
    dlg.deleteLater()

    # ── mixin：以目前頁的主版為對象，改字＋挪位置一步 undo ──
    win._footer_dialog(TITLE, {"text": "自擬手記", "outer_offset_pt": 42.0})
    item = win.template.masters[master_name].footer[TITLE]
    assert (item.text, item.outer_offset_pt) == ("自擬手記", 42.0)
    msg = win.statusBar().currentMessage()
    assert "自擬手記" in msg and f"主版 {master_name}" in msg, msg
    assert win.template.masters["E-序文版"].footer[TITLE].outer_offset_pt \
        != 42.0, "未勾批次時不應動到其他主版"
    win.session.undo()
    assert win.template.masters[master_name].footer[TITLE].text is None

    # 空變更：據實提示且不佔 undo 步
    depth = len(win.session._undo)
    win._footer_dialog(TITLE, {})
    assert len(win.session._undo) == depth, "空變更不應推 undo 步"
    assert "書眉無變更" in win.statusBar().currentMessage()

    # 批次：所有含此元素的主版一起挪，仍只推一步 undo
    win._footer_dialog(TITLE, {"outer_offset_pt": 55.0}, all_masters=True)
    assert len(win.session._undo) == depth + 1, "批次仍應只佔一步 undo"
    for name in ("A-內文版", "E-序文版"):
        assert win.template.masters[name].footer[TITLE].outer_offset_pt == 55.0
    assert "所有含此元素的主版" in win.statusBar().currentMessage()
    win.session.undo()
    assert win.template.masters["E-序文版"].footer[TITLE].outer_offset_pt \
        == win.session.template.masters["E-序文版"].footer[TITLE].outer_offset_pt

    # 未知元素：狀態不變並據實說明（不靜默吞）
    before = win.template
    win._footer_dialog("沒有這個書眉", {"outer_offset_pt": 10.0})
    assert win.template is before, "拒收時模版不得變動"
    assert "無法改書眉" in win.statusBar().currentMessage()

    # ── 封面主版沒宣告頁腳：據實拒收並指名有書眉的主版 ──
    from cjkfolio.cover import with_cover

    win.session.replace_document(with_cover(win.doc, win.template))
    win._goto_page(1)
    assert win._current_master_name() == "H-封面", win._current_master_name()
    before = win.template
    win._footer_dialog(TITLE, {"outer_offset_pt": 10.0})
    assert win.template is before
    msg = win.statusBar().currentMessage()
    assert "沒有書眉或頁碼可改" in msg and "A-內文版" in msg, msg

    win._shutdown_thumbnails()
    print(
        "C42 書眉與頁碼：對話框只回改過的欄位（沒動就按確定＝不佔 undo）＋mm↔pt 換算"
        "＋頁碼元素停用文字欄＋mixin 以目前頁主版為對象＋改字與挪位置一步 undo"
        "＋批次套多主版仍只一步＋未知元素與無頁腳主版（封面）據實拒收不改狀態"
    )
