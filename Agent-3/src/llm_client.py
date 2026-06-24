"""统一的 LLM 客户端工厂 -- 所有模块通过此文件获取 OpenAI 客户端.

切换 LLM 提供商(DeepSeek ↔ SenseNova ↔ OpenAI)只需修改 .env 中的三个变量:
    LLM_API_KEY=...
    LLM_BASE_URL=...
    LLM_MODEL=...

用法:
    from src.llm_client import get_client, get_model

    client = get_client()
    model = get_model()
"""

from __future__ import annotations

import os
import time
import threading
from typing import Any

from openai import OpenAI

from src.protocol.errors import RetryableError, with_retry

# ── 熔断器 ────────────────────────────────────────────────────────

class CircuitBreaker:
    """简单熔断器:N 次失败 → 断路 → 超时后半开探测."""

    def __init__(self, fail_max: int = 5, reset_timeout: float = 60.0):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._fail_count = 0
        self._last_fail_time = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._fail_count >= self.fail_max:
                if time.monotonic() - self._last_fail_time >= self.reset_timeout:
                    return "half_open"
                return "open"
            return "closed"

    def success(self) -> None:
        with self._lock:
            self._fail_count = 0

    def failure(self) -> None:
        with self._lock:
            self._fail_count += 1
            self._last_fail_time = time.monotonic()

    def check(self) -> None:
        """调用前检查:断路时抛出 CircuitBreakerError."""
        if self.state == "open":
            raise CircuitBreakerError("LLM 服务熔断中,请稍后重试")


class CircuitBreakerError(Exception):
    """熔断器断开异常."""
    pass


_breaker = CircuitBreaker(fail_max=int(os.getenv("CB_FAIL_MAX", "5")),
                          reset_timeout=float(os.getenv("CB_RESET_TIMEOUT", "60")))


def get_breaker() -> CircuitBreaker:
    return _breaker


def call_llm_with_retry(client: OpenAI, **kwargs: Any) -> Any:
    """带指数退避重试 + 熔断保护的 LLM 调用."""
    _breaker.check()

    @with_retry(max_retries=3)
    def _call() -> Any:
        try:
            result = client.chat.completions.create(**kwargs)
            _breaker.success()
            return result
        except CircuitBreakerError:
            raise
        except Exception as e:
            error_str = str(e).lower()
            if any(kw in error_str for kw in (
                "timed", "timeout", "rate", "429", "503", "502",
                "connection", "server error", "overloaded",
            )):
                _breaker.failure()
                raise RetryableError(str(e))
            raise
    return _call()


def get_client() -> OpenAI:
    """返回 OpenAI 兼容客户端,配置从环境变量读取.

    Raises:
        SystemExit: 如果未配置 LLM_API_KEY.
    """
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        msg = (
            "未配置 LLM_API_KEY,请在 .env 中设置:\n"
            "   LLM_API_KEY=your-api-key\n"
            "   LLM_BASE_URL=your-base-url   (可选,默认 DeepSeek)\n"
            "   LLM_MODEL=your-model-name    (可选,默认 deepseek-v4-flash)"
        )
        raise RuntimeError(msg)

    return OpenAI(api_key=api_key, base_url=base_url)


def get_model() -> str:
    """返回当前模型名."""
    return os.getenv("LLM_MODEL", "deepseek-v4-flash")
