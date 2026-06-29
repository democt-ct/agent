# 04 - Router — 智能路由

> 学习目标：理解 Router 在 Agent 架构中的角色，掌握意图分类和工具分发设计

---

## 1. 什么是 Router

Router 是 Agent 的"调度员"——把用户的请求分发到正确的处理器。

```
                          ┌──→ Browser Agent（打开网页、截图）
                          │
User: "帮我比价三款手机" → Router ──→ Search Agent（搜索商品信息）
                          │
                          ├──→ Code Agent（写比价脚本）
                          │
                          └──→ Vision Agent（识别图片中的型号）
```

没有 Router 的 Agent：所有工具定义塞进一个 Prompt → Context 占用巨大 → LLM 在 50 个工具中选 → 选错概率高。

有 Router：先分类 → 只给 LLM 相关工具 → Context 精简 → 准确率提升。

---

## 2. Router 的四个层次

```
Layer 1: Intent Classification    意图分类（这是什么类问题）
    ↓
Layer 2: Tool Selection           工具选择（用哪个工具）
    ↓
Layer 3: Parameter Resolution     参数解析（工具的入参是什么）
    ↓
Layer 4: Fallback / Escalation    降级/升级（工具不可用时怎么办）
```

---

## 3. Layer 1 — 意图分类

```python
from enum import Enum

class Intent(Enum):
    WEB_SEARCH    = "web_search"      # 搜索信息
    BROWSER       = "browser"         # 浏览器操作
    CODE          = "code"            # 编写/运行代码
    DATA_ANALYSIS = "data_analysis"   # 数据分析
    BOOKING       = "booking"         # 预订（机票/酒店）
    PLANNING      = "planning"        # 行程规划
    CHITCHAT      = "chitchat"        # 闲聊
    UNKNOWN       = "unknown"         # 无法分类

class IntentRouter:
    INTENT_PROMPT = """
    将用户消息分类为以下意图之一：
    
    意图列表：
    - web_search: 需要搜索信息（攻略、价格、天气）
    - browser: 需要浏览器操作（打开网页、截图、填表单）
    - code: 需要编写或运行代码
    - data_analysis: 需要对数据进行分析
    - booking: 需要预订服务（机票、酒店、门票）
    - planning: 需要行程规划
    - chitchat: 闲聊，不需要工具
    
    规则：
    - 如果一条消息可能属于多个意图，选最主要的那一个
    - 如果不确定，返回 unknown
    
    用户消息：{user_input}
    
    只返回意图名称，不要解释。
    """
    
    def classify(self, user_input: str) -> Intent:
        prompt = self.INTENT_PROMPT.format(user_input=user_input)
        response = llm.generate(prompt).strip().lower()
        try:
            return Intent(response)
        except ValueError:
            return Intent.UNKNOWN
```

### 旅游 Agent 的意图分类示例

```python
test_cases = [
    ("成都五日游怎么安排",           Intent.PLANNING),
    ("成都到北京机票多少钱",         Intent.WEB_SEARCH),
    ("帮我订MU5678航班",             Intent.BOOKING),
    ("打开携程帮我比价",             Intent.BROWSER),
    ("分析这份旅游消费数据",         Intent.DATA_ANALYSIS),
    ("写个脚本爬成都酒店价格",       Intent.CODE),
    ("你好",                         Intent.CHITCHAT),
]

# 分类准确率应该在 90%+ 才能投产
```

---

## 4. Layer 2 — 工具选择

分类完后，根据意图选出候选工具。

```python
TOOL_REGISTRY = {
    Intent.WEB_SEARCH: {
        "primary":   ["web_search", "news_search", "image_search"],
        "secondary": ["summarize", "translate"],
    },
    Intent.BROWSER: {
        "primary":   ["navigate", "click", "type", "screenshot", "extract"],
        "secondary": ["scroll", "wait"],
    },
    Intent.BOOKING: {
        "primary":   ["search_flights", "search_hotels", "search_trains"],
        "secondary": ["book_flight", "book_hotel", "check_availability"],
    },
    Intent.PLANNING: {
        "primary":   ["decompose_goal", "search_weather", "search_attractions"],
        "secondary": ["optimize_route", "estimate_budget"],
    },
    Intent.CODE: {
        "primary":   ["write_code", "run_code", "read_file"],
        "secondary": ["search_docs", "install_package"],
    },
    Intent.CHITCHAT: {
        "primary":   ["chat"],
        "secondary": [],
    },
}

class ToolRouter:
    def select_tools(self, intent: Intent, context: dict) -> list:
        """根据意图选择工具，只返回当前步骤需要的"""
        registry = TOOL_REGISTRY.get(intent, {})
        
        # 总是包含 primary
        tools = list(registry.get("primary", []))
        
        # 根据上下文决定是否加 secondary
        if context.get("include_secondary", False):
            tools.extend(registry.get("secondary", []))
        
        return self._load_tool_definitions(tools)
    
    def _load_tool_definitions(self, tool_names: list) -> list:
        """只加载当前需要的工具定义（节省 Context）
        
        TOOL_DEFINITIONS 是一个全局注册表，存储每个工具的完整定义：
        {
          "web_search": {
            "name": "web_search",
            "description": "搜索网页内容，返回摘要列表",
            "parameters": {"query": "string, 搜索关键词"}
          },
          ...
        }
        """
        definitions = []
        for name in tool_names:
            tool_def = TOOL_DEFINITIONS.get(name)
            if tool_def:
                definitions.append(tool_def)
        return definitions
```

> **关键优化**：不是把所有工具都给 LLM，而是按意图过滤。一个场景通常只需要 3-8 个工具，而不是 50 个。

---

## 5. Layer 3 — 参数解析

选了工具，还要从用户消息中提取参数。

```python
class ParameterResolver:
    RESOLVE_PROMPT = """
    从用户消息中提取预订参数。
    
    用户消息：{user_input}
    上下文：{context}
    
    返回 JSON：
    {{
        "departure": "出发城市",
        "destination": "目的地",
        "date": "日期（YYYY-MM-DD）",
        "passengers": 人数,
        "preferences": ["偏好1", "偏好2"],
        "missing": ["缺失的参数名"]
    }}
    """
    
    def resolve(self, user_input: str, tool_name: str, context: dict) -> dict:
        prompt = self.RESOLVE_PROMPT.format(
            user_input=user_input,
            context=json.dumps(context)
        )
        response = llm.generate(prompt)
        params = json.loads(response)
        
        # 缺失参数 → 触发追问
        if params.get("missing"):
            return {
                "status": "incomplete",
                "missing": params["missing"],
                "resolved": params
            }
        
        return {
            "status": "ready",
            "params": params
        }


# 示例
user_input = "帮我订一张下周从北京去成都的机票"
resolver = ParameterResolver()
result = resolver.resolve(user_input, "search_flights", {})

# → {"status": "incomplete", 
#    "missing": ["date"], 
#    "resolved": {"departure": "北京", "destination": "成都"}}
# "下周"太模糊，需要追问具体日期
```

---

## 6. Layer 4 — 降级与升级

```python
class RouterWithFallback:
    def route(self, user_input: str, context: dict):
        # 1. 意图分类
        intent = self.intent_router.classify(user_input)
        
        # 2. 工具选择
        tools = self.tool_router.select_tools(intent, context)
        
        # 3. 执行
        try:
            result = self.execute(intent, tools, user_input, context)
        except ToolUnavailableError as e:
            # 降级策略
            result = self._fallback(intent, e)
        except SecurityRiskError as e:
            # 升级策略
            result = self._escalate(intent, e)
        
        return result
    
    def _fallback(self, intent: Intent, error: Exception):
        """工具不可用时的降级"""
        fallback_map = {
            Intent.WEB_SEARCH:  "改用缓存数据回答，标注数据可能过时",
            Intent.BROWSER:     "告知用户浏览器暂不可用，建议手动操作",
            Intent.BOOKING:     "提供预订链接，让用户手动完成",
            Intent.CODE:        "说明无法执行代码，提供代码片段供用户本地运行",
        }
        return {
            "status": "degraded",
            "message": fallback_map.get(intent, "服务暂不可用"),
            "original_error": str(error)
        }
    
    def _escalate(self, intent: Intent, error: Exception):
        """需要人工介入时升级"""
        return {
            "status": "escalated",
            "message": "此操作需要人工审核",
            "action": "已通知管理员，请稍候"
        }
```

---

## 7. Router 的优化策略

### 策略1：多级路由

```
粗分类（规划/搜索/预订/闲聊）
    ↓
细分类（搜索 → 网页搜索/图片搜索/新闻搜索）
    ↓
工具选择（网页搜索 → 用 Google API / Bing API / 内置搜索）
```

一级分类准确但不够细，多级路由在准确性和灵活性间平衡。

### 策略2：基于 Embedding 的语义路由

```python
import numpy as np

class SemanticRouter:
    def __init__(self):
        # 为每个意图存储一个代表性 embedding
        self.intent_embeddings = {
            Intent.PLANNING:   embed("成都五日游怎么安排 行程规划 路线"),
            Intent.WEB_SEARCH: embed("搜索 查询 多少钱 天气 攻略"),
            Intent.BOOKING:    embed("预订 订票 买票 下单 确认"),
            Intent.CHITCHAT:   embed("你好 谢谢 再见 帮助"),
        }
    
    def classify(self, user_input: str) -> Intent:
        input_emb = embed(user_input)
        # 余弦相似度找最近的意图
        best_intent = max(
            self.intent_embeddings,
            key=lambda i: cosine_similarity(input_emb, 
                                            self.intent_embeddings[i])
        )
        return best_intent
```

> LLM 分类更准但更慢更贵；Embedding 分类更快更便宜。高频简单场景用 Embedding，复杂模糊场景用 LLM。

### 策略3：混合路由

```python
class HybridRouter:
    def classify(self, user_input: str) -> Intent:
        # Step 1: Embedding 快速分类
        emb_intent, confidence = self.embedding_classify(user_input)
        
        # Step 2: 高置信度直接返回
        if confidence > 0.85:
            return emb_intent
        
        # Step 3: 低置信度用 LLM 二次确认
        llm_intent = self.llm_classify(user_input)
        
        # Step 4: LLM 和 Embedding 一致 → 返回
        if llm_intent == emb_intent:
            return llm_intent
        
        # Step 5: 不一致 → 信任 LLM（更准确）
        return llm_intent
```

---

## 8. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 所有工具都给 LLM | Context 浪费，选择准确率低 | 按意图过滤工具 |
| 没有降级策略 | 一个工具挂了，整个 Agent 不可用 | 每个工具准备降级方案 |
| 意图分类太粗 | 一个意图包含太多工具，失去过滤意义 | 意图粒度对应 3-8 个工具 |
| 意图分类太细 | 分类本身成为瓶颈 | 合并高频相似意图 |
| 缺失参数不追问 | LLM 瞎猜参数 → 结果不对 | 关键参数缺失时主动追问 |

---

## 实践任务

**任务1**：为你的旅游 Agent 定义至少 6 个意图，并为每个意图分配工具。画出 Router 的分发流程图。

**任务2**：收集（或模拟）20 条用户消息，测试你的意图分类准确率。哪些意图容易混淆？如何改进？

**任务3**：为每个意图设计降级策略——如果该意图依赖的核心工具不可用，Agent 应该如何优雅降级而不是直接报错？

```
示例：
意图「预订机票」依赖 flight_search API
→ 降级方案 A：返回航空公司官网链接
→ 降级方案 B：用网页搜索代替专用 API
→ 降级方案 C：告知用户当前无法预订，建议手动操作
```

---

→ [05-Multi-Agent.md](./05-Multi-Agent.md)
