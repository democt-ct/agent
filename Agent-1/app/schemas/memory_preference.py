from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryPreferenceBase(BaseModel):
    answer_style: str = Field(default="standard", description="回答风格：brief/standard/detailed")
    answer_length: str = Field(default="standard", description="回答长度：short/standard/long")
    tone_style: str = Field(default="warm", description="语气风格：warm/direct/reassuring")
    medical_term_level: str = Field(default="plain", description="术语级别：plain/mixed/professional")
    risk_alert_level: str = Field(default="medium", description="风险提醒强度：low/medium/high")
    preferred_language: str = Field(default="zh-CN", description="偏好语言")
    prefer_summary_first: bool = Field(default=True, description="是否优先先给结论")
    prefer_step_by_step: bool = Field(default=False, description="是否偏好分步骤说明")
    notes: Optional[str] = Field(default=None, description="补充偏好说明")


class MemoryPreferenceUpsert(MemoryPreferenceBase):
    patient_id: str = Field(..., description="患者 ID")
    hospital_id: Optional[str] = Field(default=None, description="院区 ID")


class MemoryPreferenceRead(MemoryPreferenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    hospital_id: str
    created_at: datetime
    updated_at: datetime
