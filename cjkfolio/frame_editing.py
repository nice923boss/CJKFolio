"""框內編輯核心（Sprint 59）：insert／delete 入框＋apply 回路＋框游標跟隨。

編輯對象＝文字來源框（source_idx＝串接鏈首；獨立框＝自身）的 text；框為單段
單一樣式純文字（無 runs，Sprint 55），插刪＝字串切接。重佈局走
resolve_text_frames（body layout 不動＝框編輯不影響流排）；游標落點以框 cells
span（Sprint 58 provenance，座標＝來源 text）反查。與 editing.py（body 編輯）
同層分檔（行數上限管理，先例 images.py／pdfx_meta.py）。
"""
from dataclasses import dataclass, replace
from typing import Optional

from .document import Document
from .frames import masters_for_layout, resolve_text_frames
from .layout import LayoutResult
from .styles import Template


@dataclass(frozen=True)
class FrameCursor:
    """框游標：文字來源框索引（串接鏈首；獨立框＝自身）＋來源 text 半開座標 caret。"""

    source_idx: int
    caret: int


@dataclass(frozen=True)
class FrameCellAddress:
    """框字格位址（resolve_frame_hit 之 (frame_idx, line_idx, cell_idx) 對偶）。"""

    page_number: int
    frame_idx: int
    line_idx: int
    cell_idx: int


@dataclass(frozen=True)
class FrameEditResult:
    """一次框編輯的完整結果：新文件＋框鏈重佈局＋新框游標。

    layout＝body 版面原物件（框編輯不重排流排）；placements_by_page＝
    resolve_text_frames 產物（含 frame_idx／source_idx）。"""

    document: Document
    layout: LayoutResult
    placements_by_page: dict
    cursor: FrameCursor
    address: Optional[FrameCellAddress]  # None＝該游標無可見框字格可落


def _source_frame(doc: Document, source_idx: int):
    """取文字來源框；索引越界／對象為串接續框（無文字）快速失敗。"""
    if not 0 <= source_idx < len(doc.text_frames):
        raise IndexError(
            f"source_idx {source_idx} 超出 text_frames 範圍 0..{len(doc.text_frames) - 1}"
        )
    tf = doc.text_frames[source_idx]
    if not tf.text:
        raise ValueError(
            f"text_frames[{source_idx}] 為串接續框（無文字）；"
            "框編輯請對鏈首（文字來源框 source_idx）"
        )
    return tf


def _replace_frame_text(doc: Document, source_idx: int, new_text: str) -> Document:
    frames = list(doc.text_frames)
    frames[source_idx] = replace(frames[source_idx], text=new_text)
    return replace(doc, text_frames=tuple(frames))


def insert_frame_text(doc: Document, cursor: FrameCursor, text: str) -> Document:
    """在框游標處插入 text，回傳新 Document（不可變；空字串 no-op 回原物件）。

    框無 runs：新字承接框單一段落樣式（無字元樣式承接問題）。
    系統邊界快速失敗：source_idx 越界／續框／caret 越界即 raise。
    """
    if not text:
        return doc
    tf = _source_frame(doc, cursor.source_idx)
    if not 0 <= cursor.caret <= len(tf.text):
        raise ValueError(f"caret {cursor.caret} 超出框 text 範圍 0..{len(tf.text)}")
    return _replace_frame_text(
        doc, cursor.source_idx,
        tf.text[:cursor.caret] + text + tf.text[cursor.caret:],
    )


def delete_frame_range(doc: Document, source_idx: int, start: int, end: int) -> Document:
    """刪除框 text [start, end) 範圍，回傳新 Document（不可變；空範圍 no-op）。

    全刪空快速失敗：框 text 非空為 document@2 解析層不變式（鏈首／獨立框皆然），
    移除整個框請刪 text_frames 條目（「空框」schema 演進另議）。
    """
    tf = _source_frame(doc, source_idx)
    if not (0 <= start <= end <= len(tf.text)):
        raise ValueError(
            f"刪除範圍 [{start}, {end}) 不合法（框 text 長 {len(tf.text)}，"
            "需 0 ≤ start ≤ end ≤ 長度）"
        )
    if start == end:
        return doc
    new_text = tf.text[:start] + tf.text[end:]
    if not new_text:
        raise ValueError(
            f"text_frames[{source_idx}] 不可刪空（框 text 非空為 document@2 不變式；"
            "移除整個框請刪 text_frames 條目）"
        )
    return _replace_frame_text(doc, source_idx, new_text)


def locate_frame_cell(
    placements_by_page: dict, cursor: FrameCursor
) -> Optional[FrameCellAddress]:
    """框游標 → 框字格位址（resolve_frame_hit 的逆；span 座標＝來源 text）。

    找 source_idx 相符 placements 中涵蓋 caret−1（caret==0 取第 0 字）的字格；
    span 沿串接鏈遞增不相交，命中唯一。查無（無此來源框或該字未繪）回 None。
    """
    target = cursor.caret - 1 if cursor.caret > 0 else 0
    for page_number in sorted(placements_by_page):
        for pl in placements_by_page[page_number]:
            if pl.source_idx != cursor.source_idx:
                continue
            for li, fl in enumerate(pl.lines):
                for ci, cell in enumerate(fl.line.cells):
                    if cell.span is None:
                        continue
                    s, e = cell.span
                    if s <= target < e:
                        return FrameCellAddress(page_number, pl.frame_idx, li, ci)
    return None


def _apply(
    template: Template, layout: LayoutResult, new_doc: Document, cursor: FrameCursor
) -> FrameEditResult:
    placements = resolve_text_frames(
        new_doc, template, masters_for_layout(template, new_doc, layout))
    return FrameEditResult(
        document=new_doc, layout=layout, placements_by_page=placements,
        cursor=cursor, address=locate_frame_cell(placements, cursor),
    )


def apply_frame_insert(
    doc: Document, template: Template, layout: LayoutResult,
    cursor: FrameCursor, text: str,
) -> FrameEditResult:
    """完整框編輯回路：插字 → 框鏈重佈局（body layout 不動）→ 反查新框游標落點。

    新 caret＝原 caret＋len(text)；插字可使文字跨框流動（串接），落點自動跟隨。
    """
    new_doc = insert_frame_text(doc, cursor, text)
    return _apply(template, layout, new_doc,
                  FrameCursor(cursor.source_idx, cursor.caret + len(text)))


def apply_frame_delete(
    doc: Document, template: Template, layout: LayoutResult,
    source_idx: int, start: int, end: int,
) -> FrameEditResult:
    """完整框刪除回路：刪範圍 → 框鏈重佈局 → 游標落縫（start）。"""
    new_doc = delete_frame_range(doc, source_idx, start, end)
    return _apply(template, layout, new_doc, FrameCursor(source_idx, start))
