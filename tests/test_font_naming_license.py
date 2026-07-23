"""字型名義授權分類與匯出攔阻（Sprint 112，Phase 5 乙(10)；GAPS #43 (a)(b)）。

Sprint 84 的 fsType 只答「機器允不允許嵌入」，答不了「授權允不允許散布」。
本檔驗的是第二問：讀 name table ID 13（License Description）與 ID 14
（License Info URL），也就是字型檔自己宣告的授權，屬 A 級機器證據，
不做字型名稱黑名單比對（名稱可改、可缺、可撞名，猜測不入實作）。

三類：free（宣告命中已知自由授權）／declared（有宣告但非已知自由授權）／
undeclared（兩個欄位皆無）。內建六款皆 free，故既有零警告不變。

fixture 一律以 fontTools 改寫內建 OFL 字型的 name table 再存，不散布任何
商用字型（紅線，同 Sprint 84 fsType fixture 的處置）。
"""
import shutil
from pathlib import Path

import pytest

from cjkfolio.font_license import (
    RedistributionFinding,
    license_rows,
    license_warnings,
    redistribution_declaration,
)

fontTools = pytest.importorskip("fontTools")
from fontTools.ttLib import TTFont  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "fonts"
OPEN_TTF = FONT_DIR / "jf-openhuninn-2.1.ttf"
SERIF_OTF = FONT_DIR / "SourceHanSerifTC-Regular.otf"

# 真實商用字型 name ID 13 的形態（本機量測 kaiu.ttf／mingliu.ttc／arial.ttf 皆此句）。
# 只取宣告文字本身，不含任何商用字型檔。
MS_SUPPLIED = ("Microsoft supplied font. You may use this font to create, display, "
               "and print content as permitted by the license terms or terms of use, "
               "of the Microsoft product")

needs_fonts = pytest.mark.skipif(
    not OPEN_TTF.exists(),
    reason="assets/fonts 無可散布字型（依 FONTS.md 指令重現下載）")
needs_serif = pytest.mark.skipif(
    not SERIF_OTF.exists(),
    reason="assets/fonts 無思源宋體（依 FONTS.md 指令重現下載）")


def _font_with_license(src: Path, dst: Path, *, desc=None, url=None) -> Path:
    """改寫 name table 的授權宣告欄位（desc／url 給 None 即整項移除）。"""
    font = TTFont(str(src))
    name = font["name"]
    name.removeNames(nameID=13)
    name.removeNames(nameID=14)
    if desc is not None:
        name.setName(desc, 13, 3, 1, 0x409)
    if url is not None:
        name.setName(url, 14, 3, 1, 0x409)
    font.save(str(dst))
    return dst


# ---------- redistribution_declaration 純函式 ----------

@needs_fonts
def test_bundled_font_declares_ofl():
    f = redistribution_declaration(OPEN_TTF)
    assert isinstance(f, RedistributionFinding)
    assert f.klass == "free"
    assert f.license_name == "SIL Open Font License"
    assert "OFL" in f.url or "sil" in f.url.lower()


@needs_fonts
def test_declaration_not_recognised_is_declared(tmp_path):
    p = _font_with_license(OPEN_TTF, tmp_path / "ms.ttf", desc=MS_SUPPLIED)
    f = redistribution_declaration(p)
    assert f.klass == "declared"
    assert f.license_name == ""
    assert "Microsoft supplied font" in f.declaration
    assert "須自行確認" in f.note


@needs_fonts
def test_no_declaration_is_undeclared(tmp_path):
    p = _font_with_license(OPEN_TTF, tmp_path / "bare.ttf")
    f = redistribution_declaration(p)
    assert f.klass == "undeclared"
    assert f.declaration == "" and f.url == ""
    assert "無" in f.note


@needs_fonts
def test_url_alone_counts_as_declaration(tmp_path):
    """只有 ID 14 的字型：URL 本身就是宣告，不得判成無宣告。"""
    p = _font_with_license(OPEN_TTF, tmp_path / "urlonly.ttf",
                           url="https://scripts.sil.org/OFL")
    f = redistribution_declaration(p)
    assert f.klass == "free"
    assert f.license_name == "SIL Open Font License"


@needs_fonts
def test_vendor_is_font_self_report():
    """來源一律取字型自報欄位（manufacturer／copyright／achVendID），不猜。"""
    f = redistribution_declaration(OPEN_TTF)
    assert "justfont" in f.vendor


@needs_fonts
def test_declaration_is_truncated_not_dumped(tmp_path):
    """宣告全文可達數千字（OFL 全文），列出時須截斷，否則警告行不可讀。"""
    long_desc = "Foundry EULA. " + ("條款 " * 500)
    p = _font_with_license(OPEN_TTF, tmp_path / "long.ttf", desc=long_desc)
    f = redistribution_declaration(p)
    assert len(f.declaration) <= 200
    assert f.declaration.endswith("…")


# ---------- license_warnings 併入名義授權 ----------

@needs_fonts
def test_bundled_font_still_zero_warnings():
    """零回歸：內建字型 fsType=0 且宣告 OFL，兩層皆無警告。"""
    assert license_warnings([OPEN_TTF]) == []


@needs_fonts
def test_warning_for_undeclared_font(tmp_path):
    p = _font_with_license(OPEN_TTF, tmp_path / "bare.ttf")
    warns = license_warnings([p])
    assert len(warns) == 1
    assert warns[0].startswith("名義授權：")
    assert "bare.ttf" in warns[0]


@needs_fonts
def test_warning_for_declared_nonfree_font(tmp_path):
    p = _font_with_license(OPEN_TTF, tmp_path / "ms.ttf", desc=MS_SUPPLIED)
    warns = license_warnings([p])
    assert len(warns) == 1
    assert "Microsoft supplied font" in warns[0]


@needs_fonts
def test_both_layers_reported_independently(tmp_path):
    """fsType 與名義授權是兩件事：可嵌入但無宣告時仍須各自成立。"""
    p = _font_with_license(OPEN_TTF, tmp_path / "bare.ttf")
    font = TTFont(str(p))
    assert int(font["OS/2"].fsType) == 0      # 機器層允許嵌入
    warns = license_warnings([p])
    assert len(warns) == 1                     # 名義層仍出一條
    assert not any(w.startswith("字型授權：") for w in warns)


# ---------- license_rows 表列（供面板與 CLI） ----------

@needs_fonts
def test_license_rows_shape_and_status(tmp_path):
    bare = _font_with_license(OPEN_TTF, tmp_path / "bare.ttf")
    rows = license_rows([OPEN_TTF, bare])
    assert all(len(r) == 3 for r in rows)
    statuses = {Path(r[1]).name: r[0] for r in rows}
    assert statuses["jf-openhuninn-2.1.ttf"] == "可散布"
    assert statuses["bare.ttf"] == "無宣告"


@needs_fonts
def test_license_rows_flag_unembeddable(tmp_path):
    """fsType 不可嵌入優先顯示（那是硬阻擋，名義授權只是提示）。"""
    font = TTFont(str(OPEN_TTF))
    font["OS/2"].fsType = 0x0002
    p = tmp_path / "restricted.ttf"
    font.save(str(p))
    rows = license_rows([p])
    assert rows[0][0] == "不可嵌入"


# ---------- 匯出攔阻選項 ----------

def _minimal_doc():
    from cjkfolio.document import document_from_dict
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "授權攔阻樣張", "template": "neizai-zhengli",
                 "master": "A-內文版"},
        "paragraphs": [{"text": "整理與安放", "style": "內文-明體直排"}],
    })


@needs_serif
def test_export_warn_policy_is_default_and_writes(tmp_path):
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.styles import load_template

    out = tmp_path / "warn.pdf"
    result = export_pdf(_minimal_doc(), load_template(ROOT / "templates" / "neizai-zhengli.json"),
                        out, footer=False)
    assert out.exists()
    assert list(result.license_warnings) == []   # 內建字型兩層皆過


@needs_serif
def test_export_block_policy_refuses_and_writes_nothing(tmp_path):
    """block：有任何授權警告即不產出檔案（不是產出後再警告）。"""
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.styles import load_template

    font_dir = tmp_path / "fonts"
    font_dir.mkdir()
    _font_with_license(SERIF_OTF, font_dir / SERIF_OTF.name)   # 授權宣告整項移除
    out = tmp_path / "blocked.pdf"
    with pytest.raises(ValueError) as exc:
        export_pdf(_minimal_doc(),
                   load_template(ROOT / "templates" / "neizai-zhengli.json"),
                   out, footer=False, font_dir=font_dir, license_policy="block")
    assert "名義授權" in str(exc.value)
    assert SERIF_OTF.name in str(exc.value)
    assert not out.exists()


@needs_serif
def test_export_block_policy_passes_with_bundled_fonts(tmp_path):
    """block 不是把所有匯出都擋掉：內建字型組應原樣通過（開源散布情境）。"""
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.styles import load_template

    out = tmp_path / "ok.pdf"
    result = export_pdf(_minimal_doc(),
                        load_template(ROOT / "templates" / "neizai-zhengli.json"),
                        out, footer=False, license_policy="block")
    assert out.exists() and result.page_count == 1


@needs_serif
def test_unknown_license_policy_rejected(tmp_path):
    """未知政策值一律拒絕，且不得留下半成品檔案。"""
    from cjkfolio.pdf_writer import export_pdf
    from cjkfolio.styles import load_template

    out = tmp_path / "x.pdf"
    with pytest.raises(ValueError) as exc:
        export_pdf(_minimal_doc(),
                   load_template(ROOT / "templates" / "neizai-zhengli.json"),
                   out, footer=False, license_policy="strict")
    assert "license_policy" in str(exc.value)
    assert not out.exists()


# ---------- CLI ----------

def _write_doc_json(tmp_path: Path) -> Path:
    import json

    from cjkfolio.document import document_to_dict

    src = tmp_path / "doc.json"
    src.write_text(json.dumps(document_to_dict(_minimal_doc()), ensure_ascii=False),
                   encoding="utf-8")
    return src


@needs_serif
def test_cli_reports_both_license_layers(tmp_path, capsys):
    from cjkfolio.cli import main

    src = _write_doc_json(tmp_path)
    rc = main(["export-pdf", str(src), "-o", str(tmp_path / "cli.pdf"), "--no-footer"])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "name 表 ID 13／14" in printed


@needs_serif
def test_cli_block_policy_exits_two(tmp_path, capsys, monkeypatch):
    """CLI 無 --font-dir 選項，故以攔阻點替身驗 CLI 層：退出碼 2、訊息進 stderr、不留檔。

    攔阻點本身（寫檔前中止）由 test_export_block_policy_refuses_and_writes_nothing
    以真實字型驗過，此處只驗 CLI 的錯誤處置。
    """
    import cjkfolio.pdf_writer as pw
    from cjkfolio.cli import main
    from cjkfolio.font_license import LicenseBlocked

    def _blocked(policy, font_paths):
        raise LicenseBlocked("license_policy=block：名義授權：某字型.otf 未宣告授權")

    monkeypatch.setattr(pw, "enforce_license_policy", _blocked)
    src = _write_doc_json(tmp_path)
    out = tmp_path / "blocked.pdf"
    rc = main(["export-pdf", str(src), "-o", str(out), "--no-footer",
               "--license-policy", "block"])
    assert rc == 2
    assert "名義授權" in capsys.readouterr().err
    assert not out.exists()


# ---------- 量測工具 ----------

def test_tool_contains_no_system_font_path():
    """工具原始碼不得內含任何本機或系統字型路徑（素材一律由呼叫端顯式指定）。

    同 measure_long_book 的素材外置紀律：系統字型多為商用授權，工具內建路徑等於
    把某台機器的環境寫進版本控制，別人跑不出同一份結果。
    """
    src = (ROOT / "tools" / "measure_font_license.py").read_text(encoding="utf-8")
    assert "C:\\Windows" not in src and "C:/Windows" not in src
    assert "C:\\Users" not in src and "C:/Users" not in src
    assert "kaiu.ttf" not in src and "mingliu" not in src


@needs_fonts
def test_tool_measures_bundled_fonts(tmp_path, capsys):
    from tools.measure_font_license import main

    out_json = tmp_path / "授權.json"
    rc = main(["--json", str(out_json)])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "款可散布" in printed
    data = __import__("json").loads(out_json.read_text(encoding="utf-8"))
    assert len(data) >= 1
    assert all(r["名義分類"] == "free" for r in data)


def test_tool_reports_missing_font_without_crashing(tmp_path, capsys):
    from tools.measure_font_license import main

    rc = main(["--fonts", str(tmp_path / "不存在.ttf")])
    assert rc == 0
    assert "缺檔" in capsys.readouterr().out


# ---------- 內建字型組全數複驗（開源散布的前提） ----------

@needs_fonts
def test_all_bundled_fonts_are_free():
    """六款內建字型逐款須為 free，否則本專案自身的散布主張就不成立。"""
    fonts = sorted(list(FONT_DIR.glob("*.otf")) + list(FONT_DIR.glob("*.ttf")))
    assert len(fonts) >= 1
    for path in fonts:
        f = redistribution_declaration(path)
        assert f.klass == "free", f"{path.name} 非自由授權宣告：{f.note}"
    assert license_warnings(fonts) == []


@needs_fonts
def test_copy_of_bundled_font_keeps_class(tmp_path):
    """檔名不參與判定：改名不改分類（證明沒有隱藏的名稱比對）。"""
    dst = tmp_path / "看起來像商用字型.ttf"
    shutil.copy(OPEN_TTF, dst)
    assert redistribution_declaration(dst).klass == "free"
