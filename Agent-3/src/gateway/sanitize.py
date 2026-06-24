"""输入净化 -- 所有用户输入的校验和清洗.

对外暴露两个函数:
    sanitize_str(s, max_len) → 清洗后的字符串
    validate_id(id_str, pattern) → 是否合法 ID

内部规则:
    - 长度限制(默认各类型上限)
    - 控制字符剔除(\x00-\x1f 除 \t\n\r)
    - Unicode 正规化(NFKC 防同形字攻击)
"""

from __future__ import annotations

import re
import unicodedata

# ── 长度限制 ──────────────────────────────────────────────────────

MAX_USER_ID = 50
MAX_NAME = 100
MAX_PASSWORD = 128
MAX_QUERY = 2000
MAX_DESCRIPTION = 2000
MAX_REASON = 500
MAX_COMMENT = 500
MAX_TICKET_ID = 20
MAX_ISSUE_TYPE = 50

# ── 正则校验 ──────────────────────────────────────────────────────

RE_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
RE_TICKET_ID = re.compile(r"^TK\d{3,6}$")
RE_SAFE_TEXT = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]*$")  # 允许 \t \n \r


def sanitize_str(s: str, max_len: int = 2000) -> str:
    """清洗用户输入字符串.

    - 去除首尾空白
    - Unicode NFKC 正规化(防同形字攻击,如 'е' → 'e')
    - 去除控制字符(保留 \t \n \r)
    - 截断到 max_len
    """
    if not isinstance(s, str):
        return ""

    s = s.strip()
    # NFKC 正规化 -- 同形字攻击防护
    s = unicodedata.normalize("NFKC", s)
    # 去除控制字符
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    # 截断
    if len(s) > max_len:
        s = s[:max_len]

    return s


def validate_user_id(uid: str) -> bool:
    """校验员工 ID 格式: 字母/数字/下划线/连字符,1-50 字符."""
    return bool(RE_USER_ID.match(uid))


def validate_ticket_id(tid: str) -> bool:
    """校验工单 ID 格式: TK 后跟 3-6 位数字."""
    return bool(RE_TICKET_ID.match(tid))


def sanitize_all_kwargs(kwargs: dict, field_limits: dict[str, int] | None = None) -> dict:
    """批量清洗工具函数的所有字符串参数.

    Args:
        kwargs: 原始参数字典
        field_limits: {字段名: 最大长度} 覆盖,未指定的字段用默认 2000

    Returns:
        清洗后的参数字典.
    """
    limits = field_limits or {}
    result = {}
    for key, val in kwargs.items():
        if isinstance(val, str):
            limit = limits.get(key, MAX_DESCRIPTION)
            result[key] = sanitize_str(val, limit)
        else:
            result[key] = val
    return result
