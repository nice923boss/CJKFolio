"""文件編輯回路（Phase 2 編輯引擎核心）：游標插字 → reflow → 反查新游標。

純邏輯層（不碰 Qt／渲染），與 layout/engine 同屬 cjkfolio 核心、入 pytest 基線。
編輯器 GUI（editor/）呼叫本層：畫布點選得文件游標（editor.canvas.resolve_hit
的 para_idx／span），IME 提交文字經 apply_insert 插入 → layout_document 全文重排
→ locate_cell 反查新游標畫布落點。這是 §7 Pre-mortem「畫布與排版核心同步／選取
錯位」風險的可離屏驗證核心（IME 鍵盤輸入本身仍待 Owner 真視窗實測，GAPS #19）。

游標座標系：DocCursor.caret＝段 text（normalize 前原字串）半開座標 [0, len]，
與 Cell.span（Sprint 18 provenance）同座標系；插字與反查全在此座標系閉環。
v1 只做插入（IME 提交即插入）；刪除／選取範圍編輯為後續工程。
"""
from dataclasses import dataclass, replace
from typing import Optional

from .document import Document, Paragraph, Run
from .layout import LayoutResult, layout_document
from .styles import Template


@dataclass(frozen=True)
class DocCursor:
    """文件游標：段索引＋段 text 半開座標的 caret 位置（字元間隙，非字元索引）。"""

    para_idx: int
    caret: int


@dataclass(frozen=True)
class CellAddress:
    """畫布字格位址（reflow 後游標落點；resolve_hit 之 (placed_idx, cell_idx) 對偶）。"""

    page_number: int
    placed_idx: int
    cell_idx: int


@dataclass(frozen=True)
class EditResult:
    """一次編輯的完整結果：新文件＋新版面＋新游標（文件座標＋畫布落點）。"""

    document: Document
    layout: LayoutResult
    cursor: DocCursor  # 插入後 caret（段 text 座標）
    address: Optional[CellAddress]  # 新游標畫布落點（None＝該段無可見字格可落）


def insert_text(doc: Document, cursor: DocCursor, text: str) -> Document:
    """在 cursor 處插入 text，回傳新 Document（不可變；空字串為 no-op 回原物件）。

    caret 落在 run 邊界時併入左側 run，承接其字元樣式（符合輸入法「新字繼承游標前
    樣式」慣例）；caret==0 前插首 run。段其餘欄位（樣式、page_no）不變。
    系統邊界快速失敗：para_idx 或 caret 越界即 raise。
    """
    if not text:
        return doc
    if not 0 <= cursor.para_idx < len(doc.paragraphs):
        raise IndexError(
            f"para_idx {cursor.para_idx} 超出段落範圍 0..{len(doc.paragraphs) - 1}"
        )
    para = doc.paragraphs[cursor.para_idx]
    if not 0 <= cursor.caret <= len(para.text):
        raise ValueError(f"caret {cursor.caret} 超出段 text 範圍 0..{len(para.text)}")
    runs = list(para.runs)
    base = 0
    for k, r in enumerate(runs):
        end = base + len(r.text)
        if cursor.caret <= end:  # 邊界（caret==end）左偏＝併入本 run 尾
            local = cursor.caret - base
            runs[k] = Run(r.text[:local] + text + r.text[local:], r.char_style)
            break
        base = end
    else:  # caret ≤ len(text) 必落某 run，理論不可達；防禦性附加末 run
        runs[-1] = Run(runs[-1].text + text, runs[-1].char_style)
    new_para = Paragraph(style=para.style, runs=tuple(runs), page_no=para.page_no)
    new_paras = (
        doc.paragraphs[: cursor.para_idx]
        + (new_para,)
        + doc.paragraphs[cursor.para_idx + 1 :]
    )
    return replace(doc, paragraphs=new_paras)


def locate_cell(layout: LayoutResult, cursor: DocCursor) -> Optional[CellAddress]:
    """文件游標 → 畫布字格位址（resolve_hit 的逆）。

    以 Cell.span 反查：找 para_idx 段中涵蓋 caret 前一字（caret−1）的字格；
    caret==0 時取涵蓋第 0 字者。段內 span 兩兩不相交且遞增，命中唯一。
    反查不到（段無可見字格，或段不在版面）回 None。
    """
    target = cursor.caret - 1 if cursor.caret > 0 else 0
    for page in layout.pages:
        for pi, pl in enumerate(page.placed):
            if pl.para_idx != cursor.para_idx:
                continue
            for ci, cell in enumerate(pl.line.cells):
                if cell.span is None:
                    continue
                s, e = cell.span
                if s <= target < e:
                    return CellAddress(page.number, pi, ci)
    return None


def apply_insert(
    doc: Document, template: Template, cursor: DocCursor, text: str
) -> EditResult:
    """完整編輯回路：插字 → 全文 reflow → 反查新游標畫布落點。

    新 caret＝原 caret＋len(text)（落在最後一個插入字之後）；版面由 layout_document
    確定性重排（Spike 3 實測純邏輯重排 7.67ms/章，互動級）。
    """
    new_doc = insert_text(doc, cursor, text)
    new_layout = layout_document(new_doc, template)
    new_cursor = DocCursor(cursor.para_idx, cursor.caret + len(text))
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )
