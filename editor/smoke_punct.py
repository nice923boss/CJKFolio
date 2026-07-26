"""smoke C44：點字回填輸入欄與標點快捷列（Sprint 146；分檔於 editor/，行數紀律慣例）。

Owner 需求原文：「1. 點選文字，下方文字輸入欄要同步顯示該文字，這樣才可以複製文字
或標點符號快速在新位置貼上。2. 要有所有書冊會常用標點符號的快捷按鈕，點選就能輸入
該標點符號。」

離屏可驗：標點字表每一枚都在引擎既有標點常數內（逐字核對，不是新字集）、18 顆按鈕
齊備、單枚與成對的落點與游標位置、於欄內游標處插入（不是永遠接在最後）、按完焦點
回輸入欄（真視窗按 Enter 才是提交而不是又按到按鈕）、點字格回填該字且整串選取、
空字格不覆寫欄位、複製鈕真的進系統剪貼簿而空欄不靜默複製、Owner 那條路走完整趟
（點來源字格 → 複製 → 點目標字格 → 貼上取代回填 → Enter 插入新位置 → 一步 undo）、
標點提交後真的進文件且破折號由引擎塑形成一格兩枚的連字、拖曳選取整串回填而跨段
據實不回填、框字格同樣回填且標點可提交進框。

未涵蓋（離屏構不出）：無文件游標的字格（拉丁串／空格）該走「無字可回填」分支，
本樣張整頁無此種行，故以 _echo_to_ime 直接餵空字串與空白驗守門，真情境同 GAPS #96。
真視窗待驗：按鈕大小與排列是否好按、注音組字中途按標點鈕的組字狀態、直排頁面上
各標點的字形與位置（GAPS #105）。
"""
from PySide6.QtWidgets import QApplication

from cjkfolio.engine import LINE_END_FORBIDDEN, LINE_START_FORBIDDEN, _DASHES
from editor.canvas import resolve_hit
from editor.punct_panel import PAIRS, SINGLES


def _keys_by_para(win) -> dict:
    """本頁可點字格依段分組：{para_idx: [(段內起位, key), ...]}（起位排序）。"""
    out: dict = {}
    for key in win._item_by_key:
        hit = resolve_hit(win.doc, win.page, *key)
        if hit.para_idx is None or hit.span is None:
            continue
        out.setdefault(hit.para_idx, []).append((hit.span[0], key))
    return {p: sorted(v) for p, v in out.items()}


def _dash_pairs(win) -> int:
    """全書段內文的成對破折號枚數（提交前後對照，不受既有內容影響）。"""
    return sum(p.text.count("——") for p in win.doc.paragraphs)


def check_punct(EditorWindow, doc_path, cover_path) -> None:
    win = EditorWindow(str(doc_path))  # paiban-xiaoji-ch1 41 段 12 頁真樣張

    # ── 字表：每一枚都是引擎已認得的標點（禁則、擠壓、直排字形三條路徑已覆蓋）──
    known = set(LINE_START_FORBIDDEN) | set(LINE_END_FORBIDDEN) | set(_DASHES)
    for mark, name in SINGLES:
        for ch in mark:
            assert ch in known, f"單枚「{mark}」（{name}）的 U+{ord(ch):04X} 不在引擎標點表"
    for left, right, name in PAIRS:
        assert left in LINE_END_FORBIDDEN, f"成對「{left}」（{name}）不在行末禁則表"
        assert right in LINE_START_FORBIDDEN, f"成對「{right}」（{name}）不在行首禁則表"
    buttons = win._punct_bar.buttons
    assert len(buttons) == len(SINGLES) + len(PAIRS) == 18, len(buttons)

    # ── 按鈕落點：單枚游標在其後、成對游標落中間、於欄內游標處插入、焦點回輸入欄 ──
    win._ime.clear()
    buttons["。"].click()
    assert (win._ime.text(), win._ime.cursorPosition()) == ("。", 1), win._ime.text()
    assert win.focusWidget() is win._ime, "按完標點焦點應回輸入欄（否則 Enter 又按到按鈕）"
    win._ime.clear()
    buttons["「」"].click()
    assert (win._ime.text(), win._ime.cursorPosition()) == ("「」", 1), win._ime.text()
    win._ime.insert("春")  # 接著打的字落在兩枚之間
    assert win._ime.text() == "「春」", win._ime.text()
    win._ime.setText("甲乙")
    win._ime.setCursorPosition(1)
    buttons["、"].click()
    assert (win._ime.text(), win._ime.cursorPosition()) == ("甲、乙", 2), win._ime.text()

    # ── 需求一：點字格 → 回填該字並整串選取（接著打字或貼上是取代，不是疊加）──
    by_para = _keys_by_para(win)
    dot_key = next(k for k in win._item_by_key
                   if resolve_hit(win.doc, win.page, *k).text == "。")
    win._on_pick(win._item_by_key[dot_key])
    assert win._ime.text() == "。", f"點「。」字格未回填（得「{win._ime.text()}」）"
    assert win._ime.selectedText() == "。", "回填後應整串選取"
    assert "已回填輸入欄" in win.statusBar().currentMessage()

    # 空字格不覆寫（樣張無此種行，故直接驗守門本身）
    for blank in ("", "   "):
        assert win._echo_to_ime(blank) is False
    assert win._ime.text() == "。", "空字回填卻動了欄位內容"

    # ── 需求一：複製鈕真的進系統剪貼簿；空欄據實提示且不覆寫剪貼簿 ──
    win._copy_ime_text()
    assert QApplication.clipboard().text() == "。"
    assert "已複製" in win.statusBar().currentMessage()
    win._ime.clear()
    win._copy_ime_text()
    assert "文字輸入欄是空的" in win.statusBar().currentMessage()
    assert QApplication.clipboard().text() == "。", "空欄不該把剪貼簿清成空字串"

    # ── Owner 那條路整趟：點目標字格 → 貼上取代回填 → Enter 插入 → 一步 undo ──
    para = max(by_para, key=lambda p: len(by_para[p]))
    target = by_para[para][3][1]
    win._on_pick(win._item_by_key[target])
    hit = resolve_hit(win.doc, win.page, *target)
    before = win.doc.paragraphs[hit.para_idx].text
    win._ime.paste()
    assert win._ime.text() == "。", f"貼上應取代回填的字，得「{win._ime.text()}」"
    win._on_ime_commit()
    assert win.doc.paragraphs[hit.para_idx].text == \
        before[:hit.span[1]] + "。" + before[hit.span[1]:], "貼上的字未落在點選位置之後"
    win._on_undo()
    assert win.doc.paragraphs[hit.para_idx].text == before, "undo 未回原文"

    # ── 需求二：標點鈕接 Enter 真的進文件，破折號由引擎塑形成一格兩枚的連字 ──
    dashes0 = _dash_pairs(win)
    win._on_pick(win._item_by_key[target])
    buttons["——"].click()
    assert win._ime.text() == "——", "標點鈕應取代回填的字，不與它疊加"
    win._on_ime_commit()
    assert _dash_pairs(win) == dashes0 + 1, "破折號未進文件"
    ligatures = [c for pg in win.layout_result.pages for pl in pg.placed
                 for c in pl.line.cells if c.text == "——"]
    assert len(ligatures) == 1 and ligatures[0].width == 2, \
        f"破折號應為一格兩枚寬 2 的連字，得 {[(c.text, c.width) for c in ligatures]}"
    win._on_undo()
    assert _dash_pairs(win) == dashes0, "undo 未回原文"

    # ── 拖曳選取：同段整串回填；跨段據實不回填（一行欄位表達不了段落分界）──
    win._ime.clear()
    a_key, b_key = by_para[para][0][1], by_para[para][4][1]
    win._on_pick(win._item_by_key[a_key])
    win._on_drag(win._item_by_key[b_key])
    picked = win._selection_text()
    assert len(picked) >= 4 and win._ime.text() == picked, \
        f"同段選取應整串回填（選取「{picked}」／欄位「{win._ime.text()}」）"
    assert "已回填輸入欄" in win.statusBar().currentMessage()
    p1, p2 = sorted(by_para)[:2]
    win._on_pick(win._item_by_key[by_para[p1][0][1]])
    win._on_drag(win._item_by_key[by_para[p2][0][1]])
    assert win._selection_text() == "", "跨段應回空字串"
    assert "跨段選取不回填輸入欄" in win.statusBar().currentMessage()

    # ── 文字框字格同樣回填，且標點可提交進框（走 insert_frame，不動 body 版面）──
    win2 = EditorWindow(str(cover_path))  # 封面樣張：書名／作者／出版者三框
    frame_key = next(k for k in win2._item_by_key if k[0] == "frame")
    fi, li, ci = frame_key[1:]
    win2._on_pick(win2._item_by_key[frame_key])
    frame_hit = win2._frame_hit(fi, li, ci)
    assert win2._ime.text() == frame_hit.text, "框字格未回填輸入欄"
    assert "已回填輸入欄" in win2.statusBar().currentMessage()
    src_before = win2.doc.text_frames[frame_hit.source_idx].text
    pages_before = len(win2.layout_result.pages)
    win2._punct_bar.buttons["《》"].click()
    win2._on_ime_commit()
    assert win2.doc.text_frames[frame_hit.source_idx].text == \
        src_before[:frame_hit.span[1]] + "《》" + src_before[frame_hit.span[1]:]
    assert len(win2.layout_result.pages) == pages_before, "框內插入不該改 body 頁數"
    win2._on_undo()
    assert win2.doc.text_frames[frame_hit.source_idx].text == src_before

    win2._shutdown_thumbnails()
    win._shutdown_thumbnails()
    print(
        f"C44 點字回填與標點快捷列：字表 {len(SINGLES)} 單枚＋{len(PAIRS)} 成對逐字皆在"
        "引擎禁則／破折號常數內＋按鈕落點與游標位置（成對落中間）＋按完焦點回輸入欄"
        "＋點字格回填並整串選取＋空字不覆寫＋複製鈕進剪貼簿而空欄不覆寫剪貼簿"
        "＋整趟（複製→點目標→貼上取代→Enter 落在點選位置之後→一步 undo）"
        "＋標點提交後破折號塑形為寬 2 連字＋同段選取整串回填而跨段據實不回填"
        "＋框字格回填且標點提交進框不動 body 頁數"
    )
