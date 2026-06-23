# Docker 部署指南

## 概述

本项目支持使用 Docker 和 Docker Compose 进行容器化部署。

## 快速开始

### 使用 Docker Compose（推荐）

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

### 手动构建

```bash
# 构建镜像
docker build -t patient-agent .

# 运行容器
docker run -d \
  --name patient-agent \
  -p 8000:8000 \
  -e PG_HOST=your-postgres-host \
  -e PG_PORT=5432 \
  -e PG_USER=postgres \
  -e PG_PASSWORD=your-password \
  -e PG_DATABASE=patient_agent \
  -e REDIS_HOST=your-redis-host \
  -e REDIS_PORT=6379 \
  patient-agent
```

## 服务架构

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Compose                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Patient    │  │  PostgreSQL  │  │    Redis     │  │
│  │    Agent     │  │     DB       │  │    Cache     │  │
│  │   (FastAPI)  │  │              │  │              │  │
│  │   Port 8000  │  │  Port 5432   │  │  Port 6379   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 配置

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PG_HOST` | localhost | PostgreSQL 主机 |
| `PG_PORT` | 5432 | PostgreSQL 端口 |
| `PG_USER` | postgres | PostgreSQL 用户名 |
| `PG_PASSWORD` | postgres | PostgreSQL 密码 |
| `PG_DATABASE` | patient_agent | PostgreSQL 数据库名 |
| `REDIS_HOST` | localhost | Redis 主机 |
| `REDIS_PORT` | 6379 | Redis 端口 |
| `REDIS_DB` | 0 | Redis 数据库 |
| `REDIS_PASSWORD` | None | Redis 密码 |
| `SESSION_CACHE_TTL` | 86400 | 会话缓存过期时间（秒） |
| `LOG_LEVEL` | INFO | 日志级别 |
| `LOG_FORMAT` | text | 日志格式（text/json） |
| `WORKERS` | 1 | 工作进程数 |
| `PORT` | 8000 | 应用端口 |

### 使用环境文件

创建 `.env` 文件：

```bash
# PostgreSQL
PG_HOST=postgres
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=your-secure-password
PG_DATABASE=patient_agent

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# Application
LOG_LEVEL=INFO
LOG_FORMAT=json
WORKERS=2
PORT=8000
```

然后在 docker-compose.yml 中添加：

```yaml
services:
  app:
    env_file:
      - .env
```

## 数据持久化

### PostgreSQL 数据

PostgreSQL 数据存储在 Docker volume `postgres_data` 中。

```bash
# 查看 volume
docker volume ls | grep postgres

# 备份数据
docker exec patient-agent-postgres pg_dump -U postgres patient_agent > backup.sql

# 恢复数据
docker exec -i patient-agent-postgres psql -U postgres patient_agent < backup.sql
```

### Redis 数据

Redis 数据存储在 Docker volume `redis_data` 中。

```bash
# 备份 Redis 数据
docker exec patient-agent-redis redis-cli BGSAVE

# 恢复 Redis 数据
docker cp patient-agent-redis:/data/dump.rdb ./dump.rdb
```

## 健康检查

应用提供两个健康检查端点：

- `/health` - 基础健康检查
- `/health/detailed` - 详细健康检查（包含数据库和 Redis 状态）

```bash
# 基础健康检查
curl http://localhost:8000/health

# 详细健康检查
curl http://localhost:8000/health/detailed
```

## 监控和日志

### 查看日志

```bash
# 实时查看应用日志
docker-compose logs -f app

# 查看最近 100 行日志
docker-compose logs --tail=100 app

# 查看所有服务日志
docker-compose logs
```

### JSON 格式日志

设置环境变量启用 JSON 格式日志：

```bash
LOG_FORMAT=json
```

## 生产环境注意事项

### 安全性

1. **修改默认密码**：
   ```bash
   # PostgreSQL
   PG_PASSWORD=your-very-secure-password
   
   # Redis
   REDIS_PASSWORD=your-redis-password
   ```

2. **限制端口暴露**：
   ```yaml
   services:
     postgres:
       ports: []  # 不暴露端口，只在内部网络访问
     redis:
       ports: []  # 不暴露端口
   ```

3. **使用 Docker secrets**（推荐）：
   ```yaml
   services:
     app:
       environment:
         - PG_PASSWORD_FILE=/run/secrets/pg_password
       secrets:
         - pg_password
   
   secrets:
     pg_password:
       file: ./secrets/pg_password.txt
   ```

### 性能优化

1. **调整工作进程数**：
   ```bash
   WORKERS=4  # 通常设置为 CPU 核心数
   ```

2. **调整数据库连接池**：
   ```bash
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=40
   ```

3. **调整 Redis 连接**：
   ```bash
   REDIS_SOCKET_TIMEOUT=5
   REDIS_CONNECT_TIMEOUT=5
   ```

### 高可用

1. **多副本部署**：
   ```bash
   docker-compose up -d --scale app=3
   ```

2. **使用负载均衡器**（如 Nginx、Traefik）

3. **数据库主从复制**

## 故障排查

### 常见问题

1. **数据库连接失败**：
   ```bash
   docker-compose logs postgres
   ```

2. **Redis 连接失败**：
   ```bash
   docker-compose logs redis
   ```

3. **应用启动失败**：
   ```bash
   docker-compose logs app
   ```

### 进入容器调试

```bash
# 进入应用容器
docker exec -it patient-agent-app bash

# 进入 PostgreSQL 容器
docker exec -it patient-agent-postgres psql -U postgres

# 进入 Redis 容器
docker exec -it patient-agent-redis redis-cli
```

## 更新和回滚

### 更新应用

```bash
# 重新构建并更新
docker-compose up -d --build app

# 或者拉取新镜像
docker-compose pull
docker-compose up -d
```

### 回滚

```bash
# 使用之前的镜像版本
docker-compose up -d --scale app=0
docker-compose up -d app=previous-version
```