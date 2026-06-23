"""Drug interaction checking module.

Combines a local rules database with LLM-based fallback for comprehensive
drug interaction detection.
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Local drug interaction rules database
# Format: (drug1, drug2) -> (severity, warning_message)
# Severity: "high" (dangerous), "medium" (caution), "low" (minor)
KNOWN_INTERACTIONS: Dict[Tuple[str, str], Tuple[str, str]] = {
    # Anticoagulants + NSAIDs
    ("华法林", "阿司匹林"): ("high", "两者联用显著增加出血风险"),
    ("华法林", "布洛芬"): ("high", "NSAIDs增强华法林抗凝作用，增加出血风险"),
    ("华法林", "双氯芬酸"): ("high", "NSAIDs增强华法林抗凝作用，增加出血风险"),
    ("华法林", "萘普生"): ("high", "NSAIDs增强华法林抗凝作用，增加出血风险"),
    
    # Metformin + Contrast
    ("二甲双胍", "碘造影剂"): ("high", "需在使用造影剂前48小时停用二甲双胍，防止乳酸酸中毒"),
    ("二甲双胍", "造影剂"): ("high", "需在使用造影剂前48小时停用二甲双胍，防止乳酸酸中毒"),
    
    # ACE inhibitors + Potassium
    ("卡托普利", "氯化钾"): ("medium", "ACE抑制剂可升高血钾，联用高钾食物/补充剂需监测血钾"),
    ("依那普利", "氯化钾"): ("medium", "ACE抑制剂可升高血钾，联用高钾食物/补充剂需监测血钾"),
    ("缬沙坦", "氯化钾"): ("medium", "ARB可升高血钾，联用高钾食物/补充剂需监测血钾"),
    
    # Beta-blockers + Calcium channel blockers
    ("美托洛尔", "地尔硫䓬"): ("medium", "联用可能导致心动过缓、低血压"),
    ("美托洛尔", "维拉帕米"): ("high", "联用可能导致严重心动过缓、传导阻滞"),
    
    # Antibiotics interactions
    ("左氧氟沙星", "布洛芬"): ("medium", "氟喹诺酮类与NSAIDs联用可能增加癫痫风险"),
    ("头孢呋辛", "华法林"): ("medium", "头孢菌素类可能增强华法林抗凝作用"),
    
    # SSRIs + NSAIDs
    ("氟西汀", "布洛芬"): ("medium", "SSRIs与NSAIDs联用可能增加消化道出血风险"),
    ("舍曲林", "布洛芬"): ("medium", "SSRIs与NSAIDs联用可能增加消化道出血风险"),
    
    # Digoxin interactions
    ("地高辛", "胺碘酮"): ("high", "胺碘酮可使地高辛浓度升高约70%，需减量并监测"),
    ("地高辛", "维拉帕米"): ("high", "维拉帕米可使地高辛浓度升高约60%，需减量并监测"),
    
    # Statins interactions
    ("辛伐他汀", "红霉素"): ("high", "大环内酯类可显著升高他汀血药浓度，增加横纹肌溶解风险"),
    ("辛伐他汀", "克拉霉素"): ("high", "大环内酯类可显著升高他汀血药浓度，增加横纹肌溶解风险"),
    ("阿托伐他汀", "伊曲康唑"): ("medium", "唑类抗真菌药可升高他汀血药浓度"),
    
    # Thyroid medications
    ("左甲状腺素", "钙剂"): ("medium", "钙剂可降低左甲状腺素吸收，需间隔4小时服用"),
    ("左甲状腺素", "铁剂"): ("medium", "铁剂可降低左甲状腺素吸收，需间隔4小时服用"),
    ("左甲状腺素", "碳酸钙"): ("medium", "钙剂可降低左甲状腺素吸收，需间隔4小时服用"),
    
    # Diabetes medications
    ("格列本脲", "氟康唑"): ("medium", "氟康唑可增强磺脲类降糖作用，增加低血糖风险"),
    ("格列美嗪", "氟康唑"): ("medium", "氟康唑可增强磺脲类降糖作用，增加低血糖风险"),
}

# Drug name aliases for matching
DRUG_ALIASES: Dict[str, str] = {
    "对乙酰氨基酚": "扑热息痛",
    "扑热息痛": "对乙酰氨基酚",
    "维生素B12": "氰钴胺",
    "维生素C": "抗坏血酸",
    "降压药": "卡托普利",
    "降糖药": "二甲双胍",
    "消炎药": "布洛芬",
    "抗生素": "头孢呋辛",
}


def _normalize_drug_name(drug_name: str) -> str:
    """Normalize drug name using aliases."""
    normalized = drug_name.strip()
    return DRUG_ALIASES.get(normalized, normalized)


def _get_interaction_key(drug1: str, drug2: str) -> Optional[Tuple[str, str]]:
    """Get the interaction key, trying both orderings."""
    d1 = _normalize_drug_name(drug1)
    d2 = _normalize_drug_name(drug2)
    
    if (d1, d2) in KNOWN_INTERACTIONS:
        return (d1, d2)
    if (d2, d1) in KNOWN_INTERACTIONS:
        return (d2, d1)
    return None


def check_drug_interactions(
    medications: List[str],
    new_drug: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Check for drug interactions in a medication list.
    
    Args:
        medications: List of current medications
        new_drug: Optional new drug to check against current medications
        
    Returns:
        List of interaction warnings, each containing:
        - drugs: list of interacting drugs
        - severity: "high", "medium", or "low"
        - warning: warning message
    """
    if not medications:
        return []
    
    interactions = []
    checked_pairs = set()
    
    drugs_to_check = list(medications)
    if new_drug and new_drug not in drugs_to_check:
        drugs_to_check.append(new_drug)
    
    for i, drug1 in enumerate(drugs_to_check):
        for drug2 in drugs_to_check[i+1:]:
            pair_key = tuple(sorted([drug1, drug2]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)
            
            interaction_key = _get_interaction_key(drug1, drug2)
            if interaction_key:
                severity, warning = KNOWN_INTERACTIONS[interaction_key]
                interactions.append({
                    "drugs": [drug1, drug2],
                    "severity": severity,
                    "warning": warning,
                })
    
    # Sort by severity (high first)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    interactions.sort(key=lambda x: severity_order.get(x["severity"], 3))
    
    return interactions


def format_interaction_warnings(interactions: List[Dict[str, str]]) -> str:
    """Format interaction warnings into a readable string."""
    if not interactions:
        return ""
    
    lines = ["⚠️ **药物交互提醒**："]
    
    for interaction in interactions:
        drugs = " + ".join(interaction["drugs"])
        severity = interaction["severity"]
        warning = interaction["warning"]
        
        severity_label = {
            "high": "🔴 高风险",
            "medium": "🟡 中风险",
            "low": "🟢 低风险",
        }.get(severity, "⚠️ 注意")
        
        lines.append(f"- {severity_label} **{drugs}**：{warning}")
    
    lines.append("\n请在用药前咨询医生或药师，确认是否需要调整用药方案。")
    
    return "\n".join(lines)


def _check_interactions_with_llm(
    medications: List[str],
    new_drug: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Fallback: Use LLM to check drug interactions when local rules don't cover."""
    try:
        from app.mcp.config import get_llm
        
        llm = get_llm()
        
        drug_list = ", ".join(medications)
        if new_drug:
            prompt = f"""
请检查以下药物之间是否存在交互作用：
当前用药：{drug_list}
新增药物：{new_drug}

如果存在交互作用，请按以下JSON格式返回：
[{{"drugs": ["药物1", "药物2"], "severity": "high/medium/low", "warning": "交互作用说明"}}]

如果不存在交互作用，请返回空数组 []。
只返回JSON，不要解释。
"""
        else:
            prompt = f"""
请检查以下药物之间是否存在交互作用：
药物列表：{drug_list}

如果存在交互作用，请按以下JSON格式返回：
[{{"drugs": ["药物1", "药物2"], "severity": "high/medium/low", "warning": "交互作用说明"}}]

如果不存在交互作用，请返回空数组 []。
只返回JSON，不要解释。
"""
        
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Parse JSON response
        import json
        import re
        
        # Try to extract JSON array from response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            interactions = json.loads(json_match.group())
            # Validate structure
            validated = []
            for item in interactions:
                if isinstance(item, dict) and "drugs" in item and "warning" in item:
                    validated.append({
                        "drugs": item["drugs"],
                        "severity": item.get("severity", "medium"),
                        "warning": item["warning"],
                    })
            return validated
        
    except Exception as e:
        logger.warning(f"LLM drug interaction check failed: {e}")
    
    return []


def check_all_interactions(
    medications: List[str],
    new_drug: Optional[str] = None,
    use_llm_fallback: bool = True,
) -> List[Dict[str, str]]:
    """Check drug interactions with local rules + optional LLM fallback.
    
    Args:
        medications: List of current medications
        new_drug: Optional new drug to check
        use_llm_fallback: Whether to use LLM if local rules don't find interactions
        
    Returns:
        List of interaction warnings
    """
    # First check local rules
    local_interactions = check_drug_interactions(medications, new_drug)
    
    # If local rules found interactions or LLM fallback is disabled, return
    if local_interactions or not use_llm_fallback:
        return local_interactions
    
    # Try LLM fallback for uncovered interactions
    llm_interactions = _check_interactions_with_llm(medications, new_drug)
    
    return llm_interactions


def append_interaction_warnings(answer: str, interactions: List[Dict[str, str]]) -> str:
    """Append drug interaction warnings to the answer."""
    if not interactions:
        return answer
    
    warning_text = format_interaction_warnings(interactions)
    if not warning_text:
        return answer
    
    return answer + "\n\n" + warning_text
