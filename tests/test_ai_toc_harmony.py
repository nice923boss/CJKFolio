"""同編號目次一致化與前言（Sprint 159，cjkfolio.ai_toc_harmony＋editing.insert_preface）。

重現案例：同一批 AI 回應只把「四、」到「七、」列入目次並判成大標題，「一、」到
「三、」留內文不列（真稿實測，重跑又全對）。一致化後七段全列、層級一致；段首
引題段回內文。基線零網路：transport 一律注入假回應。測試素材一律自擬。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.ai_config import AiConfig
from cjkfolio.ai_style import SuggestResult, suggest_styles
from cjkfolio.ai_toc_harmony import _harmonize_numbered, _preface_at
from cjkfolio.document import Document, Paragraph
from cjkfolio.editing import insert_preface
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

CONFIG = AiConfig(base_url="http://unit.test/v1", api_key="unit-secret-key", model="m")
CANDIDATES = ("章名大標-明體W7", "章節小標-黑體", "內文-明體直排")
DEFAULT = "內文-明體直排"
HEAD = "章名大標-明體W7"
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"

MEMOIR = [
    "我出生在海邊的小鎮，家裡開雜貨店，童年記憶都是貨架與海風。",
    "趁這次機會，把一路走來的幾段時光寫下來：",
    "一、求學階段：每天走一小時的路上學。",
    "二、初入職場：第一份工作在紡織廠。",
    "三、成家立業：二十六歲結婚。",
    "四、創業維艱：開了第一家店。",
    "五、中年轉折：店面收掉後重新學習。",
    "六、含飴弄孫：孫子出生後搬回老家。",
    "那幾年最大的收穫是學會放慢腳步。",
    "七、不枉一生、智慧傳承：",
    "把這些經驗留給下一代。",
]


def _reply(items):
    return json.dumps([dict(index=i, style=s, **({"toc_title": t, "toc_level": lv} if t else {}))
                       for i, (s, t, lv) in enumerate(items)])


def _transport(text):
    def transport(url, headers, body, timeout):
        return {"choices": [{"message": {"content": text}}]}
    return transport


def _bad_memoir_reply():
    """真稿那次的回應形狀：一～三 內文不列，四～七 大標題並列入第 2 層。"""
    items = [(DEFAULT, None, None)] * 5
    items += [(HEAD, f"{MEMOIR[i][:4]}", 2) for i in (5, 6, 7)]
    items += [(DEFAULT, None, None), (HEAD, "七、不枉一生、智慧傳承", 2), (DEFAULT, None, None)]
    return _reply(items)


def test_numbered_family_fills_missing_entries_and_restores_run_in_body():
    result = suggest_styles(MEMOIR, CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=_transport(_bad_memoir_reply()))
    titled = [(i, e) for i, e in enumerate(result.toc_entries) if e is not None]
    assert [i for i, _ in titled] == [2, 3, 4, 5, 6, 7, 9]
    assert titled[0][1] == ("一、求學階段", 2)       # 段首引題取到冒號為止
    assert all(level == 2 for _i, (_t, level) in titled)
    # 段首引題整段是內文：四～六 回預設內文；獨立標題段 七 保留 AI 給的樣式
    assert result.assignments[2:8] == (DEFAULT,) * 6
    assert result.assignments[9] == HEAD
    assert any("「一、」編號補列 3 段、改樣式 3 段" in w for w in result.warnings)


def test_preface_suggested_before_leading_body_text():
    result = suggest_styles(MEMOIR, CANDIDATES, CONFIG, default_style=DEFAULT,
                            transport=_transport(_bad_memoir_reply()))
    assert result.preface == (0, 2, HEAD)


def test_no_preface_when_first_entry_opens_the_book_or_heading_exists():
    entries = [("第一章", 2), None]
    assert _preface_at(["第一章", "內文。"], [HEAD, DEFAULT], entries, DEFAULT) is None
    texts = ["自序", "寫在前面的話。", "一、童年"]
    entries = [None, None, ("一、童年", 2)]
    assert _preface_at(texts, [DEFAULT, DEFAULT, HEAD], entries, DEFAULT) is None
    assert _preface_at(["內文。"], [DEFAULT], [None], DEFAULT) is None


def test_preface_style_falls_back_to_body_when_all_entries_are_run_in():
    texts = ["開場白。", "一、童年：在鄉下。", "二、求學：在城裡。"]
    entries = [None, ("一、童年", 2), ("二、求學", 2)]
    assert _preface_at(texts, [DEFAULT] * 3, entries, DEFAULT) == (0, 2, DEFAULT)


def test_numbered_guard_skips_toc_entry_styles_and_unsuggested_paragraphs():
    """作者手寫目錄（掛目次條目樣式）不入組；AI 沒回建議的段不改樣式。"""
    texts = ["一、童年……3", "一、童年：在鄉下。", "二、求學：在城裡。"]
    styles, entries, _notes = _harmonize_numbered(
        texts, ["目錄-篇章條目", None, HEAD], [None, None, ("二、求學", 2)], DEFAULT,
        toc_styles=frozenset({"目錄-篇章條目"}))
    assert entries == [None, ("一、童年", 2), ("二、求學", 2)]
    assert styles == ["目錄-篇章條目", None, DEFAULT]


def test_insert_preface_moves_section_master_to_heading():
    doc = Document(title="t", template="x", master="A-內文版", paragraphs=(
        Paragraph(text="開場白。", style=DEFAULT, master="A-內文版"),
        Paragraph(text="一、童年", style=HEAD)))
    out = insert_preface(doc, 0, 2, HEAD)
    head, body = out.paragraphs[0], out.paragraphs[1]
    assert (head.text, head.style, head.toc_title, head.toc_level) == ("前言", HEAD, "前言", 2)
    assert head.master == "A-內文版" and body.master is None
    assert body.text == "開場白。" and len(out.paragraphs) == 3
    with pytest.raises(IndexError):
        insert_preface(doc, 2, 2, HEAD)


def test_session_inserts_preface_in_same_undo_step_as_styles_and_toc():
    template = load_template(TEMPLATE)
    src = Document(title="t", template="neizai-zhengli", master="A-內文版", paragraphs=(
        Paragraph(text="開場白。", style=DEFAULT),
        Paragraph(text="一、童年：在鄉下。", style=DEFAULT),
        Paragraph(text="二、求學：在城裡。", style=DEFAULT)))
    session = EditSession(src, template)
    session.apply_para_styles({}, {1: ("一、童年", 2), 2: ("二、求學", 2)},
                              generate_toc=True, preface=(0, 2, DEFAULT))
    body = [p for p in session.document.paragraphs if p.toc_title]
    assert [p.toc_title for p in body] == ["前言", "一、童年", "二、求學"]
    toc_lines = [p.text for p in session.document.paragraphs[:4]]
    assert any(t.startswith("前言") for t in toc_lines)   # 目次第一條＝前言
    session.undo()
    assert session.document == src and not session.can_undo()


def test_suggest_result_preface_defaults_to_none():
    """SuggestResult.preface 預設 None：舊呼叫端（無前言）不受影響。"""
    assert SuggestResult((), (), 0).preface is None
