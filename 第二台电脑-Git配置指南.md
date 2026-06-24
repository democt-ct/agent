# 🖥️ 第二台电脑 Git 配置指南

> 本指南帮助你在另一台 Windows 电脑上配置 Git，克隆项目 `D:\zhuomian\agent`。

---

## 前提检查

打开 PowerShell，确认 Git 已安装：

```powershell
git --version
```

如果未安装，去 https://git-scm.com/download/win 下载安装。安装时选 **"Use Git from the command line"** 和 **"Checkout as-is, commit as-is"**（不改行尾），其余默认。

---

## 第 1 步：生成 SSH 密钥

```powershell
ssh-keygen -t ed25519 -C "qclaw-laptop2"
```

过程中会出现三次提示，**全部直接按回车**（不设密码）：

1. `Enter file in which to save the key` → 回车（用默认路径）
2. `Enter passphrase` → 回车（不设密码）
3. `Enter same passphrase again` → 回车（确认不设密码）

成功后会看到类似输出：

```
Your identification has been saved in C:\Users\xxx\.ssh\id_ed25519
Your public key has been saved in C:\Users\xxx\.ssh\id_ed25519.pub
```

---

## 第 2 步：添加公钥到 GitHub

### 2.1 查看公钥内容

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

输出的内容类似 `ssh-ed25519 AAAAC3... qclaw-laptop2`，**全选复制**。

### 2.2 粘贴到 GitHub

打开浏览器访问：https://github.com/settings/keys

- 点绿色按钮 **New SSH Key**
- Title 随便填，比如 `laptop-2`
- Key type 选 **Authentication Key**
- Key 粘贴刚才复制的公钥
- 点 **Add SSH Key**

### 2.3 验证连接

```powershell
ssh -T git@github.com
```

看到 `Hi democt-ct! You've successfully authenticated...` 表示成功。

---

## 第 3 步：克隆项目

```powershell
git clone git@github.com:democt-ct/agent.git D:\zhuomian\agent
```

克隆完成后，项目就在 `D:\zhuomian\agent` 了。

---

## 🔄 日常使用方法

> 💡 更详细的操作指南见 **[项目运行指南.md](项目运行指南.md)**，包含每个项目如何启动、端口号、常见问题等。

### 每次工作前（拉取最新代码）

```powershell
cd D:\zhuomian\agent
git pull
```

### 工作完成后（保存并推送）

```powershell
cd D:\zhuomian\agent
git add -A
git commit -m "简述改了什么"
git push
```

### 完整节奏

```powershell
# 1️⃣ 到工位 → 先 pull
cd D:\zhuomian\agent
git pull

# 2️⃣ 改代码 → 写你的东西

# 3️⃣ 走之前 → add + commit + push
cd D:\zhuomian\agent
git add -A
git commit -m "改了什么"
git push
```

**记住这个顺序：pull → 改代码 → add → commit → push，每次都是这套。**

---

## ⚠️ 注意事项

| 规则 | 说明 |
|------|------|
| **先 pull 后干活** | 每次工作前必须 `git pull`，否则容易冲突 |
| **不要同时在两台电脑上改同一文件** | 如果改同一个文件，后 push 的人会遇到冲突 |
| **提交信息写清楚** | `修复登录bug` 好过 `update` |
| **`.env` 不会同步** | `.gitignore` 已排除 `.env`，每台电脑需要自己配 |
| **大文件注意** | `aiphoto/backend/uploads/` 里的图片较多，首次克隆会慢一点 |

---

## 🔧 遇到问题怎么办

### 冲突了？

```powershell
git pull                              # 拉取别人的改动
# 手动编辑冲突文件，删除 <<<<<<  ======  >>>>>> 标记
git add -A
git commit -m "解决冲突"
git push
```

### push 被拒（报错 rejected）？

因为远程有新的提交，需要先 pull：

```powershell
git pull
git push
```

### 想查看当前状态？

```powershell
git status        # 看哪些文件改了
git log --oneline # 看提交历史
```

---

## 项目的目录结构概览

```
D:\zhuomian\agent\
├── Agent-1/          # 客服AI Agent（旅游助手）
├── Agent-2/          # （预留）
├── Agent-3/          # 企业多专家Agent系统
├── aiphoto/          # AI 照片编辑助手
├── 项目启动/          # 各项目的启动脚本
├── .gitignore        # Git 忽略规则
└── ai.txt            # AI 相关笔记
```

---

> 📅 创建时间：2026-06-24
