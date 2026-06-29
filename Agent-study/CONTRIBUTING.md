# 贡献指南

本仓库接受针对 Prompthon Agentic Labs 的多种公开贡献形式。

第一个要问的问题不是"文章还是代码？"而是"你要添加的是什么类型的成果物？"

## 支持的贡献类型

- lab article：位于 oundations/、patterns/、
  systems/、ecosystem/ 或 case-studies/ 中的常青页面
- adar note：位于 adar/ 中的简短、按时间范围限定的现场更新
- source project：位于某条 lane 本地 examples/ 子路径下、由仓库维护的示例或 starter
- practitioner skill package：位于 skills/ 下的 Codex 兼容技能包，可包含
  SKILL.md、agent 元数据、辅助脚本、参考文件，以及运行或审查该包所需的最少文档
- curated reference note：位于 contributor-kit/reference-notes/ 下的结构化来源地图、汇总或阅读笔记

publications/ 不是第一波社区贡献的入口。请将其视为成熟实验室页面的编辑扩展区域。

## 共享 PR 流程

1. 选择贡献类型。
2. 找到或打开定义该工作的 issue。
3. 用可见评论认领 issue，并等待维护者确认或添加 claimed 标签。
4. 如果没有写权限，请 fork 仓库；如果有写权限，请基于最新 develop 创建聚焦分支。
5. 使用对应模板将工作放到正确的文件夹中。
6. 从相关 README 或贡献入口添加或更新链接。
7. 打开一个目标为 develop、带有简短范围摘要并链接 issue 的 PR。
8. 在请求合并之前，根据共享检查清单审查变更。

## 分支与发布流程

develop 是普通贡献工作的共享集成分支。Lab 文章、radar 笔记、source
projects、practitioner skill packages、reference notes，以及仓库流程变更都应先进入
develop。

main 是生产环境 Mintlify 分支。合并到 main 就是发布事件，会触发生产发布以及
GitHub release/tag。不要把功能或内容 PR 直接开到 main。
