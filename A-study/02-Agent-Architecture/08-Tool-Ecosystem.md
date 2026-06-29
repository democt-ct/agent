# 08 - Tool Ecosystem — 工具生态全景

> 学习目标：俯瞰 Agent 可用的工具生态——Function Calling、MCP、A2A 的关系，以及 Browser/Search/Vision/Code 四类 Tool 的适用场景

---

## 1. 三大工具协议

Agent 调用外部能力，经历三个阶段：

```
Phase 1: Function Calling（2023）
  你写 Python 函数 → 把签名给 LLM → LLM 决定调用哪个
  问题：每个 Agent 都要手写一遍工具定义，无法复用

Phase 2: MCP — Model Context Protocol（2024）
  标准化了"工具怎么描述、怎么调用"
  一个 MCP Server 可以被任何 MCP Client（Agent）使用
  问题：Agent 之间不能互相调用

Phase 3: A2A — Agent-to-Agent（2025）
  标准化了"Agent 之间怎么发现彼此、怎么通信"
  一个 Agent 可以调用另一个 Agent 的能力
```

```
         Function Calling        MCP              A2A
         ────────────────    ────────────    ──────────────
粒度      单个函数             一组工具         一个 Agent
复用性    ❌ 不跨 Agent       ✅ 跨 Agent       ✅✅ 跨组织
标准化    API 约定             JSON-RPC         HTTP/JSON
谁定义的  OpenAI              Anthropic         Google
```

---

## 2. Function Calling — 基础

```python
# 你定义工具
def search_flights(departure: str, destination: str, date: str) -> dict:
    """搜索航班"""
    return flight_api.search(departure, destination, date)

# 工具签名给 LLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "搜索航班信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "departure":  {"type": "string", "description": "出发城市"},
                    "destination": {"type": "string", "description": "目的城市"},
                    "date":       {"type": "string", "description": "日期 YYYY-MM-DD"}
                },
                "required": ["departure", "destination", "date"]
            }
        }
    }
]

# LLM 返回 function call
response = {
    "tool_calls": [{
        "function": {
            "name": "search_flights",
            "arguments": '{"departure":"北京","destination":"成都","date":"2026-07-15"}'
        }
    }]
}

# 你执行 + 返回结果 → LLM 继续推理
```

---

## 3. MCP — 工具标准化

MCP 解决的核心问题：**每个 Agent 不用重复实现同一类工具**。

```
传统方式（无 MCP）：
  Agent A → 自己写 search_web 函数
  Agent B → 自己写 search_web 函数
  Agent C → 自己写 search_web 函数
  → 三套代码，三套维护

MCP 方式：
  Browser MCP Server ← 一个实现
    ├── Agent A 连接它
    ├── Agent B 连接它
    └── Agent C 连接它
  → 一套代码，零重复
```

### MCP 架构

```
┌─────────────┐     JSON-RPC      ┌──────────────────┐
│  MCP Client  │ ◄──────────────► │   MCP Server      │
│  (Agent)     │                   │   (工具提供方)     │
│              │  list_tools()     │                   │
│              │ ────────────────► │   返回工具列表     │
│              │                   │                   │
│              │  call_tool()      │                   │
│              │ ────────────────► │   执行 + 返回结果  │
└─────────────┘                   └──────────────────┘

常见的 MCP Server：
  - Browser MCP：    操控浏览器（Puppeteer/Playwright）
  - Filesystem MCP： 读写文件
  - Database MCP：   查询数据库
  - GitHub MCP：     操作仓库
  - Slack MCP：      发送消息
  - 你自己写的 MCP： 任何能力
```

---

## 4. A2A — Agent 之间的互操作

MCP 解决了"Agent 怎么用工具"。A2A 解决"Agent 怎么用 Agent"。

```
场景：你的旅游 Agent 需要一个专业的"图片识别 Agent"来识别景点照片

MCP 方式：
  → 你得知道图片识别 Agent 的内部细节
  → 你得自己实现通信

A2A 方式：
  → 旅游 Agent 发现："有个 ImageAgent 能识别景点"
  → 自动协商：用 JSON 传图片 URL，返回景点名称
  → 你不需要知道 ImageAgent 的实现细节
```

```
┌──────────────┐   Agent Card    ┌──────────────┐
│  Travel Agent │ ◄────────────► │ Image Agent   │
│  (A2A Client) │   发现 + 调用   │ (A2A Server)  │
│               │                │               │
│  "这是哪个    │ ─────────────► │ "大熊猫基地"   │
│   景点？"     │                │               │
└──────────────┘                └──────────────┘
```

> 2025 年的趋势：MCP 用于 Tool 级复用，A2A 用于 Agent 级协作。两者互补，不是替代。

---

## 5. 四类核心 Tool

不管用什么协议，Agent 的 Tool 大致分为四类：

```
┌──────────┬──────────┬──────────┬──────────┐
│ Browser  │  Search  │  Vision  │   Code   │
│ 浏览器工具 │  搜索工具  │  视觉工具  │ 代码工具  │
├──────────┼──────────┼──────────┼──────────┤
│ 打开网页  │ 网页搜索  │ 图像识别  │ 编写代码  │
│ 点击/输入 │ 新闻搜索  │ OCR      │ 运行代码  │
│ 截图     │ 图片搜索  │ 视频分析  │ 调试     │
│ 提取数据  │ 语义搜索  │ 图表解读  │ 安装包   │
├──────────┼──────────┼──────────┼──────────┤
│ 场景：    │ 场景：    │ 场景：    │ 场景：    │
│ 比价     │ 查攻略    │ 识别照片  │ 数据分析  │
│ 填表单   │ 查天气    │ 读图表    │ 爬虫     │
│ 自动化测试│ 查新闻    │ 验证截图  │ 自动化脚本 │
└──────────┴──────────┴──────────┴──────────┘
```

### Browser Tool

```python
class BrowserTool:
    """操控浏览器完成 Web 任务"""
    
    async def navigate(self, url: str):
        """打开网页"""
    
    async def click(self, selector: str):
        """点击元素"""
    
    async def type_text(self, selector: str, text: str):
        """输入文本"""
    
    async def screenshot(self) -> bytes:
        """截图当前页面"""
    
    async def extract_text(self, selector: str) -> str:
        """提取页面文本"""

# 使用场景
# → Agent: "去携程搜北京到成都7月15日的航班"
# → navigate("ctrip.com") → type("#from","北京") → click("#search")
# → extract_text(".flight-list") → 返回航班列表
```

### Search Tool

```python
class SearchTool:
    """信息检索"""
    
    def web_search(self, query: str, top_k: int = 10) -> list:
        """通用网页搜索"""
    
    def news_search(self, query: str, days: int = 7) -> list:
        """新闻搜索（时效性内容）"""
    
    def image_search(self, query: str) -> list:
        """图片搜索"""
    
    def semantic_search(self, query: str, documents: list) -> list:
        """语义搜索（在给定文档集中找最相关的）"""
```

### Vision Tool

```python
class VisionTool:
    """理解和分析图像"""
    
    def describe_image(self, image: bytes) -> str:
        """描述图像内容"""
    
    def extract_text(self, image: bytes) -> str:
        """OCR 提取文字"""
    
    def compare_images(self, img1: bytes, img2: bytes) -> dict:
        """对比两张图"""
    
    def analyze_chart(self, image: bytes) -> dict:
        """分析图表数据"""

# 使用场景
# 用户上传景点照片 → Agent 识别："这是成都大熊猫基地的幼崽区"
# 用户上传菜单 → OCR 提取 → Agent 推荐菜品
```

### Code Tool

```python
class CodeTool:
    """编写和执行代码"""
    
    def write_code(self, language: str, task: str, context: dict) -> str:
        """根据需求写代码"""
    
    def run_code(self, code: str, language: str, timeout: int = 30) -> dict:
        """在沙箱中执行代码"""
    
    def debug(self, code: str, error: str) -> str:
        """根据错误信息调试"""
    
    def install_package(self, package: str):
        """安装依赖包"""

# 使用场景
# 旅游 Agent 需要分析比价数据 → write_code("Python", "对比三家航空公司的价格")
# → run_code → 输出分析结果
```

---

## 6. 工具选择决策树

```
用户需求
    │
    ├── 需要实时信息？ ───→ Search Tool（网页搜索）
    │
    ├── 需要操作网页？ ───→ Browser Tool（打开/点击/填表）
    │
    ├── 涉及图像？ ──────→ Vision Tool（识别/OCR/对比）
    │
    ├── 需要计算/分析？ ──→ Code Tool（写代码/跑脚本）
    │
    ├── 需要外部数据？ ───→ Database Tool（查数据库）
    │
    └── LLM 自己能推理？ ─→ 不调工具，直接推理
```

---

## 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 把所有工具塞给每个 Agent | Context 占用巨大 | Router 按意图过滤工具 |
| 只用 Function Calling 不用 MCP | 工具无法跨项目复用 | 通用能力封装为 MCP Server |
| 每个简单查询用 Browser | 比 Search 慢 10 倍 | 优先 Search，Browser 只用于需要交互的 |
| Code 执行不设沙箱 | 安全风险 | Docker 沙箱 + timeout |

---

## 实践任务

**任务1**：列出你的旅游 Agent 需要的全部工具，按 Browser/Search/Vision/Code 四类归类。哪些可以用现成的 MCP Server？

**任务2**：写一个最简 MCP Server（基于 Python），暴露一个 `search_flights` 工具，然后用一个 MCP Client 调用它。

**任务3**：分析 OpenHands 或 Claude Code 的源码——它们用了哪些 Tool？怎么组织的？画一张 Tool 架构图。

---

→ 继续学习：[03-Production-Engineering](../03-Production-Engineering/) 或回到 [学习指南](../学习指南.md)
