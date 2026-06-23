from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MedicalRecordCreate(BaseModel):
    record_type: str = Field(..., description="病历类型，如 outpatient / inpatient / report")
    title: str = Field(..., description="病历标题")
    department: Optional[str] = Field(None, description="科室")
    doctor_name: Optional[str] = Field(None, description="医生")
    chief_complaint: Optional[str] = Field(None, description="主诉")
    present_illness: Optional[str] = Field(None, description="现病史")
    diagnosis: Optional[str] = Field(None, description="诊断信息")
    treatment_plan: Optional[str] = Field(None, description="治疗方案")
    medications: Optional[str] = Field(None, description="用药信息")
    notes: Optional[str] = Field(None, description="备注")
    record_date: Optional[datetime] = Field(None, description="病历日期")


class MedicalRecordUpdate(BaseModel):
    """病历更新——所有字段均为可选，只更新传入的非 None 字段"""
    record_type: Optional[str] = Field(None, description="病历类型")
    title: Optional[str] = Field(None, description="病历标题")
    department: Optional[str] = Field(None, description="科室")
    doctor_name: Optional[str] = Field(None, description="医生")
    chief_complaint: Optional[str] = Field(None, description="主诉")
    present_illness: Optional[str] = Field(None, description="现病史")
    diagnosis: Optional[str] = Field(None, description="诊断信息")
    treatment_plan: Optional[str] = Field(None, description="治疗方案")
    medications: Optional[str] = Field(None, description="用药信息")
    notes: Optional[str] = Field(None, description="备注")
    record_date: Optional[datetime] = Field(None, description="病历日期")


class MedicalRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    hospital_id: str
    record_type: str
    title: str
    department: Optional[str]
    doctor_name: Optional[str]
    chief_complaint: Optional[str]
    present_illness: Optional[str]
    diagnosis: Optional[str]
    treatment_plan: Optional[str]
    medications: Optional[str]
    notes: Optional[str]
    record_date: datetime
    created_at: datetime
    updated_at: datetime
