"""三層樣式模型（cjkfolio.styles）：模版載入與驗證。"""
import json
from pathlib import Path

import pytest

from cjkfolio.styles import (
    FrameSpec,
    RuleSpec,
    TemplateError,
    TocSpec,
    load_template,
    template_from_dict,
)

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "neizai-zhengli.json"


@pytest.fixture(scope="module")
def template():
    return load_template(TEMPLATE)


def test_template_three_layers_complete(template):
    # §4.2：15 段落樣式＋圖說-辰宇落雁（Sprint 27，G 圖文版）＋個案扉頁大標（Sprint 33 拆分）＋個案欄標-黑W7（Sprint 37，slot 0 建模）＋封面書名-明體W9（Sprint 132）＋目錄-目次標題（Sprint 135，p002 一手量測）＝20、9 字元樣式、8 主版（A〜G＋H-封面）
    assert len(template.paragraph_styles) == 20
    assert len(template.character_styles) == 9
    assert len(template.masters) == 8
    assert template.default_cover == "H-封面"  # 封面主版由模版宣告（同 default_master）


def test_body_style_matches_measured_values(template):
    body = template.paragraph_styles["內文-明體直排"]
    assert body.size_pt == 11.5
    assert body.font_family == "思源宋體 TC"
    assert body.font_weight == "regular"
    assert body.indent_chars == 2
    assert body.para_gap_slots == 1
    assert body.source_font == "DFMingStd-W3"


def test_case_info_size_single_and_distinct_from_preface(template):
    """個案中標 vs 推薦序大標級數釐清（Sprint 34 量測，GAPS #13 剩項）：模版原 note
    記「個案中標另有 12.9pt 變體見掃描」為誤導待查標記。量測參考書 33 個案扉頁：
    右半頁頂 NotoSans 僅 11.4pt（資訊列副標「【欄位甲】…」）＋17.9pt（大標），12.9pt
    0 命中；全書 81 個 12.9pt NotoSans span 皆序文標題句（PDF 3/6/8/12/14/16/174 左半）。
    故個案中標＝單一 11.4pt，12.9pt 專屬 推薦序大標-黑體，二者不共用（守門防依誤導 note
    把 12.9 併回個案中標）。"""
    info = template.paragraph_styles["個案中標-NotoSans"]
    preface = template.paragraph_styles["推薦序大標-黑體"]
    assert info.size_pt == pytest.approx(11.4)      # 個案扉頁資訊列副標，單一級數
    assert preface.size_pt == pytest.approx(12.9)   # 序文標題，Sprint 23 勘誤定案
    # 同 source_font（NotoSansCJKtc-Medium）但級數與用途分離：勿把 12.9 併入個案中標
    assert info.source_font == preface.source_font == "NotoSansCJKtc-Medium"
    assert info.size_pt != preface.size_pt


def test_case_info_distinct_from_slot0_hei_label_and_case_no(template):
    """個案中標 vs slot 0 黑 W7 欄標／頁腳 Case 編號釐清（Sprint 35 量測，GAPS #13 剩項）：
    模版原 note 與 C 主版 evidence 記「slot 0 資訊列＝個案中標 11.4pt 副標＋Case 編號黑 W5
    13pt『01』雙元素」。量測參考書 33 個案扉頁交叉驗證（兩路探針）：slot 0（cx 354）實為
    DFHeiStd-W7 11.5pt（26 頁）／10.5pt（7 頁）欄標「欄標甲／欄標乙／欄標丙／欄標丁／
    欄標戊」；黑體與大字數字編號「01」全書 0 命中，真書 Case 編號＝頁腳 PepitaMT
    9pt「Case N」（top 508.3）；個案中標 NotoSans 11.4pt（【欄位甲】【欄位乙】）cx 全落 93~231
    資訊區，非 slot 0。故 slot 0 非個案中標、亦無 13pt Case 編號（守門防依誤導 note 把黑 W7
    欄標字型或虛構 13pt Case 編號併入個案中標）。黑 W7 欄標樣式與個案中標移資訊區為後續專項。"""
    info = template.paragraph_styles["個案中標-NotoSans"]
    # 個案中標＝NotoSans Medium 11.4pt（資訊區欄位標籤），非 slot 0 黑 W7 欄標
    assert info.source_font == "NotoSansCJKtc-Medium"
    assert info.font_weight == "medium"
    assert info.size_pt == pytest.approx(11.4)
    # 非 slot 0 黑 W7 欄標級數（DFHeiStd-W7 11.5／10.5pt）、非虛構 Case 編號 13pt
    assert info.size_pt != pytest.approx(11.5)
    assert info.size_pt != pytest.approx(10.5)
    assert info.size_pt != pytest.approx(13.0)


def test_case_hei_label_style_modeled(template):
    """個案欄標-黑W7（Sprint 37，slot 0 一手量測 33 個案扉頁，Owner 定案升級 C）：
    Sprint 35 揭露 slot 0（cx 354）＝DFHeiStd-W7 欄標非個案中標，本 Sprint 建模。量測
    （33 頁聚合）：欄標首字頂 92.1＝天頭 92.09（承 A、lead_offset 0，墨頂差為字型 bearing）、
    縱向 4~6 字佔 block slot 0 一行；11.5pt×26 頁（「欄標甲／欄標乙」等）為主流，
    10.5pt×7 頁（「欄標戊」訪談頁）為變體（note 記錄，主流建模）。DFHeiStd-W7 對映
    思源黑體 Bold（§8 可散布，W7＝Bold；別於章名明 W7 用 heavy＝思源宋體無 Bold 檔）。
    para_gap 0（欄標 slot 0 與大標 slot 1 相鄰）。資訊區個案中標移入為 Sprint 38 專項。"""
    label = template.paragraph_styles["個案欄標-黑W7"]
    assert label.font_family == "思源黑體 TC"
    assert label.font_weight == "bold"            # W7＝Bold（思源黑體有 Bold 檔，不 fallback）
    assert label.size_pt == pytest.approx(11.5)   # 主流 26 頁（10.5pt 訪談頁變體記 note）
    assert label.indent_chars == 0                # 欄標無縮排（天頭 92.09 起）
    assert label.para_gap_slots == 0              # slot 0 與大標 slot 1 相鄰
    assert label.lead_offset_pt == 0.0            # 首字框頂＝天頭（墨頂 92.1 差為字型 bearing）
    assert label.source_font == "DFHeiStd-W7"
    # 與個案中標分離：欄標＝黑 W7 Bold 11.5pt slot 0；個案中標＝Noto Medium 11.4pt 資訊區
    info = template.paragraph_styles["個案中標-NotoSans"]
    assert label.source_font != info.source_font
    assert label.font_weight != info.font_weight


def test_handwritten_variants_measured_not_conflated(template):
    """旁注 9pt／Case 編號 15.9pt 兩待查變體量測確認（Sprint 36，承 Sprint 34 Gate 3
    「掃描見變體」待查標記清查收尾）：與 Sprint 34／35「掃描見變體＝誤植 0 命中」相反，
    一手探針證兩變體真實存在。HanziPenTC-W5 除 8.0pt 主體另有 9.0pt（raw 8.955，4 頁
    p25／60／61／93 圖注旁注大一號、非頁腳）；PepitaMT 除 9.0pt 頁腳主體（Case N，top
    508.3）另有 15.9pt（raw 15.92，10 頁章扉大號 top 86.2）＋10.4pt（p1／p2 目錄 Case
    編號）。模版建模主體級數（旁注 8pt、Case 編號頁腳 9pt），變體屬美術／自由佈局層
    Phase 1 無渲染用例不建獨立樣式（GAPS #13 後續專項）。守門釘主體級數與 source_font，
    防變體級數併入主體、防 Pepita 15.9 章扉大號與辰宇落雁 15.9 圖說混淆（同級不同字型）。"""
    note = template.paragraph_styles["旁注-手札圖注"]
    case_no = template.character_styles["Case編號-手寫拉丁"]
    caption = template.paragraph_styles["圖說-辰宇落雁"]
    # 旁注主體＝華康手札體 8pt（9pt 為量測記錄之圖注變體，不建獨立樣式）
    assert note.source_font == "HanziPenTC-W5"
    assert note.size_pt == pytest.approx(8.0)
    assert note.size_pt != pytest.approx(9.0)
    # Case 編號主體＝Pepita 9pt 頁腳（15.9 章扉、10.4 目錄為量測記錄變體，不建獨立樣式）
    assert case_no.source_font == "PepitaMT"
    assert case_no.size_pt == pytest.approx(9.0)
    assert case_no.size_pt != pytest.approx(15.9)
    # Pepita 15.9 章扉大號與辰宇落雁 15.9 圖說同級不同字型：勿混淆
    assert caption.size_pt == pytest.approx(15.9)
    assert caption.source_font == "ChenYuluoyan-Thin"
    assert case_no.source_font != caption.source_font


def test_master_a_geometry_from_measurements(template):
    a = template.masters["A-內文版"]
    assert a.grid.chars_per_line == 32
    assert a.grid.lines_per_page == 13
    assert a.grid.char_advance_pt == 12.08
    assert a.grid.line_pitch_pt == 23.0
    assert a.grid.base_size_pt == 11.5
    assert a.margins.top_mm == 32.49
    assert a.margins.outer_mm == 21.0
    assert a.mirror is True


def test_template_page_size_and_colors(template):
    assert template.page_width_mm == 148.0
    assert template.page_height_mm == 210.0
    warm = template.colors["暖黑"]  # Sprint 76 結構化色票（§1 量測＋§9 印刷 K92）
    assert warm.hex == "#231f20"
    assert warm.cmyk == (0.0, 0.0, 0.0, 0.92)
    assert template.colors["虛線灰"].cmyk == (0.0, 0.0, 0.0, 0.57)  # p003 一手（Sprint 15）


def test_template_md_mapping_present(template):
    m = template.md_mapping
    assert m["h1"] == "章名大標-明體W7"
    assert m["h2"] == "個案大標-NotoSans"
    assert m["h3"] == "章節小標-黑體"
    assert m["blockquote"] == "引文-仿宋語錄"
    assert m["paragraph"] == "內文-明體直排"


def test_master_a_footer_spec(template):
    footer = template.masters["A-內文版"].footer
    num = footer["page_number"]
    assert num.style == "頁碼數字-GillSans"
    assert num.source == "number"
    assert num.pages == "all"
    assert num.baseline_from_top_pt == 530.43
    title = footer["running_title"]
    assert title.source == "title"
    assert title.pages == "even"  # 書名書眉在偶數頁＝右頁（真書三向互證，Sprint 22）
    assert template.masters["B-部扉"].footer == {}


def test_template_missing_masters_rejected():
    with pytest.raises(TemplateError, match="masters"):
        template_from_dict({
            "schema": "cjkfolio/template@1",
            "name": "壞模版",
            "page": {"width_mm": 148, "height_mm": 210},
            "paragraph_styles": {},
            "character_styles": {},
        })


# ---------- 向量裝飾框（Sprint 14：CIP 細框） ----------

def test_master_frame_parsing(template):
    # 值為 p178 一手量測（Sprint 19）：框色暖黑同內文（單 K92）、線寬 0.14、pad 不對稱
    f = template.masters["F-版權頁"].frame
    assert isinstance(f, FrameSpec)
    assert f.kind == "cip-box"
    assert f.cmyk == (0.0, 0.0, 0.0, 0.92)
    assert f.line_width_pt == 0.14
    assert f.pad_pt == 5.05
    assert f.pad_v_pt == 4.94
    # 非版權頁主版無框（None）
    assert template.masters["A-內文版"].frame is None
    assert template.masters["B-部扉"].frame is None


def _template_with_frame(frame_dict):
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["F-版權頁"]["frame"] = frame_dict
    return data


def test_frame_unknown_kind_rejected():
    with pytest.raises(TemplateError, match="框類型"):
        template_from_dict(_template_with_frame({"kind": "菱形雙線"}))


def test_frame_bad_cmyk_rejected():
    with pytest.raises(TemplateError, match="cmyk"):
        template_from_dict(_template_with_frame({"kind": "cip-box", "cmyk": [0, 0, 0]}))


def test_frame_defaults_when_optional_omitted():
    tpl = template_from_dict(_template_with_frame({"kind": "cip-box"}))
    f = tpl.masters["F-版權頁"].frame
    assert f.cmyk == (0.0, 0.0, 0.0, 1.0)  # 預設純黑
    assert f.line_width_pt == 0.5
    assert f.pad_pt == 6.0
    assert f.pad_v_pt is None  # 選配：未給時垂直 pad 沿用 pad_pt


def test_frame_pad_v_parsing():
    tpl = template_from_dict(_template_with_frame(
        {"kind": "cip-box", "pad_pt": 5.05, "pad_v_pt": 4.94}))
    f = tpl.masters["F-版權頁"].frame
    assert f.pad_pt == pytest.approx(5.05)
    assert f.pad_v_pt == pytest.approx(4.94)


# ---------- 向量裝飾線（Sprint 15：目錄水平虛線） ----------

TOC_RULE_DICT = {  # 移除前 neizai-zhengli.json 的 D-目錄 rule 原值（Sprint 141）
    "kind": "toc-rule", "cmyk": [0, 0, 0, 0.57], "line_width_pt": 1.0,
    "dash_on_pt": 3.0, "dash_off_pt": 2.0, "y_from_top_pt": 122.46,
    "break_before_pt": 28.5, "break_after_pt": 3.9,
}


def test_master_rule_parsing(template):
    """rule 區塊解析成 RuleSpec；產品模版自 Sprint 141 起一律不宣告 rule。"""
    r = template_from_dict(_template_with_rule(TOC_RULE_DICT)).masters["D-目錄"].rule
    assert isinstance(r, RuleSpec)
    assert r.kind == "toc-rule"
    assert r.cmyk == (0.0, 0.0, 0.0, 0.57)  # 灰 K57（參考書 p003 實測 RGB 0.427 推導）
    assert r.line_width_pt == 1.0
    assert r.dash_on_pt == 3.0 and r.dash_off_pt == 2.0  # 實測 dash pattern [3 2]
    assert r.y_from_top_pt == pytest.approx(122.46)  # 實測天頭下位置
    # 未宣告 rule 的主版為 None；D-目錄 於 Sprint 141 依 Owner 指示移除虛線後同列
    assert template.masters["A-內文版"].rule is None
    assert template.masters["F-版權頁"].rule is None
    assert template.masters["D-目錄"].rule is None


def _template_with_rule(rule_dict):
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["D-目錄"]["rule"] = rule_dict
    return data


def test_rule_unknown_kind_rejected():
    with pytest.raises(TemplateError, match="線類型"):
        template_from_dict(_template_with_rule({"kind": "波浪線", "y_from_top_pt": 100}))


def test_rule_bad_cmyk_rejected():
    with pytest.raises(TemplateError, match="cmyk"):
        template_from_dict(_template_with_rule(
            {"kind": "toc-rule", "y_from_top_pt": 100, "cmyk": [0, 0]}))


def test_rule_missing_y_rejected():
    with pytest.raises(TemplateError, match="y_from_top_pt"):
        template_from_dict(_template_with_rule({"kind": "toc-rule"}))


def test_rule_defaults_when_optional_omitted():
    tpl = template_from_dict(_template_with_rule({"kind": "toc-rule", "y_from_top_pt": 100.0}))
    r = tpl.masters["D-目錄"].rule
    assert r.cmyk == (0.0, 0.0, 0.0, 1.0)  # 預設純黑
    assert r.line_width_pt == 1.0
    assert r.dash_on_pt == 3.0 and r.dash_off_pt == 2.0
    assert r.bleed_extend_pt == pytest.approx(3.0 * 72.0 / 25.4)  # 預設出血 3mm


# ---------- 目錄條目頁碼配置（Sprint 16） ----------

def test_master_toc_parsing(template):
    t = template.masters["D-目錄"].toc
    assert isinstance(t, TocSpec)
    assert t.page_no_style == "頁碼數字-GillSans"
    assert t.page_no_bottom_pt == pytest.approx(490.0)  # p003 頁碼末位底實測
    assert t.leader_width_pt == pytest.approx(0.1)      # 引導線寬實測
    assert t.leader_gap_pt == pytest.approx(2.0)
    assert t.leader_cmyk == (0.0, 0.0, 0.0, 0.92)       # 引導線同文字單 K92
    # 非目錄主版無 toc 配置
    assert template.masters["A-內文版"].toc is None


def _template_with_toc(toc_dict):
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["D-目錄"]["toc"] = toc_dict
    return data


def test_toc_missing_required_rejected():
    with pytest.raises(TemplateError, match="page_no_style"):
        template_from_dict(_template_with_toc({"page_no_bottom_pt": 490}))
    with pytest.raises(TemplateError, match="page_no_bottom_pt"):
        template_from_dict(_template_with_toc({"page_no_style": "頁碼數字-GillSans"}))


def test_toc_unknown_page_no_style_rejected():
    with pytest.raises(TemplateError, match="頁碼字元樣式"):
        template_from_dict(_template_with_toc(
            {"page_no_style": "不存在的樣式", "page_no_bottom_pt": 490}))


# ---------- 圖框保留區（Sprint 27：G 圖文版照片區） ----------

def test_master_figure_parsing(template):
    from cjkfolio.styles import FigureSpec
    fig = template.masters["G-圖文版"].figure
    assert isinstance(fig, FigureSpec)
    assert fig.kind == "photo-slot"
    # 典型雙照片全頁一手量測（Sprint 27，tools/measure_figure_page.py，32 頁）
    assert fig.top_from_top_pt == pytest.approx(107.04)
    assert fig.bottom_from_top_pt == pytest.approx(467.62)
    assert fig.cmyk == (0.0, 0.0, 0.0, 0.3)  # 淡佔位灰
    assert fig.dash_on_pt == pytest.approx(4.0) and fig.dash_off_pt == pytest.approx(3.0)
    # 非圖文主版無圖框保留區（None）
    assert template.masters["A-內文版"].figure is None
    assert template.masters["F-版權頁"].figure is None


def test_figure_caption_style_present(template):
    # 圖說標籤段落樣式：辰宇落雁體 15.9pt（量測 15.92，與裝飾大字-辰宇落雁體同構）
    cap = template.paragraph_styles["圖說-辰宇落雁"]
    assert cap.font_family == "辰宇落雁體"
    assert cap.size_pt == pytest.approx(15.9)
    assert cap.source_font == "ChenYuluoyan-Thin"


def _template_with_figure(figure_dict):
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["masters"]["G-圖文版"]["figure"] = figure_dict
    return data


def test_figure_unknown_kind_rejected():
    with pytest.raises(TemplateError, match="圖框類型"):
        template_from_dict(_template_with_figure(
            {"kind": "圓角框", "top_from_top_pt": 107, "bottom_from_top_pt": 467}))


def test_figure_bad_cmyk_rejected():
    with pytest.raises(TemplateError, match="cmyk"):
        template_from_dict(_template_with_figure(
            {"kind": "photo-slot", "top_from_top_pt": 107, "bottom_from_top_pt": 467,
             "cmyk": [0, 0, 0]}))


def test_figure_bottom_must_exceed_top_rejected():
    with pytest.raises(TemplateError, match="bottom_from_top_pt"):
        template_from_dict(_template_with_figure(
            {"kind": "photo-slot", "top_from_top_pt": 467, "bottom_from_top_pt": 107}))


def test_figure_missing_required_rejected():
    with pytest.raises(TemplateError, match="top_from_top_pt"):
        template_from_dict(_template_with_figure(
            {"kind": "photo-slot", "bottom_from_top_pt": 467}))


def test_figure_defaults_when_optional_omitted():
    tpl = template_from_dict(_template_with_figure(
        {"kind": "photo-slot", "top_from_top_pt": 107.0, "bottom_from_top_pt": 467.0}))
    fig = tpl.masters["G-圖文版"].figure
    assert fig.cmyk == (0.0, 0.0, 0.0, 0.3)  # 預設淡佔位灰
    assert fig.line_width_pt == pytest.approx(0.5)
    assert fig.dash_on_pt == pytest.approx(4.0) and fig.dash_off_pt == pytest.approx(3.0)
