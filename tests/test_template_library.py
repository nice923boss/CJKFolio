"""模版庫管理面資料層（Sprint 77，§4.3 模版庫／§6 Phase 3）。

list_templates 目錄清單（壞檔列 error 不沉默、不擋清單）＋merge_draft_styles
萃取草稿一鍵併入（GAPS #37 (b)：同名跳過列報、新樣式立即可排版）＋
EditSession.apply_template 整模版替換入統一 undo（文件引用缺樣式快速失敗）＋
CLI merge-styles 端到端。測試素材一律自擬（版權紅線）。
"""
import json
from pathlib import Path

import pytest

from cjkfolio.cli import main as cli_main
from cjkfolio.document import document_from_dict
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.styles import TemplateError, load_template, save_template
from cjkfolio.template_library import list_templates, merge_draft_styles

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"

BODY = "內文-明體直排"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def make_doc(paragraphs):
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "自擬樣張", "template": "neizai-zhengli", "master": "A-內文版"},
        "paragraphs": paragraphs,
    })


DRAFT_STYLES = {
    "內文候選-明體 11.5pt": {
        "font_family": "思源宋體 TC", "font_weight": "regular", "size_pt": 11.5,
        "source_font": "DFMingStd-W3", "note": "主力字數（自擬草稿）",
    },
    "標題候選-黑體 21.9pt": {
        "font_family": "思源黑體 TC", "font_weight": "bold", "size_pt": 21.9,
        "source_font": "DFHeiStd-W7", "note": "1.9 倍於內文（自擬草稿）",
    },
}


def _draft(styles=DRAFT_STYLES):
    return {"source_pdf": "自擬.pdf", "pages": 2,
            "paragraph_styles": dict(styles), "colors": [], "skipped": []}


# ---------- list_templates ----------

def test_list_templates_builtin_dir():
    entries = list_templates(ROOT / "templates")
    builtin = next(e for e in entries if e.path.name == "neizai-zhengli.json")
    assert builtin.error is None
    assert builtin.name == "《內在整理》起始模版"  # 讀得出模版名


def test_list_templates_bad_files_reported_not_silent(tmp_path, template):
    save_template(template, tmp_path / "好模版.json")
    (tmp_path / "壞檔.json").write_text("{ 不是 JSON", encoding="utf-8")
    (tmp_path / "別種.json").write_text(
        json.dumps({"schema": "cjkfolio/document@2"}), encoding="utf-8")
    (tmp_path / "無關.txt").write_text("skip", encoding="utf-8")
    entries = list_templates(tmp_path)
    by_name = {e.path.name: e for e in entries}
    assert set(by_name) == {"好模版.json", "壞檔.json", "別種.json"}  # txt 不入清單
    assert by_name["好模版.json"].error is None
    assert by_name["壞檔.json"].error  # 壞檔列 error 不沉默
    assert by_name["別種.json"].error  # 非模版 schema 列 error
    assert [e.path.name for e in entries] == sorted(by_name)  # 檔名排序


def test_list_templates_missing_dir_empty():
    assert list_templates(ROOT / "templates" / "不存在的目錄") == ()


# ---------- merge_draft_styles（一鍵併入）----------

def test_merge_draft_adds_styles(template):
    out, report = merge_draft_styles(template, _draft())
    assert set(DRAFT_STYLES) <= set(out.paragraph_styles)
    st = out.paragraph_styles["標題候選-黑體 21.9pt"]
    assert (st.font_family, st.font_weight, st.size_pt) == ("思源黑體 TC", "bold", 21.9)
    assert st.source_font == "DFHeiStd-W7"
    assert report.added == tuple(DRAFT_STYLES)
    assert report.skipped == ()
    assert BODY in out.paragraph_styles  # 既有樣式保留
    assert template.paragraph_styles.get("標題候選-黑體 21.9pt") is None  # 原模版不可變


def test_merge_draft_skips_existing_names(template):
    draft = _draft({BODY: DRAFT_STYLES["內文候選-明體 11.5pt"],
                    **DRAFT_STYLES})
    out, report = merge_draft_styles(template, draft)
    assert BODY in [s.name for s in report.skipped]  # 同名跳過列報不沉默
    assert out.paragraph_styles[BODY] is template.paragraph_styles[BODY]  # 既有定義不覆蓋
    assert set(DRAFT_STYLES) <= set(out.paragraph_styles)


def test_merge_draft_all_skipped_is_noop(template):
    once, _ = merge_draft_styles(template, _draft())
    again, report = merge_draft_styles(once, _draft())
    assert again is once  # 全跳過 no-op 回原物件
    assert len(report.skipped) == len(DRAFT_STYLES) and report.added == ()


def test_merge_draft_missing_key_fast_fail(template):
    with pytest.raises(TemplateError):
        merge_draft_styles(template, {"pages": 2})


def test_merged_style_flows_into_layout(template):
    out, _ = merge_draft_styles(template, _draft())
    doc = make_doc([{"text": "自擬草稿樣式可直接排版。", "style": "內文候選-明體 11.5pt"}])
    layout = layout_document(doc, out)
    assert layout.pages and layout.violations == []


# ---------- session：套用模版與草稿併入入統一 undo ----------

def test_session_apply_template_undo(template):
    doc = make_doc([{"text": "留白是安放的開始。", "style": BODY}])
    session = EditSession(doc, template)
    merged, _ = merge_draft_styles(template, _draft())
    assert session.apply_template(merged) is not None
    assert "標題候選-黑體 21.9pt" in session.template.paragraph_styles
    assert session.apply_template(merged) is None  # 同物件 no-op 不入歷史
    assert session.undo() is not None
    assert "標題候選-黑體 21.9pt" not in session.template.paragraph_styles


def test_session_apply_template_missing_style_fast_fail(template):
    doc = make_doc([{"text": "留白。", "style": BODY}])
    session = EditSession(doc, template)
    merged, _ = merge_draft_styles(template, _draft())
    stripped = load_template(TEMPLATE)  # 移除文件正在用的樣式 → 重排 KeyError
    from cjkfolio.style_editing import remove_paragraph_style
    from dataclasses import replace
    no_body_md = replace(
        stripped, md_mapping={k: v for k, v in stripped.md_mapping.items()
                              if v != BODY})
    bad = remove_paragraph_style(no_body_md, BODY)
    with pytest.raises(KeyError):
        session.apply_template(bad)
    assert session.template is template  # 狀態不變
    assert not session.can_undo()
    assert merged is not None


def test_session_merge_draft_undo(template):
    doc = make_doc([{"text": "留白是安放的開始。", "style": BODY}])
    session = EditSession(doc, template)
    result, report = session.merge_draft(_draft())
    assert result is not None and report.added
    assert "內文候選-明體 11.5pt" in session.template.paragraph_styles
    again, report2 = session.merge_draft(_draft())
    assert again is None and len(report2.skipped) == 2  # 全跳過 no-op 不入歷史
    assert session.undo() is not None
    assert "內文候選-明體 11.5pt" not in session.template.paragraph_styles


# ---------- CLI merge-styles（extract → merge 一鍵併入全鏈）----------

def test_cli_merge_styles(tmp_path, capsys):
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(_draft(), ensure_ascii=False), encoding="utf-8")
    out_path = tmp_path / "merged.json"
    code = cli_main(["merge-styles", str(TEMPLATE), str(draft_path),
                     "--output", str(out_path)])
    assert code == 0
    text = capsys.readouterr().out
    assert "併入" in text
    merged = load_template(out_path)
    assert set(DRAFT_STYLES) <= set(merged.paragraph_styles)
    assert BODY in merged.paragraph_styles  # 既有樣式保留


def test_cli_merge_styles_reports_skipped(tmp_path, capsys):
    draft = _draft({BODY: DRAFT_STYLES["內文候選-明體 11.5pt"]})
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    out_path = tmp_path / "merged.json"
    code = cli_main(["merge-styles", str(TEMPLATE), str(draft_path),
                     "--output", str(out_path)])
    assert code == 0
    assert "跳過" in capsys.readouterr().out  # 同名跳過列報不沉默
    assert load_template(out_path).paragraph_styles[BODY].size_pt == 11.5  # 不覆蓋
