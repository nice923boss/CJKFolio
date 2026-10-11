"""從此段起新頁（Sprint 158）：對任一段設或取消「換頁不換主版」的節首標記。

Owner：「我要讓這個標題後也能直接換到下一頁」，指的是內文中段的小標（如「二、光華
商場裡的音響店」）移到下一頁開頭。本專案換頁只有一個機制：Paragraph.master 節首
標記（同名主版亦強制分頁，見 layout._sections）。故「起新頁」＝把該段標成節首，
主版沿用它所在節現行的主版（同 section_editing.apply_page_starts 的換頁不換主版）。
手動空行推行（Sprint 141）在前文一改就會錯位，這個標記則永遠落在頁首。

置入圖與文字框以版面頁號錨定，換頁後其後的頁會順移，故另給 page_mapping／
remap_page_refs：以每頁第一行（段索引＋該段第幾行）為錨點，查它在新版面落在哪一頁。
沒有內文行的頁（封面、裝訂補頁）：封面在書首不動，其餘按距書末的頁數對應（封底圖
留在末頁）。
"""
from dataclasses import replace

from .document import Document
from .layout import _sections
from .section_editing import set_section_master


def _section_master_at(document: Document, para_idx: int) -> str:
    return next(m for m, lo, hi in _sections(document) if lo <= para_idx < hi)


def _check_index(document: Document, para_idx: int) -> None:
    if not 0 <= para_idx < len(document.paragraphs):
        raise IndexError(f"para_idx {para_idx} 超出段落範圍 0..{len(document.paragraphs) - 1}")


def start_page_at(document: Document, para_idx: int) -> Document:
    """自第 para_idx 段起新頁，主版不換；已是節首或段 0 回原物件（no-op）。越界 IndexError。"""
    _check_index(document, para_idx)
    if para_idx == 0 or document.paragraphs[para_idx].master is not None:
        return document
    return set_section_master(document, para_idx, _section_master_at(document, para_idx))


def clear_page_start(document: Document, para_idx: int) -> Document:
    """取消第 para_idx 段的起新頁（併回前一節）；本來就不是節首回原物件。

    只收「換頁不換主版」的節首：主版與前一節不同者（部扉、個案扉頁、目錄等）取消
    會連帶改掉主版，raise ValueError 請改用頁面面板右鍵「取消節首」。段 0 的節首
    存於 doc.master，無前一節可併，同樣 raise ValueError。
    """
    _check_index(document, para_idx)
    master = document.paragraphs[para_idx].master
    if para_idx == 0:
        raise ValueError("第一段本來就在書首，沒有可取消的換頁")
    if master is None:
        return document
    previous = _section_master_at(document, para_idx - 1)
    if master != previous:
        raise ValueError(
            f"本段是主版「{master}」的節首（前一節為「{previous}」），取消會連主版一起改；"
            "請用頁面面板右鍵「取消節首」")
    return set_section_master(document, para_idx, None)


def _line_keys(pages):
    """逐行錨點 (段索引, 該段第幾行, 版面頁號)，依版面順序。"""
    seen = {}
    for page in pages:
        for pl in page.placed:
            if pl.para_idx is None:
                continue
            nth = seen.get(pl.para_idx, 0)
            seen[pl.para_idx] = nth + 1
            yield (pl.para_idx, nth), page.number


def page_mapping(old_pages, new_pages) -> dict:
    """舊版面頁號 → 新版面頁號（段落不增減、只改換頁位置時用）。

    有內文行的頁：取該頁第一行，查它在新版面落在哪一頁。沒有內文行的頁：在第一個
    有字頁之前（封面）不動；在最後一個有字頁之後（裝訂補頁）按距書末的頁數對應
    （不超過新末頁）；夾在中間的跟著前一個有字頁平移。末頁恆對應末頁：補頁被內文
    填滿時封底圖會落在有字的末頁，之後內文再變長，它仍要留在末頁而非夾進書中。
    """
    new_at = dict(_line_keys(new_pages))
    first_key = {}
    for key, number in _line_keys(old_pages):
        first_key.setdefault(number, key)
    anchored = sorted(first_key)
    tail = len(new_pages) - len(old_pages)
    mapping, prev = {}, None
    for page in old_pages:
        n = page.number
        if n in first_key:
            mapping[n] = new_at.get(first_key[n], n)
            prev = n
        elif prev is None:
            mapping[n] = n
        elif n > anchored[-1]:
            mapping[n] = min(len(new_pages), max(mapping[anchored[-1]] + 1, n + tail))
        else:
            mapping[n] = mapping[prev] + (n - prev)
    if old_pages:  # 末頁＝封底（Sprint 144 末紙面單頁），不論有沒有字都留在末頁
        mapping[len(old_pages)] = len(new_pages)
    return mapping


def remap_page_refs(document: Document, mapping: dict) -> Document:
    """依 page_mapping 改置入圖與文字框的頁號；頁號都沒變回原物件。"""
    images = tuple(replace(im, page=mapping.get(im.page, im.page)) for im in document.images)
    frames = tuple(replace(tf, page=mapping.get(tf.page, tf.page))
                   for tf in document.text_frames)
    if images == document.images and frames == document.text_frames:
        return document
    return replace(document, images=images, text_frames=frames)
