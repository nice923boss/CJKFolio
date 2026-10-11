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

設定錯誤即停與進度回報（Sprint 149）：401／403／404 代表金鑰、Base URL 或 Model
填錯，每一批都必然重現，舊行為是逐批降級後開出一張「全部無建議」的校正表，
使用者看不出是金鑰錯。故第一次撞到即拋 AiConfigProblem（訊息已換成白話並指出
去哪裡改），不再送後續批次。progress 回呼逐批回報，全書級指派常需數分鐘，
沒有進度等於讓使用者以為當機。check_connection 給設定面板的「測試連線」用。

全書標題一覽（Sprint 149）：分批送出時每批只看得到自己那 40 段，同一種編號的
小節（「一、」「二、」）會在不同批被判成不同樣式與目次層級（真稿實測）。故每批
的系統提示附上全書短段一覽，並明訂同編號格式須給同一樣式與層級。

長段只送段首（Sprint 149）：判樣式只需段首與段長，全文送出反而讓推理型模型
逐字推敲，真稿 docx 8 段 1,806 字一批就把 6,640 tokens 推理額度吃光、回應被截斷
而 0／8。故超過 _EXCERPT_CHARS 的段只送段首並註明全段字數；回應的 index 不變。

截斷拆批重送與輸出上限（Sprint 149）：回應被截斷時，沒拿到建議的段對半拆開
重送，一路拆到單段；單段仍截斷才放棄並指出可調高 AI 設定的「輸出上限」
（config.max_output_tokens，0＝依段數推算）。重送不算新批次。

同樣式目次一致化（Sprint 150）：提示詞約束不住跨批一致，故收尾時以確定性規則
補齊：同一建議樣式只要有一段列入目次，其餘疑似標題的短段一併列入，層級取多數
（見 _harmonize_toc）。

同編號目次一致化（Sprint 159）：同一份輸入、同一批，AI 仍可能只把「四、」到「七、」
列入目次並判成起新頁的大標題，「一、」到「三、」卻留內文不列（真稿《認真過好
每一刻的人生》實測，重跑又全對）。同樣式一致化救不了：段首引題整段是內文，預設
內文不參與。故再以段首編號格式（「一、」「（一）」「第X章」「1、」）分組補齊：
組內只要有一段列入目次，其餘可取出標題者一併列入；段首引題（引題後直接接內文）
一律回內文樣式，獨立標題段之間統一為多數樣式（見 ai_toc_harmony）。

前言（Sprint 159）：第一個目次條目之前還有內文時，建議在那段內文之前插入一段
「前言」標題並列入目次（同層），否則目次第一條之前的文字在目次上無處可指。
是否插入由校正對話框勾選，插入本身在 editing.insert_preface（建議見 ai_toc_harmony）。
"""
import dataclasses
import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Optional

from .ai_config import AiConfig
from .document import Document
from .ai_toc_harmony import (
    _OUTLINE_MAX_CHARS, _harmonize_numbered, _harmonize_toc, _heading_like, _preface_at,
)

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

# 設定錯誤：金鑰無效／無權限／端點或模型不存在。重試與換下一批都必然重現，
# 第一次撞到就停（Sprint 149）。
_FATAL_STATUS = frozenset({401, 403, 404})
_HTTP_HINTS = {
    401: "API Key 無效或已過期",
    403: "API Key 無效，或沒有使用此模型的權限",  # NVIDIA 對錯的金鑰回 403（實測）
    404: "找不到端點或模型，請確認 Base URL 與 Model",
    429: "請求過量，已超過服務端限額",
}
_SETTINGS_HINT = "請到「設定 → AI 設定…」修正，並按「測試連線」確認"

# 送給 AI 的每段上限：超過只送段首（標題、引題、編號都在段首）並註明全段字數
_EXCERPT_CHARS = 60

# 全書標題一覽的條目上限（防長書把提示撐爆；字形判準見 ai_toc_harmony）
_OUTLINE_MAX_ITEMS = 150

# 漏回警告最多列出的段號數（其餘以「等 N 段」帶過）
_MISSING_SHOWN = 10


class AiConfigProblem(RuntimeError):
    """設定錯誤（金鑰、Base URL、Model）：訊息已白話化且不含金鑰值。"""


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
    # (段序, 目次層級, 樣式)＝建議在該段前插入「前言」標題（Sprint 159）；None＝不建議
    preface: Optional[tuple] = None


def _post_json(url: str, headers: dict, body: bytes, timeout: float) -> dict:
    """預設 transport：OpenAI 相容 chat/completions POST（測試注入替身取代）。"""
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 服務端的錯誤說明（如 "Authentication failed"）只在回應本體裡，
        # 不先讀出來，使用者只看得到一個狀態碼
        try:
            exc.detail = exc.read(300).decode("utf-8", "replace").strip()
        except OSError:
            exc.detail = ""
        raise


def describe_error(exc: Exception, secret: str = "") -> str:
    """連線／HTTP 錯誤 → 使用者看得懂的一句話（不含金鑰值）。"""
    if isinstance(exc, urllib.error.HTTPError):
        hint = _HTTP_HINTS.get(exc.code)
        if hint is None:
            hint = "服務暫時無法使用" if exc.code >= 500 else "服務端拒絕請求"
        detail = getattr(exc, "detail", "")
        text = f"{hint}（HTTP {exc.code}）" + (f"：{detail}" if detail else "")
    elif isinstance(exc, urllib.error.URLError):
        text = f"連不上伺服器，請確認 Base URL 與網路：{exc.reason}"
    elif isinstance(exc, TimeoutError):
        text = "等待回應逾時"
    else:
        text = str(exc)
    return _sanitize(text, secret)


def _is_fatal(exc: Exception) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code in _FATAL_STATUS


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


def _system_prompt(candidates, default_style: str, toc_levels=(), outline=()) -> str:
    return (
        "你是書籍排版助手。針對輸入的每個段落，從以下段落樣式清單中選一個最合適的："
        + "、".join(candidates)
        + f"。逐段判斷內容結構（章名／小標／引文／內文等）；不確定時一律選「{default_style}」。"
        + "另外，若該段是應列入目次的標題（部名、篇名、章名、序文標題等），"
        + "再加兩個欄位：toc_title＝目次要顯示的文字（通常即該段文字，可去掉多餘空白），"
        + "toc_level＝目次層級的正整數。"
        + _level_prompt(toc_levels)
        + "不列入目次的段落（內文、引文等）不要輸出這兩個欄位。"
        + "toc_title 照該段原文，保留「第一章」「一、」等編號。"
        + "同一種編號格式的標題（如「第X章」一類、「一、」一類）全書必須給同一個樣式"
        + "與同一個目次層級，要列入目次就全部列入，不列就全部不列。"
        + "稿件開頭若附有作者手寫的目錄，以它列出的條目決定哪些標題列入目次；"
        + "手寫目錄本身（「目錄」二字與其條目）指派清單中的目錄類樣式且不列入目次，"
        + "排版程式會以自動生成的目次取代它。"
        + "段首引題（如「一、求學階段：」後面直接接內文）整段仍是內文樣式，"
        + "要列入目次時 toc_title 只取引題本身（到冒號為止，不含冒號）。"
        + "超過 " + str(_EXCERPT_CHARS) + " 字的段落只給段首並註明全段字數，"
        + "依段首判斷即可。"
        + _outline_prompt(outline)
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


def _outline(texts) -> tuple:
    """全書疑似標題的短段（依序）；給 AI 判斷層級一致的上下文，非判定依據。"""
    out = []
    for text in texts:
        t = text.strip()
        if _heading_like(t):
            out.append(t)
            if len(out) >= _OUTLINE_MAX_ITEMS:
                break
    return tuple(out)


def _excerpt(text: str) -> str:
    """長段只送段首並註明全段字數（判樣式不需全文，全文只會撐大推理量）。"""
    if len(text) <= _EXCERPT_CHARS:
        return text
    return f"{text[:_EXCERPT_CHARS]}……（以下省略，全段 {len(text)} 字）"


def _outline_prompt(outline) -> str:
    if not outline:
        return ""
    return ("輸入只是全書的一部分；全書疑似標題的短段依序如下，供你判斷層級一致"
            "（只需輸出本次輸入的段落）：" + "／".join(outline) + "。")


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


def _max_tokens(item_count: int, configured: int = 0) -> int:
    """該批的回應 token 上限＝推理預留＋每段預算（不寫死常數）。

    寫死 4000 的舊值對短段多的批次不夠用：114 段需要 114 項 JSON，加上推理型
    模型自己的 reasoning_content，實測正好撞滿 4000 而停在陣列中途。
    configured＞0＝使用者在 AI 設定填的輸出上限，照用不推算（Sprint 149）。
    """
    if configured > 0:
        return configured
    return _REASONING_RESERVE + _TOKENS_PER_ITEM * item_count


def _halves(positions: tuple) -> list:
    """截斷重送的拆法：兩段以上對半拆，只剩一段就單獨重送。"""
    if len(positions) < 2:
        return [positions]
    mid = len(positions) // 2
    return [positions[:mid], positions[mid:]]


def _span(positions: tuple) -> str:
    """原段索引（0 起算）→ 訊息用段號（1 起算，與校正表列號一致，Sprint 152）。"""
    first, last = positions[0] + 1, positions[-1] + 1
    return f"段 {first}" if len(positions) == 1 else f"段 {first}〜{last}"


def _sanitize(message: str, secret: str) -> str:
    """警告訊息不回帶金鑰值（紅線）。"""
    return message.replace(secret, "［api_key 已遮蔽］") if secret else message


def _parse_toc_entry(item: dict, number: int, warnings: list):
    """單項的目錄欄位 → (標題, 層級) 或 None；守門鏡射 document._paragraph_toc_from_dict。

    存檔端（document@2）明訂 toc_title 須非空字串、toc_level 須 ≥1 整數、且
    toc_level 不得單獨出現。這裡先擋，才不會讓一份「看起來套用成功」的稿件到
    存檔時才炸 DocumentError（同 import_core 不把可在邊界判定的錯留給下游）。
    number＝訊息用段號（1 起算）。
    """
    title = item.get("toc_title")
    level = item.get("toc_level")
    if title is None and level is None:
        return None
    if title is None:
        warnings.append(f"AI 只給 toc_level 未給 toc_title，忽略目錄條目（段 {number}）")
        return None
    if not (isinstance(title, str) and title.strip()):
        warnings.append(f"AI 目錄標題非非空字串，忽略：{title!r}（段 {number}）")
        return None
    if level is None:
        level = 1
    # 真布林是 int 的子類，True 會被當成層級 1；目錄層級只收真整數
    if isinstance(level, bool) or not isinstance(level, int) or level < 1:
        warnings.append(f"AI 目錄層級非 ≥1 整數，忽略：{level!r}（段 {number}）")
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


class _Truncated(ValueError):
    """回應被輸出長度上限截斷且一項都沒寫完（由上層拆小批重送）。"""


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
    if truncated:
        raise _Truncated(f"回應中無 JSON 陣列（回應被輸出長度上限截斷）（前 120 字）：{text[:120]}")
    raise ValueError(f"回應中無 JSON 陣列（前 120 字）：{text[:120]}")


def _parse_assignments(payload: dict, count: int, candidates: set, numbers=None):
    """回應 → (逐段樣式列, 逐段目錄條目列, 警告列表, 截斷而沒回到的批內索引)。

    樣式名不在候選集即拒（幻覺守門）；目錄欄位獨立守門，樣式被拒不連坐目錄條目
    （反之亦然），兩者各自可用即各自留下。被截斷時回報哪些段 AI 還沒寫到，
    由上層拆小批重送（Sprint 149），故此處不另發「只採用幾項」的警告。
    回應完整卻漏回某些段時據實警告（Sprint 151）；numbers＝批內索引對應的原段
    索引（0 起算，未帶即批內索引）。警告裡的段號一律換算成 1 起算，與校正表列號
    一致（Sprint 152）。
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
    if partial and not cut:
        # 搶救成功也要說：使用者看到的是「這批只改了一半」，不說等於沉默降級
        warnings.append(
            f"AI 回應格式不完整，只採用已寫完的 {len(items)}／{count} 項建議"
            "（其餘維持原樣式）")
    answered = set()

    def number(i):
        return (numbers[i] if numbers else i) + 1

    for item in items:
        idx = item.get("index")
        style = item.get("style")
        if not isinstance(idx, int) or not 0 <= idx < count:
            warnings.append(f"AI 回應 index 越界忽略：{idx!r}")
            continue
        answered.add(idx)
        toc_slots[idx] = _parse_toc_entry(item, number(idx), warnings)
        if style not in candidates:
            warnings.append(f"AI 建議樣式不在模版候選集，忽略：{style!r}（段 {number(idx)}）")
            continue
        slots[idx] = style
    missing = tuple(i for i in range(count) if i not in answered)
    if cut:
        return slots, toc_slots, warnings, missing
    if missing and not partial:   # 格式殘缺已有「只採用幾項」的警告，不重複
        shown = [str(number(i)) for i in missing]
        more = f" 等 {len(shown)} 列" if len(shown) > _MISSING_SHOWN else ""
        warnings.append(f"AI 回應漏回校正表第 {'、'.join(shown[:_MISSING_SHOWN])}{more} 列"
                        "，該列維持原樣式（可重跑指派補上）")
    return slots, toc_slots, warnings, ()


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
    progress=None,
) -> SuggestResult:
    """對每段文字取得樣式建議；批次失敗降級該批 None 並列警告（不擋流程）。

    toc_levels＝模版 auto_toc.level_hints()（選配）：把本書已宣告的目次層級語意
    寫進 prompt，未帶則退回通則說明（見 _level_prompt）。

    送出速率取 config.requests_per_minute（Sprint 143）：節流視窗只涵蓋這一次
    呼叫，同一把金鑰若同時被別的程式或另一次指派使用，加總仍可能超過服務端限額
    （GAPS #101）。pacer 注入＝測試用假時鐘（注入時 config 的速率不再生效）。

    progress(已完成批數, 總批數, 說明)：每批送出前、重試等待前與全部結束時呼叫。
    金鑰／端點／模型錯誤（401／403／404）拋 AiConfigProblem 並停送後續批次
    （Sprint 149）。
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
    plan = list(_batches(texts, batch_char_limit))
    report = progress or (lambda done, total, note: None)
    system = _system_prompt(candidates, default_style, toc_levels, _outline(texts))

    def request(positions: tuple, label: str, done: int) -> tuple:
        """送出一個請求並把建議寫回原段位置；回傳被截斷而沒拿到建議的原段索引。"""
        retried = []

        def note(exc, nth, wait):
            """重試據實入警告列（成功收尾也留著：使用者要看得到中途發生過什麼）。"""
            retried.append(nth)
            reason = describe_error(exc, config.api_key)
            warnings.append(f"{label}第 {nth} 次送出失敗，{wait:.0f} 秒後重試：{reason}")
            report(done, len(plan), f"{label}{reason}，{wait:.0f} 秒後重試")

        body = json.dumps({
            "model": config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n".join(
                    f"[{i}] {_excerpt(texts[p])}" for i, p in enumerate(positions))},
            ],
            "temperature": 0.2,
            "max_tokens": _max_tokens(len(positions), config.max_output_tokens),
        }).encode("utf-8")
        try:
            payload = _post_with_retry(post, (url, headers, body, timeout), gate, note)
            slots, toc_slots, batch_warnings, unanswered = _parse_assignments(
                payload, len(positions), candidate_set, positions)
        except _Truncated:
            return positions   # 一項都沒寫完：整批交給上層拆小批重送
        except Exception as exc:  # 降級不擋流程（§4.4），警告不沉默
            if _is_fatal(exc):  # 設定錯誤：後續批次必然重現，停送並明說去哪改
                raise AiConfigProblem(
                    f"{describe_error(exc, config.api_key)}。{_SETTINGS_HINT}") from None
            # 該批樣式與目錄條目一併維持 None：目錄條目源自同一次回應，
            # 回應沒回來就沒有半份可信的目錄建議。
            tried = f"（已送出 {len(retried) + 1} 次）" if retried else ""
            warnings.append(
                f"{label}AI 指派失敗{tried}，維持原樣式：{describe_error(exc, config.api_key)}")
            return ()
        warnings.extend(_sanitize(w, config.api_key) for w in batch_warnings)
        for p, style, toc in zip(positions, slots, toc_slots):
            assignments[p], toc_entries[p] = style, toc
        return tuple(positions[i] for i in unanswered)

    for batches, (start, bucket) in enumerate(plan, 1):
        report(batches - 1, len(plan),
               f"第 {batches}／{len(plan)} 批送出中（{_span(range(start, start + len(bucket)))}）")
        # 截斷時把沒拿到建議的段拆半重送，遞迴到單段為止（Sprint 149）：截斷是
        # 推理加 JSON 超過輸出上限，段少了兩者都縮小；每次重送的段數必然比上一次少，
        # 故一定收斂。單段仍被截斷才放棄，並指出可調高 AI 設定的輸出上限。
        pending = [(tuple(range(start, start + len(bucket))),
                    f"批次 {batches}（{_span(range(start, start + len(bucket)))}）")]
        while pending:
            positions, label = pending.pop(0)
            missing = request(positions, label, batches - 1)
            if not missing:
                continue
            if len(positions) == 1:
                warnings.append(f"{label}回應被輸出長度上限截斷，維持原樣式；"
                                "可到「設定 → AI 設定…」調高「輸出上限」")
                continue
            parts = _halves(missing)
            warnings.append(
                f"{label}回應被輸出長度上限截斷，已採用 {len(positions) - len(missing)}"
                f"／{len(positions)} 項，其餘 {len(missing)} 段拆成 {len(parts)} 小批重送")
            report(batches - 1, len(plan),
                   f"{label}回應被截斷，其餘 {len(missing)} 段拆小批重送")
            pending[:0] = [(part, f"批次 {batches} 重送（{_span(part)}）") for part in parts]
    toc_entries, notes = _harmonize_toc(texts, assignments, toc_entries, default_style)
    warnings.extend(notes)
    toc_styles = {style for _level, style, _wants in toc_levels}
    assignments, toc_entries, notes = _harmonize_numbered(
        texts, assignments, toc_entries, default_style, toc_styles)
    warnings.extend(notes)
    report(len(plan), len(plan), f"{len(plan)} 批全部回應")
    return SuggestResult(tuple(assignments), tuple(warnings), len(plan),
                         tuple(toc_entries),
                         _preface_at(texts, assignments, toc_entries, default_style))


def check_connection(config: AiConfig, *, transport=None, timeout: float = 60.0) -> str:
    """設定面板「測試連線」：送一則極短請求，成功回說明文字，失敗拋 AiConfigProblem。

    驗的是 Base URL、API Key、Model 三者能不能通（HTTP 200 且回應有 choices），
    不驗模型會不會正確指派樣式。max_tokens 給小值：推理型模型可能因額度用完而
    沒有正文，但服務端已接受金鑰與模型，對「設定對不對」而言已足夠。
    """
    for field, name in (("base_url", "Base URL"), ("model", "Model")):
        if not getattr(config, field):
            raise AiConfigProblem(f"{name} 未填")
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = "Bearer " + config.api_key
    body = json.dumps({
        "model": config.model,
        "messages": [{"role": "user", "content": "請回覆 OK"}],
        "max_tokens": 16,
    }).encode("utf-8")
    url = config.base_url.rstrip("/") + "/chat/completions"
    began = time.monotonic()
    try:
        payload = (transport or _post_json)(url, headers, body, timeout)
        payload["choices"][0]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AiConfigProblem(
            f"服務端有回應但格式不是 OpenAI 相容的 chat/completions：{exc}") from None
    except Exception as exc:  # noqa: BLE001（網路／HTTP 任何失敗都轉白話）
        raise AiConfigProblem(describe_error(exc, config.api_key)) from None
    return f"連線成功：{config.model} 已回應（{time.monotonic() - began:.1f} 秒）"


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
