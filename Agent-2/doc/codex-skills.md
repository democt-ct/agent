# Codex Skills 说明

Codex 安装路径：`~/.codex/skills/`

---

## 用户安装的 Skill（5 个）

### 1. frontend-design
- **大小：** 8K
- **功能：** 创建高质量、生产级别的前端界面，避免通用 AI 风格，生成有创意、精致的代码
- **触发场景：** 构建 Web 组件、页面或应用时

### 2. impeccable
- **版本：** 2.1.1
- **大小：** 92K
- **功能：** 高级前端设计 skill，支持三种模式：
  - `craft` — 先定形状再构建
  - `teach` — 设计上下文设置
  - `extract` — 提取可复用组件和 token 到设计系统
- **触发场景：** 构建 Web 组件、页面、海报、应用，或需要设计项目管理时

### 3. notebooklm-skill
- **大小：** 317K
- **功能：** 从 Claude Code 直接查询 Google NotebookLM 笔记本，获取基于文档、带引用的 Gemini 回答。支持浏览器自动化、库管理、持久化认证
- **特点：** 通过限定文档来源大幅减少幻觉
- **包含：** 认证文档、更新日志、图片资源、Python 脚本

### 4. planning-with-files
- **版本：** 2.34.1
- **大小：** 80K
- **功能：** Manus 风格的文件式任务规划，生成三个文件：
  - `task_plan.md` — 阶段划分、进度追踪、决策记录
  - `findings.md` — 研究发现和调查结果
  - `progress.md` — 会话日志和测试结果
- **触发场景：** 多步骤项目、研究任务、需要 5+ 次工具调用的工作
- **特点：** 支持 `/clear` 后自动恢复会话上下文
- **包含：** 模板、脚本（init-session、check-complete、session-catchup）

### 5. skill-creator
- **大小：** 256K
- **功能：** 创建、修改、优化和评估 skill 性能
  - 从零创建 skill
  - 编辑已有 skill
  - 运行 evals 测试 skill
  - 性能基准测试和方差分析
  - 优化 skill 描述以提高触发准确率
- **包含：** agents、assets、eval-viewer、references、scripts

---

## 系统内置 Skill（4 个）

位于 `~/.codex/skills/.system/`

### 1. imagegen
- **功能：** 生成或编辑位图图像（照片、插图、纹理、sprites、mockup、透明背景切图等）
- **注意：** 适用于需要 AI 创建新图像的场景，不适合编辑现有 SVG/矢量图

### 2. openai-docs
- **功能：** 查询 OpenAI 产品和 API 的官方文档（带引用）、帮助选择最新模型、模型升级和 prompt 迁移指导

### 3. plugin-creator
- **功能：** 创建 Codex 插件目录结构，生成 `.codex-plugin/plugin.json` 及相关配置文件

### 4. skill-installer
- **功能：** 从官方精选列表或 GitHub 仓库安装 Codex skill（包括私有仓库）

---

## 目录结构

```
~/.codex/skills/
├── .system/                  # 系统内置 skill
│   ├── imagegen/
│   ├── openai-docs/
│   ├── plugin-creator/
│   └── skill-installer/
├── frontend-design/          # 前端设计
├── impeccable/               # 高级前端设计
├── notebooklm-skill/         # NotebookLM 查询
├── planning-with-files/      # 文件式任务规划
└── skill-creator/            # Skill 创建工具
```

## 如何安装新的 Skill

使用 `skill-installer` skill 来安装新 skill，支持从 GitHub 仓库或精选列表安装。
