"""測試共用夾具：目錄天頭虛線的回歸模版（Sprint 141）。

Sprint 141 依 Owner 指示，把 rule 區塊從 templates/neizai-zhengli.json 的
D-目錄 主版移除，成品目錄不再印那條水平虛線。Sprint 15／21 的虛線機制本身
（primitives.toc_rule_line／toc_rule_segments、styles.RuleSpec、render 的
rule_breaks、pdf_writer 的 dash 描邊）全部保留，另有模版可宣告 rule 使用。

機制的回歸保護因此不能再依附產品模版，改由本夾具把移除前的實測值注回一份
模版副本，虛線相關測試吃這份。數值即移除前 neizai-zhengli.json 的原值
（p002／p003 一手量測，Sprint 15／21／24）。

只放這一個夾具：本專案測試檔各自持有 module 級 template 夾具（自成一體），
不在此處集中化，避免既有測試的來源模版被隱式改寫。
"""
from dataclasses import replace
from pathlib import Path

import pytest

from cjkfolio.styles import RuleSpec, load_template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neizai-zhengli.json"

TOC_RULE = RuleSpec(
    kind="toc-rule",
    y_from_top_pt=122.46,      # 實測天頭下位置
    cmyk=(0.0, 0.0, 0.0, 0.57),  # 灰 K57（p003 實測 RGB 0.427 推導）
    line_width_pt=1.0,
    dash_on_pt=3.0,
    dash_off_pt=2.0,
    break_before_pt=28.5,      # 篇名嵌線斷開（Sprint 21 實測中值）
    break_after_pt=3.9,
)


@pytest.fixture(scope="module")
def toc_rule_template():
    """neizai-zhengli ＋ D-目錄 主版注回 toc-rule；其餘欄位與產品模版同。"""
    template = load_template(TEMPLATE)
    master = replace(template.masters["D-目錄"], rule=TOC_RULE)
    return replace(template, masters={**template.masters, "D-目錄": master})
