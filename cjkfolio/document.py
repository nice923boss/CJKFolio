"""文件模型：段落＋樣式參照的最小 JSON schema（cjkfolio/document@2）。

語意化內容與樣式分離（PLAN §5.1 文件模型層）：段落記段落樣式名與 run 序列
（run＝連續文字＋選配字元樣式，PLAN §4.1 字元樣式層），幾何一律由樣式層＋
引擎推導。系統邊界（檔案載入）做 schema 驗證，快速失敗。

相容性：@1（純 text 段落）照載；@2 段落可用 text 捷徑或 runs 陣列。
save 一律寫 @2；單一無字元樣式 run 以 text 捷徑序列化（可讀性）。
圖片置入（images，@2 相容擴充選配欄位，同 page_no 慣例）：置入主版 figure
保留區的照片清單（PLAN §4.2 G 圖文版、§9 灰階單 K 或彩色 CMYK）。
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SCHEMA_ID = "cjkfolio/document@2"
SCHEMA_V1 = "cjkfolio/document@1"


class DocumentError(ValueError):
    """文件 JSON 不合 schema。"""


@dataclass(frozen=True)
class Run:
    text: str
    char_style: Optional[str] = None
    ruby: Optional[str] = None  # 注音／ruby 標注（Sprint 86，@2 相容擴充）：非空字串，
    # 且 base text 須恰為單一字（v1 mono-ruby，注音典型形態）；直排繪於字右側置中。


@dataclass(frozen=True)
class Paragraph:
    """不變式：text ＝ 全段字面 ＝ runs 文字串接（__post_init__ 正規化）。

    page_no：目錄條目頁碼（選配，僅數字字串；@2 相容擴充，無欄位照載）。
    master：節首標記（選配，@2 相容擴充）：自本段起新頁並改用該主版
    （節式主版指派，Sprint 51）；同名主版亦強制分頁。None＝承前節。
    toc_title：章內小節列入自動目錄的顯示標題（選配，@2 相容擴充，Sprint 108）。
    標題語意屬使用者（§4.4 分工鐵律）故一律顯式宣告，引擎不從樣式名或字級反推。
    toc_level：該條目的目錄層級（選配，≥1；None＝承所屬章層級 +1）；須搭 toc_title。
    """
    text: str = ""
    style: str = ""
    runs: tuple = ()
    page_no: Optional[str] = None
    master: Optional[str] = None
    toc_title: Optional[str] = None
    toc_level: Optional[int] = None

    def __post_init__(self):
        if self.runs:
            object.__setattr__(self, "text", "".join(r.text for r in self.runs))
        else:
            object.__setattr__(self, "runs", (Run(self.text),))


@dataclass(frozen=True)
class TextFrame:
    """獨立文字框（Sprint 55 建立＋Sprint 57 串接）：任意矩形內的直排文字。

    rect＝(x0, y0, x1, y1) trim 空間 pt、top-down（同 PlacedImage.rect 座標系，
    可溢出版心＝自由佈局層正當用法）；page＝版面頁號（1 起算，須落於流排頁）。
    thread（選配）＝串接鏈名：同 thread 的框依文件序成鏈跨框續排；文字掛鏈首
    （續框 text 為空、style 與鏈首一致，解析層守門）。
    圖說自由位置、署名字卡等「自由手排」項的機制載體。
    """
    text: str
    style: str
    page: int
    rect: tuple
    thread: Optional[str] = None


@dataclass(frozen=True)
class PlacedImage:
    """置入一張圖到某版面頁（PLAN §4.2 G 圖文版照片、§9 灰階單 K 或彩色 CMYK）。

    path：圖檔路徑（相對路徑於 render／export 時相對文件目錄解析）；
    page：版面頁號（1 起算，與 --page 選頁鍵、檔名同鍵，Sprint 12 決議）；
    rect：任意圖框（Sprint 54，選配）＝(x0, y0, x1, y1) trim 空間 pt、top-down；
    None＝置入主版 figure 保留區（槽式，每頁一張）。rect 圖每頁多張、可溢出
    版心（真書照片略溢 1〜4pt 特徵與出血照片皆正當用法，不做邊界快速失敗）。
    圖在框內 contain 等比置中（primitives.fit_image_rect）。

    wrap：圖文繞排（Sprint 89，選配，預設 False＝既有行為圖疊於文上）。True 時
    圖框成為排除區，受影響行槽的內文避開圖的字軸範圍（真書 179 頁全掃形態）；
    限 rect 圖框（槽式無座標）。wrap_margin_mm＝圖框四周額外留白（真書圖文間隙
    1〜3 字格為作者自由放置，本產品由此欄位表達不硬編）。
    """
    path: str
    page: int
    rect: Optional[tuple] = None
    wrap: bool = False
    wrap_margin_mm: float = 0.0


def _runs_from_list(raw, idx: int) -> tuple:
    runs = []
    for j, r in enumerate(raw):
        if not isinstance(r, dict) or not isinstance(r.get("text"), str):
            raise DocumentError(f"paragraphs[{idx}].runs[{j}] 需含 text 字串")
        char_style = r.get("char_style")
        if char_style is not None and (not isinstance(char_style, str) or not char_style):
            raise DocumentError(f"paragraphs[{idx}].runs[{j}] char_style 需為非空字串")
        ruby = r.get("ruby")
        if ruby is not None:
            if not isinstance(ruby, str) or not ruby:
                raise DocumentError(f"paragraphs[{idx}].runs[{j}] ruby 需為非空字串")
            if len(r["text"]) != 1:
                raise DocumentError(
                    f"paragraphs[{idx}].runs[{j}] 帶 ruby 的 run base text 須恰為單一字"
                    f"（v1 mono-ruby），得到 {r['text']!r}"
                )
        runs.append(Run(r["text"], char_style, ruby))
    if not runs:
        raise DocumentError(f"paragraphs[{idx}].runs 不得為空陣列")
    return tuple(runs)


def _rect_from_value(raw, ctx: str) -> tuple:
    """解析 rect：4 個數字 [x0, y0, x1, y1]（trim pt、top-down）且 x0 < x1、
    y0 < y1；形狀不合快速失敗。ctx＝錯誤訊息用的欄位標籤。"""
    ok = (isinstance(raw, list) and len(raw) == 4
          and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw))
    if ok:
        x0, y0, x1, y1 = (float(v) for v in raw)
        ok = x0 < x1 and y0 < y1
    if not ok:
        raise DocumentError(
            f"{ctx} rect 需為 [x0, y0, x1, y1] 四數字（pt）且 x0<x1、y0<y1，"
            f"得到 {raw!r}"
        )
    return (x0, y0, x1, y1)


def _images_from_list(raw) -> tuple:
    """解析 images 陣列（選配）。每項須含非空 path 與 ≥1 整數 page；選配 rect
    （任意圖框，每頁多張）；無 rect＝槽式（figure 保留區），槽式每頁僅一張。
    選配 wrap（bool，繞排）須搭 rect；wrap_margin_mm 須 ≥0。"""
    images = []
    slot_pages = set()
    for j, im in enumerate(raw):
        if not isinstance(im, dict):
            raise DocumentError(f"images[{j}] 須為物件")
        path = im.get("path")
        if not (isinstance(path, str) and path):
            raise DocumentError(f"images[{j}] 需含非空 path 字串")
        page = im.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise DocumentError(f"images[{j}] page 需為 ≥1 的整數，得到 {page!r}")
        rect = None
        if im.get("rect") is not None:
            rect = _rect_from_value(im["rect"], f"images[{j}]")
        else:
            if page in slot_pages:
                raise DocumentError(
                    f"images[{j}] page {page} 已有槽式置入圖（figure 保留區每頁一張；"
                    "多圖請用 rect 任意圖框）"
                )
            slot_pages.add(page)
        wrap = im.get("wrap", False)
        if not isinstance(wrap, bool):
            raise DocumentError(f"images[{j}] wrap 需為布林值，得到 {wrap!r}")
        if wrap and rect is None:
            raise DocumentError(
                f"images[{j}] wrap 需搭 rect 圖框（槽式 figure 保留區無座標，v1 不繞排）"
            )
        margin = im.get("wrap_margin_mm", 0.0)
        if (isinstance(margin, bool) or not isinstance(margin, (int, float))
                or margin < 0):
            raise DocumentError(
                f"images[{j}] wrap_margin_mm 需為 ≥0 的數字，得到 {margin!r}"
            )
        images.append(PlacedImage(path=path, page=page, rect=rect, wrap=wrap,
                                  wrap_margin_mm=float(margin)))
    return tuple(images)


def _frames_from_list(raw) -> tuple:
    """解析 text_frames 陣列（選配，Sprint 55）：style 非空字串、page ≥1 整數、
    rect 必填（任意矩形文字框）；不合 schema 快速失敗。
    thread 串接鏈（Sprint 57）：同 thread 依文件序成鏈，文字掛鏈首（text 非空）、
    續框不得帶 text（雙源）且 style 須與鏈首一致。"""
    frames = []
    chain_heads: dict = {}  # thread → 鏈首 style
    for j, f in enumerate(raw):
        if not isinstance(f, dict):
            raise DocumentError(f"text_frames[{j}] 須為物件")
        thread = f.get("thread")
        if thread is not None and (not isinstance(thread, str) or not thread):
            raise DocumentError(f"text_frames[{j}] thread 需為非空字串")
        style = f.get("style")
        if not (isinstance(style, str) and style):
            raise DocumentError(f"text_frames[{j}] 需含非空 style 字串")
        text = f.get("text", "")
        if not isinstance(text, str):
            raise DocumentError(f"text_frames[{j}] text 需為字串")
        if thread is not None and thread in chain_heads:  # 串接續框
            if text:
                raise DocumentError(
                    f"text_frames[{j}] 串接續框不得帶 text"
                    f"（文字掛鏈首，thread「{thread}」）"
                )
            if style != chain_heads[thread]:
                raise DocumentError(
                    f"text_frames[{j}] 串接續框 style 須與鏈首一致"
                    f"（thread「{thread}」鏈首為「{chain_heads[thread]}」）"
                )
        else:  # 獨立框或鏈首
            if not text:
                raise DocumentError(f"text_frames[{j}] 需含非空 text 字串")
            if thread is not None:
                chain_heads[thread] = style
        page = f.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise DocumentError(f"text_frames[{j}] page 需為 ≥1 的整數，得到 {page!r}")
        if f.get("rect") is None:
            raise DocumentError(f"text_frames[{j}] 需含 rect（任意矩形文字框必填）")
        rect = _rect_from_value(f["rect"], f"text_frames[{j}]")
        frames.append(TextFrame(text=text, style=style, page=page, rect=rect,
                                thread=thread))
    return tuple(frames)


def _paragraph_toc_from_dict(p: dict, i: int, schema: str):
    """解析段落的目錄宣告（Sprint 108）：回傳 (toc_title, toc_level)。

    toc_level 不得單獨出現：沒有 toc_title 就不會列入目錄，單給層級是無效宣告，
    快速失敗而非默默忽略。
    """
    toc_title = p.get("toc_title")
    toc_level = p.get("toc_level")
    if toc_title is None and toc_level is None:
        return None, None
    if schema == SCHEMA_V1:
        raise DocumentError(f"paragraphs[{i}] 使用 toc_title 需 schema document@2")
    if toc_title is None:
        raise DocumentError(
            f"paragraphs[{i}] toc_level 需搭 toc_title（無標題即不列入目錄）")
    if not (isinstance(toc_title, str) and toc_title):
        raise DocumentError(
            f"paragraphs[{i}] toc_title 需為非空字串，得到 {toc_title!r}")
    if toc_level is not None and (isinstance(toc_level, bool)
                                  or not isinstance(toc_level, int) or toc_level < 1):
        raise DocumentError(
            f"paragraphs[{i}] toc_level 需為 ≥1 的整數，得到 {toc_level!r}")
    return toc_title, toc_level


def document_from_dict(data) -> "Document":
    if not isinstance(data, dict):
        raise DocumentError("文件必須是 JSON 物件")
    schema = data.get("schema")
    if schema not in (SCHEMA_ID, SCHEMA_V1):
        raise DocumentError(f"schema 不符：需要 {SCHEMA_ID}（或相容 {SCHEMA_V1}），得到 {schema!r}")
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise DocumentError("meta 必須是物件")
    raw = data.get("paragraphs")
    if not isinstance(raw, list):
        raise DocumentError("paragraphs 必須是陣列")
    paragraphs = []
    for i, p in enumerate(raw):
        if not isinstance(p, dict) or not isinstance(p.get("style"), str) or not p["style"]:
            raise DocumentError(f"paragraphs[{i}] 需含非空 style 字串")
        page_no = p.get("page_no")
        if page_no is not None and not (isinstance(page_no, str) and page_no.isdigit()):
            raise DocumentError(f"paragraphs[{i}] page_no 需為數字字串，得到 {page_no!r}")
        master = p.get("master")
        if master is not None:
            if schema == SCHEMA_V1:
                raise DocumentError(f"paragraphs[{i}] 使用 master 需 schema document@2")
            if not (isinstance(master, str) and master):
                raise DocumentError(f"paragraphs[{i}] master 需為非空字串，得到 {master!r}")
        toc_title, toc_level = _paragraph_toc_from_dict(p, i, schema)
        if "runs" in p:
            if schema == SCHEMA_V1:
                raise DocumentError(f"paragraphs[{i}] 使用 runs 需 schema document@2")
            paragraphs.append(Paragraph(style=p["style"], runs=_runs_from_list(p["runs"], i),
                                        page_no=page_no, master=master,
                                        toc_title=toc_title, toc_level=toc_level))
        elif isinstance(p.get("text"), str):
            paragraphs.append(Paragraph(p["text"], p["style"], page_no=page_no, master=master,
                                        toc_title=toc_title, toc_level=toc_level))
        else:
            raise DocumentError(f"paragraphs[{i}] 需含 text 字串或 runs 陣列")
    raw_images = data.get("images", [])
    if not isinstance(raw_images, list):
        raise DocumentError("images 必須是陣列")
    raw_frames = data.get("text_frames", [])
    if raw_frames and schema == SCHEMA_V1:
        raise DocumentError("使用 text_frames 需 schema document@2")
    if not isinstance(raw_frames, list):
        raise DocumentError("text_frames 必須是陣列")
    return Document(
        title=str(meta.get("title", "")),
        template=str(meta.get("template", "")),
        master=str(meta.get("master", "A-內文版")),
        paragraphs=tuple(paragraphs),
        language=str(meta.get("language", "zh-TW")),
        images=_images_from_list(raw_images),
        text_frames=_frames_from_list(raw_frames),
    )


@dataclass(frozen=True)
class Document:
    title: str
    template: str  # 模版 id（檔名 stem）
    master: str    # 首節預設主版名（段落 master 節首標記起新節，Sprint 51）
    paragraphs: tuple
    language: str = "zh-TW"
    images: tuple = ()  # PlacedImage 序列（@2 相容擴充；槽式與 rect 任意圖框）
    text_frames: tuple = ()  # TextFrame 序列（@2 相容擴充；獨立文字框，Sprint 55）


def _paragraph_to_dict(p: Paragraph) -> dict:
    if len(p.runs) == 1 and p.runs[0].char_style is None and p.runs[0].ruby is None:
        out = {"text": p.text, "style": p.style}
    else:
        runs = [
            {"text": r.text,
             **({"char_style": r.char_style} if r.char_style else {}),
             **({"ruby": r.ruby} if r.ruby else {})}
            for r in p.runs
        ]
        out = {"style": p.style, "runs": runs}
    if p.page_no is not None:
        out["page_no"] = p.page_no
    if p.master is not None:
        out["master"] = p.master
    if p.toc_title is not None:
        out["toc_title"] = p.toc_title
    if p.toc_level is not None:
        out["toc_level"] = p.toc_level
    return out


def document_to_dict(doc: Document) -> dict:
    out = {
        "schema": SCHEMA_ID,
        "meta": {
            "title": doc.title,
            "template": doc.template,
            "master": doc.master,
            "language": doc.language,
        },
        "paragraphs": [_paragraph_to_dict(p) for p in doc.paragraphs],
    }
    if doc.images:
        out["images"] = [
            {"path": im.path, "page": im.page,
             **({"rect": list(im.rect)} if im.rect is not None else {}),
             **({"wrap": True} if im.wrap else {}),
             **({"wrap_margin_mm": im.wrap_margin_mm} if im.wrap_margin_mm else {})}
            for im in doc.images
        ]
    if doc.text_frames:
        out["text_frames"] = [
            {**({"text": tf.text} if tf.text else {}),  # 串接續框 text 為空不寫
             "style": tf.style, "page": tf.page, "rect": list(tf.rect),
             **({"thread": tf.thread} if tf.thread is not None else {})}
            for tf in doc.text_frames
        ]
    return out


def load_document(path) -> Document:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise DocumentError(f"讀取文件失敗 {path}：{e}") from e
    return document_from_dict(data)


def save_document(doc: Document, path) -> None:
    Path(path).write_text(
        json.dumps(document_to_dict(doc), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def unknown_style_refs(doc: Document, template) -> list:
    """回傳文件引用但模版沒有的段落樣式名（去重、保序）。"""
    unknown = []
    for p in doc.paragraphs:
        if p.style not in template.paragraph_styles and p.style not in unknown:
            unknown.append(p.style)
    return unknown


def unknown_char_style_refs(doc: Document, template) -> list:
    """回傳文件引用但模版沒有的字元樣式名（去重、保序）。"""
    unknown = []
    for p in doc.paragraphs:
        for r in p.runs:
            if r.char_style and r.char_style not in template.character_styles \
                    and r.char_style not in unknown:
                unknown.append(r.char_style)
    return unknown
