"""AI 指派收尾的確定性目次一致化與前言建議（自 ai_style 拆出，Sprint 159）。

AI 只回逐段建議，跨段一致性靠本模組以字形規則補齊（不呼叫 AI、不看樣式名推階層）：
同樣式一致化（Sprint 150）、同編號一致化與前言建議（Sprint 159），說明見
ai_style 模組文件。補上的條目一律進校正表由人勾選。
"""
import re

# 全書標題一覽：短段（且不以句讀收尾）才像標題
_OUTLINE_MAX_CHARS = 30
_SENTENCE_END = "。！？；，、：…」』"

# 段首編號格式（同編號一致化的分組鍵）：組名 → 段首比對式。「第X章」依單位字分組
# （章、節分屬不同組）。只認段首，句中出現的「一、」不算。
_NUM = "一二三四五六七八九十百零〇"
_NUMBERING = (
    ("一、", re.compile(f"^[{_NUM}]+、")),
    ("（一）", re.compile(f"^[（(][{_NUM}]+[）)]")),
    ("第X", re.compile(f"^第[{_NUM}\\d]+([章節篇部回卷])")),
    ("1、", re.compile(r"^\d+[、.．]")),
)
_COLONS = "：:"
PREFACE_TITLE = "前言"


def _heading_like(text: str) -> bool:
    """短段且不以句讀收尾＝疑似標題（純字形判斷，不看樣式名）。"""
    t = text.strip()
    return bool(t) and len(t) <= _OUTLINE_MAX_CHARS and t[-1] not in _SENTENCE_END


def _harmonize_toc(texts, assignments, toc_entries, default_style: str) -> tuple:
    """同樣式目次一致化（Sprint 150）→ (新目次條目列, 說明列)。

    提示詞約束不住跨批一致：真稿 17 段「章節小標-黑體」只有 6 段被列入目次。
    規則：某建議樣式只要有一段列入目次，同樣式的其餘段一併列入，層級統一取該樣式
    已宣告層級的多數（平手取先出現者）。層級仍出自 AI 宣告，不從樣式名推階層。
    守門：預設內文樣式不參與；只補疑似標題的短段（_heading_like），以免一段內文
    或引文被誤列就把同樣式的長段全拖進目次。補上的條目照樣進校正表由人勾選。
    """
    entries = list(toc_entries)
    groups = {}
    for i, style in enumerate(assignments):
        if style is not None and style != default_style:
            groups.setdefault(style, []).append(i)
    notes = []
    for style, members in groups.items():
        levels = [entries[i][1] for i in members if entries[i] is not None]
        if not levels:
            continue
        level = max(dict.fromkeys(levels), key=levels.count)
        added = relevelled = 0
        for i in members:
            if entries[i] is None:
                if _heading_like(texts[i]):
                    entries[i] = (texts[i].strip(), level)
                    added += 1
            elif entries[i][1] != level:
                entries[i] = (entries[i][0], level)
                relevelled += 1
        if added or relevelled:
            notes.append(f"目次一致化：「{style}」補列 {added} 段、改層級 {relevelled} 段，"
                         f"同樣式統一為第 {level} 層（請在校正表確認）")
    return entries, notes


def _numbering_key(text: str):
    """段首編號格式的組名（如「一、」「第X章」）；無編號回 None。"""
    t = text.strip()
    for name, pattern in _NUMBERING:
        m = pattern.match(t)
        if m:
            return name + (m.group(1) if m.groups() else "")
    return None


def _lead_title(text: str):
    """(目次標題, 是否段首引題)；取不出標題回 (None, False)。

    段首引題＝冒號在前 _OUTLINE_MAX_CHARS 字內且冒號後還有內文，標題取到冒號為止；
    獨立標題段（短、可帶結尾冒號）取全段去掉結尾冒號。長段又無引題＝取不出。
    """
    t = text.strip()
    for i, ch in enumerate(t[:_OUTLINE_MAX_CHARS + 1]):
        if ch in _COLONS:
            rest = t[i + 1:].strip()
            return t[:i].strip() or None, bool(rest)
    bare = t.rstrip(_COLONS).strip()
    return (bare, False) if _heading_like(bare) else (None, False)


def _harmonize_numbered(texts, assignments, toc_entries, default_style: str,
                        toc_styles=frozenset()) -> tuple:
    """同編號目次一致化（Sprint 159）→ (新樣式列, 新目次條目列, 說明列)。

    組內只要有一段列入目次：其餘取得出標題的段一併列入（標題取段首引題或全段），
    層級統一取組內多數（平手取先出現者）；段首引題的段回預設內文（提示詞已明訂，
    AI 仍會把整段長文判成大標題而整頁放大字）；獨立標題段之間統一為多數樣式。
    守門：掛目次條目樣式的段（作者手寫目錄）不入組；AI 沒回建議（None）的段不改
    樣式。補上的條目照樣進校正表由人勾選。
    """
    styles, entries = list(assignments), list(toc_entries)
    groups = {}
    for i, text in enumerate(texts):
        key = _numbering_key(text)
        if key is not None and styles[i] not in toc_styles:
            groups.setdefault(key, []).append(i)
    notes = []
    for key, members in groups.items():
        levels = [entries[i][1] for i in members if entries[i] is not None]
        if not levels:
            continue
        level = max(dict.fromkeys(levels), key=levels.count)
        added = restyled = 0
        heads = []
        for i in members:
            title, run_in = _lead_title(texts[i])
            if entries[i] is None and title is not None:
                entries[i] = (title, level)
                added += 1
            elif entries[i] is not None:
                entries[i] = (entries[i][0], level)
            if run_in:
                if styles[i] not in (None, default_style):
                    styles[i] = default_style
                    restyled += 1
            elif title is not None:
                heads.append(i)
        kinds = [styles[i] for i in heads if styles[i] is not None]
        if kinds:
            major = max(dict.fromkeys(kinds), key=kinds.count)
            for i in heads:
                if styles[i] not in (None, major):
                    styles[i] = major
                    restyled += 1
        if added or restyled:
            notes.append(f"目次一致化：「{key}」編號補列 {added} 段、改樣式 {restyled} 段，"
                         f"同編號統一為第 {level} 層（請在校正表確認）")
    return styles, entries, notes


def _preface_at(texts, assignments, toc_entries, default_style: str):
    """第一個目次條目之前有內文 → (插入「前言」的段序, 層級, 樣式)；否則 None。

    插在第一個內文段之前；那段到第一個條目之間已有疑似標題的短段（如「自序」）
    即視為已有標題，不建議。AI 沒回建議的段不算內文（不知道它是什麼）。
    層級取第一個條目；樣式取目次條目段中非預設內文樣式的多數（條目全是段首引題
    的內文時取預設內文，前言標題就與各節引題同樣式）。
    """
    first = next((i for i, e in enumerate(toc_entries) if e is not None), None)
    if not first:
        return None
    start = next((i for i in range(first)
                  if assignments[i] == default_style and texts[i].strip()), None)
    if start is None or any(_heading_like(texts[i]) for i in range(start, first)):
        return None
    kinds = [assignments[i] for i, e in enumerate(toc_entries)
             if e is not None and assignments[i] not in (None, default_style)]
    style = max(dict.fromkeys(kinds), key=kinds.count) if kinds else default_style
    return start, toc_entries[first][1], style
