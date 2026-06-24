"""密码学工具 -- pbkdf2_hmac 密码哈希 + 常量时间比对.

使用标准库 hashlib.pbkdf2_hmac,迭代次数 600000(OWASP 2023 推荐).
格式: pbkdf2:sha256:<iterations>$<salt_b64>$<hash_b64>

Usage:
    from src.gateway.crypto import hash_password, verify_password
    hashed = hash_password("123456")
    assert verify_password("123456", hashed)
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

_ALGORITHM = "sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16
_HASH_BYTES = 32


def hash_password(password: str) -> str:
    """对密码进行 pbkdf2 哈希.

    Returns:
        格式: "pbkdf2:sha256:600000$<salt_b64>$<hash_b64>"
    """
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        _ALGORITHM,
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_HASH_BYTES,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(dk).decode("ascii")
    return f"pbkdf2:{_ALGORITHM}:{_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, stored: str) -> bool:
    """验证密码是否匹配存储的哈希值.

    兼容旧版明文密码:如果存储值不以 "pbkdf2:" 开头,则做明文比对.
    这是临时的向后兼容措施,应在下次登录时触发哈希迁移.
    """
    if not stored:
        return False

    # 向后兼容:明文密码(旧数据)
    if not stored.startswith("pbkdf2:"):
        # 常量时间比对(防时序攻击,即使旧密码是明文)
        return secrets.compare_digest(password, stored)

    # 解析 pbkdf2 格式: "pbkdf2:sha256:600000$salt_b64$hash_b64"
    try:
        parts = stored.split("$")
        if len(parts) != 3:
            return False
        header, salt_b64, hash_b64 = parts
        _, algo, iterations_str = header.split(":")
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected_hash = base64.b64decode(hash_b64)
    except (ValueError, IndexError):
        return False

    dk = hashlib.pbkdf2_hmac(
        algo,
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected_hash),
    )
    return secrets.compare_digest(dk, expected_hash)


def needs_rehash(stored: str) -> bool:
    """检查密码哈希是否需要升级(旧明文 或 迭代次数不足)."""
    if not stored or not stored.startswith("pbkdf2:"):
        return True
    try:
        header = stored.split("$")[0]
        current_iterations = int(header.split(":")[2])
        return current_iterations < _ITERATIONS
    except (ValueError, IndexError):
        return True
