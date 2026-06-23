# Findings

## Current Itinerary Flow

- 当前行程并不总是由大模型生成，而是“优先 LLM，失败或未配置时回退模板”
- 入口在 [src/index.ts](/d:/zhuomian/Agent-2/src/index.ts#L217) 和 [src/services/conversationPlanner.ts](/d:/zhuomian/Agent-2/src/services/conversationPlanner.ts#L215)
- 默认生成类型由 [src/services/llm/modelConfig.ts](/d:/zhuomian/Agent-2/src/services/llm/modelConfig.ts#L46) 的 `getDefaultGeneratorType()` 决定
- 当 LLM 已配置时，默认走 `agent`
- 当 LLM 未配置时，默认走 `template`

## LLM Path

- 真正的大模型 itinerary 生成在 [src/services/llm/itineraryAgent.ts](/d:/zhuomian/Agent-2/src/services/llm/itineraryAgent.ts#L40)
- 它会把结构化 requirement、已有 itinerary、用户修改指令一起发给 LLM
- 通过结构化 schema 约束返回字段：`title`、`summary`、`itinerary`、`budget_estimate`、`warnings`
- 如果是重规划，不是完全重新生成，而是带上 `original_itinerary_json` 和 `user_request`

## Template Fallback

- 模板兜底在 [src/services/templateItineraryGenerator.ts](/d:/zhuomian/Agent-2/src/services/templateItineraryGenerator.ts#L49)
- 它根据 `destination`、`trip_days`、`interests`、`constraints` 生成一个固定规则的草案
- 模板版本更像“演示可用的默认草案”，不具备真实交通、天气、营业时间校验

## Current UI Facts

- 当前页面在 [fastapi/static/index.html](/d:/zhuomian/Agent-2/fastapi/static/index.html)
- 页面当前形态是“左侧聊天 + 右侧会话与当前行程”
- 它已经不是纯调试页，但产品定位仍然不够收敛
- 当前页面最核心的价值其实不是“旅游灵感发现”，而是“围绕一份 itinerary 持续生成和修改”

## PRD Gap

- 现有 [智能旅游规划Agent助手-PRD.md](/d:/zhuomian/Agent-2/智能旅游规划Agent助手-PRD.md) 更适合做总产品愿景文档
- 它覆盖了推荐、导出、预订、知识提醒、商业化等大量远期能力
- 但对“当前界面第一页该放什么、用户第一步做什么、何时显示重规划入口”指导不够
- 当前项目更需要一份“当前界面 PRD”，直接绑定现有接口和演示链路
