# Skills 层设计文档

> 版本 v1.0 · 2026-06-10  
> 描述 `src/skills/` 层的设计理念、模块职责和使用方式

---

## 1. 为什么需要 Skills 层

### 1.1 现状问题

在 v1 架构中，业务逻辑散布在三个层级：

| 层 | 示例 | 问题 |
|----|------|------|
| `src/tools/` | `it_tools.create_ticket` | 只有原子操作，无状态机、无生命周期管理 |
| `src/api/service/` | `chat_service.chat` | 编排逻辑与 HTTP/SSE 耦合，无法独立测试和复用 |
| `src/agents/` | `base_agent.run` | ReAct 循环只适合单步推理，不适合多步事务 |

实际业务场景（如工单从创建到关闭、请假从提交到多级审批完成）是 **多步骤状态流转**，
单靠 Agent 的工具调用无法保证流程完整性。

### 1.2 Skills 层定位

```
用户界面 (CLI / Web / API)
         │
    ┌────▼────┐
    │  Agent  │  ← ReAct 循环，调用工具
    └────┬────┘
         │
    ┌────▼────────┐
    │   Skills    │  ← 新增：复合业务能力 + 状态机 + 通知
    │  (本次新增)  │
    └────┬────────┘
         │
    ┌────▼────┐
    │  DB 层  │  ← 原子数据访问 (src/tools/db/)
    └─────────┘
```

**设计原则**：
- 每个函数是纯 Python，无类状态，无外部依赖（除 DB）
- 返回结构化 dict，可被 Agent / CLI / 定时任务消费
- 不修改现有 `src/tools/` 的函数签名 — 向下兼容

---

## 2. 模块地图

| 模块 | 文件 | 职责 |
|------|------|------|
| **工单生命周期** | `ticket_lifecycle.py` | 创建 → 处理 → 完成 → 关闭 → 重开 → 升级 → 统计 |
| **审批引擎** | `approval_engine.py` | 通用审批流：请假/报销共用，自动定审批链 |
| **通知中心** | `notification.py` | 统一发送/查询/标记已读，含 5 分钟去重 |
| **聚合报表** | `reporting.py` | 日报/周报/月报/预算/仪表盘 |

---

## 3. 工单生命周期

### 3.1 状态机

```
待处理 ──→ 处理中 ──→ 已完成
  │          │
  └── 已关闭 ←┘
       │
       └── 待处理 (重开)
```

### 3.2 API 一览

| 函数 | 状态转换 | 说明 |
|------|---------|------|
| `create_ticket_full()` | (新建) → 待处理 | 创建 + 自动路由 + 双重通知 |
| `process_ticket()` | 待处理 → 处理中 | 开始处理，通知申请人 |
| `complete_ticket()` | 处理中 → 已完成 | 完成 + 解决方案记录 |
| `close_ticket()` | 待处理/处理中 → 已关闭 | 撤销/重复/无法处理 |
| `reopen_ticket()` | 已关闭 → 待处理 | 重新激活，通知受理人 |
| `escalate_ticket()` | 任意非终态 | 优先级升为"高"，通知部门经理 |
| `get_ticket_detail()` | — | 详情 + 处理时长 |
| `get_ticket_summary()` | — | 按状态/类型/优先级/部门聚合 |

### 3.3 调用方

- **Agent**: 通过 `IT_TOOLS` 中的 `update_ticket_status` / `escalate_ticket` / `get_ticket_summary` / `get_ticket_detail`
- **CLI**: `python scripts/ticket_ops.py create/process/complete/close/reopen/escalate/report/list/dashboard`
- **定时任务**: `python scripts/ticket_ops.py report --type weekly`

---

## 4. 审批引擎

### 4.1 通用设计

不再为每种记录类型（请假、报销）写独立的审批逻辑，而是统一为：

```
submit_for_approval(record_type, record_id, user_id, threshold_value)
  → 根据规则自动确定审批层级
  → 创建 approval_flow 步骤
  → 通知第一位审批人
```

**审批规则配置**：

```python
LEAVE_APPROVAL_RULES = [
    (3,   "direct_manager", "直属上级"),     # ≤3 天
    (7,   "dept_head",      "部门负责人"),    # ≤7 天
    (inf, "hr",             "HR 总监"),       # >7 天
]

EXPENSE_APPROVAL_RULES = [
    (5000, "direct_manager", "直属上级"),     # <5000 元
    (inf,  "finance",        "财务经理"),     # ≥5000 元
]
```

### 4.2 API 一览

| 函数 | 说明 |
|------|------|
| `build_approval_chain()` | 按规则 + 汇报链构建审批步骤 |
| `submit_for_approval()` | 提交审批（创建审批流 + 通知） |
| `approve_step()` | 通过当前步骤，自动推进到下一级或完成 |
| `reject_step()` | 驳回（整条记录驳回，通知申请人） |
| `get_approval_status()` | 查看审批进度 |
| `get_pending_approvals()` | 某人的待审批列表（请假 + 报销合并） |

### 4.3 调用方

- **Agent**: 通过 `GENERAL_TOOLS` 的 `get_pending_approvals`
- **CLI**: `python scripts/approval_ops.py pending/approve/reject/status/submit`
- **现有工具**: `hr_tools.submit_leave_request` / `finance_tools.submit_expense_report` 可逐步迁移至调用此引擎

---

## 5. 通知中心

### 5.1 设计

所有系统通知统一走 `send_notification()`：

```python
from src.skills.notification import send_notification

send_notification(
    user_id="EMP001",
    type_="system",
    title="工单 TK005 已完成",
    body="你的硬件报修工单已处理完成",
    link_type="ticket",
    link_id="TK005",
)
```

**去重**：同一用户 + 同一标题，5 分钟内不重复发送。

### 5.2 API

| 函数 | 说明 |
|------|------|
| `send_notification()` | 发送通知（带去重） |
| `get_unread_notifications()` | 未读通知列表 |
| `mark_notifications_read()` | 批量标记已读 |
| `send_digest()` | 未读通知摘要 |

---

## 6. 聚合报表

### 6.1 API

| 函数 | 说明 |
|------|------|
| `ticket_daily_report()` | 当日工单：创建数/处理中/完成数 + 按类型/优先级分布 |
| `ticket_weekly_report()` | 周报：7 天趋势 + 当前积压 + 高优先级未解决 |
| `leave_monthly_report()` | 月度请假：按类型/状态/部门聚合 |
| `budget_usage_report()` | 预算使用率：各部门/各类别 + 超 90% 预警 |
| `dashboard_summary()` | 综合仪表盘：待处理工单 + 待审批 + 本月请假天数 |

### 6.2 调用方

- **Agent**: 通过 `GENERAL_TOOLS` 的 `get_dashboard_summary`
- **CLI**: `python scripts/ticket_ops.py report/dashboard`
- **定时任务**: crontab 调用脚本输出 JSON → 推送到企业微信/飞书

---

## 7. 与现有代码的关系

### 7.1 向下兼容

- `src/tools/it_tools.py` 的 `create_ticket()` **保持不变**
- `src/tools/hr_tools.py` 的 `submit_leave_request()` / `approve_leave()` **保持不变**
- 新 workflow 函数是**新增**，不是替换

### 7.2 渐进迁移路径

| 阶段 | 操作 |
|------|------|
| 当前 | skills 作为新层，与 tools 并行运行 |
| 短期 | `hr_tools.submit_leave_request` 内部改为调用 `approval_engine.submit_for_approval` |
| 中期 | 所有审批相关工具统一走 `approval_engine` |
| 长期 | `state_machine.py` 的 leave FSM 可合并到 `approval_engine` |

---

## 8. 测试

```bash
# 工单生命周期
python -c "
from src.skills.ticket_lifecycle import create_ticket_full, process_ticket, complete_ticket
r = create_ticket_full('EMP001', '硬件报修', '测试工单')
print(r['ticket_id'])
r2 = process_ticket(r['ticket_id'], 'EMP005', '开始处理')
print(r2['message'])
r3 = complete_ticket(r['ticket_id'], 'EMP005', '已修复')
print(r3['message'])
"

# 工单报表
python scripts/ticket_ops.py report --type daily

# 审批列表
python scripts/approval_ops.py pending EMP002
```

---

*本文档描述 v1.0 skills 层实现状态。*
