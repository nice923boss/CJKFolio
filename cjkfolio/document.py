"""文件模型：段落＋樣式參照的最小 JSON schema（cjkfolio/document@2）。

語意化內容與樣式分離（PLAN §5.1 文件模型層）：段落記段落樣式名與 run 序列
（run＝連續文字＋選配字元樣式，PLAN §4.1 字元樣式層），幾何一律由樣式層＋
引擎推導。系統邊界（檔案載入）做 schema 驗證，快速失敗。

相容性：@1（純 text 段落）照載；@2 段落可用 text 捷徑或 runs 陣列。
save 一律寫 @2；單一無字元樣式 run 以 text 捷徑序列化（可讀性）。
圖片置入（images，@2 相容擴充選配欄位，同 page_no 慣例）：置入主版 figure
保留區的照片清單（PLAN §4.2 G 圖文版、§9 灰階單 K）。
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
    """不變式：text ＝ 全段字面 ＝ runs 文字串接（__post_init__ 正規化）。

    page_no：目錄條目頁碼（選配，僅數字字串；@2 相容擴充，無欄位照載）。
    """
    text: str = ""
    style: str = ""
    runs: tuple = ()
    page_no: Optional[str] = None

    def __post_init__(self):
        if self.runs:
            object.__setattr__(self, "text", "".join(r.text for r in self.runs))
        else:
            object.__setattr__(self, "runs", (Run(self.text),))


@dataclass(frozen=True)
class PlacedImage:
    """置入一張圖到某版面頁的主版 figure 保留區（PLAN §4.2 G 圖文版照片、§9 灰階單 K）。

    path：圖檔路徑（相對路徑於 render／export 時相對文件目錄解析）；
    page：版面頁號（1 起算，與 --page 選頁鍵、檔名同鍵，Sprint 12 決議）。
    v1 每頁 figure 保留區置一張圖、contain 等比置中（primitives.fit_image_rect）。
    """
    path: str
    page: int


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


def _images_from_list(raw) -> tuple:
    """解析 images 陣列（選配）。每項須含非空 path 與 ≥1 整數 page；page 重複快速失敗
    （v1 每頁 figure 保留區只置一張圖）。"""
    images = []
    seen_pages = set()
    for j, im in enumerate(raw):
        if not isinstance(im, dict):
            raise DocumentError(f"images[{j}] 須為物件")
        path = im.get("path")
        if not (isinstance(path, str) and path):
            raise DocumentError(f"images[{j}] 需含非空 path 字串")
        page = im.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise DocumentError(f"images[{j}] page 需為 ≥1 的整數，得到 {page!r}")
        if page in seen_pages:
            raise DocumentError(
                f"images[{j}] page {page} 重複（v1 每頁 figure 保留區只置一張圖）"
            )
        seen_pages.add(page)
        images.append(PlacedImage(path=path, page=page))
    return tuple(images)


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
        page_no = p.get("page_no")
        if page_no is not None and not (isinstance(page_no, str) and page_no.isdigit()):
            raise DocumentError(f"paragraphs[{i}] page_no 需為數字字串，得到 {page_no!r}")
        if "runs" in p:
            if schema == SCHEMA_V1:
                raise DocumentError(f"paragraphs[{i}] 使用 runs 需 schema document@2")
            paragraphs.append(Paragraph(style=p["style"], runs=_runs_from_list(p["runs"], i),
                                        page_no=page_no))
        elif isinstance(p.get("text"), str):
            paragraphs.append(Paragraph(p["text"], p["style"], page_no=page_no))
        else:
            raise DocumentError(f"paragraphs[{i}] 需含 text 字串或 runs 陣列")
    raw_images = data.get("images", [])
    if not isinstance(raw_images, list):
        raise DocumentError("images 必須是陣列")
    return Document(
        title=str(meta.get("title", "")),
        template=str(meta.get("template", "")),
        master=str(meta.get("master", "A-內文版")),
        paragraphs=tuple(paragraphs),
        language=str(meta.get("language", "zh-TW")),
        images=_images_from_list(raw_images),
    )


@dataclass(frozen=True)
class Document:
    title: str
    template: str  # 模版 id（檔名 stem）
    master: str    # 主版名，v1 全文件單一主版
    paragraphs: tuple
    language: str = "zh-TW"
    images: tuple = ()  # PlacedImage 序列（@2 相容擴充；置入主版 figure 保留區）


def _paragraph_to_dict(p: Paragraph) -> dict:
    if len(p.runs) == 1 and p.runs[0].char_style is None:
        out = {"text": p.text, "style": p.style}
    else:
        runs = [
            {"text": r.text, **({"char_style": r.char_style} if r.char_style else {})}
            for r in p.runs
        ]
        out = {"style": p.style, "runs": runs}
    if p.page_no is not None:
        out["page_no"] = p.page_no
    return out


def document_to_dict(doc: Document) -> dict:
    out = {
        "schema": SCHEMA_ID,
        "meta": {
            "title": doc.title,
            "template": doc.template,
            "master": doc.master,
            "language": doc.language,
        },
        "paragraphs": [_paragraph_to_dict(p) for p in doc.paragraphs],
    }
    if doc.images:
        out["images"] = [{"path": im.path, "page": im.page} for im in doc.images]
    return out


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
