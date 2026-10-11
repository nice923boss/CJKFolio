"""刪頁、插頁後自動更新目次頁碼（Sprint 155）。

Owner 選 C：刪頁插頁後目次頁碼自動跟著變，另有右鍵「更新目次頁碼」一鍵重算。
頁碼一律拿「獨立重算的內文起始頁」對答案（Gate 4），不採信 refresh 自己填的值。
測試素材一律自擬（版權紅線）。
"""
import dataclasses
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.primitives import book_number_for
from cjkfolio.section_editing import move_section
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from cjkfolio.toc import document_with_toc, refresh_toc_page_numbers
from cjkfolio.wrap import layout_with_wrap

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"
BODY = "內文-明體直排"
FILLER = "這是一段用來把版面撐開的內文，重複多次以確保章與章之間跨頁。" * 6
TOC_LEN = 5  # 目次節：標題段 1 ＋ 條目 4（部 1、章 3）
EPIGRAPH = "題詞：獻給一路同行的人。"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(template):
    """部名（層 1、不標頁碼）＋題詞頁＋三章（層 2），生成目次後回傳。"""
    paras = [Paragraph(text="第一篇　當回憶逐漸堆疊", style="部扉大標-明體W9",
                       master="B-部扉", toc_title="第一篇　當回憶逐漸堆疊", toc_level=1),
             Paragraph(text=EPIGRAPH, style=BODY, master="A-內文版")]
    for n in range(3):
        title = f"第 {n + 1} 章"
        paras.append(Paragraph(text=title, style="章名大標-明體W7", master="A-內文版",
                               toc_title=title, toc_level=2))
        paras.append(Paragraph(text=FILLER, style=BODY))
    src = Document(title="目次更新試", template="neizai-zhengli", master="B-部扉",
                   paragraphs=tuple(paras))
    return document_with_toc(src, template)


def page_of(result, para_idx: int) -> int:
    for page in result.pages:
        if any(pl.para_idx == para_idx for pl in page.placed):
            return page.number
    raise AssertionError(f"段 {para_idx} 未出現於任何頁")


def expected_numbers(doc, template):
    """獨立重算：條目段 → 對應章首所在書頁號；層 1（部名）不標頁碼＝None。"""
    result = layout_with_wrap(doc, template)
    targets = [i for i, p in enumerate(doc.paragraphs) if p.toc_title]
    out = []
    for target in targets:
        p = doc.paragraphs[target]
        out.append(None if p.toc_level == 1 else
                   str(book_number_for(page_of(result, target), 1, result.cover_pages)))
    return out


def toc_numbers(doc):
    return [p.page_no for p in doc.paragraphs[1:TOC_LEN]]


def epigraph_idx(doc):
    return next(i for i, p in enumerate(doc.paragraphs) if p.text == EPIGRAPH)


def test_fresh_toc_needs_no_change(template):
    doc = make_doc(template)
    refresh = refresh_toc_page_numbers(doc, template)
    assert (refresh.entries, refresh.changed, refresh.problem) == (4, 0, "")
    assert refresh.document is doc


def test_document_without_toc_is_left_alone(template):
    doc = make_doc(template)
    body = dataclasses.replace(doc, master="A-內文版", paragraphs=doc.paragraphs[TOC_LEN:])
    refresh = refresh_toc_page_numbers(body, template)
    assert (refresh.entries, refresh.changed) == (0, 0)
    assert refresh.document is body


def test_delete_page_updates_toc_in_same_undo_step(template):
    doc = make_doc(template)
    session = EditSession(doc, template)
    idx = epigraph_idx(doc)
    page = page_of(session.layout, idx)
    before = toc_numbers(doc)
    session.delete_page(page, idx, idx + 1)
    after = session.document
    assert toc_numbers(after) == expected_numbers(after, template)
    assert toc_numbers(after) != before, "刪題詞頁後章首頁應往前移"
    assert session.last_toc_refresh.changed == 3
    session.undo()
    assert session.document is doc, "刪頁與頁碼更新應同屬一個 undo 步"


def test_insert_blank_page_updates_toc(template):
    doc = make_doc(template)
    session = EditSession(doc, template)
    idx = epigraph_idx(doc)
    page = page_of(session.layout, idx)
    session.insert_blank_page(idx, page, "A-內文版")
    after = session.document
    assert toc_numbers(after) == expected_numbers(after, template)
    assert [int(n) for n in toc_numbers(after)[1:]] == [
        int(n) + 1 for n in toc_numbers(doc)[1:]], "插一頁後各章頁碼應各加 1"
    assert toc_numbers(after)[0] is None, "層 1 部名條目依模版不標頁碼"


def test_images_on_body_pages_do_not_block_refresh(template):
    """重算不插新節，內文頁上的置入圖不會錯頁，故不像生成目次那樣擋下。"""
    doc = make_doc(template)
    with_image = dataclasses.replace(
        doc, images=(PlacedImage("a.png", 5, (10.0, 10.0, 50.0, 50.0)),))
    session = EditSession(with_image, template)
    idx = epigraph_idx(doc)
    session.delete_page(page_of(session.layout, idx), idx, idx + 1)
    assert toc_numbers(session.document) == expected_numbers(session.document, template)


def test_mismatched_entries_are_reported_not_guessed(template):
    """章首段的條目宣告被拿掉（如章首頁被刪）：條目數對不上，頁碼不動並說明。"""
    doc = make_doc(template)
    chapter = next(i for i, p in enumerate(doc.paragraphs) if p.toc_title == "第 2 章")
    paras = list(doc.paragraphs)
    paras[chapter] = dataclasses.replace(paras[chapter], toc_title=None, toc_level=None)
    broken = dataclasses.replace(doc, paragraphs=tuple(paras))
    refresh = refresh_toc_page_numbers(broken, template)
    assert refresh.document is broken
    assert "目次有 4 條、內文宣告 3 條" in refresh.problem


def test_reordered_chapters_are_reported_not_misassigned(template):
    """章節搬過順序（條目數相同）：照位置對會把頁碼填給別章，故比對文字後拒填。"""
    doc = make_doc(template)
    moved = move_section(doc, 5, 4)  # 第 3 章搬到第 2 章前（節 0 為目次節）
    refresh = refresh_toc_page_numbers(moved, template)
    assert refresh.document is moved
    assert "目次第 3 條「第 2 章」與內文宣告「第 3 章」對不上" in refresh.problem


def test_manual_refresh_fixes_stale_numbers_and_is_noop_when_fresh(template):
    doc = make_doc(template)
    paras = list(doc.paragraphs)
    paras[2] = dataclasses.replace(paras[2], page_no="99")
    stale = dataclasses.replace(doc, paragraphs=tuple(paras))
    session = EditSession(stale, template)
    assert session.refresh_toc() is not None
    assert toc_numbers(session.document) == toc_numbers(doc)
    assert session.last_toc_refresh.changed == 1
    assert session.refresh_toc() is None, "頁碼已對時不應再入 undo"
    session.undo()
    assert session.document is stale
