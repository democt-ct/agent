# 06 - Human-in-the-Loop — 人机协同

> 学习目标：理解 HITL 的设计原则，掌握审批节点、中断恢复和安全边界的实现

---

## 1. 为什么需要 HITL

Agent 本质上是一个**有概率出错**的系统——LLM 可能幻觉、工具可能误操作、用户意图可能被误解。

```
没有 HITL：
  Agent: "好的，我来删除数据库中的所有过期记录"
  → DELETE FROM orders WHERE created_at < '2025-01-01'
  → 删除了 50 万条记录
  → WHERE 条件写错了……但已经晚了

有 HITL：
  Agent: "我准备删除 50 万条记录，这是 SQL：
         DELETE FROM orders WHERE created_at < '2025-01-01'
         确认执行吗？"
  用户: "等等，应该是 2024 年之前！"
  → 避免了生产事故
```

> **核心认知**：HITL 不是"Agent 不够聪明"的补丁，而是**负责任系统的设计选择**。给 Agent 权力越大，HITL 越重要。

---

## 2. HITL 的三个层次

```
Layer 1: Notification    通知（Agent 做了操作，告知用户）
    ↓
Layer 2: Confirmation   确认（操作前征求用户同意）
    ↓
Layer 3: Intervention   干预（用户可以中止、修改、接管）
```

### Layer 1 — Notification（通知）

最低介入。Agent 自动执行，执行后通报。

```python
class Notifier:
    def notify(self, action: str, result: dict):
        # 写入日志
        logger.info(f"[Agent Action] {action}: {result}")
      
        # 推送通知（异步）
        notification = {
            "type": "agent_action",
            "title": f"Agent 执行了：{action}",
            "detail": result.get("summary", ""),
            "timestamp": datetime.now().isoformat()
        }
        self.push_to_user(notification)
  
    def push_to_user(self, notification: dict):
        # WebSocket / SSE / 轮询 等方式推送给前端
        pass

# 使用
agent.book_flight("MU5678")
notifier.notify("预订航班", {"flight": "MU5678", "cost": 980})
# 用户看到通知：Agent帮你订了MU5678，¥980
```

### Layer 2 — Confirmation（确认）

操作前需要用户明确同意。

```python
from enum import Enum

class ActionRisk(Enum):
    LOW    = "low"      # 搜索、查询
    MEDIUM = "medium"   # 写入、修改
    HIGH   = "high"     # 删除、支付

RISK_THRESHOLD = {
    ActionRisk.LOW:    "auto",       # 自动执行
    ActionRisk.MEDIUM: "confirm",    # 需要确认
    ActionRisk.HIGH:   "approve",    # 需要审批
}

class ConfirmationGate:
    def __init__(self):
        self.pending_actions: Dict[str, dict] = {}
  
    def check(self, action: str, params: dict) -> dict:
        """检查是否需要确认"""
        risk = self._assess_risk(action, params)
        threshold = RISK_THRESHOLD[risk]
      
        if threshold == "auto":
            return {"status": "approved", "risk": risk.value}
      
        # 需要确认
        action_id = str(uuid.uuid4())
        self.pending_actions[action_id] = {
            "action": action,
            "params": params,
            "risk": risk.value,
            "status": "pending",
            "created_at": datetime.now()
        }
      
        return {
            "status": "pending_confirmation",
            "action_id": action_id,
            "risk": risk.value,
            "message": self._format_confirmation(action, params, risk)
        }
  
    def _assess_risk(self, action: str, params: dict) -> ActionRisk:
        """评估操作风险等级"""
        # 高风险操作
        if action in ["delete_database", "drop_table", "payment", 
                       "send_email_to_all", "deploy_to_production"]:
            return ActionRisk.HIGH
      
        # 中风险操作
        if action in ["book_flight", "book_hotel", "update_record",
                       "modify_file", "run_sql"]:
            return ActionRisk.MEDIUM
      
        # 低风险操作
        return ActionRisk.LOW
  
    def _format_confirmation(self, action, params, risk):
        """生成人类可读的确认消息"""
        return f"""
⚠️ 操作确认（风险等级：{risk.value}）

Agent 计划执行：{action}

详细参数：
{json.dumps(params, indent=2, ensure_ascii=False)}

是否确认执行？
[确认] [拒绝] [修改参数]
"""
  
    def approve(self, action_id: str) -> bool:
        if action_id in self.pending_actions:
            self.pending_actions[action_id]["status"] = "approved"
            return True
        return False
  
    def reject(self, action_id: str, reason: str = "") -> bool:
        if action_id in self.pending_actions:
            self.pending_actions[action_id]["status"] = "rejected"
            self.pending_actions[action_id]["reject_reason"] = reason
            return True
        return False
```

### Layer 3 — Intervention（干预）

用户可以中止正在执行的操作、修改 Agent 的决策、或者完全接管。

```python
class InterventionManager:
    def __init__(self):
        self.intervention_flags: Dict[str, bool] = {}
        self.modifications: Dict[str, dict] = {}
  
    def request_stop(self, session_id: str):
        """用户请求中止"""
        self.intervention_flags[session_id] = True
  
    def should_stop(self, session_id: str) -> bool:
        """Agent 在每个步骤前检查"""
        return self.intervention_flags.get(session_id, False)
  
    def inject_modification(self, session_id: str, 
                            step: str, new_params: dict):
        """用户修改某个步骤的参数"""
        self.modifications[f"{session_id}:{step}"] = new_params
  
    def get_modification(self, session_id: str, step: str):
        """Agent 在执行前检查是否有用户修改"""
        return self.modifications.get(f"{session_id}:{step}")


# Agent 循环中集成 Intervention
class HITLAgent:
    def __init__(self):
        self.confirmation = ConfirmationGate()
        self.intervention = InterventionManager()
  
    def execute_step(self, step: dict, session_id: str):
        # 检查中止请求
        if self.intervention.should_stop(session_id):
            return {"status": "stopped", "message": "用户中止了操作"}
      
        # 检查用户是否修改了这个步骤
        modification = self.intervention.get_modification(
            session_id, step["name"]
        )
        if modification:
            step["params"].update(modification)
      
        # 风险评估
        check = self.confirmation.check(step["action"], step["params"])
      
        if check["status"] == "pending_confirmation":
            # 返回给前端，等待用户确认
            return {
                "status": "awaiting_confirmation",
                "action_id": check["action_id"],
                "message": check["message"]
            }
      
        # 通过，执行
        return self._do_execute(step)
```

---

## 3. 何时需要 HITL

不是每个操作都需要打断用户。判断标准：

```
必须 HITL：
  ✅ 修改生产数据
  ✅ 涉及支付
  ✅ 发送批量通知（邮件/短信）
  ✅ 执行不可逆操作（删除/部署）
  ✅ Agent 置信度低于阈值

可以自动：
  ✅ 搜索信息
  ✅ 读取数据
  ✅ 生成草稿
  ✅ 内部计算
  ✅ Agent 置信度高于 95%
```

---

## 4. 中断与恢复

用户确认（或拒绝、修改）后，Agent 必须能从断点继续。

```python
class HITLStateMachine:
    """扩展现有的 State Machine，加入 HITL 状态"""
  
    def handle_user_response(self, response: dict):
        """
        response = {
            "action_id": "uuid",
            "decision": "approve" | "reject" | "modify",
            "modifications": {...}  // 如果 decision == "modify"
        }
        """
        action_id = response["action_id"]
      
        match response["decision"]:
            case "approve":
                self.confirmation.approve(action_id)
                # 恢复执行
                self.transition(AgentState.EXECUTING, "user_approved")
                return self.resume_from_checkpoint()
          
            case "reject":
                self.confirmation.reject(action_id, 
                    response.get("reason", "用户拒绝"))
                # 跳过当前步骤，执行替代方案
                self.transition(AgentState.EXECUTING, "user_rejected")
                return self.execute_fallback()
          
            case "modify":
                # 注入修改后的参数
                self.intervention.inject_modification(
                    self.session_id,
                    self.current_step,
                    response["modifications"]
                )
                self.confirmation.approve(action_id)
                self.transition(AgentState.EXECUTING, "user_modified")
                return self.resume_from_checkpoint()
  
    def resume_from_checkpoint(self):
        """从上次中断的地方继续"""
        checkpoint = self.context.get("checkpoint")
        if not checkpoint:
            raise Exception("没有检查点，无法恢复")
      
        # 恢复状态
        self.current_step = checkpoint["step"]
        self.context.update(checkpoint["context_snapshot"])
      
        # 继续执行
        return self.execute_next_step()
  
    def save_checkpoint(self):
        """在等待确认前保存检查点"""
        self.context["checkpoint"] = {
            "step": self.current_step,
            "context_snapshot": dict(self.context),
            "timestamp": datetime.now().isoformat()
        }
```

---

## 5. HITL 的用户体验设计

```
❌ 糟糕的 HITL：
  "Agent 想执行 tool_call_7d3f8a2b，参数 {...}，确认吗？"
  → 用户看不懂，要么全点确认（形同虚设），要么全拒绝（Agent 没法用）

✅ 好的 HITL：
  "准备预订 MU5678 航班
   📅 2026年7月15日
   🛫 北京 → 成都
   💰 ¥980（含税）
   👤 1位乘客
   
   [确认预订] [换一个航班] [取消]"
```

设计原则：

```python
def format_hitl_message(action: str, params: dict, risk: str) -> str:
    """把机器参数翻译成人话"""
  
    # 按操作类型定制展示
    templates = {
        "book_flight": """
✈️ 机票预订确认

航班：{flight_number}
日期：{date}
路线：{departure} → {destination}
价格：¥{price}（{class_type}）
乘客：{passengers}人

风险等级：{risk}
        """,
      
        "delete_records": """
⚠️ 数据删除确认

表名：{table}
条件：{condition}
预计影响：{estimated_rows} 条记录

此操作不可撤销！
风险等级：{risk}
        """,
    }
  
    template = templates.get(action, "操作：{action}\n参数：{params}")
    return template.format(**params, risk=risk, action=action)
```

---

## 6. 旅游 Agent 的 HITL 节点

画出旅游 Agent 中全部需要 HITL 的节点：

```
旅游Agent流程                    HITL 节点
────────────────────────────────────────────
理解需求                         自动
    ↓
规划行程                         自动
    ↓
搜索航班                         自动
    ↓
展示航班选项 ┄┄┄┄┄┄┄┄┄┄┄┄┄┄  ← 用户选择（Layer 2）
    ↓
预订航班 ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  ← 确认支付（Layer 3）
    ↓
搜索酒店                         自动
    ↓
展示酒店选项 ┄┄┄┄┄┄┄┄┄┄┄┄┄┄  ← 用户选择
    ↓
预订酒店 ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  ← 确认支付
    ↓
生成完整行程                     自动
    ↓
展示行程 ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  ← 用户审核（Layer 2）
    ↓
完成 ✨
```

---

## 7. 常见错误

| 错误               | 后果                   | 正确做法                     |
| ------------------ | ---------------------- | ---------------------------- |
| 所有操作都确认     | 用户变成"确认机器人"   | 低风险自动，高风险确认       |
| 确认信息看不懂     | 用户盲目点确认         | 翻译成人话，突出关键信息     |
| 只确认不保存检查点 | 确认后从头重来         | 每次中断前保存完整检查点     |
| 等待确认无超时     | 流程永远挂着           | 确认等待设超时，超时自动取消 |
| 不允许修改参数     | 用户只能全接受或全拒绝 | 允许用户修改部分参数         |

---

## 实践任务

**任务1**：为你的旅游 Agent 画 HITL 节点图——标注每个节点：自动还是确认？确认什么？用户有哪些选项？

**任务2**：实现 ConfirmationGate 的完整逻辑——包含风险评估、确认消息生成、超时处理、用户三种回应（approve/reject/modify）。

**任务3**：设计一个"中断恢复"场景的完整测试：

```
① Agent 执行到"预订航班"步骤，暂停等待确认
② 模拟服务重启（证明状态持久化）
③ 从 Redis 恢复
④ 用户回应"修改参数"（换一个航班号）
⑤ Agent 从修改后的参数继续执行
⑥ 验证最终结果正确
```

---

→ [07-实践：升级旅游Agent架构.md](./07-实践：升级旅游Agent架构.md)
