"""文件資訊動作 mixin（Sprint 128：丙2 字數統計與文件資訊）。

總字數、段數、頁數、段落樣式用量過去無處可看（PLAN 丙2）。doc 與 layout_result
皆在記憶體，純呈現不重算。純函式 document_stats 與 UI 分離便於離屏釘死。

依賴 EditorWindow 提供：self.doc／self.layout_result／self.statusBar()。
"""
from dataclasses import dataclass

from editor.info_panel import DocInfoDialog


@dataclass(frozen=True)
class DocStats:
    """文件統計快照：總字數（body 段字面）、段數、版面頁數、段落樣式用量。"""

    total_chars: int
    paragraph_count: int
    page_count: int
    style_usage: tuple  # ((style_name, count), ...) 依用量遞減、同量依樣式名遞增


def document_stats(doc, layout) -> DocStats:
    """自 doc 與版面結果算統計（純函式，不動狀態）。

    總字數＝各 body 段 text 長度和（含標點與空白；文字框與圖片不計，v1 以 body 為主）。
    段落樣式用量＝每段落樣式的段數直方，依用量遞減排序（同量依樣式名遞增）。
    """
    total = sum(len(p.text) for p in doc.paragraphs)
    counts = {}
    for p in doc.paragraphs:
        counts[p.style] = counts.get(p.style, 0) + 1
    usage = tuple(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    return DocStats(
        total_chars=total,
        paragraph_count=len(doc.paragraphs),
        page_count=len(layout.pages),
        style_usage=usage,
    )


class InfoActionsMixin:
    """工具＞文件資訊…：唯讀統計面板（丙2）。"""

    def _show_document_info(self) -> None:
        """開文件資訊對話框（純呈現目前 doc／layout 的統計）。"""
        stats = document_stats(self.doc, self.layout_result)
        self.statusBar().showMessage(
            f"文件資訊：{stats.total_chars} 字、{stats.paragraph_count} 段、"
            f"{stats.page_count} 頁、{len(stats.style_usage)} 種段落樣式")
        DocInfoDialog(stats, parent=self).exec()
