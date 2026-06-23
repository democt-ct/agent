from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordRead, MedicalRecordUpdate
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.schemas.profile import PatientProfileRead
from app.schemas.visit_record import VisitRecordCreate, VisitRecordRead, VisitRecordUpdate
from app.services.patient_service import (
    create_medical_record,
    create_patient,
    create_visit_record,
    delete_medical_record,
    delete_patient,
    delete_visit_record,
    get_medical_record,
    get_patient,
    get_visit_record,
    list_medical_records,
    list_patients,
    list_visit_records,
    update_medical_record,
    update_patient,
    update_visit_record,
)


router = APIRouter(prefix="/api/v1", tags=["patient-data"])


# ── 病历 CRUD ──


@router.post(
    "/patients",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建患者",
    description="新增一条患者主档信息，用于后续病历、就诊记录和智能问答测试。",
)
def create_patient_endpoint(payload: PatientCreate, db: Session = Depends(get_db)):
    return create_patient(db, payload)


@router.get(
    "/patients",
    response_model=List[PatientRead],
    summary="查询患者列表",
    description="按院区、手机号或姓名模糊搜索患者列表。",
)
def list_patients_endpoint(
    hospital_id: Optional[str] = Query(None, description="机构ID/院区ID"),
    patient_code: Optional[str] = Query(None, description="院内患者编号"),
    phone: Optional[str] = Query(None, description="手机号（模糊匹配）"),
    name: Optional[str] = Query(None, description="姓名（模糊匹配）"),
    db: Session = Depends(get_db),
):
    return list_patients(db, hospital_id, patient_code, phone, name)


@router.get(
    "/patients/{patient_id}",
    response_model=PatientRead,
    summary="读取患者主档",
    description="根据患者 ID 读取单个患者的基础档案信息。",
)
def get_patient_endpoint(patient_id: str, db: Session = Depends(get_db)):
    return get_patient(db, patient_id)


@router.delete(
    "/patients/{patient_id}",
    status_code=status.HTTP_200_OK,
    summary="删除患者",
    description="删除患者主档以及其关联的病历、就诊记录等测试数据。",
)
def delete_patient_endpoint(patient_id: str, db: Session = Depends(get_db)):
    deleted = delete_patient(db, patient_id)
    return {
        "message": "患者及其相关病历、就诊记录已删除",
        "patient_id": deleted.id,
        "hospital_id": deleted.hospital_id,
        "patient_code": deleted.patient_code,
    }


@router.put(
    "/patients/{patient_id}",
    response_model=PatientRead,
    summary="修改患者主档",
    description="部分更新患者主档信息，只更新传入的非空字段。",
)
def update_patient_endpoint(
    patient_id: str,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
):
    return update_patient(db, patient_id, payload)


@router.post(
    "/patients/{patient_id}/medical-records",
    response_model=MedicalRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="新增病历",
    description="为指定患者新增一条病历记录，供画像聚合和问答检索使用。",
)
def create_medical_record_endpoint(
    patient_id: str,
    payload: MedicalRecordCreate,
    db: Session = Depends(get_db),
):
    return create_medical_record(db, patient_id, payload)


@router.get(
    "/patients/{patient_id}/medical-records",
    response_model=List[MedicalRecordRead],
    summary="读取病历列表",
    description="查询指定患者的病历记录，可按病历类型筛选并限制返回数量。",
)
def list_medical_records_endpoint(
    patient_id: str,
    record_type: Optional[str] = Query(None, description="病历类型"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db),
):
    return list_medical_records(db, patient_id, record_type, limit)


@router.get(
    "/patients/{patient_id}/medical-records/{record_id}",
    response_model=MedicalRecordRead,
    summary="读取单条病历",
    description="根据病历 ID 读取某位患者的单条病历详情。",
)
def get_medical_record_endpoint(
    patient_id: str,
    record_id: str,
    db: Session = Depends(get_db),
):
    return get_medical_record(db, patient_id, record_id)


@router.put(
    "/patients/{patient_id}/medical-records/{record_id}",
    response_model=MedicalRecordRead,
    summary="修改病历",
    description="部分更新一条病历记录，只更新传入的非空字段。",
)
def update_medical_record_endpoint(
    patient_id: str,
    record_id: str,
    payload: MedicalRecordUpdate,
    db: Session = Depends(get_db),
):
    return update_medical_record(db, patient_id, record_id, payload)


@router.delete(
    "/patients/{patient_id}/medical-records/{record_id}",
    status_code=status.HTTP_200_OK,
    summary="删除病历",
    description="删除指定患者的一条病历记录。",
)
def delete_medical_record_endpoint(
    patient_id: str,
    record_id: str,
    db: Session = Depends(get_db),
):
    deleted = delete_medical_record(db, patient_id, record_id)
    return {
        "message": "病历已删除",
        "record_id": deleted.id,
    }


@router.post(
    "/patients/{patient_id}/visits",
    response_model=VisitRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="新增就诊记录",
    description="为指定患者新增一条就诊记录，供复诊分析和长期记忆抽取使用。",
)
def create_visit_record_endpoint(
    patient_id: str,
    payload: VisitRecordCreate,
    db: Session = Depends(get_db),
):
    return create_visit_record(db, patient_id, payload)


@router.get(
    "/patients/{patient_id}/visits",
    response_model=List[VisitRecordRead],
    summary="读取就诊列表",
    description="查询指定患者的就诊记录，可按就诊类型筛选并限制返回数量。",
)
def list_visit_records_endpoint(
    patient_id: str,
    visit_type: Optional[str] = Query(None, description="就诊类型"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db),
):
    return list_visit_records(db, patient_id, visit_type, limit)


@router.get(
    "/patients/{patient_id}/visits/{visit_id}",
    response_model=VisitRecordRead,
    summary="读取单条就诊记录",
    description="根据就诊 ID 读取某位患者的单条就诊记录详情。",
)
def get_visit_record_endpoint(
    patient_id: str,
    visit_id: str,
    db: Session = Depends(get_db),
):
    return get_visit_record(db, patient_id, visit_id)


@router.put(
    "/patients/{patient_id}/visits/{visit_id}",
    response_model=VisitRecordRead,
    summary="修改就诊记录",
    description="部分更新一条就诊记录，只更新传入的非空字段。",
)
def update_visit_record_endpoint(
    patient_id: str,
    visit_id: str,
    payload: VisitRecordUpdate,
    db: Session = Depends(get_db),
):
    return update_visit_record(db, patient_id, visit_id, payload)


@router.delete(
    "/patients/{patient_id}/visits/{visit_id}",
    status_code=status.HTTP_200_OK,
    summary="删除就诊记录",
    description="删除指定患者的一条就诊记录。",
)
def delete_visit_record_endpoint(
    patient_id: str,
    visit_id: str,
    db: Session = Depends(get_db),
):
    deleted = delete_visit_record(db, patient_id, visit_id)
    return {
        "message": "就诊记录已删除",
        "visit_id": deleted.id,
    }


@router.get(
    "/memory/profile",
    response_model=PatientProfileRead,
    summary="读取聚合画像",
    description="聚合返回患者主档、病历列表和就诊记录，用于调试画像与问答上下文。",
)
def get_memory_profile(
    patient_id: str = Query(..., description="患者主键ID"),
    medical_record_limit: int = Query(10, ge=1, le=100, description="纳入聚合的病历数量"),
    visit_limit: int = Query(10, ge=1, le=100, description="纳入聚合的就诊记录数量"),
    db: Session = Depends(get_db),
):
    patient = get_patient(db, patient_id)
    medical_records = list_medical_records(db, patient_id, limit=medical_record_limit)
    visit_records = list_visit_records(db, patient_id, limit=visit_limit)
    return {
        "patient": patient,
        "medical_records": medical_records,
        "visit_records": visit_records,
    }
