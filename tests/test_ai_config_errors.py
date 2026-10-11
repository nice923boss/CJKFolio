"""Sprint 149：設定錯誤即停、白話錯誤訊息、進度回報、全書標題一覽、測試連線。

全部離線（注入假 transport／假時鐘），零真實網路與等待。
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from cjkfolio.ai_config import AiConfig
from cjkfolio.ai_style import (
    AiConfigProblem, _outline, _Pacer, check_connection, describe_error, suggest_styles,
)

# 循 tests/ 分檔慣例：各檔自帶 helper（與 test_ai_style 同形，不跨檔匯入）
CONFIG = AiConfig(base_url="http://unit.test/v1", api_key="unit-secret-key", model="m")
CANDIDATES = ("章名大標-明體W7", "章節小標-黑體", "內文-明體直排")
DEFAULT = "內文-明體直排"


def chat_response(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def transport_returning(*texts):
    calls = []

    def transport(url, headers, body, timeout):
        calls.append((url, headers, json.loads(body.decode("utf-8"))))
        return chat_response(texts[len(calls) - 1])

    transport.calls = calls
    return transport


def transport_raising(error, then=None):
    """第一次丟 error，之後回 then（None＝一直丟）。"""
    calls = []

    def transport(url, headers, body, timeout):
        calls.append(1)
        if len(calls) == 1 or then is None:
            raise error
        return chat_response(then)

    transport.calls = calls
    return transport


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://unit.test/v1/chat/completions", code,
                                  "Error", {}, None)


def fake_pacer():
    """回 (pacer, 已睡秒數列)：sleep 只記帳不真等。"""
    slept = []
    return _Pacer(0, now=lambda: 0.0, sleep=slept.append), slept


@pytest.mark.parametrize("code, hint", [
    (401, "API Key 無效"), (403, "沒有使用此模型的權限"), (404, "Base URL 與 Model")])
def test_config_error_stops_at_first_batch(code, hint):
    """金鑰／端點／模型錯：第一批就停，不再送後續批次，訊息指出去哪裡改。"""
    t = transport_raising(http_error(code))
    pacer, slept = fake_pacer()
    with pytest.raises(AiConfigProblem) as info:
        suggest_styles(["甲。", "乙。", "丙。"], CANDIDATES, CONFIG,
                       default_style=DEFAULT, transport=t, pacer=pacer,
                       batch_char_limit=2)
    assert len(t.calls) == 1 and slept == []
    message = str(info.value)
    assert hint in message and f"HTTP {code}" in message
    assert "AI 設定" in message and "測試連線" in message


def test_config_error_message_never_contains_api_key():
    err = http_error(401)
    err.detail = "invalid key unit-secret-key"   # 服務端回顯金鑰的最壞情況
    t = transport_raising(err)
    with pytest.raises(AiConfigProblem) as info:
        suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                       transport=t, pacer=fake_pacer()[0])
    assert "unit-secret-key" not in str(info.value)
    assert "invalid key" in str(info.value)


def test_describe_error_plain_language():
    assert "連不上伺服器" in describe_error(urllib.error.URLError("refused"))
    assert describe_error(TimeoutError()) == "等待回應逾時"
    assert "服務暫時無法使用（HTTP 503）" in describe_error(http_error(503))


def test_http_error_body_read_into_detail(monkeypatch):
    """服務端的錯誤說明在回應本體裡，_post_json 要讀出來供白話訊息引用。"""
    from cjkfolio import ai_style

    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b'{"error":"Authentication failed"}'))

    monkeypatch.setattr(ai_style.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError) as info:
        ai_style._post_json("http://unit.test/v1/chat/completions", {}, b"{}", 1)
    assert "Authentication failed" in describe_error(info.value)


def test_progress_reported_per_batch_and_at_end():
    t = transport_returning('[{"index": 0, "style": "內文-明體直排"}]',
                            '[{"index": 0, "style": "內文-明體直排"}]')
    seen = []
    suggest_styles(["甲。", "乙。"], CANDIDATES, CONFIG, default_style=DEFAULT,
                   transport=t, batch_char_limit=2,
                   progress=lambda done, total, note: seen.append((done, total, note)))
    assert [(d, n) for d, n, _ in seen] == [(0, 2), (1, 2), (2, 2)]
    assert "第 1／2 批送出中" in seen[0][2] and "全部回應" in seen[-1][2]


def test_progress_reports_retry_wait():
    t = transport_raising(http_error(503), then='[{"index": 0, "style": "內文-明體直排"}]')
    seen = []
    suggest_styles(["甲。"], CANDIDATES, CONFIG, default_style=DEFAULT, transport=t,
                   pacer=fake_pacer()[0],
                   progress=lambda done, total, note: seen.append(note))
    assert any("重試" in note and "HTTP 503" in note for note in seen)


def test_outline_keeps_short_heading_like_paragraphs_only():
    texts = ["第一章：家鄉", "一、出生", "這是一段很長的內文，" * 5, "短句收尾。", "", "二、上學"]
    assert _outline(texts) == ("第一章：家鄉", "一、出生", "二、上學")


def test_every_batch_prompt_carries_whole_book_outline():
    """分批時每批都看得到全書標題，才能讓同編號格式給同一層級（真稿實測不一致）。"""
    t = transport_returning('[{"index": 0, "style": "內文-明體直排"}]',
                            '[{"index": 0, "style": "內文-明體直排"}]')
    suggest_styles(["一、出生", "二、上學"], CANDIDATES, CONFIG, default_style=DEFAULT,
                   transport=t, batch_char_limit=4)
    assert len(t.calls) == 2
    for _, _, body in t.calls:
        system = body["messages"][0]["content"]
        assert "一、出生／二、上學" in system
        assert "同一個目次層級" in system and "手寫的目錄" in system


def test_check_connection_success():
    t = transport_returning("OK")
    message = check_connection(CONFIG, transport=t)
    assert message.startswith("連線成功：m 已回應")
    _, headers, body = t.calls[0]
    assert body["max_tokens"] == 16 and headers["Authorization"].endswith("unit-secret-key")


def test_check_connection_bad_key_plain_message_without_secret():
    with pytest.raises(AiConfigProblem) as info:
        check_connection(CONFIG, transport=transport_raising(http_error(401)))
    assert "API Key 無效" in str(info.value)
    assert "unit-secret-key" not in str(info.value)


def test_check_connection_rejects_non_chat_response():
    with pytest.raises(AiConfigProblem, match="OpenAI 相容"):
        check_connection(CONFIG, transport=lambda *a: {"data": []})


@pytest.mark.parametrize("field, name", [("base_url", "Base URL"), ("model", "Model")])
def test_check_connection_empty_field_fast_fail(field, name):
    import dataclasses
    with pytest.raises(AiConfigProblem, match=f"{name} 未填"):
        check_connection(dataclasses.replace(CONFIG, **{field: ""}),
                         transport=transport_returning("OK"))


def test_long_paragraph_sent_as_head_excerpt_with_length():
    """長段只送段首並註明全段字數（真稿 docx 長段全文送出把推理額度吃光）。"""
    from cjkfolio.ai_style import _EXCERPT_CHARS
    long_text = "一、求學階段：" + "內文" * 200
    t = transport_returning('[{"index": 0, "style": "內文-明體直排"}, '
                            '{"index": 1, "style": "內文-明體直排"}]')
    suggest_styles(["短段。", long_text], CANDIDATES, CONFIG, default_style=DEFAULT,
                   transport=t)
    user = t.calls[0][2]["messages"][1]["content"]
    assert "[0] 短段。" in user
    assert f"[1] {long_text[:_EXCERPT_CHARS]}……（以下省略，全段 {len(long_text)} 字）" in user
    assert long_text not in user
    assert "段首引題" in t.calls[0][2]["messages"][0]["content"]
