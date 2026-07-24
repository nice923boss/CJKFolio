"""安裝形態的檔案佈局鎖（Sprint 119，Spike 21）。

本檔鎖的不是「能不能 import」，而是三件被 Spike 21 量出來會出事的事：

1. **模版找得到**：repo 形態與 wheel 安裝形態的模版目錄解析都要對。
   探針二實測：未修前安裝版指到 `site-packages/templates/`（不存在），
   `import-md` 開箱即死。
2. **wheel 真的裝得到模版**：扁平佈局下 setuptools 不自動發現，套件與資料
   宣告全靠 pyproject 手寫，漏一行就是「裝得起來但少檔案」。
3. **版本號不說謊**：`pyproject.toml` 的 version 與 CHANGELOG 最新版一致
   （GAPS #71 的版本語意，本 Sprint 定案）。

不鎖的事（誠實邊界）：本檔不驗 PyPI 相依解析，也不驗 `editor/`（不是套件）。
"""
import fnmatch
import re
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import cjkfolio.cli as cli
from cjkfolio.template_library import resolve_template_dir

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
MANIFEST = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")


# --- 1. 模版目錄解析 ---------------------------------------------------

def test_repo_form_resolves_templates_at_the_repo_root():
    """repo 形態（套件內無 templates/）→ 取上一層的 templates/，即現行行為。"""
    assert resolve_template_dir(ROOT / "cjkfolio") == ROOT / "templates"


def test_installed_form_prefers_the_copy_inside_the_package(tmp_path):
    """wheel 形態（套件內有 templates/）→ 取套件內那份，不看上一層。

    上一層同時也放一份，確認優先序真的是「套件內優先」而不是碰巧命中。
    """
    pkg = tmp_path / "site-packages" / "cjkfolio"
    (pkg / "templates").mkdir(parents=True)
    (tmp_path / "site-packages" / "templates").mkdir()
    assert resolve_template_dir(pkg) == pkg / "templates"


def test_cli_default_template_actually_exists():
    """CLI 的預設模版是一個真的檔案（未修前在安裝形態是不存在的路徑）。"""
    assert cli.DEFAULT_TEMPLATE.is_file()


# --- 2. wheel 內容宣告 -------------------------------------------------

def test_build_backend_is_declared():
    """沒有 [build-system] 就沒有可複現的建置；backend 釘 setuptools。"""
    build = PYPROJECT["build-system"]
    assert build["build-backend"] == "setuptools.build_meta"
    assert any(r.startswith("setuptools>=") for r in build["requires"])


def test_flat_layout_packages_are_listed_explicitly():
    """扁平佈局下自動發現會失敗，套件清單必須顯式（且不含非套件的 editor）。"""
    packages = PYPROJECT["tool"]["setuptools"]["packages"]
    assert packages == ["cjkfolio", "cjkfolio.templates"]
    assert not any(p.startswith("editor") for p in packages)


def test_every_repo_template_is_carried_into_the_wheel():
    """repo 根每一份模版都要被 package-data 樣式涵蓋，漏一份就是少檔案。"""
    setuptools_cfg = PYPROJECT["tool"]["setuptools"]
    assert setuptools_cfg["package-dir"]["cjkfolio.templates"] == "templates"
    patterns = setuptools_cfg["package-data"]["cjkfolio.templates"]
    on_disk = sorted(p.name for p in (ROOT / "templates").glob("*.json"))
    assert on_disk, "repo 根 templates/ 沒有任何模版，這個鎖就失去意義"
    for name in on_disk:
        assert any(fnmatch.fnmatch(name, pat) for pat in patterns), name


# --- 3. 安裝形態的字型目錄 ---------------------------------------------

def test_render_and_export_pdf_take_a_font_dir(monkeypatch, tmp_path):
    """裝在 site-packages 的那份沒有 assets/fonts，字型目錄必須給得進去。

    探針二實測：修好模版之後 `render` 仍死在 `FontError`，因為 CLI 沒有任何
    途徑指定字型目錄，而字型是使用者資產（二進位不入 repo，見 GAPS #12），
    永遠不會跟著 wheel 走。核心 API（render_document／export_pdf）本就收
    font_dir，缺的只是 CLI 這一段。
    """
    captured = {}

    def fake_render(doc, template, output, **kwargs):
        captured["font_dir"] = kwargs.get("font_dir")
        raise SystemExit(0)

    monkeypatch.setattr(cli, "render_document", fake_render)
    fonts = tmp_path / "字型"
    fonts.mkdir()
    try:
        cli.main(["render", str(ROOT / "samples" / "case-divider.doc.json"),
                  "-o", str(tmp_path / "樣張"), "--font-dir", str(fonts)])
    except SystemExit:
        pass
    assert captured["font_dir"] == str(fonts)


# --- 4. 版本語意 -------------------------------------------------------

# --- 5. sdist 範圍鎖（Sprint 121，Spike 23） ----------------------------
#
# Spike 23 一手實測：setuptools 82 的 sdist 預設會把 tests/*.py 收進去
# （113 個成員中佔 66 個），「預設清單很窄」是文件說法不是實況。
# 範圍由兩層守住：MANIFEST.in 只准縮小（宣告層），加一條真的建出 sdist
# 逐項驗成員的實物鎖（升版 setuptools 換了預設就會在這裡紅）。

def _manifest_directive_lines() -> list[str]:
    """MANIFEST.in 的有效指令行（去註解、去空行、正規化空白）。

    比對一律走本函式而非原文子字串：子字串會把註解掉的指令也算數
    （RED 驗證時抓到的弱點），失去守門意義。
    """
    return [" ".join(line.split()) for line in MANIFEST.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def test_manifest_in_only_narrows():
    """MANIFEST.in 只准出現排除指令，任何 include／graft 都是把散布範圍加寬。"""
    directives = [line.split()[0] for line in _manifest_directive_lines()]
    allowed = {"prune", "exclude", "global-exclude", "recursive-exclude"}
    assert directives, "MANIFEST.in 沒有任何指令，範圍鎖失去意義"
    assert set(directives) <= allowed, f"出現非排除指令：{set(directives) - allowed}"


def test_manifest_in_covers_the_red_line_dirs():
    """紅線目錄（GAPS #1／#6）與 tests 的排除必須逐條在案（只認有效指令行）。"""
    lines = _manifest_directive_lines()
    for required in ("prune local", "prune out", "prune assets",
                     "global-exclude *.pdf", "prune tests"):
        assert required in lines, f"MANIFEST.in 缺有效指令行 `{required}`"


def test_build_requires_nothing_beyond_setuptools():
    """前提鎖：setuptools-scm 一類「git 追蹤即打包」外掛一旦進 build requires，
    sdist 範圍就不再由宣告與 MANIFEST 決定，本檔其餘的鎖全部失效。"""
    requires = PYPROJECT["build-system"]["requires"]
    assert requires and all(r.startswith("setuptools") for r in requires), requires


def test_sdist_contents_stay_within_scope(tmp_path):
    """實物鎖：真的建一份 sdist，逐項驗成員清單。

    紅線 0 命中、tests 不入、該進的（原始碼／模版／LICENSE／PKG-INFO／
    pyproject.toml）全進。--no-isolation 用本機 setuptools，離線可跑。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation",
         "--outdir", str(tmp_path), str(ROOT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr[-2000:]
    sdists = list(tmp_path.glob("*.tar.gz"))
    assert len(sdists) == 1, sdists
    with tarfile.open(sdists[0]) as tar:
        members = [m.name.replace("\\", "/") for m in tar.getmembers() if m.isfile()]

    red_segments = {"local", "out", "assets", ".git", "devlog", "hooks",
                    "tests", "spikes", "tools", "editor", "samples"}
    for name in members:
        assert not (set(name.split("/")) & red_segments), name
        assert "內在整理" not in name, name
        assert not name.lower().endswith(".pdf"), name

    for src in (ROOT / "cjkfolio").glob("*.py"):
        assert any(m.endswith(f"cjkfolio/{src.name}") for m in members), src.name
    for tpl in (ROOT / "templates").glob("*.json"):
        assert any(m.endswith(f"/{tpl.name}") for m in members), tpl.name
    for required in ("LICENSE", "PKG-INFO", "pyproject.toml"):
        assert any(m.split("/")[-1] == required for m in members), required


def test_pyproject_version_matches_the_latest_changelog_entry():
    """版本策略（Sprint 119 定案）：pyproject 的 version＝CHANGELOG 最新版。

    授權盤點是對「某一組版本」成立的（見 pyproject 檔頭），對外宣告的版本號
    若與變更紀錄對不上，複查就沒有錨點。
    """
    latest = re.search(r"^## v(\d+\.\d+\.\d+)", CHANGELOG, re.MULTILINE)
    assert latest, "CHANGELOG 找不到任何 `## vX.Y.Z` 版本標題"
    assert PYPROJECT["project"]["version"] == latest.group(1)
