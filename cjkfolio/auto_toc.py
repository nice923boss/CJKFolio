"""模版層的自動目錄生成規格（Sprint 135）：目錄節怎麼組，由模版資料宣告。

與 styles.TocSpec 分工：TocSpec 是「目錄頁怎麼畫」（主版幾何：頁碼底錨、引導線），
本模組是「目錄節怎麼組」（掛哪張主版、各層條目掛哪個樣式、哪幾層不標頁碼）。
寫在模版而非程式碼，理由同 default_master／default_cover（Sprint 105／132）：
主版名與樣式名逐書而異，寫死在生成端即為對另一本書錯的名字。

本模組刻意不 import styles（styles 反過來 import 本模組），故一律拋 ValueError，
由 styles 在載入模版時改包成 TemplateError，對外錯誤型別不變。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AutoTocSpec:
    """自動目錄生成規格：主版、逐層條目樣式、選配標題、不標頁碼的層級。

    entry_styles 鍵為目錄層級（正整數），第 1 層必宣告；階層縮排由各層樣式自身的
    head_offset_chars 表達，本規格不新增幾何機制（同 book.TocSpec）。
    no_page_levels＝該層條目不標頁碼（如部名條目，參考書 p002／p003 即如此）。
    """
    master: str
    entry_styles: dict  # {層級: 段落樣式名}
    heading: str = ""  # 目錄節標題文字（""＝不放標題段）
    heading_style: str = ""
    no_page_levels: tuple = ()

    def style_for_level(self, level: int) -> str:
        """取該層條目樣式；未宣告即快速失敗（不沉默落回第一層，同 book.TocSpec）。"""
        if level not in self.entry_styles:
            raise ValueError(
                f"自動目錄第 {level} 層無條目樣式：模版 auto_toc.entry_styles 未宣告該層"
                f"（已宣告層級：{'、'.join(str(k) for k in sorted(self.entry_styles))}）")
        return self.entry_styles[level]

    def wants_page_no(self, level: int) -> bool:
        """該層條目是否標頁碼。"""
        return level not in self.no_page_levels

    def level_hints(self) -> tuple:
        """依層級序的 (層級, 條目樣式名, 是否標頁碼)，供 AI prompt 說明本書已宣告的層。

        給 AI 的是模版**已宣告的事實**（哪幾層存在、哪幾層標頁碼），不是版面幾何，
        故不違反「不採用 AI 輸出的任何數字」的分工鐵律。少了這段，AI 只能照通則
        把章名當第 1 層，遇上本書「第 1 層＝部名且不標頁碼」的宣告，整份目次會一個
        頁碼都沒有而且不報錯（靜默落空，最不該有的失效形態）。
        """
        return tuple((level, self.entry_styles[level], self.wants_page_no(level))
                     for level in sorted(self.entry_styles))


def auto_toc_from_dict(d) -> AutoTocSpec:
    """解析模版 auto_toc 區塊；名稱是否存在留待 template 建好後由 check_auto_toc 查。"""
    if not isinstance(d, dict):
        raise ValueError("auto_toc 需為物件")
    master = d.get("master")
    if not (isinstance(master, str) and master):
        raise ValueError("auto_toc.master 需為非空字串")
    raw = d.get("entry_styles")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("auto_toc.entry_styles 需為非空物件（層級 → 樣式名）")
    entry_styles = {}
    for key, value in raw.items():
        try:  # JSON 物件鍵恆為字串，層級在此轉回整數
            level = int(key)
        except (TypeError, ValueError):
            raise ValueError(
                f"auto_toc.entry_styles 的層級鍵需為整數，得到 {key!r}") from None
        if level < 1:
            raise ValueError(f"auto_toc.entry_styles 的層級需 ≥1，得到 {level}")
        if not (isinstance(value, str) and value):
            raise ValueError(f"auto_toc.entry_styles[{level}] 需為非空樣式名")
        entry_styles[level] = value
    if 1 not in entry_styles:
        raise ValueError("auto_toc.entry_styles 需宣告第 1 層條目樣式")
    heading = str(d.get("heading", ""))
    heading_style = str(d.get("heading_style", ""))
    if heading and not heading_style:
        raise ValueError("auto_toc 有 heading 時 heading_style 必填")
    levels = d.get("no_page_levels", ())
    if not isinstance(levels, (list, tuple)):
        raise ValueError("auto_toc.no_page_levels 需為陣列")
    return AutoTocSpec(
        master=master, entry_styles=entry_styles, heading=heading,
        heading_style=heading_style, no_page_levels=tuple(int(v) for v in levels))


def check_auto_toc(template) -> None:
    """auto_toc 引用的主版與樣式須真的存在（同 default_master 的存在性守門）。

    帶頁碼的層級要求該主版有 toc 配置：layout._toc_marks 對「段帶 page_no 但主版
    無 toc」是硬失敗，在模版載入時就擋掉，不留給排版階段才炸。
    """
    spec = template.auto_toc
    if spec is None:
        return
    if spec.master not in template.masters:
        raise ValueError(f"auto_toc.master「{spec.master}」不存在於 masters")
    if template.masters[spec.master].toc is None and any(
            spec.wants_page_no(level) for level in spec.entry_styles):
        raise ValueError(
            f"auto_toc.master「{spec.master}」無 toc 配置，帶頁碼的條目會在排版時失敗")
    for level, name in sorted(spec.entry_styles.items()):
        if name not in template.paragraph_styles:
            raise ValueError(
                f"auto_toc.entry_styles[{level}]「{name}」不存在於 paragraph_styles")
    if spec.heading_style and spec.heading_style not in template.paragraph_styles:
        raise ValueError(
            f"auto_toc.heading_style「{spec.heading_style}」不存在於 paragraph_styles")
