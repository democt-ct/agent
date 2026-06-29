# 03 - Context Engineering

> 学习目标：理解Context的组成，掌握管理Context的核心策略

---

## 1. 什么是Context

Context是**LLM做决策时能看到的全部信息**。

```
Context = System Prompt + User Input + Chat History + Memory + Retrieved Knowledge + Tool Results
```

**核心认知**：Context的质量直接决定输出质量。Agent能力的上限，很大程度上由Context Engineering决定。

---

## 2. Context的组成

```
┌──────────────────────────────────────────────────────┐
│                   Context Window                      │
│                                                       │
│  [System Prompt]      角色定义、行为规则、输出格式     │
│  [User Input]         当前用户消息                    │
│  [Chat History]       历史对话记录                    │
│  [Memory]             Agent积累的状态信息             │
│  [Retrieved Knowledge] RAG检索到的相关文档            │
│  [Tool Results]       工具调用返回的结果              │
│  [Environment]        外部状态（时间、系统信息等）    │
│                                                       │
└──────────────────────────────────────────────────────┘
```

---

## 3. 各部分详解

### System Prompt

定义Agent的角色、能力边界和输出规范。

```python
system_prompt = """
你是一个代码审查助手。

## 职责
- 检查代码的安全漏洞、性能问题和可维护性
- 提供具体的改进建议，附带示例代码

## 规则
- 只评论代码，不讨论无关话题
- 不确定时明确说明，不猜测
- 按严重程度排列问题：critical > warning > suggestion

## 输出格式
返回 JSON，结构：{"issues": [...], "summary": "..."}
"""
```

设计原则：**角色明确、边界清晰、格式固定**。System Prompt是成本最低、效果最稳定的优化手段。

### Chat History

历史对话提供连续性，但会快速消耗Context空间。

```python
chat_history = [
    {"role": "user",      "content": "审查这段登录代码"},
    {"role": "assistant", "content": "发现2个安全问题..."},
    {"role": "user",      "content": "第一个问题怎么修？"},
]
```

问题：**历史越长，占用越多**，直到撑满Context Window。

解决方案：
```
方案1：截断  → 只保留最近N条
方案2：摘要  → 用LLM把早期对话压缩成摘要
方案3：分层  → 近期完整保留，早期只留摘要
```

### Memory

Agent在执行过程中积累的状态，与历史对话不同——它是**提炼后的结构化信息**。

```python
memory = {
    "user_context": {
        "project_lang": "Python",
        "team_style": "Google风格指南",
    },
    "session_progress": {
        "files_reviewed": ["auth.py", "db.py"],
        "open_issues": 3,
    }
}
```

### Retrieved Knowledge（RAG）

从外部知识库检索与当前问题相关的内容，动态注入Context。

```python
user_query = "如何防止SQL注入"
retrieved = vector_db.search(user_query, top_k=3)

# 注入到Context
context_injection = f"""
参考资料：
{format_docs(retrieved)}

用户问题：{user_query}
"""
```

RAG的价值：让LLM访问训练数据之外的知识，同时不需要把整个知识库放进Context。

### Tool Results

工具执行后返回的结果，直接追加到当前轮次的Context中。

```python
tool_results = [
    {
        "tool": "run_tests",
        "input":  {"file": "auth_test.py"},
        "output": {"passed": 8, "failed": 2, "errors": ["..."]},
        "timestamp": "2026-06-26T10:23:00"
    }
]
```

---

## 4. Context Management策略

### 问题：Context空间是有限的

```
128K tokens ≈ 10万字中文，看起来很多，但实际：

System Prompt:      ~2K
工具定义（20个）:   ~8K
历史50轮对话:      ~50K
RAG检索文档:       ~20K
─────────────────────────
剩余可用空间:       ~48K  ← 还要给当前消息和输出用
```

满了就会截断，**截断位置不可控**，可能丢失关键信息。

### 核心策略

**策略1：截断历史**
```python
def truncate_history(history, max_tokens=8000):
    total, result = 0, []
    for msg in reversed(history):
        cost = count_tokens(msg["content"])
        if total + cost > max_tokens:
            break
        total += cost
        result.insert(0, msg)
    return result
```

**策略2：摘要压缩**
```python
def summarize_old_history(history, keep_recent=5):
    recent = history[-keep_recent:]
    old    = history[:-keep_recent]
    if not old:
        return recent
    summary = llm.generate(f"将以下对话压缩为简洁摘要，保留关键信息：\n{old}")
    return [{"role": "system", "content": f"[历史摘要] {summary}"}] + recent
```

**策略3：信息密度优化**

```python
# ❌ 低密度（冗余）
context = "用户说他想写一个Python脚本，他说要处理CSV文件，他说有大概10万行数据..."

# ✅ 高密度（结构化）
context = "任务：Python脚本 | 输入：CSV | 规模：~10万行 | 要求：内存高效"
```

规则：**只放当前任务需要的信息，不放无关信息，重要的放前面。**

---

## 5. 常见错误

| 错误               | 后果                   | 正确做法                 |
| ------------------ | ---------------------- | ------------------------ |
| System Prompt 过长 | 挤占对话空间           | 精简到核心规则           |
| 历史不压缩         | 快速用满Context        | 摘要/截断               |
| 无关信息全塞进去   | 稀释有效信息，降低质量 | 按需注入，保持高密度     |
| 重要信息放在末尾   | LLM注意力可能不够      | 关键内容放在前部         |

---

## 实践任务

**任务1**：打开你项目中一个实际的 system prompt，计算它的 token 数，判断是否有精简空间。

**任务2**：设计一个针对你当前项目的 Context 结构——列出每个区域放什么内容、大概多少 token。

**任务3**：画出 Context Flow 图：
```
用户消息进来 → [如何组装Context] → LLM → 输出
                    ↑
              历史怎么截断？
              Memory怎么注入？
              RAG怎么触发？
```

---

→ [04-Memory体系.md](./04-Memory体系.md)
