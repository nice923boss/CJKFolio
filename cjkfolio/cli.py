"""命令列入口（Phase 1 極簡介面）：txt 匯入與多頁 PNG 渲染。

用法（自 repo 根執行）：
  python -m cjkfolio.cli import-txt 稿.txt -o doc.json --title 書名
  python -m cjkfolio.cli import-md 稿.md -o doc.json --title 書名
  python -m cjkfolio.cli import-docx 稿.docx -o doc.json --title 書名
  python -m cjkfolio.cli assign-styles doc.json -o out.doc.json
  python -m cjkfolio.cli extract-styles 參考.pdf -o draft.json
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
from .document import (
    load_document,
    save_document,
    unknown_char_style_refs,
    unknown_style_refs,
)
from .docx_import import import_docx
from .md_import import import_markdown_file
from .pdf_writer import export_pdf
from .preflight import check_pdfx1a
from .reference_extract import extract_draft
from .render import render_document
from .styles import load_template
from .txt_import import DEFAULT_BODY_STYLE, import_txt_file

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"


def cmd_import_txt(args) -> int:
    doc = import_txt_file(
        args.input,
        default_style=args.style,
        title=args.title or Path(args.input).stem,
    )
    save_document(doc, args.output)
    print(f"匯入完成：{len(doc.paragraphs)} 段 → {args.output}")
    return 0


def cmd_import_md(args) -> int:
    template = load_template(args.template)
    doc = import_markdown_file(
        args.input,
        mapping=template.md_mapping,
        inline_mapping=template.md_inline_mapping,
        title=args.title or Path(args.input).stem,
    )
    save_document(doc, args.output)
    styles_used = sorted({p.style for p in doc.paragraphs})
    print(f"匯入完成：{len(doc.paragraphs)} 段 → {args.output}")
    print(f"對映樣式：{'、'.join(styles_used)}")
    return 0


def cmd_import_docx(args) -> int:
    template = load_template(args.template)
    doc = import_docx(
        args.input,
        mapping=template.md_mapping,
        inline_mapping=template.md_inline_mapping,
        title=args.title or Path(args.input).stem,
    )
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
    result = suggest_styles(
        [p.text for p in doc.paragraphs], candidates, config,
        default_style=default_style, batch_char_limit=args.batch_chars,
    )
    for warning in result.warnings:
        print(f"警告：{warning}")
    out_doc = apply_suggestions(doc, result.assignments)
    changed = sum(1 for a, b in zip(doc.paragraphs, out_doc.paragraphs) if a.style != b.style)
    save_document(out_doc, args.output)
    counts = {}
    for p in out_doc.paragraphs:
        counts[p.style] = counts.get(p.style, 0) + 1
    print(f"指派完成：{len(doc.paragraphs)} 段（{result.batches} 批）、改派 {changed} 段 → {args.output}")
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
    )
    print(f"渲染完成：{len(result.paths)} 頁 → {args.output}")
    if result.images_placed:
        print(f"置入圖：{result.images_placed} 張（灰階單 K；槽式與 rect 任意圖框）")
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
    result = export_pdf(
        doc, template, args.output,
        pages=[args.page] if args.page else None,
        footer=not args.no_footer, first_page=args.first_page,
        output_condition_identifier=args.output_condition_identifier,
        output_condition=args.output_condition,
        icc_profile=args.icc, image_base_dir=Path(args.document).parent,
    )
    print(f"匯出完成：{result.page_count} 頁 → {result.path}")
    print(f"PDF/X-1a:2001 識別：OutputIntent {result.output_condition_identifier}"
          + ("（嵌入 ICC）" if result.icc_embedded else "（registry 識別，免嵌 ICC）"))
    if result.images_placed:
        print(f"置入圖：{result.images_placed} 張（DeviceGray 影像 XObject，灰階單 K）")
    print(_justify_line(result.justify_stats))
    print(f"禁則檢查：{'0 違規' if not result.violations else result.violations}")
    for warning in result.font_warnings:
        print(f"字型警告：{warning}")
    for emb in result.embedded_fonts:
        print(f"嵌入字型：{emb['base']}（{emb['glyphs']} 字形，子集 {emb['bytes']:,} bytes）")
    return 0


def cmd_assemble(args) -> int:
    book = load_book(args.book)
    doc = assemble_book(book, base_dir=Path(args.book).parent)
    save_document(doc, args.output)
    marks = sum(1 for p in doc.paragraphs if p.master)
    print(f"組裝完成：{len(book.chapters)} 章 → {len(doc.paragraphs)} 段"
          f"（{marks} 個節首標記）→ {args.output}")
    if doc.images:
        print(f"書冊層級置入圖：{len(doc.images)} 張（page＝全書版面頁號）")
    return 0


def cmd_preflight(args) -> int:
    report = check_pdfx1a(args.pdf)
    for finding in report.findings:
        print(f"{'通過' if finding.ok else '不過'}｜{finding.rule}：{finding.detail}")
    print("未涵蓋（誠實聲明）：" + "；".join(report.not_covered))
    passed = sum(1 for finding in report.findings if finding.ok)
    print(f"結論：{'全數通過' if report.ok else '未通過'}（{passed}/{len(report.findings)}）")
    return 0 if report.ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cjkfolio", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import-txt", help="txt 匯入為文件 JSON（空行切段，全掛預設樣式）")
    p_import.add_argument("input")
    p_import.add_argument("-o", "--output", required=True)
    p_import.add_argument("--style", default=DEFAULT_BODY_STYLE)
    p_import.add_argument("--title", default="")
    p_import.set_defaults(func=cmd_import_txt)

    p_md = sub.add_parser("import-md", help="Markdown 匯入（標題層級直接對映模版樣式）")
    p_md.add_argument("input")
    p_md.add_argument("-o", "--output", required=True)
    p_md.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_md.add_argument("--title", default="")
    p_md.set_defaults(func=cmd_import_md)

    p_docx = sub.add_parser("import-docx", help="docx 匯入（OOXML 標題層級直接對映模版樣式，不依賴 Word）")
    p_docx.add_argument("input")
    p_docx.add_argument("-o", "--output", required=True)
    p_docx.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_docx.add_argument("--title", default="")
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

    p_render = sub.add_parser("render", help="文件 JSON 渲染為多頁 PNG")
    p_render.add_argument("document")
    p_render.add_argument("-o", "--output", required=True)
    p_render.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_render.add_argument("--dpi", type=int, default=150)
    p_render.add_argument("--basename", default="page")
    p_render.add_argument("--first-page", type=int, default=1, help="首頁的書頁碼（頁腳與鏡像奇偶依此）")
    p_render.add_argument("--no-footer", action="store_true", help="不畫頁腳三件組")
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
    p_pdf.set_defaults(func=cmd_export_pdf)

    p_asm = sub.add_parser("assemble",
                           help="書冊清單 JSON 組裝為單一多主版文件 JSON（章序即節序，章首掛節首標記）")
    p_asm.add_argument("book", help="書冊清單 JSON（cjkfolio/book@1；章路徑相對此檔目錄）")
    p_asm.add_argument("-o", "--output", required=True)
    p_asm.set_defaults(func=cmd_assemble)

    p_pre = sub.add_parser("preflight", help="PDF/X-1a 機械檢查（自寫規則；非 Acrobat 認證級）")
    p_pre.add_argument("pdf")
    p_pre.set_defaults(func=cmd_preflight)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
