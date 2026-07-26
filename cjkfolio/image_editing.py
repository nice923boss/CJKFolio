"""置入圖的文件編輯純函式（Sprint 102）：畫布拖放與縮放置圖 UI 的判定層。

Qt 無關（同 editor/preflight_core.py 的判定層與呈現層分工紀律）：畫布只負責把
滑鼠事件換算成 trim pt 座標，圖框的建立、平移、縮放、命中判定全在本層，故除了
真視窗手感之外的行為皆能離屏以 pytest 驗證。

座標一律 trim 空間 pt、top-down，與 PlacedImage.rect 同一事實來源（Sprint 54）；
圖在框內 contain 等比置中的幾何仍在 primitives.fit_image_rect，本層不重算。

槽式圖（rect None）不參與拖放與縮放：其位置由主版 figure 保留區決定，沒有可拖
的座標，故拖放語意不成立，快速失敗而非默默改寫成 rect 圖。
"""
from dataclasses import replace

from .document import Document, PlacedImage
from .images import MIN_IMAGE_PPI, PT_PER_INCH

MIN_IMAGE_SIZE_PT = 12.0  # 圖框最小邊長：拖成零寬框後即無法再點選，不給拖到那一步
HANDLE_SIZE_PT = 8.0      # 角控制點邊長（畫布以此邊長的方塊呈現與命中）
CORNERS = ("nw", "ne", "sw", "se")
SNAP_TOLERANCE_PT = 6.0   # 吸附半徑（約 2mm）：拖到此距離內即貼齊參考線
FULL_PAGE_MODES = ("fit", "fill")  # 一鍵滿版的兩種模式（等比放大／鋪滿含出血）


def normalize_rect(rect, label: str = "圖框") -> tuple:
    """把 (x0, y0, x1, y1) 排成左上、右下序；退化（零寬或零高）快速失敗。

    label 讓文字框（frame_box_editing）共用同一份矩形數學時錯誤訊息仍講對東西
    （矩形正規化與框裡裝的是圖還是字無關，不為此另立第二套幾何）。
    """
    x0, y0, x1, y1 = (float(v) for v in rect)
    lo_x, hi_x = (x0, x1) if x0 <= x1 else (x1, x0)
    lo_y, hi_y = (y0, y1) if y0 <= y1 else (y1, y0)
    if hi_x - lo_x <= 0 or hi_y - lo_y <= 0:
        raise ValueError(f"{label}須有正的寬與高，得到 {rect}")
    return (lo_x, lo_y, hi_x, hi_y)


def default_image_rect(px_w: int, px_h: int, cx_pt: float, cy_pt: float,
                       page_w_pt: float, page_h_pt: float) -> tuple:
    """拖放落點的預設圖框：以 §9 下限 300ppi 的原生尺寸置於 (cx_pt, cy_pt) 為中心。

    取 300ppi 的理由＝那是「仍合印前規格時能放到的最大尺寸」（放更大即
    images.check 判解析度不足），故作為預設值既合規又不浪費像素。原生尺寸超出
    頁面時等比縮到整頁可容（不裁切、不變形，同 fit_image_rect 的 contain 精神）。
    落點靠頁緣時允許溢出頁面：rect 圖可溢出版心是既定設計（Sprint 54）。
    """
    if px_w <= 0 or px_h <= 0:
        raise ValueError(f"影像像素尺寸須為正，得到 {px_w}×{px_h}")
    w = px_w * PT_PER_INCH / MIN_IMAGE_PPI
    h = px_h * PT_PER_INCH / MIN_IMAGE_PPI
    if w > page_w_pt or h > page_h_pt:
        scale = min(page_w_pt / w, page_h_pt / h)
        w *= scale
        h *= scale
    return (cx_pt - w / 2, cy_pt - h / 2, cx_pt + w / 2, cy_pt + h / 2)


def _placed(doc: Document, idx: int) -> PlacedImage:
    """取第 idx 張置入圖；越界快速失敗（系統邊界，訊息含實際張數）。"""
    if not 0 <= idx < len(doc.images):
        raise ValueError(f"置入圖索引 {idx} 越界（共 {len(doc.images)} 張）")
    return doc.images[idx]


def _rect_of(doc: Document, idx: int) -> tuple:
    """取第 idx 張的 rect；槽式圖無座標故不可拖放（不默默改寫成 rect 圖）。"""
    placed = _placed(doc, idx)
    if placed.rect is None:
        raise ValueError(
            f"置入圖 {idx} 為槽式（主版 figure 保留區定位），無座標可拖放或縮放"
        )
    return placed.rect


def place_image(doc: Document, path: str, page: int, rect) -> Document:
    """追加一張 rect 置入圖到文件末（文件序＝繪製序，後置者疊在上）。"""
    if page < 1:
        raise ValueError(f"置入圖頁碼須自 1 起算，得到 {page}")
    if not path:
        raise ValueError("置入圖路徑不可為空")
    placed = PlacedImage(path=path, page=page, rect=normalize_rect(rect))
    return replace(doc, images=doc.images + (placed,))


def move_image(doc: Document, idx: int, dx_pt: float, dy_pt: float) -> Document:
    """平移第 idx 張圖框（wrap 等其餘欄位原樣保留）。"""
    x0, y0, x1, y1 = _rect_of(doc, idx)
    moved = replace(doc.images[idx],
                    rect=(x0 + dx_pt, y0 + dy_pt, x1 + dx_pt, y1 + dy_pt))
    return replace(doc, images=doc.images[:idx] + (moved,) + doc.images[idx + 1:])


def resize_image(doc: Document, idx: int, rect) -> Document:
    """換掉第 idx 張的圖框（縮放的落地；新框正規化後寫入）。"""
    _rect_of(doc, idx)  # 槽式圖與越界的守門（與 move 同一條規則）
    sized = replace(doc.images[idx], rect=normalize_rect(rect))
    return replace(doc, images=doc.images[:idx] + (sized,) + doc.images[idx + 1:])


def set_image_wrap(doc: Document, idx: int, *, wrap=None,
                   margin_mm=None) -> Document:
    """改第 idx 張圖的繞排參數（Sprint 103）：wrap 開關與 wrap_margin_mm 間隙。

    兩個欄位皆選配，未指定者保持現值（只調間隙不必重述開關，反之亦然）。等值變更
    回原文件物件，供 session 判 no-op 不塞一步空 undo（同 _commit_pair 慣例）。

    槽式圖（rect None）無座標故無排除區可算，快速失敗而非默默忽略（與拖放同一條
    規則，亦與 document.py「wrap 需搭 rect」的解析守門一致）。間隙為圖框四周額外
    留白，語意上不可為負。
    """
    placed = _placed(doc, idx)
    new_wrap = placed.wrap if wrap is None else bool(wrap)
    new_margin = (placed.wrap_margin_mm if margin_mm is None else float(margin_mm))
    if new_wrap and placed.rect is None:
        raise ValueError(
            f"置入圖 {idx} 為槽式（主版 figure 保留區定位），無座標可算繞排排除區"
        )
    if new_margin < 0:
        raise ValueError(f"繞排間隙須為 ≥0 的毫米數，得到 {margin_mm!r}")
    if new_wrap == placed.wrap and new_margin == placed.wrap_margin_mm:
        return doc
    changed = replace(placed, wrap=new_wrap, wrap_margin_mm=new_margin)
    return replace(doc, images=doc.images[:idx] + (changed,) + doc.images[idx + 1:])


def remove_image(doc: Document, idx: int) -> Document:
    """移除第 idx 張置入圖（槽式圖亦可移除，移除不需要座標）。"""
    _placed(doc, idx)
    return replace(doc, images=doc.images[:idx] + doc.images[idx + 1:])


def image_at_point(doc: Document, page: int, x_pt: float, y_pt: float):
    """該頁最上層命中的置入圖索引；無命中回 None。

    文件序＝繪製序（Sprint 54），故反序尋找＝上層優先，與畫面所見一致。
    槽式圖不參與（無座標，同 _rect_of 的理由）。
    """
    for idx in range(len(doc.images) - 1, -1, -1):
        placed = doc.images[idx]
        if placed.page != page or placed.rect is None:
            continue
        x0, y0, x1, y1 = placed.rect
        if x0 <= x_pt <= x1 and y0 <= y_pt <= y1:
            return idx
    return None


def handle_rects(rect, handle_pt: float = HANDLE_SIZE_PT) -> dict:
    """四角控制點方塊 {角名: (x0, y0, x1, y1)}，各以該角為中心。"""
    x0, y0, x1, y1 = rect
    half = handle_pt / 2
    centres = {"nw": (x0, y0), "ne": (x1, y0), "sw": (x0, y1), "se": (x1, y1)}
    return {name: (cx - half, cy - half, cx + half, cy + half)
            for name, (cx, cy) in centres.items()}


def handle_at_point(rect, x_pt: float, y_pt: float,
                    handle_pt: float = HANDLE_SIZE_PT):
    """點在哪個角控制點上；都沒有回 None（重疊時取 CORNERS 序中最先命中者）。"""
    for name in CORNERS:
        hx0, hy0, hx1, hy1 = handle_rects(rect, handle_pt)[name]
        if hx0 <= x_pt <= hx1 and hy0 <= y_pt <= hy1:
            return name
    return None


def resize_rect(rect, handle: str, x_pt: float, y_pt: float, *,
                aspect=None, min_pt: float = MIN_IMAGE_SIZE_PT) -> tuple:
    """拖角控制點後的新圖框：對角固定，被拖的角移到 (x_pt, y_pt)。

    aspect＝來源影像的寬高比時等比縮放（圖框恆貼合影像比例，拖多少放大多少，
    不產生 contain 留白）；None＝自由拉框（影像仍在框內 contain 置中，
    fit_image_rect 語意不變）。等比時取水平與垂直兩方向較大的拖曳範圍，故斜拖、
    橫拖、直拖都跟得上手。兩軸皆夾 min_pt 最小邊長。
    """
    if handle not in CORNERS:
        raise ValueError(f"未知的控制點 {handle!r}，須為 {CORNERS}")
    x0, y0, x1, y1 = rect
    fixed_x = x1 if "w" in handle else x0   # 被拖的是西側 → 東側固定
    fixed_y = y1 if "n" in handle else y0   # 被拖的是北側 → 南側固定
    dx = x_pt - fixed_x
    dy = y_pt - fixed_y
    sx = -1.0 if dx < 0 else 1.0
    sy = -1.0 if dy < 0 else 1.0
    w, h = abs(dx), abs(dy)
    if aspect is not None:
        if aspect <= 0:
            raise ValueError(f"寬高比須為正，得到 {aspect}")
        w = max(w, h * aspect)
        if w < min_pt:
            w = min_pt
        h = w / aspect
        if h < min_pt:
            h = min_pt
            w = h * aspect
    else:
        w = max(w, min_pt)
        h = max(h, min_pt)
    return normalize_rect((fixed_x, fixed_y, fixed_x + sx * w, fixed_y + sy * h))


def _axis_snap(lo: float, hi: float, span_pt: float, bleed_pt: float,
               tol_pt: float, names: tuple) -> tuple:
    """單軸的吸附量與說明：回 (位移 pt, 說明字串)；沒吸到回 (0.0, "")。

    參考線分兩類：低側線（頁緣 0、出血 −bleed）只收框的低側邊界，高側線（頁緣
    span、出血 span+bleed）只收高側邊界。刻意不交叉配對（讓左邊界貼到右頁緣即把
    圖整個拖出版外，那不是對齊）。多條線同時在容差內取最近者；等距時取先列者
    （頁緣優先於出血線，兩者相距 bleed_pt 故僅 bleed_pt=0 時同位）。
    """
    if tol_pt <= 0:  # 呼叫端關閉吸附（0 或負值）：原框原樣回去
        return 0.0, ""
    lo_name, hi_name = names
    lines = [(lo, 0.0, f"{lo_name}緣貼齊頁{lo_name}緣"),
             (hi, span_pt, f"{hi_name}緣貼齊頁{hi_name}緣")]
    if bleed_pt > 0:  # bleed_pt=0 時出血線與頁緣重合，不重複列同一條線
        lines += [(lo, -bleed_pt, f"{lo_name}緣貼齊出血{lo_name}線"),
                  (hi, span_pt + bleed_pt, f"{hi_name}緣貼齊出血{hi_name}線")]
    best = None
    for edge, line, note in lines:
        delta = line - edge
        if abs(delta) <= tol_pt and (best is None or abs(delta) < abs(best[0])):
            best = (delta, note)
    return best if best is not None else (0.0, "")


def snap_rect(rect, page_w_pt: float, page_h_pt: float, *, bleed_pt: float = 0.0,
              tol_pt: float = SNAP_TOLERANCE_PT) -> tuple:
    """拖曳中的圖框吸附到最近的頁面參考線；回傳 (新框, 吸附說明 tuple)。

    Owner 真視窗需求：「封面將圖片移到最左上角邊緣時，要有吸附自動對齊邊緣的功能」。
    滿版封面圖的正確落點是頁緣或出血線，而那條線在螢幕上肉眼對不準（差 1pt 在
    150dpi 畫布上約 2px），故由此層吸附。

    **只挪位置、不改尺寸**：兩軸各挪同一個量，寬高恆等於原框（平移語意），故吸附
    後仍是使用者拖的那個框，不會偷偷改變圖的大小。兩軸獨立判定＝拖到左上角時橫
    直兩軸同時貼齊（Owner 要的「最左上角邊緣」即此）。

    參考線＝頁緣（trim，0 與 page_w／page_h）與出血線（−bleed 與 page+bleed）兩組：
    前者是版面對齊，後者是滿版出血稿的正確落點（§9 四邊出血 3mm）。bleed_pt=0
    即只有頁緣一組。說明字串供呈現層據實顯示吸到哪幾條線（不沉默改動使用者的框）。
    """
    x0, y0, x1, y1 = rect
    dx, x_note = _axis_snap(x0, x1, page_w_pt, bleed_pt, tol_pt, ("左", "右"))
    dy, y_note = _axis_snap(y0, y1, page_h_pt, bleed_pt, tol_pt, ("上", "下"))
    notes = tuple(note for note in (x_note, y_note) if note)
    return (x0 + dx, y0 + dy, x1 + dx, y1 + dy), notes


def full_page_rect(aspect: float, page_w_pt: float, page_h_pt: float, *,
                   mode: str = "fit", bleed_pt: float = 0.0) -> tuple:
    """一鍵滿版的圖框：置中於頁面，恆等比（Owner「可選等比放大或是整個鋪滿」）。

    mode="fit"（等比放大）＝等比放到頁內可容的最大尺寸：長邊貼齊兩側頁緣、短邊
    留白，**完整不裁切**（同 fit_image_rect 的 contain 精神）。
    mode="fill"（整個鋪滿）＝等比放到「頁面＋四邊出血」全被蓋滿的最小尺寸：
    **溢出的部分被裁掉**（PNG 於畫布邊界自然裁切、PDF 落在 MediaBox 的出血區內，
    裁切後即滿版無白邊），這是滿版封面送印的正確做法。

    兩模式都要來源影像的寬高比：圖在框內恆 contain 置中（fit_image_rect），框比不
    合影像比就會在框內留白，那不是滿版。呼叫端讀不到來源尺寸時不得代為猜比例
    （猜錯＝使用者看到的滿版是歪的），故 aspect 必填且須為正。

    回傳的框刻意不夾 MIN_IMAGE_SIZE_PT：整頁尺寸恆遠大於最小邊長，夾了只是死碼。
    """
    if aspect <= 0:
        raise ValueError(f"寬高比須為正，得到 {aspect}")
    if page_w_pt <= 0 or page_h_pt <= 0:
        raise ValueError(f"頁面尺寸須為正 pt，得到 {page_w_pt}×{page_h_pt}")
    if mode not in FULL_PAGE_MODES:
        raise ValueError(f"未知的滿版模式 {mode!r}，須為 {FULL_PAGE_MODES}")
    if bleed_pt < 0:
        raise ValueError(f"出血須為 ≥0 的 pt，得到 {bleed_pt}")
    grow = 2 * bleed_pt if mode == "fill" else 0.0  # 等比放大不含出血（不裁切）
    box_w = page_w_pt + grow
    box_h = page_h_pt + grow
    # fill 取兩軸較大者（cover：兩軸皆蓋滿，短軸溢出被裁）、fit 取較小者（contain）
    w = (max if mode == "fill" else min)(box_w, box_h * aspect)
    h = w / aspect
    cx, cy = page_w_pt / 2, page_h_pt / 2  # 恆以頁面中心對齊（出血四邊對稱）
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
