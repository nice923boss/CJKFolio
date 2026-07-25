"""AI 輔助樣式指派（PLAN §4.4）：AI 只做內容結構識別，輸出「段落 → 樣式名」建議。

分工鐵律：版面幾何一律由排版引擎確定性計算，不採用 AI 輸出的任何數字。
AI 為選配增強：批次失敗（網路／解析）即該批降級 None（維持原樣式＝人工指派），
警告不沉默、不擋流程。候選集＝該書模版的實際段落樣式清單（§4.4 修正 3）；
不確定引導選預設內文（修正 2 粗分類定位）；md／docx 結構優先不經 AI（修正 1）。
金鑰紅線：設定經 ai_config 讀本機檔；警告與錯誤訊息不回帶 api_key 值。
長書稿分批（單批數千字，§4.4），段落不跨批。

目錄條目識別（Sprint 135）：同一次呼叫另回 toc_entries，逐段給 (顯示標題, 層級)
或 None。**頁碼不在其中**，AI 一個數字都不出：頁碼由 toc.document_with_toc 以兩趟
分頁確定性算出（同分工鐵律）。層級一律由 AI 顯式宣告後交人工校正，引擎不從樣式名
或字級反推階層（同 document.Paragraph.toc_title 的既有紀律）。
"""
import dataclasses
import json
import re
import urllib.request
from dataclasses import dataclass

from .ai_config import AiConfig
from .document import Document

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_ARRAY_RE = re.compile(r"\[[\s\S]*\]")


@dataclass(frozen=True)
class SuggestResult:
    """assignments：逐段建議樣式名（None＝無建議，維持原樣式）；警告不沉默。

    toc_entries（Sprint 135）：與 assignments 等長的平行位置列，第 i 項為
    (顯示標題, 層級) 或 None（＝該段不列入目錄）。給預設值 ()＝舊有三欄建構者
    （CLI、離屏替身）零改動；長度不足時視同全段無目錄建議。
    """
    assignments: tuple
    warnings: tuple
    batches: int
    toc_entries: tuple = ()


def _post_json(url: str, headers: dict, body: bytes, timeout: float) -> dict:
    """預設 transport：OpenAI 相容 chat/completions POST（測試注入替身取代）。"""
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _system_prompt(candidates, default_style: str, toc_levels=()) -> str:
    return (
        "你是書籍排版助手。針對輸入的每個段落，從以下段落樣式清單中選一個最合適的："
        + "、".join(candidates)
        + f"。逐段判斷內容結構（章名／小標／引文／內文等）；不確定時一律選「{default_style}」。"
        + "另外，若該段是應列入目次的標題（部名、篇名、章名、序文標題等），"
        + "再加兩個欄位：toc_title＝目次要顯示的文字（通常即該段文字，可去掉多餘空白），"
        + "toc_level＝目次層級的正整數。"
        + _level_prompt(toc_levels)
        + "不列入目次的段落（內文、引文等）不要輸出這兩個欄位。"
        + "不要輸出頁碼，頁碼由排版程式計算。"
        + "只輸出 JSON 陣列，格式 [{\"index\": 數字, \"style\": \"樣式名\"}]，"
        + "列入目次者為 [{\"index\": 數字, \"style\": \"樣式名\", \"toc_title\": \"文字\", "
        + "\"toc_level\": 數字}]，index 用輸入標示的編號，不要任何解釋。"
    )


def _level_prompt(toc_levels) -> str:
    """把模版已宣告的目次層級語意寫進 prompt（toc_levels＝AutoTocSpec.level_hints()）。

    未帶模版宣告時退回通則說明。帶了就明講哪幾層標頁碼、沒有上層結構的稿件該用
    第幾層：本書第 1 層可能是「部名且不標頁碼」，AI 照通則把章名全押第 1 層，
    產出的目次會一個頁碼都沒有而且不報錯（見 AutoTocSpec.level_hints 的說明）。
    """
    if not toc_levels:
        return "1 為最上層（如部名），下層依序 2、3。"
    paged = [level for level, _style, wants in toc_levels if wants]
    desc = "、".join(
        f"第 {level} 層＝{style}（{'標頁碼' if wants else '不標頁碼'}）"
        for level, style, wants in toc_levels)
    text = f"本書目次已宣告這些層：{desc}。只使用已宣告的層級。"
    if paged:
        text += (f"稿件若沒有上層結構（如沒有部名／篇名分卷），章名一律用第 {paged[0]} 層，"
                 "不要全部押在第 1 層。")
    return text


def _batches(texts, batch_char_limit: int):
    """依字數上限切批（段落不跨批，單段超限自成一批）；產出 (起始索引, 段列表)。"""
    start, bucket, size = 0, [], 0
    for i, text in enumerate(texts):
        if bucket and size + len(text) > batch_char_limit:
            yield start, bucket
            start, bucket, size = i, [], 0
        bucket.append(text)
        size += len(text)
    if bucket:
        yield start, bucket


def _sanitize(message: str, secret: str) -> str:
    """警告訊息不回帶金鑰值（紅線）。"""
    return message.replace(secret, "［api_key 已遮蔽］") if secret else message


def _parse_toc_entry(item: dict, idx: int, warnings: list):
    """單項的目錄欄位 → (標題, 層級) 或 None；守門鏡射 document._paragraph_toc_from_dict。

    存檔端（document@2）明訂 toc_title 須非空字串、toc_level 須 ≥1 整數、且
    toc_level 不得單獨出現。這裡先擋，才不會讓一份「看起來套用成功」的稿件到
    存檔時才炸 DocumentError（同 import_core 不把可在邊界判定的錯留給下游）。
    """
    title = item.get("toc_title")
    level = item.get("toc_level")
    if title is None and level is None:
        return None
    if title is None:
        warnings.append(f"AI 只給 toc_level 未給 toc_title，忽略目錄條目（段 {idx}）")
        return None
    if not (isinstance(title, str) and title.strip()):
        warnings.append(f"AI 目錄標題非非空字串，忽略：{title!r}（段 {idx}）")
        return None
    if level is None:
        level = 1
    # 真布林是 int 的子類，True 會被當成層級 1；目錄層級只收真整數
    if isinstance(level, bool) or not isinstance(level, int) or level < 1:
        warnings.append(f"AI 目錄層級非 ≥1 整數，忽略：{level!r}（段 {idx}）")
        return None
    return title.strip(), level


def _parse_assignments(payload: dict, count: int, candidates: set):
    """回應 → (逐段樣式列, 逐段目錄條目列, 警告列表)；兩條位置列等長且與批內段對齊。

    樣式名不在候選集即拒（幻覺守門）；目錄欄位獨立守門，樣式被拒不連坐目錄條目
    （反之亦然），兩者各自可用即各自留下。
    """
    msg = payload["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    text = _THINK_RE.sub("", text)
    m = _ARRAY_RE.search(text)
    if not m:
        raise ValueError(f"回應中無 JSON 陣列（前 120 字）：{text[:120]}")
    items = json.loads(m.group(0))
    slots = [None] * count
    toc_slots = [None] * count
    warnings = []
    for item in items:
        idx = item.get("index")
        style = item.get("style")
        if not isinstance(idx, int) or not 0 <= idx < count:
            warnings.append(f"AI 回應 index 越界忽略：{idx!r}")
            continue
        toc_slots[idx] = _parse_toc_entry(item, idx, warnings)
        if style not in candidates:
            warnings.append(f"AI 建議樣式不在模版候選集，忽略：{style!r}（段 {idx}）")
            continue
        slots[idx] = style
    return slots, toc_slots, warnings


def suggest_styles(
    texts,
    candidates,
    config: AiConfig,
    *,
    default_style: str,
    batch_char_limit: int = 3000,
    timeout: float = 300.0,
    transport=None,
    toc_levels=(),
) -> SuggestResult:
    """對每段文字取得樣式建議；批次失敗降級該批 None 並列警告（不擋流程）。

    toc_levels＝模版 auto_toc.level_hints()（選配）：把本書已宣告的目次層級語意
    寫進 prompt，未帶則退回通則說明（見 _level_prompt）。
    """
    for field in ("base_url", "model"):
        if not getattr(config, field):
            raise ValueError(f"AI 設定不完整：{field} 為空（見 local/ai-config.local.json）")
    post = transport or _post_json
    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = "Bearer " + config.api_key
    candidate_set = set(candidates)

    assignments = [None] * len(texts)
    toc_entries = [None] * len(texts)
    warnings = []
    batches = 0
    for start, bucket in _batches(texts, batch_char_limit):
        batches += 1
        body = json.dumps({
            "model": config.model,
            "messages": [
                {"role": "system",
                 "content": _system_prompt(candidates, default_style, toc_levels)},
                {"role": "user", "content": "\n".join(
                    f"[{i}] {t}" for i, t in enumerate(bucket))},
            ],
            "temperature": 0.2,
            "max_tokens": 4000,
        }).encode("utf-8")
        try:
            payload = post(url, headers, body, timeout)
            slots, toc_slots, batch_warnings = _parse_assignments(
                payload, len(bucket), candidate_set)
        except Exception as exc:  # 降級不擋流程（§4.4），警告不沉默
            # 該批樣式與目錄條目一併維持 None：目錄條目源自同一次回應，
            # 回應沒回來就沒有半份可信的目錄建議。
            warnings.append(_sanitize(
                f"批次 {batches}（段 {start}〜{start + len(bucket) - 1}）AI 指派失敗，"
                f"維持原樣式：{exc}", config.api_key))
            continue
        warnings.extend(_sanitize(w, config.api_key) for w in batch_warnings)
        assignments[start:start + len(bucket)] = slots
        toc_entries[start:start + len(bucket)] = toc_slots
    return SuggestResult(tuple(assignments), tuple(warnings), batches,
                         tuple(toc_entries))


def apply_suggestions(document: Document, assignments, toc_entries=None) -> Document:
    """建議套回文件（不可變）：None 維持原欄位，其餘換段落樣式名（runs 等欄位保留）。

    toc_entries（Sprint 135，選配）：與段落等長的 (標題, 層級)／None 位置列，
    None 維持該段原有 toc_title／toc_level（不當成「清空目錄條目」，那要另外
    表達，避免一次沒回目錄建議就把人工標好的條目全清掉）。
    """
    if len(assignments) != len(document.paragraphs):
        raise ValueError(
            f"建議數與段落數長度不符：{len(assignments)} vs {len(document.paragraphs)}")
    if toc_entries is None:
        toc_entries = [None] * len(document.paragraphs)
    elif len(toc_entries) != len(document.paragraphs):
        raise ValueError(
            f"目錄建議數與段落數長度不符："
            f"{len(toc_entries)} vs {len(document.paragraphs)}")
    paragraphs = tuple(
        _with_suggestion(p, style, toc)
        for p, style, toc in zip(document.paragraphs, assignments, toc_entries)
    )
    return dataclasses.replace(document, paragraphs=paragraphs)


def _with_suggestion(para, style, toc):
    """單段套用（等值即回原物件，維持既有 no-op 語意）。"""
    changes = {}
    if style is not None and style != para.style:
        changes["style"] = style
    if toc is not None and (toc[0], toc[1]) != (para.toc_title, para.toc_level):
        changes["toc_title"], changes["toc_level"] = toc[0], toc[1]
    return dataclasses.replace(para, **changes) if changes else para
