"""空白起始文件（Sprint 123）：編輯器無參數開啟時的「從零開始」狀態。

Qt 無關（同 import_core／preflight_core 慣例）。單一空段掛模版內文樣式：
引擎對空段排 0 頁（一手 probe），編輯器據此畫空紙面；第一次插入即成 1 頁。
"""
from cjkfolio.document import Document, document_from_dict


def blank_document(template, template_id: str) -> Document:
    """建未命名空白文件：單一空段，樣式與主版取自現行模版（不硬編碼樣式名）。

    走 document_from_dict 的完整驗證路徑，模版缺內文對映或預設主版時大聲失敗。
    """
    body_style = template.md_mapping["paragraph"]
    return document_from_dict({
        "schema": "cjkfolio/document@2",
        "meta": {
            "title": "未命名",
            "template": template_id,
            "master": template.default_master,
            "language": "zh-TW",
        },
        "paragraphs": [{"text": "", "style": body_style}],
    })
