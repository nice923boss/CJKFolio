"""單文件自動目次（Sprint 135）：條目宣告落地、兩趟分頁頁碼、生成守門與單一 undo 步。

與 test_toc.py／test_toc_levels.py 分工：那兩份驗書冊路徑（cjkfolio/book@1 多章
manifest 的 generate_toc 章），本檔驗單份稿件路徑（toc.document_with_toc），即
編輯器「AI 樣式指派 → 生成目次頁」所走的那條。

頁碼一律拿「獨立重算的內文起始頁」對答案（Gate 4），不採信 document_with_toc
自己填進條目的值。測試素材一律自擬（版權紅線）。
"""
import dataclasses
from pathlib import Path

import pytest

from cjkfolio.cover import with_cover
from cjkfolio.document import Document, Paragraph, PlacedImage, TextFrame
from cjkfolio.editing import change_paragraph_toc_entries
from cjkfolio.primitives import book_number_for
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from cjkfolio.toc import TocError, document_with_toc
from cjkfolio.wrap import layout_with_wrap

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"
BODY = "內文-明體直排"
FILLER = "這是一段用來把版面撐開的內文，重複多次以確保章與章之間跨頁。" * 6
# 模版 auto_toc 宣告：第 1 層＝目錄-部名（no_page_levels 內，不標頁碼）、
# 第 2 層＝目錄-篇章條目（標頁碼）；標題段＝目次／目錄-目次標題。
TOC_LEN = 7  # 本檔 make_doc 的目次節長度：標題段 1 ＋ 條目 6


@pytest.fixture
def template():
    return load_template(TEMPLATE)


def make_doc():
    """兩部各兩章的稿件：部名宣告層 1、章名宣告層 2，各章之間以長內文撐開跨頁。"""
    paras = []
    for part in ("第一篇　當回憶逐漸堆疊", "第二篇　當關係開始錯位"):
        paras.append(Paragraph(text=part, style="部扉大標-明體W9", master="B-部扉",
                               toc_title=part, toc_level=1))
        for n in range(2):
            title = f"{part[:3]}第 {n + 1} 章"
            paras.append(Paragraph(text=title, style="章名大標-明體W7",
                                   master="A-內文版", toc_title=title, toc_level=2))
            paras.append(Paragraph(text=FILLER, style=BODY))
    return Document(title="目次試", template="neizai-zhengli", master="B-部扉",
                    paragraphs=tuple(paras))


def first_page_of(result, para_idx: int):
    """段首次出現的版面頁號（獨立於 toc.py 的同名內部函式重寫，供 Gate 4 對答案）。"""
    for page in result.pages:
        for placed in page.placed:
            if placed.para_idx == para_idx:
                return page.number
    raise AssertionError(f"段 {para_idx} 未出現於任何頁")


def page_shape(result):
    """逐頁的 (段序, 槽位, 樣式) 序列＝分頁與斷行的形狀（不含 page_no 本身）。"""
    return [[(pl.para_idx, pl.slot, pl.style) for pl in page.placed]
            for page in result.pages]


# ── 生成結果的形狀 ────────────────────────────────────────────────────────

def test_toc_section_shape(template):
    src = make_doc()
    out = document_with_toc(src, template)
    assert len(out.paragraphs) == len(src.paragraphs) + TOC_LEN
    assert out.master == "D-目錄" and out.paragraphs[0].master == "D-目錄"
    assert (out.paragraphs[0].text, out.paragraphs[0].style) == ("目次", "目錄-目次標題")
    assert [p.style for p in out.paragraphs[1:TOC_LEN]] == [
        "目錄-部名", "目錄-篇章條目", "目錄-篇章條目",
        "目錄-部名", "目錄-篇章條目", "目錄-篇章條目"]
    # 條目文字取段落宣告的 toc_title，不是段落本文（兩者可不同）
    assert out.paragraphs[1].text == "第一篇　當回憶逐漸堆疊"
    # 標題段之後的條目一律不帶節首標記，整節同一張主版
    assert all(p.master is None for p in out.paragraphs[1:TOC_LEN])


def test_body_keeps_its_own_first_section_master(template):
    """目次節插到書首後，內文首段須顯式承接原首節主版，否則整份內文掛到目錄主版。"""
    out = document_with_toc(make_doc(), template)
    assert out.paragraphs[TOC_LEN].master == "B-部扉"


def test_page_numbers_match_independently_recomputed_body_pages(template):
    src = make_doc()
    out = document_with_toc(src, template)
    result = layout_with_wrap(out, template, first_page=1)
    entries = [(i, p) for i, p in enumerate(src.paragraphs) if p.toc_title]
    assert len(entries) == 6
    numbered = 0
    for k, (body_idx, para) in enumerate(entries):
        printed = out.paragraphs[1 + k].page_no
        if para.toc_level == 1:  # 模版 no_page_levels 宣告的層不標頁碼
            assert printed is None
            continue
        expect = book_number_for(first_page_of(result, TOC_LEN + body_idx), 1,
                                 result.cover_pages)
        assert printed == str(expect), f"{para.toc_title} 標 {printed}，實際起於 {expect}"
        numbered += 1
    assert numbered == 4  # 四章都標到頁碼，不是全數落在不標頁碼的層而靜默落空


def test_page_no_does_not_disturb_pagination(template):
    """page_no 是非流排載體：填了頁碼的最終稿與占位稿分頁必須一模一樣。"""
    out = document_with_toc(make_doc(), template)
    blank = dataclasses.replace(out, paragraphs=tuple(
        dataclasses.replace(p, page_no=None) for p in out.paragraphs))
    filled = layout_with_wrap(out, template, first_page=1)
    placeholder = layout_with_wrap(blank, template, first_page=1)
    assert len(filled.pages) == len(placeholder.pages)
    assert page_shape(filled) == page_shape(placeholder)
    # 差異只在 page_no 這個非流排載體本身
    assert any(pl.page_no for page in filled.pages for pl in page.placed)
    assert not any(pl.page_no for page in placeholder.pages for pl in page.placed)


def test_page_numbers_respect_first_page(template):
    """書頁號＝版面頁號 + first_page − 1：同一份稿件換 first_page 即整體位移。"""
    src = make_doc()
    at1 = document_with_toc(src, template, first_page=1)
    at30 = document_with_toc(src, template, first_page=30)
    paged = [(a.page_no, b.page_no)
             for a, b in zip(at1.paragraphs, at30.paragraphs) if a.page_no]
    assert len(paged) == 4
    assert all(int(b) - int(a) == 29 for a, b in paged)


def test_regeneration_replaces_not_stacks(template):
    """AI 指派可反覆執行：既有目次節整節換掉，不疊加第二份目次。"""
    once = document_with_toc(make_doc(), template)
    assert document_with_toc(once, template) == once


def test_regeneration_picks_up_edited_entries(template):
    """改過條目宣告再生成，目次跟著變（整節換掉而非只補新條目）。"""
    once = document_with_toc(make_doc(), template)
    edited = change_paragraph_toc_entries(once, {TOC_LEN: None})  # 撤掉第一個部名
    again = document_with_toc(edited, template)
    assert len(again.paragraphs) == len(once.paragraphs) - 1
    assert again.paragraphs[1].style == "目錄-篇章條目"


# ── 守門：全部快速失敗，不沉默降級 ────────────────────────────────────────

def test_no_auto_toc_in_template_fast_fail(template):
    bare = dataclasses.replace(template, auto_toc=None)
    with pytest.raises(TocError, match="auto_toc"):
        document_with_toc(make_doc(), bare)


def test_no_declared_entry_fast_fail(template):
    doc = Document(title="無條目", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="內文。", style=BODY),))
    with pytest.raises(TocError, match="toc_title"):
        document_with_toc(doc, template)


def test_page_anchored_image_fast_fail(template):
    """置入圖以版面頁號錨定，插入目次節會使其錯頁：擋在前面而不產出錯頁稿件。"""
    doc = dataclasses.replace(
        make_doc(), images=(PlacedImage(path="assets/x.png", page=1),))
    with pytest.raises(TocError, match="錯頁"):
        document_with_toc(doc, template)


def test_cover_anchored_frame_passes(template):
    """封面（版面頁 1，不吃內文流）上的書名框放行：目次節插在流首，不動封面。

    編輯器匯入稿件預設就建封面且帶書名框，一律擋等於整條「匯入 → AI 指派 →
    生成目次」路徑撞牆。頁碼仍自封面翻開後起算（book_number_for 的 cover_pages）。
    """
    src = with_cover(make_doc(), template, title="目次試")
    assert src.text_frames and src.text_frames[0].page == 1
    out = document_with_toc(src, template)
    assert out.cover == src.cover
    assert out.text_frames == src.text_frames        # 封面書名框零位移
    result = layout_with_wrap(out, template, first_page=1)
    assert result.pages[0].master == src.cover       # 版面頁 1 仍是封面
    entries = [p for p in out.paragraphs[:TOC_LEN] if p.page_no]
    body = [i for i, p in enumerate(out.paragraphs)
            if p.style == "章名大標-明體W7"]
    assert len(entries) == len(body) == 4
    for entry, idx in zip(entries, body):
        expect = book_number_for(first_page_of(result, idx), 1, result.cover_pages)
        assert entry.page_no == str(expect)


def test_flow_anchored_frame_still_fast_fail(template):
    """封面放行不擴及內文流頁：流排頁上的文字框仍擋，訊息指出是哪一頁。"""
    doc = with_cover(make_doc(), template, title="目次試")
    doc = dataclasses.replace(doc, text_frames=doc.text_frames + (
        TextFrame(text="邊註", style=BODY, page=3, rect=(10.0, 10.0, 60.0, 200.0)),))
    with pytest.raises(TocError, match="文字框 p.3"):
        document_with_toc(doc, template)


def test_undeclared_level_fast_fail(template):
    """層級未宣告條目樣式即失敗，不沉默落回第 1 層（會產出階層不見的目次）。"""
    src = make_doc()
    paras = list(src.paragraphs)
    paras[0] = dataclasses.replace(paras[0], toc_level=9)
    with pytest.raises(ValueError, match="第 9 層"):
        document_with_toc(dataclasses.replace(src, paragraphs=tuple(paras)), template)


# ── 條目宣告的批次編輯 ────────────────────────────────────────────────────

def test_change_toc_entries_sets_and_clears():
    doc = Document(title="t", template="neizai-zhengli", master="A-內文版", paragraphs=(
        Paragraph(text="第一章", style=BODY),
        Paragraph(text="舊條目", style=BODY, toc_title="舊標", toc_level=2),
    ))
    out = change_paragraph_toc_entries(doc, {0: ("　第一章　", 2), 1: None})
    # 標題前後空白照存檔端規矩去掉
    assert (out.paragraphs[0].toc_title, out.paragraphs[0].toc_level) == ("第一章", 2)
    assert out.paragraphs[1].toc_title is None and out.paragraphs[1].toc_level is None
    assert doc.paragraphs[0].toc_title is None  # 原件不變


def test_change_toc_entries_noop_returns_same_object():
    doc = Document(title="t", template="x", master="m", paragraphs=(
        Paragraph(text="甲", style=BODY, toc_title="甲", toc_level=1),))
    assert change_paragraph_toc_entries(doc, {0: ("甲", 1)}) is doc


@pytest.mark.parametrize("entry,match", [
    (("", 1), "不得為空"),
    (("  ", 1), "不得為空"),
    (("甲", True), "層級"),   # 真布林是 int 子類，會被當成層級 1，須擋
    (("甲", 0), "層級"),
    (("甲", "2"), "層級"),
])
def test_change_toc_entries_rejects_bad_payload(entry, match):
    doc = Document(title="t", template="x", master="m",
                   paragraphs=(Paragraph(text="甲", style=BODY),))
    with pytest.raises(ValueError, match=match):
        change_paragraph_toc_entries(doc, {0: entry})


def test_change_toc_entries_index_out_of_range():
    doc = Document(title="t", template="x", master="m",
                   paragraphs=(Paragraph(text="甲", style=BODY),))
    with pytest.raises(IndexError, match="越界"):
        change_paragraph_toc_entries(doc, {5: ("甲", 1)})


# ── 樣式＋條目＋生成目次＝單一 undo 步 ────────────────────────────────────

def test_apply_para_styles_batches_everything_into_one_undo_step(template):
    src = Document(title="t", template="neizai-zhengli", master="B-部扉", paragraphs=(
        Paragraph(text="第一篇　起", style=BODY, master="B-部扉"),
        Paragraph(text="第一章", style=BODY, master="A-內文版"),
        Paragraph(text=FILLER, style=BODY),
    ))
    session = EditSession(src, template)
    session.apply_para_styles(
        {0: "部扉大標-明體W9", 1: "章名大標-明體W7"},
        {0: ("第一篇　起", 1), 1: ("第一章", 2)},
        generate_toc=True)
    doc = session.document
    assert len(doc.paragraphs) == 6  # 標題段 1 ＋ 條目 2 ＋ 原 3 段
    assert doc.paragraphs[3].style == "部扉大標-明體W9"   # 樣式改派同批落地
    assert doc.paragraphs[3].toc_title == "第一篇　起"     # 條目宣告同批落地
    assert doc.paragraphs[2].page_no is not None          # 第 2 層條目標到頁碼
    session.undo()
    assert session.document == src and not session.can_undo()


def test_generate_toc_failure_leaves_state_untouched(template):
    src = Document(title="t", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(Paragraph(text="內文。", style=BODY),))
    session = EditSession(src, template)
    with pytest.raises(TocError):
        session.apply_para_styles({}, None, generate_toc=True)
    assert session.document is src and not session.can_undo()


def test_regenerating_identical_toc_is_a_noop(template):
    """內容相同的重生成不推一步「看不出差別」的 undo。"""
    session = EditSession(make_doc(), template)
    assert session.apply_para_styles({}, None, generate_toc=True) is not None
    assert session.apply_para_styles({}, None, generate_toc=True) is None
    session.undo()
    assert not session.can_undo()  # 全程只推了一步
