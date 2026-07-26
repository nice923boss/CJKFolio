"""書眉／頁碼編輯（cjkfolio/style_editing.set_footer_item，Sprint 142）：改字、挪位置。

Owner 回饋：右下角固定呈現的書名要能改文字、移動位置、批次移動位置，
「避免指派錯誤還可以手動修改」。故本檔驗三件事：

1. 模型層：FooterItem.text 字面覆寫的載入正規化（缺／null／空白皆＝無覆寫）與序列化往返。
2. 編輯層：set_footer_item 只開 text 與兩個位置欄位，單一主版與批次兩種語意，
   等值變更 no-op 回原物件（不推 undo 步），未知主版／元素／欄位快速失敗。
3. 送印層：覆寫後 PDF 內實際印出的字與位置改變（PyMuPDF 讀回，與寫出層不同實作，
   Gate 4 獨立驗證）；且「覆寫成 X」與「書名本來就是 X」印出同一份文字（等價驗證）。

測試素材一律自擬（版權紅線）。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.session import EditSession
from cjkfolio.style_editing import set_footer_item
from cjkfolio.styles import (
    TemplateError,
    load_template,
    template_from_dict,
    template_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

BODY = "內文-明體直排"
TITLE = "running_title"   # A-內文版／E-序文版 皆有的書眉元素（source＝title）

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(title: str = "自擬樣張"):
    """兩頁份的自擬直排稿（書眉在偶數書頁，故需跨頁）。"""
    body = (
        "整理是一場與過去的對話，我們把留下的物件一件件安放，也把回憶安放。"
        "直排的世界裡，文字由上而下、由右而左，讀者的視線像水流一樣落下。"
    ) * 8
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": title, "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": [{"text": body, "style": BODY}],
    })


# ---------- 模型層：載入正規化與序列化往返 ----------

def test_footer_text_absent_is_none(template):
    """模版沒寫 text＝無覆寫（既有模版原樣載入，不因新欄位改變語意）。"""
    assert template.masters["A-內文版"].footer[TITLE].text is None
    assert template.masters["A-內文版"].footer["page_number"].text is None


@pytest.mark.parametrize("raw, expected", [
    ("手記", "手記"),
    ("  留白書名  ", "留白書名"),   # 前後空白修掉（Owner 從輸入欄貼字的常態）
    ("", None),                     # 空字串＝清掉覆寫，回文件書名
    ("   ", None),
    (None, None),
])
def test_footer_text_normalised_on_load(raw, expected):
    """缺、null、空白字串一律正規化成同一個「無覆寫」表示法。"""
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["A-內文版"]["footer"][TITLE]["text"] = raw
    tpl = template_from_dict(data)
    assert tpl.masters["A-內文版"].footer[TITLE].text == expected


def test_footer_text_round_trip(template):
    """序列化往返：無覆寫不寫此鍵、有覆寫原樣帶回（另存模版不遺失 Owner 的改字）。"""
    plain = template_to_dict(template)["masters"]["A-內文版"]["footer"][TITLE]
    assert "text" not in plain

    edited = set_footer_item(template, "A-內文版", TITLE, {"text": "自擬手記"})
    out = template_to_dict(edited)["masters"]["A-內文版"]["footer"][TITLE]
    assert out["text"] == "自擬手記"
    assert template_from_dict(template_to_dict(edited)) == edited


# ---------- 編輯層：單一主版、批次、no-op、快速失敗 ----------

def test_set_footer_item_single_master(template):
    """只改指定主版；原模版不可變，其他主版與其他元素物件共享。"""
    out = set_footer_item(template, "A-內文版", TITLE,
                          {"text": "自擬手記", "outer_offset_pt": 70.0})
    item = out.masters["A-內文版"].footer[TITLE]
    assert (item.text, item.outer_offset_pt) == ("自擬手記", 70.0)
    assert item.style == template.masters["A-內文版"].footer[TITLE].style  # 只動指定欄位
    assert template.masters["A-內文版"].footer[TITLE].text is None  # 原模版不可變
    assert out.masters["E-序文版"] is template.masters["E-序文版"]  # 未指名的主版不動
    assert (out.masters["A-內文版"].footer["page_number"]
            is template.masters["A-內文版"].footer["page_number"])


def test_set_footer_item_all_masters_batch(template):
    """批次移動位置：所有含同名書眉的主版一起挪（Owner 的「批次移動位置」）。"""
    before = {n: m.footer[TITLE].outer_offset_pt
              for n, m in template.masters.items() if TITLE in m.footer}
    assert set(before) == {"A-內文版", "E-序文版"}, before

    out = set_footer_item(template, "A-內文版", TITLE,
                          {"outer_offset_pt": 42.0}, all_masters=True)
    for name in before:
        assert out.masters[name].footer[TITLE].outer_offset_pt == 42.0
    for name, master in out.masters.items():   # 沒有此元素的主版原物件不動
        if TITLE not in master.footer:
            assert master is template.masters[name]


def test_set_footer_item_noop_returns_same_object(template):
    """空變更與等值變更皆 no-op 回原物件（呼叫端據此不推 undo 步）。"""
    assert set_footer_item(template, "A-內文版", TITLE, {}) is template
    same = template.masters["A-內文版"].footer[TITLE].outer_offset_pt
    assert set_footer_item(
        template, "A-內文版", TITLE, {"outer_offset_pt": same}) is template
    assert set_footer_item(
        template, "A-內文版", TITLE, {"text": "  "}) is template  # 本來就沒覆寫


def test_set_footer_item_clear_override_back_to_doc_title(template):
    """覆寫後再清空＝回到文件書名（不是印出空白）。"""
    edited = set_footer_item(template, "A-內文版", TITLE, {"text": "自擬手記"})
    cleared = set_footer_item(edited, "A-內文版", TITLE, {"text": ""})
    assert cleared.masters["A-內文版"].footer[TITLE].text is None


def test_set_footer_item_rejects_uneditable_and_unknown(template):
    """style／pages 屬版型結構不開放；未知主版與未知元素快速失敗。"""
    with pytest.raises(TemplateError, match="不可編輯的欄位"):
        set_footer_item(template, "A-內文版", TITLE, {"style": "內文-明體直排"})
    with pytest.raises(TemplateError, match="不可編輯的欄位"):
        set_footer_item(template, "A-內文版", TITLE, {"pages": "odd"})
    with pytest.raises(KeyError):
        set_footer_item(template, "沒有這個主版", TITLE, {"text": "x"})
    with pytest.raises(KeyError):
        set_footer_item(template, "A-內文版", "沒有這個書眉", {"text": "x"})
    with pytest.raises(KeyError):   # 該主版根本沒宣告頁腳
        set_footer_item(template, "H-封面", TITLE, {"text": "x"})


# ---------- session：入統一 undo 歷史 ----------

def test_session_update_footer_item_undo(template):
    """改書眉與文字、樣式編輯共用同一條 undo 歷史，一步還原。"""
    session = EditSession(make_doc(), template)
    assert session.update_footer_item(
        "A-內文版", TITLE, {"text": "自擬手記"}) is not None
    assert session.template.masters["A-內文版"].footer[TITLE].text == "自擬手記"
    assert session.can_undo()
    session.undo()
    assert session.template.masters["A-內文版"].footer[TITLE].text is None


def test_session_update_footer_item_noop_no_undo_step(template):
    """等值變更不佔 undo 步（Owner 按確定但沒改東西＝什麼都沒發生）。"""
    session = EditSession(make_doc(), template)
    assert session.update_footer_item("A-內文版", TITLE, {}) is None
    assert not session.can_undo()


def test_session_update_footer_item_batch_is_one_step(template):
    """批次挪多個主版在 Owner 眼中是一次操作，故只推一步 undo。"""
    session = EditSession(make_doc(), template)
    session.update_footer_item(
        "A-內文版", TITLE, {"outer_offset_pt": 42.0}, all_masters=True)
    assert session.template.masters["E-序文版"].footer[TITLE].outer_offset_pt == 42.0
    session.undo()
    assert (session.template.masters["E-序文版"].footer[TITLE].outer_offset_pt
            == template.masters["E-序文版"].footer[TITLE].outer_offset_pt)


# ---------- 送印層：PDF 實際印出的字與位置（PyMuPDF 讀回） ----------

def _footer_rect(pdf_page, text: str):
    hits = pdf_page.search_for(text)
    assert hits, f"PDF 內找不到書眉文字「{text}」"
    return hits[0]


@needs_fonts
def test_pdf_footer_text_override(template, tmp_path):
    """覆寫的字真的印進 PDF，且與「書名本來就是它」印出同一份文字（等價驗證）。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    overridden = set_footer_item(template, "A-內文版", TITLE, {"text": "自擬手記"})
    out_a = tmp_path / "override.pdf"
    export_pdf(make_doc("原本的書名"), overridden, out_a, first_page=30)
    page_a = fitz.open(str(out_a))[0].get_text()   # 書頁 30 為偶數＝有書眉
    assert "自擬手記" in page_a
    assert "原本的書名" not in page_a              # 覆寫優先於文件書名

    out_b = tmp_path / "titled.pdf"                # 對照組：書名本來就叫自擬手記
    export_pdf(make_doc("自擬手記"), template, out_b, first_page=30)
    assert fitz.open(str(out_b))[0].get_text() == page_a


@needs_fonts
def test_pdf_footer_position_move(template, tmp_path):
    """挪位置：outer_offset 變大＝離書口更遠（右頁往左），baseline 變大＝往下。"""
    fitz = pytest.importorskip("fitz")
    from cjkfolio.pdf_writer import export_pdf

    doc = make_doc("自擬樣張")
    base = set_footer_item(template, "A-內文版", TITLE, {"text": "自擬手記"})
    out_base = tmp_path / "base.pdf"
    export_pdf(doc, base, out_base, first_page=30)
    rect0 = _footer_rect(fitz.open(str(out_base))[0], "自擬手記")

    moved = set_footer_item(base, "A-內文版", TITLE, {
        "outer_offset_pt": base.masters["A-內文版"].footer[TITLE].outer_offset_pt + 20.0,
        "baseline_from_top_pt": (
            base.masters["A-內文版"].footer[TITLE].baseline_from_top_pt + 10.0),
    })
    out_moved = tmp_path / "moved.pdf"
    export_pdf(doc, moved, out_moved, first_page=30)
    rect1 = _footer_rect(fitz.open(str(out_moved))[0], "自擬手記")

    assert rect1.x1 == pytest.approx(rect0.x1 - 20.0, abs=0.5), (rect0, rect1)
    assert rect1.y0 == pytest.approx(rect0.y0 + 10.0, abs=0.5), (rect0, rect1)
