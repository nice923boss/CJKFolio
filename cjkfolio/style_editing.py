"""樣式定義編輯（Phase 3 樣式系統，Sprint 67／68）：「改樣式即全書套用」的純模版層。

set_paragraph_style／set_character_style 對既有樣式改參數，回傳新 Template（不可變；
空變更或等值變更 no-op 回原物件，同 editing.change_paragraph_style 慣例）。欄位型別
轉換取 styles 載入層單一來源（PARAGRAPH_STYLE_FIELDS／CHARACTER_STYLE_FIELDS）；
值語意（writing_mode 是否可流排、字型家族是否入庫）不在此層驗，由 layout_document
與 FontRegistry 守門（同「樣式名有效性由 layout 守門」慣例）。

樣式繼承級聯（Sprint 68）：編輯樣式後，未宣告（未覆寫）該欄位的傳遞子孫同步刷新
（依 based_on 依賴序迭代至穩定）；被編輯欄位併入該樣式 declared＝自此成為覆寫。
based_on 本身不可經 set_* 編輯（結構變更屬後續片）。

樣式改名（Sprint 75）：rename_*_style 同步模版內所有名稱引用（樣式鍵原位改名、
子樣式 based_on、md_mapping／md_inline_mapping、主版 footer 與 toc 頁碼樣式）；
文件層參照同步在 editing.rename_*_refs，兩者由 session 成對入單一 undo 步。
全書重排與統一 undo 歷史的 session 整合見 cjkfolio/session.py。
"""
from dataclasses import replace
from typing import Mapping

from .styles import (
    CHARACTER_STYLE_FIELDS,
    PARAGRAPH_STYLE_FIELDS,
    CharacterStyle,
    ParagraphStyle,
    Template,
    TemplateError,
)

_REQUIRED_STYLE_FIELDS = ("font_family", "font_weight", "size_pt")  # 根樣式必填（同載入層）


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


def _rename_in_styles(styles: dict, old: str, new: str, kind: str) -> dict:
    """樣式集鍵原位改名＋子樣式 based_on 跟隨；守門（未知／空名／衝突）。"""
    if old not in styles:
        raise KeyError(f"未知{kind}：{old}")
    if not new.strip():
        raise TemplateError(f"{kind}新名稱不可為空")
    if new in styles:
        raise TemplateError(f"{kind}名已存在：{new}")
    renamed = {}
    for name, style in styles.items():
        if name == old:
            style = replace(style, name=new)
            name = new
        if style.based_on == old:
            style = replace(style, based_on=new)
        renamed[name] = style
    return renamed


def rename_paragraph_style(template: Template, old: str, new: str) -> Template:
    """段落樣式改名（模版層）：鍵原位改名＋based_on＋md_mapping 同步；同名 no-op。

    文件層段落／文字框參照同步在 editing.rename_paragraph_style_refs（session 成對）。
    """
    if new == old:
        return template
    return replace(
        template,
        paragraph_styles=_rename_in_styles(
            template.paragraph_styles, old, new, "段落樣式"),
        md_mapping={k: (new if v == old else v)
                    for k, v in template.md_mapping.items()},
    )


def rename_character_style(template: Template, old: str, new: str) -> Template:
    """字元樣式改名（模版層）：鍵＋based_on＋md_inline_mapping＋主版引用
    （footer 元素樣式、toc 頁碼樣式）同步；同名 no-op。"""
    if new == old:
        return template
    renamed = _rename_in_styles(template.character_styles, old, new, "字元樣式")
    masters = {}
    for mname, master in template.masters.items():
        footer = {
            fname: (replace(item, style=new) if item.style == old else item)
            for fname, item in master.footer.items()
        }
        toc = master.toc
        if toc is not None and toc.page_no_style == old:
            toc = replace(toc, page_no_style=new)
        if toc is not master.toc or any(
                footer[f] is not master.footer[f] for f in footer):
            master = replace(master, footer=footer, toc=toc)
        masters[mname] = master
    return replace(
        template,
        character_styles=renamed,
        md_inline_mapping={k: (new if v == old else v)
                           for k, v in template.md_inline_mapping.items()},
        masters=masters,
    )


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


def _added_style(styles: Mapping, fields: Mapping, name, decl: Mapping,
                 kind: str, make):
    """建構新樣式（Sprint 69）：宣告形同模版 JSON（選配 based_on＋參數欄位）。

    名稱空或衝突 TemplateError；子樣式承基底現值再以宣告覆寫（載入層同構）；
    根樣式必填欄位守門（同載入層）。
    """
    if not isinstance(name, str) or not name:
        raise TemplateError(f"{kind} 新樣式名不可為空")
    if name in styles:
        raise TemplateError(f"{kind} 已存在同名樣式「{name}」")
    decl = dict(decl)
    based_on = decl.pop("based_on", None)
    coerced = _coerce_changes(fields, decl, f"{kind}[{name}]")
    if based_on is None:
        missing = [f for f in _REQUIRED_STYLE_FIELDS if f not in coerced]
        if missing:
            raise TemplateError(f"{kind}[{name}] 根樣式缺必要欄位 {missing}")
        effective = coerced
    else:
        if based_on not in styles:
            raise TemplateError(
                f"{kind}[{name}] based_on 引用不存在的樣式「{based_on}」")
        base = styles[based_on]
        effective = {**{f: getattr(base, f) for f in fields}, **coerced}
    return make(name=name, based_on=based_on,
                declared=tuple(sorted(coerced)), **effective)


def add_paragraph_style(template: Template, name: str, decl: Mapping) -> Template:
    """新增段落樣式（§4.3 模版管理「可新增」的資料面，Sprint 69）。"""
    style = _added_style(template.paragraph_styles, PARAGRAPH_STYLE_FIELDS,
                         name, decl, "paragraph_styles", ParagraphStyle)
    return replace(
        template, paragraph_styles={**template.paragraph_styles, name: style})


def add_character_style(template: Template, name: str, decl: Mapping) -> Template:
    """新增字元樣式（對稱 add_paragraph_style）。"""
    style = _added_style(template.character_styles, CHARACTER_STYLE_FIELDS,
                         name, decl, "character_styles", CharacterStyle)
    return replace(
        template, character_styles={**template.character_styles, name: style})


def remove_paragraph_style(template: Template, name: str) -> Template:
    """刪除段落樣式（Sprint 69）：模版內參照守門（子樣式承基底、md_mapping 引用即拒）。

    未知樣式 KeyError；文件層引用不在此驗（session 全文重排 KeyError 快速失敗）。
    """
    template.paragraph_styles[name]
    children = [n for n, st in template.paragraph_styles.items()
                if st.based_on == name]
    if children:
        raise TemplateError(
            f"paragraph_styles[{name}] 有子樣式承基底，不可刪除：{children}")
    used_md = sorted(k for k, v in template.md_mapping.items() if v == name)
    if used_md:
        raise TemplateError(
            f"paragraph_styles[{name}] 被 md_mapping 引用，不可刪除：{used_md}")
    return replace(
        template,
        paragraph_styles={n: st for n, st in template.paragraph_styles.items()
                          if n != name},
    )


def remove_character_style(template: Template, name: str) -> Template:
    """刪除字元樣式（Sprint 69）：守門子樣式、md_inline_mapping、主版頁腳與 toc 引用。"""
    template.character_styles[name]
    children = [n for n, st in template.character_styles.items()
                if st.based_on == name]
    if children:
        raise TemplateError(
            f"character_styles[{name}] 有子樣式承基底，不可刪除：{children}")
    used_md = sorted(k for k, v in template.md_inline_mapping.items() if v == name)
    if used_md:
        raise TemplateError(
            f"character_styles[{name}] 被 md_inline_mapping 引用，不可刪除：{used_md}")
    for mname, master in template.masters.items():
        used_footer = sorted(k for k, item in master.footer.items()
                             if item.style == name)
        if used_footer:
            raise TemplateError(
                f"character_styles[{name}] 被 masters[{mname}] 頁腳引用，"
                f"不可刪除：{used_footer}")
        if master.toc and master.toc.page_no_style == name:
            raise TemplateError(
                f"character_styles[{name}] 被 masters[{mname}].toc 頁碼樣式引用，"
                "不可刪除")
    return replace(
        template,
        character_styles={n: st for n, st in template.character_styles.items()
                          if n != name},
    )
