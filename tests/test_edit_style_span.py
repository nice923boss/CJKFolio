"""編輯引擎跨段字元樣式套用（cjkfolio/editing.py，Sprint 49）：apply_char_style over DocSpan。

承 Sprint 45 段內 apply_char_style 與 Sprint 48 DocSpan 跨段範圍機制，補齊 GAPS #26
「跨段選取套字元樣式」子項。apply_char_style_span 對跨段選取逐段套用各自子範圍（段界
不併、各段保身分）：頭段 [start, len)、中間段整段、尾段 [0, end)；同段退化委派段內
apply_char_style。apply_style_span 為完整回路（套樣式 → 全文重排 → locate_cell 反查，
游標停選取尾）；EditSession.apply_style_span 入 undo／redo。純邏輯離屏可驗，字元樣式名
有效性由 layout_document 守門（同段內慣例）。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph, Run, document_from_dict
from cjkfolio.editing import (
    DocCursor,
    DocRange,
    DocSpan,
    EditSession,
    apply_char_style,
    apply_char_style_span,
    apply_style_span,
)
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]

BODY = "內文-明體直排"
EMPH = "內文強調-明體W9"


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def _bodies(*texts: str) -> Document:
    """A-內文版多段內文（每段單一無字元樣式 run）。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": t, "style": BODY} for t in texts],
    })


def _multi(*paras: Paragraph) -> Document:
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=tuple(paras))


def runs_of(para: Paragraph):
    return [(r.text, r.char_style) for r in para.runs]


# ---------- apply_char_style_span：跨段套字元樣式（純文件層）----------

def test_char_style_span_across_two_paragraphs():
    # 段 0 caret 2 到段 1 caret 2 套強調 → 段 0 "兩廳"、段 1 "採光" 掛強調，段界不併
    out = apply_char_style_span(_bodies("三房兩廳", "採光良好"),
                                DocSpan(DocCursor(0, 2), DocCursor(1, 2)), EMPH)
    assert len(out.paragraphs) == 2
    assert runs_of(out.paragraphs[0]) == [("三房", None), ("兩廳", EMPH)]
    assert runs_of(out.paragraphs[1]) == [("採光", EMPH), ("良好", None)]


def test_char_style_span_styles_middle_paragraph_entirely():
    # 跨三段：頭段尾、中間段整段、尾段頭皆掛強調
    out = apply_char_style_span(_bodies("甲乙", "丙丁", "戊己"),
                                DocSpan(DocCursor(0, 1), DocCursor(2, 1)), EMPH)
    assert len(out.paragraphs) == 3
    assert runs_of(out.paragraphs[0]) == [("甲", None), ("乙", EMPH)]
    assert runs_of(out.paragraphs[1]) == [("丙丁", EMPH)]  # 中間段整段
    assert runs_of(out.paragraphs[2]) == [("戊", EMPH), ("己", None)]


def test_char_style_span_same_paragraph_delegates():
    # 同段 DocSpan 退化為段內 apply_char_style（結果等價）
    doc = _bodies("三房兩廳")
    span_out = apply_char_style_span(doc, DocSpan(DocCursor(0, 1), DocCursor(0, 3)), EMPH)
    range_out = apply_char_style(doc, DocRange(0, 1, 3), EMPH)
    assert runs_of(span_out.paragraphs[0]) == runs_of(range_out.paragraphs[0])


def test_char_style_span_none_clears_across_paragraphs():
    # 兩段皆全強調，跨段清除（None）→ 回段落樣式預設
    doc = _multi(Paragraph(style=BODY, runs=(Run("三房", EMPH),)),
                 Paragraph(style=BODY, runs=(Run("兩廳", EMPH),)))
    out = apply_char_style_span(doc, DocSpan(DocCursor(0, 0), DocCursor(1, 2)), None)
    assert runs_of(out.paragraphs[0]) == [("三房", None)]
    assert runs_of(out.paragraphs[1]) == [("兩廳", None)]


def test_char_style_span_merges_adjacent_same_style():
    # 段 0 "甲"[強調]／"乙"[None]，套 [1,2)("乙")強調 → 與 "甲" 併為單一 run
    doc = _multi(Paragraph(style=BODY, runs=(Run("甲", EMPH), Run("乙", None))),
                 Paragraph(style=BODY, runs=(Run("丙丁", None),)))
    out = apply_char_style_span(doc, DocSpan(DocCursor(0, 1), DocCursor(1, 1)), EMPH)
    assert runs_of(out.paragraphs[0]) == [("甲乙", EMPH)]  # 相鄰同樣式併合
    assert runs_of(out.paragraphs[1]) == [("丙", EMPH), ("丁", None)]


def test_char_style_span_leaves_outside_untouched():
    # 範圍外字元保留原字元樣式（含既有樣式）
    doc = _multi(Paragraph(style=BODY, runs=(Run("前", "角色註記-仿宋小字"), Run("三房兩廳", None))),
                 Paragraph(style=BODY, runs=(Run("採光良好", None),)))
    # 段 0 caret 3（"房"後）到段 1 caret 2 套強調
    out = apply_char_style_span(doc, DocSpan(DocCursor(0, 3), DocCursor(1, 2)), EMPH)
    assert runs_of(out.paragraphs[0]) == [("前", "角色註記-仿宋小字"), ("三房", None), ("兩廳", EMPH)]
    assert runs_of(out.paragraphs[1]) == [("採光", EMPH), ("良好", None)]


def test_char_style_span_empty_is_noop_same_object():
    doc = _bodies("三房")
    assert apply_char_style_span(doc, DocSpan(DocCursor(0, 1), DocCursor(0, 1)), EMPH) is doc


def test_char_style_span_immutable():
    doc = _bodies("三房兩廳", "採光良好")
    apply_char_style_span(doc, DocSpan(DocCursor(0, 2), DocCursor(1, 2)), EMPH)
    assert runs_of(doc.paragraphs[0]) == [("三房兩廳", None)]  # 原文件不變


def test_char_style_span_rejects_reversed():
    with pytest.raises(ValueError):
        apply_char_style_span(_bodies("三房", "兩廳"),
                              DocSpan(DocCursor(1, 1), DocCursor(0, 1)), EMPH)


def test_char_style_span_rejects_out_of_range_para():
    with pytest.raises(IndexError):
        apply_char_style_span(_bodies("三房"),
                              DocSpan(DocCursor(0, 0), DocCursor(9, 0)), EMPH)


# ---------- apply_style_span：完整回路（套樣式 → reflow → 反查，游標停選取尾）----------

def test_apply_style_span_reflows_and_cursor_at_end(template):
    doc = _bodies("三房兩廳約三十坪", "採光良好通風佳")
    # 段 0 caret 4 到段 1 caret 2 套強調 → 段 0 "約三十坪"＋段 1 "採光" 掛強調
    res = apply_style_span(doc, template, DocSpan(DocCursor(0, 4), DocCursor(1, 2)), EMPH)
    assert res.layout.violations == []
    assert res.cursor == DocCursor(1, 2)  # 游標停選取尾
    assert len(res.document.paragraphs) == 2  # 段界不併
    assert len(doc.paragraphs) == 2 and runs_of(doc.paragraphs[0]) == [("三房兩廳約三十坪", None)]  # 原文件不變
    # 端到端：受套範圍字格 char_style＝EMPH 流入渲染層（文件序＝段0[4,8)＋段1[0,2)）
    styled = "".join(
        c.text
        for pg in res.layout.pages
        for pl in pg.placed
        for c in pl.line.cells
        if c.char_style == EMPH
    )
    assert styled == "約三十坪採光"


def test_apply_style_span_unknown_style_raises(template):
    # 未知字元樣式名由 layout_document 守門（純文件層不驗存在性）
    doc = _bodies("三房兩廳", "採光良好")
    with pytest.raises(KeyError):
        apply_style_span(doc, template, DocSpan(DocCursor(0, 0), DocCursor(1, 2)), "不存在的字元樣式")


# ---------- EditSession.apply_style_span：undo／redo 歷史 ----------

def test_session_apply_style_span_undo_redo(template):
    s = EditSession(_bodies("三房兩廳", "採光良好"), template)
    s.apply_style_span(DocSpan(DocCursor(0, 2), DocCursor(1, 2)), EMPH)
    assert runs_of(s.document.paragraphs[0]) == [("三房", None), ("兩廳", EMPH)]
    assert runs_of(s.document.paragraphs[1]) == [("採光", EMPH), ("良好", None)]
    assert s.layout.violations == []
    assert s.can_undo()
    s.undo()  # 清回原（兩段皆無字元樣式）
    assert runs_of(s.document.paragraphs[0]) == [("三房兩廳", None)]
    assert runs_of(s.document.paragraphs[1]) == [("採光良好", None)]
    s.redo()  # 復原
    assert runs_of(s.document.paragraphs[1]) == [("採光", EMPH), ("良好", None)]
    assert not s.can_redo()
