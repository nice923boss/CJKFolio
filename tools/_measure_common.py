"""量測工具共用層：參考書跨頁幾何常數、span 抽取、出血換算、輸出樣板。

抽自 measure_cip/toc/case/figure_page.py 的重複（Sprint 31，替代軌 A：順手移除
噪音）。參考書量測皆讀《內在整理》交印檔（跨頁 spread，每半頁 148mm），本機素材
不入 repo（PLAN §8）。常數量測層自持（同 cjkfolio.primitives 對 PT_PER_MM 的
「底層層各自持有免循環依賴」先例），不 import 產品層，保持量測工具輕量獨立。

各工具以 `python tools/measure_xxx_page.py` 執行，指令稿目錄自動入 sys.path，
故 `import _measure_common` 直接解析同層檔案。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PDF = ROOT / "內在整理-20260312.pdf"   # 交印檔（本機，不入 repo）
# 交印檔亦可置於 local/（GAPS #6 已列 .gitignore 的本機素材目錄）。Windows 繁中
# 環境下含中文的命令列參數會被以 mbcs 轉碼而損壞，故預設路徑自行探查兩處，免逐次
# 靠 argv 傳中文路徑。
REFERENCE_PDF_ALT = ROOT / "local" / "內在整理-20260312.pdf"
REFERENCE_DIR = ROOT / "assets" / "reference"     # 量測 JSON 輸出目錄（本機）

PT_PER_MM = 72.0 / 25.4
HALF_W = 419.53      # 148mm 跨頁半寬（pt）；沿用各工具原字面值，免捨入漂移翻動輸出
# Gate-4 出血換算：model 匯出 PDF 的 MediaBox＝trim＋3mm 出血；真書交印檔無出血
# （media＝trim，Sprint 30 實測）。比對 model 墨座標與真書 trim 空間時扣此常數，
# 免重蹈 Sprint 24/25 未扣出血得假差之覆轍。值＝cjkfolio.pdf_writer.BLEED_MM(3.0)
# 的 pt 值，量測層自持免載入 PDF 寫出層。
BLEED_PT = 3.0 * PT_PER_MM      # 8.5039pt


def stdout_utf8() -> None:
    """終端輸出設 UTF-8（Windows 繁中環境中文摘要不亂碼）。"""
    sys.stdout.reconfigure(encoding="utf-8")


def spans(page) -> list:
    """頁面所有文字 span 攤平成 list（blocks→lines→spans）。

    回傳 list（非 generator）：呼叫端常對同一頁多次篩選（標題／內文／頁碼各一
    輪），需可重複迭代。
    """
    out: list = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            out.extend(line["spans"])
    return out


def is_spread(page) -> bool:
    """是否為跨頁 spread（寬 > 1.5 半頁）；單頁（書首末）為 False。"""
    return page.rect.width > HALF_W * 1.5


def strip_bleed(v_pt: float) -> float:
    """model media 空間座標扣 3mm 出血 → trim 空間（Gate-4 model↔真書比對）。"""
    return v_pt - BLEED_PT


def reference_pdf() -> str:
    """參考書 PDF 路徑：命令列 argv[1] 覆寫，否則預設交印檔（本機根目錄或 local/）。"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return str(REFERENCE_PDF if REFERENCE_PDF.exists() else REFERENCE_PDF_ALT)


def write_measurements(name: str, data) -> Path:
    """寫量測 JSON（ensure_ascii=False、indent=1 樣板）到 assets/reference/，回傳路徑。"""
    path = REFERENCE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
