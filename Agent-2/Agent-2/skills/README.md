# 技能总览

这个文档用于记录本项目使用的 Codex 技能以及相关插件仓库。

## 已安装的 Codex 技能

已安装技能存放在：

```text
C:\Users\democt\.codex\skills
```

| 名称                | 类型  | 用途                                                                            | 状态   | 来源                               |
| ------------------- | ----- | ------------------------------------------------------------------------------- | ------ | ---------------------------------- |
| planning-with-files | skill | 基于文件的任务规划，使用 `task_plan.md`、`findings.md` 和 `progress.md`。 | 已安装 | `planning-with-files`            |
| impeccable          | skill | 高质量前端设计与构建流程，支持 `craft`、`teach` 和 `extract` 模式。       | 已安装 | `pbakaus/impeccable`             |
| frontend-design     | skill | 来自 Claude Code 前端设计插件的前端设计指导。                                   | 已安装 | `anthropics/claude-code`         |
| skill-creator       | skill | 创建、更新并改进 Codex 技能。                                                   | 已安装 | `anthropics/skills`              |
| notebooklm-skill    | skill | 面向 NotebookLM 的、基于来源内容的查询工作流。                                  | 已安装 | `PleasePrompto/notebooklm-skill` |

## 相关插件仓库

这些仓库仅作为参考记录，并没有作为标准 Codex 技能安装。

| 名称            | 类型   | 仓库                       | 状态           | 说明                                   |
| --------------- | ------ | -------------------------- | -------------- | -------------------------------------- |
| codex-plugin-cc | plugin | `openai/codex-plugin-cc` | 未作为技能安装 | 这是插件仓库，不是标准技能目录。       |
| superpowers     | plugin | `obra/superpowers`       | 未作为技能安装 | 这是插件或扩展仓库，不是标准技能目录。 |

## 使用说明

- 安装新技能后，请重启 Codex，这样它们才会在下一次会话中被加载。
- 使用技能时，直接在请求里写出技能名即可，例如：`使用 frontend-design 帮我优化这个页面`。
- 这个文件只是项目级清单，本身不会安装或启用任何技能。

## 创建新技能

项目内的草稿技能可以按下面的结构组织：

```text
skills/
  README.md
  your-skill-name/
    SKILL.md
```

如果要让 Codex 真正可用这个技能，需要把它安装到：

```text
C:\Users\democt\.codex\skills\your-skill-name\
  SKILL.md
```
