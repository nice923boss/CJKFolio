"""樣式定義編輯（Phase 3 樣式系統，Sprint 67／68）：「改樣式即全書套用」的純模版層。

set_paragraph_style／set_character_style 對既有樣式改參數，回傳新 Template（不可變；
空變更或等值變更 no-op 回原物件，同 editing.change_paragraph_style 慣例）。欄位型別
轉換取 styles 載入層單一來源（PARAGRAPH_STYLE_FIELDS／CHARACTER_STYLE_FIELDS）；
值語意（writing_mode 是否可流排、字型家族是否入庫）不在此層驗，由 layout_document
與 FontRegistry 守門（同「樣式名有效性由 layout 守門」慣例）。

樣式繼承級聯（Sprint 68）：編輯樣式後，未宣告（未覆寫）該欄位的傳遞子孫同步刷新
（依 based_on 依賴序迭代至穩定）；被編輯欄位併入該樣式 declared＝自此成為覆寫。
based_on 本身不可經 set_* 編輯（結構變更屬後續片）。

樣式改名與新增／刪除屬後續片（改名需全書段落參照同步）；全書重排與統一 undo 歷史
的 session 整合見 cjkfolio/session.py（EditSession.update_para_style／update_char_style）。
"""
from dataclasses import replace
from typing import Mapping

from .styles import (
    CHARACTER_STYLE_FIELDS,
    PARAGRAPH_STYLE_FIELDS,
    Template,
    TemplateError,
)


def _coerce_changes(fields: Mapping, changes: Mapping, ctx: str) -> dict:
    """變更欄位守門＋型別轉換；不可編輯欄位（含 name／based_on／declared）快速失敗。"""
    out = {}
    for key, value in changes.items():
        if key not in fields:
            raise TemplateError(f"{ctx} 不可編輯的欄位：{key}")
        out[key] = fields[key](value)
    return out


def _edited_style(style, fields: Mapping, changes: Mapping, ctx: str):
    """套變更回新樣式（含 declared 併入）；空或等值變更回原物件（no-op 訊號）。"""
    coerced = _coerce_changes(fields, changes, ctx)
    if not coerced:
        return style
    new_style = replace(
        style, **coerced,
        declared=tuple(sorted(set(style.declared) | set(coerced))))
    return style if new_style == style else new_style


def _with_cascade(styles: dict, name: str, new_style, fields: Mapping) -> dict:
    """以 new_style 取代 styles[name]，並刷新傳遞子孫的未覆寫欄位（Sprint 68 繼承）。

    依 based_on 依賴序迭代至穩定（樣式數十級，O(n²) 上界可忽略）；子孫僅未列於
    自身 declared 的欄位承新基底效值，覆寫欄位不動。
    """
    out = {**styles, name: new_style}
    updated = {name}
    progressed = True
    while progressed:
        progressed = False
        for child_name, child in out.items():
            if child.based_on in updated and child_name not in updated:
                parent = out[child.based_on]
                inherited = {f: getattr(parent, f) for f in fields
                             if f not in child.declared}
                out[child_name] = replace(child, **inherited)
                updated.add(child_name)
                progressed = True
    return out


def set_paragraph_style(template: Template, name: str, changes: Mapping) -> Template:
    """改段落樣式定義，回傳新 Template（原模版不可變；未動樣式物件共享）。

    未知樣式 KeyError（同 layout 慣例）；不可編輯欄位 TemplateError；
    空變更或等值變更 no-op 回原物件；未覆寫該欄位的子孫樣式同步級聯。
    """
    style = template.paragraph_styles[name]
    new_style = _edited_style(
        style, PARAGRAPH_STYLE_FIELDS, changes, f"paragraph_styles[{name}]")
    if new_style is style:
        return template
    return replace(
        template,
        paragraph_styles=_with_cascade(
            template.paragraph_styles, name, new_style, PARAGRAPH_STYLE_FIELDS),
    )


def set_character_style(template: Template, name: str, changes: Mapping) -> Template:
    """改字元樣式定義，回傳新 Template（對稱 set_paragraph_style，含繼承級聯）。"""
    style = template.character_styles[name]
    new_style = _edited_style(
        style, CHARACTER_STYLE_FIELDS, changes, f"character_styles[{name}]")
    if new_style is style:
        return template
    return replace(
        template,
        character_styles=_with_cascade(
            template.character_styles, name, new_style, CHARACTER_STYLE_FIELDS),
    )
