"""AI 指派的判定層（Sprint 104，Qt 無關故背景執行緒與 pytest 皆可跑）。

抽出的理由與 preflight_core（Sprint 100）同一條：AI 呼叫要離開 GUI 執行緒，
判定就不能綁在視窗物件上。本層只管一件事：**建議索引的有效性守門**。

`suggest_styles` 回的 `assignments` 是位置列（第 i 項＝第 i 段的建議），位置
繫於送檢當下的段落文字序列。改跑背景執行緒後使用者可以邊等邊編輯，若回來時
段落已增刪、改寫或對調，照索引套用就會把建議安到別的段落上。故送檢前取一份
文字快照，結果回來時比對相同才放行；不同即據實請使用者重跑，不猜對映。

樣式改變不使快照失效：AI 建議只依段落文字得出，而校正對話框逐列讀的是現行
樣式，故「等待期間只改了樣式」仍對得上。
"""


def paragraph_texts(doc) -> tuple:
    """送檢當下的逐段文字快照（有序、不可變，worker 讀不到其後的編輯）。"""
    return tuple(p.text for p in doc.paragraphs)


def assignments_still_apply(doc, texts: tuple) -> bool:
    """現行文件的段落文字是否仍與快照逐段相同（相同才可依索引套用建議）。

    依序逐段比對：段落對調時文字集合雖相同，位置已異，仍屬錯位。
    """
    return paragraph_texts(doc) == tuple(texts)
