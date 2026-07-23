"""相依授權稽核的判定正確性與文件漂移鎖（tools/audit_licenses.py，Sprint 118／120）。

守的是 GAPS #55 (d)(e) 與 #74 (e)(f) 補完後不再退回去：

  1. **判定要保守**：比不到已知 SPDX 識別碼、或人工複核過的字串一旦改變，一律落回
     「須確認」。這條若鬆掉，稽核就成了永遠亮綠燈的裝飾品。
  2. **文件與本機環境一致**：`THIRD-PARTY-LICENSES.md` 寫的 FreeType 與 HarfBuzz 版本必須
     等於執行期實際載入的版本；夾帶原生二進位的產品相依必須逐枚在該文件出現。升版換了
     夾帶內容而沒更新文件，這裡就紅。
  3. **散布前提不被悄悄推翻**（Sprint 120）：#74 (e)(f) 的結論建立在「本專案不散布任何原生
     二進位」與「HarfBuzz 是靜態連結」兩個前提上。哪天 repo 收了 `.dll`、或 uharfbuzz 改成
     動態連結，結論就得重寫，所以兩個前提各有一條測試守著。
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_licenses as al  # noqa: E402

DOC = (ROOT / "THIRD-PARTY-LICENSES.md").read_text(encoding="utf-8")


class FakeMeta(dict):
    """模擬 dist-info metadata：dict 取值加 get_all（多值欄位）。"""

    def __init__(self, mapping=None, classifiers=()):
        super().__init__(mapping or {})
        self._classifiers = list(classifiers)

    def get_all(self, key):
        return self._classifiers if key == "Classifier" else None


class FakeDist:
    def __init__(self, name, version, files=(), meta=None, requires=None):
        self.version = version
        self.files = list(files)
        self.requires = requires
        self.metadata = meta or FakeMeta({"Name": name})


# --- 宣告來源解析 ---

PYPROJECT = """
[project]
name = "demo"
dependencies = ["PyMuPDF>=1.27.2", "pillow>=12.2.0"]

[project.optional-dependencies]
dev = ["pytest>=9.0.2"]
"""


def test_declared_requirements_strips_version_specifiers():
    assert al.declared_requirements(PYPROJECT) == ("PyMuPDF", "pillow")


def test_declared_requirements_can_include_dev():
    assert al.declared_requirements(PYPROJECT, include_dev=True) == (
        "PyMuPDF", "pillow", "pytest")


def test_normalize_follows_pep503():
    assert al.normalize("PySide6_Essentials") == "pyside6-essentials"
    assert al.normalize("freetype.py") == "freetype-py"


# --- 傳遞相依的 marker 求值 ---

def test_extra_only_requirements_are_excluded():
    """extra 的相依不會被安裝，計入等於虛報稽核範圍。"""
    names = al.runtime_requirement_names(
        ["lxml>=4.0; extra == \"lxml\"", "iniconfig>=1.0.1"])
    assert names == ("iniconfig",)


def test_environment_markers_are_evaluated():
    names = al.runtime_requirement_names(
        ["old-thing; python_version < \"3.0\"", "new-thing; python_version >= \"3.0\""])
    assert names == ("new-thing",)


def test_requirements_are_deduplicated_in_order():
    assert al.runtime_requirement_names(["a", "b", "a"]) == ("a", "b")


# --- 授權欄位三級取用 ---

def test_license_expression_wins_over_legacy_field():
    meta = FakeMeta({"License-Expression": "MIT", "License": "BSD-3-Clause"})
    assert al.license_facts(meta) == ("MIT", "License-Expression")


def test_falls_back_to_classifier_when_fields_empty():
    meta = FakeMeta({"License-Expression": "", "License": ""},
                    classifiers=["Programming Language :: Python",
                                 "License :: OSI Approved :: BSD License"])
    assert al.license_facts(meta) == (
        "License :: OSI Approved :: BSD License", "Classifier")


def test_reports_absence_instead_of_guessing():
    assert al.license_facts(FakeMeta()) == ("", "無")


# --- 相容性判定 ---

def test_known_spdx_identifier_is_compatible():
    assert al.classify("demo", "MIT")[0] == "相容"
    assert al.classify("demo", "Apache-2.0")[0] == "相容"


def test_gpl2_only_is_incompatible():
    verdict, why = al.classify("demo", "GPL-2.0-only")
    assert verdict == "不相容" and "AGPL-3.0" in why


def test_noncommercial_wording_is_incompatible():
    """本機環境即有 pymupdf-layout 屬此類（GAPS #55 警惕欄）。"""
    verdict, _ = al.classify(
        "demo", "Dual Licensed - Polyform Noncommercial or Artifex Commercial License")
    assert verdict == "不相容"


def test_unknown_license_string_is_not_assumed_ok():
    verdict, _ = al.classify("demo", "Totally Custom Terms v3")
    assert verdict == "須確認"


def test_empty_license_is_not_assumed_ok():
    assert al.classify("demo", "")[0] == "須確認"


def test_multi_arm_license_picks_a_compatible_arm():
    verdict, why = al.classify("demo", "Apache-2.0 OR BSD-2-Clause")
    assert verdict == "相容" and "Apache-2.0" in why


def test_reviewed_string_is_recognised():
    verdict, why = al.classify(
        "PyMuPDF",
        "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License")
    assert verdict == "相容" and "AGPL-3.0" in why


def test_reviewed_entry_falls_back_when_the_string_drifts():
    """升版換了授權字串就對不上鍵，必須落回須確認（漂移鎖的本體）。"""
    verdict, _ = al.classify(
        "PyMuPDF", "Dual Licensed - GNU GPL 3.0 or Artifex Commercial License")
    assert verdict == "須確認"


# --- 檔案分類 ---

def test_separates_license_files_from_bundled_binaries():
    dist = FakeDist("demo", "1.0", files=[
        "demo-1.0.dist-info/licenses/LICENSE",
        "demo-1.0.dist-info/METADATA",
        "demo/__init__.py",
        "demo/libthing.dll",
        "demo/_speedups.cp312-win_amd64.pyd",
    ])
    licenses, binaries = al.dist_files(dist)
    assert licenses == ("demo-1.0.dist-info/licenses/LICENSE",)
    assert binaries == ("demo/libthing.dll", "demo/_speedups.cp312-win_amd64.pyd")


# --- 展開與回報 ---

def test_audit_expands_transitive_dependencies():
    child = FakeDist("child", "1.0", meta=FakeMeta({"Name": "child",
                                                    "License": "MIT"}))
    parent = FakeDist("parent", "2.0", requires=["child>=1.0"],
                      meta=FakeMeta({"Name": "parent", "License": "MIT"}))
    table = {"parent": parent, "child": child}
    deps = al.audit(("parent",), resolver=lambda n: table[al.normalize(n)])
    assert [d.name for d in deps] == ["parent", "child"]
    assert deps[1].origin == "由 parent 帶入"


def test_missing_distribution_is_reported_not_skipped():
    def resolver(name):
        raise al.md.PackageNotFoundError(name)

    deps = al.audit(("ghost",), resolver=resolver)
    assert deps[0].verdict == "須確認" and deps[0].version == "未安裝"


def test_main_exits_nonzero_when_a_declared_package_is_missing(tmp_path, capsys):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\ndependencies = ["no-such-pkg-xyz"]\n',
                    encoding="utf-8")
    assert al.main(["--pyproject", str(path)]) == 1
    assert "須確認" in capsys.readouterr().out


# --- 本機環境實跑（產品相依） ---

@pytest.fixture(scope="module")
def product_deps():
    declared = al.declared_requirements(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return al.audit(declared)


def test_every_product_dependency_is_compatible(product_deps):
    bad = [(d.name, d.verdict, d.why) for d in product_deps if d.verdict != "相容"]
    assert not bad, f"非相容相依：{bad}"


def test_pyside6_pulls_its_three_subpackages(product_deps):
    names = {al.normalize(d.name) for d in product_deps}
    assert {"shiboken6", "pyside6-essentials", "pyside6-addons"} <= names


def test_tool_runs_from_command_line():
    proc = subprocess.run([sys.executable, "tools/audit_licenses.py"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "夾帶原生二進位者" in proc.stdout


# --- 文件漂移鎖 ---

def test_document_records_the_installed_freetype_version():
    import freetype

    version = ".".join(str(x) for x in freetype.version())
    assert f"FreeType {version}" in DOC, (
        f"本機 libfreetype.dll 為 FreeType {version}，"
        "THIRD-PARTY-LICENSES.md 未記載此版本")


def test_document_records_the_freetype_license_arm():
    for token in ("FTL", "GPLv2", "The FreeType Project"):
        assert token in DOC, f"文件未交代 {token}"


def test_pyproject_comment_no_longer_claims_unverified():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if "freetype-py" in ln)
    assert "未查證" not in line, f"已查證卻仍寫未查證：{line}"


def test_every_binary_bundling_product_dependency_is_documented(product_deps):
    doc_key = al.normalize(DOC)
    missing = [d.name for d in product_deps
               if d.binaries and al.normalize(d.name) not in doc_key]
    assert not missing, f"夾帶原生二進位但文件未提及：{missing}"


# --- 夾帶原生二進位的上游條款（Sprint 120，GAPS #74 (e)(f)） ---

def test_document_records_the_installed_harfbuzz_version():
    """uharfbuzz 升版可能換掉夾帶的 HarfBuzz，條款結論須跟著重查。"""
    import uharfbuzz as hb

    version = hb.version_string
    version = version() if callable(version) else version
    assert f"HarfBuzz {version}" in DOC, (
        f"本機 _harfbuzz.pyd 夾帶 HarfBuzz {version}，"
        "THIRD-PARTY-LICENSES.md 未記載此版本")


def test_document_carries_the_harfbuzz_notice_verbatim():
    """Old MIT 要求聲明出現在所有副本中，故全文必須真的在檔案裡，不是提一句。"""
    for token in (
        "Old MIT",
        "Copyright © 2005,2006,2020,2021,2022,2023  Behdad Esfahbod",
        "above copyright notice and the following two paragraphs appear in",
        "all copies of this software.",
    ):
        assert token in DOC, f"HarfBuzz 條款全文缺片段：{token!r}"


def test_harfbuzz_is_still_statically_linked():
    """靜態連結是「散布 .pyd 即散布 HarfBuzz」這個結論的前提，改動態就得重寫。"""
    import re

    import uharfbuzz as hb

    pyd = Path(hb.__file__).resolve().parent / "_harfbuzz.pyd"
    blob = pyd.read_bytes()
    dlls = {m.group(0).decode("ascii").lower()
            for m in re.finditer(rb"[A-Za-z0-9_\-\.]{1,40}\.dll", blob)}
    external = sorted(d for d in dlls if "harfbuzz" in d)
    assert not external, f"HarfBuzz 改為動態連結（{external}），條款結論須重查"


def test_document_records_the_microsoft_redistribution_conditions():
    """四條限制少一條，安裝檔就可能踩到，故逐條釘死。"""
    for token in (
        "不得更動 Microsoft Distributable Code 中的任何著作權、商標或專利聲明",
        "不得以 Microsoft 商標為程式命名",
        "不得散布 Microsoft Distributable Code 至非 Microsoft 作業系統",
        "不得將 Microsoft Distributable Code 放進惡意、欺騙或非法的程式",
        "System Libraries",
    ):
        assert token in DOC, f"文件未記載轉散布條件：{token!r}"


def test_document_lists_every_msvc_runtime_shiboken_bundles():
    """shiboken6 換一批 DLL 而文件沒跟上，這裡就紅。"""
    import importlib.metadata as md
    import re

    root = Path(md.distribution("shiboken6").locate_file("shiboken6"))
    pattern = re.compile(r"^(concrt|msvcp|vcruntime|vccorlib|mfc|vcamp|vcomp)\d",
                         re.IGNORECASE)
    bundled = sorted({p.name for p in root.rglob("*.dll") if pattern.match(p.name)})
    assert bundled, "shiboken6 不再夾帶 VC++ 執行期，文件結論須重查"
    missing = [name for name in bundled if f"`{name}`" not in DOC]
    assert not missing, f"shiboken6 夾帶但文件未逐枚列出：{missing}"


def test_repo_ships_no_native_binaries():
    """「本專案不是散布者」是 #74 (f) 不觸發的前提，用版本控管清單守住。"""
    proc = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8")
    if proc.returncode != 0:
        pytest.skip("非 git 工作區，無法取得版本控管清單")
    suffixes = (".dll", ".pyd", ".so", ".exe")
    tracked = [ln for ln in proc.stdout.splitlines()
               if ln.lower().endswith(suffixes)]
    assert not tracked, f"repo 收了原生二進位，#74 (f) 的散布前提已變：{tracked}"


def test_pillow_bundles_its_own_freetype_copy_as_documented():
    """Pillow 的 LICENSE 內含另一份 FreeType，版本與 freetype-py 那份不同，文件須記。"""
    import re

    import importlib.metadata as md

    dist = md.distribution("pillow")
    path = next(f for f in dist.files if str(f).upper().endswith("LICENSES/LICENSE"))
    text = Path(dist.locate_file(path)).read_text(encoding="utf-8", errors="replace")
    found = re.findall(r"^=====\s*(freetype-[\d.]+)\s*=====", text, re.M)
    assert found, "Pillow LICENSE 不再列出夾帶的 freetype，稽核結論須重查"
    assert found[0] in DOC, f"Pillow 夾帶 {found[0]}，文件未記載"
