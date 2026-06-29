# 03 - Async Tasks — 异步任务与定时调度

> 学习目标：理解为什么长任务必须异步，掌握 Message Queue + Worker + Scheduler 的组合

---

## 1. 问题：同步阻塞

```
用户："帮我生成7月成都五日游的完整行程，包括每天路线、餐厅推荐、预算明细"

同步模式：
  Request → Agent 开始处理 → [5分钟...] → 用户盯着白屏 → Response

异步模式：
  Request → 立即返回 "已收到，正在规划中" → Queue → Worker处理 →
  → 完成后通知用户 / 用户轮询查看结果
```

> **核心认知**：超过 3 秒的操作必须异步。用户不关心你怎么处理，只关心"什么时候好"。

---

## 2. 消息队列架构

```
                      ┌─────────────┐
                      │   API 服务   │
                      └──────┬──────┘
                             │  收到长任务请求
                             ▼
                      ┌─────────────┐
                      │ Redis Queue │  ← 消息队列（轻量选择）
                      │  / Celery   │  ← 企业选择（更多功能）
                      └──────┬──────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Worker 1 │ │ Worker 2 │ │ Worker 3 │
        │ 行程生成  │ │ 报告生成  │ │ 数据导出  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          │
                    ┌─────▼──────┐
                    │ Result Store│  ← Redis/DB 存结果
                    └────────────┘
```

---

## 3. 基于 Redis Queue 的最简实现

```python
import json
import uuid
import redis
from datetime import datetime
from typing import Callable

class TaskQueue:
    """基于 Redis List 的轻量消息队列"""
    
    def __init__(self, redis_client: redis.Redis, queue_name: str = "agent:tasks"):
        self.redis = redis_client
        self.queue_key = queue_name
        self.result_prefix = "agent:task_result:"
    
    # ──── Producer：提交任务 ────
    def submit(self, task_type: str, params: dict, 
               user_id: str, session_id: str) -> str:
        """提交任务到队列，立即返回 task_id"""
        task_id = str(uuid.uuid4())
        task = {
            "task_id":    task_id,
            "task_type":  task_type,      # "generate_itinerary" | "export_report"
            "params":     params,
            "user_id":    user_id,
            "session_id": session_id,
            "status":    "queued",
            "submitted_at": datetime.now().isoformat()
        }
        
        # LPUSH 到队列
        self.redis.lpush(self.queue_key, json.dumps(task))
        
        # 存任务状态
        self.redis.setex(
            f"{self.result_prefix}{task_id}",
            3600,  # 结果保留1小时
            json.dumps({"status": "queued", "progress": 0})
        )
        
        return task_id
    
    # ──── Consumer：Worker 处理 ────
    def consume(self, handler: Callable, worker_name: str = "worker-1"):
        """Worker 阻塞消费队列"""
        print(f"[{worker_name}] 开始消费队列: {self.queue_key}")
        
        while True:
            # BRPOP 阻塞等待，超时5秒
            result = self.redis.brpop(self.queue_key, timeout=5)
            if result is None:
                continue  # 超时，继续等待
            
            _, task_json = result
            task = json.loads(task_json)
            task_id = task["task_id"]
            
            try:
                # 更新状态
                self._update_status(task_id, "processing", 0)
                
                # 执行实际任务（可上报进度）
                def progress_callback(pct):
                    self._update_status(task_id, "processing", pct)
                
                result_data = handler(task, progress_callback)
                
                # 标记完成
                self._update_status(task_id, "completed", 100,
                                    result=result_data)
                print(f"[{worker_name}] ✅ {task['task_type']} 完成")
                
            except Exception as e:
                self._update_status(task_id, "failed", 0, 
                                    error=str(e))
                print(f"[{worker_name}] ❌ {task['task_type']} 失败: {e}")
    
    # ──── 查询结果 ────
    def get_result(self, task_id: str) -> dict:
        """查询任务状态和结果"""
        data = self.redis.get(f"{self.result_prefix}{task_id}")
        if not data:
            return {"status": "not_found"}
        return json.loads(data)
    
    def _update_status(self, task_id: str, status: str, 
                       progress: int, result=None, error=None):
        data = {
            "status": status,
            "progress": progress,
            "updated_at": datetime.now().isoformat()
        }
        if result:
            data["result"] = result
        if error:
            data["error"] = error
        
        self.redis.setex(
            f"{self.result_prefix}{task_id}",
            3600,
            json.dumps(data, default=str)
        )


# ============ 使用示例 ============

# 定义具体任务
def generate_itinerary(task: dict, on_progress: Callable):
    """生成完整行程（模拟长任务）"""
    params = task["params"]
    
    # Step 1: 搜索目的地信息
    on_progress(10)
    destination_info = search_destination(params["destination"])
    
    # Step 2: 查交通
    on_progress(30)
    flights = search_flights(params["departure"], params["destination"])
    
    # Step 3: 制定每日行程
    on_progress(60)
    itinerary = llm.generate_itinerary(destination_info, flights, params)
    
    # Step 4: 生成文档
    on_progress(90)
    document = format_itinerary_document(itinerary)
    
    on_progress(100)
    return {"document": document, "summary": itinerary["summary"]}


# API 端（Producer）
def api_generate_trip(request):
    task_id = queue.submit(
        task_type="generate_itinerary",
        params={
            "destination": request.destination,
            "departure": request.departure,
            "days": request.days,
            "budget": request.budget
        },
        user_id=request.user_id,
        session_id=request.session_id
    )
    return {"task_id": task_id, "status": "queued",
            "poll_url": f"/tasks/{task_id}/status"}

# Worker 端（Consumer，独立进程运行）
# queue.consume(generate_itinerary, worker_name="worker-1")
```

---

## 4. 定时调度（Scheduler）

有些任务不需要用户触发，而是按时间自动执行。

```
Cron 定时任务：
- 每天早上 8:00：检查明天出发的用户，推送天气提醒
- 每周一 10:00：汇总上周 Token 消耗，发送成本周报
- 每小时：清理过期 Session
```

```python
import schedule
import time

class AgentScheduler:
    def __init__(self, session_manager, queue: TaskQueue):
        self.sm = session_manager
        self.queue = queue
    
    def start(self):
        # 每天早上 8:00 — 推送天气提醒
        schedule.every().day.at("08:00").do(self.send_weather_reminders)
        
        # 每周一 10:00 — 发送成本周报
        schedule.every().monday.at("10:00").do(self.send_cost_report)
        
        # 每小时 — 清理过期会话
        schedule.every().hour.do(self.cleanup_expired_sessions)
        
        print("[Scheduler] 启动")
        while True:
            schedule.run_pending()
            time.sleep(30)  # 30秒检查一次
    
    def send_weather_reminders(self):
        """检查明天出发的用户"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 从数据库查明天出发的活跃会话
        sessions = db.query("""
            SELECT DISTINCT user_id, context->>'destination' as dest
            FROM sessions
            WHERE context->>'departure_date' = %s
              AND current_state != 'DONE'
        """, [tomorrow])
        
        for s in sessions:
            weather = weather_api.get(s['dest'], tomorrow)
            notify_user(s['user_id'], 
                f"🌤 明天出发！{s['dest']}天气：{weather['summary']}")
    
    def send_cost_report(self):
        """汇总上周 Token 成本"""
        last_week = datetime.now() - timedelta(days=7)
        stats = db.query("""
            SELECT 
                COUNT(*) as total_calls,
                SUM(tokens_used) as total_tokens,
                SUM(cost) as total_cost
            FROM tool_logs
            WHERE created_at > %s
        """, [last_week])
        
        # 发送报告
        send_admin_report("📊 上周 Agent 成本周报", stats)
    
    def cleanup_expired_sessions(self):
        """清理 Redis 中已过期但未归档的 Session"""
        # Redis TTL 已自动删除，这里做数据库层面的清理
        db.execute("""
            UPDATE sessions SET current_state = 'TIMEOUT'
            WHERE current_state = 'WAITING'
              AND last_active < NOW() - INTERVAL '1 hour'
        """)
```

---

## 5. Celery（企业级选择）

当 Redis Queue 不够用（需要任务优先级、定时重试、结果后端），升级到 Celery：

```python
# tasks.py
from celery import Celery

app = Celery('agent_tasks', broker='redis://localhost:6379/1')

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_itinerary_task(self, user_id, params):
    """Celery 版本——自动重试、状态追踪"""
    try:
        self.update_state(state='PROGRESS', meta={'progress': 10})
        # ... 同上 ...
        return {"document": doc, "summary": summary}
    except ExternalAPIError as exc:
        raise self.retry(exc=exc)  # 自动重试


# 提交任务
result = generate_itinerary_task.delay(user_id, params)
# 查询进度
result.state    # 'PROGRESS'
result.info     # {'progress': 60}
```

---

## 6. Queue vs Scheduler 对比

| 维度 | Queue（消息队列） | Scheduler（定时调度） |
|------|------------------|---------------------|
| 触发方式 | 用户操作 → 产生任务 | 时间到达 → 自动执行 |
| 执行频率 | 按需，不可预测 | 固定时间/间隔 |
| 典型场景 | 生成行程、导出PDF | 天气提醒、成本周报、清理 |
| 技术 | Redis Queue / Celery / RabbitMQ | Cron / schedule / APScheduler |
| 重试策略 | 失败后重试 3 次 | 失败记录日志，下次继续 |

---

## 7. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 同步处理长任务 | API 超时，用户体验极差 | >3秒的操作全部异步 |
| 只有队列没进度查询 | 用户不知道还要等多久 | 提供 /tasks/{id}/status 端点 |
| Worker 没有异常处理 | 一个任务崩了，Worker 退出 | 每个任务 try/except 包裹 |
| 定时任务和业务代码耦合 | 修改 Cron 要重新部署 | Scheduler 独立进程 |
| 结果永久保留 | Redis 内存炸了 | 结果设 TTL，重要结果归档 PG |

---

## 实践任务

**任务1**：用 Redis List 实现一个最简 TaskQueue：submit → consume → get_result。用一个 sleep(10) 的假任务测试完整流程。

**任务2**：为你的旅游 Agent 列出至少 3 个需要异步处理的场景，以及 3 个需要定时调度的场景。

**任务3**：实现一个 progress_callback——在 Worker 处理行程生成时，实时更新进度（10%→30%→60%→90%→100%），前端轮询显示进度条。

---

→ [04-Resilience.md](./04-Resilience.md)
