"""smoke C34：書冊管理介面（Sprint 131 丁2；自 smoke_check.py 分檔，行數紀律慣例）。

離屏可驗（不含檔案選取對話框與真視窗手感）：
  檔案選單「組裝書冊…」項（在匯入後、轉存前，無快捷鍵）；
  真實素材自動目錄書冊組裝（Gate 4：UI 組裝段落序＝獨立呼叫 assemble_book_with_toc、
    自動目錄項＝獨立 toc_items 且頁碼真算遞增）；
  開啟語意（undo 歷史清空、剛組裝為乾淨＝可由清單重生，一經編輯即轉髒受保護）；
  模版一致守門（jiejiao-manxing 書冊擋在 neizai-zhengli 編輯器外、現行文件不動）；
  純 path 書冊組裝（不報自動目錄）；缺章據實提示且現行文件不動。
選檔對話框（QFileDialog）與真視窗手感待 Owner（GAPS #19 批次）。
"""
import json
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QMenu

from cjkfolio.book import assemble_book, load_book
from cjkfolio.toc import assemble_book_with_toc, toc_items


def check_book(EditorWindow, DOC, ROOT) -> None:
    """跑 C34 並 print（斷言失敗即 AssertionError 中止整份 smoke）。

    DOC 需為 neizai-zhengli 文件（與 samples 書冊清單模版一致，方能過守門）。"""
    samples = Path(ROOT) / "samples"
    auto_toc = samples / "book-auto-toc.json"
    plain = samples / "book.json"
    jiejiao = samples / "book-jiejiao-manxing.json"

    # 檔案選單「組裝書冊…」：在匯入後、轉存前，無快捷鍵（findChildren 慣例）
    win = EditorWindow(str(DOC))
    menu = next(m for m in win.menuBar().findChildren(QMenu) if m.title() == "檔案")
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "組裝書冊…" in labels, f"檔案選單缺組裝書冊項：{labels}"
    assert labels.index("組裝書冊…") == labels.index("匯入稿件…（txt／md／docx）") + 1, labels
    assert labels.index("組裝書冊…") + 1 == labels.index("轉存為 PDF…"), labels
    book_act = next(a for a in menu.actions() if a.text() == "組裝書冊…")
    assert book_act.shortcut().isEmpty(), "組裝書冊不應佔快捷鍵"

    # ── 自動目錄書冊：組裝 → Gate 4 獨立驗 → 開啟語意 → 編輯轉髒 ──
    assert win._assemble_book(str(auto_toc)), "自動目錄書冊組裝應成功"
    book = load_book(str(auto_toc))
    exp_doc = assemble_book_with_toc(book, win.template, base_dir=samples, first_page=1)
    exp_items = toc_items(book, win.template, base_dir=samples, first_page=1)
    assert [p.text for p in win.doc.paragraphs] == [p.text for p in exp_doc.paragraphs], \
        "UI 組裝段落序與獨立 assemble_book_with_toc 不一致"
    assert win.doc.title == "整理練習（自動目錄樣張）" and win.doc.template == "neizai-zhengli"
    # 自動目錄真頁碼：3 列入章、標題＝清單 toc_title、頁碼 ≥1 且遞增
    assert [it.title for it in exp_items] == \
        ["第一章　安放與整理的提問", "個案速寫　把家還原", "客廳一景"], exp_items
    pages = [it.page for it in exp_items]
    assert all(p >= 1 for p in pages) and pages == sorted(pages), f"自動目錄頁碼非遞增：{pages}"
    # 開啟語意：undo 歷史清空、剛組裝乾淨（可由清單重生）、停在第一頁
    assert not win.session.can_undo(), "組裝後 undo 歷史應清空（開啟語意）"
    assert not win._is_dirty(), "剛組裝（可由清單重生）應乾淨，同開啟語意"
    assert win.page.number == 1, f"組裝後應停在第一頁，得頁 {win.page.number}"
    msg = win.statusBar().currentMessage()
    assert "已組裝書冊「整理練習（自動目錄樣張）」" in msg, msg
    assert "3 章" in msg, msg  # 內容章數（3），不含 generate_toc 指令項
    assert f"自動目錄 {len(exp_items)} 項" in msg, msg
    # 一經編輯即轉髒（組裝成果自此受關閉確認保護，不再是可無痛重生態）
    win.cursor = (0, 0)
    win._ime.setText("改")
    win._on_ime_commit()
    assert win._is_dirty(), "組裝後編輯應轉髒"

    # ── 模版一致守門（pre-mortem 首險）：jiejiao 書冊擋在 neizai 編輯器外 ──
    keep = win.doc
    assert not win._assemble_book(str(jiejiao)), "模版不一致應拒絕組裝"
    assert win.doc is keep, "拒絕組裝不得動現行文件"
    msg2 = win.statusBar().currentMessage()
    assert "不一致" in msg2 and "'jiejiao-manxing'" in msg2 and "'neizai-zhengli'" in msg2, msg2

    # ── 純 path 書冊：組裝成功、狀態不報自動目錄 ──
    win3 = EditorWindow(str(DOC))
    assert win3._assemble_book(str(plain)), "純 path 書冊組裝應成功"
    exp_doc3 = assemble_book(load_book(str(plain)), base_dir=samples)
    assert [p.text for p in win3.doc.paragraphs] == [p.text for p in exp_doc3.paragraphs], \
        "UI 組裝段落序與獨立 assemble_book 不一致"
    assert win3.doc.title == "整理練習（全書樣張）"
    msg3 = win3.statusBar().currentMessage()
    assert "已組裝書冊「整理練習（全書樣張）」" in msg3, msg3
    assert "6 章" in msg3, msg3  # 純 path 六章全計入
    assert "自動目錄" not in msg3, f"純 path 書冊不應報自動目錄：{msg3}"

    # ── 缺章守門：據實提示且現行文件不動 ──
    win4 = EditorWindow(str(DOC))
    before4 = win4.doc
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "缺章.json"
        bad.write_text(json.dumps({
            "schema": "cjkfolio/book@1",
            "meta": {"title": "缺章樣張", "template": "neizai-zhengli"},
            "chapters": [{"path": "不存在的章.doc.json"}],
        }, ensure_ascii=False), encoding="utf-8")
        assert not win4._assemble_book(str(bad)), "缺章應拒絕組裝"
    assert win4.doc is before4, "缺章拒絕不得動現行文件"
    assert "無法組裝" in win4.statusBar().currentMessage()

    for w in (win, win3, win4):  # 退出安全：縮圖執行緒收工（closeEvent 同路徑）
        w._shutdown_thumbnails()
    print(
        "C34 書冊管理介面：檔案選單組裝書冊項（匯入後轉存前、無快捷鍵）＋自動目錄書冊"
        "組裝（Gate 4：UI 段落序＝獨立 assemble_book_with_toc、目錄 3 項真頁碼遞增）"
        "＋開啟語意（undo 清空、剛組裝乾淨可重生、編輯轉髒）＋模版一致守門"
        "（jiejiao 擋在 neizai 外、現行文件不動）＋純 path 書冊（不報自動目錄）"
        "＋缺章據實提示（現行文件不動）"
    )
