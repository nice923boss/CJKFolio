"""字型授權量測（Sprint 112，GAPS #43 (a)）：逐款列出嵌入權限與名義授權宣告。

兩層各答一問，缺一不可：

- **機器層**（OS/2 fsType 位元）：字型檔允不允許把輪廓子集嵌進 PDF。
- **名義層**（name 表 ID 13 License Description、ID 14 License Info URL）：授權文字
  允不允許把字型隨成品散布。實測商用字型（標楷體、新細明體、Arial、Gill Sans MT）
  fsType 皆為 0x0008 Editable，機器層零警告，名義層才看得出是商用授權。

字型一律由呼叫端以 `--fonts` 顯式列出，本工具**不內含任何字型路徑、不掃描系統字型
目錄**：系統字型多為商用授權，路徑屬呼叫端的事（同 measure_long_book 的素材外置紀律）。
未給 `--fonts` 時只量 repo 內 `assets/fonts` 的可散布字型。

用法（自 repo 根執行）：

    python tools/measure_font_license.py
    python tools/measure_font_license.py --fonts 字型1.ttf 字型2.ttc --json out/授權.json

數字與判定隨字型版本而異（商用字型不入 repo，無從重現），故**不入自動測試斷言**；
測試只驗工具邏輯與可跑。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cjkfolio.font_license import (  # noqa: E402
    embedding_permission,
    license_rows,
    redistribution_declaration,
)
from cjkfolio.fonts import DEFAULT_FONT_DIR  # noqa: E402


def bundled_fonts() -> list:
    """repo 內建可散布字型（未給 --fonts 時的預設量測對象）。"""
    return sorted(list(DEFAULT_FONT_DIR.glob("*.otf")) + list(DEFAULT_FONT_DIR.glob("*.ttf")))


def measure(paths) -> list:
    """逐款取兩層判定（開檔失敗據實記錄，不中斷整批）。"""
    out = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            out.append({"字型": p.name, "狀態": "缺檔", "路徑": str(p)})
            continue
        try:
            emb = embedding_permission(p)
            red = redistribution_declaration(p)
        except Exception as exc:  # noqa: BLE001（壞檔或不支援格式照樣列，不吞掉）
            out.append({"字型": p.name, "狀態": "讀取失敗", "路徑": str(p),
                        "明細": str(exc)})
            continue
        out.append({
            "字型": emb.font,
            "狀態": license_rows([p])[0][0],
            "路徑": str(p),
            "fsType": f"0x{emb.fs_type:04X}",
            "可嵌入": emb.embeddable,
            "嵌入判定": emb.note,
            "名義分類": red.klass,
            "自由授權": red.license_name,
            "授權宣告": red.declaration,
            "授權網址": red.url,
            "來源": red.vendor,
            "名義判定": red.note,
        })
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="字型嵌入權限與名義授權量測")
    ap.add_argument("--fonts", nargs="*", default=None,
                    help="要量的字型檔（預設量 assets/fonts 內建字型）")
    ap.add_argument("--json", default=None, help="另存 JSON 明細的路徑")
    args = ap.parse_args(argv)

    paths = [Path(f) for f in args.fonts] if args.fonts else bundled_fonts()
    if not paths:
        print("沒有可量的字型（assets/fonts 為空，請以 --fonts 指定）", file=sys.stderr)
        return 2
    rows = measure(paths)

    print(f"{'狀態':<6}｜{'字型':<34}｜{'fsType':<8}｜{'名義分類':<10}｜來源")
    for r in rows:
        print(f"{r['狀態']:<6}｜{r['字型']:<34}｜{r.get('fsType', ''):<8}｜"
              f"{r.get('名義分類', ''):<10}｜{r.get('來源', r.get('明細', ''))[:40]}")
    print()
    for r in rows:
        if r["狀態"] != "可散布":
            print(f"※ {r['字型']}：{r.get('名義判定', r.get('明細', ''))}")
    free = sum(1 for r in rows if r["狀態"] == "可散布")
    print(f"\n合計 {len(rows)} 款：{free} 款可散布，{len(rows) - free} 款須確認或不可嵌入")
    print("fsType 允許嵌入不等於授權允許散布：商用字型多為 Editable 卻仍需授權，"
          "本工具只呈報字型自報內容，不做法律判斷。")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 明細：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
