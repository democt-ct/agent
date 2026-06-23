# FastAPI Debug Guide
# FastAPI 调试指南

## What this backend does
## 这个后端做什么

- `FastAPI app` - FastAPI 应用，负责接收请求并调用业务逻辑。
- `router` - 路由器，定义 `/health`、`/sessions`、`/requirements`、`/itineraries` 等接口。
- `log_debug_event(...)` - 调试日志输出，打印结构化 JSON 方便排查。
- `uvicorn.out.log` - 标准输出日志，通常看正常流程和调试信息。
- `uvicorn.err.log` - 错误日志，通常看异常堆栈和启动失败原因。

## How to debug
## 如何调试

1. Start the server and watch the logs.
1. 启动服务并观察日志。

```powershell
uvicorn app:app --app-dir fastapi --host 127.0.0.1 --port 9000 --reload
```

2. Open the OpenAPI docs.
2. 打开 OpenAPI 文档。

```text
http://127.0.0.1:9000/docs
```

3. Check `/health` first.
3. 先检查 `/health`。

If `/health` fails, the problem is usually startup, environment, or import related.
如果 `/health` 都失败了，通常是启动、环境变量或导入问题。

4. Then test the request chain in order.
4. 然后按顺序测试请求链路。

- `/sessions` - 会话创建接口
- `/requirements` - 需求创建与解析接口
- `/itineraries` - 行程生成接口
- `/replan` - 重新规划接口

5. Use the debug logs to find the first failing layer.
5. 用调试日志找第一层失败点。

- `"[requirement.parse]"` - 需求解析日志
- `"[candidatePool]"` - 候选点池日志
- `"[planner.anchor]"` - anchor 选择日志
- `"[planner.cluster]"` - cluster 评估日志
- `"[planner.day]"` - 按天分配日志
- `"[plannerRouteEnricher]"` - 路线补全日志

6. If the UI looks wrong, compare the template and static files.
6. 如果页面显示不对，对比模板和静态文件。

- `fastapi/templates/index.html` - 模板页，适合动态渲染
- `fastapi/static/index.html` - 静态页，适合直接打开

## Common checks
## 常见检查

- Confirm `OPENAI_API_KEY` or local model variables are set.
- 确认已经设置 `OPENAI_API_KEY` 或本地模型变量。
- Confirm `DEBUG_DB_PATH` points to the database you expect.
- 确认 `DEBUG_DB_PATH` 指向的是你想调试的数据库。
- Confirm `fastapi/routes.py` is imported by `fastapi/app.py`.
- 确认 `fastapi/app.py` 已经引入 `fastapi/routes.py`。
- Confirm the log output includes the request you just sent.
- 确认日志里有你刚刚发出的那次请求。

## Practical workflow
## 实际调试流程

1. Send one request.
1. 发一个请求。
2. Read the latest log line that starts with the relevant tag.
2. 看对应 tag 的最新日志。
3. Compare request payload, parsed requirement, candidate pool, and final itinerary.
3. 对比请求体、解析后的需求、候选池和最终行程。
4. Narrow the bug to one stage before changing code.
4. 先把问题定位到某一阶段，再去改代码。

