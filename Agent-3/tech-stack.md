# 技术选型 + 协作规范

> 单人全栈开发，所有决策已敲定，直接照此执行。

---

## 1. 技术选型

| 层 | 选择 | 版本 | 理由 |
|----|------|------|------|
| 语言 | Python | ≥3.11 | 生态最全 |
| LLM | DeepSeek API | deepseek-v4-flash | 性价比高、支持 thinking mode |
| Embedding | OpenAI `text-embedding-3-small` | — | 成熟稳定 |
| 向量库 | Chroma | ≥0.6 | 零配置、内嵌运行 |
| 重排序 | Cohere Rerank | v2 | 免费额度够用 |
| BM25 | `rank-bm25` | latest | 标准实现、轻量 |
| 文档加载 | `pypdf` + `python-docx` | latest | 够用 |
| 分块 | LangChain `RecursiveCharacterTextSplitter` | latest | 分块最稳 |
| Agent 框架 | 手写 ReAct + LangGraph 编排 | — | 核心逻辑可见 |
| 前端 | Streamlit | ≥1.40 | 快速出效果 |
| 测试 | pytest | ≥8 | 标准 |

---

## 2. 不选方案及理由

| 被拒绝 | 为什么不用 |
|--------|-----------|
| CrewAI | Manager Agent 是黑箱，控制不了路由 |
| AutoGen | 太重 |
| BGE-M3 本地 Embedding | 需要下载 2GB 模型，简单项目不需要 |
| Qdrant | 需要 Docker，零配置优先 |
| Semantic Chunking | 多调一次 LLM，效果提升有限 |

---

## 3. RAG Pipeline 参数

| 参数 | 值 | 理由 |
|------|----|------|
| chunk_size | 500 tokens | 企业文档段落 300-800 |
| chunk_overlap | 80 tokens | 保留上下文过渡 |
| top_k（初次检索） | 10 | 保证召回 |
| top_k（重排序后） | 3 | 3 段够回答 |
| RRF k 值 | 60 | 标准值 |
| Embedding 维度 | 512 | text-embedding-3-small 默认 |
| 相似度阈值 | 0.3 | 低于此分数的丢弃 |

---

## 4. LLM 调用参数

| 场景 | model | temperature |
|------|-------|-------------|
| Agent 回答问题 | deepseek-v4-flash | 0.3 |
| Orchestrator 路由 | deepseek-v4-flash | 0.0 |
| 重写检索 query | deepseek-v4-flash | 0.1 |

---

## 5. Git 规范

- 单人开发，直接在 `main` 分支工作
- commit 信息用中文：`动词+模块: 做了什么`
- 如 `实现 RAG loader 文档加载` / `修复 orchestrator 关键词匹配优先级`

### .gitignore

```
.env
__pycache__/
*.pyc
.venv/
.chroma/
chroma_db/
*.egg-info/
dist/
.streamlit/
```

### .gitattributes

```
* text=auto
*.py text eol=lf
*.toml text eol=lf
*.md text eol=lf
*.json text eol=lf
```

---

## 6. 环境配置

`.env` 文件（不提交到 Git）：

```
DEEPSEEK_API_KEY=sk-xxx
COHERE_API_KEY=your-cohere-key-here
```

---

## 7. 引包规范

```python
# 一律用项目绝对路径
from src.protocol.types import AgentRequest, AgentResponse
from src.rag.knowledge_base import KnowledgeBase
```
