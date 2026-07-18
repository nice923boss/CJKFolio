"""稿件匯入判定層（Sprint 107）：依副檔名分派 txt／md／docx，預設值全由模版推導。

Qt 無關，故可在 pytest 基線裡跑（同 preflight_core／ai_assign_core 的分層）。

**本層存在的理由是「預設值不得寫死」**。匯入一份稿要決定三件事，三件都繫於當前模版：

  template_id  呼叫端給（＝模版檔 stem；編輯器同時只持一份模版）
  master       template.default_master（Sprint 105 已搬進資料層）
  內文樣式      template.md_mapping["paragraph"]

md／docx 走 md_mapping 本就由模版驅動，txt 缺的正是同一件事：`import_txt` 的
`DEFAULT_BODY_STYLE`＝「內文-明體直排」是第一本書的樣式名，對《街角慢行》模版並不
存在。Sprint 107 實測：`import-txt --template jiejiao-manxing.json` exit 0 且回報
「匯入完成：2 段」，但產出的文件到 render 才爆「文件引用模版沒有的樣式」。**匯入端
沉默產出壞文件、錯誤延到渲染才現形**，故本層一律從模版取值，並在回傳前確保
所引用的主版確實存在（不把可在匯入時判定的錯留給下游）。
"""
from pathlib import Path

from cjkfolio.docx_import import import_docx
from cjkfolio.md_import import import_markdown_file
from cjkfolio.styles import Template
from cjkfolio.txt_import import import_txt_file

# 對外廣告的格式（編輯器檔案對話框的過濾器與本層分派同源，避免選得到卻匯不進）
SUPPORTED_SUFFIXES = (".txt", ".md", ".markdown", ".docx")

FILE_DIALOG_FILTER = "稿件 (*.txt *.md *.markdown *.docx)"


def _import_defaults(template: Template, template_id: str) -> tuple:
    """從模版取 (主版, 內文樣式)；缺一即在匯入時明確失敗，不留給下游。"""
    master = template.default_master
    if not master:
        raise ValueError(
            f"模版 {template_id} 未宣告 default_master，無法決定新稿掛哪張主版"
            f"（模版可選主版：{'、'.join(sorted(template.masters))}）")
    if master not in template.masters:
        raise ValueError(
            f"模版 {template_id} 宣告的 default_master「{master}」不存在於其主版清單"
            f"（可選：{'、'.join(sorted(template.masters))}）")
    body_style = template.md_mapping.get("paragraph")
    if not body_style:
        raise ValueError(
            f"模版 {template_id} 的 md_mapping 缺 paragraph 對映，無法決定內文樣式")
    return master, body_style


def import_manuscript(path, template: Template, template_id: str, *, title: str = ""):
    """匯入一份稿件為 Document；副檔名決定解析器，預設值一律由 template 推導。

    title 預設取檔名（不含副檔名）。不支援的副檔名明確列出支援清單，不沉默略過。
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"不支援的稿件格式「{suffix or path.name}」"
            f"（支援：{'、'.join(SUPPORTED_SUFFIXES)}）")
    master, body_style = _import_defaults(template, template_id)
    common = {"title": title or path.stem, "template_id": template_id, "master": master}

    if suffix == ".txt":
        return import_txt_file(path, default_style=body_style, **common)
    structured = {"mapping": template.md_mapping,
                  "inline_mapping": template.md_inline_mapping}
    if suffix == ".docx":
        return import_docx(path, **structured, **common)
    return import_markdown_file(path, **structured, **common)
