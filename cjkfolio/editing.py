"""文件編輯回路（Phase 2 編輯引擎核心）：游標插字 → reflow → 反查新游標。

純邏輯層（不碰 Qt／渲染），與 layout/engine 同屬 cjkfolio 核心、入 pytest 基線。
編輯器 GUI（editor/）呼叫本層：畫布點選得文件游標（editor.canvas.resolve_hit
的 para_idx／span），IME 提交文字經 apply_insert 插入 → layout_with_wrap 全文重排
→ locate_cell 反查新游標畫布落點。這是 §7 Pre-mortem「畫布與排版核心同步／選取
錯位」風險的可離屏驗證核心（IME 鍵盤輸入本身仍待 Owner 真視窗實測，GAPS #19）。

重排入口＝layout_with_wrap（Sprint 103）而非 layout_document：與 render／pdf_writer
兩後端同一入口，故編輯器畫布所見的斷行就是匯出所得。無 wrap 圖時它原樣回傳
layout_document 的結果（wrap=False 為預設，既有輸出零變更）。

游標座標系：DocCursor.caret＝段 text（normalize 前原字串）半開座標 [0, len]，
與 Cell.span（Sprint 18 provenance）同座標系；插字與反查全在此座標系閉環。
本檔為純文件編輯函式層；EditSession（undo／redo 會談控制器）自 Sprint 67 依行數
紀律分檔移至 cjkfolio/session.py。
"""
from dataclasses import dataclass, replace
from typing import Optional

from .document import Document, Paragraph, Run
from .layout import LayoutResult
from .wrap import layout_with_wrap
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
    new_para = replace(para, runs=tuple(runs))
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

    新 caret＝原 caret＋len(text)（落在最後一個插入字之後）；版面由 layout_with_wrap
    確定性重排（Spike 3 實測純邏輯重排 7.67ms/章，互動級）。
    """
    new_doc = insert_text(doc, cursor, text)
    new_layout = layout_with_wrap(new_doc, template)
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
    new_para = replace(para, text="", runs=tuple(new_runs))
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
    new_layout = layout_with_wrap(new_doc, template)
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
    new_layout = layout_with_wrap(new_doc, template)
    new_cursor = DocCursor(drange.para_idx, drange.start + len(text))
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


@dataclass(frozen=True)
class DocSpan:
    """跨段選取範圍：起訖兩個 DocCursor 界定（start ≤ end，段索引優先再比 caret）。

    DocRange 為段內範圍（單一 para_idx＋caret 區間）；DocSpan 一般化為可跨段選取，
    同段（start.para_idx==end.para_idx）退化為段內範圍。start==end 為空範圍（刪除
    no-op、替換退化為純插入）。座標系同 DocCursor.caret（段 text 半開座標）。
    """

    start: DocCursor
    end: DocCursor


def _slice_runs(runs: tuple, start: int, end: int) -> list:
    """runs 串接文字 [start, end) 對應的 run 序列（邊界 run 切割、保字元樣式、濾空段）。"""
    out = []
    base = 0
    for r in runs:
        rend = base + len(r.text)
        lo, hi = max(start, base), min(end, rend)
        if lo < hi:
            out.append(Run(r.text[lo - base : hi - base], r.char_style))
        base = rend
    return out


def _validate_span(doc: Document, span: DocSpan) -> None:
    """DocSpan 系統邊界檢查：para_idx 越界 IndexError、caret 越界或起點晚於終點 ValueError。"""
    n_para = len(doc.paragraphs)
    for c in (span.start, span.end):
        if not 0 <= c.para_idx < n_para:
            raise IndexError(f"para_idx {c.para_idx} 超出段落範圍 0..{n_para - 1}")
    if not 0 <= span.start.caret <= len(doc.paragraphs[span.start.para_idx].text):
        raise ValueError(f"起點 caret {span.start.caret} 超出段 {span.start.para_idx} text 範圍")
    if not 0 <= span.end.caret <= len(doc.paragraphs[span.end.para_idx].text):
        raise ValueError(f"終點 caret {span.end.caret} 超出段 {span.end.para_idx} text 範圍")
    if (span.start.para_idx, span.start.caret) > (span.end.para_idx, span.end.caret):
        raise ValueError(
            f"範圍起點（段 {span.start.para_idx} caret {span.start.caret}）"
            f"晚於終點（段 {span.end.para_idx} caret {span.end.caret}）"
        )


def delete_span(doc: Document, span: DocSpan) -> Document:
    """刪除跨段選取範圍 [start, end)，回傳新 Document（不可變；空範圍 no-op 回原物件）。

    同段退化為段內範圍刪除（委派 delete_range）。跨段時：頭段保留 start 之前、尾段保留
    end 之後，兩者併為一段承頭段樣式與 page_no（頭段存活，同 merge_paragraph 慣例），
    中間整段一併移除；兩端 run 各保字元樣式，全刪空則正規化為單一空 run（守 document@2）。
    系統邊界快速失敗：para_idx 越界 IndexError、caret 越界或起點晚於終點 ValueError。
    """
    _validate_span(doc, span)
    if span.start == span.end:  # 空範圍 no-op
        return doc
    a, b = span.start.para_idx, span.end.para_idx
    if a == b:  # 同段退化＝段內範圍刪除
        return delete_range(doc, DocRange(a, span.start.caret, span.end.caret))
    para_a = doc.paragraphs[a]
    para_b = doc.paragraphs[b]
    merged_runs = _slice_runs(para_a.runs, 0, span.start.caret) + _slice_runs(
        para_b.runs, span.end.caret, len(para_b.text)
    )
    merged = replace(para_a, text="", runs=tuple(merged_runs))
    new_paras = doc.paragraphs[:a] + (merged,) + doc.paragraphs[b + 1 :]
    return replace(doc, paragraphs=new_paras)


def replace_span(doc: Document, span: DocSpan, text: str) -> Document:
    """以 text 替換跨段選取範圍 [start, end)，回傳新 Document（不可變）。

    等價於 delete_span 後於縫（start.para_idx, start.caret）插入 text；新字承接縫左側 run
    的字元樣式（同 insert_text 慣例）。text 為空＝退化為純刪除。
    """
    deleted = delete_span(doc, span)
    return insert_text(deleted, DocCursor(span.start.para_idx, span.start.caret), text)


def apply_delete_span(doc: Document, template: Template, span: DocSpan) -> EditResult:
    """完整編輯回路：跨段刪除 → 全文 reflow → 反查新游標畫布落點。

    新 caret＝縫（start.para_idx, start.caret）；全刪空時該段無可見字格，address None。
    """
    new_doc = delete_span(doc, span)
    new_layout = layout_with_wrap(new_doc, template)
    new_cursor = DocCursor(span.start.para_idx, span.start.caret)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


def apply_replace_span(
    doc: Document, template: Template, span: DocSpan, text: str
) -> EditResult:
    """完整編輯回路：跨段替換 → 全文 reflow → 反查新游標畫布落點。

    新 caret＝start.caret＋len(text)（落在最後一個新字之後、同一頭段內）。
    """
    new_doc = replace_span(doc, span, text)
    new_layout = layout_with_wrap(new_doc, template)
    new_cursor = DocCursor(span.start.para_idx, span.start.caret + len(text))
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
    字元樣式名是否存在於模版不在此驗（純文件層），由 apply_style 的 layout_with_wrap 守門。
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
    new_para = replace(para, text="", runs=tuple(new_runs))
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
    字格 char_style 隨 run 模型流入渲染層。未知字元樣式名由 layout_with_wrap 守門（raise KeyError）。
    """
    new_doc = apply_char_style(doc, drange, char_style)
    new_layout = layout_with_wrap(new_doc, template)
    new_cursor = DocCursor(drange.para_idx, drange.end)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


def apply_char_style_span(
    doc: Document, span: DocSpan, char_style: Optional[str]
) -> Document:
    """對跨段選取範圍 [start, end) 逐段套（或清）字元樣式 char_style，回傳新 Document（不可變）。

    段界不併（字元樣式不改變段落數量，別於 delete_span）：頭段套 [start, len)、中間段整段、
    尾段套 [0, end)，各段委派段內 apply_char_style（逐 run 切割＋相鄰同樣式併合）。同段
    （start.para_idx==end.para_idx）退化為段內 apply_char_style。空範圍 no-op 回原物件。
    系統邊界快速失敗同 delete_span（para_idx 越界 IndexError、caret 越界或起點晚於終點
    ValueError）；字元樣式名有效性不在此驗（純文件層），由 apply_style_span 的 layout_with_wrap 守門。
    """
    _validate_span(doc, span)
    if span.start == span.end:  # 空範圍 no-op
        return doc
    a, b = span.start.para_idx, span.end.para_idx
    if a == b:  # 同段退化＝段內套字元樣式
        return apply_char_style(doc, DocRange(a, span.start.caret, span.end.caret), char_style)
    # 跨段：逐段套各自子範圍（段界不併，各段保身分；套字元樣式不改 text，段長不變）
    result = apply_char_style(
        doc, DocRange(a, span.start.caret, len(doc.paragraphs[a].text)), char_style
    )
    for idx in range(a + 1, b):
        result = apply_char_style(
            result, DocRange(idx, 0, len(doc.paragraphs[idx].text)), char_style
        )
    return apply_char_style(result, DocRange(b, 0, span.end.caret), char_style)


def apply_style_span(
    doc: Document, template: Template, span: DocSpan, char_style: Optional[str]
) -> EditResult:
    """完整編輯回路：跨段套字元樣式 → 全文 reflow → 反查游標畫布落點。

    新 caret＝span.end（游標停在選取範圍尾）；套用不改 text，故 Cell.span 座標系不動、
    字格 char_style 隨 run 模型流入渲染層。未知字元樣式名由 layout_with_wrap 守門（raise KeyError）。
    """
    new_doc = apply_char_style_span(doc, span, char_style)
    new_layout = layout_with_wrap(new_doc, template)
    new_cursor = DocCursor(span.end.para_idx, span.end.caret)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )


def change_paragraph_style(doc: Document, para_idx: int, style: str) -> Document:
    """把段 para_idx 的段落樣式改為 style，回傳新 Document（不可變）。

    只換 Paragraph.style，其餘（runs 與字元樣式、page_no）不變；樣式相同為 no-op 回原
    物件。系統邊界快速失敗：para_idx 越界 raise IndexError；style 空字串 raise ValueError
    （守 document@2「段落需非空 style」不變式）。段落樣式名是否存在於模版不在此驗（純文件
    層），由 apply_para_style 的 layout_with_wrap 守門（raise KeyError，同 apply_char_style
    ／apply_style 慣例）。
    """
    if not 0 <= para_idx < len(doc.paragraphs):
        raise IndexError(
            f"para_idx {para_idx} 超出段落範圍 0..{len(doc.paragraphs) - 1}"
        )
    if not style:
        raise ValueError("段落樣式名不得為空字串")
    para = doc.paragraphs[para_idx]
    if para.style == style:  # 樣式無變化 no-op
        return doc
    new_para = replace(para, style=style)
    new_paras = (
        doc.paragraphs[:para_idx]
        + (new_para,)
        + doc.paragraphs[para_idx + 1 :]
    )
    return replace(doc, paragraphs=new_paras)


def change_paragraph_styles(doc: Document, assignments) -> Document:
    """多段批次改派段落樣式（Sprint 79，§4.4 逐段校正的核心半邊）。

    assignments＝{para_idx: 樣式名}；逐段委派 change_paragraph_style（越界
    IndexError／空名 ValueError 同守門），全數等值 no-op 回原物件。樣式名
    存在性由 session 全文重排守門（同單段慣例）。
    """
    out = doc
    for para_idx in sorted(assignments):
        out = change_paragraph_style(out, para_idx, assignments[para_idx])
    return out


def set_section_master(
    document: Document, para_idx: int, master: Optional[str]
) -> Document:
    """指派第 para_idx 段起的節式主版，回傳新 Document（不可變）。

    節式主版模型（Sprint 51／52）：主版按「節」指派，非逐頁自由套。三種情形：

    - para_idx==0 且段 0 無自帶 master：改的是首節預設主版 doc.master（寫回
      meta.master），不設段落標記（首節主版存 doc.master，無節首標記可設）。
    - para_idx==0 且段 0 自帶 master（自蓋首節）：改段 0 的節首標記；清成 None
      即退回 doc.master 預設（有前設可承，不 raise）。
    - para_idx>0：設 Paragraph.master 節首標記＝自該段起新開一頁並切主版
      （None＝承前節，清標記併回前節）。同名亦強制分頁的語意由版面層處理，本
      函式只管文件模型。

    系統邊界快速失敗：para_idx 越界 raise IndexError；首節（段 0 無自帶 master）
    清成 None（無前節可承）raise ValueError。等值為 no-op 回原物件。主版名是否存
    在於模版不在此驗（純文件層），由 session 全文重排守門（raise KeyError，同
    change_paragraph_style 慣例）。
    """
    if not 0 <= para_idx < len(document.paragraphs):
        raise IndexError(
            f"para_idx {para_idx} 超出段落範圍 0..{len(document.paragraphs) - 1}"
        )
    para = document.paragraphs[para_idx]
    if para_idx == 0 and para.master is None:
        # 首節：主版存於 doc.master（無節首標記可設；清 None 無前節可承）
        if master is None:
            raise ValueError("首節主版不得清除（無前節可承）")
        if document.master == master:  # 主版無變化 no-op
            return document
        return replace(document, master=master)
    if para.master == master:  # 節首標記無變化 no-op
        return document
    new_para = replace(para, master=master)
    new_paras = (
        document.paragraphs[:para_idx]
        + (new_para,)
        + document.paragraphs[para_idx + 1 :]
    )
    return replace(document, paragraphs=new_paras)


def apply_para_style(
    doc: Document, template: Template, cursor: DocCursor, style: str
) -> EditResult:
    """完整編輯回路：改游標所在段的段落樣式 → 全文 reflow → 反查游標畫布落點。

    改 cursor.para_idx 段的段落樣式為 style；段落樣式變更不改 text，故游標（para_idx／
    caret）保持不變，reflow 後 locate_cell 反查該游標的新畫布落點（換行／換頁時畫布落點
    隨版面更新，文件座標不動）。未知段落樣式名由 layout_with_wrap 守門（raise KeyError）。
    """
    new_doc = change_paragraph_style(doc, cursor.para_idx, style)
    new_layout = layout_with_wrap(new_doc, template)
    address = locate_cell(new_layout, cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=cursor, address=address
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
    head = replace(para, text="", runs=tuple(head_runs))  # 節首與目錄身分留 head（同 page_no 慣例）
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
    merged = replace(prev, text="", runs=merged_runs)  # 前段存活：本段節首與目錄標記隨併入消失
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
    new_layout = layout_with_wrap(new_doc, template)
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
    new_layout = layout_with_wrap(new_doc, template)
    new_cursor = DocCursor(para_idx - 1, seam)
    address = locate_cell(new_layout, new_cursor)
    return EditResult(
        document=new_doc, layout=new_layout, cursor=new_cursor, address=address
    )



def rename_paragraph_style_refs(doc: Document, old: str, new: str) -> Document:
    """全文件段落樣式參照改名（段落＋文字框，Sprint 75）；無參照回原物件。

    模版側鍵／based_on／md_mapping 同步在 style_editing.rename_paragraph_style，
    兩側由 session.rename_para_style 成對入單一 undo 步。
    """
    if new == old:
        return doc
    if not any(p.style == old for p in doc.paragraphs) and not any(
            f.style == old for f in doc.text_frames):
        return doc
    return replace(
        doc,
        paragraphs=tuple(
            replace(p, style=new) if p.style == old else p
            for p in doc.paragraphs),
        text_frames=tuple(
            replace(f, style=new) if f.style == old else f
            for f in doc.text_frames),
    )


def rename_char_style_refs(doc: Document, old: str, new: str) -> Document:
    """全文件字元樣式參照改名（run 級，Sprint 75）；無參照回原物件。文字不動、
    Paragraph 正規化不變式（text＝runs 串接）自然保持。"""
    if new == old or not any(
            r.char_style == old for p in doc.paragraphs for r in p.runs):
        return doc
    return replace(
        doc,
        paragraphs=tuple(
            replace(p, runs=tuple(
                replace(r, char_style=new) if r.char_style == old else r
                for r in p.runs))
            if any(r.char_style == old for r in p.runs) else p
            for p in doc.paragraphs),
    )
