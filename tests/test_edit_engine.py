"""編輯引擎回路（cjkfolio/editing.py，Sprint 41）：游標插字 → reflow → 反查新游標。

Phase 2 最複雜架構（§7 Pre-mortem 未退場最大風險「畫布與排版核心同步／選取錯位」）
的可離屏驗證核心。純邏輯層（不碰 Qt），與 layout/engine 同入 pytest 基線。
游標座標系＝段 text（normalize 前原字串）半開座標，與 Cell.span（Sprint 18）閉環。
測試素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph, Run, document_from_dict
from cjkfolio.editing import (
    CellAddress,
    DocCursor,
    DocRange,
    apply_delete,
    apply_insert,
    apply_replace,
    delete_range,
    insert_text,
    locate_cell,
    replace_range,
)
from cjkfolio.layout import layout_document
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "C-個案扉頁"},
        "paragraphs": paragraphs,
    })


def _plain(text: str, style: str = "內文-明體直排") -> Document:
    return Document(title="t", template="neizai-zhengli", master="A-內文版",
                    paragraphs=(Paragraph(text=text, style=style),))


# ---------- insert_text：單一 run ----------

def test_insert_middle():
    out = insert_text(_plain("三房兩廳"), DocCursor(0, 2), "大")
    assert out.paragraphs[0].text == "三房大兩廳"


def test_insert_at_start():
    out = insert_text(_plain("房兩廳"), DocCursor(0, 0), "三")
    assert out.paragraphs[0].text == "三房兩廳"


def test_insert_at_end():
    out = insert_text(_plain("三房兩"), DocCursor(0, 3), "廳")
    assert out.paragraphs[0].text == "三房兩廳"


def test_insert_empty_text_is_noop_same_object():
    doc = _plain("三房")
    assert insert_text(doc, DocCursor(0, 1), "") is doc


def test_insert_immutable_original_untouched():
    doc = _plain("三房兩廳")
    insert_text(doc, DocCursor(0, 2), "大")
    assert doc.paragraphs[0].text == "三房兩廳"  # 原文件不可變，不被就地修改


def test_insert_rejects_out_of_range_caret():
    with pytest.raises(ValueError):
        insert_text(_plain("三房"), DocCursor(0, 5), "x")


def test_insert_rejects_out_of_range_para():
    with pytest.raises(IndexError):
        insert_text(_plain("三房"), DocCursor(9, 0), "x")


# ---------- insert_text：多 run（字元樣式邊界）----------

def _two_run_doc() -> Document:
    return Document(
        title="t", template="neizai-zhengli", master="A-內文版",
        paragraphs=(Paragraph(style="訪談發言body",
                              runs=(Run("發言"), Run("重點", "內文強調-明體W9"))),),
    )


def test_insert_at_run_boundary_inherits_left_style():
    # text="發言重點"，caret 2＝run0／run1 邊界；左偏併入 run0（承接其樣式 None）
    out = insert_text(_two_run_doc(), DocCursor(0, 2), "X")
    p = out.paragraphs[0]
    assert p.text == "發言X重點"
    assert (p.runs[0].text, p.runs[0].char_style) == ("發言X", None)
    assert (p.runs[1].text, p.runs[1].char_style) == ("重點", "內文強調-明體W9")


def test_insert_inside_styled_run_keeps_style():
    # caret 3＝run1（"重點"）內部，插入承接 run1 樣式，不新增 run
    out = insert_text(_two_run_doc(), DocCursor(0, 3), "X")
    p = out.paragraphs[0]
    assert p.text == "發言重X點"
    assert len(p.runs) == 2
    assert (p.runs[1].text, p.runs[1].char_style) == ("重X點", "內文強調-明體W9")


# ---------- locate_cell：resolve_hit 的逆（span 反查）----------

def test_locate_cell_inverts_span_for_all_cells(template):
    doc = make_doc([
        {"text": "案例速寫", "style": "個案欄標-黑W7"},
        {"text": "重新安放生活的重量", "style": "個案扉頁大標-NotoSans"},
        {"text": "三房兩廳，約三十坪的老公寓。", "style": "內文-明體直排"},
    ])
    layout = layout_document(doc, template)
    checked = 0
    for page in layout.pages:
        for pi, pl in enumerate(page.placed):
            if pl.para_idx is None:
                continue
            for ci, cell in enumerate(pl.line.cells):
                if cell.span is None:
                    continue
                caret = cell.span[1]  # caret 落在此字格之後 → 應反查回本格
                addr = locate_cell(layout, DocCursor(pl.para_idx, caret))
                assert addr == CellAddress(page.number, pi, ci), (
                    f"字格 {pi},{ci} span {cell.span} 反查失敗，得 {addr}"
                )
                checked += 1
    assert checked > 0


def test_locate_cell_returns_none_for_unknown_para(template):
    doc = make_doc([{"text": "三房兩廳", "style": "內文-明體直排"}])
    layout = layout_document(doc, template)
    assert locate_cell(layout, DocCursor(99, 0)) is None


# ---------- apply_insert：完整回路（插字 → reflow → 反查）----------

def test_apply_insert_reflows_and_locates_cursor(template):
    doc = make_doc([
        {"text": "案例速寫", "style": "個案欄標-黑W7"},
        {"text": "重新安放生活的重量", "style": "個案扉頁大標-NotoSans"},
        {"text": "【空間】", "style": "個案中標-NotoSans"},
        {"text": "三房兩廳，約三十坪的老公寓。", "style": "內文-明體直排"},
    ])
    # 段 3（內文）caret 4＝"廳"後（，之前），插入 "大大"
    res = apply_insert(doc, template, DocCursor(3, 4), "大大")

    # 文件已變（不可變產生新 Document）
    assert res.document.paragraphs[3].text == "三房兩廳大大，約三十坪的老公寓。"
    assert doc.paragraphs[3].text == "三房兩廳，約三十坪的老公寓。"  # 原文件不變

    # reflow 乾淨（0 禁則違規）
    assert res.layout.violations == []

    # 新游標 caret = 4+2 = 6；畫布落點字格＝最後插入字 "大"
    assert res.cursor == DocCursor(3, 6)
    assert res.address is not None
    addr = res.address
    cell = res.layout.pages[addr.page_number - 1].placed[addr.placed_idx].line.cells[addr.cell_idx]
    assert cell.text == "大"

    # 插入內容確在新版面段 3
    joined = "".join(
        c.text
        for pg in res.layout.pages
        for pl in pg.placed
        if pl.para_idx == 3
        for c in pl.line.cells
    )
    assert "大大" in joined


def test_apply_insert_cursor_roundtrips_through_resolve(template):
    """插入後 address 反查的段／字，切片回原文＝剛插入的最後一字（選取不錯位）。"""
    doc = make_doc([{"text": "三房兩廳，約三十坪的老公寓。", "style": "內文-明體直排"}])
    res = apply_insert(doc, template, DocCursor(0, 4), "採光")
    addr = res.address
    pl = res.layout.pages[addr.page_number - 1].placed[addr.placed_idx]
    cell = pl.line.cells[addr.cell_idx]
    assert pl.para_idx == 0
    assert res.document.paragraphs[0].text[cell.span[0]:cell.span[1]] == cell.text == "光"


# ---------- delete_range：段內範圍刪除（多 run 切割）----------

def test_delete_middle():
    out = delete_range(_plain("三房大兩廳"), DocRange(0, 2, 3))
    assert out.paragraphs[0].text == "三房兩廳"


def test_delete_at_start():
    out = delete_range(_plain("三房兩廳"), DocRange(0, 0, 1))
    assert out.paragraphs[0].text == "房兩廳"


def test_delete_to_end():
    out = delete_range(_plain("三房兩廳"), DocRange(0, 2, 4))
    assert out.paragraphs[0].text == "三房"


def test_delete_whole_paragraph_empties_runs():
    out = delete_range(_plain("三房兩廳"), DocRange(0, 0, 4))
    assert out.paragraphs[0].text == ""
    assert "".join(r.text for r in out.paragraphs[0].runs) == ""  # 全刪＝空段：runs 串接為空（Paragraph 空段正規化為單一空 run，守 document@2 不變式）


def test_delete_empty_range_noop_same_object():
    doc = _plain("三房")
    assert delete_range(doc, DocRange(0, 1, 1)) is doc  # start==end no-op 回原物件


def test_delete_immutable_original_untouched():
    doc = _plain("三房兩廳")
    delete_range(doc, DocRange(0, 1, 3))
    assert doc.paragraphs[0].text == "三房兩廳"  # 原文件不可變


def test_delete_rejects_out_of_range_end():
    with pytest.raises(ValueError):
        delete_range(_plain("三房"), DocRange(0, 0, 9))


def test_delete_rejects_start_gt_end():
    with pytest.raises(ValueError):
        delete_range(_plain("三房兩廳"), DocRange(0, 3, 1))


def test_delete_rejects_out_of_range_para():
    with pytest.raises(IndexError):
        delete_range(_plain("三房"), DocRange(9, 0, 1))


def test_delete_across_runs_preserves_boundary_styles():
    # runs＝("發言", "重點"[內文強調])；刪 [1,3)＝"言重"，留 "發"＋"點"（兩端樣式各保）
    out = delete_range(_two_run_doc(), DocRange(0, 1, 3))
    p = out.paragraphs[0]
    assert p.text == "發點"
    assert (p.runs[0].text, p.runs[0].char_style) == ("發", None)
    assert (p.runs[1].text, p.runs[1].char_style) == ("點", "內文強調-明體W9")


def test_delete_removes_whole_styled_run():
    # 刪 [2,4)＝整個 "重點" run；剩 "發言"（樣式 None），帶樣式 run 整個消失
    out = delete_range(_two_run_doc(), DocRange(0, 2, 4))
    p = out.paragraphs[0]
    assert p.text == "發言"
    assert len(p.runs) == 1
    assert (p.runs[0].text, p.runs[0].char_style) == ("發言", None)


# ---------- replace_range：範圍替換（承接左側樣式）----------

def test_replace_range_swaps_text():
    out = replace_range(_plain("三房兩廳"), DocRange(0, 2, 4), "一廳")
    assert out.paragraphs[0].text == "三房一廳"


def test_replace_inherits_left_style():
    # 替換 [1,3)＝"言重" 為 "X"；新字併入左側殘存 run（"發"，樣式 None）
    out = replace_range(_two_run_doc(), DocRange(0, 1, 3), "X")
    p = out.paragraphs[0]
    assert p.text == "發X點"
    assert (p.runs[0].text, p.runs[0].char_style) == ("發X", None)
    assert (p.runs[1].text, p.runs[1].char_style) == ("點", "內文強調-明體W9")


def test_replace_empty_text_is_delete():
    out = replace_range(_plain("三房兩廳"), DocRange(0, 1, 3), "")
    assert out.paragraphs[0].text == "三廳"  # text 空＝退化為純刪除


def test_replace_whole_paragraph_then_insert():
    # 全刪成空段再插入，覆蓋 insert_text 空段 caret==0 路徑（選取整段內容後打字替換）
    out = replace_range(_plain("三房兩廳"), DocRange(0, 0, 4), "新家")
    p = out.paragraphs[0]
    assert p.text == "新家"
    assert len(p.runs) == 1
    assert p.runs[0].char_style is None


# ---------- apply_delete／apply_replace：完整回路（編輯 → reflow → 反查）----------

def test_apply_delete_reflows_and_locates_cursor(template):
    doc = make_doc([
        {"text": "案例速寫", "style": "個案欄標-黑W7"},
        {"text": "重新安放生活的重量", "style": "個案扉頁大標-NotoSans"},
        {"text": "三房兩廳，約三十坪的老公寓。", "style": "內文-明體直排"},
    ])
    # 段 2 刪 [4,6)＝"，約" → 新 caret＝4（"廳"後）
    res = apply_delete(doc, template, DocRange(2, 4, 6))
    assert res.document.paragraphs[2].text == "三房兩廳三十坪的老公寓。"
    assert doc.paragraphs[2].text == "三房兩廳，約三十坪的老公寓。"  # 原文件不變
    assert res.layout.violations == []  # reflow 0 禁則違規
    assert res.cursor == DocCursor(2, 4)
    assert res.address is not None
    addr = res.address
    cell = res.layout.pages[addr.page_number - 1].placed[addr.placed_idx].line.cells[addr.cell_idx]
    assert cell.text == "廳"  # caret 4 反查 target 3＝"廳"（刪除點左鄰）


def test_apply_delete_whole_para_address_none(template):
    doc = make_doc([{"text": "三房兩廳", "style": "內文-明體直排"}])
    # 全刪成空段：段無可見字格可落 → address None（合法，EditResult.address Optional）
    res = apply_delete(doc, template, DocRange(0, 0, 4))
    assert res.document.paragraphs[0].text == ""
    assert res.cursor == DocCursor(0, 0)
    assert res.address is None


def test_apply_replace_reflows_and_locates_cursor(template):
    doc = make_doc([
        {"text": "案例速寫", "style": "個案欄標-黑W7"},
        {"text": "重新安放生活的重量", "style": "個案扉頁大標-NotoSans"},
        {"text": "三房兩廳，約三十坪的老公寓。", "style": "內文-明體直排"},
    ])
    # 段 2 替換 [0,4)＝"三房兩廳" 為 "兩房"；新 caret＝0＋2＝2
    res = apply_replace(doc, template, DocRange(2, 0, 4), "兩房")
    assert res.document.paragraphs[2].text == "兩房，約三十坪的老公寓。"
    assert doc.paragraphs[2].text == "三房兩廳，約三十坪的老公寓。"  # 原文件不變
    assert res.layout.violations == []
    assert res.cursor == DocCursor(2, 2)
    assert res.address is not None
    addr = res.address
    cell = res.layout.pages[addr.page_number - 1].placed[addr.placed_idx].line.cells[addr.cell_idx]
    assert cell.text == "房"  # caret 2 反查 target 1＝"房"


def test_apply_replace_cursor_roundtrips_through_resolve(template):
    """替換後 address 反查的段／字，切片回原文＝剛插入的最後一字（選取不錯位）。"""
    doc = make_doc([{"text": "三房兩廳，約三十坪的老公寓。", "style": "內文-明體直排"}])
    res = apply_replace(doc, template, DocRange(0, 0, 2), "採光")
    addr = res.address
    pl = res.layout.pages[addr.page_number - 1].placed[addr.placed_idx]
    cell = pl.line.cells[addr.cell_idx]
    assert pl.para_idx == 0
    assert res.document.paragraphs[0].text[cell.span[0]:cell.span[1]] == cell.text == "光"
