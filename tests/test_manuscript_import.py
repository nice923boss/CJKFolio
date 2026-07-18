"""稿件匯入判定層（editor.import_core）與 EditSession.replace_document（Sprint 107）。

編輯器「檔案 → 匯入稿件」的兩層地基，皆 Qt 無關故入 pytest 基線：

- import_manuscript：依副檔名分派 txt／md／docx，**三個預設值（template_id、
  master、內文樣式）全部由當前模版推導**。硬編碼是本層存在的理由：Sprint 105 已
  把 master 搬進 template.default_master，但 txt 的內文樣式仍寫死「內文-明體直排」，
  對《街角慢行》模版即為不存在的樣式 → 匯入端 exit 0 產出壞文件，錯誤延到渲染才爆。
  test_txt_second_book_uses_template_body_style 與 test_imported_doc_lays_out_*
  即為此缺陷的回歸守門。
- replace_document：匯入＝整份換文件。游標必須歸零（新文件段數可能少於舊文件，
  沿用舊游標會越界），且須與既有編輯共用同一 undo 歷史（誤匯入可一步 Ctrl+Z 回）。
"""
import zipfile
from pathlib import Path

import pytest

from cjkfolio.document import Document, Paragraph
from cjkfolio.editing import DocCursor
from cjkfolio.layout import layout_document
from cjkfolio.session import EditSession
from cjkfolio.styles import load_template
from editor.import_core import SUPPORTED_SUFFIXES, import_manuscript

ROOT = Path(__file__).resolve().parents[1]
NEIZAI = ROOT / "templates" / "neizai-zhengli.json"
JIEJIAO = ROOT / "templates" / "jiejiao-manxing.json"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@pytest.fixture(scope="module")
def neizai():
    return load_template(NEIZAI)


@pytest.fixture(scope="module")
def jiejiao():
    return load_template(JIEJIAO)


@pytest.fixture
def txt_file(tmp_path):
    path = tmp_path / "稿件.txt"
    path.write_text("第一段文字。\n\n第二段文字。\n\n第三段文字。", encoding="utf-8")
    return path


@pytest.fixture
def md_file(tmp_path):
    path = tmp_path / "稿件.md"
    path.write_text(
        "# 第一章\n\n## 小節一\n\n內文一段。\n\n> 引用一句。\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def docx_file(tmp_path):
    """手工 OOXML（不依賴 python-docx 是否安裝；outlineLvl 直掛＝結構層級真值）。"""
    path = tmp_path / "稿件.docx"

    def para(text, lvl):
        ppr = f'<w:pPr><w:outlineLvl w:val="{lvl}"/></w:pPr>'
        return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"

    body = para("第一章", 0) + para("小節一", 1) + para("內文一段。", 9)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return path


# ---------- 預設值一律由模版推導（本層存在的理由） ----------

def test_txt_second_book_uses_template_body_style(txt_file, jiejiao):
    """《街角慢行》模版無「內文-明體直排」；取錯即回歸 Sprint 107 修掉的缺陷。"""
    doc = import_manuscript(txt_file, jiejiao, "jiejiao-manxing")
    assert {p.style for p in doc.paragraphs} == {"內文-宋體直排"}


def test_txt_default_book_uses_its_own_body_style(txt_file, neizai):
    doc = import_manuscript(txt_file, neizai, "neizai-zhengli")
    assert {p.style for p in doc.paragraphs} == {"內文-明體直排"}


def test_master_and_template_id_come_from_template(txt_file, jiejiao):
    doc = import_manuscript(txt_file, jiejiao, "jiejiao-manxing")
    assert doc.master == "甲-內文"      # template.default_master，非寫死 A-內文版
    assert doc.template == "jiejiao-manxing"


def test_title_defaults_to_filename_stem(txt_file, jiejiao):
    assert import_manuscript(txt_file, jiejiao, "jiejiao-manxing").title == "稿件"


def test_explicit_title_overrides_stem(txt_file, jiejiao):
    doc = import_manuscript(txt_file, jiejiao, "jiejiao-manxing", title="街角慢行")
    assert doc.title == "街角慢行"


# ---------- 三種格式各自的結構對映 ----------

def test_txt_paragraph_count(txt_file, jiejiao):
    assert len(import_manuscript(txt_file, jiejiao, "jiejiao-manxing").paragraphs) == 3


def test_md_maps_heading_levels_by_template(md_file, jiejiao):
    styles = [p.style for p in
              import_manuscript(md_file, jiejiao, "jiejiao-manxing").paragraphs]
    assert styles == ["章名-宋體特粗", "小節標-黑體", "內文-宋體直排", "引語-宋體縮排"]


def test_docx_maps_outline_levels_by_template(docx_file, jiejiao):
    styles = [p.style for p in
              import_manuscript(docx_file, jiejiao, "jiejiao-manxing").paragraphs]
    assert styles == ["章名-宋體特粗", "小節標-黑體", "內文-宋體直排"]


@pytest.mark.parametrize("name", ["稿件.TXT", "稿件.Md", "稿件.DOCX"])
def test_suffix_match_is_case_insensitive(tmp_path, jiejiao, name, docx_file):
    path = tmp_path / name
    if path.suffix.lower() == ".docx":
        path.write_bytes(docx_file.read_bytes())
    else:
        path.write_text("一段文字。", encoding="utf-8")
    assert import_manuscript(path, jiejiao, "jiejiao-manxing").paragraphs


# ---------- 匯入產物必須可直接排版（缺陷的真正守門） ----------

@pytest.mark.parametrize("fixture_name", ["txt_file", "md_file", "docx_file"])
def test_imported_doc_lays_out_without_missing_style(request, fixture_name, jiejiao):
    """匯入端不得沉默產出「渲染才爆」的文件：三格式皆須直接排得出來。"""
    path = request.getfixturevalue(fixture_name)
    doc = import_manuscript(path, jiejiao, "jiejiao-manxing")
    assert layout_document(doc, jiejiao).pages  # 樣式缺失會在此 KeyError


# ---------- 錯誤路徑明確，不沉默 ----------

def test_unknown_suffix_names_the_suffix_and_supported_list(tmp_path, jiejiao):
    path = tmp_path / "稿件.pdf"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError) as err:
        import_manuscript(path, jiejiao, "jiejiao-manxing")
    assert ".pdf" in str(err.value)
    assert ".docx" in str(err.value)


def test_missing_file_raises(tmp_path, jiejiao):
    with pytest.raises((OSError, ValueError)):
        import_manuscript(tmp_path / "不存在.txt", jiejiao, "jiejiao-manxing")


def test_template_without_default_master_is_explicit(txt_file, jiejiao):
    import dataclasses
    bare = dataclasses.replace(jiejiao, default_master="")
    with pytest.raises(ValueError) as err:
        import_manuscript(txt_file, bare, "jiejiao-manxing")
    assert "default_master" in str(err.value)


def test_supported_suffixes_are_the_three_advertised():
    assert set(SUPPORTED_SUFFIXES) == {".txt", ".md", ".markdown", ".docx"}


# ---------- CLI 的同一處硬編碼（Gate 3 同類掃描）----------

def test_cli_import_txt_without_style_uses_template_body_style(txt_file, tmp_path):
    """`import-txt --template 街角慢行` 不給 --style 時，須取該模版的內文樣式。

    修前：預設寫死「內文-明體直排」→ 匯入 exit 0，render 才爆樣式不存在。
    """
    from cjkfolio.cli import main
    from cjkfolio.document import load_document

    out = tmp_path / "cli.doc.json"
    assert main(["import-txt", str(txt_file), "-o", str(out),
                 "--template", str(JIEJIAO)]) == 0
    doc = load_document(out)
    assert {p.style for p in doc.paragraphs} == {"內文-宋體直排"}
    assert layout_document(doc, load_template(JIEJIAO)).pages


def test_cli_import_txt_explicit_style_still_wins(txt_file, tmp_path):
    from cjkfolio.cli import main
    from cjkfolio.document import load_document

    out = tmp_path / "cli2.doc.json"
    assert main(["import-txt", str(txt_file), "-o", str(out),
                 "--template", str(JIEJIAO), "--style", "引語-宋體縮排"]) == 0
    assert {p.style for p in load_document(out).paragraphs} == {"引語-宋體縮排"}


# ---------- EditSession.replace_document ----------

def _session(template):
    doc = Document(
        title="原稿", template="jiejiao-manxing", master="甲-內文",
        paragraphs=(Paragraph("原有第一段。", "內文-宋體直排"),
                    Paragraph("原有第二段。", "內文-宋體直排"),
                    Paragraph("原有第三段。", "內文-宋體直排")),
    )
    return EditSession(doc, template)


def test_replace_document_switches_document_and_relayouts(txt_file, jiejiao):
    session = _session(jiejiao)
    incoming = import_manuscript(txt_file, jiejiao, "jiejiao-manxing")
    result = session.replace_document(incoming)
    assert session.document is incoming
    assert result.layout is session.layout
    assert session.layout.pages


def test_replace_document_resets_cursor_to_start(jiejiao):
    """新文件段數可能少於舊文件：沿用舊游標會越界，故必須歸零。"""
    session = _session(jiejiao)
    session.insert(DocCursor(2, 0), "打字")          # 游標移到第 3 段
    shorter = Document(
        title="短稿", template="jiejiao-manxing", master="甲-內文",
        paragraphs=(Paragraph("只有一段。", "內文-宋體直排"),),
    )
    session.replace_document(shorter)
    assert session.cursor == DocCursor(0, 0)


def test_replace_document_is_one_undo_step(txt_file, jiejiao):
    session = _session(jiejiao)
    original = session.document
    session.replace_document(import_manuscript(txt_file, jiejiao, "jiejiao-manxing"))
    session.undo()
    assert session.document is original
    assert session.cursor == DocCursor(0, 0)


def test_replace_document_with_missing_style_fails_without_changing_state(jiejiao):
    """引用他本書樣式的文件不得入歷史：狀態原封不動。"""
    session = _session(jiejiao)
    original, undo_depth = session.document, session.can_undo()
    bad = Document(
        title="壞稿", template="jiejiao-manxing", master="甲-內文",
        paragraphs=(Paragraph("引用別本書的樣式。", "內文-明體直排"),),
    )
    with pytest.raises(KeyError):
        session.replace_document(bad)
    assert session.document is original
    assert session.can_undo() == undo_depth


def test_replace_document_same_object_is_noop(jiejiao):
    session = _session(jiejiao)
    assert session.replace_document(session.document) is None
    assert not session.can_undo()
