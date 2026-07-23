"""相依授權稽核：把傳遞相依展開，逐枚回報授權事實（Sprint 118，關 GAPS #55 (e)）。

由來：`THIRD-PARTY-LICENSES.md` 自 Sprint 98 起就寫著兩行限制，「未涵蓋：各套件自身的
傳遞相依未展開稽核」與「未查證：freetype-py 夾帶的 libfreetype.dll」。前者靠本檔補上，
後者靠本檔的「夾帶原生二進位」欄位讓同類遺漏不再靠人眼發現。

本檔做什麼：

  1. 讀 `pyproject.toml` 宣告的相依，用 `importlib.metadata` 展開傳遞相依（marker 依當前
     環境求值、不取任何 extra），得到「這台機器上實際會被 import 的那一組」。
  2. 逐枚讀 dist-info 的授權欄位（`License-Expression` → `License` → `Classifier` 三級
     取用，並記下取自哪一欄，不混為一談）。
  3. 標示與 AGPL-3.0-or-later 的相容性。**這是字串比對層級的標示，不是法律意見**：
     SPDX 識別碼比對已知表，比不到的一律標「須確認」，不猜、不預設通過。
  4. 列出各套件 dist-info 內的授權檔，以及**夾帶的原生二進位**（`.dll`／`.so`／`.dylib`／
     `.pyd`）。夾帶二進位者一律標注「上游條款須另查」：wheel 內的授權檔講的是該 Python
     套件自身的授權，不必然涵蓋它靜態連結或並排夾帶的 C 函式庫（freetype-py 即為實例，
     見 `THIRD-PARTY-LICENSES.md`）。

`REVIEWED` 表以「套件名＋授權字串逐字」為鍵，記錄已人工複核過的非 SPDX 字串。授權字串
一旦改變（升版換授權），鍵就對不上、自動落回「須確認」，這是刻意的漂移鎖。

用法：

    python tools/audit_licenses.py                          # 產品相依
    python tools/audit_licenses.py --include-dev            # 併計開發相依
    python tools/audit_licenses.py --pyproject <路徑>       # 指定其他 pyproject

有任何一枚標示為「不相容」或「須確認」即 exit 1（未查證不當成通過）。
"""
import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import importlib.metadata as md
from packaging.markers import UndefinedEnvironmentName
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]

BIN_SUFFIX = (".dll", ".so", ".dylib", ".pyd")

# 與 AGPL-3.0-or-later 相容的 SPDX 識別碼。理由見 THIRD-PARTY-LICENSES.md
#「為什麼是 AGPL」：寬鬆條款單向併入即可，GPLv3 系與 AGPLv3 §13 互相授權。
COMPATIBLE = frozenset({
    "MIT", "MIT-CMU", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC",
    "PSF-2.0", "Python-2.0", "Zlib", "HPND", "MPL-2.0",
    "AGPL-3.0-only", "AGPL-3.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
    "LGPL-3.0-only", "LGPL-3.0-or-later", "LGPL-2.1-or-later",
})

# 明確不相容。GPL-2.0-only 與 AGPL-3.0 不相容（GPLv2 無 §13 對應條款且不可升版）。
INCOMPATIBLE = frozenset({"GPL-2.0-only", "GPL-2.0"})

# 非開源條款的字樣（本機環境即有 pymupdf-layout 為 Polyform Noncommercial，見 GAPS #55）。
NON_OSS_MARKS = ("noncommercial", "polyform", "proprietary", "all rights reserved")

# 已人工複核的非 SPDX 授權字串。鍵＝（正規化套件名, 授權字串逐字），值＝（判定, 依據）。
REVIEWED = {
    ("pymupdf", "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License"):
        ("相容", "取 AGPL-3.0 臂；本專案授權即由此鎖定，見 THIRD-PARTY-LICENSES.md"),
    ("pyside6", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"):
        ("相容", "取 GPL-3.0-only 臂（Addons 夾帶的 Qt 模組無 LGPL 臂）；GPL-2.0-only 臂明確不選"),
    ("shiboken6", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"):
        ("相容", "同 PySide6，取 GPL-3.0-only 臂"),
    ("pyside6-essentials", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"):
        ("相容", "同 PySide6，取 GPL-3.0-only 臂"),
    ("pyside6-addons", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"):
        ("相容", "同 PySide6，取 GPL-3.0-only 臂"),
    ("uharfbuzz", "Apache License 2.0"):
        ("相容", "Apache-2.0 全名寫法；單向相容 GPLv3 系"),
    ("freetype-py", "License :: OSI Approved :: BSD License"):
        ("相容", "LICENSE.txt 首行明寫 new or revised BSD＝BSD-3-Clause"),
    ("colorama", "License :: OSI Approved :: BSD License"):
        ("相容", "LICENSE.txt 含不得背書條款＝BSD-3-Clause"),
}


@dataclass(frozen=True)
class Dep:
    """一枚已安裝套件的授權事實。"""
    name: str
    version: str
    origin: str            # 直接宣告，或由哪個套件帶進來
    license_text: str      # 逐字，不改寫
    license_source: str    # 取自 dist-info 的哪一欄
    verdict: str           # 相容／不相容／須確認
    why: str
    license_files: tuple
    binaries: tuple


def normalize(name: str) -> str:
    """PEP 503 正規化：大小寫、底線、句點、連字號一律折平。"""
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_requirements(pyproject_text: str, include_dev: bool = False) -> tuple:
    """讀 pyproject 宣告的相依名稱（不含版本限制）。"""
    data = tomllib.loads(pyproject_text)
    project = data.get("project", {})
    specs = list(project.get("dependencies", []))
    if include_dev:
        for group in project.get("optional-dependencies", {}).values():
            specs.extend(group)
    return tuple(dict.fromkeys(Requirement(s).name for s in specs))


def runtime_requirement_names(requires) -> tuple:
    """取 Requires-Dist 中「當前環境、不帶任何 extra」會真正安裝的那些。"""
    out = []
    for spec in requires or []:
        req = Requirement(spec)
        if req.marker is not None:
            try:
                if not req.marker.evaluate({"extra": ""}):
                    continue
            except UndefinedEnvironmentName:      # 只在 extra 情境成立者一律排除
                continue
        out.append(req.name)
    return tuple(dict.fromkeys(out))


def license_facts(metadata) -> tuple:
    """三級取用授權欄位，並回報取自哪一欄（取不到時據實回「無」）。"""
    expr = metadata.get("License-Expression")
    if expr and expr.strip():
        return expr.strip(), "License-Expression"
    legacy = metadata.get("License")
    if legacy and legacy.strip():
        return legacy.strip(), "License"
    classifiers = [c for c in (metadata.get_all("Classifier") or [])
                   if c.startswith("License ::")]
    if classifiers:
        return classifiers[0].strip(), "Classifier"
    return "", "無"


def classify(name: str, license_text: str) -> tuple:
    """標示與 AGPL-3.0-or-later 的相容性。比不到的一律「須確認」。"""
    key = (normalize(name), license_text)
    if key in REVIEWED:
        return REVIEWED[key]
    if not license_text:
        return "須確認", "dist-info 三個授權欄位皆空，須開授權檔人工判讀"
    if license_text in INCOMPATIBLE:
        return "不相容", "與 AGPL-3.0 不相容"
    if license_text in COMPATIBLE:
        return "相容", "SPDX 識別碼在已知相容表內"
    low = license_text.lower()
    if any(mark in low for mark in NON_OSS_MARKS):
        return "不相容", "字樣顯示非開源條款"
    if " OR " in license_text:
        arms = [a.strip() for a in license_text.split(" OR ")]
        picked = [a for a in arms if a in COMPATIBLE]
        if picked:
            return "相容", f"多臂授權，取 {picked[0]} 臂"
    return "須確認", "非已知 SPDX 識別碼，且未經人工複核（見本檔 REVIEWED 表）"


def dist_files(dist) -> tuple:
    """回傳（dist-info 內的授權檔, 夾帶的原生二進位）兩組檔名。"""
    files = [str(f) for f in (dist.files or [])]
    licenses = tuple(f for f in files if "dist-info" in f
                     and any(k in f.upper()
                             for k in ("LICENSE", "COPYING", "NOTICE")))
    binaries = tuple(f for f in files if f.lower().endswith(BIN_SUFFIX))
    return licenses, binaries


def audit(declared: tuple, resolver=md.distribution) -> list:
    """由宣告的相依廣度展開傳遞相依，逐枚回報授權事實。"""
    queue = [(n, "直接宣告") for n in declared]
    seen = set()
    deps = []
    while queue:
        raw, origin = queue.pop(0)
        key = normalize(raw)
        if key in seen:
            continue
        seen.add(key)
        try:
            dist = resolver(raw)
        except md.PackageNotFoundError:
            deps.append(Dep(raw, "未安裝", origin, "", "無", "須確認",
                            "宣告了但本機找不到，無從讀取授權", (), ()))
            continue
        text, source = license_facts(dist.metadata)
        verdict, why = classify(dist.metadata["Name"], text)
        licenses, binaries = dist_files(dist)
        deps.append(Dep(dist.metadata["Name"], dist.version, origin, text, source,
                        verdict, why, licenses, binaries))
        for child in runtime_requirement_names(dist.requires):
            queue.append((child, f"由 {dist.metadata['Name']} 帶入"))
    return deps


def _short(names: tuple, limit: int = 3) -> str:
    heads = [n.rsplit("/", 1)[-1] for n in names[:limit]]
    tail = f" 等 {len(names)} 個" if len(names) > limit else ""
    return ("、".join(heads) + tail) if names else "無"


def report(deps: list) -> int:
    print(f"稽核範圍：{len(deps)} 枚已安裝套件（含傳遞相依）")
    print(f"{'套件':<22}{'版本':<12}{'判定':<8}授權（逐字，取自 dist-info）")
    for d in deps:
        print(f"{d.name:<22}{d.version:<12}{d.verdict:<8}"
              f"{d.license_text or '（空）'}　[{d.license_source}]")

    binaries = [d for d in deps if d.binaries]
    print(f"\n夾帶原生二進位者 {len(binaries)} 枚"
          f"（wheel 內的授權檔未必涵蓋其上游 C 函式庫，須另查）：")
    for d in binaries:
        print(f"  {d.name} {d.version}：二進位 {len(d.binaries)} 個"
              f"（{_short(d.binaries)}）｜授權檔 {_short(d.license_files)}")

    bad = [d for d in deps if d.verdict != "相容"]
    if not bad:
        print(f"\n結果：{len(deps)} 枚全部標示為相容")
        return 0
    print(f"\n結果：{len(bad)} 枚非相容，須處理")
    for d in bad:
        print(f"  {d.name} {d.version}　[{d.verdict}] {d.why}")
        print(f"    來源：{d.origin}｜授權檔：{_short(d.license_files, 5)}")
    return 1


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="相依授權與傳遞相依稽核")
    ap.add_argument("--pyproject", default=str(ROOT / "pyproject.toml"),
                    help="相依宣告來源（預設為本 repo 的 pyproject.toml）")
    ap.add_argument("--include-dev", action="store_true", help="併計開發相依")
    args = ap.parse_args(argv)

    text = Path(args.pyproject).read_text(encoding="utf-8")
    declared = declared_requirements(text, args.include_dev)
    print(f"相依宣告：{args.pyproject}")
    print(f"直接宣告 {len(declared)} 枚："
          f"{'、'.join(declared)}（{'含' if args.include_dev else '不含'}開發相依）")
    return report(audit(declared))


if __name__ == "__main__":
    sys.exit(main())
