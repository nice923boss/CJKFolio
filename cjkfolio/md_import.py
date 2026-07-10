"""Markdown 匯入（PLAN §4.4 設計修正 1）：標題層級由結構直接對映樣式，不經 AI。

block 級：#〜###### 標題、> 引文、清單項（各自成段）、空行段落。
行內：**強調** 與 *強調* 對映字元樣式 run（模版 md_inline_mapping 的
strong／em 鍵；未對映仍剝除標記、不掛樣式）。v1 不支援嵌套標記，
未閉合標記保留原字面。
"""
import re

from .document import Document, Paragraph, Run

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_RE = re.compile(r"^[-*+]\s+(.*)$")
_INLINE_RE = re.compile(r"(\*\*[^*\n]+\*\*|\*[^*\n]+\*)")


def inline_runs(text: str, inline_mapping: dict) -> tuple:
    """行內標記 → Run 序列；相鄰同樣式片段合併。"""
    runs: list = []

    def push(t: str, style) -> None:
        if not t:
            return
        if runs and runs[-1].char_style == style:
            runs[-1] = Run(runs[-1].text + t, style)
        else:
            runs.append(Run(t, style))

    for piece in _INLINE_RE.split(text):
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            push(piece[2:-2], inline_mapping.get("strong"))
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            push(piece[1:-1], inline_mapping.get("em"))
        else:
            push(piece, None)
    return tuple(runs) if runs else (Run(""),)


def blocks_from_markdown(text: str) -> list:
    """回傳 [(kind, text), ...]；kind ∈ h1..h6 | blockquote | paragraph。"""
    blocks: list = []
    para: list = []
    quote: list = []

    def close_para() -> None:
        nonlocal para
        if para:
            blocks.append(("paragraph", "".join(para)))
            para = []

    def close_quote() -> None:
        nonlocal quote
        if quote:
            blocks.append(("blockquote", "".join(quote)))
            quote = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            close_para()
            close_quote()
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            close_para()
            close_quote()
            blocks.append((f"h{len(heading.group(1))}", heading.group(2).strip()))
            continue
        if line.startswith(">"):
            close_para()
            quote.append(line.lstrip(">").strip())
            continue
        close_quote()
        item = _LIST_RE.match(line)
        if item:
            close_para()
            blocks.append(("paragraph", item.group(1).strip()))
            continue
        para.append(line)
    close_para()
    close_quote()
    return blocks


def import_markdown(
    text: str,
    mapping: dict,
    inline_mapping: dict = None,
    title: str = "",
    template_id: str = "neizai-zhengli",
    master: str = "A-內文版",
) -> Document:
    """mapping：模版 md_mapping（kind → 段落樣式名），缺層級退回 paragraph 樣式；
    inline_mapping：模版 md_inline_mapping（strong／em → 字元樣式名）。"""
    if "paragraph" not in mapping:
        raise ValueError("md_mapping 需含 paragraph 對映（預設內文樣式）")
    default = mapping["paragraph"]
    inline = inline_mapping or {}
    paragraphs = tuple(
        Paragraph(style=mapping.get(kind, default), runs=inline_runs(t, inline))
        for kind, t in blocks_from_markdown(text)
    )
    return Document(
        title=title,
        template=template_id,
        master=master,
        paragraphs=paragraphs,
    )


def import_markdown_file(path, mapping: dict, **kwargs) -> Document:
    from pathlib import Path

    path = Path(path)
    kwargs.setdefault("title", path.stem)
    return import_markdown(path.read_text(encoding="utf-8"), mapping, **kwargs)
