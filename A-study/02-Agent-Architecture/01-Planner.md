# 01 - Planner — 任务规划

> 学习目标：理解为什么需要Planner、掌握任务分解和依赖图设计

---

## 1. 为什么需要 Planner

最简单的 Agent 是 `User → LLM → Tool → Output`。但它有一个致命问题：

```
用户："帮我把这个Python项目迁移到TypeScript"

LLM直接调 Tool → 读了一个文件 → 开始翻译 → 
  翻译到一半发现依赖关系没搞清楚 → 
    又回头读更多文件 → 
      上下文已经乱掉了
```

没有 Planner 的 Agent 是**边走边想**，复杂任务必然失控。

```
无 Planner：User → [边走边想] → 混乱 → 可能完成也可能崩溃
有 Planner：User → [先规划后执行] → 有序 → 可控可恢复
```

> **核心认知**：Planner 把「一次复杂的决策」拆成「多次简单的决策」。

---

## 2. Planner 做什么

```python
user_goal = "去成都旅游五天，预算5000元"

plan = planner.decompose(user_goal)

# 输出：Task Graph（任务图）
plan = {
    "goal": "成都五日游，预算5000",
    "tasks": [
        {"id": 1,  "name": "确定出行日期和交通方式",    "depends_on": []},
        {"id": 2,  "name": "预订往返交通（飞机/高铁）", "depends_on": [1]},
        {"id": 3,  "name": "制定每日行程路线",         "depends_on": [1, 6]},
        {"id": 4,  "name": "预订住宿",                  "depends_on": [3]},
        {"id": 5,  "name": "预订景点门票",              "depends_on": [3]},
        {"id": 6,  "name": "查询成都天气和穿衣建议",    "depends_on": [1]},
        {"id": 7,  "name": "制定美食清单",              "depends_on": [3]},
        {"id": 8,  "name": "生成完整行程文档",          "depends_on": [2, 4, 5, 7]},
    ],
    "estimated_cost": 5000
}
```

---

## 3. 任务依赖图

把上面的 plan 画成图：

```
    ┌──────────┐
    │ ① 日期交通 │
    └─────┬──────┘
          │
    ┌─────┼─────────────┐
    │     │             │
    ▼     ▼             ▼
┌───┐ ┌──────┐   ┌──────────┐
│ ② │ │  ⑥   │   │ ③ 行程路线 │
│交通│ │天气穿衣│   └─────┬────┘
└───┘ └──────┘         │
    │              ┌────┼─────┬────┐
    │              │    │     │    │
    │              ▼    ▼     ▼    ▼
    │          ┌───┐ ┌───┐ ┌───┐ ┌───┐
    │          │ ④ │ │ ⑤ │ │ ⑦ │ │...│
    │          │住宿│ │门票│ │美食│ │   │
    │          └───┘ └───┘ └───┘ └───┘
    │              │    │     │
    └──────────────┼────┼─────┘
                   │    │
                   ▼    ▼
               ┌──────────┐
               │ ⑧ 完整文档 │
               └──────────┘
```

**关键信息**：

- ① → ②、⑥、③ 依赖日期确定后才能做
- ③ → ④、⑤、⑦ 依赖路线确定后才能安排
- ⑧ 依赖所有子任务完成
- ② 和 ⑥ 可以并行（没有相互依赖）

> **并行机会**：依赖图中，同一层级的无依赖节点可以并行执行。

---

## 4. 两种规划模式

### ReAct（边走边想）

每步：Thought → Action → Observation。适合简单任务。

```
Thought: 需要先搜索成都五日游攻略
Action:  web_search("成都五日游攻略 2026")
Obs:     返回了10篇攻略...

Thought: 根据攻略，需要先确定日期
Action:  ask_user("你计划几月去？")
Obs:     用户说7月

Thought: 7月是旺季，先查机票价格
Action:  flight_search("北京→成都", "2026-07")
...
```

**优点**：灵活，能根据中间结果调整。
**缺点**：没有全局视野，容易走偏；长任务容易迷路。

### Plan-and-Execute（先规划后执行）

先出完整 Plan → 逐步执行 → 每步后检查是否需要调整。

```python
class PlanAndExecuteAgent:
    def run(self, goal):
        # 阶段1：规划（只做一次）
        plan = self.planner.decompose(goal)
      
        # 阶段2：执行（按依赖顺序）
        completed = set()
        while not plan.all_done():
            # 找到所有依赖已满足的待执行任务
            ready = plan.get_ready_tasks(completed)
          
            for task in ready:
                result = self.execute(task)
                completed.add(task.id)
              
                # 阶段3：检查是否需要重新规划
                if result.requires_replan:
                    plan = self.replan(plan, completed, result)
      
        return self.assemble_output(plan, completed)
```

**优点**：全局视角，有序可控。
**缺点**：初始规划可能不准确，需要支持 replan。

### 什么时候用什么？

| 场景                   | 推荐模式                            |
| ---------------------- | ----------------------------------- |
| 简单问答、单步查询     | ReAct                               |
| 多步骤但步骤固定       | Plan-and-Execute                    |
| 探索性任务、信息不完整 | ReAct（边走边收集信息）             |
| 企业业务流程           | Plan-and-Execute + HITL（人机协同） |

---

## 5. Planner 的核心挑战

### 挑战1：规划粒度

```
太粗 → 每一步还是太大，LLM 仍然难决策
太细 → 步骤过多，管理成本超过收益

经验：每个子任务应该是一个明确的 action，一步就能完成。
```

### 挑战2：Replan

执行过程中发现规划不对，需要重新规划。

```python
def check_and_replan(plan, completed, latest_result):
    if latest_result.status == "BLOCKED":
        # 当前步骤被阻塞，调整后续计划
        return planner.replan(plan, completed, 
                              reason=latest_result.block_reason)
  
    if latest_result.status == "NEW_INFO":
        # 发现了新信息，可能需要调整
        # 例如：搜索发现某个景点关闭了，需要改路线
        return planner.replan(plan, completed,
                              new_info=latest_result.data)
  
    return plan  # 继续原计划
```

### 挑战3：用户意图理解

```
用户："我想去成都"         → 目标明确
用户："想出去走走"         → 目标模糊，需要多轮澄清
用户："上次那个方案还行"   → 依赖历史记忆
```

好的 Planner 在分解之前先做目标理解（回顾 01-Agent-Foundations 的生命周期）。

---

## 6. 最简 Planner 实现

```python
from dataclasses import dataclass, field
from typing import List, Set

@dataclass
class Task:
    id: int
    name: str
    depends_on: List[int] = field(default_factory=list)
    status: str = "pending"  # pending | running | done | failed

class Planner:
    def decompose(self, goal: str, context: dict) -> List[Task]:
        """用LLM把目标分解为任务图"""
        prompt = f"""
        将以下目标分解为子任务，返回JSON。
      
        目标：{goal}
        已有上下文：{context}
      
        规则：
        - 每个子任务必须是一个明确的、可执行的动作
        - 标注每个任务的依赖关系（任务ID列表）
        - 粒度：一个工具调用能完成的程度
      
        格式：[{{"id": 1, "name": "...", "depends_on": []}}, ...]
        """
        response = llm.generate(prompt)
        return self._parse_tasks(response)
  
    def get_ready_tasks(self, tasks: List[Task], 
                        completed: Set[int]) -> List[Task]:
        """找出所有依赖已满足的待执行任务"""
        ready = []
        for task in tasks:
            if task.status != "pending":
                continue
            if all(dep in completed for dep in task.depends_on):
                ready.append(task)
        return ready
  
    def replan(self, tasks: List[Task], completed: Set[int],
               reason: str) -> List[Task]:
        """根据新情况重新规划未完成部分"""
        pending = [t for t in tasks 
                   if t.id not in completed and t.status != "failed"]
        pending_ids = {t.id for t in pending}
      
        # 用 LLM 重新规划 pending 部分，保留已完成的
        prompt = f"""
        以下任务因「{reason}」需要重新规划。
      
        已完成的任务（不可更改）：
        {[t for t in tasks if t.id in completed]}
      
        需要重新规划的任务：
        {pending}
      
        返回新的任务列表（JSON，保持相同的 id 和 depends_on 结构），
        已完成的任务原样保留。
        """
        new_pending = llm.generate_json(prompt)
      
        # 合并：已完成部分 + 新规划部分
        done_tasks = [t for t in tasks if t.id in completed]
        return done_tasks + self._parse_tasks(new_pending)
  
    def get_ready_tasks(self, tasks: List[Task],
                        completed: Set[int]) -> List[Task]:
        """拓扑排序：找出所有依赖已满足的待执行任务
      
        本质是做一轮拓扑遍历——检查每个 pending task 的
        depends_on 是否全部在 completed 集合中。
        没有相互依赖的任务可以安全并行执行。
        """
```

---

## 7. 常见错误

| 错误             | 后果                     | 正确做法                   |
| ---------------- | ------------------------ | -------------------------- |
| 所有任务用 ReAct | 复杂任务迷失方向         | 长流程用 Plan-Execute      |
| 规划过细         | Token 浪费在管理上       | 一步 = 一个工具调用        |
| 不设依赖         | 出现顺序错乱             | 每个任务标注 depends_on    |
| 从不 replan      | 中间出错后继续错         | 关键节点检查，异常时重规划 |
| 规划不存下来     | 调试时不知道当时怎么想的 | Plan 写入 Memory           |

---

## 实践任务

**任务1**：把「用户想去成都旅游五天」手动分解成至少8个子任务，标注依赖关系，画出依赖图。

**任务2**：分析你之前做过的 Agent 项目——它有没有 Planner？如果没有，加入 Planner 会改变什么？

**任务3**：设计一个 replan 触发条件列表——什么情况下你的旅游 Agent 需要重新规划？

```
场景：用户已经订了机票，突然说"预算从5000降到3000"
→ 哪些已完成的任务不受影响？
→ 哪些待执行的任务需要调整？
→ 如何做最小幅度的调整，而不是全盘重来？
```

---

→ [02-Workflow.md](./02-Workflow.md)
