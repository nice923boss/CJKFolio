"""目錄自動生成（cjkfolio/book@1 auto-TOC，Sprint 85，Phase 4）。

痛點（GAPS #31 (c)）：書冊目錄頁碼原為作者手填，內容變動須手動同步。本模組
把「列入章的起始頁碼」交給引擎自動計算：書冊清單以 generate_toc 章宣告目錄骨架，
內容章以 chapters[].toc_title 宣告列入標題，組裝時自動填入正確書頁號。

多層階層（Sprint 108）：章條目層級取 chapters[].toc_level、章內小節以章文件段落的
toc_title／toc_level 宣告，各層條目掛各層樣式（generate_toc.entry_styles），縮排
階層由樣式自身的 head_offset_chars 表達，本模組不新增幾何機制。

兩趟穩定分頁（無 fixpoint）：目錄條目數＝宣告條目數（列入章＋宣告小節，先驗定值），
故目錄本身頁數與計算出的頁碼「數字」無關；page_no 為非流排載體（engine：掛段末行、不影響斷行），
填值不改分頁。因此：
  Pass 1：以 page_no=None 的條目占位組裝＋流排 → 定分頁、取各列入章起始頁。
  Pass 2：把書頁號填入條目 page_no（不觸分頁）。

書頁號＝版面頁號 + first_page − 1（同 render／pdf_writer；first_page 須與最終
render／export 一致，頁碼才對得上）。版面幾何一律引擎推導，本模組不碰渲染。
"""
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from .book import Book, BookError, _resolve_chapter
from .document import Document, Paragraph
from .primitives import book_number_for
from .wrap import layout_with_wrap


@dataclass(frozen=True)
class TocItem:
    """一條自動目錄項：顯示標題＋所在書頁號＋目錄層級（第一層＝章，Sprint 108）。"""
    title: str
    page: int
    level: int = 1


@dataclass(frozen=True)
class _Entry:
    """待計算頁碼的目錄條目：層級、標題、目標段（章序 + 章內段序）。"""
    level: int
    title: str
    chapter: int
    para_in_chapter: int


def _first_page_of(result, para_idx: int) -> int:
    """段 para_idx 首次出現的版面頁號（章首＝節首＝該節首頁；小節＝該小節所在頁）。"""
    for page in result.pages:
        for pl in page.placed:
            if pl.para_idx == para_idx:
                return page.number
    raise BookError(f"目錄自動生成內部錯誤：段 {para_idx} 未出現於任何頁")


def _collect_entries(book: Book, chapters: dict) -> list:
    """依 manifest 序收集目錄條目：章條目在前，其章內小節依段序接續（Sprint 108）。

    層級一律顯式宣告：章取 chapters[].toc_level（預設 1）、章內小節取段落
    toc_level，未宣告者承所屬章層級 +1。引擎不從樣式名或字級反推階層。
    """
    entries: list = []
    for i, ch in enumerate(book.chapters):
        if ch.toc_spec:
            continue
        if ch.toc_title:
            entries.append(_Entry(ch.toc_level, ch.toc_title, i, 0))
        for j, para in enumerate(chapters[i]):
            if para.toc_title:
                level = para.toc_level if para.toc_level is not None else ch.toc_level + 1
                entries.append(_Entry(level, para.toc_title, i, j))
    return entries


def _assemble_pass1(book: Book, base: Path):
    """組裝含占位目錄條目（page_no=None）的段落列，回傳定分頁所需的中介資料。

    回傳 (paragraphs, entry_targets, entry_positions, entries, first_master)：
    - paragraphs：組裝後段落列（目錄條目 page_no=None）。
    - entry_targets：各條目的目標段在 paragraphs 的索引（與 entries 對齊）。
    - entry_positions：各目錄條目段在 paragraphs 的索引（與 entries 對齊）。
    - entries：_collect_entries 的條目序。
    - first_master：首節主版。

    各 path 章先行載入（章內小節宣告在章文件裡，須讀過才知條目數），再組裝。
    """
    if not any(ch.toc_spec for ch in book.chapters):
        raise BookError(
            "assemble_book_with_toc／toc_items 需書冊含 generate_toc 章；"
            "純 path 書冊請用 assemble_book"
        )
    chapters = {i: _resolve_chapter(ch, base, book.template, i)
                for i, ch in enumerate(book.chapters) if not ch.toc_spec}
    entries = _collect_entries(book, chapters)
    paragraphs: list = []
    chapter_offset: dict = {}
    entry_positions: list = []
    first_master: Optional[str] = None
    for i, ch in enumerate(book.chapters):
        if ch.toc_spec:
            spec = ch.toc_spec
            if spec.heading:
                paragraphs.append(Paragraph(
                    text=spec.heading, style=spec.heading_style, master=spec.master))
            elif not entries:
                raise BookError(
                    "自動目錄章無 heading 且無列入章（toc_title），無法產生節首段"
                )
            for k, entry in enumerate(entries):
                # 無 heading 時首條目承節首標記，其餘（含有 heading 者全部）承前段
                is_section_head = (not spec.heading) and k == 0
                entry_positions.append(len(paragraphs))
                paragraphs.append(Paragraph(
                    text=entry.title, style=spec.style_for_level(entry.level),
                    master=spec.master if is_section_head else None,
                    page_no=None))
            if first_master is None:
                first_master = spec.master
        else:
            chap = chapters[i]
            chapter_offset[i] = len(paragraphs)
            paragraphs.extend(chap)
            if first_master is None:
                first_master = chap[0].master
    entry_targets = [chapter_offset[e.chapter] + e.para_in_chapter for e in entries]
    return paragraphs, entry_targets, entry_positions, entries, first_master


def _build(book: Book, template, base: Path, first_page: int):
    """核心：兩趟分頁 → 回傳 (最終 Document, TocItem 序列)。"""
    paragraphs, entry_targets, entry_positions, entries, first_master = \
        _assemble_pass1(book, base)
    pass1 = Document(
        title=book.title, template=book.template, master=first_master,
        paragraphs=tuple(paragraphs), images=book.images, cover=book.cover)
    # 與 render／pdf_writer 同一重排入口（Sprint 103）：書冊帶 wrap 圖時，繞排會
    # 把內文往後推，用不繞排的分頁定條目頁碼會印出比實際早的頁（實測差 1 頁）。
    result = layout_with_wrap(pass1, template, first_page=first_page)
    items: list = []
    paras = list(paragraphs)
    for pos, target, entry in zip(entry_positions, entry_targets, entries):
        page = book_number_for(_first_page_of(result, target), first_page,
                               result.cover_pages)
        items.append(TocItem(title=entry.title, page=page, level=entry.level))
        paras[pos] = replace(paras[pos], page_no=str(page))
    final = Document(
        title=book.title, template=book.template, master=first_master,
        paragraphs=tuple(paras), images=book.images, cover=book.cover)
    return final, tuple(items)


def assemble_book_with_toc(book: Book, template, base_dir=None, first_page: int = 1) -> Document:
    """組裝書冊並自動填入目錄頁碼，回傳可直接 render／export 的 document@2 Document。

    first_page 須與最終 render／export 的 --first-page 一致（頁碼即依此換算書頁號）。
    """
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    return _build(book, template, base, first_page)[0]


def toc_items(book: Book, template, base_dir=None, first_page: int = 1) -> tuple:
    """只計算不組裝：回傳各列入章的 (標題, 書頁號) TocItem 序列（manifest 序）。"""
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    return _build(book, template, base, first_page)[1]
