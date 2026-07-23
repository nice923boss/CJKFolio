"""Spike 22 探針一：釘死 HarfBuzz 版本、證明靜態連結、找出上游條款一手副本。

方法沿用 Sprint 118（#55 (d) FreeType）定案的「先釘版本再取條款」：
條款陳述必須綁一個查得出來的版本號，且版本號兩路互證。

路徑一：執行期 API `uharfbuzz.version_string`
路徑二：`_harfbuzz.pyd` 內的位元組字串

用法：python spikes/spike22-bundled-binary-terms/probe_harfbuzz.py
"""

from __future__ import annotations

import importlib.metadata as md
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def probe_versions() -> tuple[str, Path]:
    import uharfbuzz as hb

    section("1. 版本兩路互證")
    runtime = hb.version_string
    runtime = runtime() if callable(runtime) else runtime
    pkg_dir = Path(hb.__file__).resolve().parent
    pyd = pkg_dir / "_harfbuzz.pyd"
    blob = pyd.read_bytes()

    print(f"uharfbuzz 發行版本 : {md.version('uharfbuzz')}")
    print(f"路徑一 執行期 API  : uharfbuzz.version_string = {runtime}")

    # HarfBuzz 把版本字串編進二進位；找出所有形如 N.N.N 且與執行期相符者。
    hits = [m.start() for m in re.finditer(runtime.encode("ascii"), blob)]
    print(f"路徑二 二進位字串  : {pyd.name} 內出現 {runtime!r} 共 {len(hits)} 處")
    if hits:
        off = hits[0]
        around = blob[max(0, off - 48) : off + 48]
        print(f"           首處鄰近 : {around!r}")
    print(f"互證結果           : {'一致' if hits else '不一致（需人工判讀）'}")
    return runtime, pyd


def probe_linkage(pyd: Path) -> None:
    """讀 PE 匯入表，確認沒有外部 harfbuzz DLL 相依（即靜態連結）。"""
    section("2. 連結形態（PE 匯入表）")
    blob = pyd.read_bytes()
    # 匯入的 DLL 名稱在 PE 檔中以純 ASCII 出現，直接掃 .dll 結尾的短字串即可，
    # 判定用的是「有沒有 harfbuzz.dll」這個是非題，不需完整 PE 解析。
    names = sorted({m.group(0).decode("ascii").lower()
                    for m in re.finditer(rb"[A-Za-z0-9_\-\.]{1,40}\.dll", blob)})
    print(f"二進位內出現的 DLL 名稱（{len(names)} 枚）：")
    for n in names:
        print("   ", n)
    external_hb = [n for n in names if "harfbuzz" in n]
    print()
    print(f"外部 harfbuzz DLL  : {external_hb or '無'}")
    print(f"判定               : {'動態連結' if external_hb else '靜態連結（HarfBuzz 編進 .pyd）'}")


def probe_shipped_terms() -> None:
    """uharfbuzz 自己隨附了什麼條款。"""
    section("3. uharfbuzz 隨附的條款檔")
    dist = md.distribution("uharfbuzz")
    files = [f for f in (dist.files or []) if "licen" in str(f).lower()]
    for f in files:
        p = Path(dist.locate_file(f))
        text = p.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        print(f"{f}：{len(text)} 字元")
        print(f"   含 'harfbuzz' : {'harfbuzz' in low}")
        print(f"   含 'apache'   : {'apache' in low}")
        print(f"   首行          : {text.splitlines()[0][:70]}")


def probe_local_upstream_copy() -> None:
    """全機掃描：哪裡有 HarfBuzz 上游條款的一手副本。"""
    section("4. 本機 HarfBuzz 條款一手副本掃描")
    roots = [Path(p) for p in sys.path if p and Path(p).is_dir() and "site-packages" in p]
    roots += [Path(sys.prefix)]
    seen: set[Path] = set()
    found: list[tuple[Path, int]] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path in seen:
                continue
            name = path.name.lower()
            if not (name.startswith(("license", "copying", "notice")) or name.endswith((".txt", ".md"))):
                continue
            if path.stat().st_size > 4_000_000:
                continue
            seen.add(path)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "harfbuzz" in text.lower():
                found.append((path, len(text)))
    print(f"掃描檔案數：{len(seen)}　命中 'harfbuzz' 的授權文字檔：{len(found)}")
    for path, size in found:
        print(f"   {path}（{size} 字元）")


def main() -> int:
    runtime, pyd = probe_versions()
    probe_linkage(pyd)
    probe_shipped_terms()
    probe_local_upstream_copy()
    section("結論素材")
    print(f"HarfBuzz 版本：{runtime}")
    print(f"二進位：{pyd}（{pyd.stat().st_size} 位元組）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
