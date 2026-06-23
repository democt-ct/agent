# 产品需求文档（PRD）：患者智能辅助 Agent v2.3

**文档状态：** 当前实现对齐版
**当前版本目标：** 统一产品描述与现有代码实现，明确下一阶段迭代重点
**主要面向读者：** 产品经理、后端研发、前端研发、AI 工程师、测试工程师

---

## 1. 项目背景

患者在诊前、诊中、诊后场景里普遍存在以下痛点：

- 不知道该问什么、挂什么科
- 报告和病历术语看不懂
- 同样的问题反复咨询
- 历史病历和就诊记录无法连续利用
- 医生和导诊台被大量基础问答占用

本项目希望建设一个患者侧智能辅助 Agent，作为数字服务入口，承担：

- 基础问答
- 病历与就诊记录调阅
- 报告和图片理解
- 记忆聊天
- 诊后提醒与解释

---

## 2. 当前产品定位

当前版本不是正式生产系统，而是一个：

- 可运行
- 可测试
- 可解释
- 可迭代

的患者侧 Agent 原型。

产品当前重点不是“覆盖全部医院流程”，而是验证以下能力能否稳定协同：

- 患者事实查询
- 会话连续记忆
- 长期摘要记忆
- 知识块检索
- 工具调用与问答编排

---

## 3. 当前版本范围

### 3.1 已实现范围

#### 数据与服务

- 患者主档管理
- 病历管理
- 就诊记录管理
- 聚合 profile 查询
- 知识块入库与检索
- 会话消息持久化

#### Agent 能力

- 通用聊天
- 记忆聊天
- MCP 工具调用
- 图文问答
- 语音播报
- 短期工作记忆
- 长期摘要记忆
- 患者事实记忆
- 混合 RAG

#### 测试能力

- 测试页 Query / Chat 双工作区
- Memory Debug 中文卡片
- Memory Debug 原始 JSON

### 3.2 当前不在实现范围内

- 生产级权限系统
- 正式 React 前端工程
- 后台调度与定时刷新
- 正式 HIS / LIS / RIS 联调
- 自动诊断、自动处方、替代医生决策

---

## 4. 当前核心业务场景

### 4.1 患者事实查询

患者询问：

- 我的住址是什么？
- 我有没有过敏史？
- 我的紧急联系人是谁？

系统应优先从患者主档和事实层命中，而不是依赖模型猜测。

### 4.2 病历与就诊记录调阅

患者询问：

- 我最近一次就诊是什么情况？
- 我最近的复诊建议是什么？
- 结合我的病历，总结一下当前重点

系统应从病历和就诊记录抽取结构化事实，优先给出基于事实的回答。

### 4.3 连续记忆聊天

患者先说：

- 我最近总是胸闷和心悸，你先记住这个情况

后续再问：

- 我刚才让你记住了什么？
- 我现在主要在问什么问题？

系统应通过工作记忆记住当前主题、目标和最近轮次消息。

### 4.4 图文联合问答

患者上传图片或报告，并结合历史信息提问时，系统应支持：

- 图片理解
- 上下文记忆拼装
- 结合患者事实输出结果

---

## 5. 当前系统架构

当前实现已经形成四层记忆架构：

### 5.1 事实层

事实层是最底层、最可信的数据来源，包括：

- 患者主档
- 病历
- 就诊记录
- 关键事件

### 5.2 短期工作记忆

当前短期记忆已经不是简单的“最近几轮文本”，而是结构化工作记忆，包括：

- `recent_messages`
- `intent`
- `current_topic`
- `goal`
- `working_summary`
- `next_action`
- `memory_focus`
- `active_entities`
- `risk_signals`

### 5.3 长期摘要记忆

长期摘要记忆由以下对象构成：

- `MemoryUserProfile`
- `MemoryBusinessProfile`
- `MemoryConversationProfile`
- `MemoryPreference`
- `MemoryKeyEvent`

这一层负责沉淀稳定画像、偏好、长期关注点和关键事件。

### 5.4 知识记忆

知识记忆负责承载可复用知识块，通过混合检索召回：

- 知识块 SQL 元数据
- ChromaDB 向量检索
- 关键词补召回
- 综合排序

---

## 6. 当前技术实现映射

### 6.1 后端

- `FastAPI`
- `SQLAlchemy`
- `PostgreSQL`（主数据库）
- `Redis`（会话缓存）
- 自研 MCP Server
- 自研工具路由与 Agent 编排

### 6.2 向量检索

- `ChromaDB`
- `LangChain embedding wrapper`
- `sentence-transformers`
- `BAAI/bge-small-zh-v1.5`

### 6.3 模型配置

当前采用“本地文本 + 远端视觉”的混合方案：

- 文本生成：本地 Ollama
- 图片理解：远端 OpenAI-compatible Vision
- 语音：本地 TTS / 浏览器播报

### 6.4 前端

当前不是 React 工程，而是测试态静态页面：

- `tester.html`
- Query 页面
- 通用聊天
- 记忆聊天
- Memory Debug

---

## 7. 当前关键接口

### 7.1 基础数据接口

- `POST /api/v1/patients`
- `GET /api/v1/patients`
- `GET /api/v1/patients/{patient_id}`
- `DELETE /api/v1/patients/{patient_id}`
- `POST /api/v1/patients/{patient_id}/medical-records`
- `GET /api/v1/patients/{patient_id}/medical-records`
- `POST /api/v1/patients/{patient_id}/visits`
- `GET /api/v1/patients/{patient_id}/visits`

### 7.2 Memory 接口

- `GET /api/v1/memory/profile`
- `GET /api/v1/memory/conversations/messages`
- `GET /api/v1/memory/conversations/sessions`
- `POST /api/v1/memory/conversations/promote-session`
- `POST /api/v1/memory/knowledge-chunks`
- `POST /api/v1/memory/knowledge-chunks/retrieve`

### 7.3 Agent 接口

- `POST /api/v1/mcp/agent/query`
- `POST /api/v1/mcp/agent/query-with-image`
- `POST /api/v1/mcp/agent/speech`

---

## 8. 当前前端交互要求

当前测试页已经形成以下布局：

- 左侧：个人信息 / 会话操作
- 右侧：连续对话窗口
- 对话窗口下方：输入框
- 页面最底部：Memory Debug

Memory Debug 当前保留两层：

1. 中文卡片
2. 原始 JSON

测试目的不是“做漂亮 UI”，而是确保每一轮问答都能观察到：

- 工作记忆是否更新
- 事实记忆是否命中
- 长期摘要记忆是否参与
- 知识记忆是否参与

---

## 9. 当前验收标准

### 9.1 数据层验收

- 可以创建患者、病历、就诊记录
- 可以按患者读取结构化事实
- 可以通过 profile 接口聚合读取主档、病历、就诊记录

### 9.2 Agent 验收

- 记忆聊天可正常工作
- 患者主档类问题可命中事实层
- 病历/就诊类问题可命中结构化事实
- 连续追问可利用短期工作记忆
- 图文问答可正常返回

### 9.3 记忆系统验收

- `working_memory` 随每轮对话更新
- `factual_memory` 可命中患者主档和业务事实
- `long_term_summary_memory` 可返回长期画像摘要
- `knowledge_memory` 可在知识块存在时命中
- Memory Debug 可展示中文卡片和原始 JSON

---

## 10. 当前问题与下一阶段目标

当前系统已经完成“原型级闭环”，但还存在几个明确问题：

### 10.1 记忆质量仍需优化

- 工作记忆总结规则仍可继续提升
- 长期摘要记忆仍依赖抽取质量
- 事实记忆仍是请求期临时拼装，不是持久化事实向量层

### 10.2 RAG 仍处于可用但非最终态

- 已有混合检索
- 但还没有更强 reranker
- 还没有成熟的评测集和稳定指标

### 10.3 前端仍是测试态

- 当前页面适合联调和观察
- 但还不是正式患者端产品形态

---

## 11. 下一阶段建议路线

### P1.5

- 稳定工作记忆与事实记忆
- 优化长期记忆抽取质量
- 建立基础评测问题集

### P2

- 把患者事实层正式 chunk 化并接入持久化检索
- 增加更强 rerank
- 优化前端显示与调试体验

### P3

- 真实业务系统联调
- 强化权限、审计、隔离与合规
- 进入更接近生产的工程化阶段

---

## 12. 当前结论

当前版本已经不再是“只有数据 CRUD”的早期底座，而是一套具备：

- 数据事实层
- 记忆层
- 检索层
- 工具层
- Agent 路由层
- 调试可视化层

的患者侧 Agent 原型系统。

下一阶段不应再重复搭骨架，而应转向：

- 记忆质量优化
- 检索质量优化
- 测试问题集建设
- 正式工程化收口
