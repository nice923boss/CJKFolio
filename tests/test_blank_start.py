"""空白起始文件（Sprint 123）：編輯器開啟即從零開始。

Qt 無關的純邏輯面：blank_document 的結構、排版行為（空段 0 頁＝空紙面前提）、
第一次插入與 undo 回空。EditorWindow(None) 的 GUI 行為由 smoke C25 驗。
"""
from pathlib import Path

import pytest

from cjkfolio.editing import DocCursor
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from editor.blank_doc import blank_document

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"


@pytest.fixture()
def template():
    return load_template(str(TEMPLATE))


def test_blank_document_shape(template):
    doc = blank_document(template, TEMPLATE.stem)
    assert doc.title == "未命名"
    assert doc.template == "neizai-zhengli"
    assert doc.master == template.default_master
    assert doc.master in template.masters
    assert len(doc.paragraphs) == 1
    para = doc.paragraphs[0]
    assert para.text == ""
    assert para.style == template.md_mapping["paragraph"]


def test_blank_document_lays_out_to_zero_pages(template):
    # 引擎對空段不產行（一手 probe 實測）：空白起始畫「空紙面」而非硬塞佔位字的前提
    lay = layout_document(blank_document(template, TEMPLATE.stem), template)
    assert len(lay.pages) == 0
    assert not lay.violations


def test_blank_document_accepts_first_insert_and_undo(template):
    ses = EditSession(blank_document(template, TEMPLATE.stem), template)
    res = ses.insert(DocCursor(0, 0), "測")
    assert res.address is not None, "第一次插入應落到可尋址的字格"
    assert ses.document.paragraphs[0].text == "測"
    assert len(ses.layout.pages) == 1
    ses.undo()
    assert ses.document.paragraphs[0].text == ""
    assert len(ses.layout.pages) == 0
