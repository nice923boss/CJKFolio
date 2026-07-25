"""ICC 色彩轉換（Sprint 139）：有描述檔才轉，灰階不轉，轉出照過墨量檢查。

Sprint 76 與 Sprint 137 兩度決議「不做 RGB→CMYK」，反對的是沒有色彩管理的 naive
換算。Spike 25 量測後定案的形態是三條缺一不可，本檔逐條驗：

1. 描述檔由使用者提供，無描述檔快速失敗（不退回 naive 換算，不沉默略過）
2. 灰階與 CMYK 來源原樣返回（§9 灰階照片走單 K；四色灰是退步不是進步）
3. 轉出的是 CMYK，既有 image_max_tac／tac_warnings 自然接手

真轉換須要真描述檔。本產品不內建描述檔（§10 Sprint 10 的授權轉嫁理由），Owner 手上
那份 Japan Color 2011 Coated 屬第三方散布物同樣不入 repo，故此處借作業系統夾帶的
RSWOP.icm；該檔不在時據實 skip，不用假描述檔假裝驗過（假 ICC 只有 header，
littleCMS 打不開，那條路另有測試守）。

驗證一律走 PyMuPDF／PIL 之外的獨立路徑（Gate 4）。測試素材一律自擬（版權紅線）。
"""
from io import BytesIO
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageCms

from cjkfolio.color_convert import (ColorConvertError, DEFAULT_INTENT,
                                    convert_placed_images, convert_to_cmyk,
                                    profile_label, resolve_intent)
from cjkfolio.document import Document, Paragraph, PlacedImage
from cjkfolio.ink import image_max_tac
from cjkfolio.pdf_writer import export_pdf
from cjkfolio.styles import load_template

ROOT = Path(__file__).resolve().parents[1]
G_MASTER = "G-圖文版"
ORANGE = (230, 120, 40)   # 三分量互異：轉換後四分量才有可觀察的差別

#: 作業系統夾帶的 CMYK 輸出描述檔（Spike 25 實測用的同一份）。
OS_CMYK_PROFILE = Path(r"C:\Windows\System32\spool\drivers\color\RSWOP.icm")
needs_real_icc = pytest.mark.skipif(
    not OS_CMYK_PROFILE.exists(),
    reason="本機無作業系統夾帶的 CMYK 輸出描述檔（Windows 以外環境）")


@pytest.fixture(scope="module")
def template():
    return load_template(ROOT / "templates" / "neizai-zhengli.json")


def fake_icc(space: bytes = b"CMYK", klass: bytes = b"prtr") -> bytes:
    """最小可驗 ICC：128 byte header＋tag 數 0。過得了 header 守門，轉不了色彩。"""
    head = bytearray(132)
    head[0:4] = (132).to_bytes(4, "big")
    head[12:16] = klass
    head[16:20] = space
    return bytes(head)


@pytest.fixture(scope="module")
def real_icc() -> bytes:
    return OS_CMYK_PROFILE.read_bytes()


def _rgb(size=(8, 6), color=ORANGE, profile=None):
    img = Image.new("RGB", size, color)
    if profile is not None:
        img.info["icc_profile"] = profile
    return img


def _figure_doc(name):
    return Document(title="樣張", template="x", master=G_MASTER,
                    paragraphs=(Paragraph(text="圖說", style="圖說-辰宇落雁"),),
                    images=(PlacedImage(path=name, page=1),))


def _first_image(pdf_path):
    """獨立解析（PyMuPDF）取第 1 頁首張影像的鍵值與解壓後原始樣本。"""
    doc = fitz.open(pdf_path)
    xref = doc[0].get_images(full=True)[0][0]
    keys = {k: doc.xref_get_key(xref, k)[1] for k in ("ColorSpace", "Decode")}
    raw = doc.xref_stream(xref)
    doc.close()
    return keys, raw


# ---------- rendering intent：開放兩個，其餘附理由拒收 ----------

def test_resolve_intent_maps_names():
    assert resolve_intent("perceptual") == 0
    assert resolve_intent("relative") == 1
    assert resolve_intent(DEFAULT_INTENT) == 1   # 預設＝relative colorimetric


def test_resolve_intent_rejects_saturation_with_measured_reason():
    """不開放的 intent 要說出為什麼，且理由是量到的不是猜的（Spike 25）。"""
    with pytest.raises(ColorConvertError) as e:
        resolve_intent("saturation")
    assert "純黑" in str(e.value) and "185%" in str(e.value)


def test_resolve_intent_rejects_absolute_with_reason():
    with pytest.raises(ColorConvertError) as e:
        resolve_intent("absolute")
    assert "打樣" in str(e.value)


def test_resolve_intent_rejects_unknown_and_lists_options():
    with pytest.raises(ColorConvertError) as e:
        resolve_intent("vivid")
    assert "perceptual" in str(e.value) and "relative" in str(e.value)


# ---------- 條件 1：無描述檔不轉，不合格描述檔不轉 ----------

def test_missing_profile_fails_fast_without_naive_fallback():
    """無描述檔時不退回逐通道公式：這正是 Sprint 76 禁掉的那條路。"""
    with pytest.raises(ColorConvertError) as e:
        convert_to_cmyk(_rgb(), b"")
    msg = str(e.value)
    assert "描述檔" in msg and "無色彩管理" in msg


def test_rgb_profile_rejected_as_target():
    """目標須是 CMYK 輸出描述檔，判定與 DestOutputProfile 同一條守門。"""
    with pytest.raises(ValueError) as e:
        convert_to_cmyk(_rgb(), fake_icc(space=b"RGB "))
    assert "CMYK" in str(e.value)


def test_display_class_profile_rejected_as_target():
    with pytest.raises(ValueError) as e:
        convert_to_cmyk(_rgb(), fake_icc(klass=b"mntr"))
    assert "prtr" in str(e.value)


def test_header_only_profile_cannot_convert():
    """header 合格不代表色彩轉換表在：littleCMS 打不開就據實失敗，不硬轉。"""
    with pytest.raises(ColorConvertError) as e:
        convert_to_cmyk(_rgb(), fake_icc(), source="broken.icc")
    assert "broken.icc" in str(e.value) and "無法用於色彩轉換" in str(e.value)


# ---------- 條件 2：灰階與 CMYK 原樣返回 ----------

def test_gray_source_passes_through_untouched():
    """§9 灰階照片走單 K：轉了會變近乎無 K 的四色灰，故原物件返回。"""
    img = Image.new("L", (8, 6), 90)
    out, src_label = convert_to_cmyk(img, fake_icc())
    assert out is img and src_label == ""


def test_cmyk_source_passes_through_untouched():
    """來源已在印刷色彩空間，再轉一次是 device → device 二次換算。"""
    img = Image.new("CMYK", (8, 6), (0, 0, 0, 230))
    out, src_label = convert_to_cmyk(img, fake_icc())
    assert out is img and src_label == ""


def test_other_modes_rejected():
    with pytest.raises(ColorConvertError) as e:
        convert_to_cmyk(Image.new("RGBA", (8, 6)), fake_icc())
    assert "RGBA" in str(e.value)


# ---------- 真描述檔：換算本身 ----------

@needs_real_icc
def test_converts_rgb_to_cmyk_keeping_size(real_icc):
    out, src_label = convert_to_cmyk(_rgb(size=(12, 5)), real_icc)
    assert out.mode == "CMYK" and out.size == (12, 5)
    assert src_label == "sRGB（來源未標記描述檔）"


@needs_real_icc
def test_embedded_source_profile_is_used_and_reported(real_icc):
    """來源自帶 RGB 描述檔時據以轉換，並在說明中如實標示來源。"""
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    _, src_label = convert_to_cmyk(_rgb(profile=srgb), real_icc)
    assert src_label == "來源內嵌描述檔"


@needs_real_icc
def test_non_rgb_embedded_profile_falls_back_to_srgb(real_icc):
    """內嵌描述檔與像素模式矛盾（CMYK 標記配 RGB 像素）時不採用，改記假設。"""
    _, src_label = convert_to_cmyk(_rgb(profile=real_icc), real_icc)
    assert src_label == "sRGB（來源未標記描述檔）"


@needs_real_icc
def test_white_stays_blank_and_black_gets_heavy_k(real_icc):
    """方向性：紙白不上墨，純黑上重 K。轉換確實發生而非原樣搬運。

    黑的分量由描述檔的 GCR 決定，本產品不介入：RSWOP 把純黑轉成單 K100，
    Japan Color 2011 Coated 轉成 (238, 233, 218, 204) 的四色黑（TAC 350%，
    高於 §9 門檻，由 tac_warnings 據實響）。兩者共通的是 K 重，故只驗 K。
    """
    white, _ = convert_to_cmyk(_rgb(size=(2, 2), color=(255, 255, 255)), real_icc)
    black, _ = convert_to_cmyk(_rgb(size=(2, 2), color=(0, 0, 0)), real_icc)
    assert image_max_tac(white) < 5.0
    assert black.getpixel((0, 0))[3] > 200


@needs_real_icc
def test_intent_choice_changes_out_of_gamut_pixels(real_icc):
    """intent 是使用者可見選項而非裝飾：色域外的顏色兩個選項給出不同分量。

    差異只在色域外像素的處置：實測 RSWOP 下橙、綠、紅兩 intent 完全同值，
    純藍才分岔（(253, 168, 0, 43) 對 (253, 172, 0, 54)）。這正是 Spike 25
    「本機無打樣無從判優，故列為使用者選項」的依據，不是可有可無的參數。
    """
    blue = dict(size=(2, 2), color=(0, 0, 255))
    per, _ = convert_to_cmyk(_rgb(**blue), real_icc, intent="perceptual")
    rel, _ = convert_to_cmyk(_rgb(**blue), real_icc, intent="relative")
    assert per.getpixel((0, 0)) != rel.getpixel((0, 0))


@needs_real_icc
def test_profile_label_prefers_self_reported_description(real_icc):
    assert profile_label(real_icc, OS_CMYK_PROFILE) == ImageCms.getProfileDescription(
        ImageCms.getOpenProfile(BytesIO(real_icc))).strip()


def test_profile_label_falls_back_to_filename():
    assert profile_label(fake_icc(), Path("x/press.icc")) == "press.icc"


# ---------- 置入圖整批轉換：去重、保形、逐張說明 ----------

@needs_real_icc
def test_convert_placed_images_dedups_by_path(real_icc):
    """同路徑跨頁只轉一次（與 XObject 去重同一把鑰匙），說明也只有一則。"""
    img, rect = _rgb(), ("rect", 1)
    out, notes = convert_placed_images(
        {1: (("a/c.png", img, rect),), 2: (("a/c.png", img, rect),)},
        real_icc, source=OS_CMYK_PROFILE)
    assert out[1][0][1] is out[2][0][1]      # 同一個轉出物件
    assert out[1][0][0] == "a/c.png" and out[1][0][2] == rect   # 路徑與版位不動
    assert len(notes) == 1


@needs_real_icc
def test_convert_placed_images_note_states_profile_intent_and_no_warranty(real_icc):
    _, notes = convert_placed_images({1: (("a/c.png", _rgb(), None),)},
                                     real_icc, intent="perceptual",
                                     source=OS_CMYK_PROFILE)
    note = notes[0]
    assert "c.png" in note and "perceptual" in note
    assert profile_label(real_icc, OS_CMYK_PROFILE) in note
    assert "不擔保" in note                   # 顏色正確性不宣稱（Spike 25 §3）


@needs_real_icc
def test_convert_placed_images_leaves_gray_alone(real_icc):
    gray = Image.new("L", (8, 6), 90)
    out, notes = convert_placed_images({1: (("g.png", gray, None),)}, real_icc)
    assert out[1][0][1] is gray and notes == []


# ---------- 端到端：寫進 PDF 的是 CMYK，且墨量被量到 ----------

@needs_real_icc
def test_export_embeds_devicecmyk(tmp_path, template):
    """PDF/X 送印形態＋開啟轉換：置入的彩圖以 /DeviceCMYK 嵌入，不再轉灰。"""
    Image.new("RGB", (40, 30), ORANGE).save(tmp_path / "c.png")
    out = tmp_path / "o.pdf"
    result = export_pdf(_figure_doc("c.png"), template, out, footer=False,
                        image_base_dir=tmp_path, icc_profile=OS_CMYK_PROFILE,
                        color_convert=True)
    keys, raw = _first_image(out)
    assert keys["ColorSpace"] == "/DeviceCMYK"
    assert keys["Decode"] == "null"          # 無反相陣列（PDF/X 影像慣例）
    assert len(raw) == 40 * 30 * 4           # 四分量原樣，未被降階
    assert dict(result.image_colorspaces) == {"/DeviceCMYK": 1}
    assert len(result.image_color_warnings) == 1
    assert "轉為 CMYK 嵌入" in result.image_color_warnings[0]


@needs_real_icc
def test_export_measures_ink_of_converted_image(tmp_path, template):
    """條件 3：轉出的 CMYK 進既有墨量帳，PIL 之外複量與產品自報一致（Gate 4）。"""
    Image.new("RGB", (40, 30), (0, 0, 0)).save(tmp_path / "k.png")
    out = tmp_path / "o.pdf"
    result = export_pdf(_figure_doc("k.png"), template, out, footer=False,
                        image_base_dir=tmp_path, icc_profile=OS_CMYK_PROFILE,
                        color_convert=True)
    _, raw = _first_image(out)
    recomputed = max(sum(raw[i:i + 4]) for i in range(0, len(raw), 4)) / 2.55
    inks = [u for u in result.ink_uses if "k.png" in u.label]
    assert len(inks) == 1
    assert inks[0].tac == pytest.approx(recomputed, abs=0.6)


@needs_real_icc
def test_export_gray_image_stays_single_k(tmp_path, template):
    """灰階回歸：開了轉換也不動灰階來源，仍以 /DeviceGray 單 K 嵌入。"""
    Image.new("L", (40, 30), 90).save(tmp_path / "g.png")
    out = tmp_path / "o.pdf"
    result = export_pdf(_figure_doc("g.png"), template, out, footer=False,
                        image_base_dir=tmp_path, icc_profile=OS_CMYK_PROFILE,
                        color_convert=True)
    assert _first_image(out)[0]["ColorSpace"] == "/DeviceGray"
    assert result.image_color_warnings == ()


def test_export_color_convert_requires_icc(tmp_path, template):
    """勾了轉換卻沒給描述檔＝無目標可轉，快速失敗不降級為轉灰。"""
    Image.new("RGB", (40, 30), ORANGE).save(tmp_path / "c.png")
    with pytest.raises(ValueError) as e:
        export_pdf(_figure_doc("c.png"), template, tmp_path / "o.pdf",
                   footer=False, image_base_dir=tmp_path, color_convert=True)
    assert "描述檔" in str(e.value)


def test_export_color_convert_rejected_for_plain_pdf(tmp_path, template):
    """一般 PDF 不收描述檔（無處可嵌），故也沒有可據以轉換的目標。"""
    Image.new("RGB", (40, 30), ORANGE).save(tmp_path / "c.png")
    with pytest.raises(ValueError) as e:
        export_pdf(_figure_doc("c.png"), template, tmp_path / "o.pdf",
                   footer=False, image_base_dir=tmp_path, pdfx="none",
                   color_convert=True)
    assert "一般 PDF" in str(e.value)


def test_export_rejects_unknown_intent(tmp_path, template):
    Image.new("RGB", (40, 30), ORANGE).save(tmp_path / "c.png")
    with pytest.raises(ValueError) as e:
        export_pdf(_figure_doc("c.png"), template, tmp_path / "o.pdf",
                   footer=False, image_base_dir=tmp_path,
                   icc_profile=OS_CMYK_PROFILE, color_convert=True,
                   rendering_intent="vivid")
    assert "rendering intent" in str(e.value)


def test_export_without_color_convert_still_converts_to_gray(tmp_path, template):
    """未開啟時行為不變（Sprint 137 的預設路徑不因新選項位移）。"""
    Image.new("RGB", (40, 30), ORANGE).save(tmp_path / "c.png")
    out = tmp_path / "o.pdf"
    result = export_pdf(_figure_doc("c.png"), template, out, footer=False,
                        image_base_dir=tmp_path, icc_profile=OS_CMYK_PROFILE)
    assert _first_image(out)[0]["ColorSpace"] == "/DeviceGray"
    assert "一般 PDF" in result.image_color_warnings[0]


# ---------- 命令列：同一套說法 ----------

@needs_real_icc
def test_cli_color_convert_reports_profile(tmp_path, capsys):
    import json
    from cjkfolio.cli import main
    Image.new("RGB", (40, 30), ORANGE).save(tmp_path / "c.png")
    doc = tmp_path / "d.doc.json"
    doc.write_text(json.dumps({
        "schema": "cjkfolio/document@2",
        "meta": {"title": "彩色樣張", "template": "neizai-zhengli",
                 "master": G_MASTER},
        "paragraphs": [{"text": "圖說", "style": "圖說-辰宇落雁"}],
        "images": [{"path": "c.png", "page": 1}],
    }, ensure_ascii=False), encoding="utf-8")
    rc = main(["export-pdf", str(doc), "-o", str(tmp_path / "cli.pdf"),
               "--template", str(ROOT / "templates" / "neizai-zhengli.json"),
               "--no-footer", "--icc", str(OS_CMYK_PROFILE),
               "--color-convert"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DeviceCMYK 1 張" in out
    assert "影像色彩：" in out and "轉為 CMYK 嵌入" in out
