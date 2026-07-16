"""編輯引擎段落樣式變更（cjkfolio/editing.py，Sprint 46）：改段落的段落樣式參照。

承 Sprint 41〜45 編輯回路：change_paragraph_style 於純文件層換 Paragraph.style
（runs 與字元樣式、page_no 不變）；apply_para_style 為完整回路（改樣式 →
layout_document 全文重排 → locate_cell 反查游標）；EditSession.apply_para_style
入 undo／redo 歷史。段落樣式變更不改 text，故游標保持不變、reflow 後畫布落點隨版面
更新。純邏輯離屏可驗，段落樣式名驗證由 layout_document 守門（同字元樣式慣例）。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph, Run
from cjkfolio.editing import (
    DocCursor,
    apply_para_style,
    change_paragraph_style,
)
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]

# 模版真有的段落樣式名（templates/neizai-zhengli.json），皆內文級線性樣式
P_BODY = "內文-明體直排"
P_QUOTE = "引文-仿宋語錄"
P_TITLE = "題詞-楷書"
EMPH = "內文強調-明體W9"  # 字元樣式（驗段落樣式變更不動字元樣式）


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _plain(text: str, style: str = P_BODY) -> Document:
    """A-內文版單段（單一無字元樣式 run）。"""
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=(Paragraph(text=text, style=style),))


def _para(runs, style: str = P_BODY) -> Document:
    """A-內文版單段（指定 run 序列）。"""
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=(Paragraph(style=style, runs=tuple(runs)),))


def _multi(*paras: Paragraph) -> Document:
    """A-內文版多段。"""
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=tuple(paras))


def runs_of(para: Paragraph):
    return [(r.text, r.char_style) for r in para.runs]


# ---------- change_paragraph_style：純文件層 ----------

def test_change_switches_style():
    out = change_paragraph_style(_plain("三房兩廳"), 0, P_QUOTE)
    assert out.paragraphs[0].style == P_QUOTE
    assert out.paragraphs[0].text == "三房兩廳"  # text 不變


def test_change_preserves_runs_and_char_styles():
    # 換段落樣式不動 run 模型與字元樣式
    doc = _para([Run("甲乙", EMPH), Run("丙丁", None)])
    out = change_paragraph_style(doc, 0, P_QUOTE)
    assert out.paragraphs[0].style == P_QUOTE
    assert runs_of(out.paragraphs[0]) == [("甲乙", EMPH), ("丙丁", None)]


def test_change_preserves_page_no():
    doc = _multi(Paragraph(text="第一章", style=P_BODY, page_no="17"))
    out = change_paragraph_style(doc, 0, P_QUOTE)
    assert out.paragraphs[0].page_no == "17"


def test_change_same_style_noop_returns_same():
    doc = _plain("三房兩廳")
    out = change_paragraph_style(doc, 0, P_BODY)
    assert out is doc  # 樣式相同 no-op 回原物件


def test_change_is_immutable():
    doc = _plain("三房兩廳")
    change_paragraph_style(doc, 0, P_QUOTE)
    assert doc.paragraphs[0].style == P_BODY  # 原文件不變


def test_change_only_target_paragraph():
    doc = _multi(Paragraph(text="第一段", style=P_BODY),
                 Paragraph(text="第二段", style=P_BODY))
    out = change_paragraph_style(doc, 1, P_QUOTE)
    assert out.paragraphs[0].style == P_BODY  # 段 0 不動
    assert out.paragraphs[1].style == P_QUOTE  # 段 1 改


def test_change_para_idx_out_of_range_raises():
    with pytest.raises(IndexError):
        change_paragraph_style(_plain("三房兩廳"), 5, P_QUOTE)


def test_change_empty_style_raises():
    # 空字串破壞 document@2「段落需非空 style」不變式，純文件層快速失敗
    with pytest.raises(ValueError):
        change_paragraph_style(_plain("三房兩廳"), 0, "")


# ---------- apply_para_style：完整回路（改樣式 → reflow → 反查）----------

def test_apply_para_style_reflows_keeps_cursor(template):
    doc = _plain("三房兩廳，約三十坪的老公寓。")
    res = apply_para_style(doc, template, DocCursor(0, 4), P_QUOTE)
    # 文件層：段落樣式換 P_QUOTE、text 不變
    assert res.document.paragraphs[0].style == P_QUOTE
    assert res.document.paragraphs[0].text == "三房兩廳，約三十坪的老公寓。"
    assert doc.paragraphs[0].style == P_BODY  # 原文件不變
    # reflow 乾淨、游標保持（不改 text）、畫布落點反查得到
    assert res.layout.violations == []
    assert res.cursor == DocCursor(0, 4)
    assert res.address is not None


def test_apply_para_style_cell_carries_new_style_end_to_end(template):
    # 端到端：套用後 layout 該段 placed line 的 style＝新段落樣式（流入渲染層）
    doc = _plain("三房兩廳，約三十坪的老公寓。")
    res = apply_para_style(doc, template, DocCursor(0, 0), P_QUOTE)
    styles = [
        pl.style
        for pg in res.layout.pages
        for pl in pg.placed
        if pl.para_idx == 0
    ]
    assert styles and all(s == P_QUOTE for s in styles)


def test_apply_para_style_unknown_style_raises(template):
    # 未知段落樣式名由 layout_document 守門（純文件層 change 不驗存在性）
    doc = _plain("三房兩廳")
    with pytest.raises(KeyError):
        apply_para_style(doc, template, DocCursor(0, 0), "不存在的段落樣式")


# ---------- EditSession.apply_para_style：undo／redo 歷史 ----------

def test_session_para_style_records_and_undo(template):
    doc = _plain("三房兩廳")
    session = EditSession(doc, template)
    assert not session.can_undo()
    session.apply_para_style(DocCursor(0, 0), P_QUOTE)
    assert session.can_undo()
    assert session.document.paragraphs[0].style == P_QUOTE
    # undo 還原原段落樣式
    res = session.undo()
    assert res is not None
    assert session.document.paragraphs[0].style == P_BODY
    assert session.can_redo()


def test_session_para_style_redo(template):
    doc = _plain("三房兩廳")
    session = EditSession(doc, template)
    session.apply_para_style(DocCursor(0, 0), P_QUOTE)
    session.undo()
    res = session.redo()
    assert res is not None
    assert session.document.paragraphs[0].style == P_QUOTE
    assert not session.can_redo()


def test_session_para_style_new_edit_clears_redo(template):
    doc = _plain("三房兩廳")
    session = EditSession(doc, template)
    session.apply_para_style(DocCursor(0, 0), P_QUOTE)
    session.undo()
    assert session.can_redo()
    session.apply_para_style(DocCursor(0, 0), P_TITLE)  # 新編輯清 redo
    assert not session.can_redo()


# ---------- R5 真實素材驗收（自擬）----------

def test_r5_paragraph_style_roundtrip_through_session(template):
    """自擬內文段改段落樣式：reflow 0 違規、placed line 帶新樣式、undo 還原、redo 復原。"""
    session = EditSession(_plain("三房兩廳，約三十坪的老公寓。"), template)
    res = session.apply_para_style(DocCursor(0, 0), P_QUOTE)
    assert res.layout.violations == []
    # 端到端：該段 placed line 帶新段落樣式
    styles = [
        pl.style
        for pg in res.layout.pages
        for pl in pg.placed
        if pl.para_idx == 0
    ]
    assert styles and all(s == P_QUOTE for s in styles)
    # undo：回原段落樣式
    session.undo()
    assert session.document.paragraphs[0].style == P_BODY
    # redo：復原
    session.redo()
    assert session.document.paragraphs[0].style == P_QUOTE
