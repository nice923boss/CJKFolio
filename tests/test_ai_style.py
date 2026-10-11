"""AI 輔助樣式指派（cjkfolio.ai_style）：建議層與降級防禦（PLAN §4.4）。

基線零網路：transport 一律注入假回應；真 endpoint 驗收屬 CLI R5（不入基線）。
基線零等待：節流與重試的時間全走注入的假時鐘（FakeClock），不呼叫真 time.sleep。
"""
import dataclasses
import json
import urllib.error
from pathlib import Path

import pytest

from cjkfolio.ai_config import AiConfig
from cjkfolio.ai_style import _Pacer, apply_suggestions, suggest_styles
from cjkfolio.document import Document, Paragraph

CONFIG = AiConfig(base_url="http://unit.test/v1", api_key="unit-secret-key", model="m")
CANDIDATES = ("章名大標-明體W7", "章節小標-黑體", "引文-仿宋語錄", "內文-明體直排")
DEFAULT = "內文-明體直排"


def chat_response(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 7}}


def transport_returning(*texts):
    """依呼叫序回傳指定 content 的假 transport；記錄每次請求 body。"""
    calls = []

    def transport(url, headers, body, timeout):
        calls.append((url, headers, json.loads(body.decode("utf-8"))))
        return chat_response(texts[len(calls) - 1])

    transport.calls = calls
    return transport


class FakeClock:
    """假時鐘：sleep 只推進時間並記帳，測試零真實等待（_Pacer 的注入點）。"""

    def __init__(self) -> None:
        self.t = 0.0
        self.slept = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


def fake_pacer(per_minute: int = 0):
    """回 (pacer, clock)：per_minute=0＝只驗重試退避，不摻節流等待。"""
    clock = FakeClock()
    return _Pacer(per_minute, now=clock.now, sleep=clock.sleep), clock


def http_error(code: int, retry_after=None) -> urllib.error.HTTPError:
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    return urllib.error.HTTPError("http://unit.test/v1/chat/completions", code,
                                  "Service Unavailable", headers, None)


def transport_raising(*errors, then=None):
    """前幾次丟指定例外，之後回 then（None＝一直丟最後一個例外）。"""
    calls = []

    def transport(url, headers, body, timeout):
        calls.append(1)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        if then is None:
            raise errors[-1]
        return chat_response(then)

    transport.calls = calls
    return transport


def test_suggest_maps_valid_response():
    t = transport_returning(json.dumps([
        {"index": 0, "style": "章名大標-明體W7"},
        {"index": 1, "style": "內文-明體直排"},
    ]))
    result = suggest_styles(["第一章", "內文段。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == ("章名大標-明體W7", "內文-明體直排")
    assert result.warnings == ()
    assert result.batches == 1


def test_think_shell_stripped():
    t = transport_returning(
        "<think>推理殼\n多行</think>\n[{\"index\": 0, \"style\": \"引文-仿宋語錄\"}]"
    )
    result = suggest_styles(["「語錄。」"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == ("引文-仿宋語錄",)


def test_unknown_style_becomes_none_with_warning():
    t = transport_returning(json.dumps([{"index": 0, "style": "幻覺樣式"}]))
    result = suggest_styles(["段。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == (None,)
    assert any("幻覺樣式" in w for w in result.warnings)


def test_bad_json_degrades_batch_to_none():
    t = transport_returning("完全不是 JSON 的回應")
    result = suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == (None, None)
    assert len(result.warnings) == 1  # 批次降級警告，不沉默


def test_transport_error_degrades_not_raises():
    def broken(url, headers, body, timeout):
        raise urllib.error.URLError("connection refused")

    # 連線失敗屬暫時性，Sprint 143 起會退避重試；注入假時鐘故本測試零等待
    pacer, _ = fake_pacer()
    result = suggest_styles(["甲。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=broken, pacer=pacer)
    assert result.assignments == (None,)
    assert result.warnings


def test_warning_never_contains_api_key():
    def broken(url, headers, body, timeout):
        raise RuntimeError("boom unit-secret-key boom")  # 惡意內嵌金鑰的例外訊息

    result = suggest_styles(["甲。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=broken)
    assert result.warnings
    assert all("unit-secret-key" not in w for w in result.warnings)


def test_batching_by_char_limit_with_global_indexes():
    texts = ["a" * 40, "b" * 40, "c" * 40]
    t = transport_returning(
        json.dumps([{"index": 0, "style": "內文-明體直排"}, {"index": 1, "style": "引文-仿宋語錄"}]),
        json.dumps([{"index": 0, "style": "章節小標-黑體"}]),
    )
    result = suggest_styles(texts, CANDIDATES, CONFIG, default_style=DEFAULT,
                            batch_char_limit=100, transport=t)
    assert result.batches == 2
    assert result.assignments == ("內文-明體直排", "引文-仿宋語錄", "章節小標-黑體")


def test_missing_index_left_none():
    t = transport_returning(json.dumps([{"index": 1, "style": "內文-明體直排"}]))
    result = suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == (None, "內文-明體直排")


def test_prompt_carries_candidates_and_default():
    t = transport_returning(json.dumps([{"index": 0, "style": "內文-明體直排"}]))
    suggest_styles(["段。"], CANDIDATES, CONFIG, default_style=DEFAULT, transport=t)
    body = t.calls[0][2]
    system = body["messages"][0]["content"]
    assert all(c in system for c in CANDIDATES)
    assert DEFAULT in system
    assert body["model"] == "m"
    assert t.calls[0][1]["Authorization"] == "Bearer unit-secret-key"


def test_config_incomplete_fast_fail_without_secret():
    with pytest.raises(ValueError, match="base_url"):
        suggest_styles(["段。"], CANDIDATES,
                       AiConfig(base_url="", api_key="unit-secret-key", model="m"),
                       default_style=DEFAULT, transport=transport_returning("[]"))


def test_apply_suggestions_immutable_and_partial():
    doc = Document(title="t", template="neizai-zhengli", master="A-內文版", paragraphs=(
        Paragraph(text="第一章", style="內文-明體直排"),
        Paragraph(text="內文。", style="內文-明體直排", page_no="12"),
    ))
    out = apply_suggestions(doc, ("章名大標-明體W7", None))
    assert out is not doc
    assert doc.paragraphs[0].style == "內文-明體直排"  # 原件不變
    assert out.paragraphs[0].style == "章名大標-明體W7"
    assert out.paragraphs[1].style == "內文-明體直排"  # None＝維持
    assert out.paragraphs[1].page_no == "12"  # 其他欄位保留


def test_apply_suggestions_length_mismatch_fast_fail():
    doc = Document(title="t", template="x", master="m",
                   paragraphs=(Paragraph(text="甲", style="s"),))
    with pytest.raises(ValueError, match="長度"):
        apply_suggestions(doc, ("s", "s"))


def test_cli_assign_styles_offline(monkeypatch, tmp_path):
    from cjkfolio import ai_style
    from cjkfolio.cli import main
    from cjkfolio.document import load_document, save_document

    doc = Document(title="稿", template="neizai-zhengli", master="A-內文版", paragraphs=(
        Paragraph(text="第一章　留白", style="內文-明體直排"),
        Paragraph(text="內文段落。", style="內文-明體直排"),
    ))
    src = tmp_path / "in.doc.json"
    save_document(doc, src)
    cfg = tmp_path / "ai.json"
    cfg.write_text(json.dumps({"base_url": "http://unit.test/v1",
                               "api_key": "k", "model": "m"}), encoding="utf-8")
    monkeypatch.setattr(ai_style, "_post_json", lambda url, headers, body, timeout:
                        chat_response(json.dumps([
                            {"index": 0, "style": "章名大標-明體W7"},
                            {"index": 1, "style": "內文-明體直排"},
                        ])))
    out = tmp_path / "out.doc.json"
    assert main(["assign-styles", str(src), "-o", str(out), "--config", str(cfg)]) == 0
    result = load_document(out)
    assert result.paragraphs[0].style == "章名大標-明體W7"


def test_cli_assign_styles_no_config_fast_fail(tmp_path):
    from cjkfolio.cli import main
    from cjkfolio.document import save_document

    doc = Document(title="稿", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="甲。", style="內文-明體直排"),))
    src = tmp_path / "in.doc.json"
    save_document(doc, src)
    missing = tmp_path / "none.json"
    assert main(["assign-styles", str(src), "-o", str(tmp_path / "o.json"),
                 "--config", str(missing)]) == 2


# ── 目錄條目建議（Sprint 135）：AI 只認結構，一個頁碼數字都不出 ──────────────

def test_toc_entry_parsed_with_level():
    t = transport_returning(json.dumps([
        {"index": 0, "style": "章名大標-明體W7", "toc_title": "第一章　留白",
         "toc_level": 2},
        {"index": 1, "style": "內文-明體直排"},
    ]))
    result = suggest_styles(["第一章　留白", "內文段。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.toc_entries == (("第一章　留白", 2), None)


def test_toc_level_defaults_to_one():
    t = transport_returning(json.dumps([{"index": 0, "toc_title": " 序 "}]))
    result = suggest_styles(["序"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.toc_entries == (("序", 1),)  # 標題前後空白剝掉


@pytest.mark.parametrize("item,keyword", [
    ({"toc_level": 2}, "toc_level"),                 # 只給層級沒給標題
    ({"toc_title": "  "}, "空"),                      # 全空白標題
    ({"toc_title": "甲", "toc_level": True}, "層級"),  # 真布林是 int 子類，須擋
    ({"toc_title": "甲", "toc_level": 0}, "層級"),
    ({"toc_title": "甲", "toc_level": "2"}, "層級"),
])
def test_bad_toc_entry_degrades_with_warning(item, keyword):
    t = transport_returning(json.dumps([{"index": 0, **item}]))
    result = suggest_styles(["甲。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.toc_entries == (None,)
    assert any(keyword in w for w in result.warnings), result.warnings


def test_toc_entry_survives_unknown_style_and_vice_versa():
    """樣式與目錄條目各自成立：一邊被否掉不連坐另一邊。"""
    t = transport_returning(json.dumps([
        {"index": 0, "style": "幻覺樣式", "toc_title": "後記", "toc_level": 1},
        {"index": 1, "style": "章節小標-黑體", "toc_title": "", "toc_level": 1},
    ]))
    result = suggest_styles(["後記", "小標"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == (None, "章節小標-黑體")
    assert result.toc_entries == (("後記", 1), None)


def test_batch_degrade_drops_style_and_toc_together():
    t = transport_returning("不是 JSON")
    result = suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == (None, None)
    assert result.toc_entries == (None, None)


def test_prompt_asks_for_toc_fields_and_forbids_page_numbers():
    t = transport_returning(json.dumps([{"index": 0, "style": "內文-明體直排"}]))
    suggest_styles(["段。"], CANDIDATES, CONFIG, default_style=DEFAULT, transport=t)
    system = t.calls[0][2]["messages"][0]["content"]
    assert "toc_title" in system and "toc_level" in system
    assert "頁碼" in system  # 明寫頁碼由排版程式算，AI 不得輸出


def test_apply_suggestions_writes_toc_entries_and_keeps_none():
    doc = Document(title="t", template="neizai-zhengli", master="A-內文版", paragraphs=(
        Paragraph(text="第一章", style="內文-明體直排"),
        Paragraph(text="舊條目", style="內文-明體直排", toc_title="舊標", toc_level=3),
    ))
    out = apply_suggestions(doc, (None, None), (("第一章", 1), None))
    assert (out.paragraphs[0].toc_title, out.paragraphs[0].toc_level) == ("第一章", 1)
    # None＝維持原條目宣告（不是清除）
    assert (out.paragraphs[1].toc_title, out.paragraphs[1].toc_level) == ("舊標", 3)
    assert doc.paragraphs[0].toc_title is None  # 原件不變


# ── 送出節流與暫時性失敗重試（Sprint 143）：不超過每分鐘上限，503 不再一次定生死 ──

def test_pacer_holds_at_limit_and_releases_after_window():
    """滿額時等到最舊那筆滿一分鐘才放行；放行後視窗只剩後續的送出。"""
    pacer, clock = fake_pacer(2)
    assert pacer.wait() == 0.0 and pacer.wait() == 0.0  # 前兩次不等
    clock.t = 10.0
    assert pacer.wait() == pytest.approx(50.0)          # 第 3 次等到第 1 次滿 60 秒
    assert clock.slept == [pytest.approx(50.0)]
    assert clock.t == pytest.approx(60.0)
    clock.t = 70.0                                       # 第 2 次（t=0）也過期
    assert pacer.wait() == 0.0


def test_pacer_never_exceeds_limit_in_any_window():
    """Gate 4：以送出時刻獨立重算，任一分鐘內的送出數都不超過上限。"""
    pacer, clock = fake_pacer(40)
    stamps = []
    for _ in range(100):
        pacer.wait()
        stamps.append(clock.t)
        clock.t += 0.1  # 每次請求耗時 0.1 秒
    worst = max(sum(1 for s in stamps if t <= s < t + 60.0) for t in stamps)
    assert worst <= 40, f"某一分鐘視窗內送出 {worst} 次，超過上限"


def test_pacer_zero_means_no_throttle():
    pacer, clock = fake_pacer(0)
    for _ in range(200):
        pacer.wait()
    assert clock.slept == []


def test_503_retried_then_succeeds():
    """Owner 遇到的 503：退避後重送，該批段落不再降級。"""
    t = transport_raising(http_error(503), then=json.dumps(
        [{"index": 0, "style": "章名大標-明體W7"}]))
    pacer, clock = fake_pacer()
    result = suggest_styles(["第一章"], CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=t, pacer=pacer)
    assert result.assignments == ("章名大標-明體W7",)
    assert len(t.calls) == 2
    assert clock.slept == [5.0]                       # 退避 5 秒
    assert len(result.warnings) == 1                  # 重試據實記錄，不沉默
    assert "第 1 次送出失敗" in result.warnings[0]
    assert "5 秒後重試" in result.warnings[0]


def test_503_retry_exhausted_degrades_with_attempt_count():
    t = transport_raising(http_error(503))             # 一直失敗
    pacer, clock = fake_pacer()
    result = suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=t, pacer=pacer)
    assert result.assignments == (None, None)          # 重試用完才降級
    assert len(t.calls) == 4                           # 首送＋重試 3 次
    assert clock.slept == [5.0, 10.0, 20.0]            # 指數退避
    assert "已送出 4 次" in result.warnings[-1]
    assert "維持原樣式" in result.warnings[-1]


def test_retries_count_against_the_rate_limit():
    """重試也佔配額：否則「每分鐘不超過 N 次」會被重試偷偷突破。"""
    pacer, clock = fake_pacer(2)
    sent = []

    def transport(url, headers, body, timeout):
        sent.append(clock.t)   # 記實際送出時刻，不看節流器自己的帳
        raise http_error(503)

    suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                   transport=transport, pacer=pacer)
    assert len(sent) == 4                       # 首送＋重試 3 次
    worst = max(sum(1 for s in sent if t <= s < t + 60.0) for t in sent)
    assert worst <= 2, f"重試突破了節流上限（某一分鐘 {worst} 次）：{sent}"


@pytest.mark.parametrize("code", [400, 422])
def test_permanent_http_status_not_retried(code):
    """請求被拒重試必然重現，重試只是白花配額（401／403／404 另見即停測試）。"""
    t = transport_raising(http_error(code))
    pacer, clock = fake_pacer()
    result = suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=t, pacer=pacer)
    assert len(t.calls) == 1 and clock.slept == []
    assert result.assignments == (None,)
    assert "已送出" not in result.warnings[0]          # 沒重試就不宣稱重試過


def test_bad_response_format_not_retried():
    """回應格式錯屬同一份輸入必然重現，不重試（與連線失敗分開處置）。"""
    t = transport_returning("完全不是 JSON 的回應")
    pacer, clock = fake_pacer()
    result = suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=t, pacer=pacer)
    assert len(t.calls) == 1 and clock.slept == []
    assert result.assignments == (None,)


def test_network_error_retried():
    t = transport_raising(urllib.error.URLError("connection refused"),
                          then=json.dumps([{"index": 0, "style": "內文-明體直排"}]))
    pacer, clock = fake_pacer()
    result = suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=t, pacer=pacer)
    assert result.assignments == ("內文-明體直排",)
    assert clock.slept == [5.0]


@pytest.mark.parametrize("header,expect", [
    ("30", 30.0),          # 伺服器指定秒數，照它的
    ("900", 60.0),         # 過長截到上限（背景執行緒不可無限等）
    ("Wed, 21 Oct 2026 07:28:00 GMT", 5.0),  # HTTP-date 形態不解析，退回指數退避
])
def test_retry_after_header_respected(header, expect):
    t = transport_raising(http_error(429, retry_after=header),
                          then=json.dumps([{"index": 0, "style": "內文-明體直排"}]))
    pacer, clock = fake_pacer()
    suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                   transport=t, pacer=pacer)
    assert clock.slept == [expect]


def test_retry_warning_never_contains_api_key():
    """金鑰紅線同樣蓋住重試記錄（新增的訊息路徑不得成為漏口）。"""
    t = transport_raising(urllib.error.URLError("boom unit-secret-key boom"))
    pacer, _ = fake_pacer()
    result = suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=t, pacer=pacer)
    assert len(result.warnings) == 4                   # 3 筆重試記錄＋1 筆降級
    assert all("unit-secret-key" not in w for w in result.warnings)


def test_config_rate_drives_the_default_pacer(monkeypatch):
    """未注入 pacer 時，節流上限取自設定檔那一欄（不是寫死常數）。"""
    from cjkfolio import ai_style

    built = []
    monkeypatch.setattr(ai_style, "_Pacer",
                        lambda per_minute, **kw: built.append(per_minute) or _Pacer(0))
    suggest_styles(["甲。"], CANDIDATES,
                   dataclasses.replace(CONFIG, requests_per_minute=12),
                   default_style=DEFAULT,
                   transport=transport_returning(json.dumps([])))
    assert built == [12]


def test_prompt_carries_template_declared_toc_levels():
    """模版宣告的層級語意要進 prompt：否則章名會全押第 1 層（該層不標頁碼）。"""
    from cjkfolio.styles import load_template

    template = load_template(
        Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json")
    hints = template.auto_toc.level_hints()
    assert hints == ((1, "目錄-部名", False), (2, "目錄-篇章條目", True))
    t = transport_returning(json.dumps([{"index": 0, "style": "內文-明體直排"}]))
    suggest_styles(["段。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                   transport=t, toc_levels=hints)
    system = t.calls[0][2]["messages"][0]["content"]
    assert "第 1 層＝目錄-部名（不標頁碼）" in system
    assert "第 2 層＝目錄-篇章條目（標頁碼）" in system
    assert "章名一律用第 2 層" in system


# ── 回應長度守門（Sprint 148）：短段多的批次不再整批被截斷報廢 ────────────────

def cut_response(text: str) -> dict:
    """被輸出長度上限截斷的回應（finish_reason=length，如真 endpoint 所回）。"""
    return {"choices": [{"message": {"content": text}, "finish_reason": "length"}]}


def transport_returning_raw(*payloads):
    """依呼叫序回傳整包 payload 的假 transport（要控 finish_reason 時用）。"""
    calls = []

    def transport(url, headers, body, timeout):
        calls.append((url, headers, json.loads(body.decode("utf-8"))))
        return payloads[len(calls) - 1]

    transport.calls = calls
    return transport


def test_batching_also_caps_paragraph_count():
    """短段多的稿件過得了字數關，仍須依段數切批（回應長度隨段數成長）。"""
    from cjkfolio.ai_style import _BATCH_ITEMS, _batches

    texts = ["甲。"] * (_BATCH_ITEMS + 5)          # 合計遠低於預設 3000 字上限
    sizes = [len(bucket) for _start, bucket in _batches(texts, 3000)]
    assert sizes == [_BATCH_ITEMS, 5]
    assert sum(sizes) == len(texts)


def test_max_tokens_scales_with_batch_size():
    """max_tokens 由該批段數推算：段多就給多，不是寫死的 4000。"""
    from cjkfolio.ai_style import _REASONING_RESERVE, _TOKENS_PER_ITEM

    t = transport_returning(json.dumps([]), json.dumps([]))
    suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                   batch_char_limit=3, transport=t)                 # 一段一批
    assert t.calls[0][2]["max_tokens"] == _REASONING_RESERVE + _TOKENS_PER_ITEM
    t2 = transport_returning(json.dumps([]))
    suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                   transport=t2)                                    # 兩段同批
    assert t2.calls[0][2]["max_tokens"] == _REASONING_RESERVE + _TOKENS_PER_ITEM * 2


def test_truncated_response_salvages_finished_items():
    """截斷在陣列中途：已寫完的項照採，只把沒寫到的段單獨重送（Sprint 149）。"""
    t = transport_returning_raw(
        cut_response('[{"index": 0, "style": "章名大標-明體W7"}, '
                     '{"index": 1, "style": "內文-明體直排"}, {"index": 2, "sty'),
        chat_response(json.dumps([{"index": 0, "style": "內文-明體直排"}])))
    result = suggest_styles(["第一章", "內文。", "尾段。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == ("章名大標-明體W7", "內文-明體直排", "內文-明體直排")
    assert t.calls[1][2]["messages"][1]["content"] == "[0] 尾段。"   # 只重送缺的那段
    assert len(result.warnings) == 1
    assert "被輸出長度上限截斷" in result.warnings[0]
    assert "已採用 2／3 項，其餘 1 段拆成 1 小批重送" in result.warnings[0]
    assert result.batches == 1   # 重送不算新批次（摘要的批數＝原計畫批數）


def test_truncation_with_nothing_finished_splits_in_halves():
    """一項都沒寫完：整批對半拆開重送，各半的 index 從 0 起算並對回原段位置。"""
    from cjkfolio.ai_style import _max_tokens

    t = transport_returning_raw(
        cut_response('[{"index": 0, "sty'),
        chat_response(json.dumps([{"index": 0, "style": "章名大標-明體W7"},
                                  {"index": 1, "style": "內文-明體直排"}])),
        chat_response(json.dumps([{"index": 0, "style": "章節小標-黑體"},
                                  {"index": 1, "style": "內文-明體直排"}])))
    notes = []
    result = suggest_styles(["第一章", "甲。", "一、", "乙。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t,
                            progress=lambda done, total, note: notes.append(note))
    assert result.assignments == ("章名大標-明體W7", "內文-明體直排",
                                  "章節小標-黑體", "內文-明體直排")
    assert [c[2]["messages"][1]["content"] for c in t.calls[1:]] == [
        "[0] 第一章\n[1] 甲。", "[0] 一、\n[1] 乙。"]
    assert t.calls[1][2]["max_tokens"] == _max_tokens(2)   # 段少，額度依段數重算
    assert "拆成 2 小批重送" in result.warnings[0]
    assert any("拆小批重送" in n for n in notes), f"進度未報拆批：{notes}"


def test_configured_output_cap_overrides_auto():
    """AI 設定填了輸出上限就照用，不依段數推算（0＝自動）。"""
    t = transport_returning(json.dumps([]))
    suggest_styles(["甲。", "乙。"], CANDIDATES,
                   dataclasses.replace(CONFIG, max_output_tokens=12345),
                   default_style=DEFAULT, transport=t)
    assert t.calls[0][2]["max_tokens"] == 12345


def test_truncated_response_keeps_toc_entries_of_finished_items():
    """搶救到的項若帶目錄欄位，目錄建議一併留下（與樣式同批可信）。"""
    t = transport_returning_raw(
        cut_response('[{"index": 0, "style": "章名大標-明體W7", "toc_title": "第一章　留白", '
                     '"toc_level": 2}, {"index": 1, "sty'),
        cut_response(""))   # 單段重送仍截斷：放棄該段
    result = suggest_styles(["第一章　留白", "內文。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.toc_entries == (("第一章　留白", 2), None)


def test_reasoning_prose_is_not_mistaken_for_json_array():
    """content 空而只剩推理文字時，[16] 這種段號標記不得被當成 JSON 陣列。

    舊式貪婪比對會把 prose 從第一個 [ 吃到最後一個 ]，報出「Extra data」這種
    看不懂的錯；現在一律認「[ 後接 {」，據實回報無陣列並降級該批。
    """
    prose = {"choices": [{
        "message": {"content": "", "reasoning_content":
                    "Paragraph [16] is a subheading. Paragraph [17] is body text."},
        "finish_reason": "length"}]}
    t = transport_returning_raw(prose, prose, prose)   # 拆成兩段單獨重送也都截斷
    result = suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=t)
    assert result.assignments == (None, None)
    assert len(t.calls) == 3
    assert not any("Extra data" in w for w in result.warnings)
    assert "拆成 2 小批重送" in result.warnings[0]
    # 單段仍截斷才放棄，並指出可以去調高輸出上限
    assert len(result.warnings) == 3
    assert all("調高「輸出上限」" in w for w in result.warnings[1:])
