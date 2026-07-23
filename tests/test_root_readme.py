"""根目錄 README 的對外一致性守門（Sprint 115，GAPS #56 丁類第一項）。

README 是開源 repo 的第一份對外文件，也是最容易與程式碼脫節的一份：子命令改名、
檔案搬家、授權改版，沒有一件會讓 README 失敗，只會讓它慢慢變成一份看起來很像真的
說明書。本檔釘死「寫錯會誤導下游」的那幾件事：

  1. 授權宣告與 `pyproject.toml` 一致（授權寫錯的代價不是 bug，是法律風險）
  2. 提到的 CLI 子命令真的存在、提到的 repo 路徑真的在
  3. 快速開始走可散布的公開素材，不是版權參考書（GAPS #1 紅線的對外面）
  4. 誠實範圍仍在（honest-planning R3 的 [Shell] 標記與 R7 的 GAPS 連結）
  5. 不宣稱 `pip install`（`pyproject.toml` 檔頭明記未驗證過安裝後行為）

不釘死字數、段落順序、語氣：那些是編輯自由，不是對外契約。
"""
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import precommit_scan as ps  # noqa: E402

README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"
PUBLIC_SAMPLE = "samples/paiban-xiaoji-ch1.md"


def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def inline_code_tokens(text: str) -> list:
    """取行內反引號片段（README 引用檔案路徑的慣例寫法）。"""
    return re.findall(r"`([^`\n]+)`", text)


def tracked_top_dirs() -> set:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8").stdout
    return {p.split("/")[0] for p in out.splitlines() if "/" in p}


# --- 存在與版控 ---

def test_readme_exists_and_is_tracked():
    assert README.exists(), "開源 repo 沒有根目錄 README＝下游第一眼看不到這是什麼"
    out = subprocess.run(["git", "ls-files", "--error-unmatch", "README.md"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, "README.md 未納入版控"


# --- 授權（GAPS #55） ---

def test_license_claim_matches_pyproject():
    """授權宣告只能有一個事實來源，README 與 pyproject 不一致等於對下游說了兩套話。"""
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["license"]
    assert declared in readme_text(), f"README 未宣告 pyproject 所定的授權：{declared}"


def test_readme_points_at_the_third_party_license_list():
    """AGPL 是被相依鎖死的結果（GAPS #55），成因必須指得到，不能只丟一個授權名。"""
    assert "THIRD-PARTY-LICENSES.md" in readme_text()


def test_readme_does_not_claim_pip_install():
    """`pyproject.toml` 檔頭明記未驗證過安裝後行為，README 不得先於證據宣稱可安裝。"""
    text = readme_text()
    assert not re.search(r"pip\s+install\s+cjkfolio", text), \
        "README 宣稱可 pip install，但該路徑從未驗證過（pyproject.toml 檔頭）"


# --- 與程式碼一致 ---

def test_cli_commands_mentioned_all_exist():
    """README 寫的每個子命令都要真的在 parser 裡（改名時本條會紅）。"""
    helped = subprocess.run([sys.executable, "-m", "cjkfolio.cli", "--help"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert helped.returncode == 0, helped.stdout + helped.stderr
    choices = set(re.search(r"\{([a-z0-9,\-]+)\}", helped.stdout).group(1).split(","))
    mentioned = set(re.findall(r"cjkfolio\.cli\s+([a-z][a-z0-9\-]*)", readme_text()))
    assert mentioned, "README 一個 CLI 用例都沒有"
    assert mentioned <= choices, f"README 提到不存在的子命令：{sorted(mentioned - choices)}"


def test_repo_paths_mentioned_all_exist():
    """行內反引號裡的 repo 路徑都要存在（檔案搬家時本條會紅）。"""
    dirs = tracked_top_dirs()
    missing = []
    for token in inline_code_tokens(readme_text()):
        head = token.split("/")[0]
        if "/" not in token or head not in dirs:
            continue
        if not (ROOT / token).exists():
            missing.append(token)
    assert not missing, f"README 提到不存在的路徑：{missing}"


def test_readme_documents_the_real_baseline_commands():
    """驗證方式寫在 README 就得是真的那一組，否則貢獻者跑的不是專案在跑的。"""
    cfg = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    text = readme_text()
    for path in cfg["tool"]["pytest"]["ini_options"]["testpaths"]:
        assert path in text, f"README 未列基線測試路徑 {path}"
    assert "editor/smoke_check.py" in text, "README 未列 GUI 側的離屏煙霧驗證"


# --- 紅線與誠實範圍 ---

def test_quickstart_uses_the_public_sample_not_the_reference_book():
    """GAPS #1：參考書是版權物僅限本機，對外的重現路徑只能走自撰公開素材。"""
    text = readme_text()
    assert PUBLIC_SAMPLE in text, "README 的重現路徑未使用可散布的公開素材"
    assert not re.search(r"內在整理-\d+\.pdf", text), \
        "README 指向本機參考書 PDF，該檔為版權物不隨 repo 散布"


def test_readme_declares_shell_scope_and_links_gaps():
    """R3 與 R7 的對外面：外人要看得到哪些是空殼、缺口登記在哪。"""
    text = readme_text()
    assert "[Shell]" in text, "README 未標出空殼項目（honest-planning R3）"
    assert "GAPS.md" in text, "README 未指向落差登記簿（honest-planning R7）"


def test_readme_has_no_em_dash():
    """繁中標點紅線：破折號一律不用（逗號、冒號、括號替代）。"""
    assert "—" not in readme_text()


def test_readme_passes_the_redline_scanner():
    """README 是對外文件，金鑰與私有位址寫進去的後果比寫進 devlog 更直接。"""
    hits = ps.scan_text("README.md", readme_text())
    assert hits == [], [f"{h.line}:{h.rule}：{h.excerpt}" for h in hits]
