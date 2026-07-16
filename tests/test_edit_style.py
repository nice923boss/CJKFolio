"""編輯引擎字元樣式套用（cjkfolio/editing.py，Sprint 45）：對選取範圍套字元樣式。

承 Sprint 41〜44 編輯回路：apply_char_style 於 run 模型上對段內 [start, end) 半開
範圍套（或清）字元樣式，切割後連續同樣式併為單一 run；apply_style 為完整回路
（套樣式 → layout_document 全文重排 → locate_cell 反查新游標）；EditSession.apply_style
入 undo／redo 歷史。純邏輯離屏可驗，字元樣式名驗證由 layout_document 守門。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph, Run
from cjkfolio.editing import (
    DocCursor,
    DocRange,
    apply_char_style,
    apply_style,
)
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]

# 模版真有的字元樣式名（templates/neizai-zhengli.json）
EMPH = "內文強調-明體W9"
LABEL = "發言人標籤-黑體"
ROLE = "角色註記-仿宋小字"


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _plain(text: str, style: str = "內文-明體直排") -> Document:
    """A-內文版單段（單一無字元樣式 run）。"""
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=(Paragraph(text=text, style=style),))


def _para(runs, style: str = "內文-明體直排") -> Document:
    """A-內文版單段（指定 run 序列）。"""
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=(Paragraph(style=style, runs=tuple(runs)),))


def runs_of(para: Paragraph):
    return [(r.text, r.char_style) for r in para.runs]


# ---------- apply_char_style：純文件層 run 切割 ----------

def test_apply_prefix_of_single_run():
    out = apply_char_style(_plain("三房兩廳"), DocRange(0, 0, 2), EMPH)
    assert runs_of(out.paragraphs[0]) == [("三房", EMPH), ("兩廳", None)]


def test_apply_whole_para_single_run():
    # 整段套用＝單一 run，不碎片
    out = apply_char_style(_plain("三房兩廳"), DocRange(0, 0, 4), EMPH)
    assert runs_of(out.paragraphs[0]) == [("三房兩廳", EMPH)]


def test_apply_middle_splits_three():
    out = apply_char_style(_plain("甲乙丙丁戊"), DocRange(0, 1, 3), EMPH)
    assert runs_of(out.paragraphs[0]) == [("甲", None), ("乙丙", EMPH), ("丁戊", None)]


def test_apply_across_runs_coalesced():
    # 跨 run 統一為同一樣式 → 相鄰同樣式併為單一 run
    doc = _para([Run("甲乙", EMPH), Run("丙丁", None)])
    out = apply_char_style(doc, DocRange(0, 0, 4), LABEL)
    assert runs_of(out.paragraphs[0]) == [("甲乙丙丁", LABEL)]


def test_apply_none_clears_and_coalesces():
    # 套 None＝清除字元樣式，回段落樣式預設；與右側 None 相鄰併合
    doc = _para([Run("甲乙", EMPH), Run("丙丁", None)])
    out = apply_char_style(doc, DocRange(0, 0, 2), None)
    assert runs_of(out.paragraphs[0]) == [("甲乙丙丁", None)]


def test_apply_preserves_both_ends():
    # 兩端 run 各保原字元樣式，中段換新樣式
    doc = _para([Run("甲乙", EMPH), Run("丙丁戊", LABEL)])
    out = apply_char_style(doc, DocRange(0, 1, 4), ROLE)
    assert runs_of(out.paragraphs[0]) == [("甲", EMPH), ("乙丙丁", ROLE), ("戊", LABEL)]


def test_apply_empty_range_noop_returns_same():
    doc = _plain("三房兩廳")
    out = apply_char_style(doc, DocRange(0, 2, 2), EMPH)
    assert out is doc  # 空範圍 no-op 回原物件


def test_apply_is_immutable():
    doc = _plain("三房兩廳")
    apply_char_style(doc, DocRange(0, 0, 2), EMPH)
    assert runs_of(doc.paragraphs[0]) == [("三房兩廳", None)]  # 原文件不變


def test_apply_para_idx_out_of_range_raises():
    with pytest.raises(IndexError):
        apply_char_style(_plain("三房兩廳"), DocRange(5, 0, 2), EMPH)


def test_apply_end_out_of_range_raises():
    with pytest.raises(ValueError):
        apply_char_style(_plain("三房兩廳"), DocRange(0, 0, 9), EMPH)


def test_apply_start_gt_end_raises():
    with pytest.raises(ValueError):
        apply_char_style(_plain("三房兩廳"), DocRange(0, 3, 1), EMPH)


def test_apply_on_empty_para_noop():
    # 空段（單一空 run）：range 只能 [0,0) 空範圍 → no-op
    doc = _plain("")
    out = apply_char_style(doc, DocRange(0, 0, 0), EMPH)
    assert out is doc
    assert runs_of(out.paragraphs[0]) == [("", None)]


# ---------- apply_style：完整回路（套樣式 → reflow → 反查）----------

def test_apply_style_reflows_and_locates_cursor(template):
    doc = _plain("三房兩廳，約三十坪的老公寓。")
    res = apply_style(doc, template, DocRange(0, 0, 4), EMPH)
    # 文件層：範圍套 EMPH、其餘留 None、text 不變
    assert runs_of(res.document.paragraphs[0]) == [
        ("三房兩廳", EMPH), ("，約三十坪的老公寓。", None)
    ]
    assert res.document.paragraphs[0].text == "三房兩廳，約三十坪的老公寓。"
    assert doc.paragraphs[0].text == "三房兩廳，約三十坪的老公寓。"  # 原文件不變
    # reflow 乾淨、游標停選取尾 end=4、畫布落點反查範圍末字
    assert res.layout.violations == []
    assert res.cursor == DocCursor(0, 4)
    assert res.address is not None
    addr = res.address
    cell = res.layout.pages[addr.page_number - 1].placed[addr.placed_idx].line.cells[addr.cell_idx]
    assert cell.text == "廳"  # caret 4 反查 target 3＝範圍末字


def test_apply_style_cell_carries_new_style_end_to_end(template):
    # 端到端：套用後 layout 範圍內字格的 char_style＝新樣式（流入渲染層）
    doc = _plain("三房兩廳，約三十坪的老公寓。")
    res = apply_style(doc, template, DocRange(0, 0, 4), EMPH)
    styled = [
        c.char_style
        for pg in res.layout.pages
        for pl in pg.placed
        if pl.para_idx == 0
        for c in pl.line.cells
        if c.span and c.span[0] < 4
    ]
    assert styled and all(cs == EMPH for cs in styled)


def test_apply_style_unknown_char_style_raises(template):
    doc = _plain("三房兩廳")
    with pytest.raises(KeyError):
        apply_style(doc, template, DocRange(0, 0, 2), "不存在的字元樣式")


def test_apply_style_empty_range_cursor_at_start(template):
    doc = _plain("三房兩廳")
    res = apply_style(doc, template, DocRange(0, 3, 3), EMPH)
    assert res.document is doc  # 文件層 no-op
    assert res.cursor == DocCursor(0, 3)
    assert res.layout.violations == []


# ---------- EditSession.apply_style：undo／redo 歷史 ----------

def test_session_apply_style_records_and_undo(template):
    doc = _plain("三房兩廳")
    session = EditSession(doc, template)
    assert not session.can_undo()
    session.apply_style(DocRange(0, 0, 2), EMPH)
    assert session.can_undo()
    assert runs_of(session.document.paragraphs[0]) == [("三房", EMPH), ("兩廳", None)]
    # undo 還原原樣式（單一無字元樣式 run）
    res = session.undo()
    assert res is not None
    assert runs_of(session.document.paragraphs[0]) == [("三房兩廳", None)]
    assert session.can_redo()


def test_session_apply_style_redo(template):
    doc = _plain("三房兩廳")
    session = EditSession(doc, template)
    session.apply_style(DocRange(0, 0, 2), EMPH)
    session.undo()
    res = session.redo()
    assert res is not None
    assert runs_of(session.document.paragraphs[0]) == [("三房", EMPH), ("兩廳", None)]
    assert not session.can_redo()


def test_session_apply_style_new_edit_clears_redo(template):
    doc = _plain("三房兩廳")
    session = EditSession(doc, template)
    session.apply_style(DocRange(0, 0, 2), EMPH)
    session.undo()
    assert session.can_redo()
    session.apply_style(DocRange(0, 2, 4), LABEL)  # 新編輯清 redo
    assert not session.can_redo()


# ---------- R5 真實素材驗收（自擬）----------

def test_r5_emphasis_roundtrip_through_session(template):
    """自擬內文段套字元樣式：reflow 0 違規、字格帶新樣式、undo 還原、redo 復原。"""
    session = EditSession(_plain("三房兩廳，約三十坪的老公寓。"), template)
    res = session.apply_style(DocRange(0, 5, 8), EMPH)  # index 5-7＝「約三十」套強調
    assert res.layout.violations == []
    # 端到端：範圍字格帶 EMPH
    styled = [
        c.char_style
        for pg in res.layout.pages
        for pl in pg.placed
        if pl.para_idx == 0
        for c in pl.line.cells
        if c.span and 5 <= c.span[0] < 8
    ]
    assert styled and all(cs == EMPH for cs in styled)
    # undo：字元樣式全清回原
    session.undo()
    assert runs_of(session.document.paragraphs[0]) == [("三房兩廳，約三十坪的老公寓。", None)]
    # redo：復原強調
    session.redo()
    assert runs_of(session.document.paragraphs[0]) == [
        ("三房兩廳，", None), ("約三十", EMPH), ("坪的老公寓。", None)
    ]
