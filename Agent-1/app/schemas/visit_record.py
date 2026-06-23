from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class VisitRecordCreate(BaseModel):
    visit_type: str = Field(..., description="就诊类型，如 outpatient / emergency / follow_up")
    department: str = Field(..., description="就诊科室")
    doctor_name: Optional[str] = Field(None, description="医生")
    campus: Optional[str] = Field(None, description="院区")
    chief_complaint: Optional[str] = Field(None, description="本次就诊主诉")
    visit_status: Optional[str] = Field(None, description="就诊状态")
    visit_summary: Optional[str] = Field(None, description="就诊摘要")
    follow_up_plan: Optional[str] = Field(None, description="复诊计划")
    visit_date: Optional[datetime] = Field(None, description="就诊时间")


class VisitRecordUpdate(BaseModel):
    """就诊记录更新——所有字段均为可选，只更新传入的非 None 字段"""
    visit_type: Optional[str] = Field(None, description="就诊类型")
    department: Optional[str] = Field(None, description="就诊科室")
    doctor_name: Optional[str] = Field(None, description="医生")
    campus: Optional[str] = Field(None, description="院区")
    chief_complaint: Optional[str] = Field(None, description="本次就诊主诉")
    visit_status: Optional[str] = Field(None, description="就诊状态")
    visit_summary: Optional[str] = Field(None, description="就诊摘要")
    follow_up_plan: Optional[str] = Field(None, description="复诊计划")
    visit_date: Optional[datetime] = Field(None, description="就诊时间")


class VisitRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    hospital_id: str
    visit_type: str
    department: str
    doctor_name: Optional[str]
    campus: Optional[str]
    chief_complaint: Optional[str]
    visit_status: Optional[str]
    visit_summary: Optional[str]
    follow_up_plan: Optional[str]
    visit_date: datetime
    created_at: datetime
    updated_at: datetime
