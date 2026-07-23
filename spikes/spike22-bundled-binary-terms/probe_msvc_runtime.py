"""Spike 22 探針二：shiboken6 夾帶的 Microsoft VC++ 執行期元件（GAPS #74 (f)）。

依 pre-mortem 的對策，本探針把 (f) 拆成三個各自可答的子問，不讓整項卡在
「取不到 Microsoft 條款正文」上：

  子問 1：夾帶的到底是哪幾枚、什麼版本（先釘版本再談條款）
  子問 2：同一組元件是否也隨 Python 自身安裝（判斷是否為平台既有元件）
  子問 3：本機有無 Microsoft 轉散布條款的一手副本

AGPL 的「系統程式庫」例外不在探針內判讀，那一題的一手依據是 repo 根的
LICENSE 全文，見 report.md。

用法：python spikes/spike22-bundled-binary-terms/probe_msvc_runtime.py
"""

from __future__ import annotations

import importlib.metadata as md
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Microsoft VC++ 執行期的檔名特徵。api-ms-win-* 是 Universal CRT 轉發器，
# 屬 Windows 本身元件，與 vc*140* 的散布條件不同源，分開列。
VC_PATTERN = re.compile(r"^(concrt|msvcp|vcruntime|vccorlib|mfc|vcamp|vcomp)\d*.*\.dll$", re.I)
UCRT_PATTERN = re.compile(r"^(api-ms-win-|ucrtbase)", re.I)


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def file_version(path: Path) -> str:
    """讀 Windows 版本資源。取不到就據實回報取不到，不猜。"""
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:  # pragma: no cover - 非 Windows
        return "（非 Windows 平台，無版本資源）"
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return "（無版本資源）"
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
        return "（版本資源讀取失敗）"
    ptr = ctypes.c_void_p()
    length = wintypes.UINT()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
        return "（版本資源無根節點）"
    import struct
    raw = ctypes.string_at(ptr, length.value)
    ms_file, ls_file = struct.unpack_from("<II", raw, 8)
    return f"{ms_file >> 16}.{ms_file & 0xFFFF}.{ls_file >> 16}.{ls_file & 0xFFFF}"


def collect(root: Path) -> tuple[list[Path], list[Path]]:
    vc, ucrt = [], []
    for path in sorted(root.rglob("*.dll")):
        if VC_PATTERN.match(path.name):
            vc.append(path)
        elif UCRT_PATTERN.match(path.name):
            ucrt.append(path)
    return vc, ucrt


def probe_shiboken() -> list[Path]:
    section("1. shiboken6 夾帶的 VC++ 執行期元件")
    dist_root = Path(md.distribution("shiboken6").locate_file("shiboken6"))
    print(f"套件目錄：{dist_root}")
    vc, ucrt = collect(dist_root)
    print(f"\nVC++ 執行期（{len(vc)} 枚）：")
    for p in vc:
        print(f"   {p.name:<24} {p.stat().st_size:>9,} 位元組  檔案版本 {file_version(p)}")
    print(f"\nUniversal CRT 轉發器（{len(ucrt)} 枚）：")
    for p in ucrt:
        print(f"   {p.name}")
    return vc


def probe_python_install(names: set[str]) -> None:
    section("2. 同名元件是否隨 Python 自身安裝（是否為平台既有元件）")
    root = Path(sys.base_prefix)
    print(f"Python 安裝目錄：{root}")
    for name in sorted(names):
        hits = list(root.glob(name)) + list((root / "DLLs").glob(name))
        if hits:
            p = hits[0]
            print(f"   {name:<24} 有　{p}　檔案版本 {file_version(p)}")
        else:
            print(f"   {name:<24} 無")


def probe_system32(names: set[str]) -> None:
    section("3. 同名元件是否已存在於 System32（作業系統既有）")
    root = Path(r"C:\Windows\System32")
    for name in sorted(names):
        p = root / name
        if p.is_file():
            print(f"   {name:<24} 有　檔案版本 {file_version(p)}")
        else:
            print(f"   {name:<24} 無")


def probe_ms_terms() -> None:
    section("4. 本機 Microsoft 轉散布條款一手副本掃描")
    roots = [Path(p) for p in sys.path if p and Path(p).is_dir() and "site-packages" in p]
    roots.append(Path(sys.base_prefix))
    needles = ("distributable code", "redistributable", "microsoft software license terms")
    scanned = 0
    found: list[tuple[Path, str]] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not (name.startswith(("license", "copying", "notice", "eula", "third"))
                    or name.endswith((".txt", ".md", ".rtf"))):
                continue
            if path.stat().st_size > 4_000_000:
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            for needle in needles:
                if needle in text:
                    found.append((path, needle))
                    break
    print(f"掃描檔案數：{scanned}　命中：{len(found)}")
    for path, needle in found:
        print(f"   {path}（命中 {needle!r}）")
    if not found:
        print("   → 本機無 Microsoft 轉散布條款正文，依 pre-mortem 放棄條件如實記錄，不臆測內容")


def probe_our_wheel() -> None:
    section("5. 本專案 wheel 目前有沒有夾帶任何原生二進位")
    import zipfile
    out = Path(__file__).resolve().parents[1] / "spike21-packaging" / "out" / "build"
    wheels = sorted(out.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        print("   （尚未建置 wheel，先跑 spike21-packaging/probe_wheel_build.py）")
        return
    wheel = wheels[-1]
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    binaries = [n for n in names if n.lower().endswith((".dll", ".pyd", ".so", ".exe"))]
    print(f"wheel：{wheel.name}　項目 {len(names)} 筆")
    print(f"原生二進位：{binaries or '無'}")
    print(f"判定：本專案{'有' if binaries else '未'}散布任何原生二進位")


def main() -> int:
    vc = probe_shiboken()
    names = {p.name for p in vc}
    probe_python_install(names)
    probe_system32(names)
    probe_ms_terms()
    probe_our_wheel()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
