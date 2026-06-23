# Agent 运行与端口排查

这份文档记录当前项目里最常用的本地启动、停止和端口排查方式，默认以 Windows PowerShell 为准。

## 当前项目里常见的两个服务

- `FastAPI Agent`
  - 目录：`D:\zhuomian\Agent-2\fastapi`
  - 默认端口：`9000`
  - 页面入口：`http://127.0.0.1:9000`
  - 健康检查：`http://127.0.0.1:9000/health`
- `Cloudflare Worker 本地调试`
  - 项目根目录：`D:\zhuomian\Agent-2`
  - 常见端口：`8787`
  - 启动命令：`npx.cmd wrangler dev`

## 运行当前 Agent

当前通常指本地 FastAPI 版本，也就是浏览器里直接打开 `9000` 的这一套。

### 1. 安装 Python 依赖

```powershell
cd D:\zhuomian\Agent-2
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r fastapi\requirements.txt
```

### 2. 设置模型环境变量

如果你走本地模型，可以先设置：

```powershell
$env:TEXT_API_KEY="ollama"
$env:TEXT_API_BASE="http://127.0.0.1:11434/v1/"
$env:TEXT_MODEL="modelscope.cn/unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF:latest"
```

如果你用别的兼容 OpenAI 接口，只需要把上面三个值改成自己的服务地址和模型名。

### 3. 启动 FastAPI Agent

开发调试时：

```powershell
uvicorn app:app --app-dir fastapi --host 127.0.0.1 --port 9000 --reload
```

如果你只是想稳定跑一份，不需要热更新，建议去掉 `--reload`：

```powershell
uvicorn app:app --app-dir fastapi --host 127.0.0.1 --port 9000
```

`--reload` 会多起一层监控进程，端口占用排查时更容易出现父子进程一起挂着的情况。

### 4. 确认是否启动成功

浏览器打开：

```text
http://127.0.0.1:9000
```

或者直接测健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:9000/health | Select-Object -ExpandProperty Content
```

也可以检查端口：

```powershell
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 9000 } | Select-Object LocalAddress,LocalPort,OwningProcess,State
```

## 停止当前 Agent

### 前台运行时

如果服务就是在当前 PowerShell 窗口里跑的，直接：

```powershell
Ctrl + C
```

### 后台或别的终端里运行时

先查 PID：

```powershell
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 9000 } | Select-Object LocalAddress,LocalPort,OwningProcess,State
```

然后结束进程：

```powershell
taskkill /PID 12345 /T /F
```

把 `12345` 替换成你查到的 `OwningProcess`。

`/T` 会连子进程一起结束，`uvicorn --reload` 时建议一定带上。

## 多端口占用时怎么查

如果你遇到：

```text
[Errno 10048] Only one usage of each socket address...
```

一般就是端口已经被别的进程占了。

### 查单个端口

查 `9000`：

```powershell
netstat -ano | findstr :9000
```

查 `8787`：

```powershell
netstat -ano | findstr :8787
```

### 同时查多个常用端口

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object { $_.LocalPort -in 9000,8787,8000 } |
  Select-Object LocalAddress,LocalPort,OwningProcess,State
```

### 看 PID 对应的进程

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.ProcessId -in 12345,23456 } |
  Select-Object ProcessId,Name,CommandLine
```

注意：上面这一条里的 `12345,23456` 只是示例 PID，不是端口号。实际使用时要换成你查出来的进程 PID。

## 多端口占用时怎么关闭

### 方式 1：按 PID 精确关闭

```powershell
taskkill /PID 12345 /T /F
```

如果还有别的 PID：

```powershell
taskkill /PID 23456 /T /F
taskkill /PID 34567 /T /F
```

### 方式 2：先查再批量关闭常用端口对应进程

```powershell
$ports = 9000,8787,8000
$pids = Get-NetTCPConnection -State Listen |
  Where-Object { $_.LocalPort -in $ports } |
  Select-Object -ExpandProperty OwningProcess -Unique

$pids
```

确认 PID 没问题后再逐个结束：

```powershell
foreach ($pid in $pids) {
  taskkill /PID $pid /T /F
}
```

### 方式 3：如果是 `uvicorn --reload`

`--reload` 常见情况是：

- 一个 Python 进程负责监听
- 一个子进程负责实际服务

这时只关掉其中一个，端口可能还在。最稳的做法是直接对查到的 PID 使用：

```powershell
taskkill /PID 12345 /T /F
```

也就是一定带 `/T`。

## 遇到“端口还在，但 PID 看起来不存在”怎么办

这个项目里已经遇到过一种现象：

- `netstat -ano | findstr :9000` 还能看到 `LISTENING`
- 但 `tasklist /FI "PID eq xxxx"` 提示该 PID 不存在

这类情况一般不是代码问题，而是系统里的监听状态还没完全释放，或者父终端、重载进程、IDE 内置终端还没真正收干净。

建议按这个顺序处理：

1. 先关闭启动服务的 PowerShell 窗口或 VS Code 内置终端。
2. 再重新执行一次：

```powershell
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 9000 }
```

3. 如果还是占用，关掉相关的编辑器窗口、终端标签页、旧调试会话。
4. 还不行的话，重启机器是最快的收口方式。

如果你频繁遇到这种情况，建议开发时临时去掉 `--reload`，先用单进程模式定位问题。

## 查看日志

FastAPI 目录下已经有几个常见日志文件：

- `D:\zhuomian\Agent-2\fastapi\uvicorn.out.log`
- `D:\zhuomian\Agent-2\fastapi\uvicorn.err.log`
- `D:\zhuomian\Agent-2\fastapi\uvicorn.manual.out.log`
- `D:\zhuomian\Agent-2\fastapi\uvicorn.manual.err.log`

快速查看：

```powershell
Get-Content D:\zhuomian\Agent-2\fastapi\uvicorn.err.log -Tail 50
```

```powershell
Get-Content D:\zhuomian\Agent-2\fastapi\uvicorn.out.log -Tail 50
```

## Worker 调试端口说明

如果你同时还在跑 Cloudflare Worker，本地常用是 `8787`：

```powershell
cd D:\zhuomian\Agent-2
npm.cmd install
npx.cmd wrangler dev
```

停掉它的方式也一样：

- 前台运行就 `Ctrl + C`
- 后台运行就先查 `8787` 对应 PID，再 `taskkill /PID <pid> /T /F`

## 推荐的日常操作顺序

1. 先确认 `9000` 和 `8787` 有没有旧进程占着。
2. 只启动你当前要调试的一套服务。
3. FastAPI 本地页面优先用 `9000`。
4. 调地图、会话、页面逻辑时，优先检查 `http://127.0.0.1:9000/health`。
5. 如果出现端口占用，先杀 PID，再决定是否重启 `uvicorn`。

## 一组最常用命令

启动 FastAPI：

```powershell
uvicorn app:app --app-dir fastapi --host 127.0.0.1 --port 9000 --reload
```

检查 `9000`：

```powershell
netstat -ano | findstr :9000
```

结束指定 PID：

```powershell
taskkill /PID 12345 /T /F
```

检查健康状态：

```powershell
Invoke-WebRequest http://127.0.0.1:9000/health | Select-Object -ExpandProperty Content
```
