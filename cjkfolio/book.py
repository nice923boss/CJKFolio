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
class TocSpec:
    """自動目錄章生成規格（Sprint 85）：由系統依列入章起始頁生成目錄段落。

    entry_style／master 必填；heading（部名）選配，有 heading 時 heading_style 必填。
    entry_styles（Sprint 108）＝第二層起的逐層條目樣式 {層級: 樣式名}；第一層恆為
    entry_style。階層縮排由各層樣式自身的 head_offset_chars 表達（無新幾何機制）。
    """
    entry_style: str
    master: str
    heading: Optional[str] = None
    heading_style: Optional[str] = None
    entry_styles: Optional[dict] = None

    def style_for_level(self, level: int) -> str:
        """取該層條目樣式；未宣告即快速失敗（不沉默落回第一層樣式）。"""
        if level == 1:
            return self.entry_style
        declared = self.entry_styles or {}
        if level not in declared:
            available = ", ".join(str(k) for k in [1, *sorted(declared)])
            raise BookError(
                f"自動目錄第 {level} 層無條目樣式：generate_toc.entry_styles 未宣告該層"
                f"（已宣告層級：{available}）"
            )
        return declared[level]


@dataclass(frozen=True)
class ChapterRef:
    path: Optional[str] = None  # 章文件 JSON 路徑（相對書冊清單所在目錄）；自動目錄章為 None
    master: Optional[str] = None  # 節首主版顯式覆寫（None＝依章文件）
    toc_title: Optional[str] = None  # 列入自動目錄的顯示標題（Sprint 85；None＝不列入）
    toc_spec: Optional[TocSpec] = None  # 非 None＝自動目錄章（無 path，頁碼由系統計算）
    toc_level: int = 1  # 該章條目的目錄層級（Sprint 108；章內小節預設為此值 +1）


@dataclass(frozen=True)
class Book:
    title: str
    template: str  # 模版 id；各章文件 meta.template 必須一致
    chapters: tuple
    images: tuple = ()  # 書冊層級 PlacedImage（page＝全書版面頁號）
    # 封面主版名（選配，Sprint 132）：組裝後成為 Document.cover，全書首頁為封面，
    # 頁碼自封面翻開後起算（自動目錄頁碼同步位移）。None＝無封面。
    cover: Optional[str] = None


def _toc_chapter_from_dict(ch, i: int) -> ChapterRef:
    """解析自動目錄章（含 generate_toc 的 chapter 物件）為 ChapterRef。"""
    if "path" in ch:
        raise BookError(f"chapters[{i}] 不可同時有 path 與 generate_toc")
    if "toc_title" in ch:
        raise BookError(f"chapters[{i}] 自動目錄章不可有 toc_title（不列於自身目錄）")
    spec = ch["generate_toc"]
    if not isinstance(spec, dict):
        raise BookError(f"chapters[{i}] generate_toc 需為物件")
    entry_style = spec.get("entry_style")
    if not (isinstance(entry_style, str) and entry_style):
        raise BookError(f"chapters[{i}] generate_toc.entry_style 需為非空字串")
    master = spec.get("master")
    if not (isinstance(master, str) and master):
        raise BookError(f"chapters[{i}] generate_toc.master 需為非空字串")
    heading = spec.get("heading")
    heading_style = spec.get("heading_style")
    if heading is not None and not (isinstance(heading, str) and heading):
        raise BookError(f"chapters[{i}] generate_toc.heading 需為非空字串或省略")
    if heading is not None and not (isinstance(heading_style, str) and heading_style):
        raise BookError(f"chapters[{i}] generate_toc 有 heading 時 heading_style 必填（非空字串）")
    return ChapterRef(toc_spec=TocSpec(
        entry_style=entry_style, master=master,
        heading=heading, heading_style=heading_style,
        entry_styles=_entry_styles_from_dict(spec.get("entry_styles"), i)))


def _entry_styles_from_dict(raw, i: int) -> Optional[dict]:
    """解析 generate_toc.entry_styles（選配）：{"2": 樣式名, ...} → {2: 樣式名}。

    第一層恆由 entry_style 宣告，故此表的鍵須 ≥2（宣告 "1" 即雙源，快速失敗）。
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BookError(f"chapters[{i}] generate_toc.entry_styles 需為物件，得到 {raw!r}")
    out: dict = {}
    for key, value in raw.items():
        level = int(key) if isinstance(key, str) and key.isdigit() else None
        if level is None or level < 2:
            raise BookError(
                f"chapters[{i}] generate_toc.entry_styles 的鍵需為 ≥2 的層級整數字串"
                f"（第一層由 entry_style 宣告），得到 {key!r}"
            )
        if not (isinstance(value, str) and value):
            raise BookError(
                f"chapters[{i}] generate_toc.entry_styles 的值需為非空字串，得到 {value!r}")
        out[level] = value
    return out


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
        if not isinstance(ch, dict):
            raise BookError(f"chapters[{i}] 需為物件")
        if "generate_toc" in ch:
            chapters.append(_toc_chapter_from_dict(ch, i))
            continue
        if not (isinstance(ch.get("path"), str) and ch["path"]):
            raise BookError(f"chapters[{i}] 需含非空 path 字串")
        master = ch.get("master")
        if master is not None and not (isinstance(master, str) and master):
            raise BookError(f"chapters[{i}] master 需為非空字串，得到 {master!r}")
        toc_title = ch.get("toc_title")
        if toc_title is not None and not (isinstance(toc_title, str) and toc_title):
            raise BookError(f"chapters[{i}] toc_title 需為非空字串或省略，得到 {toc_title!r}")
        toc_level = ch.get("toc_level")
        if toc_level is not None and (isinstance(toc_level, bool)
                                      or not isinstance(toc_level, int) or toc_level < 1):
            raise BookError(f"chapters[{i}] toc_level 需為 ≥1 的整數，得到 {toc_level!r}")
        if toc_level is not None and toc_title is None:
            raise BookError(
                f"chapters[{i}] toc_level 需搭 toc_title（無標題即不列入目錄）")
        chapters.append(ChapterRef(path=ch["path"], master=master, toc_title=toc_title,
                                   toc_level=toc_level if toc_level is not None else 1))
    if sum(1 for c in chapters if c.toc_spec) > 1:
        raise BookError("每書冊至多一個自動目錄章（generate_toc）")
    raw_images = data.get("images", [])
    if not isinstance(raw_images, list):
        raise BookError("images 必須是陣列")
    try:
        images = _images_from_list(raw_images)
    except DocumentError as e:
        raise BookError(str(e)) from e
    cover = meta.get("cover")
    if cover is not None and not (isinstance(cover, str) and cover):
        raise BookError(f"meta.cover 需為非空字串（封面主版名），得到 {cover!r}")
    return Book(title=title, template=template, chapters=tuple(chapters),
                images=images, cover=cover)


def load_book(path) -> Book:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise BookError(f"讀取書冊清單失敗 {path}：{e}") from e
    return book_from_dict(data)


def _resolve_chapter(ch: ChapterRef, base: Path, book_template: str, i: int) -> list:
    """載入一個 path 章、驗證並解析節首主版，回傳該章段落列（首段已掛 resolved master）。

    主版解析優先序（Sprint 52）：chapters[].master ＞ 章文件首段既有節首標記
    ＞ 章文件 meta.master。auto-TOC（Sprint 85）與 assemble_book 共用此路徑。
    """
    try:
        doc = load_document(base / ch.path)
    except DocumentError as e:
        raise BookError(f"chapters[{i}]（{ch.path}）載入失敗：{e}") from e
    if doc.template != book_template:
        raise BookError(
            f"chapters[{i}]（{ch.path}）模版不一致：書冊 {book_template!r}、"
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
    return [replace(head, master=resolved), *doc.paragraphs[1:]]


def assemble_book(book: Book, base_dir=None) -> Document:
    """依章序串接章文件為單一多主版文件（章首＝節首，Sprint 51 節式主版指派）。

    回傳普通 document@2 Document：title＝書冊題名、master＝首章節首主版、
    paragraphs＝各章段落照序串接（章內既有節首標記照搬）、images＝書冊層級清單。

    含自動目錄章（generate_toc）的書冊須用 cjkfolio.toc.assemble_book_with_toc
    （需模版計算頁碼）；本函式只處理純 path 書冊。
    """
    if any(ch.toc_spec for ch in book.chapters):
        raise BookError(
            "此書冊含自動目錄章（generate_toc），請用 cjkfolio.toc.assemble_book_with_toc"
            "（需模版計算頁碼）組裝"
        )
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    paragraphs: list = []
    first_master = None
    for i, ch in enumerate(book.chapters):
        chap = _resolve_chapter(ch, base, book.template, i)
        paragraphs.extend(chap)
        if first_master is None:
            first_master = chap[0].master
    return Document(
        title=book.title,
        template=book.template,
        master=first_master,
        paragraphs=tuple(paragraphs),
        images=book.images,
        cover=book.cover,
    )
