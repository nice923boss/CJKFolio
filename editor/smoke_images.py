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
    )
