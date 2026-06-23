from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    hospital_id: str = Field(..., description="机构ID/院区ID")
    patient_code: str = Field(..., description="院内患者编号")
    full_name: str = Field(..., description="患者姓名")
    gender: Optional[str] = Field(None, description="性别")
    birth_date: Optional[date] = Field(None, description="出生日期")
    phone: Optional[str] = Field(None, description="手机号")
    id_number: Optional[str] = Field(None, description="身份证号，仅用于入库时哈希")
    address: Optional[str] = Field(None, description="住址")
    emergency_contact_name: Optional[str] = Field(None, description="紧急联系人")
    emergency_contact_phone: Optional[str] = Field(None, description="紧急联系人电话")
    blood_type: Optional[str] = Field(None, description="血型")
    allergy_history: Optional[str] = Field(None, description="过敏史")
    family_history: Optional[str] = Field(None, description="家族史")
    notes: Optional[str] = Field(None, description="其他备注")


class PatientUpdate(BaseModel):
    """患者主档更新——所有字段均为可选，只更新传入的非 None 字段"""
    hospital_id: Optional[str] = Field(None, description="机构ID/院区ID")
    patient_code: Optional[str] = Field(None, description="院内患者编号")
    full_name: Optional[str] = Field(None, description="患者姓名")
    gender: Optional[str] = Field(None, description="性别")
    birth_date: Optional[date] = Field(None, description="出生日期")
    phone: Optional[str] = Field(None, description="手机号")
    id_number: Optional[str] = Field(None, description="身份证号，修改后重新哈希")
    address: Optional[str] = Field(None, description="住址")
    emergency_contact_name: Optional[str] = Field(None, description="紧急联系人")
    emergency_contact_phone: Optional[str] = Field(None, description="紧急联系人电话")
    blood_type: Optional[str] = Field(None, description="血型")
    allergy_history: Optional[str] = Field(None, description="过敏史")
    family_history: Optional[str] = Field(None, description="家族史")
    notes: Optional[str] = Field(None, description="其他备注")


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hospital_id: str
    patient_code: str
    full_name: str
    gender: Optional[str]
    birth_date: Optional[date]
    phone: Optional[str]
    id_number_last4: Optional[str]
    address: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    blood_type: Optional[str]
    allergy_history: Optional[str]
    family_history: Optional[str]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
