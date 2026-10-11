"""節與分頁編輯（純文件層）：指派節主版、搬移整節、依模版宣告自動起新頁。

「節」（section）＝ Paragraph.master 節首標記切出的段落區塊，切節規則的唯一實作在
layout._sections（本檔共用，不另寫一份）。節首恆起新頁（同名主版亦然），故本檔的
函式都是在動「哪裡換頁、換到哪個主版」這件事（Sprint 153 加刪頁）。

自 cjkfolio/editing.py 分出（Sprint 142，依行數紀律分檔，同 Sprint 67 把 EditSession
分到 session.py 的先例）。editing.py 仍再匯出這三個名字，既有 import 路徑不變。
"""
from collections import Counter
from dataclasses import replace
from typing import Optional

from .document import Document, Paragraph
from .frame_box_editing import remove_text_frame
# _sections＝切節規則的唯一實作（layout 與本檔共用；另寫一份遲早與版面層分歧）
from .layout import _sections
from .styles import Template


def set_section_master(
    document: Document, para_idx: int, master: Optional[str]
) -> Document:
    """指派第 para_idx 段起的節式主版，回傳新 Document（不可變）。

    節式主版模型（Sprint 51／52）：主版按「節」指派，非逐頁自由套。三種情形：

    - para_idx==0 且段 0 無自帶 master：改的是首節預設主版 doc.master（寫回
      meta.master），不設段落標記（首節主版存 doc.master，無節首標記可設）。
    - para_idx==0 且段 0 自帶 master（自蓋首節）：改段 0 的節首標記；清成 None
      即退回 doc.master 預設（有前設可承，不 raise）。
    - para_idx>0：設 Paragraph.master 節首標記＝自該段起新開一頁並切主版
      （None＝承前節，清標記併回前節）。同名亦強制分頁的語意由版面層處理，本
      函式只管文件模型。

    系統邊界快速失敗：para_idx 越界 raise IndexError；首節（段 0 無自帶 master）
    清成 None（無前節可承）raise ValueError。等值為 no-op 回原物件。主版名是否存
    在於模版不在此驗（純文件層），由 session 全文重排守門（raise KeyError，同
    change_paragraph_style 慣例）。
    """
    if not 0 <= para_idx < len(document.paragraphs):
        raise IndexError(
            f"para_idx {para_idx} 超出段落範圍 0..{len(document.paragraphs) - 1}"
        )
    para = document.paragraphs[para_idx]
    if para_idx == 0 and para.master is None:
        # 首節：主版存於 doc.master（無節首標記可設；清 None 無前節可承）
        if master is None:
            raise ValueError("首節主版不得清除（無前節可承）")
        if document.master == master:  # 主版無變化 no-op
            return document
        return replace(document, master=master)
    if para.master == master:  # 節首標記無變化 no-op
        return document
    new_para = replace(para, master=master)
    new_paras = (
        document.paragraphs[:para_idx]
        + (new_para,)
        + document.paragraphs[para_idx + 1 :]
    )
    return replace(document, paragraphs=new_paras)


def move_section(document: Document, src_index: int, dst_index: int) -> Document:
    """把第 src_index 節整段搬到第 dst_index 個插入位（節序，0-based），回傳新 Document。

    頁面拖曳重排的核心（Sprint 142）。本產品的頁面是「段落流排的結果」而非投影片
    那樣的獨立物件，故沒有「把版面頁 4 搬到版面頁 1」這個操作；可搬的最小完整單位
    是節（section＝Paragraph.master 節首標記切出的段落區塊，見 layout._sections）。
    節首恆起新頁，故搬節＝搬「自某頁起到下一節首前」的整塊內容，搬完全書重排。

    dst_index 是搬動前節序上的插入位（0＝搬到最前，len(sections)＝搬到最後），與一般
    清單拖放同語意：原位放下＝不動（回原物件，呼叫端不入 undo）。

    節首標記重寫（本函式的主要複雜度）：節式主版模型規定「首節主版存 doc.master、
    其餘節在首段帶 master 標記」，換序後誰是首節會變，故一律重寫：新首節清掉標記
    並把它的主版寫進 doc.master，其餘節在首段明寫自己的主版。如此來回搬兩次可還原
    原本的文件形狀（標記位置與 doc.master 都回到原值）。

    系統邊界快速失敗：節序越界 raise IndexError。單節文件恆為 no-op（無序可換）。
    """
    sections = _sections(document)
    n = len(sections)
    if not 0 <= src_index < n:
        raise IndexError(f"節序 {src_index} 超出範圍 0..{n - 1}")
    if not 0 <= dst_index <= n:
        raise IndexError(f"插入位 {dst_index} 超出範圍 0..{n}")
    order = list(range(n))
    order.insert(dst_index - (1 if dst_index > src_index else 0),
                 order.pop(src_index))
    if order == list(range(n)):  # 原位放下：no-op 回原物件（不入 undo）
        return document
    paras: list = []
    for pos, si in enumerate(order):
        master, lo, hi = sections[si]
        block = list(document.paragraphs[lo:hi])
        block[0] = replace(block[0], master=None if pos == 0 else master)
        paras.extend(block)
    return replace(document, paragraphs=tuple(paras),
                   master=sections[order[0]][0])


def apply_page_starts(doc: Document, template: Template) -> Document:
    """把「樣式宣告 starts_page」的段標成節首＝自該段起新頁（Sprint 141）。

    章名大標之類的章首樣式排在前一章的內文後面（截圖：頁 78「第八章｜完美謀殺」
    與內文同頁）不合書冊慣例。分頁在本專案只有一個機制：Paragraph.master 節首
    標記（同名主版亦強制分頁，見 layout._sections），故本函式把該段的 master 設成
    「該段所在節現行的主版名」＝換頁但不換主版。

    §4.4 分工鐵律：換不換頁是模版的宣告（ParagraphStyle.starts_page），不從樣式名
    或字級反推，也不由 AI 給數字。本函式只忠實執行模版宣告。

    只加不減：已自帶 master 的段（使用者手動指派的部扉、個案扉頁等節首）原樣不動；
    段 0 跳過（首節主版存 doc.master，段 0 補標記會多切一個空節）。樣式名不存在於
    模版時跳過該段（純文件層不驗樣式存在性，由 layout_with_wrap 守門，同
    change_paragraph_style 慣例）。無任何變更回原物件。

    反向清除（樣式改回內文後把自動加的節首收回）不做：文件模型沒有記錄「這個節首
    是自動加的還是使用者手動指派的」，清除會誤刪手動節首。見 GAPS #96。
    """
    paras = list(doc.paragraphs)
    current = doc.master  # 該段所在節現行的主版名（節首標記逐段更新）
    changed = False
    for idx, para in enumerate(paras):
        if para.master is not None:
            current = para.master
            continue  # 已是節首＝已換頁，不重複標記
        if idx == 0:
            continue  # 首節主版存 doc.master，無節首標記可設
        style = template.paragraph_styles.get(para.style)
        if style is None or not style.starts_page:
            continue
        paras[idx] = replace(para, master=current)
        changed = True
    return replace(doc, paragraphs=tuple(paras)) if changed else doc


def delete_page(document: Document, page: int, lo: int, hi: int) -> Document:
    """刪除版面頁 page：拿掉完整落在該頁的段 [lo, hi)，連同該頁的圖與文字框。

    頁面是流排結果，刪一頁＝刪掉排在那一頁的段落（Sprint 153，Owner：「這裡
    不需要再看到一次標題文字」）。呼叫端負責只交「乾淨頁」：首段不延續自前頁、
    末段不延續到下一頁，否則刪的就不是一整頁。裝訂補頁由版面層依 sheet_pages
    重算，本函式不碰（刪後總頁數自動湊回 4 的倍數）。

    節首標記轉移：被刪的段若含節首，其後第一段原本屬於那一節（節首起新頁、
    主版也是那一節的），刪後若不補標記就會併進前一節、黏在前一頁後面。故該段
    沒有自帶標記時補上被刪範圍內最後一個節首的主版。

    圖與文字框以頁號錨定：本頁的一併刪除（文字框走 remove_text_frame，串接鏈首
    被刪時文字交給鏈中下一框），頁號大於本頁者減 1。

    系統邊界快速失敗：範圍不合法或刪光全部段落 raise ValueError。
    """
    paras = document.paragraphs
    if not 0 <= lo < hi <= len(paras):
        raise ValueError(f"段落範圍 [{lo}, {hi}) 不合法（共 {len(paras)} 段）")
    if hi - lo == len(paras):
        raise ValueError("不能刪光全書的段落")
    head = next((p.master for p in reversed(paras[lo:hi]) if p.master), None)
    rest = list(paras[:lo] + paras[hi:])
    if head is not None and lo < len(rest) and rest[lo].master is None:
        rest[lo] = replace(rest[lo], master=head)
    doc = replace(document, paragraphs=tuple(rest))
    for idx in range(len(doc.text_frames) - 1, -1, -1):
        if doc.text_frames[idx].page == page:
            doc = remove_text_frame(doc, idx)
    return replace(
        doc,
        images=tuple(replace(im, page=im.page - 1) if im.page > page else im
                     for im in doc.images if im.page != page),
        text_frames=tuple(replace(tf, page=tf.page - 1) if tf.page > page else tf
                          for tf in doc.text_frames),
    )


def insert_blank_page(document: Document, at: int, page: int,
                      master: Optional[str] = None) -> Document:
    """在第 at 段之前插入一張空白頁（版面頁 page），回傳新 Document。

    Sprint 153（Owner：新增頁面、插入頁面）。空白頁＝一個自成一節的空段：節首
    恆起新頁，版面層對「整節只有空段」補一條空行，故它佔滿一頁、照常編頁碼。
    頁碼數字與左右側都由版面重排推導（書頁號、紙面號），本函式不碰。

    at＝插入位（0＝最前，len＝最後），呼叫端只交頁界（不切斷跨頁段）。空段取
    全書最常用的段落樣式（通常是內文），不取鄰段：鄰段若是章名或目次條目，空段
    會被目次一致化（Sprint 150）當成同樣式的短段收進目次。master 預設承插入處
    所在節的主版。原本在 at 的段若沒有節首標記，補上它所屬節的主版，使它仍從
    新頁開始（否則會黏到空白頁上、空白頁就不空了）。

    圖與文字框頁號 >= page 者加 1（跟著內容後移）。at 越界 raise IndexError。
    """
    paras = document.paragraphs
    if not 0 <= at <= len(paras):
        raise IndexError(f"插入位 {at} 超出範圍 0..{len(paras)}")
    owner = {i: m for m, lo, hi in _sections(document) for i in range(lo, hi)}
    near = owner[min(at, len(paras) - 1)]
    style = Counter(p.style for p in paras).most_common(1)[0][0]
    blank = Paragraph(text="", style=style, master=master or near)
    rest = list(paras[at:])
    if rest and rest[0].master is None:
        rest[0] = replace(rest[0], master=owner[at])
    return replace(
        document,
        paragraphs=paras[:at] + (blank,) + tuple(rest),
        images=tuple(replace(im, page=im.page + 1) if im.page >= page else im
                     for im in document.images),
        text_frames=tuple(replace(tf, page=tf.page + 1) if tf.page >= page else tf
                          for tf in document.text_frames),
    )
