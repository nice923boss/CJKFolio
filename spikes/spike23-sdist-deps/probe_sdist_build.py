"""Spike 23 探針一：sdist／wheel 建置與完整清單紅線掃描（GAPS #75 (d) 的「建得出」半邊）。

回答三個問題：
1. `python -m build --sdist --wheel` 建不建得出（Sprint 119 只跑過 --wheel）。
2. sdist 完整成員清單裡有沒有紅線內容（local/、out/、assets/、內在整理、.git）。
   setuptools 文件說預設清單只含宣告套件＋標準檔案，那是 B 級；本探針親列 A 級。
3. 該進的有沒有進：cjkfolio 全部 .py、templates 全部 .json、LICENSE（AGPL 散布義務）、
   pyproject.toml、PKG-INFO。

用法：python spikes/spike23-sdist-deps/probe_sdist_build.py
產物：spikes/spike23-sdist-deps/out/dist/（gitignore 擋下，不入 repo）
"""
from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out" / "dist"

# 紅線樣式（GAPS #1／#6）：命中任何一筆＝探針失敗。
RED_SEGMENTS = {"local", "out", "assets", ".git", "devlog", "hooks"}
RED_SUBSTRINGS = ("內在整理",)
# 非紅線但不預期入散布物的頂層目錄（進了就要解釋）。
UNEXPECTED_SEGMENTS = {"tests", "spikes", "tools", "editor", "samples", "build"}


def classify(members: list[str]) -> tuple[list[str], list[str]]:
    red, unexpected = [], []
    for name in members:
        segments = set(name.replace("\\", "/").split("/"))
        if segments & RED_SEGMENTS or any(s in name for s in RED_SUBSTRINGS):
            red.append(name)
        elif segments & UNEXPECTED_SEGMENTS:
            unexpected.append(name)
    return red, unexpected


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()

    cmd = [sys.executable, "-m", "build", "--sdist", "--wheel",
           "--outdir", str(OUT), str(ROOT)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(f"build EXIT={proc.returncode}")
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:])
        return 1

    sdists = sorted(OUT.glob("*.tar.gz"))
    wheels = sorted(OUT.glob("*.whl"))
    if len(sdists) != 1 or len(wheels) != 1:
        print(f"預期各一件產物，實得 sdist={sdists} wheel={wheels}")
        return 1

    failures: list[str] = []

    for label, path, members in (
        ("sdist", sdists[0],
         [m.name for m in tarfile.open(sdists[0]).getmembers() if m.isfile()]),
        ("wheel", wheels[0], zipfile.ZipFile(wheels[0]).namelist()),
    ):
        print(f"\n=== {label}: {path.name}（{path.stat().st_size:,} bytes，{len(members)} 個檔案）===")
        for name in sorted(members):
            print(f"  {name}")
        red, unexpected = classify(members)
        print(f"紅線樣式命中：{len(red)} 筆")
        for name in red:
            print(f"  [紅線] {name}")
            failures.append(f"{label} 含紅線成員 {name}")
        print(f"非預期頂層目錄命中：{len(unexpected)} 筆")
        for name in unexpected:
            print(f"  [非預期] {name}")
            failures.append(f"{label} 含非預期成員 {name}")

        # 該進的有沒有進。
        plain = [m.replace("\\", "/") for m in members]
        py_on_disk = sorted(p.name for p in (ROOT / "cjkfolio").glob("*.py"))
        tpl_on_disk = sorted(p.name for p in (ROOT / "templates").glob("*.json"))
        missing_py = [n for n in py_on_disk
                      if not any(m.endswith(f"cjkfolio/{n}") for m in plain)]
        if label == "sdist":
            missing_tpl = [n for n in tpl_on_disk
                           if not any(m.endswith(f"/{n}") for m in plain)]
        else:
            missing_tpl = [n for n in tpl_on_disk
                           if not any(m.endswith(f"cjkfolio/templates/{n}") for m in plain)]
        has_license = any("LICENSE" in m for m in plain)
        has_pkginfo = (label == "wheel") or any(m.endswith("PKG-INFO") for m in plain)
        has_pyproject = (label == "wheel") or any(m.endswith("pyproject.toml") for m in plain)
        print(f"cjkfolio .py 缺漏：{missing_py or '無'}（磁碟上 {len(py_on_disk)} 支）")
        print(f"templates .json 缺漏：{missing_tpl or '無'}（磁碟上 {len(tpl_on_disk)} 份）")
        print(f"LICENSE 在內：{has_license}；PKG-INFO：{has_pkginfo}；pyproject.toml：{has_pyproject}")
        if missing_py:
            failures.append(f"{label} 缺 cjkfolio 原始碼 {missing_py}")
        if missing_tpl:
            failures.append(f"{label} 缺模版 {missing_tpl}")
        if not has_license:
            failures.append(f"{label} 缺 LICENSE（AGPL 散布義務）")

        if label == "wheel":
            binaries = [m for m in plain
                        if m.lower().endswith((".dll", ".pyd", ".so", ".dylib", ".exe"))]
            print(f"wheel 內原生二進位：{len(binaries)} 枚")
            if binaries:
                failures.append(f"wheel 夾帶原生二進位 {binaries}")

    print()
    if failures:
        print("結論：FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("結論：PASS（S1 成立：紅線 0 命中、該進的全進、wheel 零原生二進位）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
