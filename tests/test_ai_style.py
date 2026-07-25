"""AI 輔助樣式指派（cjkfolio.ai_style）：建議層與降級防禦（PLAN §4.4）。

基線零網路：transport 一律注入假回應；真 endpoint 驗收屬 CLI R5（不入基線）。
"""
import json
import urllib.error
from pathlib import Path

import pytest

from cjkfolio.ai_config import AiConfig
from cjkfolio.ai_style import apply_suggestions, suggest_styles
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

    result = suggest_styles(["甲。"], CANDIDATES, CONFIG,
                            default_style=DEFAULT, transport=broken)
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
