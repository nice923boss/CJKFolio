"""多段批次改派段落樣式（Sprint 79，§4.4「逐段確認與批次改派」核心半邊）。

change_paragraph_styles：一次改多段 Paragraph.style（純文件層、不可變、無變更
no-op 回原物件、越界／空名快速失敗）；EditSession.apply_para_styles：批次改派
入**單一 undo 步**（復用 _commit_pair＝文件變模版不變；未知樣式名全文重排
KeyError 快速失敗狀態不變）。關 GAPS #24「多段一次套用需核心單一 undo 多段
API」子項＝AI 校正批次改派與跨段選取套段落樣式的共同地基。測試素材自擬。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.editing import change_paragraph_styles
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]

BODY = "內文-明體直排"
QUOTE = "引文-仿宋語錄"
H3 = "章節小標-黑體"


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def make_doc(*texts_styles):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": t, "style": s} for t, s in texts_styles],
    })


def test_change_multi_styles_basic():
    doc = make_doc(("留白是安放的開始。", BODY),
                   ("整理心法", BODY),
                   ("好好說再見。", BODY))
    out = change_paragraph_styles(doc, {1: H3, 2: QUOTE})
    assert [p.style for p in out.paragraphs] == [BODY, H3, QUOTE]
    assert [p.style for p in doc.paragraphs] == [BODY, BODY, BODY]  # 原文件不可變
    assert out.paragraphs[0] is doc.paragraphs[0]  # 未動段共享
    assert out.paragraphs[1].text == "整理心法"  # runs／text 不變


def test_change_multi_styles_noop_and_guards():
    doc = make_doc(("留白。", BODY))
    assert change_paragraph_styles(doc, {}) is doc                 # 空 no-op
    assert change_paragraph_styles(doc, {0: BODY}) is doc          # 等值 no-op
    with pytest.raises(IndexError):
        change_paragraph_styles(doc, {5: H3})                      # 越界
    with pytest.raises(ValueError):
        change_paragraph_styles(doc, {0: ""})                      # 空名


def test_session_apply_para_styles_single_undo(template):
    doc = make_doc(("留白是安放的開始。", BODY),
                   ("整理心法", BODY),
                   ("好好說再見。", BODY))
    session = EditSession(doc, template)
    res = session.apply_para_styles({1: H3, 2: QUOTE})
    assert res is not None
    assert [p.style for p in session.document.paragraphs] == [BODY, H3, QUOTE]
    assert session.apply_para_styles({1: H3}) is None  # 等值 no-op 不入歷史
    assert session.undo() is not None                  # 單一 undo 步回原
    assert [p.style for p in session.document.paragraphs] == [BODY, BODY, BODY]
    assert not session.can_undo()                      # 批次只佔一步
    assert session.redo() is not None
    assert session.document.paragraphs[2].style == QUOTE


def test_session_apply_para_styles_unknown_style_fast_fail(template):
    doc = make_doc(("留白。", BODY))
    session = EditSession(doc, template)
    with pytest.raises(KeyError):
        session.apply_para_styles({0: "不存在的樣式"})  # 全文重排守門
    assert session.document.paragraphs[0].style == BODY  # 狀態不變
    assert not session.can_undo()
