"""docx 匯入（PLAN §4.4 設計修正 1）：OOXML 標題層級由結構直接對映樣式，不經 AI。

解析走 stdlib（zipfile＋ElementTree），零新依賴、不依賴 Word COM。
標題偵測三層鏈（Spike 11 一手實證）：段落直掛 pPr/outlineLvl →
pStyle 樣式鏈（含 basedOn 遞迴）outlineLvl → 樣式名（heading N／標題 N）。
outlineLvl 有效層級 0〜8；9＝正文（TOC Heading 實測值），鏈上首見即定不再上溯。
引文＝樣式名或 styleId 含 quote／引文。粗體 → strong、斜體 → em、
粗斜並用 → strong（md v1 不嵌套同構）；對映復用模版 md_mapping／md_inline_mapping。
v1 不處理：表格、圖片、註腳、追蹤修訂、段內強制換行（w:br）、tab。
"""
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .document import Document, Paragraph, Run

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING_NAME_RE = re.compile(r"^(?:heading|標題)\s*([1-9])$", re.IGNORECASE)
_QUOTE_NAME_RE = re.compile(r"quote|引文", re.IGNORECASE)


def _flag_on(rpr, tag: str) -> bool:
    """rPr 布林屬性：存在即真，w:val 為 0/false/none 時關閉（Spike 11）。"""
    el = rpr.find(f"{_W}{tag}") if rpr is not None else None
    if el is None:
        return False
    return el.get(f"{_W}val") not in ("0", "false", "none")


def _styles_table(zf: zipfile.ZipFile) -> dict:
    """word/styles.xml → {styleId: (名稱, outlineLvl 或 None, basedOn)}；缺檔回空表。"""
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except KeyError:
        return {}
    table = {}
    for st in root.iter(f"{_W}style"):
        sid = st.get(f"{_W}styleId")
        if not sid:
            continue
        name_el = st.find(f"{_W}name")
        name = name_el.get(f"{_W}val") if name_el is not None else ""
        lvl = None
        ppr = st.find(f"{_W}pPr")
        if ppr is not None:
            lvl_el = ppr.find(f"{_W}outlineLvl")
            if lvl_el is not None and (lvl_el.get(f"{_W}val") or "").isdigit():
                lvl = int(lvl_el.get(f"{_W}val"))
        based = st.find(f"{_W}basedOn")
        table[sid] = (name or "", lvl, based.get(f"{_W}val") if based is not None else None)
    return table


def _chain_outline_level(style_id, styles: dict):
    """沿 basedOn 鏈找首個 outlineLvl（首見即定；循環守門）。"""
    seen = set()
    sid = style_id
    while sid and sid in styles and sid not in seen:
        seen.add(sid)
        name, lvl, based = styles[sid]
        if lvl is not None:
            return lvl
        sid = based
    return None


def _paragraph_kind(pstyle, direct_lvl, styles: dict) -> str:
    """kind ∈ h1..h9 | blockquote | paragraph（層級 0〜8 有效，9＝正文）。"""
    lvl = direct_lvl
    if lvl is None:
        lvl = _chain_outline_level(pstyle, styles)
    if lvl is not None and 0 <= lvl <= 8:
        return f"h{lvl + 1}"
    if lvl is None and pstyle:
        name = styles.get(pstyle, ("", None, None))[0]
        for candidate in (name, pstyle):
            m = _HEADING_NAME_RE.match(candidate.strip())
            if m:
                return f"h{m.group(1)}"
        if _QUOTE_NAME_RE.search(name) or _QUOTE_NAME_RE.search(pstyle):
            return "blockquote"
    return "paragraph"


def paragraphs_from_docx(path) -> list:
    """回傳 [(kind, ((text, bold, italic), ...)), ...]；空段跳過。"""
    path = Path(path)
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"不是有效的 docx（zip）檔：{path}（{exc}）") from None
    with zf:
        try:
            body_xml = zf.read("word/document.xml")
        except KeyError:
            raise ValueError(f"docx 內缺 word/document.xml：{path}") from None
        styles = _styles_table(zf)
    body = ET.fromstring(body_xml).find(f"{_W}body")
    if body is None:
        raise ValueError(f"docx 的 word/document.xml 缺 body：{path}")

    paragraphs = []
    for p in body.findall(f"{_W}p"):
        ppr = p.find(f"{_W}pPr")
        pstyle = None
        direct_lvl = None
        if ppr is not None:
            ps = ppr.find(f"{_W}pStyle")
            pstyle = ps.get(f"{_W}val") if ps is not None else None
            ol = ppr.find(f"{_W}outlineLvl")
            if ol is not None and (ol.get(f"{_W}val") or "").isdigit():
                direct_lvl = int(ol.get(f"{_W}val"))
        runs = []
        for r in p.iter(f"{_W}r"):  # iter 深走：hyperlink 內 run 不漏（Spike 11）
            text = "".join(t.text or "" for t in r.findall(f"{_W}t"))
            if not text:
                continue
            rpr = r.find(f"{_W}rPr")
            runs.append((text, _flag_on(rpr, "b"), _flag_on(rpr, "i")))
        if not runs:
            continue  # 空段（無文字）跳過，md blocks 同構
        paragraphs.append((_paragraph_kind(pstyle, direct_lvl, styles), tuple(runs)))
    return paragraphs


def _model_runs(raw_runs, inline_mapping: dict) -> tuple:
    """(text, bold, italic) → Run 序列；粗→strong、斜→em、並用→strong；相鄰同樣式合併。"""
    runs: list = []
    for text, bold, italic in raw_runs:
        key = "strong" if bold else ("em" if italic else None)
        style = inline_mapping.get(key) if key else None
        if runs and runs[-1].char_style == style:
            runs[-1] = Run(runs[-1].text + text, style)
        else:
            runs.append(Run(text, style))
    return tuple(runs)


def import_docx(
    path,
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
        Paragraph(style=mapping.get(kind, default), runs=_model_runs(raw, inline))
        for kind, raw in paragraphs_from_docx(path)
    )
    return Document(
        title=title or Path(path).stem,
        template=template_id,
        master=master,
        paragraphs=paragraphs,
    )
