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


@dataclass(frozen=True)
class DocRange:
    """段內文字範圍：段索引＋段 text 半開區間 [start, end)（同 DocCursor caret 座標系）。

    v1 為段內範圍（不跨段）；start==end 為空範圍（刪除 no-op、替換退化為純插入）。
    """

    para_idx: int
    start: int
    end: int


def delete_range(doc: Document, drange: DocRange) -> Document:
    """刪除段內 [start, end) 範圍文字，回傳新 Document（不可變；空範圍 no-op 回原物件）。

    範圍橫跨多 run 時逐 run 切除交集、保留兩端 run 及其字元樣式；整個 run 落在範圍
    內則該 run 連同樣式一併消失。全段刪空回合法空段（text 為空，Paragraph 正規化為單一空 run）。
    系統邊界快速失敗：para_idx 越界 raise IndexError；start/end 越界或 start>end raise ValueError。
    """
    if not 0 <= drange.para_idx < len(doc.paragraphs):
        raise IndexError(
            f"para_idx {drange.para_idx} 超出段落範圍 0..{len(doc.paragraphs) - 1}"
        )
    para = doc.paragraphs[drange.para_idx]
    n = len(para.text)
    if not 0 <= drange.start <= n or not 0 <= drange.end <= n:
        raise ValueError(f"範圍 [{drange.start}, {drange.end}) 超出段 text 範圍 0..{n}")
    if drange.start > drange.end:
        raise ValueError(f"範圍起點 {drange.start} 大於終點 {drange.end}")
    if drange.start == drange.end:
        return doc
    new_runs = []
    base = 0
    for r in para.runs:
        kept = "".join(
            ch
            for j, ch in enumerate(r.text)
            if not (drange.start <= base + j < drange.end)
        )
        if kept:
            new_runs.append(Run(kept, r.char_style))
        base += len(r.text)
    new_para = Paragraph(style=para.style, runs=tuple(new_runs), page_no=para.page_no)
    new_paras = (
        doc.paragraphs[: drange.para_idx]
        + (new_para,)
        + doc.paragraphs[drange.para_idx + 1 :]
    )
    return replace(doc, paragraphs=new_paras)


def replace_range(doc: Document, drange: DocRange, text: str) -> Document:
    """以 text 替換段內 [start, end) 範圍，回傳新 Document（不可變）。

    等價於刪除範圍後於 start 插入 text；新字承接 start 左側 run 的字元樣式（同
    insert_text「新字繼承游標前樣式」慣例）。text 為空＝退化為純刪除。
    """
    deleted = delete_range(doc, drange)
    return insert_text(deleted, DocCursor(drange.para_idx, drange.start), text)


def apply_delete(doc: Document, template: Template, drange: DocRange) -> EditResult:
    """完整編輯回路：刪範圍 → 全文 reflow → 反查新游標畫布落點。

    新 caret＝drange.start（刪除點，落在殘存文字之間）；全段刪空時該段無可見字格，
    locate_cell 回 None（address=None，合法）。
    """
    new_doc = delete_range(doc, drange)
    new_layout = layout_document(new_doc, template)
    new_cursor = DocCursor(drange.para_idx, drange.start)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


def apply_replace(
    doc: Document, template: Template, drange: DocRange, text: str
) -> EditResult:
    """完整編輯回路：替換範圍 → 全文 reflow → 反查新游標畫布落點。

    新 caret＝drange.start＋len(text)（落在最後一個新字之後）。
    """
    new_doc = replace_range(doc, drange, text)
    new_layout = layout_document(new_doc, template)
    new_cursor = DocCursor(drange.para_idx, drange.start + len(text))
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


def apply_char_style(
    doc: Document, drange: DocRange, char_style: Optional[str]
) -> Document:
    """對段內 [start, end) 範圍套（或清）字元樣式 char_style，回傳新 Document（不可變）。

    範圍內每個字元改掛 char_style（None＝清除字元樣式、回段落樣式預設）；範圍外字元
    保留原字元樣式。切割後連續同字元樣式的字元併為單一 run（避免碎片化，text 與視覺
    不變，同 InDesign 套字元樣式慣例）。空範圍（start==end）no-op 回原物件。
    系統邊界快速失敗：para_idx 越界 raise IndexError；start/end 越界或 start>end raise ValueError。
    字元樣式名是否存在於模版不在此驗（純文件層），由 apply_style 的 layout_document 守門。
    """
    if not 0 <= drange.para_idx < len(doc.paragraphs):
        raise IndexError(
            f"para_idx {drange.para_idx} 超出段落範圍 0..{len(doc.paragraphs) - 1}"
        )
    para = doc.paragraphs[drange.para_idx]
    n = len(para.text)
    if not 0 <= drange.start <= n or not 0 <= drange.end <= n:
        raise ValueError(f"範圍 [{drange.start}, {drange.end}) 超出段 text 範圍 0..{n}")
    if drange.start > drange.end:
        raise ValueError(f"範圍起點 {drange.start} 大於終點 {drange.end}")
    if drange.start == drange.end:
        return doc
    new_runs = []
    base = 0
    for r in para.runs:
        for j, ch in enumerate(r.text):
            style = char_style if drange.start <= base + j < drange.end else r.char_style
            if new_runs and new_runs[-1].char_style == style:  # 併入相鄰同樣式 run
                new_runs[-1] = Run(new_runs[-1].text + ch, style)
            else:
                new_runs.append(Run(ch, style))
        base += len(r.text)
    new_para = Paragraph(style=para.style, runs=tuple(new_runs), page_no=para.page_no)
    new_paras = (
        doc.paragraphs[: drange.para_idx]
        + (new_para,)
        + doc.paragraphs[drange.para_idx + 1 :]
    )
    return replace(doc, paragraphs=new_paras)


def apply_style(
    doc: Document, template: Template, drange: DocRange, char_style: Optional[str]
) -> EditResult:
    """完整編輯回路：套字元樣式 → 全文 reflow → 反查新游標畫布落點。

    新 caret＝drange.end（游標停在選取範圍尾）；套用不改 text，故 Cell.span 座標系不動、
    字格 char_style 隨 run 模型流入渲染層。未知字元樣式名由 layout_document 守門（raise KeyError）。
    """
    new_doc = apply_char_style(doc, drange, char_style)
    new_layout = layout_document(new_doc, template)
    new_cursor = DocCursor(drange.para_idx, drange.end)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


def split_paragraph(doc: Document, cursor: DocCursor) -> Document:
    """在 cursor 處把段落切成 head（caret 前）／tail（caret 後）兩段，回傳新 Document。

    兩段同承原段落樣式；page_no 留於 head（保有原段身分），tail 為 None。跨 run 切割
    時 caret 所在 run 一分為二、兩側各保字元樣式；空側正規化為單一空 run（守 document@2
    不變式）。系統邊界快速失敗：para_idx 越界 raise IndexError、caret 越界 raise ValueError。
    """
    if not 0 <= cursor.para_idx < len(doc.paragraphs):
        raise IndexError(
            f"para_idx {cursor.para_idx} 超出段落範圍 0..{len(doc.paragraphs) - 1}"
        )
    para = doc.paragraphs[cursor.para_idx]
    if not 0 <= cursor.caret <= len(para.text):
        raise ValueError(f"caret {cursor.caret} 超出段 text 範圍 0..{len(para.text)}")
    head_runs = []
    tail_runs = []
    base = 0
    for r in para.runs:
        end = base + len(r.text)
        if end <= cursor.caret:  # 整個 run 在 caret 前
            if r.text:
                head_runs.append(r)
        elif base >= cursor.caret:  # 整個 run 在 caret 後
            if r.text:
                tail_runs.append(r)
        else:  # run 跨越 caret，一分為二（兩側各保 char_style）
            local = cursor.caret - base
            if r.text[:local]:
                head_runs.append(Run(r.text[:local], r.char_style))
            if r.text[local:]:
                tail_runs.append(Run(r.text[local:], r.char_style))
        base = end
    head = Paragraph(style=para.style, runs=tuple(head_runs), page_no=para.page_no)
    tail = Paragraph(style=para.style, runs=tuple(tail_runs), page_no=None)
    new_paras = (
        doc.paragraphs[: cursor.para_idx]
        + (head, tail)
        + doc.paragraphs[cursor.para_idx + 1 :]
    )
    return replace(doc, paragraphs=new_paras)


def merge_paragraph(doc: Document, para_idx: int) -> Document:
    """把段 para_idx 併入前段 para_idx−1，回傳新 Document（Backspace 於段首）。

    合併段承前段樣式與 page_no（前段存活，InDesign 慣例：併入前段承其樣式）；runs＝
    前段 runs＋本段 runs、濾除空 run，全空則正規化為單一空 run（守 document@2 不變式）。
    系統邊界快速失敗：para_idx < 1 或越界 raise IndexError（para_idx 0 無前段可併）。
    """
    if not 1 <= para_idx < len(doc.paragraphs):
        raise IndexError(
            f"para_idx {para_idx} 無前段可併（合法範圍 1..{len(doc.paragraphs) - 1}）"
        )
    prev = doc.paragraphs[para_idx - 1]
    cur = doc.paragraphs[para_idx]
    merged_runs = tuple(r for r in (prev.runs + cur.runs) if r.text)
    merged = Paragraph(style=prev.style, runs=merged_runs, page_no=prev.page_no)
    new_paras = (
        doc.paragraphs[: para_idx - 1]
        + (merged,)
        + doc.paragraphs[para_idx + 1 :]
    )
    return replace(doc, paragraphs=new_paras)


def apply_split(doc: Document, template: Template, cursor: DocCursor) -> EditResult:
    """完整編輯回路：分段 → 全文 reflow → 反查新游標畫布落點。

    新游標＝tail 段起點（para_idx+1, caret 0）；tail 為空段時無可見字格，address None。
    """
    new_doc = split_paragraph(doc, cursor)
    new_layout = layout_document(new_doc, template)
    new_cursor = DocCursor(cursor.para_idx + 1, 0)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


def apply_merge(doc: Document, template: Template, para_idx: int) -> EditResult:
    """完整編輯回路：併段 → 全文 reflow → 反查新游標畫布落點。

    新游標＝合併縫（para_idx−1, 前段原長）＝前段末字與併入內容之間；合併段全空時
    無可見字格，address None。
    """
    new_doc = merge_paragraph(doc, para_idx)
    seam = len(doc.paragraphs[para_idx - 1].text)  # 前段原長（para_idx 已由 merge 驗證合法）
    new_layout = layout_document(new_doc, template)
    new_cursor = DocCursor(para_idx - 1, seam)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


class EditSession:
    """編輯會談：文件＋游標的 undo／redo 歷史（可變控制器，純邏輯離屏可驗）。

    現態＝(document, cursor, layout)；undo／redo 各持 (document, cursor) 快照堆疊，採
    標準「回上一個提交態」模型：一次編輯把編輯前的 (document, cursor) 推入 undo 並清空
    redo；undo 把現態推入 redo、彈回上一態並全文重排（Spike 3 認可 7.67ms/章，非增量），
    redo 對稱。初始游標＝段 0 caret 0（UI 點選另覆寫；v1 undo 還原上一提交態游標，不追
    UI 中途點選）。app.py 尚未接線 undo／redo（GAPS #24／#19 待 Owner 真視窗）。
    """

    def __init__(self, document: Document, template: Template):
        self._template = template
        self._document = document
        self._cursor = DocCursor(0, 0)
        self._layout = layout_document(document, template)
        self._undo: list = []  # [(document, cursor)]，最舊→最新
        self._redo: list = []

    @property
    def document(self) -> Document:
        return self._document

    @property
    def cursor(self) -> DocCursor:
        return self._cursor

    @property
    def layout(self) -> LayoutResult:
        return self._layout

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def _commit(self, result: EditResult) -> EditResult:
        """把現態存入 undo、清 redo，切換至編輯結果（供各編輯方法共用）。"""
        self._undo.append((self._document, self._cursor))
        self._redo.clear()
        self._document = result.document
        self._cursor = result.cursor
        self._layout = result.layout
        return result

    def insert(self, cursor: DocCursor, text: str) -> EditResult:
        return self._commit(apply_insert(self._document, self._template, cursor, text))

    def delete(self, drange: DocRange) -> EditResult:
        return self._commit(apply_delete(self._document, self._template, drange))

    def replace(self, drange: DocRange, text: str) -> EditResult:
        return self._commit(apply_replace(self._document, self._template, drange, text))

    def split(self, cursor: DocCursor) -> EditResult:
        return self._commit(apply_split(self._document, self._template, cursor))

    def merge(self, para_idx: int) -> EditResult:
        return self._commit(apply_merge(self._document, self._template, para_idx))

    def apply_style(self, drange: DocRange, char_style: Optional[str]) -> EditResult:
        return self._commit(
            apply_style(self._document, self._template, drange, char_style)
        )

    def _restore(self, document: Document, cursor: DocCursor) -> EditResult:
        """切換現態至還原的 (document, cursor)、全文重排、反查游標畫布落點。"""
        self._document = document
        self._cursor = cursor
        self._layout = layout_document(document, self._template)
        return EditResult(
            document=document,
            layout=self._layout,
            cursor=cursor,
            address=locate_cell(self._layout, cursor),
        )

    def undo(self) -> Optional[EditResult]:
        """回退一步至上一提交態；無可回退回 None（no-op）。"""
        if not self._undo:
            return None
        self._redo.append((self._document, self._cursor))
        document, cursor = self._undo.pop()
        return self._restore(document, cursor)

    def redo(self) -> Optional[EditResult]:
        """重做一步至下一提交態；無可重做回 None（no-op）。"""
        if not self._redo:
            return None
        self._undo.append((self._document, self._cursor))
        document, cursor = self._redo.pop()
        return self._restore(document, cursor)
