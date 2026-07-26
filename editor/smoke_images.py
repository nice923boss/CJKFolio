"""editor 畫布置圖 UI 的離屏煙霧驗證（C19，Sprint 102）。

驗證項（皆離屏可自主驗證，真視窗拖曳手感待 Owner）：
  拖放真圖檔進畫布（走 CanvasView.dropEvent 真事件）→ 文件多一張 rect 圖、
  底圖確實畫出該圖、互動層有圖框與四角控制點；拖曳移動與拖角等比縮放各成
  一步 undo；Delete 移除可回原；非影像檔拖入被拒；缺圖不炸且據實提示。

由 smoke_check.main() 呼叫，離屏環境（QT_QPA_PLATFORM＝offscreen、QApplication
已建）由呼叫端備妥。獨立成檔的理由同 smoke_preflight（smoke_check.py 行數上限）。
"""
import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QGraphicsPixmapItem

from cjkfolio.press_marks import BLEED_MM
from cjkfolio.render import mm_to_pt

DPI = 150
SCALE = DPI / 72.0


def _base_pixels(win) -> int:
    """底圖非白像素數（置入圖是否真的畫上底圖的獨立判準，不看互動層）。"""
    base = next(it for it in win.scene.items()
                if isinstance(it, QGraphicsPixmapItem))
    image = base.pixmap().toImage()
    dark = 0
    for y in range(0, image.height(), 3):     # 取樣列（全掃過慢，形態判定足夠）
        for x in range(0, image.width(), 3):
            if image.pixelColor(x, y).value() < 250:
                dark += 1
    return dark


def _keys(win) -> list:
    return [it.data(0) for it in win.scene.items() if it.data(0) is not None]


def check_images(EditorWindow, DOC, ROOT) -> None:
    """跑 C19 並 print（斷言失敗即 AssertionError 中止整份 smoke）。"""
    photo = ROOT / "samples" / "wrap-photo.png"   # 自擬灰階樣張（360×270，非參考書）

    # --- 拖放置入（真 QDropEvent 走 CanvasView 的接受判定與座標換算） ---
    win = EditorWindow(str(DOC))
    ink_before = _base_pixels(win)
    assert len(win.doc.images) == 0, "樣張本無置入圖"

    def _drop(path, x_px, y_px):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        event = QDropEvent(QPointF(x_px, y_px), Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        win.view.dropEvent(event)
        return event

    ev = _drop(photo, 300.0, 400.0)
    assert ev.isAccepted(), "拖放影像檔未被接受"
    assert len(win.doc.images) == 1, "拖放後文件應多一張置入圖"
    placed = win.doc.images[0]
    assert placed.path == "wrap-photo.png", f"應存相對路徑，得到 {placed.path}"
    assert placed.page == win.page.number
    w_pt = placed.rect[2] - placed.rect[0]
    h_pt = placed.rect[3] - placed.rect[1]
    assert abs(w_pt - 360 * 72 / 300) < 1e-6, f"預設寬應為 300ppi 尺寸，得到 {w_pt}"
    assert abs(h_pt - 270 * 72 / 300) < 1e-6, f"預設高應為 300ppi 尺寸，得到 {h_pt}"

    # 非影像檔（文件本身）拖入：dragEnter 即拒絕，不進置入流程
    reject = QMimeData()
    reject.setUrls([QUrl.fromLocalFile(str(DOC))])
    enter = QDropEvent(QPointF(300.0, 400.0), Qt.DropAction.CopyAction, reject,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    win.view.dropEvent(enter)
    assert len(win.doc.images) == 1, "非影像檔不應被置入"

    # --- 底圖確實畫出圖、互動層有圖框與四角控制點 ---
    ink_after = _base_pixels(win)
    assert ink_after > ink_before, (
        f"底圖未見置入圖墨跡（前 {ink_before} → 後 {ink_after}）")
    keys = _keys(win)
    assert ("image", 0) in keys, "互動層缺置入圖框"
    handles = [k for k in keys if k[0] == "image-handle"]
    assert len(handles) == 4, f"角控制點應為 4 個，得到 {len(handles)}"
    n_cells = len([k for k in keys if isinstance(k[0], int)])
    assert n_cells == 48, f"字格互動層應不退步（48），得到 {n_cells}"

    # 圖框中心的最上層 item＝圖框（圖疊在字格之上，點圖不會誤取到其下的字）
    cx = (placed.rect[0] + placed.rect[2]) / 2 * SCALE
    cy = (placed.rect[1] + placed.rect[3]) / 2 * SCALE
    top = next(it for it in win.scene.items(QPointF(cx, cy)) if it.data(0) is not None)
    assert top.data(0) == ("image", 0), f"圖框中心取到 {top.data(0)}"

    # --- 拖曳移動（放開才提交一步） ---
    item = next(it for it in win.scene.items() if it.data(0) == ("image", 0))
    win._on_pick(item, QPointF(cx, cy))
    assert win._image_idx == 0, "按下圖框應選取該圖"
    win._on_image_move(QPointF(cx + 20 * SCALE, cy - 10 * SCALE))
    assert win.doc.images[0].rect == placed.rect, "拖曳途中不應改動文件（只畫預覽）"
    win._on_image_release()
    moved = win.doc.images[0].rect
    assert abs(moved[0] - (placed.rect[0] + 20)) < 1e-6, f"位移不符：{moved}"
    assert abs(moved[1] - (placed.rect[1] - 10)) < 1e-6, f"位移不符：{moved}"
    win._on_undo()
    assert win.doc.images[0].rect == placed.rect, "一步 undo 應回移動前"
    win._on_redo()

    # --- 拖角等比縮放 ---
    se = next(it for it in win.scene.items()
              if it.data(0) == ("image-handle", 0, "se"))
    rect_before = win.doc.images[0].rect
    win._on_pick(se, QPointF(rect_before[2] * SCALE, rect_before[3] * SCALE))
    win._on_image_move(QPointF((rect_before[0] + 172.8) * SCALE,
                               (rect_before[1] + 60.0) * SCALE))
    win._on_image_release()
    sized = win.doc.images[0].rect
    ratio = (sized[2] - sized[0]) / (sized[3] - sized[1])
    assert abs(ratio - 360 / 270) < 1e-6, f"縮放後應維持來源比例，得到 {ratio}"
    assert abs((sized[2] - sized[0]) - 172.8) < 1e-6, f"應跟隨拖曳範圍：{sized}"
    assert (sized[0], sized[1]) == (rect_before[0], rect_before[1]), "對角應固定"
    win._on_undo()
    assert win.doc.images[0].rect == rect_before, "一步 undo 應回縮放前"

    # --- Delete 移除與 undo ---
    win._select_image(0)
    assert win._remove_selected_image() is True
    assert win.doc.images == (), "移除後不應留置入圖"
    win._on_undo()
    assert len(win.doc.images) == 1, "undo 應把圖放回來"

    # --- 角控制點的縮放游標（Sprint 147）---
    # 控制點全透明看不見，游標形狀是它唯一的存在提示，故形狀本身即受測行為。
    corners = {it.data(0)[2]: it for it in win.scene.items()
               if isinstance(it.data(0), tuple) and it.data(0)[0] == "image-handle"}
    assert set(corners) == {"nw", "ne", "sw", "se"}, f"控制點不全：{sorted(corners)}"
    for name, want in (("se", Qt.CursorShape.SizeFDiagCursor),   # ↖↘
                       ("nw", Qt.CursorShape.SizeFDiagCursor),
                       ("ne", Qt.CursorShape.SizeBDiagCursor),   # ↗↙
                       ("sw", Qt.CursorShape.SizeBDiagCursor)):
        handle = corners[name]
        assert handle.hasCursor(), f"控制點 {name} 未設游標（滑過看不出可拖）"
        assert handle.cursor().shape() == want, \
            f"控制點 {name} 游標應為 {want}，得到 {handle.cursor().shape()}"
    body = next(it for it in win.scene.items() if it.data(0) == ("image", 0))
    assert not body.hasCursor(), "圖框本體不應改游標（縮放示意只在四角）"
    here = win.doc.images[0].rect
    top_se = next(it for it in win.scene.items(
        QPointF(here[2] * SCALE, here[3] * SCALE)) if it.data(0) is not None)
    assert top_se.data(0) == ("image-handle", 0, "se"), \
        f"右下角最上層應為控制點（游標才會生效），得到 {top_se.data(0)}"

    # --- 拖到頁緣自動吸附（Sprint 147）---
    def _drag_to(x0_pt, y0_pt) -> tuple:
        """把圖 0 的左上角拖到 (x0_pt, y0_pt)；回 (提交後圖框, 拖曳中訊息)。"""
        rect = win.doc.images[0].rect
        hw, hh = (rect[2] - rect[0]) / 2, (rect[3] - rect[1]) / 2
        frame = next(it for it in win.scene.items() if it.data(0) == ("image", 0))
        win._on_pick(frame, QPointF((rect[0] + hw) * SCALE, (rect[1] + hh) * SCALE))
        win._on_image_move(QPointF((x0_pt + hw) * SCALE, (y0_pt + hh) * SCALE))
        during = win.statusBar().currentMessage()
        win._on_image_release()
        return win.doc.images[0].rect, during

    win.view.set_zoom(1.0)   # 吸附半徑依縮放倍率換算，固定倍率才可斷言 pt 值
    size_before = (here[2] - here[0], here[3] - here[1])
    snapped, during = _drag_to(3.0, 3.0)  # 距左上頁緣 3pt（容差 6pt 內）
    assert "已吸附" in during, f"拖曳中未回報吸附：{during}"
    assert abs(snapped[0]) < 1e-6 and abs(snapped[1]) < 1e-6, \
        f"拖到左上角未貼齊頁緣：{snapped}"
    assert (abs((snapped[2] - snapped[0]) - size_before[0]) < 1e-6
            and abs((snapped[3] - snapped[1]) - size_before[1]) < 1e-6), \
        f"吸附只該挪位置不該改尺寸：{size_before} → {snapped}"
    release_msg = win.statusBar().currentMessage()
    assert "已吸附：左緣貼齊頁左緣、上緣貼齊頁上緣" in release_msg, \
        f"提交訊息未指名吸到哪幾條線：{release_msg}"

    bleed_pt = mm_to_pt(BLEED_MM)
    on_bleed, during = _drag_to(-7.0, 3.0)  # 距出血左線 1.5pt、距頁左緣 7pt（超容差）
    assert abs(on_bleed[0] + bleed_pt) < 1e-6, f"未貼齊出血左線：{on_bleed}"
    assert "出血左線" in during, f"未回報吸到出血線：{during}"

    far, during = _drag_to(60.0, 300.0)  # 離任何參考線都超過容差
    assert abs(far[0] - 60.0) < 1e-6 and abs(far[1] - 300.0) < 1e-6, \
        f"容差外不應被吸走：{far}"
    assert "已吸附" not in during, f"容差外誤報吸附：{during}"

    win.view.set_zoom(4.0)  # 放大 4 倍→容差 1.5pt：3pt 落在容差外（吸附是螢幕距離）
    win._select_image(0)
    fine, _ = _drag_to(3.0, 3.0)
    assert abs(fine[0] - 3.0) < 1e-6 and abs(fine[1] - 3.0) < 1e-6, \
        f"放大 4 倍後 3pt 應超出吸附半徑（1.5pt）：{fine}"
    win.view.set_zoom(1.0)

    # --- 一鍵滿版兩模式（Sprint 147）---
    page_w = mm_to_pt(win.template.page_width_mm)
    page_h = mm_to_pt(win.template.page_height_mm)
    win._select_image(0)
    win._fill_page_image("fit")
    fit = win.doc.images[0].rect
    assert abs(fit[0]) < 1e-6 and abs(fit[2] - page_w) < 1e-6, \
        f"等比放大應貼齊左右頁緣：{fit}"
    assert fit[1] > 0 and fit[3] < page_h, f"等比放大不應裁切（上下留白）：{fit}"
    assert abs((fit[2] - fit[0]) / (fit[3] - fit[1]) - 360 / 270) < 1e-6, \
        f"等比放大不應變形：{fit}"
    fit_msg = win.statusBar().currentMessage()
    assert "ppi" in fit_msg and "低於 §9 下限" in fit_msg, \
        f"放大到 62ppi 未據實警示畫質不足：{fit_msg}"
    win._on_undo()
    assert win.doc.images[0].rect != fit, "一鍵滿版應可一步 undo 回原"

    win._select_image(0)
    win._fill_page_image("fill")
    fill = win.doc.images[0].rect
    assert fill[0] <= -bleed_pt + 1e-6 and fill[2] >= page_w + bleed_pt - 1e-6, \
        f"鋪滿未蓋滿左右出血線：{fill}"
    assert fill[1] <= -bleed_pt + 1e-6 and fill[3] >= page_h + bleed_pt - 1e-6, \
        f"鋪滿未蓋滿上下出血線：{fill}"
    assert abs((fill[2] - fill[0]) / (fill[3] - fill[1]) - 360 / 270) < 1e-6, \
        f"鋪滿也不該變形：{fill}"
    # 獨立判準：讀底圖四角像素（不看 rect 數字）→ 真的無白邊才算鋪滿
    base = next(it for it in win.scene.items() if isinstance(it, QGraphicsPixmapItem))
    shot = base.pixmap().toImage()
    for x, y in ((0, 0), (shot.width() - 1, 0), (0, shot.height() - 1),
                 (shot.width() - 1, shot.height() - 1)):
        assert shot.pixelColor(x, y).value() < 250, \
            f"鋪滿後底圖 ({x}, {y}) 仍是白的＝有白邊"
    win._fill_page_image("fill")  # 已在該尺寸：不塞一步空 undo
    assert "未變更" in win.statusBar().currentMessage(), \
        f"重複套用同一滿版未判無變更：{win.statusBar().currentMessage()}"
    win._select_image(None)
    win._fill_page_image("fit")
    assert "先點選一張置入圖" in win.statusBar().currentMessage(), \
        f"未選取圖未據實提示：{win.statusBar().currentMessage()}"

    # --- 缺圖不炸：文件引用不存在的圖檔仍可開，且據實提示 ---
    with tempfile.TemporaryDirectory() as td:
        raw = json.loads(Path(DOC).read_text(encoding="utf-8"))
        raw["images"] = [{"path": "不存在的圖.png", "page": 1,
                          "rect": [60.0, 120.0, 180.0, 210.0]}]
        broken = Path(td) / "missing-image.doc.json"
        broken.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        win_missing = EditorWindow(str(broken))
        assert "無法載入" in win_missing.statusBar().currentMessage(), \
            f"缺圖未據實提示：{win_missing.statusBar().currentMessage()}"
        assert len(win_missing.doc.images) == 1, "缺圖不應被默默移出文件"

    print(
        "C19 畫布置圖 UI：拖放真圖檔入畫布（非影像檔拒收）→ 300ppi 預設框置於落點"
        "＋底圖見墨跡＋互動層圖框與四角控制點（字格 48 不退步）→ 拖曳移動"
        "（途中只畫預覽、放開提交一步）→ 拖角等比縮放（比例守恆、對角固定）"
        "→ Delete 移除，三者各一步 undo 回原；缺圖不炸且據實提示"
        "｜Sprint 147：四角游標為對角縮放形狀（右下角最上層即控制點、圖框本體不改"
        "游標）→ 拖到左上角吸附頁緣（尺寸不變、訊息指名吸到哪幾條線）、出血線同為"
        "參考線、容差外不吸、放大 4 倍後容差同步縮小（吸附是螢幕距離）"
        "→ 一鍵滿版等比放大貼齊左右頁緣且據實警示 ppi 不足、整個鋪滿蓋滿四邊出血"
        "（讀底圖四角像素證無白邊）、重複套用判無變更、未選取圖據實提示"
    )


def _caps(win) -> dict:
    """首頁逐欄行長 {slot: cap}：繞排把受影響欄的行裁短，故可判畫布是否套繞排。"""
    return {pl.slot: pl.line.cap for pl in win.layout_result.pages[0].placed}


def _cell_count(win) -> int:
    """互動層 body 字格數（鍵為 (placed_idx, cell_idx)）：繞排後字變少，畫布同步。"""
    return len([it for it in win.scene.items()
                if isinstance(it.data(0), tuple) and isinstance(it.data(0)[0], int)])


def check_wrap_ui(EditorWindow, ROOT) -> None:
    """跑 C20 並 print（斷言失敗即 AssertionError 中止整份 smoke）。

    素材＝samples/wrap-demo.doc.json（Sprint 89 自擬樣張，已開 wrap），故可先驗
    「開著繞排時畫布確實繞排」，再走 UI 關掉它驗回路與 undo。
    """
    from editor.image_actions import WrapDialog

    win = EditorWindow(str(ROOT / "samples" / "wrap-demo.doc.json"))
    assert win.doc.images[0].wrap is True, "樣張本應已開繞排"

    # --- 畫布套繞排：被圖擋住的欄行長短於滿行，互動層字格數同步 ---
    wrapped_caps = _caps(win)
    wrapped_cells = _cell_count(win)
    full_line = max(wrapped_caps.values())
    blocked = [s for s, cap in wrapped_caps.items() if cap <= full_line / 2]
    assert len(blocked) >= 6, f"畫布未套繞排（逐欄行長 {wrapped_caps}）"

    # --- UI 關掉繞排：對話框回呼 → 畫布重排回滿行 → 一步 undo 回原 ---
    win._select_image(0)
    win._edit_image_wrap(wrap=False, margin_text="4.26")
    assert win.doc.images[0].wrap is False, "UI 未關掉繞排"
    off_caps = _caps(win)
    assert not [s for s, cap in off_caps.items() if cap <= full_line / 2], \
        f"關繞排後仍見被裁短的欄（{wrapped_caps} → {off_caps}）"
    off_cells = _cell_count(win)
    assert off_cells > wrapped_cells, \
        f"關繞排後首頁字格數應回升（{wrapped_cells} → {off_cells}）"
    win._on_undo()
    assert win.doc.images[0].wrap is True, "一步 undo 應回到繞排開啟"
    assert _caps(win) == wrapped_caps, "undo 後畫布版面應回原"

    # --- 加大間隙＝排除區外擴（首頁容字再少一截），亦為一步 undo ---
    win._select_image(0)
    win._edit_image_wrap(margin_text="8.0")
    loose_cells = _cell_count(win)
    assert loose_cells < wrapped_cells, \
        f"加大間隙未使排除區外擴（首頁字格 {wrapped_cells} → {loose_cells}）"
    win._on_undo()
    assert _cell_count(win) == wrapped_cells, "undo 應回到原間隙的版面"

    # --- 對話框本體（真 widget 走 _on_save 回呼，不 exec） ---
    dlg = WrapDialog(win.doc.images[0], win._apply_image_wrap)
    assert dlg._wrap.isChecked() is True, "對話框應預填現行繞排開關"
    assert dlg._margin.text() == "4.26", f"應預填現行間隙，得到 {dlg._margin.text()}"
    dlg._margin.setText("不是數字")
    dlg._on_save()
    assert "需為數字" in dlg._notice.text(), f"非數字間隙未擋下：{dlg._notice.text()}"
    assert win.doc.images[0].wrap_margin_mm == 4.26, "錯誤輸入不應改動文件"

    # --- 未選取圖時據實提示（不猜使用者指哪張） ---
    win._select_image(None)
    win._edit_image_wrap(wrap=True)
    assert "先點選一張置入圖" in win.statusBar().currentMessage(), \
        f"未選取圖未據實提示：{win.statusBar().currentMessage()}"

    print(
        "C20 文繞圖參數 UI：畫布確實套繞排（受影響欄行長短於滿行、互動層字格同步）"
        "→ UI 關繞排使內文回滿行、加大間隙使排除區外擴，兩者各一步 undo 回原"
        "→ 對話框預填現值且非數字間隙擋在對話框內（文件不動）→ 未選取圖據實提示"
    )
