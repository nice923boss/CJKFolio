"""editor preflight 面板的離屏煙霧驗證（C16〜C18，自 smoke_check 抽出）。

抽出理由：smoke_check.py 逾單檔 800 行上限（同 Sprint 93 pdf_writer → pdf_objects
的處置），本檔為純機械搬移，驗證項與輸出逐字不變。

  C16 preflight 面板三分區（Sprint 87 建立；Sprint 94 擴三分區）
  C17 preflight 背景執行緒與快取（Sprint 100）
  C18 X-4 preflight 與 ICC 選取（Sprint 101）
  C23 字型授權分區（Sprint 112）

由 smoke_check.main() 呼叫，需求的離屏環境（QT_QPA_PLATFORM＝offscreen、
QApplication 已建）由呼叫端備妥。
"""
import tempfile
import threading
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from cjkfolio.editing import DocCursor


def check_preflight(EditorWindow, DOC, ROOT) -> None:
    """跑 C16〜C18 與 C23 並逐項 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    # C16 preflight 面板（Sprint 87 建立；Sprint 94 擴為 X-1a／影像解析度／油墨總量三分區）
    from cjkfolio.preflight import (
        Finding,
        ImageFinding,
        ImageResolutionReport,
        InkCoverageReport,
        InkFinding,
        PreflightReport,
    )
    from editor.preflight_panel import PreflightDialog

    def _run_panel(doc_path):
        """跑一次 preflight 並等背景完成（面板不真開），回傳 (window, report, dialog)。"""
        win = EditorWindow(str(doc_path))
        cap = {}
        orig = PreflightDialog.exec
        PreflightDialog.exec = lambda dlg: cap.setdefault("dlg", dlg) or 0
        try:
            win._run_preflight()
            rep = win._preflight_wait()
        finally:
            PreflightDialog.exec = orig
        return win, rep, cap.get("dlg")

    win16, report16, dlg16 = _run_panel(DOC)
    assert report16 is not None and report16.ok, "preflight 應全數通過"
    assert len(report16.findings) == 12, f"規則數 {len(report16.findings)}（預期 12）"
    assert dlg16.table.rowCount() == 12, "面板表列數非 12"
    assert "全數通過（12/12）" in dlg16.summary_label.text(), "摘要非全數通過"
    assert dlg16.not_covered_label.text().startswith("未涵蓋"), "未涵蓋聲明未顯示"
    assert dlg16.tabs.count() == 4, "面板分頁非四區（X-1a／影像／墨量／字型授權）"
    assert dlg16.tabs.tabText(0).startswith("PDF/X-1a"), "首頁非 X-1a"
    # 無置入圖的樣張：影像區零列且摘要據實說「無置入影像」；墨量區列出內文著色且達標
    assert dlg16.image_table.rowCount() == 0, "無圖樣張影像區不應有列"
    assert "無置入影像" in dlg16.image_summary_label.text(), "影像摘要異常"
    assert dlg16.ink_report.ok and dlg16.ink_table.rowCount() > 0, "墨量區應有達標列"
    assert "皆在上限內" in dlg16.ink_summary_label.text(), "墨量摘要異常"
    assert "preflight：全數通過" in win16.statusBar().currentMessage(), "statusBar 未列結論"
    # 低解析度樣張（wrap-demo 置入 218ppi 佔位圖）：影像區報不足，X-1a 結論仍通過
    win16b, report16b, dlg16b = _run_panel(ROOT / "samples" / "wrap-demo.doc.json")
    assert report16b is not None and report16b.ok, "低解析度不應影響 X-1a 合規"
    assert dlg16b.image_table.rowCount() == 1, "影像區應列一次置入"
    assert dlg16b.image_table.item(0, 0).text() == "不足", "218ppi 應判不足"
    assert "解析度不足" in dlg16b.image_summary_label.text(), "影像摘要未報不足"
    assert "影像解析度：解析度不足" in win16b.statusBar().currentMessage(), \
        "statusBar 未附影像警示"
    # 失敗案例：合成不過報告 → X-1a 紅字摘要與「不過」列；印廠條件兩區各自警示
    bad16 = PreflightReport(path="x", findings=(
        Finding("header-version", True, "1.3"),
        Finding("color-cmyk-only", False, "RGB 殘留")))
    bad_img16 = ImageResolutionReport(path="x", min_ppi=300.0, findings=(
        ImageFinding(page=1, xref=5, px_w=400, px_h=600, draw_w_pt=265.2,
                     draw_h_pt=360.9, ppi=108.6, ok=False),))
    bad_ink16 = InkCoverageReport(path="x", max_tac=320.0, findings=(
        InkFinding(kind="影像", label="obj 7 881×588px", tac=349.5, ok=False),),
        unchecked=("obj 9 無法解碼",))
    bdlg16 = PreflightDialog(bad16, bad_img16, bad_ink16)
    assert "未通過（1/2）" in bdlg16.summary_label.text(), "失敗摘要異常"
    assert bdlg16.table.item(1, 0).text() == "不過", "失敗列狀態非『不過』"
    assert bdlg16.image_table.item(0, 0).text() == "不足", "影像失敗列異常"
    assert bdlg16.ink_table.item(0, 0).text() == "超標", "墨量失敗列異常"
    assert bdlg16.ink_table.item(1, 0).text() == "未判讀", "未判讀列未接於末尾"
    print(
        "C16 preflight 面板三分區：匯出臨時 PDF → X-1a 12/12＋影像解析度＋油墨總量"
        "（無圖樣張『無置入影像』、墨量皆在上限內）→ wrap-demo 218ppi 影像區報不足"
        "而 X-1a 仍 12/12（statusBar 附警示）；合成不過報告三區各列不過／不足／超標與未判讀"
    )

    # C17 preflight 背景執行緒與快取（Sprint 100，關 GAPS #47 (d)）
    import threading

    from editor import preflight_actions as _pa

    main_tid = threading.get_ident()
    calls = []
    real_checks = _pa.run_preflight_checks

    def _spy(*args, **kwargs):
        """包住真檢查（非替身）：記錄實際執行的執行緒與呼叫次數。"""
        calls.append(threading.get_ident())
        return real_checks(*args, **kwargs)

    orig_exec17 = PreflightDialog.exec
    PreflightDialog.exec = lambda dlg: 0
    _pa.run_preflight_checks = _spy
    try:
        win17 = EditorWindow(str(DOC))
        assert win17._run_preflight() is None, "首次應交背景執行緒（不同步回報告）"
        assert "背景執行" in win17.statusBar().currentMessage(), "statusBar 未報背景執行中"
        rep17 = win17._preflight_wait()
        assert rep17 is not None and rep17.ok and len(rep17.findings) == 12, \
            "背景跑出的 X-1a 報告不符（應 12/12）"
        assert len(calls) == 1 and calls[0] != main_tid, \
            f"檢查未跑在非 GUI 執行緒（calls={calls}）"
        # 文件未變 → 二次呼叫走快取：同步回同一份報告，且不再跑一次檢查
        rep17b = win17._run_preflight()
        assert rep17b is rep17, "快取未命中（未回同一份報告物件）"
        assert len(calls) == 1, f"快取命中卻又跑了檢查（calls={len(calls)}）"
        assert "沿用上次結果" in win17.statusBar().currentMessage(), "快取命中未據實聲明"
        # 文件改動 → 快取失效重跑
        win17.session.insert(DocCursor(0, 0), "快取失效測試")
        assert win17._run_preflight() is None, "文件改動後應重跑而非用快取"
        assert win17._preflight_wait() is not None, "重跑未取得報告"
        assert len(calls) == 2, f"文件改動後未重跑檢查（calls={len(calls)}）"
    finally:
        _pa.run_preflight_checks = real_checks
        PreflightDialog.exec = orig_exec17

    # 執行中再觸發不重入（以可控阻塞替身固定時序，判定層本身已由上段真檢查驗過）
    gate = threading.Event()
    entered = threading.Event()
    stub_calls = []

    def _blocking(*args, **kwargs):
        stub_calls.append(1)
        entered.set()
        gate.wait(30)
        return real_checks(*args, **kwargs)

    _pa.run_preflight_checks = _blocking
    PreflightDialog.exec = lambda dlg: 0
    try:
        win17b = EditorWindow(str(DOC))
        win17b._run_preflight()
        assert entered.wait(30), "背景執行緒未進入檢查"
        assert win17b._run_preflight() is None, "執行中再觸發不應回報告"
        assert "進行中" in win17b.statusBar().currentMessage(), "重入未提示進行中"
        assert len(stub_calls) == 1, f"重入起了第二輪檢查（{len(stub_calls)}）"
    finally:
        gate.set()
        win17b._preflight_wait()
        _pa.run_preflight_checks = real_checks
        PreflightDialog.exec = orig_exec17
    print(
        "C17 preflight 背景執行緒與快取：檢查跑於非 GUI 執行緒（tid 相異）→ 同文件"
        "二次呼叫走快取（0 次重跑、statusBar 聲明沿用）→ 插字後快取失效重跑（2 次）"
        "→ 執行中再觸發不重入（提示進行中、不起第二輪）"
    )

    # C18 X-4 preflight 與 ICC 選取（Sprint 101，關 GAPS #47 (a)）
    def _fake_icc(space=b"CMYK", klass=b"prtr"):
        """最小可驗 ICC（同 tests/test_preflight_cache.fake_icc 結構）。"""
        head = bytearray(132)
        head[0:4] = (132).to_bytes(4, "big")
        head[12:16] = klass
        head[16:20] = space
        return bytes(head)

    orig_exec18 = PreflightDialog.exec
    cap18 = {}
    PreflightDialog.exec = lambda dlg: cap18.__setitem__("dlg", dlg) or 0
    with tempfile.TemporaryDirectory() as td18:
        icc_path = Path(td18) / "shop.icc"
        icc_path.write_bytes(_fake_icc())
        try:
            win18 = EditorWindow(str(DOC))
            # 未選 ICC 即觸發 X-4：不執行、不默默改跑 X-1a（檔案對話框回空＝取消）
            orig_dlg = QFileDialog.getOpenFileName
            QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
            try:
                assert win18._run_preflight("x-4") is None, "取消選 ICC 仍執行"
                assert "未選輸出 ICC" in win18.statusBar().currentMessage(), \
                    "取消選 ICC 未據實說明"
                assert win18._preflight_results is None, "取消後不應有報告"
            finally:
                QFileDialog.getOpenFileName = orig_dlg
            # 選取器回傳 ICC → X-4 走完整回路
            QFileDialog.getOpenFileName = staticmethod(
                lambda *a, **k: (str(icc_path), "ICC"))
            try:
                assert win18._run_preflight("x-4") is None, "X-4 首次應交背景執行緒"
                rep18 = win18._preflight_wait()
            finally:
                QFileDialog.getOpenFileName = orig_dlg
            assert rep18 is not None and rep18.ok, \
                f"X-4 未通過：{[f.rule for f in rep18.findings if not f.ok] if rep18 else None}"
            assert len(rep18.findings) == 11, f"X-4 規則數 {len(rep18.findings)}（預期 11）"
            assert {f.rule for f in rep18.findings}.isdisjoint({"no-transparency"}), \
                "X-4 允許透明，不應列 no-transparency"
            assert cap18["dlg"].tabs.tabText(0).startswith("PDF/X-4"), \
                f"面板分頁未標 X-4：{cap18['dlg'].tabs.tabText(0)}"
            assert "PDF/X-4" in cap18["dlg"].windowTitle(), "面板標題未標 X-4"
            assert win18.statusBar().currentMessage().startswith("PDF/X-4 preflight"), \
                "statusBar 未標形態"
            assert win18._preflight_icc == icc_path, "ICC 路徑未留給下次沿用"
            # 形態不互相污染：同文件改跑 X-1a 不得命中 X-4 的快取
            assert win18._run_preflight("x-1a") is None, "X-1a 誤命中 X-4 的快取"
            rep18b = win18._preflight_wait()
            assert rep18b is not None and len(rep18b.findings) == 12, \
                f"X-1a 規則數 {len(rep18b.findings) if rep18b else None}（預期 12）"
        finally:
            PreflightDialog.exec = orig_exec18
    print(
        "C18 X-4 preflight 與 ICC 選取：取消選 ICC 則不執行（不默默降回 X-1a）→ 選取器"
        "回傳 ICC 後背景跑出 X-4 11 規則全過（無 no-transparency）→ 面板標題與分頁標 X-4"
        "＋ICC 留給下次沿用 → 改跑 X-1a 不命中 X-4 快取（重跑得 12 規則）"
    )

    # C23 字型授權分區（Sprint 112，關 GAPS #43 (b)）
    from editor.preflight_panel import license_summary

    assert dlg16.tabs.tabText(3) == "字型授權", "第四分頁非字型授權"
    assert dlg16.license_table.rowCount() == len(dlg16.license_rows) > 0, \
        "字型授權區應逐款列出實際嵌入字型"
    assert all(r[0] == "可散布" for r in dlg16.license_rows), \
        f"內建字型應皆可散布：{dlg16.license_rows}"
    assert "皆可嵌入且宣告可散布" in dlg16.license_summary_label.text(), "授權摘要異常"
    assert "字型授權" not in win16.statusBar().currentMessage(), \
        "內建字型全過時 statusBar 不應附授權警示"
    # 合成未過列：面板據實標示，且 X-1a 結論不因授權而變（非 X 條款）
    warn_rows = (("無宣告", "某商用字型.ttf", "字型未宣告授權（name ID 13／14 皆無）"),
                 ("可散布", "SourceHanSerifTC-Regular.otf", "SIL Open Font License"))
    wdlg = PreflightDialog(report16, dlg16.image_report, dlg16.ink_report,
                           license_rows=warn_rows)
    assert wdlg.license_table.item(0, 0).text() == "無宣告", "未宣告列狀態異常"
    assert "1／2 款須注意" in wdlg.license_summary_label.text(), "混合摘要異常"
    assert "全數通過" in wdlg.summary_label.text(), "授權未過不得改動 X-1a 結論"
    assert license_summary(()) == "無嵌入字型可判讀", "空列摘要未據實說明"
    print(
        "C23 字型授權分區：面板四分頁末頁逐款列出實際嵌入字型（內建 %d 款皆『可散布』，"
        "statusBar 不附警示）；合成『無宣告』列標示須注意 1／2 款，X-1a 結論不受影響"
        % len(dlg16.license_rows)
    )
