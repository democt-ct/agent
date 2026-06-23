# PostgreSQL 和 Redis 配置指南

## 概述

本项目使用 PostgreSQL 作为主数据库，Redis 作为会话缓存，以支持生产级部署。

## 快速开始

### 方式一：使用 Docker Compose（推荐）

```bash
# 启动服务
python scripts/setup_services.py start

# 查看状态
python scripts/setup_services.py status

# 停止服务
python scripts/setup_services.py stop
```

### 方式二：手动安装

#### PostgreSQL

1. 安装 PostgreSQL 15+
2. 创建数据库：
   ```sql
   CREATE DATABASE patient_agent;
   ```
3. 配置连接信息（见下方配置部分）

#### Redis

1. 安装 Redis 7+
2. 启动 Redis 服务
3. 配置连接信息（见下方配置部分）

## 配置

### 环境变量

可以通过环境变量配置数据库连接：

```bash
# PostgreSQL
export PG_HOST=localhost
export PG_PORT=5432
export PG_USER=postgres
export PG_PASSWORD=postgres
export PG_DATABASE=patient_agent

# Redis
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=

# 或使用 URL 格式
export REDIS_URL=redis://localhost:6379/0

# 会话缓存过期时间（秒）
export SESSION_CACHE_TTL=86400
```

### 本地配置文件

1. 复制配置文件：
   ```bash
   cp app/mcp/local_settings.postgres.py app/mcp/local_settings.py
   ```

2. 编辑 `app/mcp/local_settings.py`，修改数据库连接信息。

## 初始化数据库

```bash
# 运行初始化脚本
python scripts/init_postgres.py
```

这将：
1. 创建数据库（如果不存在）
2. 创建所有必要的表

## 验证安装

```bash
# 检查 PostgreSQL 连接
python -c "import psycopg2; conn = psycopg2.connect(host='localhost', dbname='patient_agent'); print('PostgreSQL OK')"

# 检查 Redis 连接
python -c "import redis; r = redis.Redis(); r.ping(); print('Redis OK')"
```

## 生产环境注意事项

1. **安全性**：
   - 修改默认密码
   - 配置防火墙规则
   - 使用 SSL 连接

2. **性能优化**：
   - 调整 PostgreSQL 连接池大小
   - 配置 Redis 持久化
   - 监控系统资源

3. **备份策略**：
   - 定期备份 PostgreSQL 数据
   - 配置 Redis 持久化（RDB/AOF）

4. **高可用**：
   - 考虑 PostgreSQL 主从复制
   - Redis Sentinel 或 Cluster

## 故障排查

### PostgreSQL 连接失败

```bash
# 检查 PostgreSQL 服务状态
sudo systemctl status postgresql

# 查看日志
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

### Redis 连接失败

```bash
# 检查 Redis 服务状态
sudo systemctl status redis-server

# 测试连接
redis-cli ping
```

## 迁移指南

如果之前使用 SQLite，需要将数据迁移到 PostgreSQL：

1. 导出 SQLite 数据
2. 转换格式
3. 导入 PostgreSQL

详细的迁移脚本请参考项目 Git 历史中的 `scripts/migrate_sqlite_to_pg.py`（如果需要）。