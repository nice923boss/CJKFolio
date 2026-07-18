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

由 smoke_check.main() 呼叫，需求的離屏環境（QT_QPA_PLATFORM＝offscreen、
QApplication 已建）由呼叫端備妥。
"""
import threading

from cjkfolio.ai_config import AiConfig
from cjkfolio.ai_style import SuggestResult
from cjkfolio.editing import DocCursor
from editor import ai_actions
from editor.ai_assign import AssignReviewDialog


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
