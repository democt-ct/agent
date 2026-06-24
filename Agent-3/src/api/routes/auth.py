"""Auth API -- POST /api/auth/login."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.gateway.auth import create_token, login

router = APIRouter(tags=["auth"])


@router.get("/me/leaves")
async def my_leaves_endpoint(request: Request):
    """获取当前用户的请假记录列表."""
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, leave_type, start_date, end_date, total_days, reason, status, created_at "
            "FROM leave_records WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (session.user_id,),
        ).fetchall()
    return {"leaves": [dict(r) for r in rows]}


@router.get("/me")
async def me_endpoint(request: Request):
    """获取当前登录用户的完整信息(需 Bearer token)."""
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import db_get_user, db_get_leave_balance, db_get_org_chain

    user = db_get_user(session.user_id)
    balance = db_get_leave_balance(session.user_id)
    chain = db_get_org_chain(session.user_id)
    manager_name = chain[1]["name"] if chain and len(chain) > 1 else None

    # 统一申请记录(请假 + IT工单 + 报销)
    from src.tools.db import db_get_my_applications
    all_apps = db_get_my_applications(session.user_id, limit=50)

    # 格式化统一申请记录
    status_map = {
        "pending": "待审批", "approved": "已通过", "rejected": "已驳回",
        "draft": "草稿", "cancelled": "已取消", "completed": "已完成",
        "待处理": "待处理", "处理中": "处理中", "已完成": "已完成",
        "reimbursed": "已报销",
    }
    applications = []
    for r in all_apps:
        raw_status = r.get("status", "")
        applications.append({
            "app_type": r.get("app_type"),
            "app_type_label": r.get("app_type_label"),
            "id": r.get("id"),
            "subtype": r.get("subtype"),
            "start_date": r.get("start_date"),
            "end_date": r.get("end_date"),
            "amount": r.get("amount_val"),
            "description": r.get("description"),
            "status": raw_status,
            "status_label": status_map.get(raw_status, raw_status),
            "created_at": r.get("created_at"),
        })

    return {
        "user_id": session.user_id,
        "name": session.name,
        "department": session.department_name,
        "department_id": user.get("department_id") if user else "",
        "role": session.role,
        "balance": balance or {},
        "tenure_years": user.get("tenure_years") if user else 0,
        "hire_date": user.get("hire_date") if user else "",
        "status": user.get("status") if user else "active",
        "manager_name": manager_name,
        "leaves": [a for a in applications if a["app_type"] == "leave"],
        "applications": applications,
        "org_chain": [{"user_id": n["user_id"], "name": n["name"], "role": n["role"]} for n in chain] if chain else [],
    }


class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50, description="员工ID")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, description="Refresh Token")


@router.post("/auth/refresh")
async def refresh_token_endpoint(req: RefreshRequest, request: Request):
    """用 Refresh Token 换取新的 Access Token."""
    from src.gateway.auth import verify_refresh_token, create_token

    user_id = verify_refresh_token(req.refresh_token)
    if user_id is None:
        return JSONResponse(status_code=401, content={"error": "无效或已过期的 refresh token"})

    token, payload = create_token(user_id)
    from src.gateway.auth import JWT_EXPIRY_HOURS
    return {
        "token": token,
        "token_type": "bearer",
        "user": {
            "user_id": payload["sub"],
            "name": payload.get("name"),
            "department": payload.get("department_name"),
            "role": payload.get("role"),
        },
        "expires_in": JWT_EXPIRY_HOURS * 3600,
    }


@router.post("/auth/logout")
async def logout_endpoint(req: RefreshRequest, request: Request):
    """登出 -- 撤销 Refresh Token."""
    from src.gateway.auth import revoke_refresh_token

    ok = revoke_refresh_token(req.refresh_token)
    return {"success": ok}


@router.post("/auth/login")
async def login_endpoint(req: LoginRequest, request: Request):
    """用户登录,返回 JWT + Refresh Token."""
    from src.gateway.sanitize import sanitize_str, MAX_USER_ID, MAX_PASSWORD

    uid = sanitize_str(req.user_id, MAX_USER_ID)
    pwd = sanitize_str(req.password, MAX_PASSWORD)

    if not uid or not pwd:
        return JSONResponse(status_code=400, content={"error": "用户名和密码不能为空"})

    token = login(uid, pwd)
    if token is None:
        return JSONResponse(
            status_code=401,
            content={"error": "用户名或密码错误"},
        )

    # 签发 Refresh Token
    from src.gateway.auth import create_refresh_token, verify_token, JWT_EXPIRY_HOURS
    refresh_token = create_refresh_token(uid)
    payload = verify_token(token)

    return {
        "token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "user_id": payload["sub"],
            "name": payload.get("name"),
            "department": payload.get("department_name"),
            "role": payload.get("role"),
        },
        "expires_in": JWT_EXPIRY_HOURS * 3600,
    }
