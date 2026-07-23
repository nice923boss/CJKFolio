"""模版庫管理面資料層（Sprint 77，§4.3「模版庫」／§6 Phase 3）。

list_templates：目錄掃描模版清單（*.json 淺讀 name；壞檔／非模版 schema 列
entry.error 不沉默、不擋清單，供庫面板與匯入選擇）。
merge_draft_styles：參考萃取草稿（reference_extract.extract_draft 形）一鍵併入
模版（GAPS #37 (b)）：逐條 add_paragraph_style，同名跳過列報不覆蓋（既有定義
優先，覆蓋屬 UI 層選項後續）；全跳過 no-op 回原物件（session no-op 慣例）。
套用整個模版到編輯中文件見 session.EditSession.apply_template。
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from .style_editing import add_paragraph_style
from .styles import SCHEMA_ID, Template, TemplateError


def resolve_template_dir(package_dir=None) -> Path:
    """內建模版目錄：wheel 安裝形態取套件內，repo 形態取 repo 根（Spike 21）。

    repo 裡模版放在根目錄的 `templates/`（模版是專案交付物，不是躲在套件裡的
    實作細節），wheel 則靠 pyproject 的 package-dir 把同一批檔案映射成
    `cjkfolio/templates/`。兩種形態的差別只有這一個目錄在不在，所以判斷條件
    就寫這一個目錄在不在，不去猜執行環境。

    package_dir 供測試注入；預設為本模組所在的套件目錄。
    """
    pkg = Path(package_dir) if package_dir else Path(__file__).resolve().parent
    packaged = pkg / "templates"
    return packaged if packaged.is_dir() else pkg.parent / "templates"


@dataclass(frozen=True)
class TemplateEntry:
    """庫清單項：讀得出名稱的模版，或帶 error 的壞檔（不沉默）。"""
    path: Path
    name: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class MergeReport:
    """草稿併入結果：added＝新增樣式名、skipped＝跳過樣式（同名既有優先）。"""
    added: tuple = ()
    skipped: tuple = ()


@dataclass(frozen=True)
class SkippedStyle:
    name: str
    reason: str


def list_templates(directory) -> tuple:
    """掃描目錄 *.json 為模版清單（檔名排序）；目錄不存在回空 tuple。

    每檔淺讀 schema 與 name（不做完整載入＝清單快；完整驗證留給 load_template）；
    壞 JSON／非模版 schema 列 entry.error（不沉默、不擋其他項）。
    """
    directory = Path(directory)
    if not directory.is_dir():
        return ()
    entries = []
    for path in sorted(directory.glob("*.json"), key=lambda p: p.name):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            entries.append(TemplateEntry(path=path, error=f"讀取失敗：{e}"))
            continue
        if not isinstance(data, dict) or data.get("schema") != SCHEMA_ID:
            entries.append(TemplateEntry(
                path=path,
                error=f"schema 不符：需要 {SCHEMA_ID}，得到 {data.get('schema')!r}"
                if isinstance(data, dict) else "非 JSON 物件"))
            continue
        entries.append(TemplateEntry(path=path, name=str(data.get("name", ""))))
    return tuple(entries)


def merge_draft_styles(template: Template, draft: Mapping):
    """萃取草稿一鍵併入：draft["paragraph_styles"] 逐條新增，回 (Template, MergeReport)。

    同名樣式跳過（既有定義優先、列 skipped 不沉默）；全跳過 no-op 回原物件；
    草稿缺 paragraph_styles 鍵 TemplateError 快速失敗。
    """
    if "paragraph_styles" not in draft:
        raise TemplateError("草稿缺 paragraph_styles 區塊（reference_extract 草稿形）")
    added, skipped = [], []
    out = template
    for name, decl in draft["paragraph_styles"].items():
        if name in out.paragraph_styles:
            skipped.append(SkippedStyle(name=name, reason="同名樣式已存在（既有定義優先）"))
            continue
        out = add_paragraph_style(out, name, decl)
        added.append(name)
    return out, MergeReport(added=tuple(added), skipped=tuple(skipped))
