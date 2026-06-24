# Git 团队协作手册

> Person A 建 repo 开干，从零到团队协作的完整指南

---

## 目录

1. [角色分工](#1-角色分工)
2. [Person A：项目初始化](#2-person-a项目初始化)
3. [分支策略](#3-分支策略)
4. [日常开发流程](#4-日常开发流程)
5. [Pull Request 流程](#5-pull-request-流程)
6. [他人参与（Fork 模式）](#6-他人参与fork-模式)
7. [代码 Review 规范](#7-代码-review-规范)
8. [常用 Git 命令速查](#8-常用-git-命令速查)
9. [常见问题](#9-常见问题)

---

## 1. 角色分工

| 角色 | 职责 | 权限 |
|------|------|------|
| **Person A** | 建仓库、搭骨架、review PR、合并代码 | 仓库 Owner，管理 main 分支 |
| **Person B** | 开发某个模块，提 PR | 无 main 写入权限，通过 Fork + PR 贡献 |
| **Person C** | 修 bug / 加功能，提 PR | 同 B |

**核心规则：main 分支受保护，任何人（包括 Person A）不直接往 main 上 push，所有改动走 PR + review。**

---

## 2. Person A：项目初始化

### 2.1 本地创建项目

```bash
mkdir project-name
cd project-name
git init
echo "# Project Name" > README.md
```

### 2.2 写好项目基础文件

```bash
touch .gitignore      # 忽略 node_modules, .env, dist 等
touch README.md       # 项目说明：什么项目、怎么跑
touch CONTRIBUTING.md # 贡献指南：分支命名、commit 规范、PR 流程
```

`.gitignore` 示例：

```
node_modules/
dist/
.env
*.log
.DS_Store
```

### 2.3 推送到 GitHub

```bash
# 先在 GitHub 上新建空仓库（不要勾 README/.gitignore）
git remote add origin git@github.com:你的用户名/仓库名.git
git branch -M main
git add .
git commit -m "chore: init project"
git push -u origin main
```

### 2.4 设置 main 分支保护

GitHub → **Settings → Branches → Add branch protection rule**：

- [x] `Branch name pattern`: `main`
- [x] **Require a pull request before merging**
- [x] **Require approvals** → `1`
- [x] **Require status checks to pass**（有 CI 时勾）
- [x] **Do not allow bypassing the above settings**

---

## 3. 分支策略

### 3.1 分支命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feat/<name>` | `feat/user-login` |
| 修 bug | `fix/<name>` | `fix/login-error` |
| 文档 | `docs/<name>` | `docs/api-guide` |
| 重构 | `refactor/<name>` | `refactor/auth-module` |

### 3.2 分支关系图

```
main ────●──────────●──────────●────  (受保护，不可直接 push)
          \        / \        /
feat/login ●──●──●   \      /
                      \    /
feat/goods  ●──●──●──●──●
```

- 每个功能/修复在独立分支上开发
- 完成后通过 PR 合并回 main
- main 永远是稳定可部署的状态

---

## 4. 日常开发流程

### 4.1 从 main 拉新分支

```bash
git checkout main
git pull                         # 确保 main 是最新的
git checkout -b feat/add-login   # 新建功能分支
```

### 4.2 在分支上写代码

```bash
# 写代码...
git status                       # 查看改动
git add src/login.ts             # 暂存指定文件
git commit -m "feat: add login page"
```

Commit 信息规范（Conventional Commits）：

```
<type>: <简短描述>

feat: add login page        # 新功能
fix: fix login validation   # 修 bug
docs: update README         # 文档
refactor: extract auth util # 重构
test: add login tests       # 测试
chore: update deps          # 杂务
```

### 4.3 推送到远程

```bash
git push -u origin feat/add-login   # 首次推送（-u 建立关联）
# 之后只需
git push
```

### 4.4 多人协同时，保持分支同步

如果开发周期长，其他人已经合了代码进 main，需要同步：

```bash
# 方法 1：rebase（推荐，保持历史干净）
git checkout feat/add-login
git fetch origin
git rebase origin/main

# 方法 2：merge（保留合并记录）
git checkout feat/add-login
git merge main
```

**rebase vs merge 选择：**

| | rebase | merge |
|---|---|---|
| 历史 | 线性干净 | 保留分支合并记录 |
| 冲突 | 逐一解决（一个 commit 一个冲突） | 一次性解决 |
| 推荐场景 | 个人分支同步 main | 多人协作的公共分支 |

---

## 5. Pull Request 流程

### 5.1 开 PR

```bash
# push 完分支后，终端会显示一行链接：
# remote: Create a pull request for 'feat/add-login' on GitHub by visiting:
# remote:   https://github.com/your/repo/pull/new/feat/add-login

# 直接打开那个链接，或者去 GitHub → Pull Requests → New Pull Request
```

PR 模板填写：

```
## 描述
实现了用户登录功能，包含邮箱+密码登录。

## 改动文件
- src/login.ts
- src/types.ts
- tests/login.test.ts

## 关联 Issue
Closes #12

## 测试方式
- [x] 本地运行通过
- [x] 已添加单元测试
```

### 5.2 Review 流程

```
你：开 PR → 分配 reviewer
reviewer：看代码 → 评论 / 请求修改
   ↓
你：修改 → git commit → git push（PR 自动更新）
reviewer：再看 → 通过（Approve）
   ↓
你：点击 Merge 按钮 → 代码进入 main
```

### 5.3 Merge 方式

GitHub 提供三种合并方式：

| 方式 | 效果 | 推荐场景 |
|------|------|----------|
| **Squash and merge** | 把分支所有 commit 压成一个，合进 main | ✅ 最常用。保持 main 历史干净 |
| **Merge commit** | 保留所有 commit + 一条 merge 记录 | 多人合作分支 |
| **Rebase and merge** | 把 commit 一个个 rebase 到 main 顶部 | 确保每个 commit 都可独立运行 |

**推荐：Squash and merge。**

### 5.4 合并后清理

```bash
# 在 GitHub 上 merge 后，本地删掉已合并的分支
git checkout main
git pull
git branch -d feat/add-login        # 删除本地分支
git push origin --delete feat/add-login  # 删除远程分支
```

---

## 6. 他人参与（Fork 模式）

当 B 不是你仓库的 Collaborator 时，用 Fork 方式。

### 6.1 B：Fork 仓库

1. 去 Person A 的 GitHub 仓库页面
2. 点右上角 **Fork** 按钮
3. 自己的 GitHub 下多出一个副本

```bash
# B 克隆自己的 Fork
git clone git@github.com:B-user/repo-name.git
cd repo-name

# 添加 A 的仓库为 upstream（上游仓库）
git remote add upstream git@github.com:A-user/repo-name.git

# 查看远程仓库
git remote -v
# origin     → B/repo-name  （自己的 Fork）
# upstream   → A/repo-name  （A 的原始仓库）
```

### 6.2 B：开发流程

```bash
# 从 upstream 同步 main
git checkout main
git pull upstream main
git push origin main          # 同步自己的 Fork

# 新建功能分支
git checkout -b feat/my-part

# 写代码...
git add .
git commit -m "feat: my part"
git push -u origin feat/my-part
```

### 6.3 B：开 PR

去 B 的 GitHub → 点 **Pull Request** → 选择：

- base repository: **A-user/repo-name** (目标：A 的仓库)
- base: **main**
- head repository: **B-user/repo-name** (来源：B 的 Fork)
- compare: **feat/my-part**

**这个 PR 会出现在 A 的仓库里，A 来 review。**

### 6.4 A：合入后 B 同步

```bash
# A 合入 PR 后，B 同步
git checkout main
git pull upstream main   # 拉 A 的最新代码
git push origin main     # 更新自己的 Fork
```

### 6.5 关键图

```
A/repo (main)  ←── PR 合入这里
    ↑
B 的 Fork (B/repo)
    ↑
B 本地开发 (feat/my-part)
```

---

## 7. 代码 Review 规范

### 7.1 Reviewer 看什么

- [ ] 逻辑是否正确？
- [ ] 是否有测试覆盖？
- [ ] 代码风格是否符合项目规范？
- [ ] 有没有安全漏洞（SQL 注入、XSS 等）？
- [ ] 函数/变量命名是否清晰？
- [ ] 有没有不必要的重复代码？

### 7.2 Review 用语示例

| 场景 | 写法 |
|------|------|
| 建议改 | `这个变量名 `data` 太模糊了，改成 `loginResponse` 更清楚？` |
| 提问 | `这里为什么要用 `any` 类型？可以用具体接口吗？` |
| 表扬 | `这个测试用例写得很完整 👍` |
| 必须改 | `这里有 SQL 注入风险，输入没有转义。` |

### 7.3 谁可以 Merge

- 开 PR 的人**不能自己 merge**（需要另一个人 Approve）
- 但如果是非常小的改动（typo、文档），可以放宽

---

## 8. 常用 Git 命令速查

### 8.1 初始化 & 配置

```bash
git init                           # 初始化仓库
git config --global user.name "名字"
git config --global user.email "邮箱"
```

### 8.2 日常操作

```bash
git status                         # 查看状态
git add .                          # 暂存所有改动
git add 文件名                      # 暂存指定文件
git commit -m "message"            # 提交
git commit -am "message"           # add + commit 一步到位（仅已跟踪文件）
```

### 8.3 分支操作

```bash
git branch                         # 查看本地分支
git branch -a                      # 查看所有分支（含远程）
git checkout -b 分支名              # 新建并切换分支
git checkout 分支名                 # 切换分支
git branch -d 分支名                # 删除本地分支
git push origin --delete 分支名     # 删除远程分支
```

### 8.4 远程操作

```bash
git remote -v                      # 查看远程仓库地址
git remote add origin <url>        # 关联远程仓库
git push -u origin main            # 首次推送
git push                           # 推送
git pull                           # 拉取 = fetch + merge
git fetch                          # 仅获取远程信息
```

### 8.5 同步 & 冲突

```bash
git rebase origin/main             # rebase 方式同步 main
git merge main                     # merge 方式同步 main
```

**遇到冲突时：**

```bash
# Git 会标记冲突文件，手动编辑解决后：
git add <解决完的文件>
git rebase --continue   # 如果用 rebase 产生的冲突
# 或
git commit              # 如果用 merge 产生的冲突
```

### 8.6 查看历史

```bash
git log                            # 查看提交历史
git log --oneline                  # 一行显示
git log --graph                    # 图形化显示
git diff                           # 查看未暂存的改动
git diff --staged                  # 查看已暂存的改动
```

### 8.7 后悔药

```bash
git restore <文件>                  # 撤销未暂存的修改
git restore --staged <文件>         # 取消暂存
git commit --amend -m "新消息"      # 修改上一次 commit 信息
git reset --soft HEAD~1            # 撤销上一次 commit，保留改动
git reset --hard HEAD~1            # 彻底删除上一次 commit 和改动 ⚠️
```

---

## 9. 常见问题

### Q1：我 push 之后想改 commit 信息

```bash
git commit --amend -m "新消息"
git push --force-with-lease        # 注意：force push 会覆盖远程！
```

### Q2：我忘了切分支，直接改了 main

```bash
# 如果还没 commit
git stash
git checkout -b feat/xxx
git stash pop

# 如果已经 commit
git checkout -b feat/xxx    # 分支指向同一个 commit
git branch -f main HEAD~1   # main 退回上一步
```

### Q3：冲突了怎么办？

1. Git 会告诉你哪些文件冲突
2. 打开文件，找到 `<<<<<<<` / `=======` / `>>>>>>>` 标记
3. 手动选择保留哪部分，删掉标记
4. `git add <文件>` → `git rebase --continue`（或 `git commit`）

### Q4：.gitignore 不生效？

如果文件已经被跟踪了，.gitignore 不会生效：

```bash
git rm --cached <文件>   # 从跟踪中移除但保留本地文件
```

### Q5：我不小心把敏感信息（密码、token）push 了？

```bash
# 1. 立即去 GitHub 撤销这个 token / 改密码
# 2. 删除文件 + commit
git rm --cached .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "fix: remove sensitive info"
git push
# 3. 注意：历史里还有！！如果有人 clone 过，信息已经泄漏了
#    彻底清除需要 git filter-branch 或用 BFG Repo-Cleaner
```

---

## 总结：一次完整协作流程

```
Person A:
  git init → 推送 → 设保护规则 → 写项目骨架

每个人（含 A）:
  git checkout -b feat/my-part
  # 写代码
  git add . && git commit -m "feat: xxx"
  git push -u origin feat/my-part
  → 去 GitHub 开 PR
  → 等 review → 修改 → Approve

Reviewer:
  看代码 → 评论 → Approve

合并者:
  点 Squash and merge → 合并进 main

所有人:
  git checkout main && git pull
  git branch -d feat/my-part
```

> **核心原则：main 不可直接 push，所有改动走分支 + PR + review，代码永远保持可部署状态。**
