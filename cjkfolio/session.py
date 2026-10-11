"""編輯會談（EditSession）：文件＋模版＋游標的統一 undo／redo 歷史。

自 cjkfolio/editing.py 抽出（Sprint 67 行數紀律分檔，先例 images.py／pdfx_meta.py／
frame_editing.py）：editing.py 保留純文件編輯函式，本檔持有狀態控制器。

現態＝(document, template, cursor, layout)；undo／redo 各持 (document, template, cursor)
快照堆疊（Sprint 67 起快照含模版＝樣式定義編輯與文件編輯同一歷史；快照層只存不解釋），
採標準「回上一個提交態」模型：一次編輯把編輯前態推入 undo 並清空 redo；undo 把現態
推入 redo、彈回上一態並全文重排（Spike 3 認可 7.67ms/章，非增量），redo 對稱。初始
游標＝段 0 caret 0（UI 點選另覆寫；v1 undo 還原上一提交態游標，不追 UI 中途點選）。

Sprint 47：連續前進打字（游標接續前一輸入尾且兩次間隔未逾 coalesce_window 秒）併為
單一 undo 單元（對標 InDesign／多數編輯器逐字輸入不各成一步）；輸入序列邊界＝游標
不連續、逾時間窗、或任何非插入操作（含 undo／redo 與樣式編輯）介入。clock 預設
time.monotonic，測試可注入可控假時鐘以離屏確定性驗證時間邊界。

Sprint 67：update_para_style／update_char_style＝改樣式定義即全書套用（§4.3）：
純模版層 style_editing.set_*，套用前先全文重排快速失敗（非法值不入歷史），入同一
undo 歷史；樣式編輯不改文件，游標保持並反查新版面落點。
"""
import time
from typing import Callable, Mapping, Optional

from .document import Document
from .editing import (
    DocCursor,
    DocRange,
    DocSpan,
    EditResult,
    apply_delete,
    apply_delete_span,
    apply_insert,
    apply_insert_blank,
    apply_merge,
    apply_page_starts,
    apply_remove_blank,
    apply_para_style,
    apply_replace,
    apply_replace_span,
    apply_split,
    apply_style,
    apply_style_span,
    change_paragraph_styles,
    change_paragraph_toc_entries,
    delete_page,
    insert_blank_page,
    locate_cell,
    move_section,
    rename_char_style_refs,
    rename_paragraph_style_refs,
    set_section_master,
)
from .frame_editing import (
    FrameCursor,
    FrameEditResult,
    apply_frame_delete,
    apply_frame_insert,
    locate_frame_cell,
)
from .frame_box_editing import (
    add_text_frame,
    move_text_frame,
    remove_text_frame,
    resize_text_frame,
)
from .frames import masters_for_layout, resolve_text_frames
from .image_editing import (
    move_image,
    place_image,
    remove_image,
    resize_image,
    set_image_wrap,
)
from .layout import LayoutResult
from .page_size import set_page_size
from .toc import TocRefresh, document_with_toc, refresh_toc_page_numbers
from .wrap import layout_with_wrap
from .style_editing import (
    add_character_style,
    add_paragraph_style,
    remove_character_style,
    remove_paragraph_style,
    rename_character_style,
    rename_paragraph_style,
    set_character_style,
    set_color,
    set_footer_item,
    set_paragraph_style,
)
from .style_editing import add_color as add_color_swatch
from .style_editing import remove_color as remove_color_swatch
from .template_library import merge_draft_styles
from .styles import Template


class EditSession:
    """編輯會談：文件＋模版＋游標的 undo／redo 歷史（可變控制器，純邏輯離屏可驗）。"""

    def __init__(
        self,
        document: Document,
        template: Template,
        *,
        coalesce_window: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._template = template
        self._document = document
        self._cursor = DocCursor(0, 0)
        self._layout = layout_with_wrap(document, template)
        self._undo: list = []  # [(document, template, cursor)]，最舊→最新
        self._redo: list = []
        self._coalesce_window = coalesce_window  # 連續輸入合併時間窗（秒）
        self._clock = clock  # 單調時鐘（測試可注入可控假時鐘）
        # 連續輸入序列尾：(鍵, 尾 caret, 時戳)；鍵＝("body", para_idx) 或
        # ("frame", source_idx)（Sprint 60：body 與框輸入互為序列邊界，鍵不同即打斷）
        self._pending_insert: Optional[tuple] = None
        # 最近一次刪頁、插頁或手動更新的目次頁碼重算結果（Sprint 155，供編輯器回報）
        self.last_toc_refresh = TocRefresh(document)

    @property
    def document(self) -> Document:
        return self._document

    @property
    def template(self) -> Template:
        """現態模版（Sprint 67 起可經 update_para_style／update_char_style 演進）。"""
        return self._template

    @property
    def cursor(self):
        """現態游標：DocCursor（body）或 FrameCursor（框編輯後，Sprint 60）。"""
        return self._cursor

    @property
    def layout(self) -> LayoutResult:
        return self._layout

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def _commit(self, result):
        """把現態存入 undo、清 redo，切換至編輯結果（供各編輯方法共用）。

        result＝EditResult（body 編輯）或 FrameEditResult（框編輯，Sprint 60；其
        layout 為原物件＝框編輯不重排 body）。記為一個新 undo 單元並重置輸入序列
        （_pending_insert 歸零，其後的連續輸入不與此前輸入合併）。
        """
        self._undo.append((self._document, self._template, self._cursor))
        self._redo.clear()
        self._document = result.document
        self._cursor = result.cursor
        self._layout = result.layout
        self._pending_insert = None
        return result

    def insert(self, cursor: DocCursor, text: str) -> EditResult:
        """插入 text；連續前進打字（游標接續前一輸入且未逾時間窗）併入同一 undo 單元。

        對標 InDesign／多數編輯器：逐字輸入合併為單一 undo 步。序列邊界＝游標不連續、
        兩次輸入間隔逾 coalesce_window、或任何非插入操作（含 undo／redo）介入（皆令
        _pending_insert 歸零，其後起新 undo 單元）。
        """
        result = apply_insert(self._document, self._template, cursor, text)
        now = self._clock()
        if self._can_coalesce(("body", cursor.para_idx), cursor.caret, now):
            # 併入當前 undo 單元：更新現態但不新增 undo 快照、不動 redo
            self._document = result.document
            self._cursor = result.cursor
            self._layout = result.layout
        else:
            self._commit(result)  # 起新 undo 單元（推編輯前態、清 redo、重置序列）
        # 記錄本次輸入尾為序列新尾（含合併路徑：時戳刷新為最近一次輸入）
        self._pending_insert = (("body", cursor.para_idx), result.cursor.caret, now)
        return result

    def insert_frame(self, cursor: FrameCursor, text: str) -> FrameEditResult:
        """框內插字（Sprint 60）：與 body 編輯共用同一 undo／redo 歷史。

        框連續前進打字（同一來源框、caret 接續前一輸入尾、未逾時間窗）併入同一
        undo 單元；body 與框輸入互為序列邊界（鍵不同即起新單元）。框編輯不重排
        body（result.layout＝原物件），現態 layout 不變。
        """
        result = apply_frame_insert(
            self._document, self._template, self._layout, cursor, text)
        now = self._clock()
        key = ("frame", cursor.source_idx)
        if self._can_coalesce(key, cursor.caret, now):
            self._document = result.document
            self._cursor = result.cursor  # layout 不變（框編輯不影響流排）
        else:
            self._commit(result)
        self._pending_insert = (key, result.cursor.caret, now)
        return result

    def delete_frame(self, source_idx: int, start: int, end: int) -> FrameEditResult:
        """框內刪除範圍（Sprint 60）：入同一 undo／redo 歷史（非插入操作，打斷輸入序列）。"""
        return self._commit(apply_frame_delete(
            self._document, self._template, self._layout, source_idx, start, end))

    def _can_coalesce(self, key: tuple, caret: int, now: float) -> bool:
        """連續輸入是否併入當前 undo 單元：同鍵（body 段／框來源）、caret 接續前一
        輸入尾、未逾時間窗。"""
        if self._pending_insert is None:
            return False
        pkey, end_caret, ts = self._pending_insert
        return pkey == key and caret == end_caret and now - ts <= self._coalesce_window

    def delete(self, drange: DocRange) -> EditResult:
        return self._commit(apply_delete(self._document, self._template, drange))

    def replace(self, drange: DocRange, text: str) -> EditResult:
        return self._commit(apply_replace(self._document, self._template, drange, text))

    def delete_span(self, span: DocSpan) -> EditResult:
        return self._commit(apply_delete_span(self._document, self._template, span))

    def replace_span(self, span: DocSpan, text: str) -> EditResult:
        return self._commit(
            apply_replace_span(self._document, self._template, span, text)
        )

    def split(self, cursor: DocCursor) -> EditResult:
        return self._commit(apply_split(self._document, self._template, cursor))

    def merge(self, para_idx: int) -> EditResult:
        return self._commit(apply_merge(self._document, self._template, para_idx))

    def insert_blank(self, para_idx: int) -> EditResult:
        """在第 para_idx 段前插入空段（手動空一行，Sprint 141）；入統一 undo 歷史。"""
        return self._commit(
            apply_insert_blank(self._document, self._template, para_idx))

    def remove_blank(self, para_idx: int) -> EditResult:
        """移除第 para_idx 空段（Sprint 141）；非空段 ValueError，狀態不變不入歷史。"""
        return self._commit(
            apply_remove_blank(self._document, self._template, para_idx))

    def apply_style(self, drange: DocRange, char_style: Optional[str]) -> EditResult:
        return self._commit(
            apply_style(self._document, self._template, drange, char_style)
        )

    def apply_style_span(self, span: DocSpan, char_style: Optional[str]) -> EditResult:
        return self._commit(
            apply_style_span(self._document, self._template, span, char_style)
        )

    def apply_para_style(self, cursor: DocCursor, style: str) -> EditResult:
        return self._commit(
            apply_para_style(self._document, self._template, cursor, style)
        )

    def apply_para_styles(self, assignments, toc_entries=None, *,
                          generate_toc: bool = False):
        """多段批次改派段落樣式入**單一 undo 步**（Sprint 79，§4.4 逐段校正批次
        改派＝AI 建議採用與跨段套段落樣式的共同地基；復用 _commit_pair＝文件變
        模版不變）。未知樣式名全文重排 KeyError 快速失敗；全數等值 no-op 回 None。

        toc_entries／generate_toc（Sprint 135）刻意併在同一個方法裡：AI 指派一次
        送出的三件事（樣式、目錄條目宣告、生成目錄節）若分三次 session 呼叫就變成
        三步 undo，違反本方法「單一 undo 步」的對外承諾。三者依序作用於同一份中介
        文件，最後只 commit 一次。生成失敗（如無條目、模版未宣告 auto_toc）拋
        TocError（ValueError 子類），此時狀態完全不變、不入歷史。

        改派後隨即補章首分頁（Sprint 141 apply_page_starts）：順序必須在生成目錄
        之前，否則目錄的兩趟穩定分頁算的是「還沒換頁」的頁碼，印出來的目錄頁碼
        會整批偏掉。

        生成目錄時一併拿掉內文中的手寫目錄（Sprint 149 drop_manual），段數可能
        變少，游標越界即歸零（同 replace_document，避免指到不存在的段）。"""
        document = change_paragraph_styles(self._document, assignments)
        document = apply_page_starts(document, self._template)
        if toc_entries:
            document = change_paragraph_toc_entries(document, toc_entries)
        if generate_toc:
            document = document_with_toc(document, self._template, drop_manual=True)
            if document == self._document:
                # 目錄重生成恆造新物件（replace），內容相同時還原同一性，
                # 讓 _commit_pair 的 no-op 判定成立＝不推一步「看不出差別」的 undo
                document = self._document
        result = self._commit_pair(document, self._template)
        cursor = self._cursor
        if result is not None and isinstance(cursor, DocCursor) and (
                cursor.para_idx >= len(document.paragraphs)
                or cursor.caret > len(document.paragraphs[cursor.para_idx].text)):
            self._cursor = DocCursor(0, 0)
            result = self._state_result()
        return result

    def set_section_master(self, para_idx: int, master: Optional[str]):
        """指派節式主版入**單一 undo 步**（Sprint 130 主版指派介面的核心半邊；
        復用 _commit_pair＝文件變模版不變）。para_idx==0 改首節 doc.master，其餘
        設段落節首標記（None＝承前節）。未知主版名於套用前全文重排 KeyError 快速
        失敗、狀態不變不入歷史；等值 no-op 回 None。"""
        return self._commit_pair(
            set_section_master(self._document, para_idx, master), self._template)

    def move_section(self, src_index: int, dst_index: int):
        """把整節搬到另一個節序位置入單一 undo 步（Sprint 142 頁面拖曳重排）。

        節序（非版面頁號）由呼叫端換算：頁面是流排結果，可搬的最小完整單位是節。
        原位放下＝等值 no-op 回 None（不推一步看不出差別的 undo）。節序越界由
        move_section IndexError 快速失敗、狀態不變不入歷史。"""
        return self._commit_pair(
            move_section(self._document, src_index, dst_index), self._template)

    def delete_page(self, page: int, lo: int, hi: int):
        """刪除版面頁 page（段 [lo, hi) 與該頁的圖、文字框）入單一 undo 步。

        Sprint 153。段數變少，游標一律落到刪除處（越界即退到末段段首）：留著舊
        游標會靜默指到別段，文字框游標同理（框可能已被刪）。

        Sprint 155：同一步內重算目次頁碼（結果見 last_toc_refresh）。"""
        result = self._commit_pair(
            self._with_toc_refreshed(delete_page(self._document, page, lo, hi)),
            self._template)
        if result is not None:
            self._cursor = DocCursor(min(lo, len(self._document.paragraphs) - 1), 0)
            result = self._state_result()
        return result

    def insert_blank_page(self, at: int, page: int, master: Optional[str] = None):
        """在第 at 段之前插入空白頁（版面頁 page）入單一 undo 步（Sprint 153）。

        段數加 1，內文游標在插入處之後者跟著後移一段（仍指同一個字）。
        Sprint 155：同一步內重算目次頁碼（結果見 last_toc_refresh）。"""
        result = self._commit_pair(
            self._with_toc_refreshed(insert_blank_page(self._document, at, page, master)),
            self._template)
        if result is not None and isinstance(self._cursor, DocCursor)                 and self._cursor.para_idx >= at:
            self._cursor = DocCursor(self._cursor.para_idx + 1, self._cursor.caret)
            result = self._state_result()
        return result

    def _with_toc_refreshed(self, document: Document) -> Document:
        """重算 document 的目次頁碼並記入 last_toc_refresh（刪頁、插頁、手動更新共用）。"""
        self.last_toc_refresh = refresh_toc_page_numbers(document, self._template)
        return self.last_toc_refresh.document

    def refresh_toc(self):
        """依現行版面更新目次頁碼入單一 undo 步（Sprint 155）；頁碼沒變＝no-op。"""
        return self._commit_pair(self._with_toc_refreshed(self._document), self._template)

    def replace_document(self, document: Document):
        """整份換文件（Sprint 107 稿件匯入）：游標歸零，入統一 undo 歷史。

        游標歸零而非沿用：新稿的段數與舊稿無關，沿用舊游標會指到不存在的段。
        與文字、樣式、圖片編輯共用同一條歷史，故誤匯入一步 Ctrl+Z 即回到匯入前的
        稿件（同 Sprint 67 模版編輯、Sprint 102 圖片編輯的處置）。文件引用現行模版
        沒有的樣式時，於套用前的重排 KeyError 快速失敗、狀態不變不入歷史。
        """
        if document is self._document:
            return None
        new_layout = layout_with_wrap(document, self._template)  # 套用前快速失敗
        self._undo.append((self._document, self._template, self._cursor))
        self._redo.clear()
        self._document = document
        self._cursor = DocCursor(0, 0)
        self._layout = new_layout
        self._pending_insert = None
        return self._state_result()

    def place_image(self, path: str, page: int, rect):
        """置入一張 rect 圖（Sprint 102 畫布拖放）：入統一 undo 歷史。

        圖片編輯與文字編輯共用同一條歷史（同 Sprint 67 模版編輯的處置），故
        Ctrl+Z 一路回退的順序就是使用者實際操作的順序，不分兩套歷史。
        """
        return self._commit_pair(
            place_image(self._document, path, page, rect), self._template)

    def move_image(self, idx: int, dx_pt: float, dy_pt: float):
        """平移置入圖（拖曳放開時提交一步，拖曳途中的預覽不入歷史）。"""
        return self._commit_pair(
            move_image(self._document, idx, dx_pt, dy_pt), self._template)

    def resize_image(self, idx: int, rect):
        """縮放置入圖（同 move_image，放開才提交）。"""
        return self._commit_pair(
            resize_image(self._document, idx, rect), self._template)

    def remove_image(self, idx: int):
        """移除置入圖。"""
        return self._commit_pair(
            remove_image(self._document, idx), self._template)

    def set_image_wrap(self, idx: int, *, wrap=None, margin_mm=None):
        """改繞排參數（Sprint 103）：入統一 undo 歷史，畫布即時重排。

        未指定的欄位保持現值；等值變更 no-op 回 None（不入歷史）。繞排改變流排，
        故本層的重排（layout_with_wrap）即是畫布所見的版面。
        """
        return self._commit_pair(
            set_image_wrap(self._document, idx, wrap=wrap, margin_mm=margin_mm),
            self._template)

    def add_text_frame(self, text: str, style: str, page: int, rect):
        """新增一個獨立文字框（Sprint 136）：與圖片、文字共用同一條 undo 歷史。"""
        return self._commit_pair(
            add_text_frame(self._document, self._template, text, style, page, rect),
            self._template)

    def move_text_frame(self, idx: int, dx_pt: float, dy_pt: float):
        """平移整個文字框（拖曳放開時提交一步，拖曳途中的預覽不入歷史）。"""
        return self._commit_pair(
            move_text_frame(self._document, idx, dx_pt, dy_pt), self._template)

    def resize_text_frame(self, idx: int, rect):
        """縮放整個文字框（同 move_text_frame，放開才提交）。"""
        return self._commit_pair(
            resize_text_frame(self._document, idx, rect), self._template)

    def remove_text_frame(self, idx: int):
        """移除整個文字框（框內文字一併移除；Ctrl+Z 一步回原）。

        框游標指向被移除框或其右側時一併歸零：移除後右側框全體左移一位，留著舊
        source_idx 會靜默指到「別的框的同位置字」，使用者看到游標跳到沒點過的地方
        卻無從得知為何。歸零成內文游標是可解釋的行為，靜默錯位不是。
        """
        result = self._commit_pair(
            remove_text_frame(self._document, idx), self._template)
        if result is not None and isinstance(self._cursor, FrameCursor) \
                and self._cursor.source_idx >= idx:
            self._cursor = DocCursor(0, 0)
            return self._state_result()
        return result

    def update_para_style(self, name: str, changes: Mapping):
        """改段落樣式定義（§4.3「改樣式即全書套用」，Sprint 67）：全書重排入統一歷史。

        等值變更 no-op 回 None（不入歷史）；非法值（如 writing_mode）於套用前全文重排
        快速失敗、狀態不變。回傳 EditResult 或 FrameEditResult（依現態游標型別）。
        """
        return self._commit_template(
            set_paragraph_style(self._template, name, changes))

    def update_char_style(self, name: str, changes: Mapping):
        """改字元樣式定義（對稱 update_para_style）：字槽網格依段落樣式（Sprint 9），
        字元樣式變更不動斷行、由渲染層取新定義。"""
        return self._commit_template(
            set_character_style(self._template, name, changes))

    def update_footer_item(self, master_name: str, item_name: str,
                           changes: Mapping, *, all_masters: bool = False):
        """改書眉／頁碼的字面文字與位置（Sprint 142）：入統一 undo 歷史，一步可還原。

        all_masters=True＝批次挪所有含同名元素的主版，仍只推一步 undo（Owner 眼中
        是一次操作）。書眉不參與斷行幾何，重排仍照 _commit_template 紀律先跑一次。"""
        return self._commit_template(set_footer_item(
            self._template, master_name, item_name, changes,
            all_masters=all_masters))

    def add_para_style(self, name: str, decl: Mapping):
        """新增段落樣式（Sprint 69）：入統一 undo 歷史，新樣式立即可套用。"""
        return self._commit_template(
            add_paragraph_style(self._template, name, decl))

    def add_char_style(self, name: str, decl: Mapping):
        """新增字元樣式（對稱 add_para_style）。"""
        return self._commit_template(
            add_character_style(self._template, name, decl))

    def remove_para_style(self, name: str):
        """刪除段落樣式：模版內參照守門在純層；文件仍用該樣式者由全文重排
        KeyError 快速失敗（狀態不變，不入歷史）。"""
        return self._commit_template(
            remove_paragraph_style(self._template, name))

    def remove_char_style(self, name: str):
        """刪除字元樣式（對稱 remove_para_style）。"""
        return self._commit_template(
            remove_character_style(self._template, name))

    def apply_template(self, template: Template):
        """套用整個模版（§4.3 模版庫「套用到新書」，Sprint 77）：整份替換入統一 undo。

        文件引用的樣式在新模版缺失 → 全文重排 KeyError 快速失敗（狀態不變）；
        同一模版物件 no-op 回 None。
        """
        return self._commit_template(template)

    def update_page_size(self, width_mm, height_mm, *, refit_grid: bool = False):
        """改成品尺寸（trim size，Sprint 140）：入統一 undo 歷史，一步可還原。

        refit_grid=True 時邊距不動、把紙張增減換算成版心行列增減，內文重排、頁數會變；
        False 只換紙張，一個字都不重排。溢出成品的項不在此擋（改小開本本來就可能讓
        既有元件落到紙外），由 page_size.page_fit_warnings 據實回報、呼叫端呈現。
        等值變更 no-op 回 None；非法尺寸於套用前 TemplateError 快速失敗、狀態不變。
        """
        return self._commit_template(set_page_size(
            self._template, width_mm, height_mm, refit_grid=refit_grid))

    def merge_draft(self, draft: Mapping):
        """萃取草稿一鍵併入現行模版（GAPS #37 (b)，Sprint 77）：回 (result, report)。

        全跳過（模版不變）＝no-op 回 (None, report) 不入歷史；新增樣式入統一 undo。
        """
        merged, report = merge_draft_styles(self._template, draft)
        return self._commit_template(merged), report

    def update_color(self, name: str, changes: Mapping):
        """改色票定義（§4.3 色票管理，Sprint 76）：改值即全書變色，入統一 undo 歷史。

        文字色只在渲染層取值（不動斷行幾何），重排仍照 _commit_template 紀律
        （先重排快速失敗再入歷史）；等值變更 no-op 回 None。
        """
        return self._commit_template(set_color(self._template, name, changes))

    def add_color(self, name: str, *, cmyk=None, hex=None, note=None):
        """新增色票：入統一 undo 歷史，新色票立即可被樣式 color 引用。"""
        return self._commit_template(
            add_color_swatch(self._template, name, cmyk=cmyk, hex=hex, note=note))

    def remove_color(self, name: str):
        """刪除色票：被樣式引用即 TemplateError（純模版層守門），狀態不變不入歷史。"""
        return self._commit_template(remove_color_swatch(self._template, name))

    def rename_para_style(self, old: str, new: str):
        """段落樣式改名（Sprint 75）：模版引用（鍵／based_on／md_mapping）與文件參照
        （段落／文字框）成對改名，單一 undo 步；同名 no-op 回 None。"""
        return self._commit_pair(
            rename_paragraph_style_refs(self._document, old, new),
            rename_paragraph_style(self._template, old, new))

    def rename_char_style(self, old: str, new: str):
        """字元樣式改名（對稱 rename_para_style）：模版引用（鍵／based_on／
        md_inline_mapping／主版 footer 與 toc 頁碼樣式）與文件 run 參照成對改名。"""
        return self._commit_pair(
            rename_char_style_refs(self._document, old, new),
            rename_character_style(self._template, old, new))

    def _commit_pair(self, document: Document, template: Template):
        """文件＋模版成對變更入單一 undo 步（改名共用）：先重排快速失敗再入歷史；
        兩側皆無變更＝no-op 不入 undo（同 _commit_template 慣例）。"""
        if document is self._document and template is self._template:
            return None
        new_layout = layout_with_wrap(document, template)  # 套用前快速失敗
        self._undo.append((self._document, self._template, self._cursor))
        self._redo.clear()
        self._document = document
        self._template = template
        self._layout = new_layout
        self._pending_insert = None
        return self._state_result()

    def _commit_template(self, template: Template):
        """模版變更入歷史（樣式編輯共用）：先重排快速失敗，再推快照切換現態。"""
        if template is self._template:
            return None  # 空／等值變更 no-op：不入 undo
        new_layout = layout_with_wrap(self._document, template)  # 套用前快速失敗
        self._undo.append((self._document, self._template, self._cursor))
        self._redo.clear()
        self._template = template
        self._layout = new_layout
        self._pending_insert = None
        return self._state_result()

    def _state_result(self):
        """依現態游標型別組結果（_restore 與樣式編輯共用，Sprint 60 雙型別慣例）。"""
        if isinstance(self._cursor, FrameCursor):  # 現態為框編輯態 → 框結果
            placements = resolve_text_frames(
                self._document, self._template,
                masters_for_layout(self._template, self._document, self._layout))
            return FrameEditResult(
                document=self._document,
                layout=self._layout,
                placements_by_page=placements,
                cursor=self._cursor,
                address=locate_frame_cell(placements, self._cursor),
            )
        return EditResult(
            document=self._document,
            layout=self._layout,
            cursor=self._cursor,
            address=locate_cell(self._layout, self._cursor),
        )

    def _restore(self, document: Document, template: Template, cursor) -> EditResult:
        """切換現態至還原的 (document, template, cursor)、全文重排、反查游標落點。

        undo／redo 均重置輸入序列（_pending_insert 歸零，還原後重新打字不與被還原的
        輸入合併）。
        """
        self._document = document
        self._template = template
        self._cursor = cursor
        self._layout = layout_with_wrap(document, template)
        self._pending_insert = None
        return self._state_result()

    def undo(self):
        """回退一步至上一提交態；無可回退回 None（no-op）。

        回傳 EditResult 或 FrameEditResult（依還原態游標型別，Sprint 60）。"""
        if not self._undo:
            return None
        self._redo.append((self._document, self._template, self._cursor))
        document, template, cursor = self._undo.pop()
        return self._restore(document, template, cursor)

    def redo(self):
        """重做一步至下一提交態；無可重做回 None（no-op）。

        回傳 EditResult 或 FrameEditResult（依還原態游標型別，Sprint 60）。"""
        if not self._redo:
            return None
        self._undo.append((self._document, self._template, self._cursor))
        document, template, cursor = self._redo.pop()
        return self._restore(document, template, cursor)
