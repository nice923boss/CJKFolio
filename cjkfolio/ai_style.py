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

送出節流與重試（Sprint 143）：批次送出受 _Pacer 的滑動視窗節流（每分鐘至多
config.requests_per_minute 次），且暫時性失敗（503／429／5xx／逾時／連線失敗）
退避重試而非直接降級，因為降級就是「這批段落維持原樣式」，對使用者而言等於指派
沒做完，能重試就不該讓一次 503 定生死。重試同樣走節流計數，故不會偷偷超過上限。

回應長度守門（Sprint 148）：分批只看輸入字數會漏掉「短段多」的稿件，因為回應
長度是隨**段數**成長（一段一項 JSON），與輸入字數無關。故段數另設上限，
max_tokens 亦由該批段數推算並為推理型模型的 reasoning_content 預留額度；萬一
仍被截斷，逐項搶救已寫完的建議而非整批報廢，並據實說明只採用了幾項。
"""
import dataclasses
import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass

from .ai_config import AiConfig
from .document import Document

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
# 物件陣列的起頭（「[」後接「{」）：推理文字裡的 [12] 這種段號標記不算陣列。
# 舊式貪婪比對 \[[\s\S]*\] 會把整段推理文字誤當陣列，報出「Extra data」這種
# 看不懂的錯（Sprint 148 實測，見下方 _extract_items）。
_ARRAY_START_RE = re.compile(r"\[\s*\{")
_ITEM_RE = re.compile(r"\{[^{}]*\}")   # 截斷時逐項搶救（每項都是扁平物件）

# 單批段數上限：**回應長度隨段數線性成長，與輸入字數無關**。真稿《一路走來，
# 恩典相伴》一批 114 段只有 2,983 字（短段多，過得了 batch_char_limit），輸出
# 卻要 114 項 JSON，實測 completion_tokens 撞滿 max_tokens 被截斷（見 _max_tokens）。
_BATCH_ITEMS = 40
# 單段回應的 token 預算：實測 40 段的 JSON 本體約 1,630 字（約 20〜25 tokens／段），
# 帶 toc_title 的長項更貴，取 80 留餘裕。
_TOKENS_PER_ITEM = 80
# 推理型模型的 reasoning_content 也吃 max_tokens，且**它才是主成本**：同一批 40 段
# 實測 completion 3,364〜4,986 tokens，其中 JSON 本體只佔約 800，其餘全是推理，
# 且同一份輸入兩次跑的推理長度差到 1.2 倍。不留足額度就會「推理推完、JSON 一個字
# 都還沒寫」而整批報廢（本書前 40 段在 5,200 額度下即如此）。
_REASONING_RESERVE = 6000

# 值得重試的 HTTP 狀態：伺服器端暫時性，同一份輸入再送一次有機會成功。
# 401／403（金鑰錯）、400（請求壞）、404（路徑錯）不在其中：重試必然重現。
_RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_RETRIES = 3          # 一批最多重送 3 次（合計最多 4 次送出）
_BACKOFF_BASE = 5.0       # 指數退避 5、10、20 秒
_BACKOFF_MAX = 60.0       # 退避與 Retry-After 的共同上限（背景執行緒不可無限等）
_WINDOW = 60.0            # 節流視窗＝一分鐘


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


class _Pacer:
    """送出節流器：每分鐘至多 per_minute 次（滑動視窗）；now／sleep 可注入。

    視窗記的是**實際送出**的時刻，重試也記一筆，故重試不會偷偷超過上限。
    per_minute <= 0＝不節流（無限額的自架 endpoint）。
    退避等待也走本物件的 sleep，測試注入一份假時鐘即可全程零真實等待。
    """

    def __init__(self, per_minute: int, *, now=time.monotonic, sleep=time.sleep) -> None:
        self._per_minute = per_minute
        self._now = now
        self._sleep = sleep
        self._sent = deque()   # 視窗內的送出時刻（單調遞增）

    def wait(self) -> float:
        """必要時等到視窗有空位再放行，並記下這次送出；回實際等待秒數。"""
        waited = 0.0
        while self._per_minute > 0:
            self._expire()
            if len(self._sent) < self._per_minute:
                break
            gap = _WINDOW - (self._now() - self._sent[0])
            self.sleep(gap)
            waited += gap
            # 剛才就是為了等這一筆過期才睡的，直接汰除而不再比時刻：時鐘解析度
            # 不足時（gap 小到加不進浮點時刻）比時刻會永遠汰不掉，變成空轉
            self._sent.popleft()
        self._sent.append(self._now())
        return waited

    def sleep(self, seconds: float) -> None:
        """退避等待（重試用）；與節流共用同一個可注入的 sleep。"""
        if seconds > 0:
            self._sleep(seconds)

    def _expire(self) -> None:
        now = self._now()
        while self._sent and now - self._sent[0] >= _WINDOW:
            self._sent.popleft()


def _retry_after(exc) -> float:
    """伺服器指定的 Retry-After 秒數；無／不是純秒數（HTTP-date 形態）回 -1。"""
    headers = getattr(exc, "headers", None)
    raw = headers.get("Retry-After") if headers is not None else None
    try:
        return min(max(float(raw), 0.0), _BACKOFF_MAX)
    except (TypeError, ValueError):
        return -1.0


def _retry_wait(exc: Exception, attempt: int):
    """可重試就回等待秒數，不可重試回 None。

    可重試＝伺服器端暫時性（服務不可用、過量、逾時、連線失敗）。回應格式錯誤
    （ValueError／KeyError）不重試：同一份輸入必然重現，重試只是白花配額。
    伺服器有給 Retry-After 就照它的（上限 _BACKOFF_MAX），沒有才用指數退避。
    """
    if isinstance(exc, urllib.error.HTTPError):   # 是 URLError 的子類，先判
        if exc.code not in _RETRY_STATUS:
            return None
        after = _retry_after(exc)
        if after >= 0:
            return after
    elif not isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return None
    return min(_BACKOFF_BASE * 2 ** attempt, _BACKOFF_MAX)


def _post_with_retry(post, args, pacer: _Pacer, note) -> dict:
    """送出一批；暫時性失敗退避重試，重試次數用完或不可重試即上拋（由上層降級）。

    note(exc, 第幾次, 等待秒數)＝據實記錄每次重試（警告不沉默：使用者要看得到
    「試過了、等了多久」，不是只看到最後一次的錯誤訊息）。
    """
    attempt = 0
    while True:
        pacer.wait()
        try:
            return post(*args)
        except Exception as exc:
            wait = _retry_wait(exc, attempt) if attempt < _MAX_RETRIES else None
            if wait is None:
                raise
            note(exc, attempt + 1, wait)
            pacer.sleep(wait)
            attempt += 1


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


def _batches(texts, batch_char_limit: int, batch_item_limit: int = _BATCH_ITEMS):
    """依字數與段數雙上限切批（段落不跨批，單段超限自成一批）；產出 (起始索引, 段列表)。

    段數上限是 Sprint 148 補的：字數上限管的是**送進去**的量，回應長度卻是隨
    **段數**成長（一段一項 JSON），短段多的稿件會過得了字數關卻在回應端被截斷。
    """
    start, bucket, size = 0, [], 0
    for i, text in enumerate(texts):
        if bucket and (size + len(text) > batch_char_limit
                       or len(bucket) >= batch_item_limit):
            yield start, bucket
            start, bucket, size = i, [], 0
        bucket.append(text)
        size += len(text)
    if bucket:
        yield start, bucket


def _max_tokens(item_count: int) -> int:
    """該批的回應 token 上限＝推理預留＋每段預算（不寫死常數）。

    寫死 4000 的舊值對短段多的批次不夠用：114 段需要 114 項 JSON，加上推理型
    模型自己的 reasoning_content，實測正好撞滿 4000 而停在陣列中途。
    """
    return _REASONING_RESERVE + _TOKENS_PER_ITEM * item_count


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


def _salvage_items(chunk: str):
    """從沒收尾的陣列裡撿出已寫完的項（解析不了的殘項直接跳過）。"""
    items = []
    for m in _ITEM_RE.finditer(chunk):
        try:
            item = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def _extract_items(text: str, truncated: bool):
    """回應文字 → (項目列, 是否只搶救到局部)。

    回應被輸出長度上限截斷時，AI 停在陣列中途、沒有收尾的「]」，整份 json.loads
    必失敗。此時**整批丟掉等於數十段指派沒做**，而已寫完的那些項本身完整可信，
    故逐項搶救；沒搶救到任何一項才上拋（由上層降級該批）。
    """
    start = _ARRAY_START_RE.search(text)
    if start:
        chunk = text[start.start():]
        end = chunk.rfind("]")
        if end >= 0:
            try:
                items = json.loads(chunk[:end + 1])
            except json.JSONDecodeError:
                items = None
            if isinstance(items, list):
                return items, False
        salvaged = _salvage_items(chunk)
        if salvaged:
            return salvaged, True
    hint = "（回應被輸出長度上限截斷）" if truncated else ""
    raise ValueError(f"回應中無 JSON 陣列{hint}（前 120 字）：{text[:120]}")


def _parse_assignments(payload: dict, count: int, candidates: set):
    """回應 → (逐段樣式列, 逐段目錄條目列, 警告列表)；兩條位置列等長且與批內段對齊。

    樣式名不在候選集即拒（幻覺守門）；目錄欄位獨立守門，樣式被拒不連坐目錄條目
    （反之亦然），兩者各自可用即各自留下。
    """
    choice = payload["choices"][0]
    msg = choice["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    text = _THINK_RE.sub("", text)
    cut = choice.get("finish_reason") == "length"
    items, partial = _extract_items(text, cut)
    slots = [None] * count
    toc_slots = [None] * count
    warnings = []
    if partial:
        # 搶救成功也要說：使用者看到的是「這批只改了一半」，不說等於沉默降級
        why = "被輸出長度上限截斷" if cut else "格式不完整"
        warnings.append(
            f"AI 回應{why}，只採用已寫完的 {len(items)}／{count} 項建議"
            "（其餘維持原樣式）")
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
    pacer=None,
) -> SuggestResult:
    """對每段文字取得樣式建議；批次失敗降級該批 None 並列警告（不擋流程）。

    toc_levels＝模版 auto_toc.level_hints()（選配）：把本書已宣告的目次層級語意
    寫進 prompt，未帶則退回通則說明（見 _level_prompt）。

    送出速率取 config.requests_per_minute（Sprint 143）：節流視窗只涵蓋這一次
    呼叫，同一把金鑰若同時被別的程式或另一次指派使用，加總仍可能超過服務端限額
    （GAPS #101）。pacer 注入＝測試用假時鐘（注入時 config 的速率不再生效）。
    """
    for field in ("base_url", "model"):
        if not getattr(config, field):
            raise ValueError(f"AI 設定不完整：{field} 為空（見 local/ai-config.local.json）")
    post = transport or _post_json
    gate = pacer if pacer is not None else _Pacer(config.requests_per_minute)
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
            "max_tokens": _max_tokens(len(bucket)),
        }).encode("utf-8")
        label = f"批次 {batches}（段 {start}〜{start + len(bucket) - 1}）"
        retried = []

        def note(exc, nth, wait, label=label):
            """重試據實入警告列（成功收尾也留著：使用者要看得到中途發生過什麼）。"""
            retried.append(nth)
            warnings.append(_sanitize(
                f"{label}第 {nth} 次送出失敗，{wait:.0f} 秒後重試：{exc}",
                config.api_key))

        try:
            payload = _post_with_retry(post, (url, headers, body, timeout), gate, note)
            slots, toc_slots, batch_warnings = _parse_assignments(
                payload, len(bucket), candidate_set)
        except Exception as exc:  # 降級不擋流程（§4.4），警告不沉默
            # 該批樣式與目錄條目一併維持 None：目錄條目源自同一次回應，
            # 回應沒回來就沒有半份可信的目錄建議。
            tried = f"（已送出 {len(retried) + 1} 次）" if retried else ""
            warnings.append(_sanitize(
                f"{label}AI 指派失敗{tried}，維持原樣式：{exc}", config.api_key))
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
