# 需求拆分

## 基础要求
- [x] 功能列表页（GET /api/functions）
- [x] 翻译页（中译英/英译中，流式结果展示）
- [x] 总结页（长文本输入、字数/要点数控制，流式结果展示）
- [x] SSE 流式推送 + 打字机效果
- [x] 取消进行中的任务（前端发取消请求，后端终止执行）
- [x] POST /api/task 提交任务
- [x] DELETE /api/task/{taskId} 取消任务
- [x] CLI 工具（translate/summarize，直接调用后端服务）
- [ ] skill.md + Agent 调用截图（`skill.md` 已完成；Agent 调用 CLI 的截图
      需用户在真实 Agent 环境中手动操作产生，属于设计文档"开放事项"中
      标注的无法自动化步骤，尚未提供）

## 加分项
- [x] agent.md + spec/ 目录（本文档所在）
- [x] 虚拟滚动优化大文本输入
- [x] 流式渲染性能优化（requestAnimationFrame 批量更新）
- [x] 深色/浅色主题切换
- [x] 响应式布局
- [x] 请求参数校验（Pydantic）+ 统一错误处理 + 日志追踪（trace_id）+ 任务超时控制
- [x] 前端轮询任务状态（SSE 失败降级路径）
- [x] Redis + arq 异步任务队列
- [x] 数据闭环：调用记录持久化（SQLite）+ 查询页（GET /api/records）
- [x] Docker：Dockerfile + docker-compose.yml 一键启动
