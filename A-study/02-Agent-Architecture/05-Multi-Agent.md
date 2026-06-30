# 05 - Multi-Agent — 多智能体

> 学习目标：理解什么时候需要 Multi-Agent、掌握协作模式，更重要的是——知道什么时候不该用

---

## 1. 最重要的认知

```
⚠️ 不要为了 Multi-Agent 而 Multi-Agent。

每增加一个 Agent：
  - 延迟 +1 轮 LLM 调用
  - 出错概率 +1 个环节
  - 调试难度 ×2
  - Token 消耗 +N

一个 Agent 能解决的问题，不要用两个。
```

**什么时候真的需要 Multi-Agent？**

| 场景                   | 是否适合 Multi-Agent | 原因                                    |
| ---------------------- | -------------------- | --------------------------------------- |
| 复杂任务可自然分工     | ✅                   | 搜索/编码/分析 天然不同                 |
| 需要不同 System Prompt | ✅                   | 不同角色需要不同行为规则                |
| 需要不同工具集         | ✅                   | 浏览器 Agent vs 代码 Agent 工具完全不同 |
| 想提升准确率           | ❌                   | 更好的 Prompt 比更多 Agent 有效         |
| 看起来"更高级"         | ❌                   | 错误理由                                |
| 简单线性任务           | ❌                   | 一个 Agent + 好的 Planner 足够          |

---

## 2. 三种 Multi-Agent 协作模式

### 模式 1：Orchestrator + Workers（主从模式）

```
User → Orchestrator ─→ Worker A（搜索）
                    ├→ Worker B（编码）
                    ├→ Worker C（分析）
                    └→ Worker D（写作）
                            │
                    Orchestrator ← 汇总 ─┘
                            │
                         Output
```

Orchestrator 负责分解、分配、汇总。Worker 只做自己擅长的事。

```python
class Orchestrator:
    def __init__(self):
        self.workers = {
            "researcher": ResearcherAgent(),
            "coder":      CoderAgent(),
            "analyst":    AnalystAgent(),
            "writer":     WriterAgent(),
        }
  
    def handle(self, user_input: str, context: dict):
        # 1. 决定需要哪些 Worker
        plan = self.plan(user_input)
      
        # 2. 并行或串行调用 Worker
        results = {}
        for task in plan["tasks"]:
            worker = self.workers[task["worker"]]
            results[task["id"]] = worker.execute(task, context)
      
        # 3. 汇总结果
        return self.synthesize(results, user_input)
  
    def plan(self, user_input: str):
        """决定任务分配"""
        prompt = f"""
        用户需求：{user_input}
      
        可用的 Worker：
        - researcher: 搜索信息、查找资料
        - coder: 编写代码、运行分析
        - analyst: 数据分析、生成洞察
        - writer: 撰写文档、生成报告
      
        将任务分解，返回 JSON：
        [{{"id": 1, "worker": "researcher", "task": "..."}}, ...]
        """
        return llm.generate_json(prompt)

class ResearcherAgent:
    def execute(self, task: dict, context: dict):
        # 这个 Agent 只有搜索相关工具
        return self.llm.generate(
            system="你是信息搜集专家，只负责搜索和整理信息。",
            tools=["web_search", "news_search"],
            prompt=task["task"]
        )

class CoderAgent:
    def execute(self, task: dict, context: dict):
        # 这个 Agent 只有代码相关工具
        return self.llm.generate(
            system="你是编程专家，只负责编写和执行代码。输出代码和运行结果。",
            tools=["write_code", "run_code", "search_docs"],
            prompt=task["task"]
        )
```

### 模式 2：Peer-to-Peer（对等协作）

```
Agent A ⇄ Agent B ⇄ Agent C

没有中央调度，每个 Agent 自主决定何时与其他 Agent 通信。
```

```python
class PeerAgent:
    def __init__(self, name: str, role: str, tools: list):
        self.name = name
        self.role = role
        self.tools = tools
        self.peers: Dict[str, 'PeerAgent'] = {}
  
    def connect(self, peer: 'PeerAgent'):
        self.peers[peer.name] = peer
  
    def execute(self, task: dict, conversation: list):
        """执行任务，可能请求其他 Agent 帮助"""
        prompt = f"""
        你是 {self.name}，角色：{self.role}
      
        可用工具：{self.tools}
        可请求帮助的同事：{list(self.peers.keys())}
      
        当前任务：{task}
        当前进展：{conversation}
      
        决定下一步：
        1. 使用工具自己完成
        2. 请求某个同事帮助 → 输出 "HELP:<同事名>:<请求内容>"
        3. 任务完成 → 输出 "DONE:<结果>"
        """
      
        response = llm.generate(prompt)
      
        if response.startswith("HELP:"):
            _, peer_name, request = response.split(":", 2)
            peer_result = self.peers[peer_name].execute(
                {"task": request}, conversation
            )
            # 拿到帮助后继续
            return self.execute(task, conversation + [peer_result])
      
        return response
```

> ⚠️ Peer-to-Peer 灵活但难调试。通信模式可能变成"无限对话"。生产环境建议用 Orchestrator 模式。

### 模式 3：Debate / Review（辩论/审查）

```
Agent A（提案）→ Agent B（审查）→ Agent A（修改）→ Agent C（终审）→ Output
```

适合高风险场景：代码安全审查、合同审核、医疗建议。

```python
class ReviewPipeline:
    def __init__(self):
        self.proposer = ProposerAgent()   # 生成方案
        self.reviewer = ReviewerAgent()   # 挑剔找问题
        self.approver = ApproverAgent()   # 最终裁决
  
    def run(self, task: str, max_rounds: int = 3):
        proposal = self.proposer.generate(task)
      
        for round_num in range(max_rounds):
            # Review 当前提案
            feedback = self.reviewer.review(proposal, task)
          
            if feedback["approved"]:
                return proposal
          
            # 根据反馈修改
            proposal = self.proposer.revise(proposal, feedback)
      
        # 达到最大轮次，最终裁决
        return self.approver.final_decision(proposal, task)


class ReviewerAgent:
    def review(self, proposal: str, original_task: str) -> dict:
        prompt = f"""
        严格审查以下方案，找出所有问题。
      
        原始需求：{original_task}
        方案：{proposal}
      
        检查项：
        - 是否满足所有需求？
        - 有没有安全隐患？
        - 有没有遗漏的边界情况？
        - 是否选择了最优方案？
      
        返回 JSON：
        {{"approved": false, "issues": ["问题1", ...], "suggestions": ["建议1", ...]}}
        """
        return llm.generate_json(prompt)
```

---

## 3. 旅游 Agent 的 Multi-Agent 设计

```
用户："帮我规划成都五日游"

Orchestrator
    │
    ├──→ PlannerAgent    → 制定行程框架
    │       ↓
    ├──→ ResearcherAgent → 搜索景点、天气、交通
    │       ↓
    ├──→ BudgetAgent     → 计算预算、比价
    │       ↓
    ├──→ OptimizerAgent  → 优化路线、调顺序
    │       ↓
    └──→ WriterAgent     → 生成最终行程文档
```

但仔细想想——这个场景真的需要5个 Agent 吗？

```
可能只需要 1 个 Agent + 好的 Planner：

一个 Agent 按顺序：
  ① 搜索攻略（web_search tool）
  ② 根据攻略制定行程（LLM 推理）
  ③ 比价（web_search tool + LLM 比价）
  ④ 优化路线（LLM 推理）
  ⑤ 生成文档（LLM 生成）

→ 延迟更低、更简单、更好调试
```

> **判断标准**：这些"Agent"是否真的需要不同的 System Prompt 和不同的 Tool Set？如果不是，用一个 Agent + Planner 就够了。

---

## 4. Multi-Agent 的通信协议

Agent 之间怎么说话？两种方式：

### 结构化消息

```python
@dataclass
class AgentMessage:
    sender: str
    receiver: str
    msg_type: str        # "task" | "result" | "question" | "error"
    content: Any
    correlation_id: str  # 关联到原始任务
  
    def to_prompt(self) -> str:
        return f"[{self.sender} → {self.receiver}] {self.msg_type}: {self.content}"
```

### 共享黑板（Blackboard）

所有 Agent 读写同一个共享空间，而不是直接对话。

```python
class Blackboard:
    """所有 Agent 共享的工作空间"""
    def __init__(self):
        self.data: Dict[str, Any] = {}
  
    def write(self, agent_name: str, key: str, value: Any):
        self.data[f"{agent_name}:{key}"] = value
  
    def read(self, key_pattern: str = None) -> dict:
        if key_pattern:
            return {k: v for k, v in self.data.items() 
                    if key_pattern in k}
        return dict(self.data)
  
    def clear(self):
        self.data = {}


# 使用
blackboard = Blackboard()

# Researcher 搜到信息后写到黑板
blackboard.write("researcher", "chengdu_weather", 
    {"temp": "28-35°C", "rain": "偶有阵雨"})

# Planner 读黑板上的天气信息来制定行程
weather = blackboard.read("chengdu_weather")
# → {"researcher:chengdu_weather": {"temp": "28-35°C", ...}}
```

> 黑板模式的好处：Agent 之间解耦、易于调试（可以直接看黑板内容）、自然支持并行。

---

## 5. 常见陷阱

### 陷阱 1：Agent 过多

```
❌ 给旅游 Agent 设了 8 个 Agent：
   FlightAgent, HotelAgent, WeatherAgent, RestaurantAgent,
   AttractionAgent, BudgetAgent, RouteAgent, WriterAgent

→ 8 次 LLM 调用 × 每次 2-5 秒 = 16-40 秒延迟
→ 每个 Agent 的 System Prompt + 工具定义 = Context 膨胀
→ 一个 Agent 出错，整个流程乱掉
```

### 陷阱 2：循环通信

```python
# Agent A: 这个方案需要 B 确认
# Agent B: 这个方案需要 A 先改
# Agent A: 改了但 B 还是不满意
# ... 永远循环

# 解决方案：
MAX_ROUNDS = 3
ROUND_DETECTOR = "检测到重复请求，强制终止并输出当前结果"
```

### 陷阱 3：隐性依赖

```
Agent A 等 Agent B 的结果，Agent B 在等 Agent C，
但 Agent C 在等用户输入，用户不知道在等什么。

→ 每个等待点都要可视化给用户
→ "正在搜索景点信息... ✓"
→ "正在比价酒店... ⏳"
→ "需要您选择：A酒店 vs B酒店"
```

---

## 6. 常见错误

| 错误                   | 后果                     | 正确做法                                  |
| ---------------------- | ------------------------ | ----------------------------------------- |
| 简单任务用 Multi-Agent | 延迟高、成本高、没收益   | 一个 Agent + 好的 Planner                 |
| 没有最大轮次限制       | Agent 之间无限对话       | 所有协作设 MAX_ROUNDS                     |
| Worker 之间职责重叠    | 两个 Agent 做了一样的事  | 每个 Worker 的 System Prompt 职责边界清晰 |
| 缺少超时               | 一个 Worker 卡住拖垮全局 | 每个 Worker 设独立超时                    |
| 串行等待               | 明明可以并行却在排队     | 识别无依赖 Worker 并行执行                |

---

## 实践任务

**任务1**：分析你的旅游 Agent——哪些环节用 Multi-Agent 真的比单 Agent + Planner 更好？画两种方案的对比图。

**任务2**：实现一个最简的 Orchestrator + 2 Workers（Researcher + Writer），完成一个简单任务："帮我研究一下成都必去的三个景点，写一段推荐"。对比单 Agent 和 Multi-Agent 的延迟和结果质量。

**任务3**：阅读 OpenHands 或 CrewAI 的源码，画出它们的 Multi-Agent 架构图。关注：Agent 之间怎么通信？任务怎么分配？出错怎么处理？

---

→ [06-Human-in-the-Loop.md](./06-Human-in-the-Loop.md)
