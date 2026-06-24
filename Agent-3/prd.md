# 企业多专家 Agent 系统 — PRD

> Product Requirements Document v2.0  
> 单人全栈开发 | 教学项目 + 求职作品集

---

## 1. 产品背景与动机

### 1.1 背景

企业内部有大量分散的知识（HR 政策、IT 运维手册、法务合规文档、财务报销流程），员工需要花大量时间在多个系统/文档之间切换。现有方案要么是纯关键词搜索（准确率低），要么是单一 Chatbot（一个模型回答所有领域，幻觉率高）。

### 1.2 目标

构建一个**多专家 Agent 系统**，每个 Agent 拥有独立的知识库和工具集，由 Orchestrator Agent 统一调度，实现：

- 员工用自然语言提问，系统自动路由到对应专家
- 复杂跨域问题自动协调多个 Agent 接力回答
- 每个 Agent 的回答基于其专属 RAG 知识库，降低幻觉

### 1.3 非目标（明确不做）

- 不涉及真实企业数据安全/权限（用模拟数据）
- 不做生产级高并发（不考虑多租户、负载均衡）
- 不做完整 UI（以 CLI / Streamlit demo 为主）
- 不接入真实企业系统（工具是 mock 或沙箱版）

---

## 2. 用户场景与 Persona

### 2.1 目标用户（Demo 视角）

| Persona | 典型问题 | 期望 |
|---------|---------|------|
| 普通员工 | "我今年还剩几天年假？" | 快速准确回答 |
| 员工 | "笔记本坏了怎么报修？"+ "病假工资怎么算？" | 一次提问覆盖两个领域 |
| 管理者 | "我们部门上季度报销超支了多少？" | 跨 Agent 汇总 |

### 2.2 面试官视角（关键）

面试官看的不是产品功能，而是**技术决策**：

- 为什么用 Multi-Agent 而不是一个 Agent 加长 prompt？
- Agent 交割协议怎么设计的？上下文如何传递？
- RAG 召回失败了有什么兜底？
- 路由错误了怎么恢复？

---

## 3. 系统架构

### 3.1 整体架构

```
                    ┌─────────────────────┐
                    │    用户界面 (CLI)     │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │   Orchestrator      │
                    │   Agent (路由/规划)  │
                    │                     │
                    │  - 寒暄检测          │
                    │  - 关键词规则匹配     │
                    │  - LLM 意图路由      │
                    │  - 兜底/降级         │
                    └──┬──┬──┬──┬──┬─────┘
                       │  │  │  │  │
          ┌────────────┘  │  │  │  └────────────┐
          │               │  │  │                │
    ┌─────▼─────┐  ┌─────▼──▼──▼──────┐  ┌─────▼─────┐
    │  HR Agent  │  │  IT Agent      │  │ 法务 Agent  │
    │            │  │                │  │            │
    │ RAG: 人事   │  │ RAG: 运维文档  │  │ RAG: 合规   │
    │ 制度/流程  │  │ 设备/工单      │  │ 合同/政策   │
    │            │  │                │  │            │
    │ Tools:     │  │ Tools:         │  │ Tools:     │
    │ · 查假期   │  │ · 查工单状态   │  │ · 查合同   │
    │ · 提交审批 │  │ · 重启服务     │  │ · 合规检查 │
    └────────────┘  └────────────────┘  └────────────┘
```

### 3.2 路由设计

三级路由链路（确定性优先）：

```
用户 query
  → ① 寒暄检测     ("你好"→fallback，模式匹配)
  → ② 关键词匹配   (30+ 关键词 × 3 领域，位置优先级定 primary/secondary)
  → ③ LLM 路由     (DeepSeek temperature=0.0，JSON structured output)
  → {"primary": "hr_agent", "secondary": "it_agent"}
```

兜底策略：
- 无法路由时 → 追问澄清
- 连续失败 → 降级为通用回答
- 模糊输入 ("帮我查一下") → confidence 低，要求用户补充

### 3.3 Agent 定义

#### Orchestrator Agent

| 属性 | 说明 |
|------|------|
| 职责 | 接收用户输入，判断意图，路由到正确的 Specialist Agent |
| 输入 | 用户自然语言问题 + 历史对话上下文 |
| 输出 | 最终回答（或经 Agent 处理后的汇总） |
| 关键技术 | 关键词规则匹配 + LLM 意图分类 + 位置优先级 |

#### HR Agent

| 属性 | 说明 |
|------|------|
| RAG 知识库 | 人事制度、考勤政策、请假流程、薪酬福利文档 |
| 工具 | `get_leave_balance(user_id)`, `submit_leave_request(...)` |
| 典型场景 | "我今年年假还剩几天？" |
| 边界 | 不处理技术问题 |

#### IT Agent

| 属性 | 说明 |
|------|------|
| RAG 知识库 | IT 运维手册、设备申领流程、常见故障排查指南 |
| 工具 | `check_ticket_status(ticket_id)`, `create_ticket(...)`, `check_device_inventory(...)` |
| 典型场景 | "笔记本蓝屏怎么办？" |
| 边界 | 不处理人事问题 |

#### 法务 Agent

| 属性 | 说明 |
|------|------|
| RAG 知识库 | 合规政策、合同模板、数据保护条例 |
| 工具 | `search_contract(keyword)`, `check_compliance(doc_summary)` |
| 典型场景 | "员工数据能存到境外服务器吗？" |
| 边界 | 不提供法律建议（带 disclaimer） |

### 3.4 跨 Agent 交割协议

```json
{
  "from_agent": "hr_agent",
  "context": {
    "query": "我请病假，顺便笔记本报修",
    "already_answered": ["病假已审批"]
  },
  "summary": "已处理假期申请部分",
  "handoff_type": "chain"
}
```

### 3.5 RAG Pipeline（每个 Agent 独立一份）

```
文档 (MD) → 加载 → 分块 → Embedding → 向量库 (Chroma)
                                              ↑
用户提问 → 意图路由 → [Agent] → 向量检索 + BM25 混合
                                          ↓
                                      重排序
                                          ↓
                                      LLM 生成回答
```

| 决策 | 选择 | 理由 |
|------|------|------|
| 分块策略 | RecursiveCharacter + 语义段落 | 企业文档段落边界清晰 |
| chunk_size | 500 tokens | 企业文档段落通常 300-800 |
| chunk_overlap | 80 tokens | 保留上下文过渡 |
| Embedding 模型 | text-embedding-3-small | 质量成本平衡 |
| 向量库 | Chroma（本地） | 零配置，适合 demo |
| 检索方式 | 向量 + BM25 混合 (RRF k=60) | 关键词匹配兜底 |
| top_k 初次检索 | 10 | 保证召回 |
| top_k 重排序后 | 3 | 3段足够回答 |
| 重排序 | Cohere Rerank | API 简单 |

---

## 4. 功能需求分级

### P0 — Step 1~6 必做

| ID | 功能 | 涉及模块 |
|----|------|---------|
| F1 | 用户输入自然语言，系统返回回答 | 全链路 |
| F2 | Orchestrator 三级路由（寒暄+关键词+LLM） | Orchestrator |
| F3 | HR Agent 基于 RAG 回答人事政策问题 | HR Agent + RAG |
| F4 | IT Agent 基于 RAG 回答 IT 问题 | IT Agent + RAG |
| F5 | 法务 Agent 基于 RAG 回答合规/合同问题 | 法务 Agent + RAG |
| F6 | 每个 Agent 能调用 mock 工具 | 各 Agent |
| F7 | 每个 Agent 有独立的 RAG 知识库 | RAG Pipeline |
| F8 | Orchestrator 支持跨 Agent 串行编排 | Orchestrator |

### P1 — Step 7

| ID | 功能 |
|----|------|
| F9 | RAG 混合检索 + 重排序 |
| F10 | 对话历史记忆 |
| F11 | Streamlit 前端 + Agent 思维链可视化 |
| F12 | 评估脚本（路由准确率 + RAG 命中率） |

---

## 5. 数据 / 知识库

需准备的模拟企业文档：

| 知识库 | 文档数 | 内容 |
|--------|--------|------|
| HR | 5 份 | 请假制度、考勤规则、薪酬福利、年假管理、病假规定 |
| IT | 5 份 | 设备申领流程、报修指南、软件安装、密码管理、网络/VPN |
| 法务 | 5 份 | 数据保护条例、合同审批流程、保密协议、合规清单、知识产权 |

每份 500-2000 字，中文。

---

## 6. 评估指标

| 指标 | 定义 | 目标 |
|------|------|------|
| **路由准确率** | Orchestrator 正确分配到 Agent 的比例 | > 90% |
| **RAG 命中率** | LLM 回答基于检索到的正确文档片段 | > 85% |
| **工具调用正确率** | Agent 在正确时机调用了正确的工具 | > 90% |
| **端到端满意度** | 人工判断回答是否完整正确 | > 80% |
| **跨 Agent 成功率** | 多步编排完整走完的比例 | > 70% |

---

## 7. 开发步骤

详见 [`docs/development-steps.md`](development-steps.md)。

```
Step 1 ✅ 项目骨架 + Protocol 协议层
Step 2 ✅ BaseAgent ReAct 引擎
Step 3 ✅ Orchestrator 路由引擎
Step 4 ⬜ 知识库文档 + RAG 管线
Step 5 ⬜ 3 个 Specialist Agent + 工具
Step 6 ⬜ 集成联调 + CLI + 测试
Step 7 ⬜ Streamlit 前端 + 评估 + Demo
```

---

## 8. Demo 场景

### 场景 1：单 Agent 简单查询

> **用户**：我今年年假还剩几天？  
> **预期**：Orchestrator 路由到 HR Agent → RAG 检索出年假政策 → 调用 `get_leave_balance()` → 返回结果

### 场景 2：跨 Agent 复合查询

> **用户**：我请 3 天病假，顺便笔记本最近很卡想报修  
> **预期**：
> 1. Orchestrator 判断跨 HR + IT 两个领域
> 2. → HR Agent：查病假政策 + 提交请假申请
> 3. → IT Agent：RAG 检索报修流程 + 创建工单
> 4. → 汇总："病假已审批，IT 工单 #1024 已创建"

### 场景 3：兜底

> **用户**：今天的晚饭吃什么？  
> **预期**：Orchestrator 无法路由 → 兜底："这个问题不在我的知识范围内"

---

## 9. 已确认技术决策

| 决策项 | 结论 | 理由 |
|-------|------|------|
| Agent 通信模式 | **Orchestrator 中转** | 集中调度便于 debug，加新 Agent 只需加路由规则 |
| LLM 方案 | **DeepSeek** | deepseek-v4-flash 性价比高 |
| MVP Agent 数量 | **3 个（HR + IT + 法务）** | 领域各有特色，知识库不重叠 |
| 知识库语言 | **中文** | 中文企业文档更好找 |
| 工具实现 | **Mock 优先** | MVP 聚焦逻辑正确性 |
| 开发语言 | **Python 3.11+** | LLM/RAG 生态最成熟 |
| 路由策略 | **关键词优先于 LLM** | 关键词确定性高，LLM 做兜底 |

---

*本文档为 v2.0，随开发步骤迭代。*
