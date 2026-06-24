"""JWT Auth -- 签发 / 验证 / SessionContext / Refresh Token.

Access Token: 短期(默认 8h),用于 API 鉴权.
Refresh Token: 长期(默认 7d),用于无感续签,落库可撤销.

生产环境强制 JWT_SECRET 环境变量,dev 环境允许默认值.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import jwt

from src.tools.db import db_get_user, db_verify_password, get_db, _uid, _now

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production-32b")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "8"))
REFRESH_EXPIRY_DAYS = int(os.getenv("REFRESH_EXPIRY_DAYS", "7"))
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))

# 生产环境启动即校验
if os.getenv("APP_ENV", "dev") == "production":
    if JWT_SECRET == "dev-secret-change-in-production":
        raise RuntimeError("生产环境必须设置 JWT_SECRET 环境变量,不能使用默认值")


@dataclass
class SessionContext:
    """当前请求的会话上下文 -- 由 AuthMiddleware 注入.

    下游 Agent 和 Tool 通过此对象获取用户身份和权限.
    """

    user_id: str
    name: str
    department_id: str
    department_name: str
    manager_id: str | None
    role: str                      # employee / manager / hr / admin
    permissions: list[str] = field(default_factory=list)

    def is_self(self, user_id: str) -> bool:
        """检查是否操作自己的数据."""
        return self.user_id == user_id

    def has_role(self, *roles: str) -> bool:
        """检查是否拥有指定角色之一."""
        return self.role in roles

    def can_approve(self, user_id: str) -> bool:
        """检查是否可以审批指定用户(是直属上级或 HR)."""
        if self.role in ("hr", "admin"):
            return True
        # 查汇报链
        from src.tools.db import db_get_org_chain
        chain = db_get_org_chain(user_id)
        for node in chain[1:]:  # 跳过本人
            if node["user_id"] == self.user_id:
                return True
        return False


def create_token(user_id: str) -> tuple[str, dict]:
    """为用户签发 JWT(含 8h 过期时间).

    Returns:
        (token_string, payload_dict)
    """
    user = db_get_user(user_id)
    if user is None:
        raise ValueError(f"用户不存在: {user_id}")

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "sub": user_id,
        "name": user["name"],
        "department_id": user["department_id"],
        "department_name": user.get("department_name", ""),
        "manager_id": user.get("manager_id"),
        "role": user["role"],
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, payload


def verify_token(token: str) -> dict | None:
    """验证 JWT,返回 payload 或 None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_from_token(token: str) -> SessionContext | None:
    """从 JWT 解析并构造 SessionContext."""
    payload = verify_token(token)
    if payload is None:
        return None
    return SessionContext(
        user_id=payload["sub"],
        name=payload.get("name", ""),
        department_id=payload.get("department_id", ""),
        department_name=payload.get("department_name", ""),
        manager_id=payload.get("manager_id"),
        role=payload.get("role", "employee"),
    )


def login(user_id: str, password: str) -> str | None:
    """登录验证:校验密码 + 速率限制 → 返回 Access Token 或 None.

    失败 5 次后锁定 15 分钟.
    """
    if _is_locked_out(user_id):
        logger.warning("Login blocked (locked out): %s", user_id)
        return None

    if not db_verify_password(user_id, password):
        _record_login_attempt(user_id, success=False)
        return None

    _record_login_attempt(user_id, success=True)
    token, _ = create_token(user_id)
    return token


def create_refresh_token(user_id: str) -> str:
    """签发 Refresh Token,落库可撤销.

    Returns:
        refresh_token 字符串(随机 + sha256 哈希落库).
    """
    import secrets
    raw = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRY_DAYS)).isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO refresh_tokens (token_hash, user_id, expires_at, revoked, created_at)
               VALUES (?, ?, ?, 0, ?)""",
            (token_hash, user_id, expires_at, _now()),
        )
        conn.commit()

    return raw


def verify_refresh_token(raw_token: str) -> str | None:
    """验证 Refresh Token,返回 user_id 或 None."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with get_db() as conn:
        row = conn.execute(
            """SELECT user_id, expires_at, revoked FROM refresh_tokens
               WHERE token_hash = ?""",
            (token_hash,),
        ).fetchone()

    if row is None:
        return None
    if row["revoked"]:
        return None
    if row["expires_at"] < datetime.now(timezone.utc).isoformat():
        return None

    return row["user_id"]


def revoke_refresh_token(raw_token: str) -> bool:
    """撤销 Refresh Token(登出)."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with get_db() as conn:
        conn.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?",
            (token_hash,),
        )
        conn.commit()
    return True


def revoke_all_user_tokens(user_id: str) -> int:
    """撤销某用户所有 Refresh Token(改密码后强制登出)."""
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ? AND revoked = 0",
            (user_id,),
        )
        conn.commit()
        return cur.rowcount


# ── 登录速率限制(内存实现,重启清零) ──────────────────────────

_login_attempts: dict[str, list[datetime]] = {}

def _record_login_attempt(user_id: str, success: bool) -> None:
    """记录登录尝试时间."""
    if success:
        _login_attempts.pop(user_id, None)
        return
    now = datetime.now(timezone.utc)
    if user_id not in _login_attempts:
        _login_attempts[user_id] = []
    _login_attempts[user_id].append(now)
    # 只保留最近 N 分钟的记录
    cutoff = now - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    _login_attempts[user_id] = [t for t in _login_attempts[user_id] if t > cutoff]


def _is_locked_out(user_id: str) -> bool:
    """检查用户是否被登录锁定."""
    attempts = _login_attempts.get(user_id, [])
    if len(attempts) < LOGIN_MAX_ATTEMPTS:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    recent = [t for t in attempts if t > cutoff]
    return len(recent) >= LOGIN_MAX_ATTEMPTS
