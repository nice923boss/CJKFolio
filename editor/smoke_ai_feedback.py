"""AI 指派的進度與結果回饋離屏煙霧驗證（C45，Sprint 149）。

抽為獨立模組同 smoke_ai 的行數紀律。驗七件事，全部走真實執行緒與真訊號派送：

  (1) 批次進度跨執行緒送回狀態列：跑到一半時進度條與說明已更新（非結束才一次跳完）
  (2) 結束後結果摘要常駐狀態列，校正表頂部摘要列報出批數與建議段數
  (3) 金鑰／端點／模型錯 → 跳「AI 設定有誤」警告框，不開校正表
  (4) 整份沒有任何建議 → 跳警告框說明，不開一張全空的校正表
  (5) 套用時拿掉稿件自帶的手寫目錄，並在狀態列報出拿掉幾段
  (6) AI 設定面板「測試連線」用未儲存的欄位值測，成功綠字、失敗紅字白話且不含金鑰值
  (7) AI 設定面板「輸出上限」預設自動（0），改值存得回設定檔、重開帶入

全程以替身攔在送出前，不外連任何 endpoint、不讀使用者的本機設定。
"""
import contextlib
import tempfile
import threading
from pathlib import Path

from cjkfolio.ai_config import AiConfig, load_ai_config
from cjkfolio.ai_style import AiConfigProblem, SuggestResult
from editor import ai_actions
from editor.ai_assign import AssignReviewDialog
from editor.ai_panel import AiConfigDialog

_FAKE = AiConfig(base_url="http://smoke.test/v1", api_key="smoke-secret", model="m")


@contextlib.contextmanager
def _fake_ai(fake_suggest):
    """真路徑的設定與呼叫層換成替身（不外連）。

    worker 在執行緒裡才解析 suggest_styles 這個名字，替身須撐到執行緒跑完才還原，
    否則會打到真的呼叫層。"""
    real_load, real_suggest = ai_actions.load_ai_config, ai_actions.suggest_styles
    ai_actions.load_ai_config = lambda path: _FAKE
    ai_actions.suggest_styles = fake_suggest
    try:
        yield
    finally:
        ai_actions.load_ai_config, ai_actions.suggest_styles = real_load, real_suggest


def _check_progress_and_summary(EditorWindow, DOC, app) -> None:
    captured = {}
    halfway, release = threading.Event(), threading.Event()

    def staged(texts, candidates, config, *, progress, **kwargs):
        progress(0, 2, "第 1／2 批送出中（段 0〜1）")
        progress(1, 2, "第 2／2 批送出中（段 2〜3）")
        halfway.set()
        release.wait(30)
        progress(2, 2, "2 批全部回應")
        assign = [None] * len(texts)
        assign[2] = "章節小標-黑體"
        return SuggestResult(assignments=tuple(assign), warnings=(), batches=2)

    win = EditorWindow(str(DOC))
    orig_exec = AssignReviewDialog.exec
    AssignReviewDialog.exec = lambda dlg: captured.setdefault("dlg", dlg) or 0
    try:
        with _fake_ai(staged):
            win._run_ai_assign()
            assert halfway.wait(30), "替身未跑到一半"
            app.processEvents()  # 派送已送出的進度訊號（worker 仍卡在半途）
            assert win._ai_bar.isVisibleTo(win) and win._ai_bar.value() == 1 \
                and win._ai_bar.maximum() == 2, "跑到一半時進度條未更新"
            label = win._ai_label.text()
            assert "第 2／2 批送出中" in label and "已 " in label, f"進度說明未更新：{label}"
            release.set()
            win._ai_assign_wait()
    finally:
        release.set()
        AssignReviewDialog.exec = orig_exec
    assert not win._ai_bar.isVisibleTo(win), "結束後進度條未收起"
    assert "AI 指派完成：2 批、1／" in win._ai_label.text(), \
        f"結果摘要未常駐狀態列：{win._ai_label.text()}"
    summary = captured["dlg"]._summary.text()
    assert "AI 共 2 批回應" in summary and "1 段異於現行" in summary, \
        f"校正表摘要列不符：{summary}"


def _check_warning_boxes(EditorWindow, DOC) -> None:
    captured = {}

    def bad_key(texts, candidates, config, **kwargs):
        raise AiConfigProblem("API Key 無效或已過期（HTTP 401）。請到「設定 → AI 設定…」修正")

    def empty(texts, candidates, config, **kwargs):
        return SuggestResult(assignments=(None,) * len(texts),
                             warnings=("批次 1（段 0〜3）AI 指派失敗，維持原樣式：服務暫時無法使用",),
                             batches=1)

    orig_exec = AssignReviewDialog.exec
    AssignReviewDialog.exec = lambda dlg: captured.setdefault("dlg", dlg) or 0
    try:
        for fake, title, keyword in ((bad_key, "AI 設定有誤", "API Key 無效"),
                                     (empty, "AI 沒有回任何建議", "服務暫時無法使用")):
            win = EditorWindow(str(DOC))
            with _fake_ai(fake):
                win._run_ai_assign()
                win._ai_assign_wait()
            box = win._ai_box
            assert box is not None and box.isVisible() and box.windowTitle() == title, \
                f"未跳「{title}」警告框"
            assert keyword in box.text(), f"警告框未說明原因：{box.text()}"
            assert "dlg" not in captured, f"{title} 仍開了校正表"
            assert "smoke-secret" not in box.text() + win._ai_label.text(), "金鑰值外洩"
            box.close()
    finally:
        AssignReviewDialog.exec = orig_exec


def _check_manual_toc_removed(EditorWindow, DOC) -> None:
    """把第 1 段改成目錄條目樣式（模擬稿件自帶的手寫目錄），套用時應被拿掉並報數。"""
    win = EditorWindow(str(DOC))
    second = win.doc.paragraphs[2].text
    err = win._apply_assignments({1: "目錄-篇章條目"}, {2: (second, 2)}, True)
    assert err is None, f"套用失敗：{err}"
    message = win.statusBar().currentMessage()
    assert "移除稿件自帶的手寫目錄 1 段" in message, f"未報手寫目錄移除：{message}"
    assert "已套用" in win._ai_label.text(), "套用結果未常駐狀態列"


def _check_connection_button() -> None:
    seen = []

    def ok(config):
        seen.append(config)
        return f"連線成功：{config.model} 已回應（0.1 秒）"

    def bad(config):
        raise AiConfigProblem("API Key 無效或已過期（HTTP 401）")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ai.json"
        for check, expect, color in ((ok, "連線成功：typed-model", "#060"),
                                     (bad, "API Key 無效", "#b00")):
            dlg = AiConfigDialog(config_path=path, check=check)
            dlg._base_url.setText("http://smoke.test/v1")
            dlg._api_key.setText("smoke-secret")
            dlg._model.setText("typed-model")
            dlg._test.click()
            assert "測試中" in dlg._notice.text() or dlg._check_thread is None, "未顯示測試中"
            dlg._wait_check()
            text = dlg._notice.text()
            assert expect in text and color in dlg._notice.styleSheet(), \
                f"測試結果顯示不符：{text}"
            assert "smoke-secret" not in text, "金鑰值外洩"
            assert dlg._test.isEnabled(), "測試完按鈕未恢復"
        assert not path.exists(), "測試連線不該順手存檔"
    assert seen and seen[0].model == "typed-model", "測試未用面板上目前填的值"


def _check_output_cap_field() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ai.json"
        dlg = AiConfigDialog(config_path=path)
        assert dlg._max_out.value() == 0 and "自動" in dlg._max_out.text(),             f"輸出上限預設不是自動：{dlg._max_out.text()}"
        dlg._max_out.setValue(16000)
        dlg._on_save()
        assert load_ai_config(path).max_output_tokens == 16000, "輸出上限未存進設定檔"
        reopened = AiConfigDialog(config_path=path)  # 留參照：暫存物件會連子元件一起被回收
        assert reopened._max_out.value() == 16000, "重開未帶入輸出上限"


def check_ai_feedback(EditorWindow, DOC, app) -> None:
    """跑 C45 並 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    _check_progress_and_summary(EditorWindow, DOC, app)
    _check_warning_boxes(EditorWindow, DOC)
    _check_manual_toc_removed(EditorWindow, DOC)
    _check_connection_button()
    _check_output_cap_field()
    print(
        "C45 AI 指派進度與回饋：跑到一半進度條 1／2 與說明已更新 → 結束收進度條、"
        "結果摘要常駐狀態列、校正表摘要列報批數 → 金鑰錯跳「AI 設定有誤」不開校正表 → "
        "全無建議跳警告框不開空表 → 套用時移除手寫目錄並報段數 → "
        "測試連線用未存的值、成功綠字失敗紅字且不含金鑰值、不順手存檔 → "
        "輸出上限預設自動、改 16000 存得回設定檔並重開帶入"
    )
