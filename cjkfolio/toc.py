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


class TocError(ValueError):
    """單文件自動目錄生成失敗（Sprint 135）。"""


def _body_of(doc: Document, spec):
    """拆掉文件開頭的既有自動目錄節，回傳 (內文段落列, 內文首節主版)。

    判準：文件首節主版＝spec.master 即視為自動目錄節（本模組生成的節恆如此），
    整節換掉使「AI 指派 → 生成目錄」可重複執行而不疊加。使用者自己以目錄主版
    起頭的手寫目錄同樣會被換掉，這是本判準的已知代價（首節主版即為節的身分，
    不另加「這是系統生成的」旗標去污染 document@2 schema）。
    """
    paras = doc.paragraphs
    if doc.master != spec.master or not paras:
        return paras, doc.master
    if paras[0].master not in (None, spec.master):
        return paras, doc.master
    for i in range(1, len(paras)):
        if paras[i].master is not None:
            return paras[i:], paras[i].master
    return (), doc.master


def _manual_toc_styles(spec) -> frozenset:
    return frozenset({spec.heading_style, *spec.entry_styles.values()} - {None})


def manual_toc_indices(doc: Document, spec) -> tuple:
    """內文中掛目錄類樣式、且自身不宣告目錄條目的段序（＝作者手寫目錄）。"""
    styles = _manual_toc_styles(spec)
    body, _ = _body_of(doc, spec)
    offset = len(doc.paragraphs) - len(body)
    return tuple(offset + i for i, p in enumerate(body)
                 if p.style in styles and not p.toc_title)


def _drop_manual_toc(body, spec) -> tuple:
    """拿掉手寫目錄段；被拿掉段的節首主版標記轉給下一個留下的段（節不消失）。"""
    styles = _manual_toc_styles(spec)
    kept, carry = [], None
    for p in body:
        if p.style in styles and not p.toc_title:
            carry = p.master if p.master is not None else carry
            continue
        if carry is not None and p.master is None:
            p = replace(p, master=carry)
        carry = None
        kept.append(p)
    return tuple(kept)


def document_with_toc(doc: Document, template, *, first_page: int = 1,
                      spec=None, drop_manual: bool = False) -> Document:
    """單份稿件於書首生成自動目錄節，回傳可直接 render／export 的 Document。

    條目來源＝段落自身宣告的 toc_title／toc_level（未宣告層級者視為第 1 層）；
    層級一律顯式，引擎不從樣式名或字級反推階層（同 book 路徑的紀律）。

    兩趟穩定分頁（無 fixpoint，同 _build）：目錄條目數為先驗定值，且 page_no 是
    非流排載體（掛段末行、不影響斷行），故 Pass 1 以 page_no=None 的條目占位排一次
    即定分頁，Pass 2 填書頁號不再動分頁。spec.no_page_levels 宣告的層級不填頁碼
    （參考書 p002／p003 的部名條目即如此）。

    first_page 須與最終 render／export 的 --first-page 一致，頁碼才對得上。

    drop_manual（Sprint 149）：一併拿掉內文中的手寫目錄（掛目錄標題或條目樣式、
    自身不宣告條目的段）。匯入的稿件常自帶一份打字的目錄，不拿掉就與生成的目次
    並排成兩份。判準靠樣式（AI 指派或使用者手動套的目錄類樣式），不猜文字內容。
    """
    spec = spec if spec is not None else getattr(template, "auto_toc", None)
    if spec is None:
        raise TocError(
            "模版未宣告 auto_toc，無法生成自動目錄"
            "（模版需宣告目錄主版與各層條目樣式）")
    # 置入圖與獨立文字框皆以版面頁號錨定，插入目錄節會把內文流整體往後推而使其
    # 錯頁，故擋下不沉默產出圖文錯頁的稿件。但封面（版面頁 1，layout 不吃內文流）
    # 在流之前，目錄節插在流首不動它，故封面上的書名框與置圖放行：編輯器匯入預設
    # 就建封面（import_actions cover=default_cover），一律擋等於 Owner 的
    # 「匯入 → AI 指派 → 生成目次」整條路徑撞牆。
    cover_pages = 1 if doc.cover is not None else 0
    on_flow = ([f"置入圖 p.{im.page}" for im in doc.images if im.page > cover_pages]
               + [f"文字框 p.{f.page}" for f in doc.text_frames
                  if f.page > cover_pages])
    if on_flow:
        raise TocError(
            f"文件有 {len(on_flow)} 個以內文頁號錨定的置入圖或獨立文字框"
            f"（{'、'.join(on_flow[:3])}{'…' if len(on_flow) > 3 else ''}），"
            "插入目錄節會使其錯頁；請先移除，或改走書冊自動目錄"
            "（assemble_book_with_toc）")
    body, body_master = _body_of(doc, spec)
    if drop_manual:
        body = _drop_manual_toc(body, spec)
    if not body:
        raise TocError("文件無內文段落，無法生成目錄")
    entries = [(i, p.toc_title, 1 if p.toc_level is None else p.toc_level)
               for i, p in enumerate(body) if p.toc_title]
    if not entries:
        raise TocError(
            "沒有任何段落宣告目錄條目（toc_title），無條目可生成目錄")

    toc_paras: list = []
    if spec.heading:
        toc_paras.append(Paragraph(text=spec.heading, style=spec.heading_style,
                                   master=spec.master))
    for _, title, level in entries:
        # 無 heading 時首條目承節首標記，其餘承前段（同 _assemble_pass1）
        head = spec.master if not toc_paras else None
        toc_paras.append(Paragraph(text=title, style=spec.style_for_level(level),
                                   master=head, page_no=None))
    # 內文首段顯式承接原首節主版：目錄節插到它前面後，原本靠 doc.master 隱含
    # 繼承的段落會改繼承目錄主版（節式主版規則），不明寫即整份內文掛錯主版。
    body = (replace(body[0], master=body_master), *body[1:])

    pass1 = replace(doc, master=spec.master, paragraphs=(*toc_paras, *body))
    result = layout_with_wrap(pass1, template, first_page=first_page)
    offset = len(toc_paras)
    entry_pos = 1 if spec.heading else 0
    paras = list(pass1.paragraphs)
    for k, (body_idx, _title, level) in enumerate(entries):
        if not spec.wants_page_no(level):
            continue
        page = book_number_for(_first_page_of(result, offset + body_idx),
                               first_page, result.cover_pages)
        paras[entry_pos + k] = replace(paras[entry_pos + k], page_no=str(page))
    return replace(pass1, paragraphs=tuple(paras))


@dataclass(frozen=True)
class TocRefresh:
    """目次頁碼重算結果（Sprint 155）。entries＝0 即文件沒有目次節（不算錯）。"""
    document: Document
    entries: int = 0
    changed: int = 0
    problem: str = ""  # 非空＝條目對不上內文，頁碼未動


def refresh_toc_page_numbers(doc: Document, template, *,
                             first_page: int = 1) -> TocRefresh:
    """依現行版面重算書首目次節的條目頁碼，條目文字與節結構一律不動（Sprint 155）。

    刪頁、插頁後內文起始頁會移動，但目次條目數不變，故不必像 document_with_toc
    重建目次節：照順序把目次條目（掛條目樣式的段）對到內文宣告 toc_title 的段，
    排一次版面填頁碼即準（page_no 不影響斷行，填值不改分頁）。不插新節，所以內文頁
    上有置入圖、文字框也不受擋。

    條目數或條目文字與內文宣告對不上（目次頁或章首頁被刪過、章節搬過順序、條目
    文字改過）時不猜對應，原文件照回並在 problem 說明，交由使用者重新生成目次。
    """
    spec = getattr(template, "auto_toc", None)
    if spec is None:
        return TocRefresh(doc)
    body, _ = _body_of(doc, spec)
    offset = len(doc.paragraphs) - len(body)
    if offset == 0:
        return TocRefresh(doc)
    entry_styles = frozenset(spec.entry_styles.values())
    slots = [i for i in range(offset) if doc.paragraphs[i].style in entry_styles]
    targets = [(offset + i, 1 if p.toc_level is None else p.toc_level, p.toc_title)
               for i, p in enumerate(body) if p.toc_title]
    redo = "目次頁碼未更新；請重新執行 AI 指派並勾生成目次頁"
    if len(slots) != len(targets):
        return TocRefresh(doc, len(slots), problem=(
            f"目次有 {len(slots)} 條、內文宣告 {len(targets)} 條，對不上，{redo}"))
    for k, (slot, (_, _, title)) in enumerate(zip(slots, targets)):
        if doc.paragraphs[slot].text != title:  # 章節搬過或條目文字改過：不猜對應
            return TocRefresh(doc, len(slots), problem=(
                f"目次第 {k + 1} 條「{doc.paragraphs[slot].text}」與內文宣告"
                f"「{title}」對不上，{redo}"))
    result = layout_with_wrap(doc, template, first_page=first_page)
    paras = list(doc.paragraphs)
    changed = 0
    for slot, (target, level, _) in zip(slots, targets):
        if not spec.wants_page_no(level):
            continue
        page_no = str(book_number_for(_first_page_of(result, target), first_page,
                                      result.cover_pages))
        if paras[slot].page_no != page_no:
            paras[slot] = replace(paras[slot], page_no=page_no)
            changed += 1
    if not changed:
        return TocRefresh(doc, len(slots))
    return TocRefresh(replace(doc, paragraphs=tuple(paras)), len(slots), changed)

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
