"""文件模型：段落＋樣式參照的最小 JSON schema（cjkfolio/document@2）。

語意化內容與樣式分離（PLAN §5.1 文件模型層）：段落記段落樣式名與 run 序列
（run＝連續文字＋選配字元樣式，PLAN §4.1 字元樣式層），幾何一律由樣式層＋
引擎推導。系統邊界（檔案載入）做 schema 驗證，快速失敗。

相容性：@1（純 text 段落）照載；@2 段落可用 text 捷徑或 runs 陣列。
save 一律寫 @2；單一無字元樣式 run 以 text 捷徑序列化（可讀性）。
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SCHEMA_ID = "cjkfolio/document@2"
SCHEMA_V1 = "cjkfolio/document@1"


class DocumentError(ValueError):
    """文件 JSON 不合 schema。"""


@dataclass(frozen=True)
class Run:
    text: str
    char_style: Optional[str] = None


@dataclass(frozen=True)
class Paragraph:
    """不變式：text ＝ 全段字面 ＝ runs 文字串接（__post_init__ 正規化）。"""
    text: str = ""
    style: str = ""
    runs: tuple = ()

    def __post_init__(self):
        if self.runs:
            object.__setattr__(self, "text", "".join(r.text for r in self.runs))
        else:
            object.__setattr__(self, "runs", (Run(self.text),))


def _runs_from_list(raw, idx: int) -> tuple:
    runs = []
    for j, r in enumerate(raw):
        if not isinstance(r, dict) or not isinstance(r.get("text"), str):
            raise DocumentError(f"paragraphs[{idx}].runs[{j}] 需含 text 字串")
        char_style = r.get("char_style")
        if char_style is not None and (not isinstance(char_style, str) or not char_style):
            raise DocumentError(f"paragraphs[{idx}].runs[{j}] char_style 需為非空字串")
        runs.append(Run(r["text"], char_style))
    if not runs:
        raise DocumentError(f"paragraphs[{idx}].runs 不得為空陣列")
    return tuple(runs)


def document_from_dict(data) -> "Document":
    if not isinstance(data, dict):
        raise DocumentError("文件必須是 JSON 物件")
    schema = data.get("schema")
    if schema not in (SCHEMA_ID, SCHEMA_V1):
        raise DocumentError(f"schema 不符：需要 {SCHEMA_ID}（或相容 {SCHEMA_V1}），得到 {schema!r}")
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise DocumentError("meta 必須是物件")
    raw = data.get("paragraphs")
    if not isinstance(raw, list):
        raise DocumentError("paragraphs 必須是陣列")
    paragraphs = []
    for i, p in enumerate(raw):
        if not isinstance(p, dict) or not isinstance(p.get("style"), str) or not p["style"]:
            raise DocumentError(f"paragraphs[{i}] 需含非空 style 字串")
        if "runs" in p:
            if schema == SCHEMA_V1:
                raise DocumentError(f"paragraphs[{i}] 使用 runs 需 schema document@2")
            paragraphs.append(Paragraph(style=p["style"], runs=_runs_from_list(p["runs"], i)))
        elif isinstance(p.get("text"), str):
            paragraphs.append(Paragraph(p["text"], p["style"]))
        else:
            raise DocumentError(f"paragraphs[{i}] 需含 text 字串或 runs 陣列")
    return Document(
        title=str(meta.get("title", "")),
        template=str(meta.get("template", "")),
        master=str(meta.get("master", "A-內文版")),
        paragraphs=tuple(paragraphs),
        language=str(meta.get("language", "zh-TW")),
    )


@dataclass(frozen=True)
class Document:
    title: str
    template: str  # 模版 id（檔名 stem）
    master: str    # 主版名，v1 全文件單一主版
    paragraphs: tuple
    language: str = "zh-TW"


def _paragraph_to_dict(p: Paragraph) -> dict:
    if len(p.runs) == 1 and p.runs[0].char_style is None:
        return {"text": p.text, "style": p.style}
    runs = [
        {"text": r.text, **({"char_style": r.char_style} if r.char_style else {})}
        for r in p.runs
    ]
    return {"style": p.style, "runs": runs}


def document_to_dict(doc: Document) -> dict:
    return {
        "schema": SCHEMA_ID,
        "meta": {
            "title": doc.title,
            "template": doc.template,
            "master": doc.master,
            "language": doc.language,
        },
        "paragraphs": [_paragraph_to_dict(p) for p in doc.paragraphs],
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


def unknown_char_style_refs(doc: Document, template) -> list:
    """回傳文件引用但模版沒有的字元樣式名（去重、保序）。"""
    unknown = []
    for p in doc.paragraphs:
        for r in p.runs:
            if r.char_style and r.char_style not in template.character_styles \
                    and r.char_style not in unknown:
                unknown.append(r.char_style)
    return unknown
