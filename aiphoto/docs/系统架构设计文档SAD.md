# AI Photo Agent 系统架构设计文档（SAD）

# 1. 系统概述

## 1.1 项目名称

AI Photo Agent

## 1.2 项目定位

AI Photo Agent 是一个基于多模态大模型、多 Agent 协同决策与图像编辑引擎构建的智能后期处理平台。

系统通过图像理解、问题诊断、修图策略规划和编辑执行等多个 Agent 的协同工作，实现从图片上传到最终成片的全自动修图流程。

---

# 2. 系统目标

## 核心目标

将专业摄影师后期工作流程 Agent 化。

传统流程：

摄影师

↓

分析照片

↓

发现问题

↓

制定调色方案

↓

手动修图

↓

导出图片

AI Photo Agent：

上传图片

↓

Vision Agent

↓

Analysis Agent

↓

Color Agent

↓

Editing Agent

↓

输出结果

---

# 3. 总体架构

```text
┌──────────────────────┐
│       Frontend       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    API Gateway       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────┐
│         Orchestrator Agent       │
└──────────┬───────────┬────────────┘
           │           │
           ▼           ▼

 Vision Agent      Conversation Agent

           │
           ▼

 Analysis Agent

           │
           ▼

 Color Expert Agent

           │
           ▼

 Editing Agent

           │
           ▼

 Preview Agent

           │
           ▼

        Output
```

---

# 4. Agent设计

## 4.1 Orchestrator Agent

职责：

负责整个工作流编排。

主要功能：

* Agent调度
* 状态管理
* 上下文管理
* 用户意图解析

输入：

用户请求

输出：

执行计划

示例：

用户：

帮我修成电影感

执行计划：

1. 调用Vision Agent
2. 调用Analysis Agent
3. 调用Color Agent
4. 调用Editing Agent
5. 返回结果

---

## 4.2 Vision Agent

职责：

负责图片内容理解。

输入：

图片

输出：

```json
{
  "scene":"landscape",
  "weather":"cloudy",
  "time":"day",
  "objects":[
    "sky",
    "grass",
    "mountain"
  ]
}
```

分析维度：

* 场景识别
* 主体识别
* 目标检测
* 光照分析
* 色彩分析

候选模型：

* Qwen2.5-VL
* Qwen3-VL
* InternVL3

---

## 4.3 Analysis Agent

职责：

发现图片问题。

输入：

Vision结果

输出：

```json
{
  "issues":[
    "low_contrast",
    "under_saturation",
    "flat_sky"
  ]
}
```

分析内容：

* 曝光
* 对比度
* 色温
* 噪点
* 构图
* 清晰度

---

## 4.4 Color Expert Agent

职责：

模拟专业调色师。

输入：

问题分析结果

输出：

```json
{
  "brightness":0.2,
  "contrast":20,
  "highlights":-15,
  "shadows":10,
  "vibrance":15
}
```

核心任务：

生成最优修图策略。

支持：

* 风景
* 人像
* 夜景
* 美食
* 建筑

---

## 4.5 Editing Agent

职责：

执行具体图像处理。

输入：

调色方案

输出：

修图结果

支持：

* 曝光调整
* 色温调整
* 曲线调整
* HSL调整
* 锐化
* 降噪

技术方案：

OpenCV

Pillow

ImageMagick

---

## 4.6 Conversation Agent

职责：

支持自然语言编辑。

示例：

用户：

天空再蓝一点

↓

意图解析：

增加天空区域蓝色饱和度

↓

生成参数

↓

调用Editing Agent

---

## 4.7 Preview Agent

职责：

结果评估与展示。

输出：

* 原图
* 修图图
* 前后对比图
* 修改记录

---

# 5. 工作流设计

## 自动修图流程

上传图片

↓

Vision Agent

↓

Analysis Agent

↓

Color Agent

↓

Editing Agent

↓

Preview Agent

↓

返回结果

---

## 对话修图流程

用户：

肤色自然一点

↓

Conversation Agent

↓

解析需求

↓

生成编辑策略

↓

Editing Agent

↓

返回结果

---

# 6. Prompt工程设计

## Vision Prompt

目标：

分析图片内容。

输出格式：

JSON

字段：

* scene
* objects
* weather
* quality
* lighting

---

## Analysis Prompt

目标：

发现图片问题。

输出：

问题列表

严重程度

优化建议

---

## Color Expert Prompt

角色：

20年经验摄影后期专家

任务：

根据图片问题生成调色参数

输出：

JSON格式参数

---

# 7. 数据库设计

## users

```sql
id
username
email
avatar
created_at
```

---

## images

```sql
id
user_id
origin_url
edited_url
created_at
```

---

## edit_tasks

```sql
id
image_id
task_type
status
created_at
```

---

## edit_history

```sql
id
image_id
prompt
parameters
created_at
```

---

# 8. 技术栈

## 前端

Next.js

React

TailwindCSS

Shadcn UI

---

## 后端

FastAPI

Python

Celery

Redis

---

## 数据库

PostgreSQL

Redis

MinIO

---

## AI层

Qwen3-VL

GPT-4o

DeepSeek

---

## 图像处理

OpenCV

Pillow

Diffusers

Flux Kontext

---

# 9. MVP开发路线

Phase 1

* 上传图片
* 自动分析
* 自动调色

预计：

2周

---

Phase 2

* Agent工作流
* 对话修图

预计：

2周

---

Phase 3

* 风格迁移
* 局部修图
* 批量修图

预计：

3周

---

# 10. 简历包装亮点

项目名称：

AI Photo Agent

项目描述：

基于多模态大模型与多 Agent 协同架构构建的智能修图系统。通过 Vision Agent、Analysis Agent、Color Agent 与 Editing Agent 的协同工作，实现图像理解、问题诊断、修图策略生成与自动编辑闭环，支持自然语言驱动的对话式修图与风格迁移。

技术栈：

FastAPI、Next.js、PostgreSQL、Redis、Qwen-VL、OpenCV、Agent Workflow、Multi-Agent、RAG、Prompt Engineering
