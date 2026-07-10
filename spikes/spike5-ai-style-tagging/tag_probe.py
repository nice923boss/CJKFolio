"""Spike 5 PoC：驗證私有 LLM 能否對書稿段落做結構分類（AI 樣式指派的核心）。

設計原則（呼應 PLAN 分工）：AI 只回「段落 → 樣式名」對映，
版面幾何一律由排版引擎確定性計算，不採用 AI 輸出的任何數字。
素材為自擬段落（不用參考書文字，守版權紅線）。
設定讀自 local/ai-config.local.json（金鑰不入原始碼）。
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CONFIG = json.loads(
    (Path(__file__).parents[2] / "local" / "ai-config.local.json").read_text("utf-8")
)

STYLES = ["章名大標", "章節小標", "內文", "引文", "訪談發言", "個案大標"]

# (段落, 預期樣式)
SAMPLES = [
    ("第三章　把空間還給自己", "章名大標"),
    ("整理不是丟東西", "章節小標"),
    ("每一次的整理，其實都是與過去的自己對話。我們留下的物品，記錄著某段時間的樣子；而願意放手的那一刻，往往才是新生活真正的開始。", "內文"),
    ("「留下來的每一件物品，都該有它自己的位置。」", "引文"),
    ("廖：你當初是怎麼開始接觸整理這件事的？", "訪談發言"),
    ("鄧：其實是從一次搬家開始的。那時候我看著滿屋子的紙箱，突然不知道這些東西為什麼跟著我。", "訪談發言"),
    ("Case 3　與母親的衣櫃和解", "個案大標"),
    ("衣櫃深處那件二十年前的洋裝，她一直捨不得丟。直到那天下午，她把它攤在床上，拍了一張照片，然後輕輕放進回收袋。", "內文"),
]

SYSTEM = (
    "你是書籍排版助手。針對輸入的每個段落，從以下樣式中選一個："
    + "、".join(STYLES)
    + "。只輸出 JSON 陣列，格式 [{\"index\": 數字, \"style\": \"樣式名\"}]，不要任何解釋。"
)


def call_llm(paragraphs):
    user = "\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs))
    body = json.dumps({
        "model": CONFIG["model"],
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }).encode("utf-8")
    req = urllib.request.Request(
        CONFIG["base_url"].rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + CONFIG["api_key"],
        },
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)  # 剝 thinking 殼
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        raise ValueError(f"回應中無 JSON 陣列：{text[:300]}")
    return json.loads(m.group(0)), data.get("usage", {})


def main():
    result, usage = call_llm([p for p, _ in SAMPLES])
    tagged = {item["index"]: item["style"] for item in result}
    correct = 0
    for i, (para, expect) in enumerate(SAMPLES):
        got = tagged.get(i, "(缺)")
        ok = got == expect
        correct += ok
        print(f"[{i}] {'O' if ok else 'X'} 預期={expect}  模型={got}  | {para[:18]}")
    print(f"\n正確率：{correct}/{len(SAMPLES)}　tokens：{usage}")
    print("判定：", "可行（達初稿門檻 7/8）" if correct >= 7 else "未達門檻，需調 prompt 或重估")


if __name__ == "__main__":
    main()
