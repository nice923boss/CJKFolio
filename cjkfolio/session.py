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
    apply_merge,
    apply_para_style,
    apply_replace,
    apply_replace_span,
    apply_split,
    apply_style,
    apply_style_span,
    locate_cell,
)
from .frame_editing import (
    FrameCursor,
    FrameEditResult,
    apply_frame_delete,
    apply_frame_insert,
    locate_frame_cell,
)
from .frames import masters_for_layout, resolve_text_frames
from .layout import LayoutResult, layout_document
from .style_editing import set_character_style, set_paragraph_style
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
        self._layout = layout_document(document, template)
        self._undo: list = []  # [(document, template, cursor)]，最舊→最新
        self._redo: list = []
        self._coalesce_window = coalesce_window  # 連續輸入合併時間窗（秒）
        self._clock = clock  # 單調時鐘（測試可注入可控假時鐘）
        # 連續輸入序列尾：(鍵, 尾 caret, 時戳)；鍵＝("body", para_idx) 或
        # ("frame", source_idx)（Sprint 60：body 與框輸入互為序列邊界，鍵不同即打斷）
        self._pending_insert: Optional[tuple] = None

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

    def _commit_template(self, template: Template):
        """模版變更入歷史（樣式編輯共用）：先重排快速失敗，再推快照切換現態。"""
        if template is self._template:
            return None  # 空／等值變更 no-op：不入 undo
        new_layout = layout_document(self._document, template)  # 套用前快速失敗
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
        self._layout = layout_document(document, template)
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
