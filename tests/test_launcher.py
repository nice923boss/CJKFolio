"""啟動編輯器.bat 與手動測試指南的守門（Sprint 122）。

背景：產生 bat 時 Bash heredoc 把 ``\\a`` 摺疊成 BEL（0x07），檔案看似 ASCII
卻讓 cmd 執行 ``python editor\x07pp.py`` 而失敗。本檔把「純 ASCII 可列印＋CRLF＋
路徑正斜線」釘成規則，並以當日真實壞樣本驗證檢查函式本身抓得到（守門測試
自己要過 RED，Sprint 121 教訓）。
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "啟動編輯器.bat"
GUIDE = ROOT / "手動測試指南.md"


def _bat_byte_violations(data: bytes) -> list[str]:
    """回傳 bat 位元組規則違反清單（空清單＝合規）。"""
    problems = []
    printable = set(range(0x20, 0x7F)) | {0x0D, 0x0A}
    bad = sorted({b for b in data if b not in printable})
    if bad:
        problems.append(f"非 ASCII 可列印位元組：{[hex(b) for b in bad]}")
    if b"\n" in data.replace(b"\r\n", b""):
        problems.append("含裸 LF（cmd 需 CRLF）")
    return problems


def test_bat_exists_and_ascii_crlf():
    data = BAT.read_bytes()
    assert _bat_byte_violations(data) == []


def test_bat_calls_editor_app_with_forward_slash():
    data = BAT.read_bytes()
    assert b"editor/app.py" in data, "應以正斜線引用 editor/app.py（反斜線在產生鏈有轉義風險）"
    assert b"editor\\app.py" not in data
    assert b"%*" in data, "應轉發拖放文件參數（b60f6b2 版既有行為）"
    assert b"import PySide6" in data, "應保留 PySide6 預檢（b60f6b2 版既有行為，缺依賴時給安裝指引）"


def test_byte_rule_catches_sprint122_bel_sample():
    # 當日真實壞樣本：\a 被摺疊成 BEL 後 cmd 收到 editor<BEL>pp.py
    broken = b"@echo off\r\npython editor\x07pp.py\r\n"
    assert _bat_byte_violations(broken), "檢查函式應抓到 BEL 損壞"


def test_byte_rule_catches_bare_lf():
    assert _bat_byte_violations(b"@echo off\npython editor/app.py\n")


@pytest.mark.parametrize("path", [BAT, GUIDE])
def test_deliverables_exist(path):
    assert path.exists(), f"{path.name} 應隨 repo 散布"


def test_guide_mentions_launcher_and_no_em_dash():
    text = GUIDE.read_text(encoding="utf-8")
    assert "啟動編輯器.bat" in text
    assert "—" not in text, "使用者可見文字禁用破折號（U+2014，紅線）"
