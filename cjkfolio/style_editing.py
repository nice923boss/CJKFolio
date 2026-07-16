"""樣式定義編輯（Phase 3 樣式系統第一片，Sprint 67）：「改樣式即全書套用」的純模版層。

set_paragraph_style／set_character_style 對既有樣式改參數，回傳新 Template（不可變；
空變更或等值變更 no-op 回原物件，同 editing.change_paragraph_style 慣例）。欄位型別
轉換語意同 styles 載入層（_paragraph_style／_character_style）；值語意（writing_mode
是否可流排、字型家族是否入庫）不在此層驗，由 layout_document 與 FontRegistry 守門
（同「樣式名有效性由 layout 守門」慣例）。

樣式改名與新增／刪除屬後續片（改名需全書段落參照同步）；全書重排與統一 undo 歷史
的 session 整合見 cjkfolio/session.py（EditSession.update_para_style／update_char_style）。
"""
from dataclasses import replace
from typing import Callable, Mapping, Optional

from .styles import Template, TemplateError


def _opt_str(value) -> Optional[str]:
    return None if value is None else str(value)


# 可編輯欄位 → 型別轉換器（同載入層語意；name 不在內＝不可改名）
PARAGRAPH_EDITABLE_FIELDS: Mapping[str, Callable] = {
    "font_family": str,
    "font_weight": str,
    "size_pt": float,
    "indent_chars": int,
    "para_gap_slots": int,
    "writing_mode": str,
    "head_offset_chars": int,
    "lead_offset_pt": float,
    "source_font": _opt_str,
    "note": _opt_str,
}

CHARACTER_EDITABLE_FIELDS: Mapping[str, Callable] = {
    "font_family": str,
    "font_weight": str,
    "size_pt": float,
    "source_font": _opt_str,
    "note": _opt_str,
}


def _coerce_changes(fields: Mapping[str, Callable], changes: Mapping, ctx: str) -> dict:
    """變更欄位守門＋型別轉換；不可編輯欄位（含 name）快速失敗。"""
    out = {}
    for key, value in changes.items():
        if key not in fields:
            raise TemplateError(f"{ctx} 不可編輯的欄位：{key}")
        out[key] = fields[key](value)
    return out


def set_paragraph_style(template: Template, name: str, changes: Mapping) -> Template:
    """改段落樣式定義，回傳新 Template（原模版不可變；其他樣式物件共享）。

    未知樣式 KeyError（同 layout 慣例）；不可編輯欄位 TemplateError；
    空變更或等值變更 no-op 回原物件。
    """
    style = template.paragraph_styles[name]
    coerced = _coerce_changes(
        PARAGRAPH_EDITABLE_FIELDS, changes, f"paragraph_styles[{name}]")
    if not coerced:
        return template
    new_style = replace(style, **coerced)
    if new_style == style:
        return template
    return replace(
        template,
        paragraph_styles={**template.paragraph_styles, name: new_style},
    )


def set_character_style(template: Template, name: str, changes: Mapping) -> Template:
    """改字元樣式定義，回傳新 Template（對稱 set_paragraph_style）。"""
    style = template.character_styles[name]
    coerced = _coerce_changes(
        CHARACTER_EDITABLE_FIELDS, changes, f"character_styles[{name}]")
    if not coerced:
        return template
    new_style = replace(style, **coerced)
    if new_style == style:
        return template
    return replace(
        template,
        character_styles={**template.character_styles, name: new_style},
    )
