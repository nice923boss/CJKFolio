"""命令列入口（Phase 1 極簡介面）：txt 匯入與多頁 PNG 渲染。

用法（自 repo 根執行）：
  python -m cjkfolio.cli import-txt 稿.txt -o doc.json --title 書名
  python -m cjkfolio.cli import-md 稿.md -o doc.json --title 書名
  python -m cjkfolio.cli import-docx 稿.docx -o doc.json --title 書名
  python -m cjkfolio.cli assign-styles doc.json -o out.doc.json
  python -m cjkfolio.cli extract-styles 參考.pdf -o draft.json
  python -m cjkfolio.cli merge-styles 模版.json draft.json -o 新模版.json
  python -m cjkfolio.cli assemble book.json -o 全書.doc.json
  python -m cjkfolio.cli render doc.json -o out/樣張 --dpi 150 --first-page 30
  python -m cjkfolio.cli export-pdf doc.json -o out/書.pdf
  python -m cjkfolio.cli preflight out/書.pdf
"""
import argparse
import sys
from pathlib import Path

from .ai_config import load_ai_config
from .ai_style import apply_suggestions, suggest_styles
from .book import assemble_book, load_book
from .color_convert import DEFAULT_INTENT, RENDERING_INTENTS
from .document import (
    load_document,
    save_document,
    unknown_char_style_refs,
    unknown_style_refs,
)
from .docx_import import import_docx
from .font_license import LICENSE_POLICIES, LicenseBlocked
from .images import MIN_IMAGE_PPI
from .ink import MAX_TAC
from .md_import import import_markdown_file
from .pdf_writer import export_pdf
from .preflight import (
    check_image_resolution,
    check_ink_coverage,
    check_pdfx,
    image_resolution_summary,
    image_rows,
    ink_coverage_summary,
    ink_rows,
    preflight_summary,
)
from .reference_extract import extract_draft
from .render import render_document
from .styles import load_template, save_template
from .template_library import merge_draft_styles, resolve_template_dir
from .cover import with_cover
from .txt_import import DEFAULT_BODY_STYLE, import_txt_file

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = resolve_template_dir() / "neizai-zhengli.json"

# 字型是使用者資產（二進位不入 repo，見 assets/fonts/FONTS.md 與 GAPS #12），
# 不會跟著 wheel 走；pip 安裝形態非給不可，自 repo 執行則維持預設不必給。
FONT_DIR_HELP = "字型目錄（預設 assets/fonts；pip 安裝形態需明給）"


def _import_target(args, template):
    """匯入的文件要掛哪一套模版與哪張主版（Sprint 105 多書專案）。

    模版 id 取模版檔名（`--template` 指的就是那份模版，不另猜）；主版取 `--master`
    覆寫，未給則取模版自行宣告的 default_master。兩者都沒有時快速失敗並列出可選
    主版，不沉默套用參考書的「A-內文版」（第二本書並無此主版名）。
    """
    template_id = Path(args.template).stem
    master = getattr(args, "master", "") or template.default_master
    if not master:
        raise SystemExit(
            f"模版 {template_id} 未宣告 default_master，請以 --master 指定主版"
            f"（可選：{'、'.join(sorted(template.masters))}）")
    if master not in template.masters:
        raise SystemExit(
            f"主版「{master}」不存在於模版 {template_id}"
            f"（可選：{'、'.join(sorted(template.masters))}）")
    return template_id, master


def _maybe_cover(doc, template, args):
    """--cover 時於書首建封面頁（Sprint 132）；未指定即回原文件。

    三個匯入子命令共用單一入口：封面主版與書名樣式一律由模版宣告推導
    （cjkfolio.cover），三處各自寫死即為 Sprint 107 修過的同型缺陷。
    """
    if not getattr(args, "cover", False):
        return doc
    doc = with_cover(doc, template)
    print(f"已建封面（主版 {doc.cover}）：頁碼自封面翻開後起算")
    return doc


def cmd_import_txt(args) -> int:
    template = load_template(args.template)
    template_id, master = _import_target(args, template)
    # 未指定即取該模版的內文樣式：寫死第一本書的樣式名會讓第二本書匯入 exit 0
    # 卻產出 render 才爆的文件（Sprint 107；同 Sprint 105 把 master 搬進模版）
    doc = import_txt_file(
        args.input,
        default_style=args.style or template.md_mapping.get(
            "paragraph", DEFAULT_BODY_STYLE),
        title=args.title or Path(args.input).stem,
        template_id=template_id,
        master=master,
    )
    doc = _maybe_cover(doc, template, args)
    save_document(doc, args.output)
    print(f"匯入完成：{len(doc.paragraphs)} 段 → {args.output}")
    return 0


def cmd_import_md(args) -> int:
    template = load_template(args.template)
    template_id, master = _import_target(args, template)
    doc = import_markdown_file(
        args.input,
        mapping=template.md_mapping,
        inline_mapping=template.md_inline_mapping,
        title=args.title or Path(args.input).stem,
        template_id=template_id,
        master=master,
    )
    doc = _maybe_cover(doc, template, args)
    save_document(doc, args.output)
    styles_used = sorted({p.style for p in doc.paragraphs})
    print(f"匯入完成：{len(doc.paragraphs)} 段 → {args.output}")
    print(f"對映樣式：{'、'.join(styles_used)}")
    return 0


def cmd_import_docx(args) -> int:
    template = load_template(args.template)
    template_id, master = _import_target(args, template)
    doc = import_docx(
        args.input,
        mapping=template.md_mapping,
        inline_mapping=template.md_inline_mapping,
        title=args.title or Path(args.input).stem,
        template_id=template_id,
        master=master,
    )
    doc = _maybe_cover(doc, template, args)
    save_document(doc, args.output)
    styles_used = sorted({p.style for p in doc.paragraphs})
    print(f"匯入完成：{len(doc.paragraphs)} 段 → {args.output}")
    print(f"對映樣式：{'、'.join(styles_used)}")
    return 0


def cmd_assign_styles(args) -> int:
    """AI 樣式指派（§4.4）：txt 入口的初稿建議；md／docx 結構優先不經此。"""
    doc = load_document(args.document)
    template = load_template(args.template)
    config = load_ai_config(args.config)
    if not (config.base_url and config.model):
        print(f"錯誤：AI 未設定（{args.config} 缺 base_url／model）。"
              "AI 為選配：可跳過本步驟，直接以編輯器人工指派樣式。")
        return 2
    candidates = tuple(template.paragraph_styles)
    default_style = template.md_mapping.get("paragraph", next(iter(candidates)))
    spec = template.auto_toc
    result = suggest_styles(
        [p.text for p in doc.paragraphs], candidates, config,
        default_style=default_style, batch_char_limit=args.batch_chars,
        toc_levels=spec.level_hints() if spec is not None else (),
    )
    for warning in result.warnings:
        print(f"警告：{warning}")
    out_doc = apply_suggestions(doc, result.assignments, result.toc_entries)
    changed = sum(1 for a, b in zip(doc.paragraphs, out_doc.paragraphs) if a.style != b.style)
    entries = sum(1 for p in out_doc.paragraphs if p.toc_title)
    save_document(out_doc, args.output)
    counts = {}
    for p in out_doc.paragraphs:
        counts[p.style] = counts.get(p.style, 0) + 1
    print(f"指派完成：{len(doc.paragraphs)} 段（{result.batches} 批）、改派 {changed} 段、"
          f"目次條目 {entries} 段 → {args.output}")
    print("樣式分布：" + "、".join(f"{k}×{v}" for k, v in sorted(counts.items())))
    print("定位提醒：AI 建議為初稿，請以編輯器逐段確認與批次改派（§4.4）。")
    return 0


def cmd_extract_styles(args) -> int:
    """從參考 PDF 萃取起始樣式草稿（§4.3）；草稿只含量測參數，不含 PDF 文句。"""
    import json as _json

    draft = extract_draft(args.input, min_chars=args.min_chars,
                          max_styles=args.max_styles)
    Path(args.output).write_text(
        _json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"萃取完成：{draft['pages']} 頁 → {len(draft['paragraph_styles'])} 個樣式提案 → {args.output}")
    for name, s in draft["paragraph_styles"].items():
        print(f"  {name:<24} ← {s['source_font']:<28} {s['note']}")
    if draft["skipped"]:
        print(f"濾除 {len(draft['skipped'])} 組（門檻／上限，草稿 skipped 段列明細）")
    if draft["colors"]:
        top = "、".join(f"{c['hex']}（{c['chars']:,} 字）" for c in draft["colors"][:3])
        print(f"用色統計：{top}")
    print("定位提醒：草稿供命名與調整（§4.3），可經樣式管理 UI 逐條新增至模版。")
    return 0


def cmd_merge_styles(args) -> int:
    """萃取草稿一鍵併入模版（§4.3 模版庫；extract-styles → merge-styles 全鏈）。"""
    import json as _json

    template = load_template(args.template)
    draft = _json.loads(Path(args.draft).read_text(encoding="utf-8"))
    merged, report = merge_draft_styles(template, draft)
    save_template(merged, args.output)
    print(f"併入完成：新增 {len(report.added)} 個段落樣式 → {args.output}")
    for name in report.added:
        print(f"  ＋ {name}")
    if report.skipped:
        print(f"跳過 {len(report.skipped)} 個（同名既有優先，不覆蓋）：")
        for s in report.skipped:
            print(f"  － {s.name}")
    print("定位提醒：併入樣式為草稿命名（§4.3），可經樣式管理 UI 改名與調整。")
    return 0


def _justify_line(stats: dict) -> str:
    return (f"齊行統計：擠入 {stats['squeezed']} 行、撐開 {stats['stretched']} 行、"
            f"超容忍 {stats['beyond']} 行（維持網格）")


def _check_style_refs(doc, template) -> int:
    unknown = unknown_style_refs(doc, template)
    if unknown:
        print(f"錯誤：文件引用模版沒有的樣式：{unknown}")
        return 2
    unknown_char = unknown_char_style_refs(doc, template)
    if unknown_char:
        print(f"錯誤：文件引用模版沒有的字元樣式：{unknown_char}")
        return 2
    return 0


def cmd_render(args) -> int:
    doc = load_document(args.document)
    template = load_template(args.template)
    if _check_style_refs(doc, template):
        return 2
    result = render_document(
        doc, template, args.output, dpi=args.dpi, basename=args.basename,
        footer=not args.no_footer, first_page=args.first_page,
        image_base_dir=Path(args.document).parent,
        font_dir=args.font_dir or None,
    )
    print(f"渲染完成：{len(result.paths)} 頁 → {args.output}")
    if result.images_placed:
        print(f"置入圖：{result.images_placed} 張（PNG 預覽一律灰階畫布，"
              f"彩色 CMYK 只在 PDF 完稿呈現；槽式與 rect 任意圖框）")
    print(f"禁則檢查：{'0 違規' if not result.violations else result.violations}")
    print(_justify_line(result.justify_stats))
    for warning in result.font_warnings:
        print(f"字型警告：{warning}")
    print("使用字型：" + "、".join(Path(f).name for f in result.fonts_used))
    if result.paths:
        print(f"首頁：{result.paths[0]}")
        print(f"末頁：{result.paths[-1]}")
    return 0


def cmd_export_pdf(args) -> int:
    doc = load_document(args.document)
    template = load_template(args.template)
    if _check_style_refs(doc, template):
        return 2
    if args.trim_only and (args.crop_marks or args.press_marks):
        print("錯誤：--trim-only 沒有出血與標記帶，不可搭 --crop-marks／--press-marks",
              file=sys.stderr)
        return 2
    if args.registration_single_k and not args.press_marks:
        print("錯誤：--registration-single-k 需搭 --press-marks"
              "（套準十字只在印前標記中產生）", file=sys.stderr)
        return 2
    try:
        result = export_pdf(
            doc, template, args.output,
            pages=[args.page] if args.page else None,
            footer=not args.no_footer, first_page=args.first_page,
            output_condition_identifier=args.output_condition_identifier,
            output_condition=args.output_condition,
            icc_profile=args.icc, image_base_dir=Path(args.document).parent,
            pdfx=args.pdfx, crop_marks=args.crop_marks,
            press_marks=args.press_marks,
            registration_single_k=args.registration_single_k,
            trim_only=args.trim_only,
            color_convert=args.color_convert,
            rendering_intent=args.rendering_intent,
            license_policy=args.license_policy,
            max_tac=args.max_tac,
            font_dir=args.font_dir or None,
        )
    except LicenseBlocked as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 2
    print(f"匯出完成：{result.page_count} 頁 → {result.path}")
    if result.trim_only:
        print("只輸出成品範圍：MediaBox=TrimBox=BleedBox=成品尺寸，無出血")
    if result.crop_marks:
        print("裁切標記：8 條單 K 角標（MediaBox 外擴、BleedBox=trim+出血）")
    if result.press_marks:
        reg = "單 K100" if result.registration_single_k else "四版套準色"
        print(f"印前標記：四邊中點套準十字（{reg}）＋色條 8 塊＋灰梯尺 9 階"
              "（落在 TrimBox 外的標記環內）")
        print("印前標記為自擬配置，非任何標準控制條（Ugra／Fogra／Brunner）；"
              "送印前請向印廠索取規格")
    # 依成品自身的事實分流（一般 PDF 未寫 OutputIntent → 識別為空字串），與
    # editor 報告同一條判準：報告要說的是檔案裡有什麼，不是選項送了什麼。
    if not result.output_condition_identifier:
        print(f"{result.pdfx_label}：無 OutputIntent、無 GTS 識別鍵，不可送印")
    else:
        print(f"{result.pdfx_label} 識別：OutputIntent {result.output_condition_identifier}"
              + ("（嵌入 ICC）" if result.icc_embedded else "（registry 識別，免嵌 ICC）"))
    if result.images_placed:
        spaces = "、".join(
            f"{cs.lstrip('/')} {n} 張"
            for cs, n in sorted(result.image_colorspaces.items()))
        print(f"置入圖：{result.images_placed} 張影像 XObject（{spaces}）")
        for warning in result.image_color_warnings:
            print(f"影像色彩：{warning}")
        for warning in result.ppi_warnings:
            print(warning)
        if not result.ppi_warnings:
            print("影像解析度：置入影像實效 PPI 皆達 §9 300ppi 下限")
        for warning in result.bleed_warnings:
            print(warning)
    if result.tac_warnings:
        for warning in result.tac_warnings:
            print(warning)
    elif result.ink_uses:
        print(f"油墨總量：最高 TAC {result.ink_uses[0].tac:.0f}%"
              f"（{result.ink_uses[0].kind} {result.ink_uses[0].label}）"
              f"，未逾上限 {args.max_tac:.0f}%")
    print(_justify_line(result.justify_stats))
    print(f"禁則檢查：{'0 違規' if not result.violations else result.violations}")
    for warning in result.font_warnings:
        print(f"字型警告：{warning}")
    if result.license_warnings:
        for warning in result.license_warnings:
            print(warning)
        if args.license_policy == "warn":
            print("以上為提示，未擋匯出；要擋請加 --license-policy block")
    else:
        print("字型授權：嵌入字型皆可合法嵌入子集，且皆宣告可散布授權"
              "（fsType 位元＋name 表 ID 13／14 檢查）")
    for emb in result.embedded_fonts:
        print(f"嵌入字型：{emb['base']}（{emb['glyphs']} 字形，子集 {emb['bytes']:,} bytes）")
    return 0


def cmd_assemble(args) -> int:
    book = load_book(args.book)
    base = Path(args.book).parent
    has_toc = any(ch.toc_spec for ch in book.chapters)
    items = ()
    if has_toc:
        if not args.template:
            print("錯誤：此書冊含自動目錄章（generate_toc），需 --template <模版路徑> "
                  "以計算目錄頁碼", file=sys.stderr)
            return 2
        from .toc import assemble_book_with_toc, toc_items
        template = load_template(args.template)
        items = toc_items(book, template, base_dir=base, first_page=args.first_page)
        doc = assemble_book_with_toc(book, template, base_dir=base,
                                     first_page=args.first_page)
    else:
        doc = assemble_book(book, base_dir=base)
    save_document(doc, args.output)
    marks = sum(1 for p in doc.paragraphs if p.master)
    print(f"組裝完成：{len(book.chapters)} 章 → {len(doc.paragraphs)} 段"
          f"（{marks} 個節首標記）→ {args.output}")
    if has_toc:
        if items:
            print("自動目錄（first-page=%d）：%s" % (
                args.first_page, "；".join(f"{it.title}→{it.page}" for it in items)))
        else:
            print("自動目錄：（無列入章 toc_title）")
    if doc.images:
        print(f"書冊層級置入圖：{len(doc.images)} 張（page＝全書版面頁號）")
    return 0


def cmd_preflight(args) -> int:
    report = check_pdfx(args.pdf, profile=args.pdfx)
    for finding in report.findings:
        print(f"{'通過' if finding.ok else '不過'}｜{finding.rule}：{finding.detail}")
    print("未涵蓋（誠實聲明）：" + "；".join(report.not_covered))
    print(f"結論：{preflight_summary(report)}")
    # 影像解析度為 §9 印廠條件（非 X-1a 條款）：獨立規則集，不影響 X 合規判定
    img = check_image_resolution(args.pdf, min_ppi=args.min_ppi)
    for status, rule, detail in image_rows(img):
        print(f"{status}｜{rule}：{detail}")
    print(f"影像解析度（§9，非 X-1a 條款）：{image_resolution_summary(img)}")
    # 總墨量亦為 §9 印廠條件（非 X-1a 條款）：獨立規則集，不影響 X 合規判定
    ink = check_ink_coverage(args.pdf, max_tac=args.max_tac)
    for status, rule, detail in ink_rows(ink):
        print(f"{status}｜{rule}：{detail}")
    print(f"油墨總量（§9，非 X-1a 條款）：{ink_coverage_summary(ink)}")
    return 0 if report.ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cjkfolio", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import-txt", help="txt 匯入為文件 JSON（空行切段，全掛預設樣式）")
    p_import.add_argument("input")
    p_import.add_argument("-o", "--output", required=True)
    p_import.add_argument("--style", default="",
                          help="全掛哪個段落樣式（預設取模版 md_mapping 的 paragraph）")
    p_import.add_argument("--title", default="")
    p_import.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_import.add_argument("--master", default="",
                          help="掛哪張主版（預設取模版宣告的 default_master）")
    p_import.add_argument("--cover", action="store_true",
                          help="於書首建封面頁（可置圖與加字），頁碼自封面翻開後起算")
    p_import.set_defaults(func=cmd_import_txt)

    p_md = sub.add_parser("import-md", help="Markdown 匯入（標題層級直接對映模版樣式）")
    p_md.add_argument("input")
    p_md.add_argument("-o", "--output", required=True)
    p_md.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_md.add_argument("--master", default="",
                      help="掛哪張主版（預設取模版宣告的 default_master）")
    p_md.add_argument("--title", default="")
    p_md.add_argument("--cover", action="store_true",
                          help="於書首建封面頁（可置圖與加字），頁碼自封面翻開後起算")
    p_md.set_defaults(func=cmd_import_md)

    p_docx = sub.add_parser("import-docx", help="docx 匯入（OOXML 標題層級直接對映模版樣式，不依賴 Word）")
    p_docx.add_argument("input")
    p_docx.add_argument("-o", "--output", required=True)
    p_docx.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_docx.add_argument("--master", default="",
                        help="掛哪張主版（預設取模版宣告的 default_master）")
    p_docx.add_argument("--title", default="")
    p_docx.add_argument("--cover", action="store_true",
                          help="於書首建封面頁（可置圖與加字），頁碼自封面翻開後起算")
    p_docx.set_defaults(func=cmd_import_docx)

    p_assign = sub.add_parser("assign-styles",
                              help="AI 樣式指派（§4.4 初稿建議；失敗批降級維持原樣式）")
    p_assign.add_argument("document")
    p_assign.add_argument("-o", "--output", required=True)
    p_assign.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_assign.add_argument("--config", default=str(ROOT / "local" / "ai-config.local.json"))
    p_assign.add_argument("--batch-chars", type=int, default=3000,
                          help="單批字數上限（長書稿分批送，段落不跨批）")
    p_assign.set_defaults(func=cmd_assign_styles)

    p_ext = sub.add_parser("extract-styles",
                           help="從參考 PDF 萃取起始樣式草稿（§4.3 從參考萃取）")
    p_ext.add_argument("input")
    p_ext.add_argument("-o", "--output", required=True)
    p_ext.add_argument("--min-chars", type=int, default=60,
                       help="納入提案的最少字數（低於門檻列 skipped 不沉默）")
    p_ext.add_argument("--max-styles", type=int, default=20)
    p_ext.set_defaults(func=cmd_extract_styles)

    p_merge = sub.add_parser("merge-styles",
                             help="萃取草稿一鍵併入模版（同名跳過不覆蓋）")
    p_merge.add_argument("template")
    p_merge.add_argument("draft")
    p_merge.add_argument("-o", "--output", required=True)
    p_merge.set_defaults(func=cmd_merge_styles)

    p_render = sub.add_parser("render", help="文件 JSON 渲染為多頁 PNG")
    p_render.add_argument("document")
    p_render.add_argument("-o", "--output", required=True)
    p_render.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_render.add_argument("--dpi", type=int, default=150)
    p_render.add_argument("--basename", default="page")
    p_render.add_argument("--first-page", type=int, default=1, help="首頁的書頁碼（頁腳與鏡像奇偶依此）")
    p_render.add_argument("--no-footer", action="store_true", help="不畫頁腳三件組")
    p_render.add_argument("--font-dir", default="", help=FONT_DIR_HELP)
    p_render.set_defaults(func=cmd_render)

    p_pdf = sub.add_parser("export-pdf", help="文件 JSON 匯出 PDF（字型子集嵌入，盒框依 PLAN §9）")
    p_pdf.add_argument("document")
    p_pdf.add_argument("-o", "--output", required=True)
    p_pdf.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_pdf.add_argument("--page", type=int, default=None, help="只匯出此版面頁（1 起算；預設全頁）")
    p_pdf.add_argument("--first-page", type=int, default=1, help="首頁的書頁碼（頁腳與鏡像奇偶依此）")
    p_pdf.add_argument("--no-footer", action="store_true", help="不排頁腳三件組")
    p_pdf.add_argument("--output-condition-identifier", default="JC200103",
                       help="OutputIntent 印刷條件識別（ICC registry 名；預設 Japan Color 2001 Coated）")
    p_pdf.add_argument("--output-condition", default="Japan Color 2001 Coated",
                       help="印刷條件人讀描述")
    p_pdf.add_argument("--icc", default=None,
                       help="嵌入 DestOutputProfile 的 CMYK 輸出 ICC 檔（自訂識別時必填）")
    p_pdf.add_argument("--pdfx", choices=["x-1a", "x-4", "none"], default="x-1a",
                       help="輸出形態（預設 x-1a:2001；x-4:2010 須以 --icc 提供 ICC；"
                            "none＝非 PDF/X 的一般 PDF，可含 RGB 彩色影像但不可送印）")
    p_pdf.add_argument("--color-convert", action="store_true",
                       help="RGB 置入圖依 --icc 的描述檔轉 CMYK 嵌入（須有 --icc；"
                            "灰階與 CMYK 來源不動）。顏色是否符合印出來的樣子須打樣確認")
    p_pdf.add_argument("--rendering-intent", choices=sorted(RENDERING_INTENTS),
                       default=DEFAULT_INTENT,
                       help="色彩轉換的 rendering intent（預設 relative＝相對色度；"
                            "perceptual＝感知，全域壓縮色域）")
    p_pdf.add_argument("--crop-marks", action="store_true",
                       help="加裁切標記（MediaBox 外擴、BleedBox=trim+出血、8 條單 K 角標）")
    p_pdf.add_argument("--trim-only", action="store_true",
                       help="只輸出成品範圍（無出血；超出成品邊的圖裁掉，不留白邊）。"
                            "不可搭 --crop-marks／--press-marks")
    p_pdf.add_argument("--press-marks", action="store_true",
                       help="加印前標記（四邊中點套準十字、色條 8 塊、灰梯尺 9 階；"
                            "MediaBox 外擴 8mm。套準十字為四版套準色 TAC 400%%，"
                            "油墨檢查將據實回報一處超標，該標記位於 TrimBox 外）")
    p_pdf.add_argument("--registration-single-k", action="store_true",
                       help="套準十字改單 K100（油墨檢查全綠，但該標記不會出現在 "
                            "C／M／Y 印版上）；需搭 --press-marks")
    p_pdf.add_argument("--max-tac", type=float, default=MAX_TAC,
                       help="總墨量上限百分比（印廠條件；§9 320〜340%%，預設 320）；"
                            "只影響油墨警告門檻，不改寫出的位元")
    p_pdf.add_argument("--license-policy", choices=list(LICENSE_POLICIES), default="warn",
                       help="字型授權未過時的處置：warn 只提示（預設）；"
                            "block 不產出檔案")
    p_pdf.add_argument("--font-dir", default="", help=FONT_DIR_HELP)
    p_pdf.set_defaults(func=cmd_export_pdf)

    p_asm = sub.add_parser("assemble",
                           help="書冊清單 JSON 組裝為單一多主版文件 JSON（章序即節序，章首掛節首標記）")
    p_asm.add_argument("book", help="書冊清單 JSON（cjkfolio/book@1；章路徑相對此檔目錄）")
    p_asm.add_argument("-o", "--output", required=True)
    p_asm.add_argument("--template",
                       help="模版路徑；含自動目錄章（generate_toc）時必填，用以計算目錄頁碼")
    p_asm.add_argument("--first-page", type=int, default=1,
                       help="首頁書頁碼（自動目錄頁碼依此換算，須與最終 render／export 一致）")
    p_asm.set_defaults(func=cmd_assemble)

    p_pre = sub.add_parser("preflight", help="PDF/X 機械檢查（自寫規則；非 Acrobat 認證級）")
    p_pre.add_argument("pdf")
    p_pre.add_argument("--pdfx", choices=["x-1a", "x-4"], default="x-1a",
                       help="以此 PDF/X 形態的規則集檢查（預設 x-1a）")
    p_pre.add_argument("--min-ppi", type=float, default=MIN_IMAGE_PPI,
                       help="影像實效解析度下限（§9 連續調 300〜350ppi，預設 300）")
    p_pre.add_argument("--max-tac", type=float, default=MAX_TAC,
                       help="總墨量上限百分比（§9 320〜340%%，預設 320）")
    p_pre.set_defaults(func=cmd_preflight)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
