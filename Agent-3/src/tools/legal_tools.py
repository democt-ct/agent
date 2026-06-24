"""Legal Agent 工具集 -- SQLite 持久化实现.

每个函数返回 dict,与 ToolDef.implementation 签名对齐.
"""

from __future__ import annotations

from src.tools.base import ToolDef
from src.tools.db import db_search_contract, db_check_compliance

# ── 工具实现 ─────────────────────────────────────────────────────

def search_contract(keyword: str) -> dict:
    """搜索合同条款.

    Args:
        keyword: 搜索关键词(如 保密,竞业,知识产权,违约).

    Returns:
        匹配的合同条款.
    """
    result = db_search_contract(keyword)
    if result["matches"] == 0:
        return {
            "message": f"未找到含'{keyword}'的合同条款",
            "available_keywords": result["available_keywords"],
        }
    return result


def check_compliance(doc_summary: str) -> dict:
    """合规性初步检查.

    Args:
        doc_summary: 待检查事项的简要描述.

    Returns:
        合规风险和建议.
    """
    result = db_check_compliance(doc_summary)
    if result is None:
        return {
            "message": "未匹配到特定合规规则",
            "recommendation": "请提供更多信息或联系法务部人工审核",
        }
    return result


# ── 工具列表 ─────────────────────────────────────────────────────

LEGAL_TOOLS: list[ToolDef] = [
    ToolDef(
        name="search_contract",
        description=(
            "搜索合同条款库.输入关键词(如 保密,竞业,知识产权,违约,数据保护),"
            "返回相关的合同条款原文."
        ),
        parameters={
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词,如 保密,竞业,知识产权",
                },
            },
            "required": ["keyword"],
        },
        implementation=search_contract,
    ),
    ToolDef(
        name="check_compliance",
        description=(
            "对某事项进行合规性初步检查.输入事项简述(如 跨境数据传输,竞业限制条款),"
            "返回风险等级和法务建议."
        ),
        parameters={
            "type": "object",
            "properties": {
                "doc_summary": {
                    "type": "string",
                    "description": "待检查事项的简要描述",
                },
            },
            "required": ["doc_summary"],
        },
        implementation=check_compliance,
    ),
]
