# AI Photo Agent

智能修图助手 - 基于多模态大模型与图像处理技术构建的智能修图系统

## 功能特性

- 📷 图片上传与管理
- 🔍 智能图像分析
- 🎨 一键自动优化
- 🖌️ 手动参数调整
- 🎭 风格预设（电影感、复古风、明亮风、情绪风）
- 📊 前后对比展示

## 技术栈

### 后端
- FastAPI - 高性能Python Web框架
- OpenCV - 图像处理
- SQLAlchemy - ORM数据库操作
- PostgreSQL - 关系型数据库
- Redis - 缓存与消息队列

### 前端
- Next.js - React框架
- TailwindCSS - CSS框架
- Axios - HTTP客户端

## 快速开始

### 环境要求
- Python 3.8+
- Node.js 16+
- PostgreSQL 12+
- Redis 6+

### 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd ai-photo-agent
```

2. 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

3. 安装前端依赖
```bash
cd frontend
npm install
```

4. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件配置数据库等信息
```

5. 初始化数据库
```bash
cd database
psql -U your_user -d your_database -f migrations/001_initial.sql
```

6. 启动应用
```bash
# 启动后端
cd backend
uvicorn app.main:app --reload

# 启动前端（新终端）
cd frontend
npm run dev
```

### 访问地址
- 前端: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 项目结构

```
ai-photo-agent/
├── backend/                # 后端代码
│   ├── app/
│   │   ├── api/           # API路由
│   │   ├── core/          # 核心配置
│   │   ├── models/        # 数据库模型
│   │   ├── services/      # 业务逻辑
│   │   └── utils/         # 工具函数
│   └── requirements.txt
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── components/    # React组件
│   │   ├── pages/         # 页面组件
│   │   └── styles/        # 样式文件
│   └── package.json
├── database/               # 数据库相关
│   └── migrations/        # 数据库迁移
└── docs/                   # 项目文档
```

## API接口

### 图片管理
- `POST /api/v1/images/upload` - 上传图片
- `GET /api/v1/images/{image_id}` - 获取图片
- `DELETE /api/v1/images/{image_id}` - 删除图片

### 图像分析
- `POST /api/v1/analysis/analyze` - 分析图像
- `GET /api/v1/analysis/{image_id}/report` - 获取分析报告

### 图像编辑
- `POST /api/v1/editing/apply` - 应用编辑
- `POST /api/v1/editing/auto-enhance` - 自动增强
- `GET /api/v1/editing/{image_id}/compare` - 对比原图与编辑后

## 开发计划

### 第一阶段（2周）
- [x] 项目初始化
- [x] 基础图像上传
- [x] 图像分析功能
- [x] 自动调色算法
- [ ] 前后对比展示

### 第二阶段（2周）
- [ ] 对话式修图
- [ ] 风格模板库
- [ ] 历史记录

### 第三阶段（3周）
- [ ] 局部修图
- [ ] 批量修图
- [ ] 人像优化

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

MIT License