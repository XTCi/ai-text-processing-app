# 接口设计

详见设计文档 `docs/superpowers/specs/2026-07-03-ai-text-processing-app-design.md`
的"接口设计"一节，此处摘录核心决策：

浏览器原生 `EventSource` 只支持 GET，因此"提交任务"与"读取流式结果"拆分为
两个独立接口，而不是让 `POST /api/task` 本身承载 SSE 响应。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | /api/functions | 返回功能列表 |
| POST | /api/task | 提交任务，同步返回 taskId |
| GET | /api/task/{taskId}/stream | SSE 流式结果 |
| GET | /api/task/{taskId} | 查询任务状态（轮询/CLI 用） |
| DELETE | /api/task/{taskId} | 取消任务 |
| GET | /api/records | 查询历史调用记录 |

请求/响应模型定义在 `backend/models/task.py`（`TaskSubmitRequest`/
`TaskSubmitResponse`/`TaskStatusResponse`）与 `backend/models/events.py`
（`TaskEvent`，SSE 消息体）。

生产环境部署时，前端静态资源与 `/api` 后端服务分属不同容器，因此新增了
两处反向代理配置，保证浏览器始终以同源相对路径 `fetch("/api/...")` /
`EventSource("/api/...")` 访问后端，无需处理跨域：

- 本地开发：`frontend/vite.config.ts` 的 dev-server proxy，将 `/api` 转发到
  `http://localhost:8000`。
- 生产构建：`nginx.conf` 中的 `location /api/`，将请求转发到 Docker 内部网络
  的 `backend:8000`，并关闭 `proxy_buffering`，确保 SSE 流式响应逐 token
  实时到达浏览器而不是被整体缓冲后一次性发出。
