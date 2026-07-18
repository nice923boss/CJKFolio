"""preflight 背景執行緒的判定層與快取鍵（editor.preflight_core，Sprint 100）。

本檔驗的是 Qt 無關的兩件事，故不需 PySide6：

- run_preflight_checks：匯出臨時 PDF → 三項機械檢查，回三份報告
  （原 EditorWindow._run_preflight 的判定層，抽出後才能離開 GUI 執行緒跑）。
- preflight_cache_key：文件／模版／置入圖檔任一改動即換鍵，否則同鍵
  （快取的正確性全繫於此，故逐項釘死；漏一項就會拿舊報告當新結論）。

素材一律自擬（版權紅線）。
"""
from pathlib import Path

import pytest

from cjkfolio.document import document_from_dict
from cjkfolio.styles import load_template, template_from_dict, template_to_dict

fitz = pytest.importorskip("fitz")

from editor.preflight_core import (  # noqa: E402（需在 importorskip 之後）
    preflight_cache_key,
    run_preflight_checks,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"
FONT_DIR = ROOT / "assets" / "fonts"

needs_fonts = pytest.mark.skipif(
    not (FONT_DIR / "SourceHanSerifTC-Regular.otf").exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）",
)


def sample_doc(text: str = "快取鍵測試段落，內容任意。", images=()) -> object:
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "快取測試", "template": "neizai-zhengli",
                 "master": "A-內文版", "language": "zh-TW"},
        "paragraphs": [{"text": text, "style": "內文-明體直排"}],
        "images": list(images),
    })


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def test_cache_key_is_deterministic(template):
    """同文件同模版同基準目錄 → 同鍵（否則快取永不命中，等於沒做）。"""
    doc = sample_doc()
    key = preflight_cache_key(doc, template, ROOT / "samples")
    assert key == preflight_cache_key(sample_doc(), template, ROOT / "samples")
    assert len(key) == 64 and key == key.lower()  # sha256 十六進位


def test_cache_key_changes_with_document_text(template):
    """文件改一字即換鍵（stale 報告是本功能唯一的正確性風險）。"""
    a = preflight_cache_key(sample_doc("原文"), template, ROOT / "samples")
    b = preflight_cache_key(sample_doc("原文改"), template, ROOT / "samples")
    assert a != b


def test_cache_key_changes_with_template(template):
    """模版改字級即換鍵（版面幾何變了，舊報告不再代表當前輸出）。"""
    raw = template_to_dict(template)
    raw["paragraph_styles"]["內文-明體直排"]["size_pt"] = 99.0
    changed = template_from_dict(raw)
    doc = sample_doc()
    assert preflight_cache_key(doc, template, ROOT / "samples") != \
        preflight_cache_key(doc, changed, ROOT / "samples")


def test_cache_key_changes_with_image_base_dir(template):
    """基準目錄換了即換鍵（相對路徑解到別張圖）。"""
    doc = sample_doc()
    assert preflight_cache_key(doc, template, ROOT / "samples") != \
        preflight_cache_key(doc, template, ROOT / "templates")


def test_cache_key_tracks_image_file_bytes(tmp_path, template):
    """置入圖檔內容改變即換鍵（文件本身沒變，但輸出的影像變了）。"""
    from PIL import Image

    img = tmp_path / "photo.png"
    Image.new("L", (400, 300), 128).save(img)
    doc = sample_doc(images=[{"path": "photo.png", "page": 1,
                             "rect": [50, 50, 200, 170]}])
    before = preflight_cache_key(doc, template, tmp_path)
    Image.new("L", (800, 600), 64).save(img)  # 換一張像素不同的圖
    assert before != preflight_cache_key(doc, template, tmp_path)


def test_cache_key_handles_missing_image(tmp_path, template):
    """圖檔不存在時仍算得出鍵（缺檔的誠實失敗留給匯出階段，不在算鍵時炸掉）。"""
    doc = sample_doc(images=[{"path": "nowhere.png", "page": 1,
                              "rect": [50, 50, 200, 170]}])
    key = preflight_cache_key(doc, template, tmp_path)
    assert len(key) == 64


@needs_fonts
def test_run_preflight_checks_returns_three_reports(template):
    """判定層回三份報告，且與 CLI 走同一組檢查器（X-1a 12 規則全過）。"""
    results = run_preflight_checks(sample_doc(), template, ROOT / "samples")
    assert results.report.ok and len(results.report.findings) == 12
    assert results.image_report.findings == ()  # 本樣張無置入影像
    assert results.ink_report.ok and len(results.ink_report.findings) > 0


# ---------- X-4 preflight 與 ICC（Sprint 101，關 GAPS #47 (a)） ----------

def fake_icc(space: bytes = b"CMYK", klass: bytes = b"prtr") -> bytes:
    """最小可驗 ICC（與 test_preflight.fake_icc 同構，避免跨測試檔匯入）。"""
    head = bytearray(132)
    head[0:4] = (132).to_bytes(4, "big")
    head[12:16] = klass
    head[16:20] = space
    return bytes(head)


def test_cache_key_separates_profiles(template):
    """X-1a 與 X-4 的鍵必須相異（否則切形態時會拿另一份報告當結論）。"""
    doc = sample_doc()
    base = ROOT / "samples"
    assert preflight_cache_key(doc, template, base, pdfx="x-1a") != \
        preflight_cache_key(doc, template, base, pdfx="x-4")


def test_cache_key_tracks_icc_file(tmp_path, template):
    """換 ICC 檔或改 ICC 內容即換鍵（輸出的 OutputIntent 變了）。"""
    doc = sample_doc()
    icc_a = tmp_path / "a.icc"
    icc_a.write_bytes(fake_icc())
    icc_b = tmp_path / "b.icc"
    icc_b.write_bytes(fake_icc())
    key_a = preflight_cache_key(doc, template, tmp_path, pdfx="x-4", icc_profile=icc_a)
    key_b = preflight_cache_key(doc, template, tmp_path, pdfx="x-4", icc_profile=icc_b)
    assert key_a != key_b, "不同 ICC 檔應換鍵"
    icc_a.write_bytes(fake_icc(klass=b"scnr"))  # 同路徑、內容不同
    assert key_a != preflight_cache_key(doc, template, tmp_path, pdfx="x-4",
                                        icc_profile=icc_a), "ICC 內容改變應換鍵"


@needs_fonts
def test_run_preflight_checks_x4_with_icc(tmp_path, template):
    """X-4 形態：嵌 ICC 後過 X-4 規則集，且不列 no-transparency（X-4 允許透明）。"""
    icc = tmp_path / "out.icc"
    icc.write_bytes(fake_icc())
    results = run_preflight_checks(sample_doc(), template, ROOT / "samples",
                                   pdfx="x-4", icc_profile=icc)
    assert results.report.ok, [f for f in results.report.findings if not f.ok]
    rules = {f.rule for f in results.report.findings}
    assert "no-transparency" not in rules
    assert len(results.report.findings) == 11


@needs_fonts
def test_run_preflight_checks_x4_without_icc_fails_loudly(template):
    """X-4 未給 ICC 時快速失敗（不得沉默降級成 X-1a 再宣稱通過）。"""
    with pytest.raises(ValueError, match="X-4"):
        run_preflight_checks(sample_doc(), template, ROOT / "samples", pdfx="x-4")
