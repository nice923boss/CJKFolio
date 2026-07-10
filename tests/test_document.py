"""文件模型（cjkfolio.document）：JSON schema 載入、驗證、往返。"""
from pathlib import Path

import pytest

from cjkfolio.document import (
    SCHEMA_ID,
    Document,
    DocumentError,
    Paragraph,
    document_from_dict,
    document_to_dict,
    load_document,
    save_document,
    unknown_style_refs,
)
from cjkfolio.styles import load_template

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"


def valid_dict():
    return {
        "schema": SCHEMA_ID,
        "meta": {"title": "測試稿", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [
            {"text": "第一段自擬文字。", "style": "內文-明體直排"},
            {"text": "第二段自擬文字。", "style": "內文-明體直排"},
        ],
    }


def test_document_from_dict_valid():
    doc = document_from_dict(valid_dict())
    assert doc.title == "測試稿"
    assert doc.master == "A-內文版"
    assert len(doc.paragraphs) == 2
    assert doc.paragraphs[0] == Paragraph("第一段自擬文字。", "內文-明體直排")


def test_document_round_trip_dict():
    doc = document_from_dict(valid_dict())
    assert document_from_dict(document_to_dict(doc)) == doc


def test_document_rejects_wrong_schema():
    d = valid_dict()
    d["schema"] = "cjkfolio/document@99"
    with pytest.raises(DocumentError, match="schema"):
        document_from_dict(d)


def test_document_rejects_bad_paragraph():
    d = valid_dict()
    d["paragraphs"][1] = {"text": "缺樣式"}
    with pytest.raises(DocumentError, match="1"):
        document_from_dict(d)


def test_document_file_round_trip(tmp_path):
    doc = document_from_dict(valid_dict())
    path = tmp_path / "doc.json"
    save_document(doc, path)
    assert load_document(path) == doc


def test_unknown_style_refs_against_template():
    d = valid_dict()
    d["paragraphs"].append({"text": "壞樣式段", "style": "不存在的樣式"})
    doc = document_from_dict(d)
    template = load_template(TEMPLATE)
    assert unknown_style_refs(doc, template) == ["不存在的樣式"]
