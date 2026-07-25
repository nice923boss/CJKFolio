"""印前設定層（cjkfolio/press_config.py，Sprint 140）：總墨量上限與 PDF/X 形態預設。

覆蓋：缺檔＝§9 保守預設（320%／X-1a，未設定不擋流程）、round-trip、壞 JSON 與壞
值域明確錯誤、未知鍵容忍（向前相容）、save 建父目錄且不寫出讀不回來的檔。

併驗 max_tac 一路接到 export_pdf 的判定門檻：改上限只動警告，不動寫出的位元
（tac_warnings 是印廠條件的提醒，不是 PDF/X 合規條款）。
"""
import json

import pytest

from cjkfolio.ink import MAX_TAC, InkUse, tac_warnings
from cjkfolio.press_config import (
    MAX_POSSIBLE_TAC,
    PressConfig,
    PressConfigError,
    load_press_config,
    save_press_config,
)


def test_missing_file_gives_section9_defaults(tmp_path):
    """缺檔回 §9 保守預設：320%／X-1a，未設定完全不擋流程。"""
    cfg = load_press_config(tmp_path / "沒有這個檔.json")
    assert cfg == PressConfig(max_tac=320.0, pdfx="x-1a")
    assert cfg.max_tac == MAX_TAC  # 預設值單一事實來源在 ink.MAX_TAC


def test_roundtrip(tmp_path):
    path = tmp_path / "local" / "press-config.local.json"
    cfg = PressConfig(max_tac=340.0, pdfx="x-4")
    save_press_config(cfg, path)  # save 建父目錄
    assert load_press_config(path) == cfg
    assert set(json.loads(path.read_text(encoding="utf-8"))) == {"max_tac", "pdfx"}


def test_malformed_json_raises_clear_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{壞掉", encoding="utf-8")
    with pytest.raises(PressConfigError, match="讀取"):
        load_press_config(p)


def test_unknown_key_tolerated(tmp_path):
    """未知鍵容忍（向前相容）；缺鍵補預設。"""
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"max_tac": 330.0, "未來欄位": 1}), encoding="utf-8")
    assert load_press_config(p) == PressConfig(max_tac=330.0, pdfx="x-1a")


@pytest.mark.parametrize("bad", [0, -5, MAX_POSSIBLE_TAC + 1, "320", None, True])
def test_out_of_range_tac_rejected(tmp_path, bad):
    """0、負值、超過四版全滿 400% 與非數字都擋下（誤填不該沉默生效）。"""
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"max_tac": bad}), encoding="utf-8")
    with pytest.raises(PressConfigError, match="總墨量上限"):
        load_press_config(p)


def test_unknown_pdfx_rejected(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"pdfx": "x-3"}), encoding="utf-8")
    with pytest.raises(PressConfigError, match="PDF/X"):
        load_press_config(p)


def test_save_refuses_unreadable_values(tmp_path):
    """不寫出讀不回來的檔：save 先驗值域再落地。"""
    p = tmp_path / "cfg.json"
    with pytest.raises(PressConfigError):
        save_press_config(PressConfig(max_tac=500.0), p)
    assert not p.exists()


def test_all_three_pdfx_forms_accepted(tmp_path):
    """三種輸出形態都存得下（一般 PDF 也是合法選擇，只是不可送印）。"""
    p = tmp_path / "cfg.json"
    for key in ("x-1a", "x-4", "none"):
        save_press_config(PressConfig(pdfx=key), p)
        assert load_press_config(p).pdfx == key


def test_raising_limit_silences_warning():
    """把上限調到印廠給的數字，原本超標的項就不再報（門檻真的生效）。"""
    uses = (InkUse(kind="影像", label="cover.tif", tac=335.0),)
    assert tac_warnings(uses, 320.0)
    assert tac_warnings(uses, 340.0) == []
