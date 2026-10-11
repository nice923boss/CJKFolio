"""txt 匯入（PLAN §4.4）：按空行切段，先全掛預設樣式（v1 為「內文」）。

CJK 段內換行併接不加空白；AI 輔助樣式指派是 Phase 3 範圍，此處不涉。
"""
from pathlib import Path

from .document import Document, Paragraph

DEFAULT_BODY_STYLE = "內文-明體直排"


def paragraphs_from_text(text: str) -> list:
    """空行切段；段內各行 strip 後直接併接（CJK 不加空白）。"""
    blocks: list = []
    cur: list = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line:
            cur.append(line)
        elif cur:
            blocks.append("".join(cur))
            cur = []
    if cur:
        blocks.append("".join(cur))
    return blocks


def import_txt(
    text: str,
    default_style: str = DEFAULT_BODY_STYLE,
    title: str = "",
    template_id: str = "neizai-zhengli",
    master: str = "A-內文版",
) -> Document:
    paragraphs = tuple(
        Paragraph(t, default_style) for t in paragraphs_from_text(text)
    )
    return Document(
        title=title,
        template=template_id,
        master=master,
        paragraphs=paragraphs,
    )


def import_txt_file(path, **kwargs) -> Document:
    path = Path(path)
    kwargs.setdefault("title", path.stem)
    return import_txt(path.read_text(encoding="utf-8-sig"), **kwargs)
