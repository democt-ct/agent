import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.mcp.auth import issue_auth_token, verify_auth_token
from app.mcp.schemas import MCPToolCallResponse, MCPToolDefinition
from app.services.patient_service import get_patient, list_medical_records, list_visit_records


@dataclass
class RegisteredTool:
    definition: MCPToolDefinition
    handler: Callable[..., Any]


class ModularMCPServer:
    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = RegisteredTool(
            definition=MCPToolDefinition(
                name=name,
                description=description,
                input_schema=input_schema,
            ),
            handler=handler,
        )

    def list_tools(self) -> List[MCPToolDefinition]:
        return [tool.definition for tool in self._tools.values()]

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> MCPToolCallResponse:
        if tool_name not in self._tools:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到 MCP 工具: {tool_name}",
            )

        arguments = arguments or {}
        result = self._tools[tool_name].handler(**arguments)
        return MCPToolCallResponse(
            tool_name=tool_name,
            success=True,
            data=_serialize_value(result),
            message="ok",
        )



def normalize_optional_auth_token(auth_token: Optional[str]) -> Optional[str]:
    if auth_token is None:
        return None

    token = str(auth_token).strip()
    if not token:
        return None

    if token.lower() in {"string", "null", "none", "undefined", "nil"}:
        return None

    return token

@contextmanager
def session_scope() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if hasattr(value, "__table__"):
        mapper = sa_inspect(value.__class__)
        return {
            column.key: _serialize_value(getattr(value, column.key))
            for column in mapper.columns
        }
    return value

def _resolve_patient_context(
    db: Session,
    patient_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    hospital_id: Optional[str] = None,
):
    identity = None
    auth_token = normalize_optional_auth_token(auth_token)
    if auth_token:
        try:
            identity = verify_auth_token(db, auth_token)
        except HTTPException as exc:
            detail = str(getattr(exc, "detail", "") or "")
            if detail == "?? token ???" and patient_id:
                identity = None
            else:
                raise
        if identity is not None:
            if patient_id and patient_id != identity["patient_id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="token ??????? patient_id ???",
                )
            if hospital_id and hospital_id != identity["hospital_id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="token ??????? hospital_id ???",
                )
            patient_id = identity["patient_id"]
            hospital_id = identity["hospital_id"]

    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="??? patient_id ? auth_token",
        )

    patient = get_patient(db, patient_id)
    if hospital_id and patient.hospital_id != hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="??????? hospital_id",
        )
    return patient, identity


def tool_issue_identity_token(
    patient_id: str,
    hospital_id: Optional[str] = None,
    expires_in_minutes: int = 120,
):
    with session_scope() as db:
        patient = get_patient(db, patient_id)
        if hospital_id and hospital_id != patient.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hospital_id 与患者记录不匹配",
            )
        return issue_auth_token(
            patient_id=patient.id,
            hospital_id=patient.hospital_id,
            expires_in_minutes=expires_in_minutes,
        )


def tool_verify_identity(auth_token: str):
    auth_token = normalize_optional_auth_token(auth_token)
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供有效 auth_token",
        )
    with session_scope() as db:
        return verify_auth_token(db, auth_token)


def tool_get_medical_records(
    patient_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    hospital_id: Optional[str] = None,
    record_type: Optional[str] = None,
    limit: int = 20,
):
    with session_scope() as db:
        patient, identity = _resolve_patient_context(
            db,
            patient_id=patient_id,
            auth_token=auth_token,
            hospital_id=hospital_id,
        )
        records = list_medical_records(
            db,
            patient_id=patient.id,
            record_type=record_type,
            limit=limit,
        )
        return {
            "identity": identity,
            "patient": patient,
            "count": len(records),
            "medical_records": records,
        }


def tool_get_visit_records(
    patient_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    hospital_id: Optional[str] = None,
    visit_type: Optional[str] = None,
    limit: int = 20,
):
    with session_scope() as db:
        patient, identity = _resolve_patient_context(
            db,
            patient_id=patient_id,
            auth_token=auth_token,
            hospital_id=hospital_id,
        )
        records = list_visit_records(
            db,
            patient_id=patient.id,
            visit_type=visit_type,
            limit=limit,
        )
        return {
            "identity": identity,
            "patient": patient,
            "count": len(records),
            "visit_records": records,
        }


def tool_get_patient_profile(
    patient_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    hospital_id: Optional[str] = None,
    medical_record_limit: int = 10,
    visit_limit: int = 10,
):
    with session_scope() as db:
        patient, identity = _resolve_patient_context(
            db,
            patient_id=patient_id,
            auth_token=auth_token,
            hospital_id=hospital_id,
        )
        medical_records = list_medical_records(
            db,
            patient_id=patient.id,
            limit=medical_record_limit,
        )
        visit_records = list_visit_records(
            db,
            patient_id=patient.id,
            limit=visit_limit,
        )
        return {
            "identity": identity,
            "patient": patient,
            "medical_records": medical_records,
            "visit_records": visit_records,
        }


mcp_server = ModularMCPServer()
mcp_server.register_tool(
    name="issue_identity_token",
    description="为指定患者签发一个测试认证 token，便于后续调用 verify_identity 和隐私查询工具。",
    input_schema={
        "type": "object",
        "properties": {
            "patient_id": {"type": "string"},
            "hospital_id": {"type": "string"},
            "expires_in_minutes": {"type": "integer", "default": 120},
        },
        "required": ["patient_id"],
    },
    handler=tool_issue_identity_token,
)
mcp_server.register_tool(
    name="verify_identity",
    description="校验患者认证 token 是否有效，并返回认证上下文。",
    input_schema={
        "type": "object",
        "properties": {
            "auth_token": {"type": "string"},
        },
        "required": ["auth_token"],
    },
    handler=tool_verify_identity,
)
mcp_server.register_tool(
    name="get_medical_records",
    description="查询患者病历记录，可直接传 patient_id，或传 auth_token 进行受控查询。",
    input_schema={
        "type": "object",
        "properties": {
            "patient_id": {"type": "string"},
            "auth_token": {"type": "string"},
            "hospital_id": {"type": "string"},
            "record_type": {"type": "string"},
            "limit": {"type": "integer", "default": 20},
        },
    },
    handler=tool_get_medical_records,
)
mcp_server.register_tool(
    name="get_visit_records",
    description="查询患者就诊记录，可直接传 patient_id，或传 auth_token 进行受控查询。",
    input_schema={
        "type": "object",
        "properties": {
            "patient_id": {"type": "string"},
            "auth_token": {"type": "string"},
            "hospital_id": {"type": "string"},
            "visit_type": {"type": "string"},
            "limit": {"type": "integer", "default": 20},
        },
    },
    handler=tool_get_visit_records,
)
mcp_server.register_tool(
    name="get_patient_profile",
    description="一次性聚合患者身份、病历和就诊记录，适合作为 Agent 的统一入口工具。",
    input_schema={
        "type": "object",
        "properties": {
            "patient_id": {"type": "string"},
            "auth_token": {"type": "string"},
            "hospital_id": {"type": "string"},
            "medical_record_limit": {"type": "integer", "default": 10},
            "visit_limit": {"type": "integer", "default": 10},
        },
    },
    handler=tool_get_patient_profile,
)
