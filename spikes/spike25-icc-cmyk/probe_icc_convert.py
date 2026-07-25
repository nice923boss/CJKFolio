"""Spike 25 探針：ICC 色彩管理下的 RGB → CMYK 轉換（GAPS #92 (a)(b)）。

問題不是「littleCMS 轉不轉得出來」（轉得出來，那是既知的），是**本產品該不該把這道
工序內建進送印路徑**。故本探針只量本機驗得到的機械性質，不宣稱色彩正確性：

1. 引擎與描述檔盤點：ImageCms 是否隨 Pillow 在庫；本機有無 §9 指定的 Japan Color；
   目標描述檔能否同時充當 X-1a／X-4 的 DestOutputProfile（轉換目標與宣告的輸出條件
   須為同一個檔，否則等於宣告 A 卻按 B 轉）
2. 中性灰是否守單 K（§9「灰階照片走單 K」）
3. 轉出影像的最高／平均 TAC（§9 ≤ 320〜340%，以既有 ink.image_max_tac 量）
4. rendering intent 之間的差異幅度，與本機有無依據可決定該用哪個
5. 300ppi 送印尺寸的耗時
6. 端到端：轉出的 CMYK 進本產品 PDF → PyMuPDF 取原始樣本位元組，於 PIL 之外複量

7. 來源側：未標記影像假設 sRGB 站不站得住
8. 反向（預覽的 CMYK → sRGB）改用 ICC 的代價（GAPS #92 (b)）

素材沿用 Sprint 137 R5 的 Owner 機器既有彩色影像（Windows Spotlight 桌布，屬 3D 算圖
非實拍照片；版權紅線：留 out/ 不入 repo）。
重現：python spikes/spike25-icc-cmyk/probe_icc_convert.py
"""
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageCms, ImageStat

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cjkfolio.ink import image_max_tac                    # noqa: E402
from cjkfolio.pdfx_meta import validate_output_profile    # noqa: E402

SOURCE = ROOT / "out" / "sprint137-r5" / "cover-color.png"
OUT = ROOT / "spikes" / "spike25-icc-cmyk" / "out"
COLOR_DIR = Path(r"C:\Windows\System32\spool\drivers\color")
INTENTS = {0: "perceptual", 1: "relative colorimetric",
           2: "saturation", 3: "absolute colorimetric"}


def rule(title: str) -> None:
    print(f"\n{'=' * 4} {title} {'=' * 4}")


def mean_tac(image: Image.Image) -> float:
    """平均墨量百分比（image_max_tac 只給最高點，平均用於看整張圖的重墨傾向）。"""
    return sum(ImageStat.Stat(image).mean) / 2.55


def describe(path: Path) -> dict:
    """讀 ICC 表頭：類別（prtr／mntr…）、資料色彩空間、說明。"""
    data = path.read_bytes()
    profile = ImageCms.getOpenProfile(str(path))
    return {
        "path": path,
        "cls": data[12:16].decode("latin-1"),
        "space": data[16:20].decode("latin-1").strip(),
        "desc": ImageCms.getProfileDescription(profile).strip(),
        "bytes": len(data),
    }


def probe_profiles() -> list:
    rule("1. 引擎與描述檔盤點")
    print(f"Pillow {Image.__version__}　littleCMS {ImageCms.core.littlecms_version}")
    found = []
    for path in sorted(COLOR_DIR.glob("*.ic[mc]")):
        try:
            info = describe(path)
        except Exception as exc:                       # 壞檔不中斷盤點
            print(f"  略過 {path.name}：{exc}")
            continue
        found.append(info)
        print(f"  {path.name:34} class={info['cls']} space={info['space']:5} "
              f"{info['bytes']:>7} bytes　{info['desc']}")
    cmyk = [i for i in found if i["space"] == "CMYK" and i["cls"] == "prtr"]
    print(f"\n可作轉換目標的 CMYK 輸出（prtr）描述檔：{len(cmyk)} 個")
    jc = [i for i in found if "japan" in i["desc"].lower()]
    print(f"§9 指定的 Japan Color 2001/2011 Coated：{'有 ' + jc[0]['desc'] if jc else '**本機沒有**'}")
    for info in cmyk:                                  # 同一檔能否充當 DestOutputProfile
        try:
            validate_output_profile(info["path"].read_bytes(), info["path"])
            print(f"  {info['path'].name}：validate_output_profile 通過"
                  f"（可同時作 X-1a／X-4 的 DestOutputProfile）")
        except ValueError as exc:
            print(f"  {info['path'].name}：validate_output_profile 拒收：{exc}")
    return cmyk


def neutral_ramp(dst_profile) -> None:
    """§9「灰階照片走單 K」：中性 RGB 灰經 ICC 轉換後 C／M／Y 是否為 0。"""
    rule("2. 中性灰是否守單 K")
    src = ImageCms.createProfile("sRGB")
    ramp = Image.new("RGB", (256, 1))
    ramp.putdata([(v, v, v) for v in range(256)])
    for intent, name in INTENTS.items():
        try:
            out = ImageCms.profileToProfile(
                ramp, src, dst_profile, renderingIntent=intent, outputMode="CMYK")
        except ImageCms.PyCMSError as exc:
            print(f"  intent {intent} {name}：不支援（{exc}）")
            continue
        px = list(out.getdata())
        polluted = [v for v in range(256) if any(px[v][:3])]
        mid, black = px[128], px[0]
        print(f"  intent {intent} {name:22}：256 階中 C/M/Y 非零 {len(polluted)} 階"
              f"　中灰 128 → CMYK {mid}　純黑 0 → CMYK {black}"
              f"　TAC 中灰 {sum(mid) / 2.55:.0f}% 純黑 {sum(black) / 2.55:.0f}%")


def convert_material(dst_profile, dst_name: str) -> dict:
    """真素材逐 intent 轉換：TAC、往返差、耗時。"""
    rule("3〜5. 真素材轉換（TAC、intent 差異、耗時）")
    src_img = Image.open(SOURCE)
    print(f"素材 {SOURCE.name} {src_img.mode} {src_img.size}"
          f"　來源內嵌 ICC：{'有' if src_img.info.get('icc_profile') else '無（依 sRGB 假設）'}")
    src = ImageCms.createProfile("sRGB")
    results = {}
    OUT.mkdir(parents=True, exist_ok=True)
    for intent, name in INTENTS.items():
        started = time.perf_counter()
        try:
            cmyk = ImageCms.profileToProfile(
                src_img, src, dst_profile, renderingIntent=intent, outputMode="CMYK")
        except ImageCms.PyCMSError as exc:
            print(f"  intent {intent} {name}：不支援（{exc}）")
            continue
        elapsed = time.perf_counter() - started
        back = ImageCms.profileToProfile(cmyk, dst_profile, src,
                                         renderingIntent=1, outputMode="RGB")
        diff = ImageChops.difference(src_img.convert("RGB"), back)
        stat = ImageStat.Stat(diff)
        results[intent] = cmyk
        cmyk.save(OUT / f"cover-{dst_name}-intent{intent}.tif")
        print(f"  intent {intent} {name:22}：最高 TAC {image_max_tac(cmyk):6.1f}%"
              f"　平均 TAC {mean_tac(cmyk):5.1f}%"
              f"　往返 RGB 平均差 {sum(stat.mean) / 3:5.2f}／255 最大 {max(stat.extrema[i][1] for i in range(3)):3}"
              f"　{elapsed * 1000:6.0f} ms")
    if 0 in results and 1 in results:                  # intent 之間的實際分量差
        d = ImageChops.difference(results[0], results[1])
        s = ImageStat.Stat(d)
        print(f"\n  perceptual 對 relative colorimetric 的分量差："
              f"平均 {sum(s.mean) / 4:.2f}／255、最大 {max(e[1] for e in s.extrema)}／255")
    # 300ppi 送印尺寸耗時（148×210mm 成品滿版）
    big = src_img.resize((int(148 / 25.4 * 300), int(210 / 25.4 * 300)), Image.LANCZOS)
    started = time.perf_counter()
    ImageCms.profileToProfile(big, src, dst_profile, renderingIntent=1, outputMode="CMYK")
    print(f"  300ppi 滿版 {big.size} 轉換耗時 {(time.perf_counter() - started) * 1000:.0f} ms")
    return results


def end_to_end(cmyk: Image.Image, dst_name: str) -> None:
    """Gate 4 獨立路徑：轉出的 CMYK 進本產品 PDF，再由 PyMuPDF 取原始樣本複量。"""
    rule("6. 端到端：本產品 PDF 寫出與 PyMuPDF 讀回")
    import fitz                                          # noqa: PLC0415
    from cjkfolio.document import load_document          # noqa: PLC0415
    from cjkfolio.pdf_writer import export_pdf           # noqa: PLC0415
    from cjkfolio.styles import load_template            # noqa: PLC0415

    src_doc = ROOT / "out" / "sprint137-r5" / "cover-color.doc.json"
    tif = OUT / f"cover-{dst_name}-intent1.tif"
    doc_json = OUT / "cover-cmyk.doc.json"
    doc_json.write_text(
        src_doc.read_text(encoding="utf-8").replace("cover-color.png", tif.name),
        encoding="utf-8")
    doc = load_document(doc_json)
    template = load_template(ROOT / "templates" / "neizai-zhengli.json")
    pdf = OUT / "封面-ICC轉CMYK-x1a.pdf"
    result = export_pdf(doc, template, pdf, image_base_dir=OUT)
    print(f"  寫出 {pdf.name}　影像色彩警告 {list(result.image_color_warnings) or '無'}")
    print(f"  墨量警告 {list(result.tac_warnings) or '無'}")

    with fitz.open(pdf) as fdoc:
        for xref in range(1, fdoc.xref_length()):
            obj = fdoc.xref_object(xref)
            if "/Image" not in obj:
                continue
            cs = fdoc.xref_get_key(xref, "ColorSpace")[1]
            decode = fdoc.xref_get_key(xref, "Decode")
            raw = fdoc.xref_stream(xref)                 # 解壓後的原始樣本
            peak = max(sum(raw[i:i + 4]) for i in range(0, len(raw) - 3, 4))
            print(f"  xref {xref}：ColorSpace {cs}　Decode {decode[1] if decode[0] != 'null' else '無'}"
                  f"　樣本 {len(raw)} bytes")
            print(f"  PIL 之外複量最高 TAC {peak / 2.55:.1f}%"
                  f"（PIL 自報 {image_max_tac(Image.open(tif)):.1f}%）")


def source_profile_handling(dst_profile) -> None:
    """來源側：未標記影像假設 sRGB 站不站得住（內嵌描述檔與合成 sRGB 是否等價）。"""
    rule("7. 來源描述檔的處置")
    import io                                            # noqa: PLC0415
    src_img = Image.open(SOURCE).convert("RGB")
    system_srgb = COLOR_DIR / "sRGB Color Space Profile.icm"
    tagged = OUT / "cover-tagged-srgb.png"
    src_img.save(tagged, icc_profile=system_srgb.read_bytes())
    reopened = Image.open(tagged)
    embedded = reopened.info.get("icc_profile")
    print(f"  存檔後內嵌描述檔：{'有 ' + str(len(embedded)) + ' bytes' if embedded else '無'}")
    by_embedded = ImageCms.profileToProfile(
        reopened, ImageCms.getOpenProfile(io.BytesIO(embedded)), dst_profile,
        renderingIntent=1, outputMode="CMYK")
    by_synth = ImageCms.profileToProfile(
        reopened, ImageCms.createProfile("sRGB"), dst_profile,
        renderingIntent=1, outputMode="CMYK")
    stat = ImageStat.Stat(ImageChops.difference(by_embedded, by_synth))
    print(f"  內嵌 sRGB 對合成 sRGB 的 CMYK 分量差：平均 {sum(stat.mean) / 4:.3f}／255、"
          f"最大 {max(e[1] for e in stat.extrema)}／255")


def preview_reverse(dst_profile) -> None:
    """GAPS #92 (b)：預覽的 CMYK → RGB 若改用 ICC 反算，內文暖黑會變成什麼。

    現行為無色彩管理的逐通道近似 255×(1−x)×(1−k)，其對單 K 恆產出中性灰。
    """
    rule("8. 預覽反向（CMYK → sRGB）改用 ICC 的代價")
    srgb = ImageCms.createProfile("sRGB")
    samples = {"內文暖黑 K92": (0, 0, 0, 235), "實黑 K100": (0, 0, 0, 255),
               "紙白 K0": (0, 0, 0, 0), "富黑 60/40/40/100": (153, 102, 102, 255)}
    patch = Image.new("CMYK", (len(samples), 1))
    patch.putdata(list(samples.values()))
    for flags, label in ((0, "無 BPC"), (ImageCms.Flags.BLACKPOINTCOMPENSATION, "帶 BPC")):
        out = ImageCms.profileToProfile(patch, dst_profile, srgb, renderingIntent=1,
                                        outputMode="RGB", flags=flags)
        px = list(out.getdata())
        for (name, cmyk), rgb in zip(samples.items(), px):
            naive = tuple(round(255 * (1 - c / 255) * (1 - cmyk[3] / 255)) for c in cmyk[:3])
            print(f"  {label}　{name:18}：ICC 反算 {str(rgb):16} 中性 {'是' if len(set(rgb)) == 1 else '**否**'}"
                  f"　現行逐通道近似 {naive}")


def main() -> None:
    cmyk_profiles = probe_profiles()
    if not cmyk_profiles:
        print("\n無 CMYK 輸出描述檔，探針中止（此結果本身即為結論輸入）")
        return
    target = cmyk_profiles[0]
    print(f"\n以 {target['path'].name}（{target['desc']}）為轉換目標繼續")
    dst = ImageCms.getOpenProfile(str(target["path"]))
    dst_name = target["path"].stem
    neutral_ramp(dst)
    results = convert_material(dst, dst_name)
    if 1 in results:
        end_to_end(results[1], dst_name)
    source_profile_handling(dst)
    preview_reverse(dst)


if __name__ == "__main__":
    main()
