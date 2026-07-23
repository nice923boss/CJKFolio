"""探針二：把 wheel 裝進 venv，刻意在 repo 外的目錄執行 CLI，逐字記下每個錯誤。

關鍵設計：工作目錄一定在 repo 外。`python -m cjkfolio.cli` 會把 cwd 放進
sys.path[0]，若在 repo 根執行，載到的是 repo 裡那份原始碼而不是裝好的那份，
測起來會「全過」但什麼都沒驗到（pre-mortem §3 的假通過）。本探針兩種 cwd 都跑，
把假通過本身也量成資料。

venv 用 --system-site-packages 加 pip install --no-deps：本探針要驗的是本專案
自己的檔案佈局，不是 PyPI 相依解析。此限制寫進報告，不假裝驗過相依解析。

用法：
    python spikes/spike21-packaging/probe_install_run.py [wheel 路徑] [工作根目錄]

wheel 未給時取 out/build 內最新一份；工作根目錄未給時取系統暫存目錄新建一份。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SAMPLE_MD = """# 測試篇章

這是一段用來驗證安裝後行為的內文，不取自任何參考書。

## 測試小節

第二段內文。
"""

DIAG = r"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
import cjkfolio.cli as cli
import cjkfolio.fonts as fonts
print("套件位置：", Path(cli.__file__).parent)
print("預設模版：", cli.DEFAULT_TEMPLATE)
print("預設模版存在：", cli.DEFAULT_TEMPLATE.exists())
print("預設字型目錄：", fonts.DEFAULT_FONT_DIR)
print("預設字型目錄存在：", fonts.DEFAULT_FONT_DIR.exists())
"""


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    # 子行程預設用系統 codepage（本機 CP950）寫 stderr，父行程以 utf-8 讀會拿到
    # 一堆亂碼，錯誤訊息就沒法逐字入報告。強制兩邊都講 utf-8。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def report(label: str, proc: subprocess.CompletedProcess) -> None:
    print(f"\n=== {label} → exit={proc.returncode} ===")
    body = (proc.stdout + proc.stderr).strip()
    lines = body.splitlines()
    for line in lines[-20:]:
        print(" ", line)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    if argv:
        wheel = Path(argv[0]).resolve()
    else:
        # 取最新修改時間那份，不是字典序最後那份（0.112.0 < 0.93.0）。
        wheels = sorted((HERE / "out" / "build").glob("*.whl"),
                        key=lambda p: p.stat().st_mtime)
        if not wheels:
            print("找不到 wheel，請先跑 probe_wheel_build.py")
            return 1
        wheel = wheels[-1]

    base = Path(argv[1]).resolve() if len(argv) > 1 else \
        Path(tempfile.mkdtemp(prefix="cjkfolio-spike21-"))
    venv = base / "venv"
    work = base / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "稿.md").write_text(SAMPLE_MD, encoding="utf-8")

    print(f"wheel：{wheel}")
    print(f"工作根目錄（repo 外）：{base}")

    report("建 venv（--system-site-packages）",
           run([sys.executable, "-m", "venv", "--system-site-packages",
                str(venv)], cwd=base))
    py = venv / "Scripts" / "python.exe"
    if not py.exists():
        py = venv / "bin" / "python"
    report("pip install --no-deps",
           run([str(py), "-m", "pip", "install", "--no-deps", str(wheel)],
               cwd=base))

    report("安裝後的資源錨點（cwd 在 repo 外）",
           run([str(py), "-c", DIAG], cwd=work))
    report("import-md（cwd 在 repo 外）",
           run([str(py), "-m", "cjkfolio.cli", "import-md", "稿.md",
                "-o", "doc.json", "--title", "測試"], cwd=work))
    report("render（cwd 在 repo 外，未給字型目錄）",
           run([str(py), "-m", "cjkfolio.cli", "render", "doc.json",
                "-o", "樣張", "--dpi", "72"], cwd=work))
    fonts = Path(argv[2]).resolve() if len(argv) > 2 else ROOT / "assets" / "fonts"
    report(f"render（cwd 在 repo 外，--font-dir {fonts}）",
           run([str(py), "-m", "cjkfolio.cli", "render", "doc.json",
                "-o", "樣張", "--dpi", "72", "--font-dir", str(fonts)],
               cwd=work))
    report("import-md（cwd 在 repo 根：假通過對照組）",
           run([str(py), "-m", "cjkfolio.cli", "import-md",
                str(work / "稿.md"), "-o", str(work / "doc2.json"),
                "--title", "測試"], cwd=ROOT))

    print(f"\n產物留在：{base}（本探針不自動刪，供覆查）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
