"""Spike 19 探針二：行首行尾字面調整的斷行迭代收斂機制（GAPS #50 (c) 的 R2 PoC）。

問題（GAPS #50 (c) 原文）：行首／行尾字面調整「與斷行互為因果（壓縮改容量、容量改
行邊界）需迭代收斂機制」，v1 因此不做以維持斷行確定性。本探針用資料回答兩件事：

  Q1 這個情境在真實素材出現得多頻繁？（不頻繁＝不值得為它引入迭代）
  Q2 迭代收斂機制到底可不可行？收斂率、振盪率、成本各是多少？

兩個候選模型：

  模型 A（單向，不回饋容量）：先照現行規則斷行，再依行首／行尾套 0.5 字面調整。
    調整只改字形落點與齊行分配，不回頭改斷行 → 行邊界與現行完全相同，確定性維持。
  模型 B（回饋容量，迭代求不動點）：把調整後省下的半格還給行容量，重新斷行，
    直到「行邊界導出的調整」與「調整導出的行邊界」一致。

**成功標準（動工前定，R2）**：模型 B 四條全過才算 PoC 通過，否則據實登記不實作。

  S1 收斂率：≥ 95% 段落在 ≤ 3 輪內達不動點
  S2 終止確定性：偵測到循環時有明確回退（退回未調整版本）且事件可觀察，不沉默
  S3 品質不退：收斂後 check_kinsoku 0 違規、check_overflow 0 筆
  S4 成本可量：據實記錄排版耗時倍數（不預設門檻）

素材：repo 內 `samples/*.md`，外加呼叫端以命令列顯式指定的外置素材（`python
probe_edge_converge.py <txt 路徑>...`）。**本檔不內含任何本機書稿路徑**（同
`tests/test_long_book_tool.py` 釘死的素材外置紅線，GAPS #63）。

另記錄決策所需的兩個數字：

  D1 模型 B 與模型 A 的行邊界差異行數。差異為 0 代表迭代除了成本什麼也沒換到。
  D2 模型 A 的齊行抵銷率：非段末行齊行以 `advance_pt * cap / used` 均勻放大字距
     （layout.line_justified_advance）。模型 A 不回饋容量，省下的半格會落進 used
     的缺口被齊行分回字間，行首行尾的視覺目的因此落空。此數字量的就是「有多少
     命中行會被齊行抵銷」。
"""
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

from cjkfolio.engine import (  # noqa: E402
    SQUEEZE_CLOSERS,
    SQUEEZE_OPENERS,
    break_cells,
    check_kinsoku,
    check_overflow,
    normalize,
    squeeze_punctuation,
    tokenize,
)
from cjkfolio.layout import line_justified_advance  # noqa: E402

EDGE_WIDTH = 0.5   # §3.1.6.2 縮減二分之一個漢字
MAX_ROUNDS = 8     # 上限：超過即判未收斂（S1 只認 ≤ 3）
CAPS = (20, 25, 30, 35, 40)
INDENT = 2

ROOT = Path(__file__).resolve().parents[2]


def paragraphs(text: str) -> list:
    """取純內文段落：跳過 markdown 標題與空行。"""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def base_cells(text: str) -> list:
    """現行管線的段落 cells：正規化 → tokenize → 位置無關的相鄰約物擠壓。"""
    return squeeze_punctuation(tokenize(normalize(text), vertical=True))


def edge_adjust(base: list, lines: list) -> list:
    """依行邊界回推字面調整：行首開括號、行尾閉括號各讓出半格。

    每輪都從 base 重算（不在前一輪結果上累加），故同一枚最多只被減一次；
    已因相鄰擠壓變 0.5 者跳過（CLREQ 未定義累加量，同 GAPS #50 (g) 的立場）。
    """
    out = list(base)
    i = 0
    for line in lines:
        n = len(line.cells)
        if n:
            head, tail = out[i], out[i + n - 1]
            if head.width == 1 and head.text in SQUEEZE_OPENERS:
                out[i] = replace(head, width=EDGE_WIDTH)
            if tail.width == 1 and tail.text in SQUEEZE_CLOSERS:
                out[i + n - 1] = replace(tail, width=EDGE_WIDTH)
        i += n
    return out


def model_a_lines(base: list, lines: list) -> list:
    """模型 A：行邊界照舊，只把字面調整套進各行 cells（不回頭改斷行）。"""
    adjusted = edge_adjust(base, lines)
    out, i = [], 0
    for line in lines:
        n = len(line.cells)
        out.append(replace(line, cells=tuple(adjusted[i:i + n])))
        i += n
    return out


def widths(cells: list) -> tuple:
    return tuple(c.width for c in cells)


def bounds(lines: list) -> tuple:
    return tuple(len(line.cells) for line in lines)


def converge(base: list, cap: int) -> dict:
    """模型 B：迭代至不動點，回傳 {rounds, status, lines}。"""
    cur = base
    seen = {widths(base)}
    for r in range(1, MAX_ROUNDS + 1):
        lines = break_cells(cur, cap, INDENT)
        nxt = edge_adjust(base, lines)
        if widths(nxt) == widths(cur):
            return {"rounds": r, "status": "收斂", "lines": lines}
        if widths(nxt) in seen:   # S2：偵測到循環，回退未調整版本並標記
            return {"rounds": r, "status": "振盪回退",
                    "lines": break_cells(base, cap, INDENT)}
        seen.add(widths(nxt))
        cur = nxt
    return {"rounds": MAX_ROUNDS, "status": "未收斂",
            "lines": break_cells(base, cap, INDENT)}


def main() -> int:
    materials = []
    for md in sorted((ROOT / "samples").glob("*.md")):
        if md.name == "README.md":
            continue
        materials.append((f"samples/{md.name}", md.read_text(encoding="utf-8")))
    for i, arg in enumerate(sys.argv[1:], 1):   # 外置素材：只取數字，內容不入 repo
        p = Path(arg)
        if not p.exists():
            print(f"外置素材 {i} 不存在，略過：{arg}")
            continue
        materials.append((f"外置素材 {i}（{p.suffix}）", p.read_text(encoding="utf-8")))

    print(f"素材 {len(materials)} 份　行容量 {CAPS}　縮排 {INDENT}　"
          f"迭代上限 {MAX_ROUNDS} 輪\n")

    tot_paras = tot_lines = 0
    hit_head = hit_tail = 0
    rounds_hist: dict = {}
    osc = noconv = 0
    undo = keep = 0
    diff_lines = diff_paras = 0
    kin_bad = ovf_bad = 0
    t_a = t_b = 0.0

    print(f"{'素材':<26}｜{'段':>4}｜{'行':>5}｜{'行首(':>6}｜{'行尾)':>6}｜"
          f"{'≤3輪':>5}｜{'振盪':>4}｜{'未收':>4}｜{'B≠A 行':>7}")
    print("-" * 96)
    for name, text in materials:
        m = {"paras": 0, "lines": 0, "head": 0, "tail": 0,
             "ok3": 0, "osc": 0, "noconv": 0, "diff": 0,
             "undo": 0, "keep": 0}
        for para in paragraphs(text):
            base = base_cells(para)
            if not base:
                continue
            for cap in CAPS:
                m["paras"] += 1
                t0 = time.perf_counter()
                lines_a = break_cells(base, cap, INDENT)
                t_a += time.perf_counter() - t0

                t0 = time.perf_counter()
                res = converge(base, cap)
                t_b += time.perf_counter() - t0

                lines_b = res["lines"]
                m["lines"] += len(lines_a)
                lines_a2 = model_a_lines(base, lines_a)
                for line, adj in zip(lines_a, lines_a2):
                    if not line.cells:
                        continue
                    hit = (line.cells[0].text in SQUEEZE_OPENERS
                           or line.cells[-1].text in SQUEEZE_CLOSERS)
                    if line.cells[0].text in SQUEEZE_OPENERS:
                        m["head"] += 1
                    if line.cells[-1].text in SQUEEZE_CLOSERS:
                        m["tail"] += 1
                    if not hit:
                        continue
                    a_adv, a_status = line_justified_advance(adj, 1.0)
                    if a_status == "stretched" and a_adv > 1.0:
                        m["undo"] += 1   # 省下的半格被齊行分回字間
                    else:
                        m["keep"] += 1
                rounds_hist[res["rounds"]] = rounds_hist.get(res["rounds"], 0) + 1
                if res["status"] == "收斂" and res["rounds"] <= 3:
                    m["ok3"] += 1
                elif res["status"] == "振盪回退":
                    m["osc"] += 1
                elif res["status"] == "未收斂":
                    m["noconv"] += 1
                if bounds(lines_a) != bounds(lines_b):
                    m["diff"] += 1
                    ba, bb = bounds(lines_a), bounds(lines_b)
                    diff_lines += sum(1 for x, y in zip(ba, bb) if x != y) \
                        + abs(len(ba) - len(bb))
                kin_bad += len(check_kinsoku(lines_b))
                ovf_bad += len(check_overflow(lines_b))

        tot_paras += m["paras"]
        tot_lines += m["lines"]
        hit_head += m["head"]
        hit_tail += m["tail"]
        osc += m["osc"]
        noconv += m["noconv"]
        diff_paras += m["diff"]
        undo += m["undo"]
        keep += m["keep"]
        print(f"{name:<26}｜{m['paras']:>4}｜{m['lines']:>5}｜{m['head']:>6}｜"
              f"{m['tail']:>6}｜{m['ok3']:>5}｜{m['osc']:>4}｜{m['noconv']:>4}｜"
              f"{m['diff']:>7}")

    ok3 = sum(c for r, c in rounds_hist.items() if r <= 3) - osc - noconv
    print("\n" + "=" * 72)
    print(f"Q1 情境頻率：{tot_lines} 行中，行首開括號 {hit_head} 行"
          f"（{hit_head / tot_lines:.2%}）、行尾閉括號 {hit_tail} 行"
          f"（{hit_tail / tot_lines:.2%}）")
    print(f"S1 收斂率：{tot_paras} 個（段×行容量）樣本，"
          f"≤3 輪收斂 {ok3}（{ok3 / tot_paras:.2%}）"
          f"　輪數分布 {dict(sorted(rounds_hist.items()))}")
    print(f"S2 終止：振盪回退 {osc}　未收斂（>{MAX_ROUNDS} 輪）{noconv}")
    print(f"S3 品質：收斂後 check_kinsoku {kin_bad} 違規、check_overflow {ovf_bad} 筆")
    print(f"S4 成本：模型 A {t_a:.3f}s　模型 B {t_b:.3f}s　"
          f"倍數 {t_b / t_a:.2f}×")
    print(f"D1 模型 B 與模型 A 行邊界不同的樣本 {diff_paras}"
          f"（{diff_paras / tot_paras:.2%}），不同的行數 {diff_lines}")
    hits = undo + keep
    print(f"D2 模型 A 齊行抵銷：命中行 {hits} 行中，"
          f"省下的半格被齊行分回字間 {undo} 行"
          + (f"（{undo / hits:.2%}）" if hits else "")
          + f"，視覺目的成立 {keep} 行")

    verdict = (ok3 / tot_paras >= 0.95 and noconv == 0
               and kin_bad == 0 and ovf_bad == 0)
    print(f"\nPoC 判定：{'通過' if verdict else '未通過'}"
          f"（S1 {ok3 / tot_paras:.2%} ≥ 95%？{ok3 / tot_paras >= 0.95}；"
          f"S2 未收斂 {noconv}＝0？{noconv == 0}；"
          f"S3 {kin_bad}+{ovf_bad}＝0？{kin_bad == 0 and ovf_bad == 0}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
