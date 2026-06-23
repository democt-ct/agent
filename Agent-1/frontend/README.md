# 患者智能辅助 Agent — 前端

> React 18 + TypeScript + Vite 前端，通过代理连接后端 FastAPI 服务。

---

## 启动

```bash
# 安装依赖（首次或新增依赖时）
npm install

# 开发模式（:3000 自动代理到 :8000）
npm run dev

# 生产构建
npm run build
```

开发模式访问 `http://localhost:3000`，API 请求自动代理到 `http://127.0.0.1:8000`（详见 `vite.config.ts`）。

---

## 项目结构

```
frontend/
├── src/
│   ├── main.tsx                # 入口
│   ├── App.tsx                 # 根组件（路由 + 布局）
│   ├── context/
│   │   └── AppContext.tsx       # 全局状态（会话、患者、偏好）
│   ├── components/
│   │   ├── Header.tsx          # 顶栏（身份选择 + 导航）
│   │   ├── Sidebar.tsx         # 侧栏（会话列表 + 记忆面板切换）
│   │   ├── ChatPanel.tsx       # 聊天面板（消息流 + 输入框 + SSE 流式）
│   │   ├── PatientPanel.tsx    # 患者信息面板（CRUD + 病历/就诊查询）
│   │   ├── LoginModal.tsx      # 身份登录弹窗
│   │   └── MemoryDebugPanel.tsx # 记忆 Debug 可视化面板
│   ├── services/
│   │   └── api.ts              # API 客户端（患者/记忆/Agent/评估接口）
│   ├── hooks/                  # 自定义 Hooks
│   ├── types/
│   │   └── index.ts            # TypeScript 类型定义
│   └── styles/
│       └── global.css          # 全局样式（~50KB）
├── public/                     # 静态资源
├── index.html                  # HTML 入口
├── vite.config.ts              # Vite 配置（代理、构建）
├── tsconfig.json               # TypeScript 配置
├── eslint.config.js            # ESLint 配置
└── package.json                # 依赖清单
```

---

## 页面路由

| 路径 | 内容 |
|------|------|
| `/` | 聊天主页（ChatPanel + Sidebar） |
| `/evaluate` | 质量评估控制台（由后端 `evaluate.html` 提供） |

---

## 主要依赖

- `react` 18 + `react-dom` 18
- `typescript` 5.x
- `vite` 5.x + `@vitejs/plugin-react`
- `eslint` 9.x（React + TypeScript 规则）

---

## 与后端交互

前端通过 `services/api.ts` 封装以下 API 类别：

| 类别 | 基础路径 | 说明 |
|------|---------|------|
| 患者数据 | `/api/v1/patients` | CRUD 操作 |
| 记忆系统 | `/api/v1/memory` | 画像、消息、偏好、知识块 |
| Agent | `/api/v1/mcp/agent` | 问答（文本/图文/流式） |
| 评估 | `/api/v1/evaluation` | 质量评估用例 |
