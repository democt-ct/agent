"""Hallucination detection module for medical Q&A.

Detects when the LLM might be fabricating medical information (drugs, diseases,
examinations) that is not supported by the patient's data or the knowledge base.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Known medical entities for validation
KNOWN_DRUG_CATEGORIES = {
    "降压药": ["氨氯地平", "缬沙坦", "美托洛尔", "卡托普利", "依那普利", "硝苯地平"],
    "降糖药": ["二甲双胍", "格列本脲", "阿卡波糖", "胰岛素", "达格列净"],
    "抗生素": ["阿莫西林", "头孢呋辛", "左氧氟沙星", "阿奇霉素"],
    "解热镇痛": ["布洛芬", "对乙酰氨基酚", "阿司匹林", "双氯芬酸"],
    "抗凝药": ["华法林", "利伐沙班", "阿司匹林"],
    "降脂药": ["辛伐他汀", "阿托伐他汀", "瑞舒伐他汀"],
}

# Common disease names that should not be invented
COMMON_DISEASES = [
    "高血压", "糖尿病", "冠心病", "心肌梗死", "脑梗死", "脑出血",
    "肺炎", "支气管炎", "哮喘", "慢性阻塞性肺疾病",
    "胃炎", "胃溃疡", "十二指肠溃疡", "肝炎", "胆囊炎",
    "肾结石", "尿路感染", "前列腺炎",
    "甲状腺功能亢进", "甲状腺功能减退",
    "贫血", "血小板减少", "白血病",
    "骨折", "关节炎", "腰椎间盘突出",
    "抑郁症", "焦虑症", "失眠",
]

# Common examination items
COMMON_EXAMS = [
    "血常规", "尿常规", "生化全套", "肝功能", "肾功能", "血脂",
    "空腹血糖", "糖化血红蛋白", "甲状腺功能",
    "心电图", "胸片", "CT", "MRI", "B超", "彩超",
    "胃镜", "肠镜", "支气管镜",
    "病理检查", "基因检测",
]


def _extract_medical_entities(text: str) -> Dict[str, List[str]]:
    """Extract medical entities from text."""
    entities = {
        "drugs": [],
        "diseases": [],
        "exams": [],
    }
    
    # Extract drugs
    for category, drugs in KNOWN_DRUG_CATEGORIES.items():
        for drug in drugs:
            if drug in text:
                entities["drugs"].append(drug)
    
    # Extract diseases
    for disease in COMMON_DISEASES:
        if disease in text:
            entities["diseases"].append(disease)
    
    # Extract examinations
    for exam in COMMON_EXAMS:
        if exam in text:
            entities["exams"].append(exam)
    
    return entities


def _extract_entities_from_data(tool_result: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract medical entities from patient data."""
    entities = {
        "drugs": [],
        "diseases": [],
        "exams": [],
    }
    
    data = tool_result.get("data") or {}
    
    # Extract from medical records
    medical_records = data.get("medical_records") or []
    for record in medical_records:
        # Medications
        meds = record.get("medications") or ""
        if meds:
            for drug in meds.split(","):
                drug = drug.strip()
                if drug and len(drug) < 30:
                    entities["drugs"].append(drug)
        
        # Diagnosis (diseases)
        diagnosis = record.get("diagnosis") or ""
        if diagnosis:
            # Split by common delimiters
            for disease in re.split(r'[,，、;；\n]+', diagnosis):
                disease = disease.strip()
                if disease and len(disease) < 50:
                    entities["diseases"].append(disease)
    
    # Extract from visit records
    visit_records = data.get("visit_records") or []
    for record in visit_records:
        diagnosis = record.get("diagnosis") or ""
        if diagnosis:
            for disease in re.split(r'[,，、;；\n]+', diagnosis):
                disease = disease.strip()
                if disease and len(disease) < 50:
                    entities["diseases"].append(disease)
    
    # Deduplicate
    for key in entities:
        entities[key] = list(set(entities[key]))
    
    return entities


def _check_entity_coverage(
    answer_entities: Dict[str, List[str]],
    data_entities: Dict[str, List[str]],
) -> Tuple[List[str], List[str]]:
    """Check which entities in the answer are not supported by data.
    
    Returns:
        (flagged_entities, supported_entities) tuple
    """
    flagged = []
    supported = []
    
    # Check drugs
    answer_drugs = set(answer_entities.get("drugs", []))
    data_drugs = set(data_entities.get("drugs", []))
    
    for drug in answer_drugs:
        if drug in data_drugs:
            supported.append(f"药物:{drug}")
        else:
            flagged.append(f"药物:{drug}")
    
    # Check diseases
    answer_diseases = set(answer_entities.get("diseases", []))
    data_diseases = set(data_entities.get("diseases", []))
    
    for disease in answer_diseases:
        if disease in data_diseases:
            supported.append(f"疾病:{disease}")
        else:
            flagged.append(f"疾病:{disease}")
    
    # Check exams
    answer_exams = set(answer_entities.get("exams", []))
    data_exams = set(data_entities.get("exams", []))
    
    for exam in answer_exams:
        if exam in data_exams:
            supported.append(f"检查:{exam}")
        else:
            flagged.append(f"检查:{exam}")
    
    return flagged, supported


def check_hallucination(
    answer: str,
    tool_result: Dict[str, Any],
    context: Optional[str] = None,
    strict_mode: bool = True,
) -> Dict[str, Any]:
    """Check for potential hallucinations in the medical answer.
    
    Args:
        answer: The generated answer text
        tool_result: The tool execution result containing patient data
        context: Optional conversation context
        strict_mode: If True, flag all unsupported entities; if False, only flag obvious fabrications
        
    Returns:
        Dictionary containing:
        - safe: bool indicating if the answer is safe
        - flagged_items: list of potentially fabricated items
        - supported_items: list of items supported by data
        - warning: warning message if unsafe
    """
    if not answer:
        return {"safe": True, "flagged_items": [], "supported_items": [], "warning": None}
    
    # Extract entities from answer
    answer_entities = _extract_medical_entities(answer)
    
    # Extract entities from patient data
    data_entities = _extract_entities_from_data(tool_result)
    
    # Also check context if provided
    if context:
        context_entities = _extract_medical_entities(context)
        for key in data_entities:
            data_entities[key] = list(set(data_entities[key] + context_entities[key]))
    
    # Check coverage
    flagged, supported = _check_entity_coverage(answer_entities, data_entities)
    
    # In strict mode, flag all unsupported entities
    # In non-strict mode, only flag if there are many unsupported entities
    if strict_mode:
        is_safe = len(flagged) == 0
    else:
        # Allow a few unsupported entities (e.g., general knowledge)
        is_safe = len(flagged) <= 2
    
    warning = None
    if not is_safe:
        flagged_list = "、".join(flagged[:5])
        warning = (
            f"⚠️ **内容核实提醒**：回答中提到的 {flagged_list} 无法从您的病历资料中确认。"
            f"请以医生的诊断和医嘱为准，如有疑问请及时咨询主治医生。"
        )
    
    return {
        "safe": is_safe,
        "flagged_items": flagged,
        "supported_items": supported,
        "warning": warning,
    }


def _check_with_llm(
    answer: str,
    context: str,
    patient_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Use LLM to verify medical facts in the answer.
    
    This is a more thorough but expensive check.
    """
    try:
        from app.mcp.config import get_llm
        
        llm = get_llm()
        
        # Prepare patient data summary
        data_summary = ""
        medical_records = patient_data.get("medical_records") or []
        if medical_records:
            latest = medical_records[0]
            data_summary += f"诊断: {latest.get('diagnosis', '无')}\n"
            data_summary += f"用药: {latest.get('medications', '无')}\n"
        
        prompt = f"""
你是一个医疗事实核查员。请检查以下回答是否包含编造的医疗信息。

患者资料摘要：
{data_summary}

对话上下文：
{context[:500] if context else "无"}

回答内容：
{answer}

请检查回答中是否有以下情况：
1. 编造不存在的药物名称
2. 编造不存在的疾病诊断
3. 编造不存在的检查项目
4. 给出患者资料中没有的用药建议

如果发现编造，请按JSON格式返回：
{{"safe": false, "flagged_items": ["编造项1", "编造项2"], "warning": "警告信息"}}

如果回答安全，请返回：
{{"safe": true, "flagged_items": [], "warning": null}}

只返回JSON，不要解释。
"""
        
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Parse JSON response
        import json
        import re
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "safe": result.get("safe", True),
                "flagged_items": result.get("flagged_items", []),
                "supported_items": [],
                "warning": result.get("warning"),
            }
        
    except Exception as e:
        logger.warning(f"LLM hallucination check failed: {e}")
    
    # Default to safe if LLM check fails
    return {"safe": True, "flagged_items": [], "supported_items": [], "warning": None}


def apply_hallucination_check(
    answer: str,
    tool_result: Dict[str, Any],
    context: Optional[str] = None,
    strict_mode: bool = True,
    use_llm_fallback: bool = False,
) -> str:
    """Apply hallucination check and append warning if needed.
    
    Args:
        answer: The generated answer text
        tool_result: The tool execution result
        context: Optional conversation context
        strict_mode: Whether to use strict checking
        use_llm_fallback: Whether to use LLM for additional verification
        
    Returns:
        Answer with warning appended if hallucinations detected
    """
    if not answer:
        return answer
    
    # First check with local rules
    result = check_hallucination(answer, tool_result, context, strict_mode)
    
    # If local check found issues or LLM fallback is disabled
    if not result["safe"] or not use_llm_fallback:
        if result["warning"]:
            return answer + "\n\n" + result["warning"]
        return answer
    
    # If local check passed but we want additional LLM verification
    llm_result = _check_with_llm(answer, context or "", tool_result.get("data") or {})
    
    if not llm_result["safe"] and llm_result["warning"]:
        return answer + "\n\n" + llm_result["warning"]
    
    return answer
