"""封面建立（Sprint 132）：把一份文件變成「首頁為封面」的文件。

Owner 真視窗回饋：匯入稿件後封面的位置直接就是第一頁，書該有封面可放圖片與
自加文字，且頁碼自封面翻開後才算第一頁。

分層：封面**頁**由 layout 依 Document.cover 插入（版面頁 1，不吃內文流）、封面
**頁碼語意**由 primitives.book_number_for 位移，本模組只負責「建立封面時的預設
內容與既有自由佈局項的頁號位移」這一件編輯層的事。

封面內容不新增機制：書名走既有 TextFrame（直排文字框）、圖片走既有 PlacedImage
（rect 圖框），使用者之後可在編輯器自由拖放、增刪。預設書名框的幾何一律由主版
margins 與樣式級數推導（§4.4 分工鐵律：幾何屬引擎），不硬編座標。
"""
from dataclasses import replace

from .document import Document, TextFrame
from .frames import frame_pitch_pt
from .layout import style_advance_pt
from .primitives import PT_PER_MM

# 預設書名框佔頁高的比例（自擬版面設計，非量測）：自天頭起向下 62%，
# 直排書名自上而下書寫，留下方 38% 給作者與出版社等後續自加文字。
_TITLE_BLOCK_RATIO = 0.62
_TITLE_COLUMNS = 2  # 書名框寬＝2 欄（長書名可折欄，不必逐字改框）


def default_title_frame(template, cover_master: str, title: str,
                        style: str = "") -> TextFrame:
    """預設封面書名框（版面頁 1）：靠書口側、自天頭起的直排 2 欄框。

    幾何確定性推導：書口側緣＝頁寬−outer（封面書頁號 0＝偶數＝右頁，書口在右，
    見 primitives.is_right_page）；框寬＝2 欄（欄距依書名樣式級數換算）；
    框高＝頁高×0.62 自天頭起。style 省略時取模版宣告的封面書名樣式。
    """
    master = template.masters[cover_master]
    style = style or cover_title_style(template)
    st = template.paragraph_styles[style]
    pitch = frame_pitch_pt(st, master.grid)
    page_w = template.page_width_mm * PT_PER_MM
    page_h = template.page_height_mm * PT_PER_MM
    x1 = page_w - master.margins.outer_mm * PT_PER_MM
    y0 = master.margins.top_mm * PT_PER_MM
    return TextFrame(
        text=title,
        style=style,
        page=1,
        rect=(x1 - _TITLE_COLUMNS * pitch, y0, x1, y0 + page_h * _TITLE_BLOCK_RATIO),
    )


def cover_title_style(template) -> str:
    """模版宣告的封面書名樣式名（md_mapping["cover_title"]）。

    未宣告即快速失敗，不從字級猜「最大的那個大概是書名樣式」：樣式語意屬模版
    作者（§4.4 分工鐵律），猜錯的代價是封面用錯字形而使用者無從得知。
    """
    declared = template.md_mapping.get("cover_title")
    if not declared:
        raise KeyError(
            "模版 md_mapping 未宣告 cover_title（封面書名樣式），無法建立封面書名框")
    if declared not in template.paragraph_styles:
        raise KeyError(
            f"模版 md_mapping.cover_title 指向不存在的段落樣式：{declared}")
    return declared


def title_fits(template, cover_master: str, title: str, style: str = "") -> bool:
    """預設書名框是否容得下 title（用於呼叫端在建封面前先判定，不沉默溢出）。

    容量＝每欄字數×欄數；框內斷行與禁則由 frames 層負責，此處只做粗容量判定
    （字數為上界：標點與縱中橫可能佔不同槽寬，故通過此判定仍可能有框內違規，
    最終以 frames.layout_text_frame 的 violations 為準）。
    """
    master = template.masters[cover_master]
    style = style or cover_title_style(template)
    st = template.paragraph_styles[style]
    frame = default_title_frame(template, cover_master, title, style)
    _x0, y0, _x1, y1 = frame.rect
    per_column = int((y1 - y0) / style_advance_pt(st, master.grid))
    return len(title) <= per_column * _TITLE_COLUMNS


def with_cover(doc: Document, template, cover_master: str = "",
               title: str = "") -> Document:
    """回傳「首頁為封面」的新文件（不可變：原文件不動）。

    做三件事，缺一即為使用者可見的錯：
      1. 標記 cover 主版名（layout 據此插封面頁、頁碼據此位移）。
      2. 既有 images／text_frames 的 page 全部 +1：其 page 是版面頁號，封面插在
         最前會使原本的頁 N 變成頁 N+1，不位移即為靜默錯位。
      3. 加一個預設書名文字框（title 省略時取 doc.title）；書名為空則不加框
         （空框無意義），封面留白由使用者自行置圖與加字。

    cover_master 省略時取 template.default_cover；模版未宣告即快速失敗
    （不猜主版名，同 import_core._import_defaults 的分層理由）。
    已帶封面的文件再套用即為重複建封面，快速失敗而非疊加第二層。
    """
    if doc.cover is not None:
        raise ValueError(f"文件已有封面（主版「{doc.cover}」），不重複建立")
    cover_master = cover_master or template.default_cover
    if not cover_master:
        raise ValueError(
            "模版未宣告 default_cover，無法決定封面主版"
            f"（模版可選主版：{'、'.join(sorted(template.masters))}）")
    if cover_master not in template.masters:
        raise ValueError(
            f"封面主版「{cover_master}」不存在於模版主版清單"
            f"（可選：{'、'.join(sorted(template.masters))}）")
    title = title or doc.title
    frames = tuple(replace(f, page=f.page + 1) for f in doc.text_frames)
    images = tuple(replace(im, page=im.page + 1) for im in doc.images)
    if title:
        frames = (default_title_frame(template, cover_master, title),) + frames
    return replace(doc, cover=cover_master, text_frames=frames, images=images)


def without_cover(doc: Document) -> Document:
    """回傳「移除封面」的新文件：封面頁的自由佈局項一併移除，其餘頁號回退 1。

    封面頁上的圖與文字框屬封面設計，移除封面即失去落點（版面頁 1 變回內文首頁），
    故一併移除而非往後擠到內文首頁上（那是靜默污染內文）。
    """
    if doc.cover is None:
        raise ValueError("文件無封面，無可移除")
    return replace(
        doc,
        cover=None,
        text_frames=tuple(replace(f, page=f.page - 1)
                          for f in doc.text_frames if f.page > 1),
        images=tuple(replace(im, page=im.page - 1)
                     for im in doc.images if im.page > 1),
    )
