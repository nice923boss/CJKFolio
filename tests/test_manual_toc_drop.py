"""Sprint 149：生成目次時拿掉稿件自帶的手寫目錄，不與生成的目次並排成兩份。

真稿（回憶錄 txt）開頭有「目錄」＋一段打字的章名清單；AI 指派給它們目錄類樣式
（目錄-目次標題／目錄-篇章條目），舊版生成目次後兩份目錄並存。判準靠樣式，
不猜文字。測試素材一律自擬（版權紅線）。
"""
import dataclasses
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph
from cjkfolio.editing import DocCursor
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from cjkfolio.toc import document_with_toc, manual_toc_indices

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"
BODY = "內文-明體直排"
FILLER = "這是一段用來把版面撐開的內文，重複多次以確保章與章之間跨頁。" * 6


@pytest.fixture
def template():
    return load_template(TEMPLATE)


def memoir_doc():
    """書名、手寫目錄（標題＋一段條目）、兩章；章名已宣告目錄條目。"""
    return Document(title="t", template="neizai-zhengli", master="A-內文版", paragraphs=(
        Paragraph(text="某某回憶錄", style=BODY),
        Paragraph(text="目錄", style="目錄-目次標題"),
        Paragraph(text="第一章：家鄉第二章：求學", style="目錄-篇章條目"),
        Paragraph(text="第一章：家鄉", style="章名大標-明體W7",
                  toc_title="第一章：家鄉", toc_level=2),
        Paragraph(text=FILLER, style=BODY),
        Paragraph(text="第二章：求學", style="章名大標-明體W7",
                  toc_title="第二章：求學", toc_level=2),
        Paragraph(text=FILLER, style=BODY),
    ))


def test_manual_toc_indices_found_by_style(template):
    assert manual_toc_indices(memoir_doc(), template.auto_toc) == (1, 2)


def test_drop_manual_leaves_only_generated_toc(template):
    out = document_with_toc(memoir_doc(), template, drop_manual=True)
    texts = [p.text for p in out.paragraphs]
    assert texts.count("第一章：家鄉第二章：求學") == 0
    # 生成的目次：標題段＋2 條目，接著內文 5 段（原 7 段去掉手寫目錄 2 段）
    assert len(out.paragraphs) == 3 + 5
    assert texts[3:] == ["某某回憶錄", "第一章：家鄉", FILLER, "第二章：求學", FILLER]


def test_without_drop_manual_keeps_old_behaviour(template):
    out = document_with_toc(memoir_doc(), template)
    assert "第一章：家鄉第二章：求學" in [p.text for p in out.paragraphs]


def test_dropped_section_head_master_moves_to_next_kept(template):
    """手寫目錄段若是節首（帶主版標記），標記轉給下一段，節不消失。"""
    src = memoir_doc()
    paras = list(src.paragraphs)
    paras[1] = Paragraph(text="目錄", style="目錄-目次標題", master="B-部扉")
    out = document_with_toc(dataclasses.replace(src, paragraphs=tuple(paras)),
                            template, drop_manual=True)
    chapter_one = next(p for p in out.paragraphs[3:] if p.text == "第一章：家鄉")
    assert chapter_one.master == "B-部扉"


def test_entry_style_paragraph_that_declares_entry_is_kept(template):
    """掛條目樣式但自身宣告了目錄條目的段，是要列入的標題，不當手寫目錄刪。"""
    src = memoir_doc()
    paras = list(src.paragraphs)
    paras[2] = Paragraph(text="附錄", style="目錄-篇章條目", toc_title="附錄", toc_level=2)
    out = document_with_toc(dataclasses.replace(src, paragraphs=tuple(paras)),
                            template, drop_manual=True)
    assert "附錄" in [p.text for p in out.paragraphs[4:]]


def test_session_generate_drops_manual_and_clamps_cursor(template):
    """段數變少時游標越界即歸零；整件事仍是單一 undo 步。"""
    src = memoir_doc()
    session = EditSession(src, template)
    last = len(src.paragraphs) - 1
    session.insert(DocCursor(last, len(FILLER)), "尾")   # 游標停在最後一段末
    before = session.document
    session.apply_para_styles({}, None, generate_toc=True)
    assert "第一章：家鄉第二章：求學" not in [p.text for p in session.document.paragraphs]
    cursor = session.cursor
    para = session.document.paragraphs[cursor.para_idx]
    assert cursor.caret <= len(para.text)
    session.undo()
    assert session.document == before
