"""提交前字串掃描器的規則正確性與全庫零命中（tools/precommit_scan.py，Sprint 114）。

**這支測試守的是紅線，不是風格**。Sprint 97 的紅線違反（真書逐字內容進了 11 個已追蹤
檔案）留下的流程教訓寫在 PLAN §10：「`.gitignore` 只擋檔案層級，擋不住字串層級，同類
洩漏會再發生」。掃描器就是補那一層，本檔則釘死掃描器本身可信：

  1. 規則表每條都指得出紅線出處（無出處的規則＝沒人知道為什麼要守，遲早被刪）
  2. 命中與不命中都要驗（只驗命中會養出一條「什麼都吃」的規則）
  3. **全庫掃描 0 命中**＝清洗後狀態的回歸鎖，未來任何一次提交把金鑰或私有位址寫
     進已追蹤檔案，這條就紅

本檔內的假金鑰與假路徑一律**以字串串接組出**，不寫成完整字面量，否則測試檔自己就
成了掃描器的命中來源（那等於用一條豁免規則換一條測試，紅線反而變鬆）。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import precommit_scan as ps  # noqa: E402

# 假樣本一律串接組出，避免本檔自身成為命中來源（見模組 docstring）
FAKE_KEY = "sk-" + "A" * 32
FAKE_GOOGLE_KEY = "AIza" + "B" * 35
FAKE_GITHUB_TOKEN = "ghp_" + "C" * 36
FAKE_TAILSCALE_HOST = "my-box" + ".ts" + ".net"
FAKE_CGNAT = "100." + "115.94.1"
FAKE_LOCAL_PATH = "C:" + "\\" + "Users" + "\\" + "someone"


# --- 規則表 ---

def test_rules_are_not_empty():
    assert ps.RULES, "規則表為空＝掃描器等於沒開"


def test_every_rule_declares_a_redline_source():
    """每條規則都要寫明守的是哪條紅線（GAPS 編號或 PLAN 段落）。"""
    missing = [r.name for r in ps.RULES if not r.why.strip()]
    assert not missing, f"下列規則沒有紅線出處：{missing}"


def test_rule_names_are_unique():
    names = [r.name for r in ps.RULES]
    assert len(names) == len(set(names))


# --- 命中：金鑰樣式（GAPS #6） ---

def test_detects_openai_style_key(tmp_path):
    hits = ps.scan_text("cfg.py", f'KEY = "{FAKE_KEY}"')
    assert [h.rule for h in hits] == ["key-sk"]


def test_detects_google_and_github_tokens():
    assert [h.rule for h in ps.scan_text("a.py", FAKE_GOOGLE_KEY)] == ["key-google"]
    assert [h.rule for h in ps.scan_text("a.py", FAKE_GITHUB_TOKEN)] == ["key-github"]


def test_key_hit_is_masked_in_report():
    """命中片段不得整串印出，否則掃描報告本身變成第二個外洩管道。"""
    hit = ps.scan_text("cfg.py", FAKE_KEY)[0]
    assert FAKE_KEY not in hit.excerpt
    assert hit.excerpt.startswith("sk-")
    assert "…" in hit.excerpt


# --- 命中：私有 endpoint（GAPS #6） ---

def test_detects_tailscale_magicdns_host():
    assert [h.rule for h in ps.scan_text("d.md", f"http://{FAKE_TAILSCALE_HOST}/v1")] \
        == ["net-tailscale"]


def test_detects_cgnat_address():
    assert [h.rule for h in ps.scan_text("d.md", f"http://{FAKE_CGNAT}:8080/v1")] \
        == ["net-cgnat"]


def test_public_hundred_dot_address_is_not_cgnat():
    """CGNAT 網段（100.64 起算的 /10）以外的 100.x 是公網位址，不該被當私有 endpoint 擋下。

    這行原本寫成完整的網段字面量，被掃描器自己抓出來（規則的說明文字命中規則本身），
    改為描述式寫法。同一類自我命中在掃描器 docstring 也閃過一次，記在 PLAN §10。
    """
    assert ps.scan_text("d.md", "100.200.1.1") == []
    assert ps.scan_text("d.md", "100.63.255.255") == []


def test_version_like_numbers_are_not_cgnat():
    assert ps.scan_text("d.md", "耗時 100.64 秒") == []


# --- 命中：本機路徑（GAPS #63，只掃程式碼） ---

def test_detects_local_user_path_in_python_source():
    assert [h.rule for h in ps.scan_text("tools/x.py", FAKE_LOCAL_PATH)] == ["path-local"]


def test_local_path_rule_does_not_apply_to_documents():
    """GAPS 與 PLAN 記錄本機量測軌跡時會寫到路徑，那是紀錄不是程式碼。"""
    assert ps.scan_text("GAPS.md", FAKE_LOCAL_PATH) == []


def test_local_path_rule_exempts_the_existing_guard_tests():
    """既有兩支守門測試以字面量斷言「路徑不存在」，是紅線的守方不是違方。"""
    assert ps.scan_text("tests/test_long_book_tool.py", FAKE_LOCAL_PATH) == []
    assert ps.scan_text("tests/test_font_naming_license.py", FAKE_LOCAL_PATH) == []


# --- 外置參考書字串清單（GAPS #1，清單本身是版權內容故不入 repo） ---

def test_reference_rule_reports_skipped_when_local_list_absent(tmp_path):
    """本機清單不在時要明說略過，不可沉默當成通過（不沉默降級）。"""
    status = ps.reference_rule_status(tmp_path / "缺席.txt")
    assert status.available is False
    assert "略過" in status.message


def test_reference_rule_loads_local_list(tmp_path):
    p = tmp_path / "reference-strings.txt"
    p.write_text("# 註解行不算\n某段逐字內容\n\n另一段逐字內容\n", encoding="utf-8")
    status = ps.reference_rule_status(p)
    assert status.available is True
    assert status.count == 2
    hits = ps.scan_text("samples/x.md", "前略某段逐字內容後略", extra=status.needles)
    assert [h.rule for h in hits] == ["reference-verbatim"]


def test_reference_needles_are_not_committed():
    """清單檔本身必須在 .gitignore 的 local/ 底下，不得成為已追蹤檔案。"""
    assert ps.REFERENCE_LIST_PATH.relative_to(ROOT).parts[0] == "local"


# --- 全庫零命中（回歸鎖） ---

def test_whole_repo_scan_is_clean():
    """已追蹤檔案掃描 0 命中。這條紅了就是有東西洩漏進版本控制，不是測試壞了。"""
    hits = ps.scan_tracked_files(ROOT)
    detail = "\n".join(f"{h.path}:{h.line}:{h.rule}：{h.excerpt}" for h in hits)
    assert hits == [], "已追蹤檔案命中紅線字串：\n" + detail


# --- hook 安裝物 ---

def test_hook_script_exists_and_calls_the_scanner():
    hook = (ROOT / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "tools/precommit_scan.py" in hook
    assert "--staged" in hook


def test_hook_stays_lf_so_the_shebang_survives_checkout():
    """hook 由 sh 執行，CRLF 會讓 shebang 變 `/bin/sh` 加一個跳脫字元而 bad interpreter。

    本機 `core.autocrlf=true`，沒有 `.gitattributes` 釘住的話，clone 後 hook 直接壞掉，
    而且壞在「每次提交都報錯」而非靜默，仍是形同虛設。
    """
    assert b"\r\n" not in (ROOT / "hooks" / "pre-commit").read_bytes()
    attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "hooks/pre-commit text eol=lf" in attrs


def test_hook_readme_documents_the_install_command():
    doc = (ROOT / "hooks" / "README.md").read_text(encoding="utf-8")
    assert "core.hooksPath" in doc


def test_cli_all_mode_exits_zero_on_clean_repo():
    """對外契約：`--all` 乾淨時 exit 0，供日後 CI 直接接。"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "precommit_scan.py"), "--all"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr
