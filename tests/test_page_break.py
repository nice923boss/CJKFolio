"""從此段起新頁（cjkfolio/page_break.py＋EditSession.start_page_at，Sprint 158）。

Owner：「我要讓這個標題後也能直接換到下一頁」，選定把小標移到下一頁開頭。本測試釘住：

1. 起新頁＝該段落在新頁第一行、主版沿用所在節；段 0 與已是節首者 no-op。
2. 取消起新頁還原原文件；主版不同的節首（部扉、目錄等）拒收並指向「取消節首」。
3. 置入圖頁號跟著內容順移；封面圖不動，末頁（裝訂補頁）的封底圖留在末頁。
4. session 單一 undo 步、游標落在該段段首。

素材用本專案自擬模版與樣張（版權紅線）。
"""
from dataclasses import replace
from pathlib import Path

import pytest

from cjkfolio.document import PlacedImage, load_document
from cjkfolio.page_break import (
    clear_page_start,
    page_mapping,
    refs_past_end,
    remap_page_refs,
    start_page_at,
)
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from cjkfolio.wrap import layout_with_wrap

ROOT = Path(__file__).resolve().parents[1]
BODY = "A-內文版"
MID = 6  # 樣張段 6 從第 2 頁第 5 行起


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


@pytest.fixture(scope="module")
def doc():
    return load_document(ROOT / "samples" / "paiban-xiaoji-ch1.doc.json")


def _where(layout, para_idx):
    for page in layout.pages:
        for k, pl in enumerate(page.placed):
            if pl.para_idx == para_idx:
                return page.number, k
    raise AssertionError(para_idx)


def test_paragraph_moves_to_top_of_next_page(template, doc):
    page, line = _where(layout_with_wrap(doc, template), MID)
    assert line > 0
    new = start_page_at(doc, MID)
    assert new.paragraphs[MID].master == BODY
    assert _where(layout_with_wrap(new, template), MID) == (page + 1, 0)


def test_noop_on_first_paragraph_and_existing_break(template, doc):
    assert start_page_at(doc, 0) is doc
    once = start_page_at(doc, MID)
    assert start_page_at(once, MID) is once
    with pytest.raises(IndexError):
        start_page_at(doc, len(doc.paragraphs))


def test_clear_restores_and_refuses_master_change(template, doc):
    assert clear_page_start(start_page_at(doc, MID), MID) == doc
    assert clear_page_start(doc, MID) is doc
    other = next(m for m in template.masters if m != BODY)
    titled = replace(doc, paragraphs=tuple(
        replace(p, master=other) if i == MID else p for i, p in enumerate(doc.paragraphs)))
    with pytest.raises(ValueError, match="取消節首"):
        clear_page_start(titled, MID)
    with pytest.raises(ValueError):
        clear_page_start(doc, 0)


def test_images_follow_content_and_back_cover_stays_last(template, doc):
    src = replace(doc, cover=BODY, sheet_pages=8)
    old = layout_with_wrap(src, template)
    last = len(old.pages)
    assert old.pages[-1].blank
    body_page = _where(old, 30)[0]
    new_doc = start_page_at(src, MID)
    new = layout_with_wrap(new_doc, template)
    mapping = page_mapping(old.pages, new.pages)
    assert mapping[1] == 1
    assert mapping[last] == len(new.pages)
    assert mapping[body_page] == _where(new, old.pages[body_page - 1].placed[0].para_idx)[0]
    imgs = (PlacedImage(path="c.png", page=1, rect=(0.0, 0.0, 10.0, 10.0)),
            PlacedImage(path="b.png", page=body_page, rect=(0.0, 0.0, 10.0, 10.0)),
            PlacedImage(path="z.png", page=last, rect=(0.0, 0.0, 10.0, 10.0)))
    moved = remap_page_refs(replace(new_doc, images=imgs), mapping)
    assert [im.page for im in moved.images] == [1, mapping[body_page], len(new.pages)]


def test_session_single_undo_and_cursor(template, doc):
    s = EditSession(doc, template)
    pages = len(s.layout.pages)
    result = s.start_page_at(MID)
    assert result is not None and s.cursor.para_idx == MID and s.cursor.caret == 0
    assert _where(s.layout, MID)[1] == 0 and len(s.layout.pages) >= pages
    assert s.start_page_at(MID) is None
    s.undo()
    assert s.document is doc
    s.redo()
    assert s.clear_page_start(MID) is not None
    assert s.document.paragraphs == doc.paragraphs


def test_last_page_with_text_still_maps_to_last(template, doc):
    """補頁被內文填滿時封底圖落在有字的末頁；之後再起新頁，它仍跟到新末頁。"""
    old = layout_with_wrap(doc, template)  # 11 頁、無補頁，末頁有字
    assert not old.pages[-1].blank
    new = layout_with_wrap(start_page_at(doc, MID), template)
    assert len(new.pages) > len(old.pages)
    assert page_mapping(old.pages, new.pages)[len(old.pages)] == len(new.pages)


def test_snap_past_end_moves_back_cover_to_last_page(template, doc):
    """全書變短後封底圖落到書外：開檔一步移回末頁，書內的圖不動，undo 回原。"""
    s = EditSession(doc, template)
    last = len(s.layout.pages)
    imgs = (PlacedImage(path="c.png", page=1, rect=(0.0, 0.0, 10.0, 10.0)),
            PlacedImage(path="z.png", page=last + 4, rect=(0.0, 0.0, 10.0, 10.0)))
    s = EditSession(replace(doc, images=imgs), template)
    assert refs_past_end(s.document, last) == (f"置入圖「z.png」頁 {last + 4}",)
    assert s.snap_past_end() is not None
    assert [im.page for im in s.document.images] == [1, last]
    assert refs_past_end(s.document, last) == () and s.snap_past_end() is None
    s.undo()
    assert s.document.images == imgs


def test_cover_image_shows_although_another_page_is_out_of_range(template, doc, tmp_path):
    """一張圖頁號超出全書，不再連累封面（之前整本每頁都不顯示圖）。"""
    from PIL import Image

    from editor.canvas import page_images

    Image.new("RGB", (8, 8), "red").save(tmp_path / "c.png")
    layout = layout_with_wrap(doc, template)
    bad = replace(doc, images=(
        PlacedImage(path="c.png", page=1, rect=(0.0, 0.0, 10.0, 10.0)),
        PlacedImage(path="z.png", page=len(layout.pages) + 4, rect=(0.0, 0.0, 10.0, 10.0))))
    assert len(page_images(template, bad, layout, layout.pages[0], base_dir=tmp_path)) == 1
