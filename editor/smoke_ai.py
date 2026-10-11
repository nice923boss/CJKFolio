"""AI 指派背景執行緒的離屏煙霧驗證（C21，Sprint 104）。

抽為獨立模組同 Sprint 101（smoke_preflight）／102（smoke_images）的行數紀律。
驗四件事，全部繞不過真實執行緒（不以假時序取代）：

  (1) 呼叫確實跑在非 GUI 執行緒，且等待期間主執行緒仍能編輯文件
  (2) 執行中再觸發不重入
  (3) 段落文字在等待期間被改動時，舊建議的段序已不對應 → 不開校正對話框、
      不改任何樣式、statusBar 據實聲明（照索引硬套即沉默錯派）
  (4) 呼叫失敗時 statusBar 據實提示且不 crash
  (5) 不注入替身的真路徑確實讀得到本機設定（Sprint 104 修 load_ai_config 漏傳
      path 的既有缺陷；以間諜攔在送出前，不外連任何 endpoint、不輸出欄位值）

C37（Sprint 135）驗 AI 指派把目次整理出來並標註頁數的整條路徑：對話框目次三欄
帶回建議、人工否決一條、確定後生成目次節、頁碼與獨立重算的內文起始頁相符
（Gate 4：不採信 toc.py 自己填的值）、且整批一步 Ctrl+Z 回原稿。

由 smoke_check.main() 呼叫，需求的離屏環境（QT_QPA_PLATFORM＝offscreen、
QApplication 已建）由呼叫端備妥。
"""
import threading

from PySide6.QtCore import Qt

from cjkfolio.ai_config import AiConfig
from cjkfolio.ai_style import SuggestResult
from cjkfolio.editing import DocCursor
from cjkfolio.primitives import book_number_for
from editor import ai_actions
from editor.ai_assign import AssignReviewDialog
from editor.smoke_ai_feedback import check_ai_feedback


def check_ai_all(EditorWindow, DOC, app) -> None:
    """C21＋C37＋C45 一次跑完（smoke_check 已逼近行數上限，入口收成一行）。"""
    check_ai_assign(EditorWindow, DOC)
    check_ai_toc(EditorWindow, DOC)
    check_ai_feedback(EditorWindow, DOC, app)


def check_ai_assign(EditorWindow, DOC) -> None:
    """跑 C21 並 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    main_tid = threading.get_ident()
    worker_tids = []
    gate = threading.Event()
    captured = {}

    def gated_suggest(texts, candidates):
        """在 worker 裡阻塞到主執行緒放行（固定時序才驗得了「等待期間可編輯」）。"""
        worker_tids.append(threading.get_ident())
        gate.wait(30)
        assign = [None] * len(texts)
        assign[2] = "章節小標-黑體"
        return SuggestResult(assignments=tuple(assign), warnings=(), batches=1)

    def failing_suggest(texts, candidates):
        raise RuntimeError("自擬連線失敗")

    orig_exec = AssignReviewDialog.exec
    AssignReviewDialog.exec = lambda dlg: captured.setdefault("dlg", dlg) or 0
    try:
        win = EditorWindow(str(DOC))
        orig_styles = [p.style for p in win.doc.paragraphs]

        # (1)(2) 背景執行、不重入、等待期間主執行緒可編輯
        win._run_ai_assign(suggest=gated_suggest)
        assert "背景執行" in win.statusBar().currentMessage(), "statusBar 未報背景執行中"
        win._run_ai_assign(suggest=gated_suggest)  # 執行中再觸發
        assert "進行中" in win.statusBar().currentMessage(), "執行中未擋重入"
        win.session.insert(DocCursor(0, 0), "等待期間插字")  # 主執行緒未被凍住
        gate.set()
        win._ai_assign_wait()
        assert len(worker_tids) == 1 and worker_tids[0] != main_tid, \
            f"呼叫未跑在非 GUI 執行緒或發生重入（tids={worker_tids}）"

        # (3) 文字已改動 → 段序失效，不開對話框且不改樣式
        assert "dlg" not in captured, "文字已改動仍開了校正對話框（會錯派）"
        assert "不再對應" in win.statusBar().currentMessage(), "索引失效未據實聲明"
        assert [p.style for p in win.doc.paragraphs] == orig_styles, "未經確認即改派"

        # 守門不誤擋：文件未再變動的一輪照常開對話框並帶回建議
        win._run_ai_assign(suggest=gated_suggest)
        win._ai_assign_wait()
        dlg = captured.get("dlg")
        assert dlg is not None, "文件未變卻未開校正對話框"
        assert dlg._combos[2].currentText() == "章節小標-黑體", "建議未帶進對話框"

        # (4) 呼叫失敗 → 據實提示不 crash（同 CLI assign-styles 誠實失敗語意）
        win._run_ai_assign(suggest=failing_suggest)
        win._ai_assign_wait()
        assert "AI 指派失敗：自擬連線失敗" in win.statusBar().currentMessage(), \
            "失敗未據實提示"

        # (5) 不注入替身的真路徑：走真設定檔載入（Sprint 104 修 load_ai_config
        #     漏傳 path 的既有缺陷），以間諜攔在送出前，不外連任何 endpoint
        seen = []

        def spy_suggest_styles(texts, candidates, config, **kwargs):
            seen.append(config)
            return SuggestResult(assignments=(None,) * len(texts),
                                 warnings=(), batches=1)

        real = ai_actions.suggest_styles
        ai_actions.suggest_styles = spy_suggest_styles
        try:
            win._run_ai_assign()  # suggest=None＝真路徑
            win._ai_assign_wait()
        finally:
            ai_actions.suggest_styles = real
        if seen:  # 本機有設定：真路徑已把設定讀進來並交給呼叫層
            assert isinstance(seen[0], AiConfig), "真路徑未取得 AiConfig"
            assert seen[0].base_url and seen[0].model, "真路徑取到的設定為空"
            note = "真路徑讀本機設定成功（值零輸出）"
        else:  # 本機無設定：據實提示且不擋流程（非 TypeError 崩潰）
            assert "尚未設定 AI" in win.statusBar().currentMessage(), \
                "無設定時未據實提示"
            note = "本機無設定，真路徑據實提示不擋流程"
    finally:
        AssignReviewDialog.exec = orig_exec

    print(
        "C21 AI 指派背景執行緒：呼叫跑於非 GUI 執行緒（tid 相異）＋執行中不重入＋"
        "等待期間主執行緒可編輯 → 段序失效不開對話框、不改樣式並據實聲明 → "
        f"文件未變照常開且帶回建議 → 連線失敗 statusBar 提示不 crash；{note}"
    )


def _first_page_of(layout, para_idx: int):
    """獨立重算：段 para_idx 首次落在哪一版面頁（不看 toc.py 填進去的值）。"""
    for page in layout.pages:
        for pl in page.placed:
            if pl.para_idx == para_idx:
                return page.number
    return None


def check_ai_toc(EditorWindow, DOC) -> None:
    """跑 C37 並 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    captured = {}

    def toc_suggest(texts, candidates):
        """建議 3 條目次條目（層 1 一條＋層 2 兩條）；樣式只動一段以驗兩組採用語意各自獨立。"""
        assign = [None] * len(texts)
        assign[0] = "章節小標-黑體"
        toc = [None] * len(texts)
        toc[1] = (texts[1], 1)
        toc[2] = (texts[2], 2)
        toc[4] = (texts[4], 2)
        return SuggestResult(assignments=tuple(assign), warnings=(), batches=1,
                             toc_entries=tuple(toc))

    orig_exec = AssignReviewDialog.exec
    AssignReviewDialog.exec = lambda dlg: captured.setdefault("dlg", dlg) or 0
    try:
        win = EditorWindow(str(DOC))
        src_paras = win.doc.paragraphs
        n = len(src_paras)
        win._run_ai_assign(suggest=toc_suggest)
        win._ai_assign_wait()
        dlg = captured["dlg"]
    finally:
        AssignReviewDialog.exec = orig_exec

    # (1) 目次三欄帶回建議：標題落格、層級落下拉、採用勾選只勾有建議者
    assert dlg.table.columnCount() == 7, "目次三欄未加上"
    assert dlg.table.item(1, 5).text() == src_paras[1].text, "建議標題未帶進目次欄"
    assert [dlg._levels[i].currentText() for i in (1, 2, 4)] == ["1", "2", "2"], \
        "建議層級未帶進下拉"
    toc_checked = [i for i in range(n)
                   if dlg.table.item(i, 4).checkState() == Qt.CheckState.Checked]
    assert toc_checked == [1, 2, 4], f"目次採用預設勾選不符，得到 {toc_checked}"
    style_checked = [i for i in range(n)
                     if dlg.table.item(i, 0).checkState() == Qt.CheckState.Checked]
    assert style_checked == [0], f"樣式採用與目次採用未各自獨立，得到 {style_checked}"
    assert dlg._generate.isEnabled() and dlg._generate.isChecked(), \
        "模版已宣告 auto_toc 且有條目，生成目次未預設開啟"

    # (2) 人工否決一條後才確定（§4.4 初稿＋人工校正）
    dlg.table.item(4, 4).setCheckState(Qt.CheckState.Unchecked)
    assert set(dlg._toc_entries()) == {1, 2}, "否決後的目次載荷不符"
    dlg._on_confirm()

    # (3) 目次節生成於書首：標題段＋2 條目，內文原樣接在後面
    doc = win.doc
    assert len(doc.paragraphs) == n + 3, f"目次節段數不符（{len(doc.paragraphs)}）"
    assert doc.master == "D-目錄" and doc.paragraphs[0].master == "D-目錄", \
        "目次節未成為書首節"
    assert doc.paragraphs[0].text == "目次", "目次標題段未生成"
    assert [p.text for p in doc.paragraphs[1:3]] == \
        [src_paras[1].text, src_paras[2].text], "目次條目序不符宣告序"
    assert doc.paragraphs[1].page_no is None, \
        "層 1 條目（no_page_levels）被填了頁碼"
    assert doc.paragraphs[3].style == "章節小標-黑體", "樣式改派未同批落地"

    # (4) Gate 4：頁碼與獨立重算的內文起始頁相符（不採信 toc.py 自己填的值）
    layout = win.session.layout
    printed = doc.paragraphs[2].page_no
    expect = book_number_for(_first_page_of(layout, 3 + 2), 1, layout.cover_pages)
    assert printed == str(expect), f"標註頁數 {printed} 不等於獨立重算 {expect}"
    assert "生成目次 2 條" in win.statusBar().currentMessage(), \
        f"狀態列未據實列報生成結果：{win.statusBar().currentMessage()}"

    # (5) 一步 Ctrl+Z 整批回原稿（樣式＋條目宣告＋目次節同屬一步）
    win._on_undo()
    assert win.doc.paragraphs == src_paras, "一步 undo 未整批回原稿"

    print(
        "C37 AI 指派整理目次：建議 3 條帶進目次三欄（標題／層級／採用各自獨立於樣式欄）"
        "→ 人工否決 1 條 → 確定後書首生成目次節（標題段＋2 條目，層 1 依模版不標頁碼）"
        f"＋樣式改派同批落地 → 條目頁數 {printed} 等於獨立重算的內文起始頁 → "
        "一步 Ctrl+Z 整批回原稿"
    )
