# 06 - Monitoring — 可观测性

> 学习目标：掌握 Agent 系统的四大可观测性支柱——Logging、Tracing、Metrics、Cost Tracking

---

## 1. 上线之前，先"看见"它

```
没有监控的 Production Agent：

  周二上午 10:23，用户开始投诉"规划行程特别慢"
  → 你翻日志：没有结构化的日志
  → 你看延迟：没有收集过
  → 你看成本：不知道哪个工具最费钱
  → 你看成功率：不知道是不是某个 API 挂了
  
  你瞎了。你不知道发生了什么。
```

> **核心认知**：监控不是"锦上添花"，是"安全带"。四个指标必须先有：**Latency、Token、Cost、Success Rate**。

---

## 2. 四大支柱

```
┌─────────────────────────────────────────────────────┐
│                   Agent Monitoring                   │
│                                                      │
│  [Logging]    结构化日志，记录每个决策点              │
│  [Tracing]    链路追踪，一次请求经过的所有组件        │
│  [Metrics]    指标仪表盘，实时数值                    │
│  [Cost]       Token/费用追踪，按用户/工具/天聚合     │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 3. Logging — 结构化日志

```python
import logging
import json
from datetime import datetime
from typing import Any, Dict

class AgentLogger:
    """Agent 专用结构化日志"""
    
    def __init__(self, app_name: str = "travel-agent"):
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(logging.DEBUG)
        
        # JSON 格式输出（方便 ELK/Loki 采集）
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)
    
    def _log(self, level: str, event: str, 
             session_id: str = None, **kwargs):
        record = {
            "timestamp": datetime.now().isoformat(),
            "level":     level,
            "event":     event,
            "session_id": session_id,
            **kwargs
        }
        getattr(self.logger, level.lower())(json.dumps(record, default=str))
    
    # ──── Agent 专用日志事件 ────
    
    def agent_start(self, session_id: str, user_input: str):
        self._log("INFO", "agent.start", session_id, 
                  user_input=user_input[:200])
    
    def planner_decompose(self, session_id: str, goal: str, 
                          task_count: int, plan_tokens: int):
        self._log("INFO", "planner.decompose", session_id,
                  goal=goal, task_count=task_count, tokens=plan_tokens)
    
    def state_transition(self, session_id: str, 
                         from_state: str, to_state: str, event: str):
        self._log("INFO", "state.transition", session_id,
                  from_state=from_state, to_state=to_state, trigger=event)
    
    def tool_call_start(self, session_id: str, tool_name: str, 
                        params: Dict[str, Any]):
        self._log("DEBUG", "tool.call.start", session_id,
                  tool=tool_name, params=json.dumps(params, default=str))
    
    def tool_call_end(self, session_id: str, tool_name: str,
                      latency_ms: int, tokens: int, cost: float,
                      status: str, error: str = None):
        self._log("INFO", "tool.call.end", session_id,
                  tool=tool_name, latency_ms=latency_ms,
                  tokens=tokens, cost=cost, status=status, error=error)
    
    def hitl_decision(self, session_id: str, action: str, 
                      decision: str, user_id: str):
        self._log("WARNING", "hitl.decision", session_id,
                  action=action, decision=decision, user_id=user_id)
    
    def agent_end(self, session_id: str, 
                  total_tokens: int, total_cost: float,
                  total_latency_ms: int, success: bool):
        self._log("INFO", "agent.end", session_id,
                  total_tokens=total_tokens, total_cost=total_cost,
                  total_latency_ms=total_latency_ms, success=success)
    
    def error(self, session_id: str, component: str, 
              error_msg: str, context: dict = None):
        self._log("ERROR", f"{component}.error", session_id,
                  error=error_msg, context=context)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return record.getMessage()  # 消息已是 JSON


# 全局实例
agent_log = AgentLogger()

# 使用
agent_log.tool_call_end("sess_abc", "flight_search", 
    latency_ms=450, tokens=1200, cost=0.003, status="success")

# 输出：
# {"timestamp": "2026-07-15T10:05:00", "level": "INFO", 
#  "event": "tool.call.end", "session_id": "sess_abc",
#  "tool": "flight_search", "latency_ms": 450, "tokens": 1200,
#  "cost": 0.003, "status": "success"}
```

---

## 4. Tracing — 链路追踪

一次用户请求经过 Router → Planner → Workflow → 3 个 Tool 调用 → HITL → Output。每个环节耗时多少？

```python
import time
import uuid
from contextlib import contextmanager

class AgentTracer:
    """轻量链路追踪（不依赖外部服务）"""
    
    def __init__(self):
        self.traces: Dict[str, list] = {}
    
    def start_trace(self, session_id: str) -> str:
        trace_id = str(uuid.uuid4())[:8]
        self.traces[trace_id] = []
        return trace_id
    
    @contextmanager
    def span(self, trace_id: str, span_name: str):
        """追踪一个操作的耗时"""
        start = time.perf_counter()
        span_data = {"name": span_name, "start": start}
        
        try:
            yield
        except Exception as e:
            span_data["error"] = str(e)
            raise
        finally:
            span_data["duration_ms"] = (time.perf_counter() - start) * 1000
            self.traces[trace_id].append(span_data)
    
    def get_trace(self, trace_id: str) -> dict:
        spans = self.traces.get(trace_id, [])
        
        if not spans:
            return {"trace_id": trace_id, "spans": [], "total_ms": 0}
        
        total_ms = sum(s["duration_ms"] for s in spans)
        
        # 格式化输出
        print(f"\n{'='*60}")
        print(f"Trace: {trace_id}  |  Total: {total_ms:.0f}ms")
        print(f"{'='*60}")
        
        for span in sorted(spans, key=lambda s: s["start"]):
            bar = "█" * int(span["duration_ms"] / total_ms * 40) if total_ms else ""
            error = f" ❌ {span.get('error', '')}" if "error" in span else ""
            print(f"  {span['name']:30s} {span['duration_ms']:8.1f}ms {bar}{error}")
        
        return {"trace_id": trace_id, "spans": spans, "total_ms": total_ms}
    
    def to_dict(self, trace_id: str) -> dict:
        spans = self.traces.get(trace_id, [])
        return {
            "trace_id": trace_id,
            "spans": [{"name": s["name"], "duration_ms": s["duration_ms"]} 
                      for s in spans],
            "total_ms": sum(s["duration_ms"] for s in spans)
        }


# ============ 集成到 Agent 中 ============

class MonitoredAgent:
    def __init__(self):
        self.logger = AgentLogger()
        self.tracer = AgentTracer()
    
    def handle(self, user_input: str, session_id: str, user_id: str):
        trace_id = self.tracer.start_trace(session_id)
        start_time = time.perf_counter()
        total_tokens = 0
        total_cost = 0.0
        
        self.logger.agent_start(session_id, user_input)
        
        # Router
        with self.tracer.span(trace_id, "router.classify"):
            intent = self.router.classify(user_input)
        
        # Planner
        with self.tracer.span(trace_id, "planner.decompose"):
            plan = self.planner.decompose(user_input)
            total_tokens += plan.tokens
            total_cost += plan.cost
            self.logger.planner_decompose(
                session_id, user_input, len(plan.tasks), plan.tokens
            )
        
        # Tool Calls
        for task in plan.tasks:
            with self.tracer.span(trace_id, f"tool.{task.tool_name}"):
                result = self.execute_tool(task)
                total_tokens += result.tokens
                total_cost += result.cost
                self.logger.tool_call_end(
                    session_id, task.tool_name,
                    latency_ms=result.latency_ms,
                    tokens=result.tokens, cost=result.cost,
                    status=result.status
                )
        
        total_latency = (time.perf_counter() - start_time) * 1000
        self.logger.agent_end(session_id, total_tokens, total_cost,
                              total_latency, success=True)
        
        # 输出链路追踪
        trace = self.tracer.get_trace(trace_id)
        
        return {"output": output, "trace": trace}
```

链路追踪输出示例：

```
============================================================
Trace: a3f7b2c1  |  Total: 3245ms
============================================================
  router.classify                    12.3ms ▏
  planner.decompose                 856.2ms ██████████
  tool.web_search                  1205.1ms ██████████████▌
  tool.flight_search                804.7ms █████████▉
  tool.hotel_search                 345.0ms ████▏
  state.save_checkpoint              21.7ms ▏
============================================================
```

---

## 5. Metrics — 实时指标

```python
from collections import defaultdict
from datetime import datetime, timedelta

class AgentMetrics:
    """内存指标收集器（生产用 Prometheus client）"""
    
    def __init__(self):
        self.counters = defaultdict(int)
        self.latencies = defaultdict(list)
        self.window_seconds = 3600  # 1小时滑动窗口
    
    # ──── 记录 ────
    def record_tool_call(self, tool_name: str, latency_ms: int,
                         tokens: int, cost: float, status: str):
        now = datetime.now()
        
        # 计数
        self.counters[f"tool:{tool_name}:calls"] += 1
        self.counters[f"tool:{tool_name}:{status}"] += 1
        self.counters["total:tokens"] += tokens
        self.counters["total:cost"] += cost
        
        # 延迟（保留滑动窗口）
        self.latencies[f"tool:{tool_name}"].append((now, latency_ms))
        self._cleanup_latencies()
    
    def record_session(self, success: bool, total_ms: int):
        self.counters["session:total"] += 1
        self.counters[f"session:{'success' if success else 'failed'}"] += 1
        self.latencies["session"].append((datetime.now(), total_ms))
    
    # ──── 查询 ────
    def success_rate(self) -> float:
        total = self.counters["session:total"]
        if total == 0:
            return 1.0
        return self.counters["session:success"] / total
    
    def avg_latency(self, metric_name: str) -> float:
        entries = self.latencies.get(metric_name, [])
        if not entries:
            return 0
        return sum(e[1] for e in entries) / len(entries)
    
    def total_cost(self) -> float:
        return self.counters["total:cost"]
    
    def total_tokens(self) -> int:
        return self.counters["total:tokens"]
    
    def dashboard(self) -> str:
        """打印仪表盘"""
        return f"""
╔══════════════════════════════════════════════════╗
║            Agent Metrics Dashboard               ║
╠══════════════════════════════════════════════════╣
║ Sessions:   {self.counters['session:total']:>5} total │ {self.counters['session:success']:>5} success │ {self.counters['session:failed']:>5} failed
║ Success Rate: {self.success_rate():.1%}
║ Total Tokens: {self.total_tokens():,}
║ Total Cost:   ${self.total_cost():.4f}
╠══════════════════════════════════════════════════╣
║ Tool Latency (avg):
║   web_search:     {self.avg_latency('tool:web_search'):8.0f}ms
║   flight_search:  {self.avg_latency('tool:flight_search'):8.0f}ms
║   hotel_search:   {self.avg_latency('tool:hotel_search'):8.0f}ms
╚══════════════════════════════════════════════════╝
"""
    
    def _cleanup_latencies(self):
        """只保留滑动窗口内的数据"""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        for key in self.latencies:
            self.latencies[key] = [
                (t, v) for t, v in self.latencies[key] if t > cutoff
            ]


# 使用
metrics = AgentMetrics()
metrics.record_tool_call("flight_search", 450, 1200, 0.003, "success")
metrics.record_tool_call("hotel_search", 320, 800, 0.002, "success")
metrics.record_tool_call("flight_search", 5200, 1200, 0.003, "timeout")
metrics.record_session(True, 3245)

print(metrics.dashboard())
```

---

## 6. Cost Tracking — Token 费用追踪

```python
# 各模型定价（2026 年参考，实际价格会变动）
MODEL_PRICING = {
    "gpt-4o":       {"input": 2.50,  "output": 10.00},   # 每 1M tokens, USD
    "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
    "claude-3.5":   {"input": 3.00,  "output": 15.00},
    "deepseek-v3":  {"input": 0.27,  "output": 1.10},
}

class CostTracker:
    def __init__(self):
        self.daily_costs = defaultdict(lambda: {"tokens": 0, "cost": 0.0})
    
    def track_llm_call(self, model: str, input_tokens: int, 
                       output_tokens: int):
        pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
        cost = (input_tokens / 1_000_000 * pricing["input"] +
                output_tokens / 1_000_000 * pricing["output"])
        
        today = datetime.now().strftime("%Y-%m-%d")
        self.daily_costs[today]["tokens"] += input_tokens + output_tokens
        self.daily_costs[today]["cost"] += cost
        
        return cost
    
    def report(self, days: int = 7):
        """周报"""
        report = f"\n{'='*50}\n  Token 费用周报（最近 {days} 天）\n{'='*50}\n"
        total = 0
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            data = self.daily_costs.get(date, {"tokens": 0, "cost": 0})
            bar = "█" * int(data["cost"] * 200)
            report += f"  {date}: {data['tokens']:>8,} tokens | ${data['cost']:.4f} {bar}\n"
            total += data["cost"]
        
        report += f"  {'─'*45}\n  合计: ${total:.4f}\n"
        return report
```

---

## 7. 告警规则

```python
ALERT_RULES = {
    "high_cost": {
        "condition": lambda m: m.total_cost() > 50.0,   # 日费用 > $50
        "message": "🚨 今日 Token 费用超过 $50，请检查",
        "severity": "warning"
    },
    "low_success_rate": {
        "condition": lambda m: m.success_rate() < 0.85,  # 成功率 < 85%
        "message": "🚨 Agent 成功率低于 85%，可能存在故障",
        "severity": "critical"
    },
    "high_latency": {
        "condition": lambda m: m.avg_latency("session") > 10000,  # 平均>10s
        "message": "⚠️ Agent 平均延迟超过 10 秒",
        "severity": "warning"
    },
    "circuit_breaker_open": {
        "condition": "on_event",  # 事件驱动
        "message": "🔴 断路器已打开：{tool_name}",
        "severity": "critical"
    }
}
```

---

## 8. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 用 print 代替日志 | 无法采集、无法搜索 | 结构化 JSON 日志 |
| 只记错误不记正常 | 不知道正常是什么样 | 每个关键事件都记 |
| Token 费用不追踪 | 月底账单吓一跳 | 实时追踪+日/周报告 |
| 只监控不告警 | 问题发生几小时后才知道 | 关键指标设告警阈值 |
| 链路不追踪 | 不知道瓶颈在哪 | 每个 span 计时 |

---

## 实践任务

**任务1**：实现 AgentLogger，在你的旅游 Agent 中埋点至少 6 个日志事件。运行一次完整流程，查看 JSON 日志输出。

**任务2**：用手写的 AgentTracer 追踪一次完整请求的链路，输出每个环节的耗时。找出最慢的环节。

**任务3**：实现 AgentMetrics 的 dashboard，模拟 100 次 session（80%成功），20%失败的原因随机（超时/工具不可用/用户取消）。输出仪表盘。

---

→ [07-实践：Docker部署旅游Agent.md](./07-实践：Docker部署旅游Agent.md)
