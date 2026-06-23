# 前端界面优化设计文档

## 概述

对 `app/static/tester.html` 进行纯视觉/体验层面的增量优化，不改变任何业务功能、API 调用和数据结构。采用原地渐进优化方案（方案 A），不引入新框架或新文件。

---

## 1. 视觉美观度优化

### 1.1 面板层次区分

- 主面板（chat-panel、query-shell）：保持现有 `rgba(255,253,249,0.84)` 背景
- 次要面板（context-card、general-quick-card 等）：降为 `rgba(255,253,249,0.6)` 背景，边框色降为 `rgba(24,50,45,0.06)`
- 通过背景透明度差异建立视觉主次

### 1.2 聊天气泡区分度加强

- 用户气泡：从纯色 `#daf5dd` 改为品牌绿渐变 `linear-gradient(135deg, #daf5dd, #c8edcc)`
- 助手气泡：从纯灰 `#f4f5f7` 改为微暖色 `#f7f5f0`
- 系统气泡：保持现有 `#f4ebdc`

### 1.3 空状态提示美化

- `.chat-empty` 加 `font-size: 15px`、`letter-spacing: 0.02em`、`line-height: 1.9`
- 颜色从 `var(--subtle)` 微调为稍暖的 `rgba(24,50,45,0.45)`

### 1.4 Hero aside 增强

- `.hero-aside` 加 `box-shadow: inset 0 0 0 1px rgba(255,255,255,0.22), 0 12px 28px rgba(0,0,0,0.08)`

### 1.5 间距体系统一

- 统一为 8 的倍数体系：8 / 12 / 16 / 24 / 32
- gap 目前混用 10/12/14/16/18 → 统一归到 12 或 16
- margin-top 目前混用 6/8/10/12/14/16/18 → 统一归到 8 或 16

### 1.6 字号层级

- h2：18px → 20px
- 正文：保持 14px
- 小字：13px 统一降为 12px
- `.hint`、`.microcopy`、`.voice-note` 等：统一 12px

---

## 2. 导航模型重构

### 2.1 Hero 区域新增 Query 入口

- 在 `.hero-links` 中新增一个链接按钮："患者检索"
- 样式与现有 "打开 Swagger" 等链接一致
- 点击后切换到 Query 视图（复用现有 `switchMode` 逻辑）

### 2.2 聊天视图合并

将原来的"通用聊天"和"记忆聊天"两个独立 workspace 合并为一个聊天页面：

- 顶部加切换条：两个胶囊按钮 `[通用聊天] [记忆聊天]`
  - 活跃态：品牌绿渐变背景 + 白色文字
  - 非活跃态：淡色背景 + 深色文字
  - 样式参考现有 `.mode-tab`
- 侧边栏内容根据切换状态显示不同区块：
  - 通用模式：显示"新建对话 + 最近对话列表"
  - 记忆模式：显示"个人信息绑定 + 一键选患者 + 会话操作"
- 聊天窗口各自独立消息列表
  - 通用：`generalChatMessages` / `#generalChatTranscript`
  - 记忆：`chatMessages` / `#chatTranscript`
- 输入框共享同一个 composer，发送时根据当前切换状态走对应 API
- 切换状态存入 `localStorage`，下次打开恢复上次选择
- 切换时加淡入过渡（opacity 0.15s）

### 2.3 模式切换条调整

原来的三按钮模式切换（Query / 通用聊天 / 记忆聊天）改为两按钮：

- `[患者检索] [智能聊天]`
  - "患者检索" → 切换到 Query 视图
  - "智能聊天" → 切换到合并后的聊天视图（内部再切通用/记忆）

---

## 3. 性能/流畅度优化

### 3.1 CSS contain

- `.chat-window`、`.chat-panel` 加 `contain: content`
- 防止内部滚动/变化触发全页重绘

### 3.2 will-change

- `.chat-window` 加 `will-change: scroll-position`
- 按钮 hover 场景不加 will-change（本身是短暂状态，不值得常驻 GPU 层）

### 3.3 减少面板 hover 抬升

- 去掉静态展示面板（`.context-card`、`.answer-stage`）的 hover `translateY(-1px)`
- 只保留可交互面板（`.query-shell`、`.chat-composer`）的 hover 效果

### 3.4 聊天窗口滚动优化

- 不设全局 `scroll-behavior: smooth`
- 仅在程序化滚动（如 scrollToBottom）时临时添加

### 3.5 去掉 body::before 网格纹理

- 移除全屏 28px 网格纹理覆盖（mask-image + 透明网格线）
- 改用更轻量的纯色渐变背景（已有多层 radial-gradient，足够有层次感）

---

## 4. 移动端适配优化

### 4.1 新增 480px 断点

- Hero 标题字号 clamp 下限降为 22px
- 按钮全宽排列
- 间距整体收紧（shell padding 减半）
- Hero aside 和 Hero copy 纵向排列

### 4.2 720px 以下完善

- chat-stage 单栏时，侧边栏与聊天窗口之间加 12px 间距
- 面板圆角从 24px 降为 16px
- 内边距从 20px 降为 14px

### 4.3 触摸友好

- 输入框 font-size 确保 ≥ 16px（防止 iOS Safari 自动 zoom）
- 链接和按钮的 tap 区域四周加 padding

### 4.4 安全区域

- `.chat-composer` 加 `padding-bottom: max(12px, env(safe-area-inset-bottom))`
- 适配 iPhone 底部安全区

---

## 5. 交互动效优化

### 5.1 消息出现动画

```css
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.chat-message.new-msg {
  animation: fadeInUp 0.25s ease-out;
}
```

- JS 在追加消息 DOM 时加 `.new-msg` 类，animationend 后移除
- 尊重 `prefers-reduced-motion`：该媒体查询下 `animation: none`

### 5.2 按钮 loading 态

- 发送按钮点击后：加 `disabled` 属性 + 脉冲背景动画 + 文字改为"发送中..."
- 请求完成后恢复原状

### 5.3 面板展开/收起过渡

- 使用 CSS `grid-template-rows: 0fr → 1fr` 过渡实现 `<details>` 展开动画
- `transition: grid-template-rows 0.25s ease`
- 需要用 JS 监听 `toggle` 事件来切换类名

### 5.4 聊天模式切换过渡

- 通用/记忆切换时，聊天窗口内容加 `opacity` 过渡 0.15s

### 5.5 空状态 → 有内容

- 聊天窗口从空状态到第一条消息时，`.chat-empty` 加 `opacity: 0; transition: opacity 0.2s` 淡出后移除

### 5.6 无障碍

- 所有动画在 `@media (prefers-reduced-motion: reduce)` 下禁用
- 关键过渡和动画加 `@media` 包裹

---

## 约束

- 不改变任何 HTML 的 name/id/class 语义（可以新增 class，不删改现有）
- 不改变 JS 中的 state 结构、API 调用、事件绑定逻辑
- 不引入外部依赖或新文件
- 所有改动仅在 `app/static/tester.html` 一个文件内完成
