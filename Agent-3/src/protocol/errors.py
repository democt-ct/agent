from __future__ import annotations

import functools
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class AgentError(Exception):
    """Agent 系统基础异常"""

    def __init__(self, message: str, agent_name: str | None = None) -> None:
        self.agent_name = agent_name
        super().__init__(message)


class RetryableError(AgentError):
    """可重试的临时错误(API 超时,网络抖动等)"""

    def __init__(
        self,
        message: str,
        agent_name: str | None = None,
        retry_after: float = 1.0,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, agent_name)


class MaxRetriesExceeded(AgentError):
    """超过最大重试次数"""

    def __init__(
        self,
        message: str,
        agent_name: str | None = None,
        last_error: Exception | None = None,
    ) -> None:
        self.last_error = last_error
        super().__init__(message, agent_name)


class TimeoutError(AgentError):
    """Agent 执行超时"""

    def __init__(
        self,
        message: str,
        agent_name: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(message, agent_name)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    agent_name: str | None = None,
) -> Callable[[F], F]:
    """可重试装饰器:遇到 RetryableError 时指数退避重试.

    Args:
        max_retries: 最大重试次数(默认 3).
        base_delay: 首次重试等待秒数(默认 1.0).
        backoff_factor: 退避倍数(默认 2.0,即 1s → 2s → 4s).
        agent_name: Agent 名称(可选,用于错误信息).

    Returns:
        装饰后的函数.

    Raises:
        MaxRetriesExceeded: 超过最大重试次数后抛出.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            delay = base_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RetryableError as e:
                    last_exc = e
                    if attempt < max_retries:
                        wait = max(e.retry_after, delay)
                        time.sleep(wait)
                        delay *= backoff_factor
                except AgentError:
                    raise  # 非重试类 Agent 错误直接透传

            raise MaxRetriesExceeded(
                message=(
                    f"超过最大重试次数 {max_retries},"
                    f"最后一次错误: {last_exc}"
                ),
                agent_name=agent_name,
                last_error=last_exc,
            )

        return wrapper  # type: ignore[return-value]

    return decorator
