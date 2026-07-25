"""文字框的框級編輯純函式（Sprint 136）：整框的新增、平移、縮放、移除。

與 frame_editing.py 的分工：那邊管「框**內**的字」（插刪字元），本模組管「框
**本身**」。兩者合起來才是完整的文字框編輯：使用者在封面刪到只剩最後一字時撞見的
`text_frames[0] 不可刪空` 是 document@2 的「框 text 非空」不變式，它的出路是移除
整個框而不是留一個空殼框，故整框移除正是那條不變式的配套能力。缺它，封面書名框
就是刪不掉也搬不動的死結（Owner 真視窗回饋）。

Qt 無關（同 image_editing.py 的判定層與呈現層分工紀律）：座標一律 trim 空間 pt、
top-down，與 TextFrame.rect 同一事實來源；命中判定、四角控制點與拖角縮放的幾何
直接復用 image_editing 的純矩形數學（與影像語意無關），不另立第二套。

新框幾何一律由樣式級數與主版網格推導（§4.4 分工鐵律：幾何屬引擎），不硬編座標，
同 cover.default_title_frame 的作法。

串接鏈（thread）：移除鏈首時把 text 交給鏈中下一框（該框隨即成為新鏈首）。續框
自身不帶 text，鏈首一走文字即無處可掛，靜默丟字或留下違反 schema 的空鏈首都是
使用者看不見的損壞，故明確承接。
"""
import math
from dataclasses import replace

from .document import Document, TextFrame
from .frames import frame_pitch_pt
from .image_editing import normalize_rect
from .layout import style_advance_pt
from .primitives import PT_PER_MM

#: 新框預設佔頁高的比例上限（自擬版面預設，非量測）：留天地邊不貼滿整頁，
#: 使用者拖角改大小即可。字多到單欄放不下時往左加欄，不把框撐出頁面。
DEFAULT_FRAME_HEIGHT_RATIO = 0.6


def _frame(doc: Document, idx: int) -> TextFrame:
    """取第 idx 個文字框；越界快速失敗（系統邊界，訊息含實際框數）。"""
    if not 0 <= idx < len(doc.text_frames):
        raise ValueError(f"文字框索引 {idx} 越界（共 {len(doc.text_frames)} 框）")
    return doc.text_frames[idx]


def default_frame_rect(template, master, text: str, style: str,
                       cx_pt: float, cy_pt: float) -> tuple:
    """新框預設幾何：以 (cx_pt, cy_pt) 為中心、剛好容得下 text 的直排框。

    欄距與字距取該樣式在該主版網格下的實效值（frame_pitch_pt／style_advance_pt，
    與 frames 佈局同源），故「預設框剛好放得下預設文字」不是巧合而是同一組公式
    算出來的。單欄放不下時增欄（直排往左長），欄高上限＝頁高×0.6。
    空 text 不成框（document@2 要求框 text 非空），快速失敗。
    """
    if not text:
        raise ValueError("新文字框需有文字（document@2 要求框 text 非空）")
    st = template.paragraph_styles[style]
    pitch = frame_pitch_pt(st, master.grid)
    advance = style_advance_pt(st, master.grid)
    page_h = template.page_height_mm * PT_PER_MM
    per_column = max(1, int(page_h * DEFAULT_FRAME_HEIGHT_RATIO / advance))
    columns = max(1, math.ceil(len(text) / per_column))
    w = columns * pitch
    h = min(len(text), per_column) * advance
    return (cx_pt - w / 2, cy_pt - h / 2, cx_pt + w / 2, cy_pt + h / 2)


def add_text_frame(doc: Document, template, text: str, style: str, page: int,
                   rect) -> Document:
    """追加一個獨立文字框到文件末（文件序＝繪製序，後置者疊在上）。

    style 需存在於模版：不存在的樣式要到渲染時才炸，那時使用者已看不出是這一步
    造成的，故在此快速失敗（同 frames._frame_style 的守門語意，只是提早）。
    新框不入串接鏈（thread=None）：拉線串框屬真視窗 UI，見 GAPS #32 (a)。
    """
    if not text:
        raise ValueError("新文字框需有文字（document@2 要求框 text 非空）")
    if style not in template.paragraph_styles:
        raise ValueError(
            f"文字框樣式「{style}」不存在於模版"
            f"（可選：{'、'.join(sorted(template.paragraph_styles))}）")
    if page < 1:
        raise ValueError(f"文字框頁碼須自 1 起算，得到 {page}")
    frame = TextFrame(text=text, style=style, page=page,
                      rect=normalize_rect(rect, label="文字框"))
    return replace(doc, text_frames=doc.text_frames + (frame,))


def move_text_frame(doc: Document, idx: int, dx_pt: float, dy_pt: float) -> Document:
    """平移第 idx 個文字框（text／style／thread 等其餘欄位原樣保留）。"""
    x0, y0, x1, y1 = _frame(doc, idx).rect
    moved = replace(doc.text_frames[idx],
                    rect=(x0 + dx_pt, y0 + dy_pt, x1 + dx_pt, y1 + dy_pt))
    return replace(doc, text_frames=(doc.text_frames[:idx] + (moved,)
                                     + doc.text_frames[idx + 1:]))


def resize_text_frame(doc: Document, idx: int, rect) -> Document:
    """換掉第 idx 個文字框的矩形（拖角縮放的落地；新框正規化後寫入）。

    框變小到容不下文字時由 frames.layout_text_frame 記溢出違規（既有行為，
    不沉默），本層不擋：使用者可能先縮框再刪字，中途狀態不該被拒。
    """
    _frame(doc, idx)
    sized = replace(doc.text_frames[idx], rect=normalize_rect(rect, label="文字框"))
    return replace(doc, text_frames=(doc.text_frames[:idx] + (sized,)
                                     + doc.text_frames[idx + 1:]))


def remove_text_frame(doc: Document, idx: int) -> Document:
    """移除第 idx 個文字框；被移除者為串接鏈首時把文字交給鏈中下一框。

    續框自身不帶 text（文字掛鏈首，document@2 解析層守門），鏈首一走，文字若不
    承接就整段消失、且留下的續框成為無 text 的鏈首＝存檔後讀不回來。故承接是
    正確性要求，不是貼心功能。鏈中已無他框時即整鏈移除，文字隨框一併消失
    （使用者要的就是刪掉這段文字，Ctrl+Z 一步回原）。
    """
    removed = _frame(doc, idx)
    rest = list(doc.text_frames[:idx] + doc.text_frames[idx + 1:])
    if removed.thread and removed.text:  # 非空 text＝鏈首（續框恆為空）
        for j, tf in enumerate(rest):
            if tf.thread == removed.thread:
                rest[j] = replace(tf, text=removed.text)
                break
    return replace(doc, text_frames=tuple(rest))


def text_frame_at_point(doc: Document, page: int, x_pt: float, y_pt: float):
    """該頁最上層命中的文字框索引；無命中回 None。

    文件序＝繪製序（同 images），故反序尋找＝上層優先，與畫面所見一致。
    """
    for idx in range(len(doc.text_frames) - 1, -1, -1):
        tf = doc.text_frames[idx]
        if tf.page != page:
            continue
        x0, y0, x1, y1 = tf.rect
        if x0 <= x_pt <= x1 and y0 <= y_pt <= y1:
            return idx
    return None
