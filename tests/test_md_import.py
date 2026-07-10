"""Markdown 匯入（cjkfolio.md_import）：block 級結構直接對映樣式（PLAN §4.4 修正 1）。"""
from pathlib import Path

import pytest

from cjkfolio.md_import import blocks_from_markdown, import_markdown
from cjkfolio.styles import load_template

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"

MD = """# 章名標題

引言段落自擬。

## 個案標題

### 小標

> 引文第一行
> 引文第二行

正文段落一。
正文段落二併行。
"""


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def test_blocks_parse_kinds():
    blocks = blocks_from_markdown(MD)
    assert blocks[0] == ("h1", "章名標題")
    assert blocks[1] == ("paragraph", "引言段落自擬。")
    assert ("h2", "個案標題") in blocks
    assert ("h3", "小標") in blocks


def test_blockquote_lines_join():
    blocks = blocks_from_markdown("> 甲\n> 乙\n\n丙")
    assert blocks == [("blockquote", "甲乙"), ("paragraph", "丙")]


def test_paragraph_lines_join_without_space():
    assert blocks_from_markdown("正文一。\n正文二。") == [("paragraph", "正文一。正文二。")]


def test_list_items_become_paragraphs():
    assert blocks_from_markdown("- 項目一\n- 項目二") == [
        ("paragraph", "項目一"), ("paragraph", "項目二"),
    ]


def test_import_markdown_maps_template_styles(template):
    doc = import_markdown(MD, mapping=template.md_mapping, title="自擬稿")
    styles = [p.style for p in doc.paragraphs]
    assert styles[0] == "章名大標-明體W7"
    assert styles[1] == "內文-明體直排"
    assert "個案大標-NotoSans" in styles
    assert "章節小標-黑體" in styles
    assert "引文-仿宋語錄" in styles
    texts = [p.text for p in doc.paragraphs]
    assert "引文第一行引文第二行" in texts


def test_unmapped_heading_level_falls_back_to_paragraph():
    doc = import_markdown("#### 深層標題", mapping={"paragraph": "內文-明體直排"})
    assert doc.paragraphs[0].style == "內文-明體直排"
    assert doc.paragraphs[0].text == "深層標題"


def test_mapping_requires_paragraph_key():
    with pytest.raises(ValueError, match="paragraph"):
        import_markdown("字", mapping={})
