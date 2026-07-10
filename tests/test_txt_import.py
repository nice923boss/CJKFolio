"""txt 匯入（cjkfolio.txt_import）：空行切段、全掛預設樣式（PLAN §4.4）。"""
from cjkfolio.txt_import import import_txt_file, paragraphs_from_text

DEFAULT = "內文-明體直排"


def test_blank_line_splits_paragraphs():
    assert paragraphs_from_text("甲段。\n\n乙段。") == ["甲段。", "乙段。"]


def test_intra_block_lines_join_without_space():
    # CJK 換行併接不加空白
    assert paragraphs_from_text("甲段第一行\n甲段第二行\n\n乙段") == ["甲段第一行甲段第二行", "乙段"]


def test_crlf_and_multiple_blank_lines():
    assert paragraphs_from_text("甲\r\n\r\n\r\n乙\r\n") == ["甲", "乙"]


def test_leading_trailing_blank_blocks_ignored():
    assert paragraphs_from_text("\n\n　\n甲\n\n") == ["甲"]


def test_import_txt_file_assigns_default_style(tmp_path):
    p = tmp_path / "稿.txt"
    p.write_text("首段。\n\n次段。", encoding="utf-8")
    doc = import_txt_file(p, default_style=DEFAULT, title="自擬稿")
    assert doc.title == "自擬稿"
    assert [para.style for para in doc.paragraphs] == [DEFAULT, DEFAULT]
    assert [para.text for para in doc.paragraphs] == ["首段。", "次段。"]
