# AI Photo Agent 安装与配置指南

## 环境要求

- Python 3.8+
- Node.js 16+
- PostgreSQL 12+
- Redis 6+

## 快速安装

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 安装前端依赖

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
```

### 3. 配置环境变量

复制环境变量示例文件：

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，填写以下配置：

```env
# 数据库配置
DATABASE_URL=postgresql://用户名:密码@localhost:5432/ai_photo_agent

# 魔搭社区API配置（免费视觉模型）
MODELSCOPE_API_TOKEN=你的魔搭API_TOKEN
MODELSCOPE_MODEL_ID=Qwen/Qwen-VL-Chat
```

### 4. 获取魔搭社区API Token

1. 访问 [魔搭社区](https://modelscope.cn/)
2. 注册并登录账号
3. 进入个人中心 -> 访问令牌
4. 创建新的API Token
5. 将Token复制到 `.env` 文件的 `MODELSCOPE_API_TOKEN` 字段

### 5. 初始化数据库

```bash
cd database
psql -U 你的用户名 -d 你的数据库名 -f migrations/001_initial.sql
```

### 6. 启动应用

**启动后端：**

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端（新终端）：**

```bash
cd frontend
npm run dev
```

### 7. 访问应用

- 前端界面: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 配置说明

### 魔搭社区模型配置

- `MODELSCOPE_API_TOKEN`: 魔搭社区API访问令牌
- `MODELSCOPE_MODEL_ID`: 使用的视觉模型ID
  - 推荐: `Qwen/Qwen-VL-Chat` (通义千问视觉模型)
  - 备选: `InternLM/InternVL-Chat` (书生·浦语视觉模型)

### 免费模型说明

魔搭社区提供免费的视觉模型API，每月有免费额度：
- Qwen-VL-Chat: 每月1000次免费调用
- 支持图像理解、描述生成、视觉问答等功能

## 常见问题

### 1. 安装依赖失败

使用国内镜像源：
- Python: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
- Node.js: `npm install --registry=https://registry.npmmirror.com`

### 2. 数据库连接失败

检查PostgreSQL服务是否启动，用户名密码是否正确。

### 3. 模型调用失败

1. 检查API Token是否正确
2. 检查网络连接
3. 确认模型ID是否正确

### 4. 图片上传失败

检查 `UPLOAD_DIR` 目录是否存在，是否有写入权限。