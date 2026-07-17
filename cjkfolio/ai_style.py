"""AI 輔助樣式指派（PLAN §4.4）：AI 只做內容結構識別，輸出「段落 → 樣式名」建議。

分工鐵律：版面幾何一律由排版引擎確定性計算，不採用 AI 輸出的任何數字。
AI 為選配增強：批次失敗（網路／解析）即該批降級 None（維持原樣式＝人工指派），
警告不沉默、不擋流程。候選集＝該書模版的實際段落樣式清單（§4.4 修正 3）；
不確定引導選預設內文（修正 2 粗分類定位）；md／docx 結構優先不經 AI（修正 1）。
金鑰紅線：設定經 ai_config 讀本機檔；警告與錯誤訊息不回帶 api_key 值。
長書稿分批（單批數千字，§4.4），段落不跨批。
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
    """assignments：逐段建議樣式名（None＝無建議，維持原樣式）；警告不沉默。"""
    assignments: tuple
    warnings: tuple
    batches: int


def _post_json(url: str, headers: dict, body: bytes, timeout: float) -> dict:
    """預設 transport：OpenAI 相容 chat/completions POST（測試注入替身取代）。"""
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _system_prompt(candidates, default_style: str) -> str:
    return (
        "你是書籍排版助手。針對輸入的每個段落，從以下段落樣式清單中選一個最合適的："
        + "、".join(candidates)
        + f"。逐段判斷內容結構（章名／小標／引文／內文等）；不確定時一律選「{default_style}」。"
        + "只輸出 JSON 陣列，格式 [{\"index\": 數字, \"style\": \"樣式名\"}]，"
        + "index 用輸入標示的編號，不要任何解釋。"
    )


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


def _parse_assignments(payload: dict, count: int, candidates: set):
    """回應 → (逐段樣式或 None 列表, 警告列表)；樣式名不在候選集即拒（幻覺守門）。"""
    msg = payload["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    text = _THINK_RE.sub("", text)
    m = _ARRAY_RE.search(text)
    if not m:
        raise ValueError(f"回應中無 JSON 陣列（前 120 字）：{text[:120]}")
    items = json.loads(m.group(0))
    slots = [None] * count
    warnings = []
    for item in items:
        idx = item.get("index")
        style = item.get("style")
        if not isinstance(idx, int) or not 0 <= idx < count:
            warnings.append(f"AI 回應 index 越界忽略：{idx!r}")
            continue
        if style not in candidates:
            warnings.append(f"AI 建議樣式不在模版候選集，忽略：{style!r}（段 {idx}）")
            continue
        slots[idx] = style
    return slots, warnings


def suggest_styles(
    texts,
    candidates,
    config: AiConfig,
    *,
    default_style: str,
    batch_char_limit: int = 3000,
    timeout: float = 300.0,
    transport=None,
) -> SuggestResult:
    """對每段文字取得樣式建議；批次失敗降級該批 None 並列警告（不擋流程）。"""
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
    warnings = []
    batches = 0
    for start, bucket in _batches(texts, batch_char_limit):
        batches += 1
        body = json.dumps({
            "model": config.model,
            "messages": [
                {"role": "system", "content": _system_prompt(candidates, default_style)},
                {"role": "user", "content": "\n".join(
                    f"[{i}] {t}" for i, t in enumerate(bucket))},
            ],
            "temperature": 0.2,
            "max_tokens": 4000,
        }).encode("utf-8")
        try:
            payload = post(url, headers, body, timeout)
            slots, batch_warnings = _parse_assignments(payload, len(bucket), candidate_set)
        except Exception as exc:  # 降級不擋流程（§4.4），警告不沉默
            warnings.append(_sanitize(
                f"批次 {batches}（段 {start}〜{start + len(bucket) - 1}）AI 指派失敗，"
                f"維持原樣式：{exc}", config.api_key))
            continue
        warnings.extend(_sanitize(w, config.api_key) for w in batch_warnings)
        assignments[start:start + len(bucket)] = slots
    return SuggestResult(tuple(assignments), tuple(warnings), batches)


def apply_suggestions(document: Document, assignments) -> Document:
    """建議套回文件（不可變）：None 維持原樣式，其餘換段落樣式名（runs 等欄位保留）。"""
    if len(assignments) != len(document.paragraphs):
        raise ValueError(
            f"建議數與段落數長度不符：{len(assignments)} vs {len(document.paragraphs)}")
    paragraphs = tuple(
        p if style is None or style == p.style else dataclasses.replace(p, style=style)
        for p, style in zip(document.paragraphs, assignments)
    )
    return dataclasses.replace(document, paragraphs=paragraphs)
