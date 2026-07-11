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
    unknown_char_style_refs,
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


# ---------- document@2：段內 run ----------

def test_document_v2_runs_load_and_text_property():
    d = valid_dict()
    d["paragraphs"] = [{
        "style": "內文-明體直排",
        "runs": [
            {"text": "前段"},
            {"text": "重點", "char_style": "內文強調-明體W9"},
            {"text": "後段。"},
        ],
    }]
    p = document_from_dict(d).paragraphs[0]
    assert p.text == "前段重點後段。"
    assert [r.char_style for r in p.runs] == [None, "內文強調-明體W9", None]


def test_document_v2_runs_round_trip(tmp_path):
    d = valid_dict()
    d["paragraphs"].append({
        "style": "內文-明體直排",
        "runs": [{"text": "甲"}, {"text": "乙", "char_style": "內文強調-明體W9"}],
    })
    doc = document_from_dict(d)
    path = tmp_path / "doc.json"
    save_document(doc, path)
    assert load_document(path) == doc


def test_document_v1_still_loads_and_v1_rejects_runs():
    d = valid_dict()
    d["schema"] = "cjkfolio/document@1"
    assert document_from_dict(d).paragraphs[0].text == "第一段自擬文字。"
    d["paragraphs"][0] = {"style": "內文-明體直排", "runs": [{"text": "字"}]}
    with pytest.raises(DocumentError, match="document@2"):
        document_from_dict(d)


def test_document_v2_rejects_bad_run():
    d = valid_dict()
    d["paragraphs"][0] = {"style": "內文-明體直排", "runs": [{"char_style": "無文字"}]}
    with pytest.raises(DocumentError, match="0"):
        document_from_dict(d)


def test_unknown_char_style_refs_against_template():
    d = valid_dict()
    d["paragraphs"].append({
        "style": "內文-明體直排",
        "runs": [{"text": "字", "char_style": "不存在的字元樣式"}],
    })
    doc = document_from_dict(d)
    template = load_template(TEMPLATE)
    assert unknown_char_style_refs(doc, template) == ["不存在的字元樣式"]


# ---------- 目錄條目頁碼（Sprint 16） ----------

def test_document_page_no_optional_load_and_round_trip(tmp_path):
    d = valid_dict()
    d["paragraphs"][0] = {"text": "安放與整理的十個提問", "style": "目錄-篇章條目",
                          "page_no": "169"}
    doc = document_from_dict(d)
    assert doc.paragraphs[0].page_no == "169"
    assert doc.paragraphs[1].page_no is None  # 無欄位照載（@2 相容擴充）
    # round-trip：有值才寫、無值不出現
    out = document_to_dict(doc)
    assert out["paragraphs"][0]["page_no"] == "169"
    assert "page_no" not in out["paragraphs"][1]
    path = tmp_path / "toc.json"
    save_document(doc, path)
    assert load_document(path) == doc


def test_document_page_no_rejects_non_digit():
    d = valid_dict()
    d["paragraphs"][0] = {"text": "條目", "style": "目錄-篇章條目", "page_no": "十六"}
    with pytest.raises(DocumentError, match="page_no"):
        document_from_dict(d)
    d["paragraphs"][0] = {"text": "條目", "style": "目錄-篇章條目", "page_no": 169}
    with pytest.raises(DocumentError, match="page_no"):
        document_from_dict(d)
