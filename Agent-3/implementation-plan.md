# 实现规格书 — 技术参考

> 每个模块的接口契约、函数签名、数据结构。  
> 按 Step 顺序组织，不按角色。

---

## §0 公共约定

### 0.1 引包规范

```python
from src.protocol.types import AgentRequest, AgentResponse
from src.rag.knowledge_base import KnowledgeBase
```

### 0.2 项目目录结构

```
enterprise-multi-agent/
├── pyproject.toml
├── .env.example / .gitignore / README.md
├── docs/
│   ├── development-steps.md
│   └── implementation-plan.md          ← 本文档
├── src/
│   ├── main.py                         ✅ Step 1
│   ├── protocol/
│   │   ├── types.py                    ✅ Step 1
│   │   ├── handoff.py                  ✅ Step 1
│   │   └── errors.py                   ✅ Step 1
│   ├── agents/
│   │   ├── base_agent.py               ✅ Step 2
│   │   ├── orchestrator.py             ✅ Step 3
│   │   ├── hr_agent.py                 ⬜ Step 5
│   │   ├── it_agent.py                 ⬜ Step 5
│   │   └── legal_agent.py              ⬜ Step 5
│   ├── rag/                            ⬜ Step 4
│   │   ├── loader.py
│   │   ├── chunker.py
│   │   ├── embedder.py
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   └── knowledge_base.py
│   ├── tools/
│   │   ├── base.py                     ✅ Step 1
│   │   ├── hr_tools.py                 ⬜ Step 5
│   │   ├── it_tools.py                 ⬜ Step 5
│   │   └── legal_tools.py              ⬜ Step 5
│   └── frontend/
│       └── app.py                      ⬜ Step 7
├── data/
│   ├── hr/                             ⬜ Step 4
│   ├── it/                             ⬜ Step 4
│   └── legal/                          ⬜ Step 4
├── tests/                              ⬜ Step 6
└── scripts/
    ├── test_base_agent.py              ✅ Step 2
    └── test_routing.py                 ✅ Step 3
```

---

## §1 Protocol 层（Step 1 · 已完成）

### types.py

```python
@dataclass
class AgentRequest:
    query: str
    agent_name: str
    conversation_history: list[dict] = field(default_factory=list)
    extracted_entities: dict = field(default_factory=dict)
    handoff_context: dict | None = None
    max_tool_calls: int = 5
    temperature: float = 0.3

@dataclass
class AgentResponse:
    agent_name: str
    answer: str
    confidence: float
    tool_calls: list[dict] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    handoff_suggestions: list[dict] | None = None
    status: str = "success"     # "success" | "partial" | "failed"
    error: str | None = None
    processing_time_ms: int = 0
    tokens_used: int = 0

@dataclass
class AgentRegistration:
    agent_name: str
    display_name: str
    description: str
    tool_descriptions: list[str] = field(default_factory=list)
```

### handoff.py

```python
def build_handoff(from_agent: str, response: AgentResponse,
                  shared_context: dict) -> dict:
    """用上一个 Agent 的输出构造交割上下文"""

def merge_results(responses: list[AgentResponse]) -> str:
    """汇总多个 Agent 的回答"""
```

### errors.py

```python
class AgentError(Exception): ...
class RetryableError(AgentError): ...
class MaxRetriesExceeded(AgentError): ...
class TimeoutError(AgentError): ...

def with_retry(max_retries=3, base_delay=1.0, backoff=2.0):
    """指数退避重试装饰器"""
```

---

## §2 BaseAgent ReAct 引擎（Step 2 · 已完成）

```python
class BaseAgent:
    def __init__(self, name, tools, kb, client, model="deepseek-v4-flash")

    def run(self, request: AgentRequest) -> AgentResponse:
        # 计时 → _react_loop() → 填充 AgentResponse

    def _react_loop(self, request, total_tokens, tool_call_log)
        # ① kb.query(query, top_k=10)
        # ② _build_system_prompt(query, retrieved, handoff_context)
        # ③ messages = [system] + history + [user]
        # ④ for _ in range(max_tool_calls):
        #      LLM 返回 content → return
        #      LLM 返回 tool_calls → _execute_tool → 塞回对话
        # ⑤ 强制生成最终回答

    def _build_system_prompt(self, query, retrieved, handoff_context=None) -> str:
        # 角色定义 + 交割上下文 + RAG 检索结果 → 三段式 prompt

    def _execute_tool(self, name, arguments) -> dict:
        # 从 self.tools 查找 → 执行 → 返回结果
```

---

## §3 Orchestrator 路由引擎（Step 3 · 已完成）

### AGENT_REGISTRY

```python
AGENT_REGISTRY = {
    "hr_agent": AgentRegistration(
        agent_name="hr_agent",
        display_name="HR 专家",
        description="负责回答人事制度、考勤、请假...",
        tool_descriptions=["get_leave_balance", "submit_leave_request"],
    ),
    "it_agent": AgentRegistration(display_name="IT 专家", ...),
    "legal_agent": AgentRegistration(display_name="法务专家", ...),
    "fallback": AgentRegistration(display_name="通用助手", ...),
}
```

### 路由链路

```
route(query):
  ① _is_greeting(query)        → fallback
  ② _keyword_match(query)      → {primary, secondary} or None
  ③ _llm_route(query)          → {primary, secondary, confidence}
```

### 关键词规则

```python
KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["请假","年假","考勤","工资",...], "hr_agent"),
    (["报修","蓝屏","vpn","密码",...], "it_agent"),
    (["合同","合规","保密",...], "legal_agent"),
]
```

决策顺序：数量差异 → 位置优先级 → LLM 兜底

### LLM 路由 Prompt

```
系统：你是一个精确的问题路由专家。
专家列表：
- hr_agent: 人事制度、考勤、请假、薪酬...
- it_agent: 设备报修、工单、软件...
- legal_agent: 合同、合规、数据保护...
- fallback: 不属于以上任何领域

输出 JSON: {"primary":"agent_name","secondary":"agent_name|null","confidence":0.0-1.0}
```

---

## §4 RAG 管线（Step 4 · 待实现）

### KnowledgeBase 对外接口

```python
class KnowledgeBase:
    def __init__(
        self,
        kb_name: str,
        docs_dir: str,
        embedding_model: str = "text-embedding-3-small",
        chunk_size: int = 500,
        chunk_overlap: int = 80,
    ):
        ...

    def build_index(self) -> None:
        """第一次或文档变更后：加载 → 分块 → 向量化 → 存 Chroma"""
        ...

    def load_index(self) -> None:
        """重启时加载已有索引"""
        ...

    def query(self, query: str, top_k: int = 10) -> list[dict]:
        """检索并重排序。

        Returns:
            [{"content": "...", "source": "年假制度.md",
              "chunk_index": 3, "score": 0.94}, ...]
        """
```

### 各子模块职责

| 模块 | 功能 | 关键实现 |
|------|------|---------|
| `loader.py` | 加载 PDF/MD/TXT/DOCX | pypdf, python-docx |
| `chunker.py` | 分块 | LangChain RecursiveCharacterTextSplitter |
| `embedder.py` | 向量化 | OpenAI text-embedding-3-small |
| `retriever.py` | 混合检索 | 向量余弦相似度 + BM25 → RRF 融合 |
| `reranker.py` | 重排序 | Cohere Rerank v2 |
| `knowledge_base.py` | 封装 | build_index / load_index / query |

### retriever.py 算法

```python
def hybrid_search(query, chunks, embeddings, vector_weight=0.7):
    """RRF 融合：
    score(chunk) = 1/(60 + rank_vector(chunk))
                 + 1/(60 + rank_bm25(chunk))
    """
```

---

## §5 Agent + 工具（Step 5 · 待实现）

### 工具定义

#### HR 工具

```python
HR_TOOLS = [
    ToolDef(
        name="get_leave_balance",
        description="查询员工假期余额（年假和病假）",
        parameters={
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
        },
        implementation=get_leave_balance_mock,
    ),
    ToolDef(
        name="submit_leave_request",
        description="提交请假申请。输入员工ID、假期类型、起止日期、理由。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "leave_type": {"type": "string", "enum": ["annual", "sick", "personal"]},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["user_id", "leave_type", "start_date", "end_date"],
        },
        implementation=submit_leave_request_mock,
    ),
]
```

#### IT 工具

```python
IT_TOOLS = [
    ToolDef(name="check_ticket_status", ...),
    ToolDef(name="create_ticket", ...),
    ToolDef(name="check_device_inventory", ...),
]
```

#### 法务工具

```python
LEGAL_TOOLS = [
    ToolDef(name="search_contract", ...),
    ToolDef(name="check_compliance", ...),
]
```

### Agent 类

```python
class HRAgent(BaseAgent):
    def __init__(self, client, kb):
        super().__init__(
            name="HR 专家",
            tools=HR_TOOLS,
            kb=kb,
            client=client,
        )

class ITAgent(BaseAgent):
    def __init__(self, client, kb):
        super().__init__(
            name="IT 专家",
            tools=IT_TOOLS,
            kb=kb,
            client=client,
        )

class LegalAgent(BaseAgent):
    def __init__(self, client, kb):
        super().__init__(
            name="法务专家",
            tools=LEGAL_TOOLS,
            kb=kb,
            client=client,
        )
```

---

## §6 RAG 知识库文档（Step 4 · 待创建）

### HR 知识库（data/hr/）

| 文件 | 内容要点 |
|------|---------|
| `年假管理制度.md` | 工龄分级、年假天数、结转上限、申请流程 |
| `考勤政策.md` | 上下班时间、迟到早退处理、外勤打卡 |
| `薪酬福利说明.md` | 工资结构、社保公积金比例、年终奖 |
| `请假审批流程.md` | 各类假的申请方式、审批人、时效 |
| `病假和医疗期规定.md` | 病假工资比例、医疗期计算、证明要求 |

### IT 知识库（data/it/）

| 文件 | 内容要点 |
|------|---------|
| `设备申领流程.md` | 申请条件、审批层级、到货时间 |
| `报修指南.md` | 报修方式、故障分类、响应时效 |
| `软件安装申请.md` | 软件白名单、安装权限、常见问题 |
| `密码和账号管理.md` | 密码重置、双因素认证、账号锁定 |
| `网络和VPN配置.md` | VPN 安装步骤、网络故障排查 |

### 法务知识库（data/legal/）

| 文件 | 内容要点 |
|------|---------|
| `数据保护条例.md` | 个人信息保护、数据跨境、存储期限 |
| `合同审批流程.md` | 合同类型、审批权限、签约流程 |
| `保密协议说明.md` | 保密义务、违约金、竞业限制 |
| `合规检查清单.md` | 常规合规项、检查频率、违规处理 |
| `知识产权政策.md` | 职务作品归属、专利申请、商标保护 |

---

## §7 评估体系（Step 7 · 待实现）

### 测试集格式

```json
[
  {
    "id": "test-001",
    "query": "我今年还剩几天年假？",
    "expected_route": "hr_agent",
    "expected_tool": "get_leave_balance",
    "expected_answer_contains": ["年假", "天"],
    "note": "单 Agent 简单路由"
  }
]
```

### 评估指标

```python
# eval.py 输出：
# 1. 路由准确率 = 正确路由次数 / 总数
# 2. 工具调用准确率 = 正确调用次数 / 应调用次数
# 3. RAG 命中率 = 基于检索片段 / 总数
# 4. 端到端成功率 = 回答合格 / 总数
```

---

## §8 LLM 调用参数

| 场景 | model | temperature | 说明 |
|------|-------|-------------|------|
| Agent 回答问题 | deepseek-v4-flash | 0.3 | 有创造性但不发散 |
| Orchestrator 路由 | deepseek-v4-flash | 0.0 | 贪婪，路由要稳定 |
| 重写检索 query | deepseek-v4-flash | 0.1 | 轻微变化 |

---

## §9 环境配置

### .env

```
DEEPSEEK_API_KEY=sk-xxx
COHERE_API_KEY=your-cohere-key-here
```

### 依赖

```
openai>=1.50 (兼容 DeepSeek)
langgraph>=0.2
chromadb>=0.6
langchain-text-splitters>=0.3
pypdf>=5
python-docx>=1
rank-bm25>=0.2
cohere>=5
python-dotenv>=1
streamlit>=1.40
click>=8
```

---

*本文档是技术参考，开发步骤见 [`docs/development-steps.md`](development-steps.md)。*
