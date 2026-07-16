"""書冊組裝（cjkfolio/book@1）：多章文件串接為單一多主版文件（Sprint 52）。

書冊清單 JSON 列出章文件（序即節序），組裝時把每章首段掛節首標記
（Paragraph.master，Sprint 51 節式主版指派），輸出一份普通 document@2 文件；
render／export／editing 全部照既有管線走，組裝層不新增排版機制。

主版解析優先序（決議紀錄 Sprint 52）：chapters[].master 顯式覆寫
＞ 章文件首段既有節首標記 ＞ 章文件 meta.master。

v1 限制（GAPS #31）：images 僅書冊層級（版面頁號＝全書；章層級 images 的頁號
是章內排版頁號、組裝後即失效，快速失敗）；直排橫排不可混（承 GAPS #30 (b)，
F 版權頁另出）；目錄頁碼為作者手填（自動生成屬 Phase 4）。
"""
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from .document import (
    Document,
    DocumentError,
    _images_from_list,
    load_document,
)

SCHEMA_ID = "cjkfolio/book@1"


class BookError(ValueError):
    """書冊清單 JSON 不合 schema，或章文件無法組裝。"""


@dataclass(frozen=True)
class ChapterRef:
    path: str  # 章文件 JSON 路徑（相對書冊清單所在目錄）
    master: Optional[str] = None  # 節首主版顯式覆寫（None＝依章文件）


@dataclass(frozen=True)
class Book:
    title: str
    template: str  # 模版 id；各章文件 meta.template 必須一致
    chapters: tuple
    images: tuple = ()  # 書冊層級 PlacedImage（page＝全書版面頁號）


def book_from_dict(data) -> Book:
    if not isinstance(data, dict):
        raise BookError("書冊清單必須是 JSON 物件")
    if data.get("schema") != SCHEMA_ID:
        raise BookError(f"schema 不符：需要 {SCHEMA_ID}，得到 {data.get('schema')!r}")
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise BookError("meta 必須是物件")
    title = meta.get("title")
    if not (isinstance(title, str) and title):
        raise BookError("meta.title 需為非空字串（PDF/X-1a 要求 Info /Title）")
    template = meta.get("template")
    if not (isinstance(template, str) and template):
        raise BookError("meta.template 需為非空字串")
    raw = data.get("chapters")
    if not (isinstance(raw, list) and raw):
        raise BookError("chapters 必須是非空陣列（章序即節序）")
    chapters = []
    for i, ch in enumerate(raw):
        if not isinstance(ch, dict) or not (isinstance(ch.get("path"), str) and ch["path"]):
            raise BookError(f"chapters[{i}] 需含非空 path 字串")
        master = ch.get("master")
        if master is not None and not (isinstance(master, str) and master):
            raise BookError(f"chapters[{i}] master 需為非空字串，得到 {master!r}")
        chapters.append(ChapterRef(path=ch["path"], master=master))
    raw_images = data.get("images", [])
    if not isinstance(raw_images, list):
        raise BookError("images 必須是陣列")
    try:
        images = _images_from_list(raw_images)
    except DocumentError as e:
        raise BookError(str(e)) from e
    return Book(title=title, template=template, chapters=tuple(chapters), images=images)


def load_book(path) -> Book:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise BookError(f"讀取書冊清單失敗 {path}：{e}") from e
    return book_from_dict(data)


def assemble_book(book: Book, base_dir=None) -> Document:
    """依章序串接章文件為單一多主版文件（章首＝節首，Sprint 51 節式主版指派）。

    回傳普通 document@2 Document：title＝書冊題名、master＝首章節首主版、
    paragraphs＝各章段落照序串接（章內既有節首標記照搬）、images＝書冊層級清單。
    """
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    paragraphs: list = []
    first_master = None
    for i, ch in enumerate(book.chapters):
        try:
            doc = load_document(base / ch.path)
        except DocumentError as e:
            raise BookError(f"chapters[{i}]（{ch.path}）載入失敗：{e}") from e
        if doc.template != book.template:
            raise BookError(
                f"chapters[{i}]（{ch.path}）模版不一致：書冊 {book.template!r}、"
                f"章文件 {doc.template!r}"
            )
        if not doc.paragraphs:
            raise BookError(f"chapters[{i}]（{ch.path}）無段落，空章不可組裝")
        if doc.images:
            raise BookError(
                f"chapters[{i}]（{ch.path}）帶章層級 images：其 page 為章內排版頁號，"
                "組裝後即失效；置入圖請改列書冊清單的 images（全書版面頁號）"
            )
        if doc.text_frames:
            raise BookError(
                f"chapters[{i}]（{ch.path}）帶章層級 text_frames：其 page 為章內排版"
                "頁號，組裝後即失效；文字框請於組裝後的全書文件上以全書版面頁號加入"
            )
        head = doc.paragraphs[0]
        resolved = ch.master or head.master or doc.master
        paragraphs.append(replace(head, master=resolved))
        paragraphs.extend(doc.paragraphs[1:])
        if first_master is None:
            first_master = resolved
    return Document(
        title=book.title,
        template=book.template,
        master=first_master,
        paragraphs=tuple(paragraphs),
        images=book.images,
    )
