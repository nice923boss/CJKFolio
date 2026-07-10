"""命令列入口（Phase 1 極簡介面）：txt 匯入與多頁 PNG 渲染。

用法（自 repo 根執行）：
  python -m cjkfolio.cli import-txt 稿.txt -o doc.json --title 書名
  python -m cjkfolio.cli import-md 稿.md -o doc.json --title 書名
  python -m cjkfolio.cli render doc.json -o out/樣張 --dpi 150 --first-page 30
"""
import argparse
import sys
from pathlib import Path

from .document import load_document, save_document, unknown_style_refs
from .md_import import import_markdown_file
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
        title=args.title or Path(args.input).stem,
    )
    save_document(doc, args.output)
    styles_used = sorted({p.style for p in doc.paragraphs})
    print(f"匯入完成：{len(doc.paragraphs)} 段 → {args.output}")
    print(f"對映樣式：{'、'.join(styles_used)}")
    return 0


def cmd_render(args) -> int:
    doc = load_document(args.document)
    template = load_template(args.template)
    unknown = unknown_style_refs(doc, template)
    if unknown:
        print(f"錯誤：文件引用模版沒有的樣式：{unknown}")
        return 2
    result = render_document(
        doc, template, args.output, dpi=args.dpi, basename=args.basename,
        footer=not args.no_footer, first_page=args.first_page,
    )
    print(f"渲染完成：{len(result.paths)} 頁 → {args.output}")
    print(f"禁則檢查：{'0 違規' if not result.violations else result.violations}")
    for warning in result.font_warnings:
        print(f"字型警告：{warning}")
    print("使用字型：" + "、".join(Path(f).name for f in result.fonts_used))
    if result.paths:
        print(f"首頁：{result.paths[0]}")
        print(f"末頁：{result.paths[-1]}")
    return 0


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

    p_render = sub.add_parser("render", help="文件 JSON 渲染為多頁 PNG")
    p_render.add_argument("document")
    p_render.add_argument("-o", "--output", required=True)
    p_render.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    p_render.add_argument("--dpi", type=int, default=150)
    p_render.add_argument("--basename", default="page")
    p_render.add_argument("--first-page", type=int, default=1, help="首頁的書頁碼（頁腳用）")
    p_render.add_argument("--no-footer", action="store_true", help="不畫頁腳三件組")
    p_render.set_defaults(func=cmd_render)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
