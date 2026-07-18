"""AI 指派背景執行緒的判定層（editor.ai_assign_core，Sprint 104）。

本檔驗的是 Qt 無關的一件事，故不需 PySide6：**建議索引的有效性守門**。

`suggest_styles` 回的是 `{段序: 樣式}` 語意的位置列，位置繫於送檢當下的段落
文字序列。AI 呼叫改跑背景執行緒後，使用者在等待期間可以繼續編輯，若回來時
段落已增刪或改寫，仍照索引套用就會把建議安到別的段落上（沉默的錯派）。故
送檢前取文字快照，回來時比對相同才放行。

樣式改變不使快照失效：對話框逐列讀的是現行樣式，建議本身只依文字內容而定。

素材一律自擬（版權紅線）。
"""
from cjkfolio.document import document_from_dict
from editor.ai_assign_core import assignments_still_apply, paragraph_texts


def sample_doc(*paragraphs) -> object:
    """自擬文件：paragraphs 為 (文字, 樣式) 序對。"""
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "指派守門測試", "template": "neizai-zhengli",
                 "master": "A-內文版", "language": "zh-TW"},
        "paragraphs": [{"text": t, "style": s} for t, s in paragraphs],
        "images": [],
    })


BASE = (("第一段文字，內容任意。", "內文-明體直排"),
        ("第二段文字，內容任意。", "內文-明體直排"),
        ("第三段文字，內容任意。", "內文-明體直排"))


def test_paragraph_texts_is_ordered_snapshot():
    """快照＝逐段文字的有序 tuple（不可變，worker 讀不到後續編輯）。"""
    texts = paragraph_texts(sample_doc(*BASE))
    assert texts == ("第一段文字，內容任意。", "第二段文字，內容任意。",
                     "第三段文字，內容任意。")
    assert isinstance(texts, tuple)


def test_unchanged_document_still_applies():
    doc = sample_doc(*BASE)
    assert assignments_still_apply(doc, paragraph_texts(doc))


def test_style_only_change_still_applies():
    """只改樣式不改文字＝建議仍對得上（建議依文字內容而定）。"""
    before = sample_doc(*BASE)
    snapshot = paragraph_texts(before)
    after = sample_doc(("第一段文字，內容任意。", "章節小標-黑體"),
                       ("第二段文字，內容任意。", "內文-明體直排"),
                       ("第三段文字，內容任意。", "內文-明體直排"))
    assert assignments_still_apply(after, snapshot)


def test_edited_text_does_not_apply():
    """段落被改寫＝該段建議已非依此文字得出，不放行。"""
    snapshot = paragraph_texts(sample_doc(*BASE))
    edited = sample_doc(("第一段文字，內容任意。已插入字。", "內文-明體直排"),
                        *BASE[1:])
    assert not assignments_still_apply(edited, snapshot)


def test_inserted_paragraph_does_not_apply():
    """插入段落＝其後所有索引位移，硬套即整批錯位。"""
    snapshot = paragraph_texts(sample_doc(*BASE))
    inserted = sample_doc(BASE[0], ("插入的新段落。", "內文-明體直排"), *BASE[1:])
    assert not assignments_still_apply(inserted, snapshot)


def test_deleted_paragraph_does_not_apply():
    snapshot = paragraph_texts(sample_doc(*BASE))
    assert not assignments_still_apply(sample_doc(*BASE[:2]), snapshot)


def test_reordered_paragraphs_do_not_apply():
    """段落順序對調＝文字集合相同但位置不同，仍屬錯位（比對須依序）。"""
    snapshot = paragraph_texts(sample_doc(*BASE))
    swapped = sample_doc(BASE[1], BASE[0], BASE[2])
    assert not assignments_still_apply(swapped, snapshot)
