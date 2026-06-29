# 05 - Cache Strategy — 缓存策略

> 学习目标：理解 Tool 调用为什么需要缓存，掌握 Redis 缓存的设计和失效策略

---

## 1. 为什么 Tool 不能一直调用

```python
# 场景：用户问了3次"成都7月天气怎么样"

# 无缓存：
#  第1次 → weather_api.call("成都", "2026-07") → 800ms → 扣费
#  第2次 → weather_api.call("成都", "2026-07") → 800ms → 扣费
#  第3次 → weather_api.call("成都", "2026-07") → 800ms → 扣费
#  总计：2.4s 延迟，3 次 API 费用

# 有缓存：
#  第1次 → weather_api.call("成都", "2026-07") → 800ms → 写入 Redis
#  第2次 → Redis 命中 → 5ms
#  第3次 → Redis 命中 → 5ms
#  总计：810ms 延迟，1 次 API 费用
```

> **核心认知**：Tool 调用 = 延迟 + 费用。缓存让"问过的问题"不用再花钱。

---

## 2. 缓存什么

不是所有 Tool 结果都适合缓存。

```
适合缓存 ✅：
  - 天气查询（短时间内不变）
  - 景点介绍（静态信息）
  - 航班价格查询（至少缓存几分钟）
  - 语义搜索结果（相同query的结果可复用）

不适合缓存 ❌：
  - 实时库存（随时变）
  - 用户个人信息
  - 支付/预订操作
  - 每次结果必须不同的操作
```

---

## 3. Redis 缓存层实现

```python
import json
import hashlib
import redis
from functools import wraps
from typing import Optional, Callable

class ToolCache:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "cache:tool:"
        
        # 每种 Tool 的默认 TTL
        self.default_ttls = {
            "weather_api":    1800,   # 天气：30分钟
            "flight_search":   300,   # 航班价格：5分钟
            "hotel_search":    300,   # 酒店价格：5分钟
            "attraction_info": 3600,  # 景点信息：1小时
            "web_search":      600,   # 搜索结果：10分钟
        }
    
    def _make_key(self, tool_name: str, params: dict) -> str:
        """生成缓存 Key"""
        # 参数排序 + hash → 确保相同参数命中相同缓存
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
        return f"{self.prefix}{tool_name}:{params_hash}"
    
    def get(self, tool_name: str, params: dict) -> Optional[dict]:
        """尝试读取缓存"""
        key = self._make_key(tool_name, params)
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    def set(self, tool_name: str, params: dict, 
            result: dict, ttl: int = None):
        """写入缓存"""
        key = self._make_key(tool_name, params)
        ttl = ttl or self.default_ttls.get(tool_name, 300)
        self.redis.setex(key, ttl, json.dumps(result, default=str))
    
    def invalidate(self, tool_name: str = None):
        """批量失效缓存"""
        pattern = f"{self.prefix}{tool_name}:*" if tool_name else f"{self.prefix}*"
        keys = list(self.redis.scan_iter(match=pattern))
        if keys:
            self.redis.delete(*keys)
        return len(keys)
    
    def stats(self) -> dict:
        """缓存统计"""
        all_keys = list(self.redis.scan_iter(match=f"{self.prefix}*"))
        by_tool = {}
        for key in all_keys:
            tool = key.decode().split(":")[2]  # cache:tool:weather_api:hash
            by_tool[tool] = by_tool.get(tool, 0) + 1
        return {"total_cached": len(all_keys), "by_tool": by_tool}


# ============ 装饰器：自动缓存 Tool 调用 ============

def cached_tool(cache: ToolCache, ttl: int = None):
    """装饰器：自动对 Tool 调用做缓存"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(params: dict):
            tool_name = func.__name__
            
            # 1. 先查缓存
            cached = cache.get(tool_name, params)
            if cached is not None:
                return {**cached, "_source": "cache"}
            
            # 2. 缓存未命中，真实调用
            result = func(params)
            
            # 3. 写入缓存
            cache.set(tool_name, params, result, ttl)
            
            return {**result, "_source": "fresh"}
        
        return wrapper
    return decorator


# ============ 使用示例 ============

cache = ToolCache(redis_client)

@cached_tool(cache, ttl=1800)
def weather_api(params: dict) -> dict:
    """天气查询（30分钟内缓存）"""
    city = params["city"]
    date = params["date"]
    # 实际 HTTP 调用
    response = requests.get(
        f"https://api.weather.com/forecast",
        params={"city": city, "date": date},
        timeout=5
    )
    return response.json()

# 第一次调用 → 真实 API 请求
result1 = weather_api({"city": "成都", "date": "2026-07-15"})
print(result1["_source"])  # "fresh"

# 第二次调用（相同参数）→ 缓存命中
result2 = weather_api({"city": "成都", "date": "2026-07-15"})
print(result2["_source"])  # "cache"
```

---

## 4. 语义缓存（Semantic Cache）

参数完全相同的 Tool 调用容易缓存。但参数不同、意思相近的呢？

```
"成都7月天气"  vs  "成都七月份气候怎么样"
→ 字符串不同，但语义相同 → 都应该命中同一个缓存
```

```python
import numpy as np

class SemanticCache(ToolCache):
    """基于 Embedding 相似度的语义缓存"""
    
    def __init__(self, redis_client, similarity_threshold: float = 0.92):
        super().__init__(redis_client)
        self.threshold = similarity_threshold
    
    def get_semantic(self, tool_name: str, query: str) -> Optional[dict]:
        """用语义相似度匹配缓存"""
        query_emb = embed(query)
        
        # 扫描该工具的所有缓存 key
        pattern = f"{self.prefix}{tool_name}:*"
        best_match = None
        best_similarity = 0
        
        for key in self.redis.scan_iter(match=pattern):
            # 缓存时同时存储了 query 的 embedding
            cached_emb = self.redis.hget(key, "embedding")
            if not cached_emb:
                continue
            
            cached_emb = np.frombuffer(cached_emb, dtype=np.float32)
            similarity = cosine_similarity(query_emb, cached_emb)
            
            if similarity > best_similarity and similarity >= self.threshold:
                best_similarity = similarity
                best_match = key
        
        if best_match:
            data = self.redis.hget(best_match, "result")
            return {
                **json.loads(data),
                "_source": f"semantic_cache (sim={best_similarity:.2f})"
            }
        return None
    
    def set_semantic(self, tool_name: str, query: str, 
                     result: dict, ttl: int = None):
        """写入时同时存 embedding"""
        key = self._make_key(tool_name, {"query": query})
        ttl = ttl or self.default_ttls.get(tool_name, 300)
        
        query_emb = embed(query)
        self.redis.hset(key, "result", json.dumps(result, default=str))
        self.redis.hset(key, "embedding", query_emb.tobytes())
        self.redis.expire(key, ttl)
```

---

## 5. 缓存失效策略

```
策略              | 做法                    | 适用场景
─────────────────────────────────────────────────────
TTL 过期          | 固定时间后自动失效       | 大多数场景
主动失效          | 数据更新时手动删除缓存    | 预订状态、库存
写穿透            | 先写缓存再写DB           | 需要强一致性的读
Cache-Aside      | 读缓存→miss→读DB→写缓存 | 最常用
```

```python
class CacheInvalidationStrategy:
    """旅游 Agent 的缓存失效规则"""
    
    RULES = {
        # 用户预订了航班 → 相关航班搜索缓存可能过期
        "book_flight": {
            "on_success": ["flight_search"],   # 预订成功后失效航班缓存
            "ttl_override": None
        },
        # 用户改了预算 → 酒店/航班推荐可能变化
        "budget_change": {
            "on_success": ["flight_search", "hotel_search"],
            "ttl_override": None
        },
        # 距出发日期 < 1天 → 缩短缓存
        "near_departure": {
            "on_success": None,
            "ttl_override": 60  # 1分钟
        }
    }
    
    def on_action(self, action: str, cache: ToolCache):
        """某操作完成后，失效相关缓存"""
        rule = self.RULES.get(action, {})
        for tool in (rule.get("on_success") or []):
            count = cache.invalidate(tool)
            print(f"失效 {tool} 缓存: {count} 条")
```

---

## 6. 缓存击穿防护

热点 Key 过期瞬间，大量请求打到后端 → 可能打挂服务。

```python
import threading

class SafeCache(ToolCache):
    """防止缓存击穿的缓存"""
    
    def __init__(self, redis_client):
        super().__init__(redis_client)
        self.locks = {}  # 本地锁（生产用 Redis 分布式锁）
    
    def get_or_compute(self, tool_name: str, params: dict,
                       compute_fn: Callable, ttl: int = None):
        """读缓存，miss 时只有一个请求去计算，其余等待"""
        cached = self.get(tool_name, params)
        if cached is not None:
            return cached
        
        key = self._make_key(tool_name, params)
        
        # 防止缓存击穿：只让一个请求去计算
        if key not in self.locks:
            self.locks[key] = threading.Lock()
        
        with self.locks[key]:
            # Double-check：可能锁等待期间别的请求已写入
            cached = self.get(tool_name, params)
            if cached is not None:
                return cached
            
            # 真实计算
            result = compute_fn(params)
            self.set(tool_name, params, result, ttl)
            return result
```

---

## 7. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 所有 Tool 结果都缓存 | 读到过期数据 | 只缓存"一段时间内不变的" |
| TTL 设太长 | 用户看到昨天的航班价格 | 价格类 ≤5min，天气≤30min |
| 没有缓存击穿保护 | 热点 Key 过期瞬间打挂服务 | 互斥锁 / 永不过期+异步更新 |
| 缓存 Key 设计不当 | 大量 Key 从不命中 | 排序参数再 hash |
| 语义缓存阈值太低 | 不相关的结果被复用 | 阈值 ≥0.92 |

---

## 实践任务

**任务1**：实现 ToolCache，用 Redis 缓存 weather_api 和 flight_search 的结果。对比有缓存和无缓存的延迟差异。

**任务2**：为你的旅游 Agent 列出所有 Tool，标注每个 Tool 的缓存 TTL 和失效条件。画出缓存决策流程图。

**任务3**：实现缓存击穿保护——模拟 10 个并发请求同时查询同一个未缓存的 Key，验证只有一个真实调用了外部 API。

---

→ [06-Monitoring.md](./06-Monitoring.md)
