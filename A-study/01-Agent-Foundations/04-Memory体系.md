、

# 04 - Memory体系

> 学习目标：理解Agent的记忆层级，学会为你的Agent设计Memory架构

---

## 1. 为什么需要Memory

没有Memory的Agent每次都从零开始；有Memory的Agent能积累状态、学习经验。

```
无Memory：
  用户："用Python，不用注释"
  Agent：[写了有注释的代码]  ← 忘了偏好

有Memory：
  用户："用Python，不用注释"
  Agent：[写了无注释的代码]
  （下次）用户："再写一个类似的"
  Agent：[还是Python，还是无注释]  ← 记住了
```

---

## 2. Memory的四个层级

```
┌─────────────────────────────────────────────────────┐
│  Working Memory  （工作记忆）                        │
│  当前Context内容 · 生命周期：本次推理 · 存储：内存   │
├─────────────────────────────────────────────────────┤
│  Session Memory  （会话记忆）                        │
│  本次会话状态   · 生命周期：会话结束 · 存储：Redis   │
├─────────────────────────────────────────────────────┤
│  Long-term Memory（长期记忆）                        │
│  用户偏好/历史  · 生命周期：永久    · 存储：数据库   │
├─────────────────────────────────────────────────────┤
│  Semantic Memory （语义记忆）                        │
│  结构化知识库   · 按需检索         · 存储：向量DB    │
└─────────────────────────────────────────────────────┘
         + Episodic Memory：历史经验，用于改进决策
```

---

## 3. 各层详解

### Working Memory（工作记忆）

就是当前的Context Window内容，容量受限，每次推理结束即清空。

```python
working_memory = {
    "system_prompt":  "你是代码审查助手...",
    "chat_history":   [...],        # 最近几轮对话
    "current_task":   "审查 auth.py",
    "tool_results":   [...]         # 本轮工具调用结果
}
# 容量限制由Context Window决定
# 超出就必须压缩或截断
```

### Session Memory（会话记忆）

跨轮次保持、会话结束后过期。典型存储：Redis。

```python
session = {
    "session_id":   "sess_abc123",
    "user_id":      "u_456",
    "summary":      "用户在审查一个FastAPI项目的鉴权模块",
    "progress": {
        "done":     ["auth.py", "models/user.py"],
        "current":  "middleware/auth_middleware.py",
        "pending":  ["tests/"]
    },
    "accumulated": {
        "issues_found": 7,
        "user_style":   "Google风格，偏好类型注解"
    }
}
# TTL: 会话结束后1小时自动过期
```

### Long-term Memory（长期记忆）

跨会话持久化，存用户偏好、历史总结等高价值信息。

```python
long_term = {
    "user_id": "u_456",
    "profile": {
        "preferred_lang":   "Python",
        "code_style":       "Google风格",
        "expertise_level":  "senior"
    },
    "history_summary": [
        {"project": "FastAPI鉴权", "outcome": "发现7个安全漏洞，用户接受了5个建议"},
        {"project": "数据库优化",  "outcome": "提供了3个索引建议，用户说太激进了"}
    ]
}
# 写入条件：用户明确的偏好 + 可复用的经验
```

### Semantic Memory（语义记忆）

结构化的知识库，通过向量相似度检索相关内容。

```python
# 知识库示例内容
knowledge_base = [
    {"topic": "SQL注入防护",      "content": "使用参数化查询..."},
    {"topic": "JWT安全最佳实践",  "content": "设置合理过期时间，避免敏感信息入payload..."},
    {"topic": "Python性能优化",   "content": "使用__slots__减少内存..."},
]

# 检索
query = "如何防止越权访问"
relevant = vector_db.search(query, top_k=3)
# → 返回最相关的3条知识
```

### Episodic Memory（情景记忆）

记录具体经历和教训，用于改进未来决策。

```python
episodes = [
    {
        "situation": "用户要求重构，但没说清楚范围",
        "action":    "直接重构了整个模块",
        "outcome":   "用户说改多了，只需要改函数签名",
        "lesson":    "重构前先确认范围，展示diff让用户确认"
    },
    {
        "situation": "发现严重安全漏洞",
        "action":    "在问题列表里和普通问题放一起",
        "outcome":   "用户没重视，后来出了生产故障",
        "lesson":    "严重安全问题要单独高亮，不能混在列表里"
    }
]
```

---

## 4. Memory操作

```python
# 写入
def write(memory_type, key, value, user_id):
    match memory_type:
        case "session":   redis.hset(f"s:{user_id}", key, value, ex=3600)
        case "long_term": db.update({"user_id": user_id}, {"$set": {key: value}})
        case "semantic":  vector_db.upsert(key, value)

# 读取
def read(memory_type, key, user_id):
    match memory_type:
        case "session":   return redis.hget(f"s:{user_id}", key)
        case "long_term": return db.find_one({"user_id": user_id}).get(key)
        case "semantic":  return vector_db.search(key)

# 压缩工作记忆（防止Working Memory溢出）
def compress_working(history, max_tokens=4000):
    if count_tokens(history) <= max_tokens:
        return history
    # 保留最近5条，其余摘要
    recent  = history[-5:]
    summary = llm.summarize(history[:-5])
    return [{"role": "system", "content": f"[早期对话摘要] {summary}"}] + recent
```

---

## 5. Memory设计原则

| 原则               | 说明                                     |
| ------------------ | ---------------------------------------- |
| **分层**     | 不同时效、不同重要性的信息放不同层       |
| **按需加载** | 每次只拉取当前任务需要的记忆，不全量加载 |
| **写入门槛** | 不是所有信息都值得写入长期记忆           |
| **及时压缩** | Working Memory快满时主动压缩，不要等溢出 |
| **隐私保护** | 用户敏感信息加密存储，写入前脱敏         |

**什么值得写入长期记忆？**

- 用户明确表达的偏好（"我不喜欢X风格"）
- 可复用的经验教训
- 重复出现的模式

---

## 实践任务

**任务1**：为你当前在做的项目设计Memory架构——每层存什么、用什么技术栈、TTL是多少？

**任务2**：实现一个最简Session Memory：

```python
import redis

class SessionMemory:
    def __init__(self, session_id, ttl=3600):
        self.r   = redis.Redis()
        self.key = f"session:{session_id}"
        self.ttl = ttl

    def save(self, key, value):
        self.r.hset(self.key, key, str(value))
        self.r.expire(self.key, self.ttl)

    def load(self, key):
        return self.r.hget(self.key, key)
```

**任务3**：规划你Agent的Memory生命周期：

```
100轮对话 → Working Memory 什么时候压缩？
用户换设备 → Session Memory 怎么恢复？
用户明说了不喜欢某种写法 → 写入哪层？何时更新？
```

---

→ [05-实践：设计你的第一个Agent.md](./05-实践：设计你的第一个Agent.md)
