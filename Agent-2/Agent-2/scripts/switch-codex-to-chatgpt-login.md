# Codex 切换到 ChatGPT 账号登录模式

这个脚本对应文件：

`scripts/switch-codex-to-chatgpt-login.ps1`

## 这到底是在切什么

这个脚本主要是切换 **Codex CLI 的登录方式**，不是切换你项目代码里的 LLM API。

更准确地说，它做的是：

1. 从 Codex 的用户配置里移除自定义 provider（默认是 `picklyone`）
2. 备份当前的 `auth.json`
3. 备份当前的 `config.toml`
4. 运行 `codex login`

所以它的目标是把 Codex 从：

- 自定义 provider / API key 模式

切到：

- ChatGPT 账号登录模式

## 它不会改什么

它不会修改你项目里的这些内容：

- [src/config/llm.ts](/d:/zhuomian/Agent-2/src/config/llm.ts)
- 你的 `browserKey`
- 你的 `securityJsCode`
- 项目自己的 OpenAI / Ollama / ModelScope 配置

也就是说，这个脚本不负责切换项目业务代码中的模型供应商，它只处理 `Codex CLI` 自己的登录状态和 provider 配置。

## 默认操作的目录

脚本默认操作的是你用户目录下的：

`C:\Users\democt\.codex`

涉及文件通常是：

- `C:\Users\democt\.codex\config.toml`
- `C:\Users\democt\.codex\auth.json`

它不会去改仓库里的 `D:\zhuomian\Agent-2\.codex`。

## 运行方式

### 方式 1：通过 npm 脚本运行

```powershell
npm run codex:login-chatgpt
```

### 方式 2：直接运行 PowerShell 脚本

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/switch-codex-to-chatgpt-login.ps1
```

## 常用参数

### 预演，不真正修改

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/switch-codex-to-chatgpt-login.ps1 -WhatIf -SkipLogin
```

这个命令只会告诉你“将会做什么”，不会真的改文件，也不会执行登录。

### 指定 provider 名

如果你要移除的 provider 不是 `picklyone`，可以这样运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/switch-codex-to-chatgpt-login.ps1 -ProviderName "你的provider名"
```

### 只清理配置，不立刻登录

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/switch-codex-to-chatgpt-login.ps1 -SkipLogin
```

这个模式适合你先清理配置，后面再手动执行：

```powershell
codex login
```

## 脚本实际行为

脚本会按这个顺序执行：

1. 确认 `C:\Users\democt\.codex` 存在
2. 创建 `C:\Users\democt\.codex\backups`
3. 备份 `auth.json`
4. 备份 `config.toml`
5. 删除 `config.toml` 里与指定 provider 相关的配置块
6. 删除 `provider = "picklyone"` 这一类引用
7. 执行 `codex login`

## 什么时候该用它

适合的场景：

- 你现在的 Codex 走的是自定义 provider
- Codex 提示你要先移除自定义 provider 才能用 ChatGPT 账号登录
- 你想保留备份，安全地切回官方登录方式

不适合的场景：

- 你只是想改项目里的接口 key
- 你只是想切换 `src/config/llm.ts` 里的模型配置
- 你想切换高德地图 key、OpenAI key、Ollama 地址

## 一句话结论

这个脚本是：

**切换 Codex 账号登录方式**

不是：

**切换项目代码里的 API 配置**
