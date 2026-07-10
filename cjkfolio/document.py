"""文件模型：段落＋樣式參照的最小 JSON schema（cjkfolio/document@1）。

語意化內容與樣式分離（PLAN §5.1 文件模型層）：段落只記文字與段落樣式名，
幾何一律由樣式層＋引擎推導。系統邊界（檔案載入）做 schema 驗證，快速失敗。
"""
import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA_ID = "cjkfolio/document@1"


class DocumentError(ValueError):
    """文件 JSON 不合 schema。"""


@dataclass(frozen=True)
class Paragraph:
    text: str
    style: str


@dataclass(frozen=True)
class Document:
    title: str
    template: str  # 模版 id（檔名 stem）
    master: str    # 主版名，v1 全文件單一主版
    paragraphs: tuple
    language: str = "zh-TW"


def document_from_dict(data) -> Document:
    if not isinstance(data, dict):
        raise DocumentError("文件必須是 JSON 物件")
    if data.get("schema") != SCHEMA_ID:
        raise DocumentError(f"schema 不符：需要 {SCHEMA_ID}，得到 {data.get('schema')!r}")
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise DocumentError("meta 必須是物件")
    raw = data.get("paragraphs")
    if not isinstance(raw, list):
        raise DocumentError("paragraphs 必須是陣列")
    paragraphs = []
    for i, p in enumerate(raw):
        if (
            not isinstance(p, dict)
            or not isinstance(p.get("text"), str)
            or not isinstance(p.get("style"), str)
            or not p["style"]
        ):
            raise DocumentError(f"paragraphs[{i}] 需含 text 與非空 style 字串")
        paragraphs.append(Paragraph(p["text"], p["style"]))
    return Document(
        title=str(meta.get("title", "")),
        template=str(meta.get("template", "")),
        master=str(meta.get("master", "A-內文版")),
        paragraphs=tuple(paragraphs),
        language=str(meta.get("language", "zh-TW")),
    )


def document_to_dict(doc: Document) -> dict:
    return {
        "schema": SCHEMA_ID,
        "meta": {
            "title": doc.title,
            "template": doc.template,
            "master": doc.master,
            "language": doc.language,
        },
        "paragraphs": [{"text": p.text, "style": p.style} for p in doc.paragraphs],
    }


def load_document(path) -> Document:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise DocumentError(f"讀取文件失敗 {path}：{e}") from e
    return document_from_dict(data)


def save_document(doc: Document, path) -> None:
    Path(path).write_text(
        json.dumps(document_to_dict(doc), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def unknown_style_refs(doc: Document, template) -> list:
    """回傳文件引用但模版沒有的段落樣式名（去重、保序）。"""
    unknown = []
    for p in doc.paragraphs:
        if p.style not in template.paragraph_styles and p.style not in unknown:
            unknown.append(p.style)
    return unknown
