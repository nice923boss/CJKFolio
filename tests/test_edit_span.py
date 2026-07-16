"""編輯引擎跨段選取範圍（cjkfolio/editing.py，Sprint 48）：DocSpan 跨段刪除／替換。

承 Sprint 41〜47 編輯回路：DocRange 為段內範圍，DocSpan 一般化為兩 DocCursor 界定的
跨段選取（start ≤ end）。delete_span 跨段時頭段保留 start 之前、尾段保留 end 之後、
中間整段移除，頭尾併為一段承頭段樣式與 page_no（同 merge_paragraph 慣例）；同段退化
委派 delete_range。replace_span＝delete_span 後於縫插入（承左側樣式）。apply_* 為完整
回路（編輯 → layout_document 全文重排 → locate_cell 反查游標）；EditSession.delete_span
／replace_span 入 undo／redo 歷史。純邏輯離屏可驗，為 GAPS #26 跨段字元樣式所需的
跨段範圍機制地基。測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph, Run, document_from_dict
from cjkfolio.editing import (
    DocCursor,
    DocRange,
    DocSpan,
    apply_delete_span,
    apply_replace_span,
    delete_range,
    delete_span,
    replace_span,
)
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]

BODY = "內文-明體直排"
EMPH = "內文強調-明體W9"  # 字元樣式（驗跨段刪除保留兩端 run 樣式）


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


def _plain(text: str, style: str = BODY) -> Document:
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=(Paragraph(text=text, style=style),))


def _bodies(*texts: str) -> Document:
    """A-內文版多段內文（每段單一無字元樣式 run）。"""
    return make_doc([{"text": t, "style": BODY} for t in texts])


class _FakeClock:
    """可控時鐘：預設凍結，advance() 手動推進（驗連續輸入序列被跨段刪除打斷）。"""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


def _cell_text(res, addr):
    return res.layout.pages[addr.page_number - 1].placed[addr.placed_idx].line.cells[addr.cell_idx].text


# ---------- delete_span：跨段範圍刪除（DocSpan）----------

def test_delete_span_across_two_paragraphs():
    # 段 0 caret 2（"房"後）刪到段 1 caret 2（"光"後）→ 頭 "三房"＋尾 "良好" 併為一段
    out = delete_span(_bodies("三房兩廳", "採光良好"),
                      DocSpan(DocCursor(0, 2), DocCursor(1, 2)))
    assert len(out.paragraphs) == 1
    assert out.paragraphs[0].text == "三房良好"


def test_delete_span_removes_middle_paragraphs():
    # 段 0 caret 1 刪到段 3 caret 1 → 中間段 1／2 整段移除，頭 "第"＋尾 "四段" 併段
    out = delete_span(_bodies("第一段", "中間整段", "還有一段", "第四段"),
                      DocSpan(DocCursor(0, 1), DocCursor(3, 1)))
    assert len(out.paragraphs) == 1
    assert out.paragraphs[0].text == "第四段"


def test_delete_span_adopts_head_style_and_page_no():
    # 併段承頭段樣式與 page_no（頭段存活，同 merge_paragraph 慣例）
    doc = Document(title="t", template="neizai-zhengli", master="D-目錄",
                   paragraphs=(Paragraph(text="第一章", style="個案中標-NotoSans", page_no="12"),
                               Paragraph(text="內文段", style=BODY)))
    out = delete_span(doc, DocSpan(DocCursor(0, 1), DocCursor(1, 1)))
    p = out.paragraphs[0]
    assert p.text == "第文段"  # 頭 "第"＋尾 "文段"
    assert p.style == "個案中標-NotoSans"
    assert p.page_no == "12"


def test_delete_span_preserves_boundary_run_styles():
    # 頭段（"發言"＋"重點"[強調]）、尾段（"補述"＋"結語"[強調]）
    head = Paragraph(style="訪談發言body", runs=(Run("發言"), Run("重點", EMPH)))
    tail = Paragraph(style="訪談發言body", runs=(Run("補述"), Run("結語", EMPH)))
    doc = Document(title="t", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(head, tail))
    # 段 0 caret 3（"重"後）刪到段 1 caret 3（"結"後）→ 頭保 "發言重"、尾保 "語"（兩端樣式各保）
    out = delete_span(doc, DocSpan(DocCursor(0, 3), DocCursor(1, 3)))
    p = out.paragraphs[0]
    assert p.text == "發言重語"
    assert [(r.text, r.char_style) for r in p.runs] == [
        ("發言", None), ("重", EMPH), ("語", EMPH)]


def test_delete_span_same_paragraph_delegates_to_range():
    # 同段 DocSpan 退化為段內 delete_range（結果等價、仍單段）
    doc = _plain("三房大兩廳")
    span_out = delete_span(doc, DocSpan(DocCursor(0, 2), DocCursor(0, 3)))
    range_out = delete_range(doc, DocRange(0, 2, 3))
    assert span_out.paragraphs[0].text == range_out.paragraphs[0].text == "三房兩廳"
    assert len(span_out.paragraphs) == 1


def test_delete_span_empty_is_noop_same_object():
    doc = _plain("三房兩廳")
    assert delete_span(doc, DocSpan(DocCursor(0, 2), DocCursor(0, 2))) is doc  # start==end no-op


def test_delete_span_whole_two_paras_to_single_empty():
    # 段 0 首刪到段 1 末 → 全空單段（正規化為單一空 run，守 document@2）
    out = delete_span(_bodies("三房", "兩廳"),
                      DocSpan(DocCursor(0, 0), DocCursor(1, 2)))
    assert len(out.paragraphs) == 1
    assert out.paragraphs[0].text == ""
    assert "".join(r.text for r in out.paragraphs[0].runs) == ""


def test_delete_span_immutable_original_untouched():
    doc = _bodies("三房兩廳", "採光良好")
    delete_span(doc, DocSpan(DocCursor(0, 2), DocCursor(1, 2)))
    assert len(doc.paragraphs) == 2 and doc.paragraphs[0].text == "三房兩廳"  # 原文件不可變


def test_delete_span_rejects_start_after_end():
    # 起點段晚於終點段（起點 > 終點）→ ValueError（系統邊界快速失敗）
    with pytest.raises(ValueError):
        delete_span(_bodies("三房", "兩廳"), DocSpan(DocCursor(1, 1), DocCursor(0, 1)))


def test_delete_span_rejects_out_of_range_para():
    with pytest.raises(IndexError):
        delete_span(_plain("三房"), DocSpan(DocCursor(0, 0), DocCursor(9, 0)))


def test_delete_span_rejects_out_of_range_caret():
    with pytest.raises(ValueError):
        delete_span(_bodies("三房", "兩廳"), DocSpan(DocCursor(0, 0), DocCursor(1, 9)))


# ---------- replace_span：跨段範圍替換（承接縫左側樣式）----------

def test_replace_span_across_paragraphs_inserts_at_seam():
    # 段 0 caret 2 到段 1 caret 2 替換為 "格局" → "三房"＋"格局"＋"良好"
    out = replace_span(_bodies("三房兩廳", "採光良好"),
                       DocSpan(DocCursor(0, 2), DocCursor(1, 2)), "格局")
    assert len(out.paragraphs) == 1
    assert out.paragraphs[0].text == "三房格局良好"


def test_replace_span_inherits_left_style():
    # 縫左側殘存 run＝"重"（強調）→ 新字併入承接強調樣式
    head = Paragraph(style="訪談發言body", runs=(Run("發言"), Run("重點", EMPH)))
    tail = Paragraph(style="訪談發言body", runs=(Run("補述"),))
    doc = Document(title="t", template="neizai-zhengli", master="A-內文版",
                   paragraphs=(head, tail))
    out = replace_span(doc, DocSpan(DocCursor(0, 3), DocCursor(1, 1)), "X")
    p = out.paragraphs[0]
    assert p.text == "發言重X述"
    assert [(r.text, r.char_style) for r in p.runs] == [
        ("發言", None), ("重X", EMPH), ("述", None)]


def test_replace_span_empty_text_is_delete():
    out = replace_span(_bodies("三房兩廳", "採光良好"),
                       DocSpan(DocCursor(0, 2), DocCursor(1, 2)), "")
    assert out.paragraphs[0].text == "三房良好"  # text 空＝退化為純刪除


# ---------- apply_delete_span／apply_replace_span：完整回路（跨段編輯 → reflow → 反查）----------

def test_apply_delete_span_reflows_and_locates_seam(template):
    doc = _bodies("三房兩廳約三十坪", "採光良好通風佳")
    # 段 0 caret 4（"廳"後）刪到段 1 caret 2（"光"後）→ 頭 "三房兩廳"＋尾 "良好通風佳"
    res = apply_delete_span(doc, template, DocSpan(DocCursor(0, 4), DocCursor(1, 2)))
    assert len(res.document.paragraphs) == 1
    assert res.document.paragraphs[0].text == "三房兩廳良好通風佳"
    assert len(doc.paragraphs) == 2  # 原文件不變
    assert res.layout.violations == []  # reflow 0 禁則違規
    assert res.cursor == DocCursor(0, 4)  # 縫
    assert res.address is not None
    assert _cell_text(res, res.address) == "廳"  # caret 4 反查 target 3＝"廳"（縫左鄰）


def test_apply_delete_span_whole_span_address_none(template):
    # 全刪兩段 → 單一空段無可見字格 → address None（合法，同全刪空段先例）
    res = apply_delete_span(_bodies("三房", "兩廳"), template,
                            DocSpan(DocCursor(0, 0), DocCursor(1, 2)))
    assert len(res.document.paragraphs) == 1
    assert res.document.paragraphs[0].text == ""
    assert res.cursor == DocCursor(0, 0)
    assert res.address is None


def test_apply_replace_span_reflows_and_locates_cursor(template):
    doc = _bodies("三房兩廳", "採光良好")
    # 段 0 caret 2 到段 1 caret 2 替換為 "格局" → 新 caret＝2＋2＝4
    res = apply_replace_span(doc, template, DocSpan(DocCursor(0, 2), DocCursor(1, 2)), "格局")
    assert len(res.document.paragraphs) == 1
    assert res.document.paragraphs[0].text == "三房格局良好"
    assert len(doc.paragraphs) == 2  # 原文件不變
    assert res.layout.violations == []
    assert res.cursor == DocCursor(0, 4)
    assert res.address is not None
    assert _cell_text(res, res.address) == "局"  # caret 4 反查 target 3＝"局"（最後一個新字）


def test_apply_replace_span_cursor_roundtrips_through_resolve(template):
    """跨段替換後 address 反查的字，切片回原文＝剛插入的最後一字（選取不錯位）。"""
    doc = _bodies("三房兩廳", "採光良好的老公寓")
    res = apply_replace_span(doc, template, DocSpan(DocCursor(0, 2), DocCursor(1, 2)), "採光")
    addr = res.address
    pl = res.layout.pages[addr.page_number - 1].placed[addr.placed_idx]
    cell = pl.line.cells[addr.cell_idx]
    assert pl.para_idx == 0
    assert res.document.paragraphs[0].text[cell.span[0]:cell.span[1]] == cell.text == "光"


# ---------- EditSession：跨段刪除／替換路由（undo／redo）----------

def test_session_routes_delete_span_and_replace_span(template):
    s = EditSession(_bodies("三房兩廳", "採光良好", "通風佳"), template)
    s.delete_span(DocSpan(DocCursor(0, 2), DocCursor(1, 2)))  # 頭 "三房"＋尾 "良好" 併段
    assert len(s.document.paragraphs) == 2 and s.document.paragraphs[0].text == "三房良好"
    s.replace_span(DocSpan(DocCursor(0, 1), DocCursor(1, 1)), "格")  # 再跨新段 0／1 替換
    assert len(s.document.paragraphs) == 1 and s.document.paragraphs[0].text == "三格風佳"
    assert s.layout.violations == []
    s.undo()  # 回退 replace_span
    assert len(s.document.paragraphs) == 2 and s.document.paragraphs[0].text == "三房良好"
    s.undo()  # 回退 delete_span
    assert len(s.document.paragraphs) == 3 and s.document.paragraphs[0].text == "三房兩廳"
    assert s.can_undo() is False


def test_session_delete_span_breaks_coalesce_run(template):
    # 跨段刪除為非插入操作，打斷連續輸入序列（其後打字起新 undo 單元）
    s = EditSession(_bodies("兩廳", "採光"), template, clock=_FakeClock())
    s.insert(DocCursor(0, 0), "三")  # "三兩廳"，run 尾 caret 1
    s.delete_span(DocSpan(DocCursor(0, 3), DocCursor(1, 1)))  # 跨段刪 → "三兩廳光"，打斷序列
    s.insert(DocCursor(0, 1), "房")  # caret 1＝原 run 尾，但已被 delete_span 打斷 → 新單元
    assert s.document.paragraphs[0].text == "三房兩廳光"
    s.undo()  # 只退 "房"（delete_span 已起新單元、未與首次 insert 合併）
    assert s.document.paragraphs[0].text == "三兩廳光"
    assert s.can_undo() is True
