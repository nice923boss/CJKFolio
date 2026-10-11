"""AI 設定檔層（Sprint 56，§4.4 LLM 介接）：本機設定檔讀寫與金鑰紅線。

覆蓋：缺檔＝預設空值（未設定不擋流程）、round-trip、壞 JSON／壞欄位明確錯誤、
未知鍵容忍（向前相容）、save 建父目錄。金鑰紅線：預設空值、值不入訊息。
Sprint 143 另加 requests_per_minute（每分鐘送出上限）的型別與範圍守門、
舊設定檔缺鍵補預設 40（非 0＝不節流）。Sprint 149 另加 max_output_tokens
（輸出上限，0＝自動推算）。
"""
import json

import pytest

from cjkfolio.ai_config import AiConfig, AiConfigError, load_ai_config, save_ai_config


def test_missing_file_gives_empty_defaults(tmp_path):
    cfg = load_ai_config(tmp_path / "沒有這個檔.json")
    assert cfg == AiConfig(base_url="", api_key="", model="")


def test_roundtrip(tmp_path):
    path = tmp_path / "local" / "ai-config.local.json"
    cfg = AiConfig(base_url="http://127.0.0.1:8080/v1", api_key="k-本機", model="qwen",
                   requests_per_minute=20, max_output_tokens=12000)
    save_ai_config(cfg, path)  # save 建父目錄
    assert load_ai_config(path) == cfg
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(raw) == {"base_url", "api_key", "model", "requests_per_minute",
                        "max_output_tokens"}


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


def test_legacy_config_without_rate_gets_default_not_zero(tmp_path):
    """Sprint 143 前寫的設定檔沒有這個鍵：補預設 40，不能靜默變成 0＝不節流。"""
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps({"base_url": "http://x/v1", "api_key": "k", "model": "m"}),
                 encoding="utf-8")
    assert load_ai_config(p).requests_per_minute == 40


@pytest.mark.parametrize("value,keyword", [
    ("40", "整數"),      # 字串形態
    (40.0, "整數"),      # 浮點形態
    (True, "整數"),      # 真布林是 int 子類，不能被當成每分鐘 1 次
    (-1, "≥0"),          # 負數無意義
])
def test_bad_rate_raises(tmp_path, value, keyword):
    p = tmp_path / "bad-rate.json"
    p.write_text(json.dumps({"requests_per_minute": value}), encoding="utf-8")
    with pytest.raises(AiConfigError, match=keyword):
        load_ai_config(p)


def test_zero_rate_allowed_means_no_throttle(tmp_path):
    """0＝不節流（無限額的自架 endpoint）；是宣告不是壞值。"""
    p = tmp_path / "zero.json"
    p.write_text(json.dumps({"requests_per_minute": 0}), encoding="utf-8")
    assert load_ai_config(p).requests_per_minute == 0


def test_legacy_config_without_output_cap_gets_auto(tmp_path):
    """Sprint 149 前的設定檔沒有輸出上限：補 0＝自動推算（沿用既有行為）。"""
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps({"model": "m"}), encoding="utf-8")
    assert load_ai_config(p).max_output_tokens == 0


@pytest.mark.parametrize("value,keyword", [("8000", "整數"), (-1, "≥0")])
def test_bad_output_cap_raises(tmp_path, value, keyword):
    p = tmp_path / "bad-cap.json"
    p.write_text(json.dumps({"max_output_tokens": value}), encoding="utf-8")
    with pytest.raises(AiConfigError, match=keyword):
        load_ai_config(p)


def test_error_message_never_contains_secret(tmp_path):
    """金鑰紅線：載入錯誤訊息不得回帶欄位值（避免金鑰入 log）。"""
    p = tmp_path / "leak.json"
    p.write_text(json.dumps({"api_key": ["祕密值"]}), encoding="utf-8")
    with pytest.raises(AiConfigError) as e:
        load_ai_config(p)
    assert "祕密值" not in str(e.value)
