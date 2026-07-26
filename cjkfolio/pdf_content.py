"""PDF 內容流組裝（自 pdf_writer.py 分檔，Sprint 145；GAPS #103 行數紀律）。

_Content 收集單頁的圖形（prologue）與文字（ops）算符並串成內容流位元組；
_fmt／_fill_op 為算符數字與 DeviceCMYK 填色的字面化。頁面幾何、字型嵌入與
物件寫出仍在 pdf_writer.py（本檔不認識 LayoutPage 與 PdfBuilder）。
"""
from .styles import DEFAULT_TEXT_CMYK


def _fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _fill_op(cmyk) -> str:
    """DeviceCMYK 文字填色算符（小寫 k）。"""
    c, m, y, k = cmyk
    return f"{_fmt(c)} {_fmt(m)} {_fmt(y)} {_fmt(k)} k"


class _Content:
    def __init__(self):
        self.prologue: list = []  # 圖形（path／影像）算符，置於文字塊（BT／ET）之前
        self.ops = ["q", _fill_op(DEFAULT_TEXT_CMYK), "BT"]
        self._cur = None
        self._fill = DEFAULT_TEXT_CMYK  # 現行文字填色（預設暖黑 K92）
        # 本頁實際發出的 DeviceCMYK 著色值（TAC 檢核產出側，Sprint 93）：預設填色
        # 恆隨 prologue 發出故先入集
        self.cmyk_used: set = {tuple(DEFAULT_TEXT_CMYK)}
        # 印前標記與裁切標記的著色值另立帳本（Sprint 109）：標記落在 TrimBox 外、
        # 裁切後不入成品，分帳讓墨量報告能標出來源。**這不是豁免**：檢查器一行
        # 未動，超標仍照報 ok=False（見 ink.py 與 GAPS #42）。
        self.mark_cmyk_used: set = set()

    def set_fill(self, cmyk) -> None:
        """切換文字填色（Sprint 76 色票）：與現行相同不發算符（預設輸出形態不變）；
        `k` 為 DeviceCMYK 填色算符，於文字物件（BT 內）合法且不觸 preflight rg/RG。"""
        cmyk = tuple(cmyk)
        if cmyk != self._fill:
            self.ops.append(_fill_op(cmyk))
            self._fill = cmyk
            self.cmyk_used.add(cmyk)

    def _ledger(self, cmyk, is_mark: bool) -> None:
        """記一筆著色值到內容帳本或標記帳本（Sprint 109 分帳，見 __init__ 註解）。"""
        (self.mark_cmyk_used if is_mark else self.cmyk_used).add(tuple(cmyk))

    def fill_rect(self, cmyk, x_ll: float, y_ll: float, w: float, h: float,
                  *, is_mark: bool = False) -> None:
        """DeviceCMYK 填色矩形（獨立 q…Q 狀態塊；Sprint 109 印前標記色塊）。

        `k`（填色）＋`re`＋`f` 皆不觸 preflight 的 rg／RG 判定，且 `f` 不觸發
        no-transparency 與 no-lzw（R2 spike 以 PyMuPDF 實測確認，X-1a 仍 12/12）。
        """
        c, m, y, k = cmyk
        self._ledger(cmyk, is_mark)
        self.prologue += [
            "q",
            f"{_fmt(c)} {_fmt(m)} {_fmt(y)} {_fmt(k)} k",
            f"{x_ll:.3f} {y_ll:.3f} {_fmt(w)} {_fmt(h)} re",
            "f",
            "Q",
        ]

    def stroke_rect(self, cmyk, line_width_pt: float,
                    x_ll: float, y_ll: float, w: float, h: float,
                    *, is_mark: bool = False) -> None:
        """DeviceCMYK 描邊矩形（獨立 q…Q 狀態塊，狀態隔離；`K` 不觸 preflight rg/RG）。"""
        c, m, y, k = cmyk
        self._ledger(cmyk, is_mark)
        self.prologue += [
            "q",
            f"{_fmt(c)} {_fmt(m)} {_fmt(y)} {_fmt(k)} K",
            f"{_fmt(line_width_pt)} w",
            f"{x_ll:.3f} {y_ll:.3f} {_fmt(w)} {_fmt(h)} re",
            "S",
            "Q",
        ]

    def stroke_line(self, cmyk, line_width_pt: float,
                    x0: float, y0: float, x1: float, y1: float,
                    dash_on_pt: float = 0.0, dash_off_pt: float = 0.0,
                    *, is_mark: bool = False) -> None:
        """DeviceCMYK 描邊線段（獨立 q…Q 狀態塊）。dash_on_pt>0 時掛 `d` dash 陣列，
        dash 狀態隨 Q 還原不外洩（spike8 實證）；`d`/`m`/`l` 不觸 preflight rg/RG。"""
        c, m, y, k = cmyk
        self._ledger(cmyk, is_mark)
        ops = [
            "q",
            f"{_fmt(c)} {_fmt(m)} {_fmt(y)} {_fmt(k)} K",
            f"{_fmt(line_width_pt)} w",
        ]
        if dash_on_pt > 0:
            ops.append(f"[ {_fmt(dash_on_pt)} {_fmt(dash_off_pt)} ] 0 d")
        ops += [
            f"{x0:.3f} {y0:.3f} m",
            f"{x1:.3f} {y1:.3f} l",
            "S",
            "Q",
        ]
        self.prologue += ops

    def draw_image(self, res_name: str, w: float, h: float,
                   x_ll: float, y_ll: float) -> None:
        """置入影像 XObject（獨立 q…Q，置文字塊 BT／ET 前）：cm 縮放單位方陣至 w×h、
        平移到左下角 (x_ll, y_ll)。影像首列在上（PIL tobytes 語意），cm h>0 使影像正立。"""
        self.prologue += [
            "q",
            f"{_fmt(w)} 0 0 {_fmt(h)} {x_ll:.3f} {y_ll:.3f} cm",
            f"/{res_name} Do",
            "Q",
        ]

    def show(self, res_name: str, code: int, x: float, y: float,
             size_pt: float, rotated: bool) -> None:
        key = (res_name, round(size_pt, 4))
        if key != self._cur:
            self.ops.append(f"/{res_name} {_fmt(size_pt)} Tf")
            self._cur = key
        tm = f"0 -1 1 0 {x:.3f} {y:.3f}" if rotated else f"1 0 0 1 {x:.3f} {y:.3f}"
        self.ops.append(f"{tm} Tm <{code:04X}> Tj")

    def finish(self) -> bytes:
        return "\n".join(self.prologue + self.ops + ["ET", "Q"]).encode("latin-1")
