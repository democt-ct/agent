# AI Photo Agent - Agent Workflow 与系统设计文档

# 1. 文档说明

本文档主要描述 AI Photo Agent 的 Agent 架构设计、工作流设计、状态管理机制、工具调用机制（Tool Use）、记忆机制（Memory）以及自反思机制（Reflection）。

目标是构建一个具备自主规划、工具调用、结果评估和持续优化能力的多 Agent 智能修图系统。

---

# 2. Agent 设计原则

系统遵循以下原则：

## 单一职责原则

每个 Agent 仅负责单一任务。

例如：

* Vision Agent负责图片理解
* Critic Agent负责质量分析
* Planner Agent负责策略制定
* Tool Agent负责工具选择

避免一个 Agent 完成所有任务。

---

## 工具驱动原则

Agent 不直接执行图像处理。

Agent 负责：

* 思考
* 决策
* 规划

工具负责：

* 执行

实现思考与执行解耦。

---

## 可扩展原则

新增功能时无需修改已有 Agent。

例如：

新增：

* AI扩图
* AI换背景
* AI换天空

仅需新增 Tool 即可。

---

# 3. Multi-Agent 架构

## 总体架构

```text
                   User
                     │
                     ▼

          Orchestrator Agent
                     │
 ┌─────────┬─────────┬─────────┐
 │         │         │         │
 ▼         ▼         ▼         ▼

Vision   Critic   Planner   Memory

                     │
                     ▼

               Tool Agent

                     │

      ┌──────────────┼──────────────┐
      │              │              │

      ▼              ▼              ▼

   OpenCV       Flux Kontext    SDXL

                     │
                     ▼

             Evaluator Agent

                     │
         ┌───────────┴───────────┐
         │                       │

      Success                Retry

         │                       │
         ▼                       │

      Output                     │
                                 │
                                 └────→ Planner Agent
```

---

# 4. Agent 详细设计

# 4.1 Orchestrator Agent

职责：

负责系统整体调度。

主要功能：

* Agent编排
* 状态管理
* 工作流控制
* 上下文传递

输入：

```json
{
  "image":"xxx",
  "user_prompt":"修成电影感"
}
```

输出：

```json
{
  "next_agent":"VisionAgent"
}
```

---

# 4.2 Vision Agent

职责：

理解图片内容。

输出：

```json
{
  "scene":"landscape",
  "objects":[
    "sky",
    "grass",
    "mountain"
  ],
  "lighting":"cloudy",
  "quality":"medium"
}
```

分析内容：

* 场景识别
* 主体识别
* 天气识别
* 光照分析
* 图像质量分析

---

# 4.3 Photo Critic Agent

职责：

发现图片存在的问题。

输出：

```json
{
  "issues":[
    {
      "type":"low_contrast",
      "severity":"medium"
    },
    {
      "type":"flat_sky",
      "severity":"high"
    }
  ]
}
```

分析维度：

* 曝光
* 对比度
* 色彩
* 构图
* 主体突出度

---

# 4.4 Style Planner Agent

职责：

生成修图策略。

用户：

```text
修成电影感
```

输出：

```json
{
  "style":"cinematic",
  "actions":[
    "降低曝光",
    "提高对比",
    "增加蓝绿色调",
    "压缩高光"
  ]
}
```

核心作用：

将自然语言转换为修图计划。

---

# 4.5 Tool Agent

职责：

选择最合适的工具。

---

## 工具分类

### OpenCV

适用于：

* 曝光调整
* 对比度调整
* 饱和度调整
* 锐化
* 降噪

---

### Flux Kontext

适用于：

* 换天空
* 换天气
* 语义修改

---

### SDXL

适用于：

* 局部重绘
* 内容补全
* AI扩图

---

## Tool Routing

示例：

用户：

```text
亮一点
```

输出：

```json
{
  "tool":"opencv"
}
```

---

用户：

```text
改成日落
```

输出：

```json
{
  "tool":"flux_kontext"
}
```

---

# 4.6 Editing Agent

职责：

调用具体工具完成编辑。

输入：

```json
{
  "tool":"opencv",
  "params":{
    "brightness":0.2,
    "contrast":15
  }
}
```

输出：

编辑后的图片。

---

# 4.7 Evaluator Agent

职责：

评估修图结果。

作用：

实现 Reflection。

---

输入：

原图

修图图

用户目标

---

输出：

```json
{
  "score":85,
  "reason":"达到电影感目标"
}
```

---

若评分低于阈值：

```json
{
  "retry":true
}
```

返回 Planner Agent。

形成闭环。

---

# 5. Workflow 设计

## 自动修图流程

```text
Upload

↓

Vision Agent

↓

Critic Agent

↓

Planner Agent

↓

Tool Agent

↓

Editing Agent

↓

Evaluator Agent

↓

Output
```

---

## Reflection Workflow

```text
Editing

↓

Evaluator

↓

Score < 80

↓

Planner

↓

Editing

↓

Evaluator

↓

Output
```

---

## 对话修图 Workflow

```text
用户：

天空蓝一点

↓

Conversation Agent

↓

Planner Agent

↓

Tool Agent

↓

Editing Agent

↓

Output
```

---

# 6. Agent State 设计

## State Schema

```python
class PhotoState:
    
    image_id: str

    original_image: str

    current_image: str

    user_goal: str

    scene_info: dict

    issues: list

    edit_plan: list

    selected_tool: str

    edit_history: list

    score: float
```

---

# 7. Memory 设计

## 短期记忆

保存当前会话。

例如：

```text
电影感
↓
天空更蓝
↓
肤色暖一点
```

系统持续保存状态。

---

## 长期记忆

记录用户偏好。

示例：

```json
{
  "favorite_style":"cinematic",
  "favorite_temperature":"warm",
  "favorite_saturation":"medium"
}
```

---

下次自动推荐。

---

# 8. 数据库设计

# users

```sql
id
username
email
created_at
```

---

# images

```sql
id
user_id
original_url
edited_url
created_at
```

---

# sessions

```sql
id
user_id
session_name
created_at
```

---

# edit_history

```sql
id
session_id
prompt
tool
parameters
created_at
```

---

# user_preferences

```sql
id
user_id
style
temperature
saturation
updated_at
```

---

# 9. LangGraph 工作流设计

```text
START

↓

VisionNode

↓

CriticNode

↓

PlannerNode

↓

ToolNode

↓

EditingNode

↓

EvaluatorNode

↓

score >= 80 ?

├─ YES → END

└─ NO

      ↓

 PlannerNode
```

---

# 10. 面试亮点

本项目不仅是一个 AI 修图系统，更是一个具备完整 Agent 能力的智能工作流系统。

核心亮点：

* Multi-Agent 架构设计
* Tool Use 机制
* Reflection 自反思机制
* Agent Memory 设计
* LangGraph 工作流编排
* 多模态大模型应用
* OpenCV 与生成式 AI 联合编辑

具备典型 Agent Application 开发特征，可扩展至设计、视频编辑、内容创作等多个场景。
