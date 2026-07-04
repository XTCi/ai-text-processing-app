# AI Agent 在本项目中的角色

本项目由 Claude Code（AI Agent）与开发者协作完成，采用规范驱动开发（SDD）+
测试驱动开发（TDD）流程：

1. **brainstorming** — 与开发者逐项澄清需求、技术选型（DeepSeek + OpenAI 兼容
   格式、Redis+arq 异步队列、SQLite 数据闭环等），产出设计文档
   `docs/superpowers/specs/2026-07-03-ai-text-processing-app-design.md`。
2. **writing-plans** — 将设计文档拆解为可独立测试、可独立提交的实现任务，
   产出 `docs/superpowers/plans/2026-07-03-ai-text-processing-app.md`。
3. **执行** — 按计划逐任务实现：每个任务先写失败的测试，再写最小实现使其通过，
   再提交。后端严格 TDD；前端只对关键组件（`useSSETask`/`StreamingOutput`/
   `ModeToggle`）编写测试。

AI Agent 负责：架构设计、代码实现、测试编写、文档撰写。开发者负责：需求
澄清中的关键决策（如是否拆分 SSE 接口、是否引入 Map-Reduce/Draft-Review
工作流、DeepSeek Key 的配置）、以及无法自动化的验证步骤（如 Agent 调用 CLI
的截图）。
