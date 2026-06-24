"""Hallucination detection module for medical Q&A.

Uses LLM-based entity extraction to detect when the model might be fabricating
medical information (drugs, diseases, examinations) not supported by patient data.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _extract_entities_with_llm(text: str) -> Dict[str, List[str]]:
    """Use LLM to extract medical entities from text.
    
    Returns dict with keys: drugs, diseases, exams, symptoms, treatments
    """
    if not text or not text.strip():
        return {"drugs": [], "diseases": [], "exams": [], "symptoms": [], "treatments": []}
    
    try:
        from app.mcp.config import get_llm
        
        llm = get_llm()
        
        prompt = f"""从以下文本中提取所有医疗实体，按类别分类。

文本：
{text[:2000]}

请严格按以下JSON格式返回，每个类别提取所有出现的实体：
{{
  "drugs": ["药物名1", "药物名2"],
  "diseases": ["疾病名1", "疾病名2"],
  "exams": ["检查项目1", "检查项目2"],
  "symptoms": ["症状1", "症状2"],
  "treatments": ["治疗方式1", "治疗方式2"]
}}

注意：
- 提取所有出现的医疗实体，不要遗漏
- 药物包括：处方药、中成药、保健品（如提到具体名称）
- 疾病包括：诊断名称、病症描述
- 检查包括：化验、影像、病理等
- 症状包括：患者描述的不适
- 治疗包括：手术、放疗、化疗等
- 不要编造不存在的实体，只提取文本中明确提到的
- 只返回JSON，不要解释"""
        
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Parse JSON response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            # Ensure all keys exist with list values
            return {
                "drugs": result.get("drugs", []) or [],
                "diseases": result.get("diseases", []) or [],
                "exams": result.get("exams", []) or [],
                "symptoms": result.get("symptoms", []) or [],
                "treatments": result.get("treatments", []) or [],
            }
        
    except Exception as e:
        logger.warning(f"LLM entity extraction failed, falling back to local extraction: {e}")
    
    # Fallback to local extraction
    return _extract_entities_local(text)


def _extract_entities_local(text: str) -> Dict[str, List[str]]:
    """Fallback: local keyword-based entity extraction.
    
    Used when LLM extraction fails.
    """
    entities = {"drugs": [], "diseases": [], "exams": [], "symptoms": [], "treatments": []}
    
    # Drug suffixes
    drug_patterns = re.findall(r'[\u4e00-\u9fa5]{2,8}(?:片|胶囊|颗粒|口服液|注射液|滴丸|软膏|凝胶|贴剂|喷雾剂)', text)
    entities["drugs"].extend(drug_patterns)
    
    # Common drug name patterns
    common_drugs = re.findall(r'(?:服用|使用|服用|用药|口服|外用)\s*([\u4e00-\u9fa5]{2,10})', text)
    entities["drugs"].extend(common_drugs)
    
    # Disease patterns (XX病/XX炎/XX症)
    disease_patterns = re.findall(r'[\u4e00-\u9fa5]{2,10}(?:病|炎|症|综合征|损伤|障碍|异常|增生|结石)', text)
    entities["diseases"].extend(disease_patterns)
    
    # Common diagnoses
    diagnoses = re.findall(r'(?:诊断|确诊|患有|患有|考虑|疑似)\s*(?:为\s*)?([\u4e00-\u9fa5]{2,15})', text)
    entities["diseases"].extend(diagnoses)
    
    # Exam patterns
    exam_keywords = ['检查', '化验', '检测', '扫描', '拍片', '超声']
    for kw in exam_keywords:
        exams = re.findall(rf'[\u4e00-\u9fa5]{{2,10}}{kw}', text)
        entities["exams"].extend(exams)
    
    # Common exams
    common_exams = ['血常规', '尿常规', '生化', '肝功能', '肾功能', '血脂', '血糖', 
                    '心电图', 'CT', 'MRI', 'B超', '彩超', 'X光', '胃镜', '肠镜']
    for exam in common_exams:
        if exam in text:
            entities["exams"].append(exam)
    
    # Deduplicate
    for key in entities:
        entities[key] = list(set(entities[key]))
    
    return entities


def _extract_entities_from_data(tool_result: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract medical entities from patient data (structured records)."""
    entities = {"drugs": [], "diseases": [], "exams": [], "symptoms": [], "treatments": []}
    
    data = tool_result.get("data") or {}
    
    # Extract from medical records
    medical_records = data.get("medical_records") or []
    for record in medical_records:
        # Medications
        meds = record.get("medications") or ""
        if meds:
            for drug in re.split(r'[,，、;；\n]+', meds):
                drug = drug.strip()
                if drug and 1 < len(drug) < 50:
                    entities["drugs"].append(drug)
        
        # Diagnosis (diseases)
        diagnosis = record.get("diagnosis") or ""
        if diagnosis:
            for disease in re.split(r'[,，、;；\n]+', diagnosis):
                disease = disease.strip()
                if disease and 1 < len(disease) < 50:
                    entities["diseases"].append(disease)
        
        # Treatment plan
        treatment = record.get("treatment_plan") or ""
        if treatment:
            entities["treatments"].append(treatment.strip()[:100])
        
        # Chief complaint (symptoms)
        complaint = record.get("chief_complaint") or ""
        if complaint:
            entities["symptoms"].append(complaint.strip()[:100])
    
    # Extract from visit records
    visit_records = data.get("visit_records") or []
    for record in visit_records:
        diagnosis = record.get("diagnosis") or ""
        if diagnosis:
            for disease in re.split(r'[,，、;；\n]+', diagnosis):
                disease = disease.strip()
                if disease and 1 < len(disease) < 50:
                    entities["diseases"].append(disease)
    
    # Deduplicate
    for key in entities:
        entities[key] = list(set(entities[key]))
    
    return entities


def _check_entity_coverage(
    answer_entities: Dict[str, List[str]],
    data_entities: Dict[str, List[str]],
    context_entities: Optional[Dict[str, List[str]]] = None,
) -> Tuple[List[str], List[str]]:
    """Check which entities in the answer are not supported by patient data or context.
    
    Returns:
        (flagged_items, supported_items) tuple
    """
    flagged = []
    supported = []
    
    # Merge data and context entities for comparison
    all_known = {
        "drugs": set(data_entities.get("drugs", [])),
        "diseases": set(data_entities.get("diseases", [])),
        "exams": set(data_entities.get("exams", [])),
        "symptoms": set(data_entities.get("symptoms", [])),
        "treatments": set(data_entities.get("treatments", [])),
    }
    
    if context_entities:
        for key in all_known:
            all_known[key].update(context_entities.get(key, []))
    
    # Category labels for display
    category_labels = {
        "drugs": "药物",
        "diseases": "疾病",
        "exams": "检查",
        "symptoms": "症状",
        "treatments": "治疗",
    }
    
    # Check each category
    for category in ["drugs", "diseases", "exams", "symptoms", "treatments"]:
        answer_items = set(answer_entities.get(category, []))
        known_items = all_known[category]
        label = category_labels[category]
        
        for item in answer_items:
            # Check exact match or containment
            is_known = False
            for known in known_items:
                if item in known or known in item:
                    is_known = True
                    break
            
            if is_known:
                supported.append(f"{label}:{item}")
            else:
                flagged.append(f"{label}:{item}")
    
    return flagged, supported


def check_hallucination(
    answer: str,
    tool_result: Dict[str, Any],
    context: Optional[str] = None,
    strict_mode: bool = True,
) -> Dict[str, Any]:
    """Check for potential hallucinations in the medical answer.
    
    Uses LLM-based entity extraction to identify medical entities in the answer,
    then compares them against patient data to detect potential fabrications.
    
    Args:
        answer: The generated answer text
        tool_result: The tool execution result containing patient data
        context: Optional conversation context
        strict_mode: If True, flag all unsupported entities; if False, allow some general knowledge
        
    Returns:
        Dictionary with safe, flagged_items, supported_items, warning
    """
    if not answer:
        return {"safe": True, "flagged_items": [], "supported_items": [], "warning": None}
    
    # Extract entities from answer using LLM
    answer_entities = _extract_entities_with_llm(answer)
    
    # Extract entities from patient data
    data_entities = _extract_entities_from_data(tool_result)
    
    # Extract entities from context if provided
    context_entities = None
    if context:
        context_entities = _extract_entities_with_llm(context[:1500])
    
    # Check coverage
    flagged, supported = _check_entity_coverage(answer_entities, data_entities, context_entities)
    
    # Determine safety
    if strict_mode:
        is_safe = len(flagged) == 0
    else:
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


def apply_hallucination_check(
    answer: str,
    tool_result: Dict[str, Any],
    context: Optional[str] = None,
    strict_mode: bool = True,
) -> str:
    """Apply hallucination check and append warning if needed.
    
    Args:
        answer: The generated answer text
        tool_result: The tool execution result
        context: Optional conversation context
        strict_mode: Whether to use strict checking
        
    Returns:
        Answer with warning appended if hallucinations detected
    """
    if not answer:
        return answer
    
    result = check_hallucination(answer, tool_result, context, strict_mode)
    
    if result["warning"]:
        return answer + "\n\n" + result["warning"]
    
    return answer
