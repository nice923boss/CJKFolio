"""AI 設定檔層（Sprint 56，§4.4 LLM 介接三欄位）：本機設定檔讀寫與金鑰紅線。

覆蓋：缺檔＝預設空值（未設定不擋流程）、round-trip、壞 JSON／壞欄位明確錯誤、
未知鍵容忍（向前相容）、save 建父目錄。金鑰紅線：預設空值、值不入訊息。
"""
import json

import pytest

from cjkfolio.ai_config import AiConfig, AiConfigError, load_ai_config, save_ai_config


def test_missing_file_gives_empty_defaults(tmp_path):
    cfg = load_ai_config(tmp_path / "沒有這個檔.json")
    assert cfg == AiConfig(base_url="", api_key="", model="")


def test_roundtrip(tmp_path):
    path = tmp_path / "local" / "ai-config.local.json"
    cfg = AiConfig(base_url="http://127.0.0.1:8080/v1", api_key="k-本機", model="qwen")
    save_ai_config(cfg, path)  # save 建父目錄
    assert load_ai_config(path) == cfg
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(raw) == {"base_url", "api_key", "model"}


def test_malformed_json_raises_clear_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{壞掉", encoding="utf-8")
    with pytest.raises(AiConfigError, match="讀取"):
        load_ai_config(p)


def test_non_string_field_raises(tmp_path):
    p = tmp_path / "bad-field.json"
    p.write_text(json.dumps({"base_url": 123}), encoding="utf-8")
    with pytest.raises(AiConfigError, match="base_url"):
        load_ai_config(p)


def test_unknown_keys_tolerated_and_partial_fields_default(tmp_path):
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({"model": "qwen", "自訂鍵": True}), encoding="utf-8")
    cfg = load_ai_config(p)
    assert cfg == AiConfig(base_url="", api_key="", model="qwen")


def test_error_message_never_contains_secret(tmp_path):
    """金鑰紅線：載入錯誤訊息不得回帶欄位值（避免金鑰入 log）。"""
    p = tmp_path / "leak.json"
    p.write_text(json.dumps({"api_key": ["祕密值"]}), encoding="utf-8")
    with pytest.raises(AiConfigError) as e:
        load_ai_config(p)
    assert "祕密值" not in str(e.value)
