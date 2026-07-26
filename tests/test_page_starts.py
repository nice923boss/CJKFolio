"""樣式宣告起新頁（Sprint 141）：章名大標一律另起一頁。

AI 樣式指派把「第八章｜完美謀殺」標成章名大標後，它仍接在前一章內文後面同頁
（Owner 截圖 p78）。章首該不該起新頁是模版的排版意圖，不是 AI 的判斷，故走
§4.4 分工：模版用 ParagraphStyle.starts_page 宣告，引擎照宣告補節首標記。

覆蓋三層：styles 解析、editing.apply_page_starts 語意（只加不減、段 0 例外、
冪等）、session 指派回路（AI 指派後即生效）。素材一律自擬（版權紅線）。
"""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.editing import apply_page_starts
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template, template_from_dict

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"

CHAPTER = "章名大標-明體W7"
BODY = "內文-明體直排"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs, master="A-內文版"):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": master},
        "paragraphs": paragraphs,
    })


def two_chapter_doc():
    """兩章連排：章名各接在前文之後（未補節首），即 Owner 截圖的病灶形態。"""
    return make_doc([
        {"text": "第一章｜起點", "style": CHAPTER},
        {"text": "整" * 40, "style": BODY},
        {"text": "第二章｜轉折", "style": CHAPTER},
        {"text": "理" * 40, "style": BODY},
    ])


# ---------- styles 層：模版宣告 ----------

def test_chapter_style_declares_starts_page(template):
    """產品模版的章名大標宣告 starts_page；內文與其他樣式不宣告。"""
    assert template.paragraph_styles[CHAPTER].starts_page is True
    assert template.paragraph_styles[BODY].starts_page is False


def test_starts_page_defaults_false_when_omitted():
    """未宣告即 False（既有模版不受影響，不從樣式名或字級反推階層）。"""
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["paragraph_styles"][CHAPTER].pop("starts_page")
    assert template_from_dict(data).paragraph_styles[CHAPTER].starts_page is False


# ---------- editing 層：補節首語意 ----------

def test_page_starts_breaks_page_at_chapter(template):
    """章名段補上節首標記＝自該段起新頁；主版沿用當前節（換頁不換版式）。"""
    before = layout_document(two_chapter_doc(), template)
    assert len(before.pages) == 1  # 病灶形態：兩章擠同頁

    doc = apply_page_starts(two_chapter_doc(), template)
    assert doc.paragraphs[2].master == "A-內文版"  # 第二章補節首
    assert doc.paragraphs[0].master is None        # 段 0 不補（首節主版存 doc.master）
    assert doc.paragraphs[1].master is None
    assert doc.paragraphs[3].master is None
    after = layout_document(doc, template)
    assert len(after.pages) == 2
    assert after.pages[1].placed[0].para_idx == 2  # 第二頁首行＝第二章章名


def test_page_starts_keeps_existing_master(template):
    """已自帶 master 的段原樣不動（使用者手動指派的部扉節首不被改寫），
    且其後的章名沿用該節主版，不倒退回前一節。"""
    doc = make_doc([
        {"text": "第一章｜起點", "style": CHAPTER},
        {"text": "整" * 40, "style": BODY},
        {"text": "把留下的東西安放好", "style": "部扉大標-明體W9", "master": "B-部扉"},
        {"text": "第二章｜轉折", "style": CHAPTER},
    ])
    out = apply_page_starts(doc, template)
    assert out.paragraphs[2].master == "B-部扉"  # 手動節首不動
    assert out.paragraphs[3].master == "B-部扉"  # 補的節首沿用當前節主版


def test_page_starts_idempotent_and_noop_returns_same_object(template):
    """跑第二次無變更；無任何可補的段時回原物件（不製造無謂的新文件）。"""
    once = apply_page_starts(two_chapter_doc(), template)
    assert apply_page_starts(once, template) is once
    plain = make_doc([{"text": "整" * 40, "style": BODY}])
    assert apply_page_starts(plain, template) is plain


def test_page_starts_skips_unknown_style(template):
    """樣式名不在模版時跳過該段（不猜、不炸；由既有樣式驗證路徑處理）。"""
    doc = make_doc([
        {"text": "第一章｜起點", "style": CHAPTER},
        {"text": "字", "style": BODY},
    ])
    doc = replace(doc, paragraphs=(
        doc.paragraphs[0], replace(doc.paragraphs[1], style="不存在的樣式")))
    assert apply_page_starts(doc, template) is doc


# ---------- session 層：AI 指派回路 ----------

def test_apply_para_styles_breaks_page_at_chapter(template):
    """把段改成章名大標＝該段起新頁（AI 指派後即生效，不必再手動切節）。"""
    doc = make_doc([
        {"text": "第一章｜起點", "style": CHAPTER},
        {"text": "整" * 40, "style": BODY},
        {"text": "第二章｜轉折", "style": BODY},  # 待指派
    ])
    session = EditSession(doc, template)
    assert len(session.layout.pages) == 1
    result = session.apply_para_styles({2: CHAPTER})
    assert result.document.paragraphs[2].master == "A-內文版"
    assert len(result.layout.pages) == 2
    session.undo()
    assert session.document.paragraphs[2].master is None  # 補節首與指派同一步撤銷
    assert len(session.layout.pages) == 1
