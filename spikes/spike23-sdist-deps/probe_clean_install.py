"""Spike 23 探針二：乾淨 venv 相依解析與 repo 外 CLI 全鏈（GAPS #75 (a)＋(d) 的「裝得起來」半邊）。

Spike 21 的兩個刻意隔離在此解除：venv 不帶 --system-site-packages、pip 不帶 --no-deps，
「pip 會不會把六枚產品相依裝好」第一次被實測。CLI 一律在 repo 外執行
（Spike 21 教訓：repo 內測安裝版，`python -m` 會載到 repo 那份原始碼，等於沒測）。

用法：
  python spikes/spike23-sdist-deps/probe_clean_install.py <artifact(.whl|.tar.gz)> \
      [--cli-chain --sample <md> --font-dir <dir>]

venv 與工作目錄建在系統 temp（執行期推導，原始碼不含本機路徑），跑完保留供
Gate 4 獨立複驗與 R5 親驗，路徑印在結尾；清理由呼叫端自行 rmtree。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(label: str, cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=cwd)
    secs = time.perf_counter() - start
    print(f"[{label}] EXIT={proc.returncode}（{secs:.1f}s）")
    return proc


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact")
    ap.add_argument("--cli-chain", action="store_true")
    ap.add_argument("--sample")
    ap.add_argument("--font-dir")
    args = ap.parse_args()

    artifact = Path(args.artifact).resolve()
    if not artifact.is_file():
        print(f"找不到散布物：{artifact}")
        return 1

    venv_dir = Path(tempfile.mkdtemp(prefix="cjkfolio-venv-"))
    failures: list[str] = []

    proc = run("venv 建立", [sys.executable, "-m", "venv", str(venv_dir)])
    if proc.returncode != 0:
        print(proc.stderr[-1500:])
        return 1
    vpy = venv_dir / "Scripts" / "python.exe"

    # 相依解析本體：不帶 --no-deps。
    proc = run(f"pip install {artifact.name}",
               [str(vpy), "-m", "pip", "install", str(artifact)])
    tail = "\n".join(proc.stdout.strip().splitlines()[-12:])
    print(tail)
    if proc.returncode != 0:
        print(proc.stderr[-3000:])
        failures.append("pip install 失敗")

    if not failures:
        proc = run("pip check", [str(vpy), "-m", "pip", "check"])
        print(proc.stdout.strip())
        if proc.returncode != 0:
            failures.append("pip check 報相依不一致")

        proc = run("已安裝清單", [str(vpy), "-m", "pip", "list", "--format=freeze"])
        print(proc.stdout.strip())

        proc = run("import 冒煙", [str(vpy), "-c",
                   "import cjkfolio, cjkfolio.cli, fitz, PySide6, PIL, "
                   "fontTools, freetype, uharfbuzz; print('imports ok')"])
        print(proc.stdout.strip() or proc.stderr[-1500:])
        if proc.returncode != 0:
            failures.append("六枚相依 import 冒煙失敗")

    workdir: Path | None = None
    if args.cli_chain and not failures:
        if not (args.sample and args.font_dir):
            print("--cli-chain 需要 --sample 與 --font-dir（素材與字型由呼叫端顯式指定）")
            return 1
        workdir = Path(tempfile.mkdtemp(prefix="cjkfolio-work-"))
        sample = workdir / Path(args.sample).name
        shutil.copyfile(args.sample, sample)
        font_dir = str(Path(args.font_dir).resolve())

        steps = [
            ("import-md", ["import-md", sample.name, "-o", "ch1.doc.json",
                           "--title", "排版小記"]),
            ("render", ["render", "ch1.doc.json", "-o", "png",
                        "--font-dir", font_dir]),
            ("export-pdf", ["export-pdf", "ch1.doc.json", "-o", "ch1.pdf",
                            "--font-dir", font_dir]),
            ("preflight", ["preflight", "ch1.pdf"]),
        ]
        for label, cli_args in steps:
            proc = run(f"repo 外 {label}",
                       [str(vpy), "-m", "cjkfolio.cli", *cli_args], cwd=workdir)
            out = proc.stdout.strip()
            print("\n".join(out.splitlines()[-8:]))
            if proc.returncode != 0:
                print(proc.stderr[-2000:])
                failures.append(f"CLI {label} 失敗")
                break

    print()
    print(f"venv：{venv_dir}")
    if workdir:
        print(f"workdir：{workdir}")
    if failures:
        print("結論：FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("結論：PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
