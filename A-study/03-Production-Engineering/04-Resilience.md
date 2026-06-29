# 04 - Resilience Patterns — 容错模式

> 学习目标：掌握四种核心容错模式的组合使用，让 Agent 在故障中优雅降级而非崩溃

---

## 1. 为什么 try/except 不够

```python
# ❌ 天真的"容错"
try:
    result = flight_search_api.search("北京", "成都")
except Exception as e:
    logger.error(f"搜索失败: {e}")
    return None  # ← 然后呢？用户看到空白结果？
```

`try/except` 只是捕获，没有回答：
- 要不要再试一次？（Retry）
- 试几次？间隔多久？（Backoff）
- 有没有备用方案？（Fallback）
- 如果这个 API 持续失败，要不要跳过它？（Circuit Breaker）
- 最长等多久？（Timeout）

> **核心认知**：容错 = Retry + Timeout + Circuit Breaker + Fallback 四者组合。缺一个都不叫"韧性"。

---

## 2. 模式一：Retry（重试）+ Backoff（退避）

```python
import time
import random
from functools import wraps
from typing import Type, Tuple

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    指数退避重试装饰器
    
    重试间隔：base_delay × backoff_factor^attempt + jitter
    示例：1s → 2s → 4s → 8s ...（max 60s）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        break  # 重试耗尽
                    
                    # 计算延迟
                    delay = min(
                        base_delay * (backoff_factor ** attempt),
                        max_delay
                    )
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    print(f"⚠️ {func.__name__} 失败 (尝试 {attempt+1}/{max_retries+1})，"
                          f"{delay:.1f}s 后重试: {e}")
                    time.sleep(delay)
            
            # 所有重试都失败
            raise MaxRetriesExceededError(
                f"{func.__name__} 在 {max_retries} 次重试后仍失败"
            ) from last_exception
        
        return wrapper
    return decorator


class MaxRetriesExceededError(Exception):
    pass


# 使用示例
@retry_with_backoff(max_retries=3, base_delay=1.0,
                    retryable_exceptions=(ConnectionError, TimeoutError))
def search_flights(departure, destination, date):
    """调用外部航班搜索 API（可能不稳定）"""
    response = requests.get(
        "https://api.flights.com/search",
        params={"from": departure, "to": destination, "date": date},
        timeout=10
    )
    if response.status_code == 429:  # Rate limited
        raise ConnectionError("被限流")
    return response.json()
```

---

## 3. 模式二：Timeout（超时）

每个外部调用必须有超时。没有超时的调用 = 潜在的无限等待。

```python
import asyncio
import signal
from contextlib import contextmanager

# 同步版本
@contextmanager
def timeout(seconds: int):
    """为同步代码添加超时（Unix only）"""
    def handler(signum, frame):
        raise TimeoutError(f"操作超时 ({seconds}s)")
    
    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


# 异步版本（推荐，跨平台）
async def call_with_timeout(coro, seconds: int):
    """为异步调用添加超时"""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"操作超时 ({seconds}s)")


# 完整的带超时的工具调用
class TimedToolExecutor:
    DEFAULT_TIMEOUTS = {
        "web_search":      15,   # 搜索：15s
        "flight_search":   10,   # 航班查询：10s
        "hotel_search":    10,   # 酒店查询：10s
        "book_flight":     30,   # 预订：30s（涉及支付）
        "generate_report": 120,  # 报告生成：2min
    }
    
    async def execute(self, tool_name: str, params: dict) -> dict:
        timeout_seconds = self.DEFAULT_TIMEOUTS.get(tool_name, 30)
        
        try:
            result = await call_with_timeout(
                self._do_execute(tool_name, params),
                timeout_seconds
            )
            return {"status": "success", "data": result}
        
        except TimeoutError:
            return {
                "status": "timeout",
                "message": f"{tool_name} 超时 ({timeout_seconds}s)",
                "fallback_action": self._get_fallback(tool_name)
            }
```

---

## 4. 模式三：Circuit Breaker（熔断器）

当某个外部服务持续失败时，暂时跳过它——避免雪崩效应。

```
Circuit Breaker 三种状态：

  ┌──────────┐     连续失败N次     ┌──────────┐
  │  CLOSED  │ ─────────────────→  │  OPEN    │
  │  正常工作 │                      │  拒绝调用  │
  └──────────┘                      └─────┬────┘
       ↑                                  │
       │       等待 timeout 秒后           │
       │   ┌──────────────────────────────┘
       │   │
       │   ▼
  ┌──────────┐
  │ HALF-OPEN│  放行一个请求测试
  │  试探中   │
  └────┬─────┘
       │
  成功 ↓  失败 → 回到 OPEN
  CLOSED
```

```python
from enum import Enum
from datetime import datetime

class CircuitState(Enum):
    CLOSED = "closed"          # 正常
    OPEN = "open"              # 熔断
    HALF_OPEN = "half_open"    # 试探

class CircuitBreaker:
    def __init__(self, name: str, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 half_open_max_requests: int = 1):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout     # 熔断后多久试探
        self.half_open_max_requests = half_open_max_requests
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_requests = 0
    
    def call(self, func, *args, **kwargs):
        """调用前先检查断路器状态"""
        if self.state == CircuitState.OPEN:
            if self._should_try_half_open():
                self.state = CircuitState.HALF_OPEN
                self.half_open_requests = 0
            else:
                raise CircuitBreakerOpenError(
                    f"[{self.name}] 熔断中，拒绝调用 "
                    f"({self.failure_count}次连续失败)"
                )
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_requests >= self.half_open_max_requests:
                raise CircuitBreakerOpenError(
                    f"[{self.name}] 试探中，已达最大请求数"
                )
            self.half_open_requests += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            # 试探成功 → 恢复正常
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        # CLOSED 状态的成功不用处理
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if (self.state == CircuitState.CLOSED 
            and self.failure_count >= self.failure_threshold):
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN  # 试探失败，继续熔断
    
    def _should_try_half_open(self) -> bool:
        if self.last_failure_time is None:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout


class CircuitBreakerOpenError(Exception):
    pass


# 使用示例
flight_search_cb = CircuitBreaker("flight_search", 
    failure_threshold=3, recovery_timeout=30)

try:
    flights = flight_search_cb.call(search_flights, "北京", "成都", "2026-07-15")
except CircuitBreakerOpenError:
    flights = fallback_flight_cache("北京", "成都", "2026-07-15")
```

---

## 5. 模式四：Fallback（降级）

以上三种都失败了，必须有兜底。

```python
class ResilientToolExecutor:
    """组合四种容错模式的工具执行器"""
    
    def __init__(self):
        self.breakers = {}  # 每个工具一个断路器
        self.fallbacks = {
            "flight_search": self._fallback_flight_search,
            "hotel_search":  self._fallback_hotel_search,
            "weather_api":   self._fallback_weather,
        }
    
    async def execute(self, tool_name: str, params: dict) -> dict:
        # 1. 获取或创建断路器
        if tool_name not in self.breakers:
            self.breakers[tool_name] = CircuitBreaker(tool_name)
        breaker = self.breakers[tool_name]
        
        try:
            # 2. 通过断路器调用（内含重试 + 超时）
            result = breaker.call(
                self._timed_execute, tool_name, params
            )
            return {"status": "success", "data": result}
        
        except CircuitBreakerOpenError:
            # 3. 断路器打开 → 直接降级
            return await self._fallback(tool_name, params, "熔断")
        
        except MaxRetriesExceededError:
            # 4. 重试耗尽 → 降级
            return await self._fallback(tool_name, params, "重试耗尽")
        
        except TimeoutError:
            # 5. 超时 → 降级
            return await self._fallback(tool_name, params, "超时")
    
    @retry_with_backoff(max_retries=2, retryable_exceptions=(ConnectionError,))
    async def _timed_execute(self, tool_name, params):
        """带超时的实际执行"""
        timeout_sec = TimedToolExecutor.DEFAULT_TIMEOUTS.get(tool_name, 30)
        return await call_with_timeout(
            actual_tool_call(tool_name, params),
            timeout_sec
        )
    
    async def _fallback(self, tool_name: str, params: dict, 
                        reason: str) -> dict:
        fallback_fn = self.fallbacks.get(tool_name)
        if fallback_fn:
            result = await fallback_fn(params)
            return {
                "status": "degraded",
                "reason": reason,
                "data": result,
                "warning": f"{tool_name} 不可用({reason})，使用了备用数据"
            }
        
        return {"status": "failed", "reason": reason, 
                "message": f"{tool_name} 不可用且无降级方案"}
    
    async def _fallback_flight_search(self, params):
        """降级：用缓存 + 网页搜索代替专用 API"""
        # 尝试缓存
        cache_key = f"flight:{params['departure']}:{params['destination']}"
        cached = redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # 缓存也没有，用通用网页搜索
        results = await web_search(
            f"{params['departure']} 到 {params['destination']} 机票"
        )
        return {"source": "web_search_fallback", "results": results}
```

---

## 6. 四种模式组合决策树

```
调用外部工具/API
    │
    ▼
┌── 断路器是否 OPEN？ ──→ 是 ──→ Fallback
│   否
│   ▼
│  执行（带 Timeout）
│   │
│   ├── 成功 ──→ 返回结果
│   │
│   └── 失败
│       │
│       ├── 可重试的错误？
│       │   是 → Retry（指数退避）
│       │    │
│       │    ├── 重试成功 → 返回结果，重置断路器
│       │    └── 重试耗尽 → 记录失败，判断是否触发熔断
│       │
│       └── Fallback
```

---

## 7. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 无差别重试所有错误 | 参数错误重试也白费 | 只重试可恢复错误（网络、超时、限流） |
| 重试不设退避 | 打挂自己的服务 | 指数退避 + jitter |
| 熔断阈值设 1 | 一次失败就熔断，服务永远不可用 | 阈值 ≥ 3 |
| 没有 Fallback | 所有容错都没了，还是报错 | 每个关键工具准备降级方案 |
| 熔断状态不恢复 | 服务恢复了但熔断器永久 OPEN | recovery_timeout + HALF_OPEN |

---

## 实践任务

**任务1**：实现一个 Reaction 装饰器，支持指数退避和 jitter。用猴子补丁的方式测试重试3次后抛出的异常是否正确。

**任务2**：为你的旅游 Agent 的 5 个外部依赖（航班搜索、酒店搜索、天气API、景点搜索、预订API）设计容错矩阵：

```
工具          | 超时 | 重试次数 | 熔断阈值 | 降级方案
flight_search | 10s  | 3       | 5       | 网页搜索代替
weather_api   | 5s   | 2       | 3       | 使用历史数据
...
```

**任务3**：实现 CircuitBreaker，测试场景：连续失败5次 → 断路器 OPEN → 等待30秒 → HALF_OPEN → 第6次成功 → CLOSED。

---

→ [05-Cache-Strategy.md](./05-Cache-Strategy.md)
