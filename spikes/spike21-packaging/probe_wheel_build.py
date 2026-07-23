"""探針一：現況的 pyproject.toml 建得出 wheel 嗎？建出來的 wheel 裡有什麼？

不改任何產品碼，只把「從未驗證」這件事量成資料。用 --no-isolation 是因為本機
setuptools 82.0.1 已在，隔離建置會另從 PyPI 抓一份建置相依，對本題零資訊量。

用法：
    python spikes/spike21-packaging/probe_wheel_build.py [輸出目錄]

輸出目錄未給時取本檔同層的 out/build（不寫進使用者其他位置）。
"""
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def build_wheel(outdir: Path) -> subprocess.CompletedProcess:
    outdir.mkdir(parents=True, exist_ok=True)
    # 舊 wheel 先清掉：版本號的字典序不等於新舊（0.112.0 排在 0.93.0 前面），
    # 留著就會有人撿到上一輪的產物，量到的是舊行為。
    for stale in outdir.glob("*.whl"):
        stale.unlink()
    return subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation",
         "--outdir", str(outdir)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace")


def describe(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        return sorted(zf.namelist())


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    outdir = Path(argv[0]).resolve() if argv else HERE / "out" / "build"

    proc = build_wheel(outdir)
    print(f"建置指令 exit={proc.returncode}")
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    print("--- 建置輸出（末 25 行）---")
    for line in tail[-25:]:
        print(line)

    wheels = sorted(outdir.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        print("\n結果：未產生任何 wheel。")
        return 1

    wheel = wheels[-1]
    names = describe(wheel)
    print(f"\n產出：{wheel.name}（{wheel.stat().st_size:,} bytes，{len(names)} 個項目）")
    print("--- wheel 內容 ---")
    for name in names:
        print(" ", name)

    for label, needle in (("模版", "templates/"), ("字型資產", "assets/"),
                          ("editor", "editor/"), ("授權全文", "LICENSE")):
        hit = [n for n in names if needle in n]
        print(f"{label}：{'在' if hit else '不在'} wheel 內"
              f"（{len(hit)} 個項目）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
