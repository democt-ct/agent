# 智能旅游规划 Agent 助手 PRD

## 1. 文档信息

- 产品名称：智能旅游规划 Agent 助手
- 文档版本：V1.0
- 文档日期：2026-04-20
- 文档状态：初稿

## 2. 产品背景

旅游规划是一个高决策成本、高信息密度、强个性化的场景。用户在出行前通常需要在多个平台之间来回切换，完成目的地筛选、行程安排、预算控制、交通衔接、酒店筛选、景点取舍、餐饮推荐、签证/天气/注意事项查询等任务。当前主流产品往往只覆盖单点需求，难以形成“从想去到出发”的完整闭环。

随着大模型与 Agent 能力的发展，旅游场景已经具备从“搜索工具”升级为“可对话、可理解偏好、可自动编排行程、可动态调整”的智能助手条件。因此，需要设计一款面向 C 端用户的智能旅游规划 Agent 助手，帮助用户以更低成本完成高质量出行决策。

## 3. 产品目标

### 3.1 产品愿景

成为用户出行前和出行中的“私人旅行规划师”，能够理解用户偏好、约束和变化，自动生成可执行的个性化旅行方案，并在旅途中持续提供动态支持。

### 3.2 核心目标

- 降低用户做旅游攻略的时间成本
- 提升行程规划的个性化和可执行性
- 提供从灵感获取到最终行程确认的一站式体验
- 在用户行程变化时提供动态重规划能力

### 3.3 阶段性目标

#### MVP 阶段

- 支持用户通过自然语言输入需求
- 自动生成多天旅行行程草案
- 支持预算、出行天数、同行人群、兴趣偏好的约束
- 输出交通、住宿、景点、美食、日程建议

#### 成长期

- 接入实时天气、交通、门票、营业时间等数据
- 支持多轮追问和动态修改行程
- 支持收藏、导出、分享、预订跳转

#### 成熟期

- 支持旅行中实时调整
- 支持多城市联程与复杂路线
- 支持会员化和商业化转化

## 4. 用户定义

### 4.1 目标用户

- 自由行用户：希望自主规划，但不想花大量时间查攻略
- 轻度旅游用户：一年出行 1-3 次，希望快速得到可靠方案
- 家庭出游用户：关注老人、小孩、节奏、舒适度和预算
- 情侣/朋友结伴用户：关注体验感、氛围感、拍照、美食和效率
- 商旅延伸用户：出差前后顺便游玩，需要短时间内快速成方案

### 4.2 用户痛点

- 信息分散，需要在多个 App/网站之间切换
- 很难平衡预算、时间、景点密度和交通效率
- 攻略过多但不适合自己，缺少个性化判断
- 行程改动频繁，手动调整成本高
- 不清楚哪些安排“看起来好但实际上不可执行”

## 5. 核心使用场景

### 场景 1：出游灵感阶段

用户还没决定去哪，只知道预算、假期时长和兴趣方向，希望系统推荐合适目的地和大致玩法。

### 场景 2：确定目的地后的详细规划

用户已经确定城市/国家，希望快速生成完整的 3 天、5 天或 7 天行程。

### 场景 3：已有草案后的优化

用户已有初步计划，希望 Agent 帮助压缩预算、减少奔波、增加适合拍照/亲子/美食的安排。

### 场景 4：出行中动态调整

因天气、晚点、疲劳、临时兴趣变化，需要快速重排当日或后续行程。

## 6. 产品定位

智能旅游规划 Agent 助手不是单纯的攻略搜索器，也不是纯模板型行程生成器，而是一个能够：

- 理解用户意图和约束
- 主动追问关键缺失信息
- 自动拆解任务并输出完整方案
- 根据变化进行动态重规划
- 提供理由说明和备选方案

的智能规划系统。

## 7. 核心功能设计

### 7.1 智能需求采集

#### 功能描述

通过对话方式采集用户需求，识别并补全关键信息。

#### 输入维度

- 出发地/目的地
- 出行时间
- 行程天数
- 预算范围
- 同行人群
- 兴趣偏好
- 出行节奏
- 酒店偏好
- 餐饮偏好
- 特殊限制：如带老人、带儿童、无障碍、避免打车、低强度行程等

#### 关键能力

- 自动识别缺失字段并追问
- 将模糊表达结构化，如“不要太累”“想吃本地特色”“预算有限”
- 支持中途修改需求并同步更新规划

### 7.2 行程自动生成

#### 功能描述

根据用户输入生成可执行的旅行计划。

#### 输出内容

- 每日主题
- 上午/下午/晚间安排
- 景点顺序与停留时长建议
- 城市内交通建议
- 酒店选址建议
- 美食/餐饮建议
- 预算拆分
- 注意事项

#### 输出形式

- 文本版攻略
- 卡片版日程
- 地图线路版
- 可导出的行程单

### 7.3 智能优化与重规划

#### 功能描述

用户可对现有行程提出优化诉求，系统自动重排。

#### 常见优化指令

- 太赶了，帮我轻松一点
- 预算超了，帮我压到 3000 元以内
- 想加一个适合拍照的地方
- 第三天下雨，重排一下
- 去掉太热门排队久的景点

#### 关键能力

- 保留用户已确认偏好
- 局部修改，不强制推翻全部方案
- 明确提示调整影响，如预算变化、交通增加、体验变化

### 7.4 目的地推荐

#### 功能描述

当用户尚未决定去哪里时，基于预算、时间、季节和兴趣给出推荐。

#### 推荐维度

- 性价比
- 季节适配度
- 飞行/高铁便利度
- 适合人群
- 热门程度
- 风格标签：海岛、城市漫游、自然风光、文化历史、美食之旅等

### 7.5 旅行知识与提醒

#### 功能描述

补充旅行决策中高频但容易遗漏的信息。

#### 典型内容

- 天气与穿衣建议
- 签证/证件提醒
- 当地交通方式
- 营业时间与预约建议
- 节假日拥挤风险
- 当地风俗和注意事项

### 7.6 收藏、导出与分享

#### 功能描述

支持用户保存结果并用于后续执行。

#### 主要能力

- 收藏目的地/方案
- 导出 PDF 或图片行程单
- 生成分享链接
- 同行人协同查看

## 8. 用户流程

### 8.1 主流程

1. 用户进入产品首页
2. 选择“我想去哪”或“帮我推荐去哪”
3. 通过对话输入旅行需求
4. 系统补问关键信息
5. Agent 自动生成旅行方案
6. 用户查看并进行修改/细化
7. 用户确认并保存/导出行程
8. 出行中按需继续调用 Agent 做动态调整

### 8.2 对话式体验原则

- 先理解约束，再给方案
- 先给可用版本，再逐步细化
- 每轮输出都应可执行，而不是泛泛而谈
- 对关键决策给出理由，增强用户信任
- 避免一次性输出过长内容，支持分块展开

## 9. MVP 范围

### 9.1 必做功能

- 对话式需求采集
- 目的地推荐
- 单目的地多天行程生成
- 预算约束
- 人群偏好适配
- 行程修改与重生成
- 行程保存

### 9.2 暂不纳入 MVP

- 实时预订闭环
- 多人协同编辑
- 国际签证全流程办理
- 实时语音导游
- 复杂多国联程规划

## 10. 非功能需求

### 10.1 可用性

- 首次生成行程时间尽量控制在 10 秒内
- 修改指令响应时间尽量控制在 5 秒内
- 结果表达清晰，适合移动端阅读

### 10.2 准确性

- 行程安排需避免明显地理冲突和时间冲突
- 景点营业时间、交通时间、天气等动态信息需标注来源时间
- 对不确定信息需明确提示，不伪造事实

### 10.3 个性化

- 支持基于历史偏好持续优化推荐
- 支持用户画像沉淀，如预算习惯、节奏偏好、兴趣标签

### 10.4 安全与合规

- 用户个人信息需加密存储
- 涉及定位、行程等敏感信息时需明确授权
- 输出内容应规避虚假预订、过度承诺和安全风险建议
- 考虑后续部署在 Cloudflare 平台，持久化数据方案需优先兼容 Cloudflare D1，避免强依赖传统自建数据库能力

## 11. 关键指标

### 11.1 北极星指标

- 用户成功生成并保存旅行方案的比例

### 11.2 核心业务指标

- 行程生成完成率
- 行程保存率
- 二次编辑率
- 7 日留存率
- 用户满意度评分
- 平均单次规划时长下降比例

### 11.3 质量指标

- 用户反馈“行程太赶/不可执行”的比例
- 动态重规划成功率
- 推荐点击率
- 用户人工修改幅度

## 12. 竞品与差异化方向

### 12.1 典型竞品类型

- OTA 平台的攻略/路线推荐功能
- 地图类产品的路线规划功能
- 通用大模型对话助手
- 独立旅游攻略社区

### 12.2 差异化方向

- 更强的个性化约束理解能力
- 从“推荐内容”升级到“可执行方案”
- 支持动态修改而不是一次性静态输出
- 提供“为什么这么安排”的解释能力
- 形成旅行前、中、后的连续服务链路

## 13. 商业化设想

- 会员订阅：高级规划、无限次重排、深度攻略包
- 联盟分佣：酒店、门票、当地玩乐、保险、接送机
- B2B 合作：与旅行社、酒店集团、旅游平台合作提供智能助手能力
- 企业服务：商旅出行和会奖旅游行程规划

## 14. 风险与挑战

- 动态旅游数据接入复杂，数据一致性要求高
- 大模型在地理、时间和事实性约束上可能出现幻觉
- 过长输出可能导致用户阅读负担高
- 用户需求高度个性化，标准化产品设计难度大
- 若缺乏真实预订与履约能力，闭环价值有限

## 15. 产品迭代路线图

### Phase 1：MVP

- 完成需求采集、目的地推荐、行程生成、基础重排、保存导出

### Phase 2：增强版

- 接入天气、地图、POI、营业时间、交通等外部数据
- 加强地图可视化与预算可视化
- 支持行程模板和个性化画像
- 完成面向 Cloudflare 部署的数据库层适配，核心结构化数据落地到 D1

### Phase 3：智能出行助手

- 支持旅行中实时调整
- 支持通知提醒
- 支持多城市复杂联程
- 接入预订闭环和商业化能力

## 16. 附录：示例用户故事

### 用户故事 1

作为一名上班族，我只有五一前后 4 天假期，预算 4000 元，希望去一个风景好、拍照出片、不要太累的地方，这样我能快速获得适合自己的旅行方案。

### 用户故事 2

作为一名家庭用户，我带 1 个老人和 1 个孩子出行，希望行程节奏慢、酒店位置方便、餐饮适合全家，这样我可以减少安排风险。

### 用户故事 3

作为一名自由行用户，如果旅行中第三天下雨，我希望 Agent 能快速调整当天安排并说明原因，这样我不用重新做全部攻略。

## 17. 给研发团队的产品建议

- 前端优先采用聊天式交互 + 卡片化结果展示
- 后端将需求解析、行程生成、数据查询、重规划拆成独立 Agent/工作流模块
- 对核心事实信息设置校验层，降低模型幻觉风险
- 所有行程结果应具备结构化输出能力，便于地图、预算、导出等模块复用
- 需明确技术选型约束：产品后续计划部署到 Cloudflare，数据库优先采用 D1；研发阶段的数据访问层、迁移脚本和表结构设计需围绕 D1 能力边界实现
- 预留外部数据接口层，后续方便接入 OTA、地图、天气和票务系统

## 18. 第一阶段实施建议

### 18.1 第一步要先实现什么

第一步应优先实现“需求采集 + 会话存储 + D1 数据底座”的最小可用闭环，而不是直接追求复杂的 Agent 行程生成能力。

原因如下：

- 后续所有能力，包括需求补问、行程生成、重规划、收藏保存，都会依赖统一的会话和结构化数据模型
- 产品后续计划部署在 Cloudflare，需尽早按 D1 能力边界设计表结构、读写方式和迁移方案，避免后期返工
- 先打通数据闭环后，可以先用规则或模板生成草案，再逐步替换为大模型/Agent，提高迭代效率

### 18.2 第一步的目标

- 用户发起一次新的旅游规划会话
- 用户提交旅行需求
- 系统将需求结构化并写入 D1
- 系统返回一份可展示、可保存、可继续编辑的行程草案

### 18.3 第一步的技术任务清单

#### 任务 1：搭建 Cloudflare 兼容运行底座

- 明确运行环境为 Cloudflare Workers 或 Cloudflare Pages Functions
- 建立本地开发、预发、生产的环境配置方式
- 配置 D1 数据库绑定与基础访问方式
- 建立数据库 migration 管理机制

#### 任务 2：设计 D1 数据模型

- 明确用户、匿名访客、会话、需求、行程草案之间的关系
- 区分“用户原始输入”和“结构化解析结果”
- 区分“当前生效版本”和“历史版本”，为后续重规划留空间
- 对复杂字段采用 JSON 存储，但关键查询字段应结构化落表

#### 任务 3：实现基础后端接口

- 创建规划会话
- 保存用户需求原文
- 保存结构化需求
- 获取当前会话详情
- 保存行程草案
- 获取最新行程草案

#### 任务 4：实现最小可用草案生成器

- 初期可不接大模型，先用模板/规则输出一份演示型草案
- 输出格式需与未来 Agent 生成结果保持一致或尽量兼容
- 确保前端可以直接消费并展示结果

#### 任务 5：验证最小闭环

- 验证一次完整流程：创建会话 -> 提交需求 -> 写入 D1 -> 生成草案 -> 返回展示
- 验证会话刷新后仍可读取历史需求与草案
- 验证后续继续编辑需求时，可在原会话上追加版本

### 18.4 第一阶段暂时不要优先做的内容

- 不优先接入复杂多 Agent 编排
- 不优先做实时天气、地图、门票等外部数据接入
- 不优先做多人协同、分享编辑、预订闭环
- 不优先做复杂推荐算法和个性化画像系统

## 19. D1 数据库草案

### 19.1 建议的核心表

#### 1）users

用途：存储注册用户信息；如果 MVP 阶段暂不做登录，可先保留表结构或使用匿名 visitor 替代。

建议字段：

- id
- status
- nickname
- created_at
- updated_at

#### 2）visitors

用途：支持未登录用户或匿名会话。

建议字段：

- id
- device_fingerprint
- created_at
- updated_at

#### 3）sessions

用途：记录一次旅游规划会话，是后续需求、草案、重规划的主关联对象。

建议字段：

- id
- user_id
- visitor_id
- title
- status
- source
- current_requirement_version
- current_itinerary_version
- created_at
- updated_at

#### 4）trip_requirements

用途：保存一次会话下的需求版本，可同时保存原始文本和结构化结果。

建议字段：

- id
- session_id
- version
- raw_input
- origin_city
- destination
- start_date
- end_date
- trip_days
- budget_min
- budget_max
- travelers_summary
- interests_json
- constraints_json
- structured_payload_json
- created_at

#### 5）itinerary_drafts

用途：保存行程草案及其版本，用于首次生成、修改、重规划。

建议字段：

- id
- session_id
- requirement_id
- version
- status
- title
- summary
- itinerary_json
- budget_estimate_json
- warnings_json
- generator_type
- created_at
- updated_at

#### 6）conversation_messages

用途：保存会话中的用户消息与系统回复，为后续 Agent 补问、上下文回放和调试提供依据。

建议字段：

- id
- session_id
- role
- message_type
- content
- metadata_json
- created_at

### 19.2 D1 设计原则

- 关键筛选字段结构化：如 `session_id`、`version`、`status`、出发地、目的地、日期、预算等
- 高变动或复杂嵌套数据使用 JSON 字段保存，如兴趣标签、约束条件、日程详情、预算拆分
- 所有可重写对象尽量保留版本号，不直接覆盖旧数据
- 所有表统一保留 `created_at`、必要时保留 `updated_at`
- MVP 阶段优先追求可维护和可迭代，不必一开始过度范式化

### 19.3 推荐的第一批接口

- `POST /sessions`：创建会话
- `GET /sessions/:id`：获取会话概览
- `POST /sessions/:id/requirements`：提交需求并生成结构化记录
- `GET /sessions/:id/requirements/latest`：获取最新需求版本
- `POST /sessions/:id/itineraries`：生成并保存一版草案
- `GET /sessions/:id/itineraries/latest`：获取最新草案
- `POST /sessions/:id/messages`：追加对话消息

### 19.4 推荐的实现顺序

1. 先建 `sessions`
2. 再建 `trip_requirements`
3. 再建 `itinerary_drafts`
4. 最后补 `conversation_messages`

这样可以最短路径跑通 MVP 的“需求采集 -> 草案生成 -> 保存读取”闭环。

### 19.5 D1 建表 SQL 草案

以下为面向 Cloudflare D1 的 MVP 建表草案，优先满足“会话、需求、草案、消息”四类核心数据读写。

```sql
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  visitor_id TEXT,
  title TEXT NOT NULL DEFAULT '新的旅行规划',
  status TEXT NOT NULL DEFAULT 'active',
  source TEXT NOT NULL DEFAULT 'web',
  current_requirement_version INTEGER NOT NULL DEFAULT 0,
  current_itinerary_version INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_visitor_id ON sessions(visitor_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

CREATE TABLE IF NOT EXISTS trip_requirements (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  raw_input TEXT NOT NULL,
  origin_city TEXT,
  destination TEXT,
  start_date TEXT,
  end_date TEXT,
  trip_days INTEGER,
  budget_min INTEGER,
  budget_max INTEGER,
  travelers_summary TEXT,
  interests_json TEXT,
  constraints_json TEXT,
  structured_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trip_requirements_session_version
  ON trip_requirements(session_id, version);
CREATE INDEX IF NOT EXISTS idx_trip_requirements_destination
  ON trip_requirements(destination);
CREATE INDEX IF NOT EXISTS idx_trip_requirements_start_date
  ON trip_requirements(start_date);

CREATE TABLE IF NOT EXISTS itinerary_drafts (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  title TEXT NOT NULL,
  summary TEXT,
  itinerary_json TEXT NOT NULL,
  budget_estimate_json TEXT,
  warnings_json TEXT,
  generator_type TEXT NOT NULL DEFAULT 'template',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (requirement_id) REFERENCES trip_requirements(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_itinerary_drafts_session_version
  ON itinerary_drafts(session_id, version);
CREATE INDEX IF NOT EXISTS idx_itinerary_drafts_requirement_id
  ON itinerary_drafts(requirement_id);
CREATE INDEX IF NOT EXISTS idx_itinerary_drafts_status
  ON itinerary_drafts(status);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  message_type TEXT NOT NULL DEFAULT 'text',
  content TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_session_id
  ON conversation_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at
  ON conversation_messages(created_at);
```

### 19.6 字段约定建议

- `id` 统一使用字符串主键，推荐 `UUID` 或 `cuid`
- 时间字段统一使用 ISO 8601 字符串，便于 Cloudflare Worker 和前端直接处理
- `interests_json`、`constraints_json`、`structured_payload_json`、`itinerary_json`、`budget_estimate_json`、`warnings_json`、`metadata_json` 均以 JSON 字符串形式保存
- `status` 建议使用有限枚举值，如 `active`、`archived`、`draft`、`confirmed`
- `generator_type` 可用于区分 `template`、`llm`、`agent`

## 20. API 路由清单草案

### 20.1 `POST /sessions`

用途：创建一次新的旅游规划会话。

请求体建议：

```json
{
  "user_id": "optional-user-id",
  "visitor_id": "optional-visitor-id",
  "title": "五一杭州 4 天旅行"
}
```

响应体建议：

```json
{
  "id": "sess_001",
  "title": "五一杭州 4 天旅行",
  "status": "active",
  "current_requirement_version": 0,
  "current_itinerary_version": 0,
  "created_at": "2026-04-20T10:00:00Z"
}
```

### 20.2 `GET /sessions/:id`

用途：获取会话概览，用于页面初始化和恢复上下文。

响应体建议：

```json
{
  "id": "sess_001",
  "title": "五一杭州 4 天旅行",
  "status": "active",
  "current_requirement_version": 1,
  "current_itinerary_version": 1,
  "latest_requirement_id": "req_001",
  "latest_itinerary_id": "iti_001",
  "created_at": "2026-04-20T10:00:00Z",
  "updated_at": "2026-04-20T10:05:00Z"
}
```

### 20.3 `POST /sessions/:id/messages`

用途：追加用户消息或系统消息，保留对话上下文。

请求体建议：

```json
{
  "role": "user",
  "message_type": "text",
  "content": "我想五一去杭州玩 4 天，预算 4000 元，不要太累。",
  "metadata": {
    "client_ts": "2026-04-20T10:01:00Z"
  }
}
```

响应体建议：

```json
{
  "id": "msg_001",
  "session_id": "sess_001",
  "role": "user",
  "message_type": "text",
  "content": "我想五一去杭州玩 4 天，预算 4000 元，不要太累。",
  "created_at": "2026-04-20T10:01:01Z"
}
```

### 20.4 `POST /sessions/:id/requirements`

用途：提交用户需求，并保存一版结构化需求。

请求体建议：

```json
{
  "raw_input": "我想五一去杭州玩 4 天，预算 4000 元，不要太累，适合拍照。",
  "structured_payload": {
    "origin_city": "上海",
    "destination": "杭州",
    "start_date": "2026-05-01",
    "trip_days": 4,
    "budget_min": 0,
    "budget_max": 4000,
    "interests": ["拍照", "城市漫游"],
    "constraints": ["不要太累"]
  }
}
```

响应体建议：

```json
{
  "id": "req_001",
  "session_id": "sess_001",
  "version": 1,
  "origin_city": "上海",
  "destination": "杭州",
  "trip_days": 4,
  "budget_max": 4000,
  "created_at": "2026-04-20T10:02:00Z"
}
```

### 20.5 `GET /sessions/:id/requirements/latest`

用途：获取最新一版结构化需求。

响应体建议：

```json
{
  "id": "req_001",
  "session_id": "sess_001",
  "version": 1,
  "raw_input": "我想五一去杭州玩 4 天，预算 4000 元，不要太累，适合拍照。",
  "structured_payload": {
    "origin_city": "上海",
    "destination": "杭州",
    "start_date": "2026-05-01",
    "trip_days": 4,
    "budget_max": 4000,
    "interests": ["拍照", "城市漫游"],
    "constraints": ["不要太累"]
  }
}
```

### 20.6 `POST /sessions/:id/itineraries`

用途：基于最新需求生成并保存一版行程草案。

请求体建议：

```json
{
  "requirement_id": "req_001",
  "generator_type": "template"
}
```

响应体建议：

```json
{
  "id": "iti_001",
  "session_id": "sess_001",
  "requirement_id": "req_001",
  "version": 1,
  "status": "draft",
  "title": "杭州 4 天轻松拍照行程",
  "summary": "适合五一假期的低强度城市漫游路线。",
  "generator_type": "template",
  "created_at": "2026-04-20T10:03:00Z"
}
```

### 20.7 `GET /sessions/:id/itineraries/latest`

用途：获取最新一版行程草案。

响应体建议：

```json
{
  "id": "iti_001",
  "session_id": "sess_001",
  "version": 1,
  "status": "draft",
  "title": "杭州 4 天轻松拍照行程",
  "summary": "适合五一假期的低强度城市漫游路线。",
  "itinerary": {
    "days": [
      {
        "day": 1,
        "theme": "西湖经典线",
        "items": [
          { "time": "上午", "name": "断桥-白堤漫步" },
          { "time": "下午", "name": "湖滨商圈休闲" }
        ]
      }
    ]
  },
  "warnings": ["五一期间热门景点可能拥挤"]
}
```

### 20.8 API 设计原则

- 所有“可编辑对象”都使用版本递增，而不是直接覆盖旧记录
- `POST /sessions/:id/requirements` 不要求一开始就完全结构化，可先保存原文，再补结构化字段
- `POST /sessions/:id/itineraries` 初期可由模板生成器实现，后续平滑替换为 LLM/Agent
- 所有列表和详情接口都应优先返回当前版本号，方便前端做状态同步

## 21. 三阶段开发计划

### 21.1 总体原则

后续研发按“三阶段递进”推进，先完成数据闭环，再完成可演示闭环，最后再接入真实 Agent 能力。这样可以降低返工风险，并保证 Cloudflare + D1 的基础架构优先稳定。

### 21.2 Phase A：数据闭环

目标：先把会话、需求、草案的存储与读取跑通，为后续所有智能能力提供稳定底座。

本阶段必须完成：

- 建立 Cloudflare D1 的基础 schema 与 migration
- 完成 `sessions`、`trip_requirements`、`itinerary_drafts` 三张核心表
- 实现基础数据访问层，统一封装增删改查
- 实现以下 API：
- `POST /sessions`
- `GET /sessions/:id`
- `POST /sessions/:id/requirements`
- `GET /sessions/:id/requirements/latest`
- `POST /sessions/:id/itineraries`
- `GET /sessions/:id/itineraries/latest`

本阶段交付标准：

- 可以创建一个新的旅行规划会话
- 可以保存一版需求
- 可以保存一版行程草案
- 刷新页面或重新请求后，仍能正确读取最新版本
- 所有数据都已落到 D1

建议代码结构：

- `db/`：D1 连接、schema、migration
- `repositories/`：`sessionRepository`、`requirementRepository`、`itineraryRepository`
- `routes/` 或 `api/`：会话、需求、草案接口
- `types/`：请求响应 DTO 与领域模型

本阶段暂不处理：

- 大模型接入
- 多轮补问
- 实时外部数据
- 多 Agent 编排

### 21.3 Phase B：伪智能闭环

目标：在不依赖真实 LLM 的前提下，先把“需求 -> 草案”的产品流程跑通，形成一个可演示、可联调的 MVP。

本阶段必须完成：

- 新增模板型或规则型 itinerary 生成器
- 将用户输入需求转成基本结构化字段
- 在 `POST /sessions/:id/itineraries` 中接入模板生成逻辑
- 为前端返回统一格式的 itinerary 数据结构
- 增加 `conversation_messages` 表和 `POST /sessions/:id/messages`

本阶段交付标准：

- 用户输入一句自然语言需求后，系统可生成一版可展示的旅行草案
- 草案内容虽然不是 AI 智能生成，但格式上已与未来真实 Agent 输出保持兼容
- 前后端可完成完整联调：创建会话、提交需求、生成草案、查看历史消息

建议新增模块：

- `services/requirement-parser`：将原始输入转成基础结构化字段
- `services/itinerary-generator`：模板生成器
- `repositories/messageRepository`

本阶段暂不处理：

- 复杂推理
- 自动补问决策
- 动态重规划
- 外部数据校验

### 21.4 Phase C：真实 Agent

目标：在已有 D1 数据底座和 API 稳定的前提下，逐步替换模板逻辑，接入真实 LLM / Agent 工作流。

本阶段必须完成：

- 接入 LLM 做需求结构化提取
- 支持根据缺失字段触发补问
- 接入真实 itinerary 生成能力
- 支持对现有草案进行重规划或局部修改
- 为关键事实信息增加校验或来源标记

本阶段交付标准：

- 用户可通过多轮对话逐步补全需求
- 系统可生成较高质量、可解释的旅行方案
- 行程可基于新约束进行增量调整，而不是每次完全重建
- 重要动态信息具备时间或来源标记

建议新增模块：

- `services/llm/`
- `services/agent-workflow/`
- `services/replanner/`
- `services/fact-checker/`

### 21.5 三阶段对应的代码优先级

优先级 1：

- `schema.sql` 或 migration 文件
- `sessions` / `trip_requirements` / `itinerary_drafts` 表
- 基础 repository
- 基础 API 路由

优先级 2：

- 模板生成器
- 基础结构化解析器
- `conversation_messages`
- 前端联调所需的响应格式稳定化

优先级 3：

- LLM 需求解析
- Agent 补问
- 重规划能力
- 外部事实校验与数据接入

### 21.6 立刻开始时先做什么

如果现在开始编码，第一批实现内容应固定为以下顺序：

1. 写 D1 schema 和 migration
2. 写 `sessions` repository 和创建/查询接口
3. 写 `trip_requirements` repository 和保存/读取接口
4. 写 `itinerary_drafts` repository 和保存/读取接口
5. 用模板逻辑临时实现 `POST /sessions/:id/itineraries`

这 5 步完成后，就已经具备后续围绕 Cloudflare + D1 持续扩展的主干代码结构。
