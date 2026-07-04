# AI 文本处理应用

中译英、英译中、文本总结三个功能，支持流式（SSE）输出、任务取消、CLI 调用
和 Agent 发现（见 `skill.md`）。

## 技术栈
- 后端：Python 3.11 + FastAPI + `arq`（Redis 异步任务队列）+ SQLite
- 大模型：OpenAI 兼容格式（`openai` SDK），默认指向 DeepSeek
  （`deepseek-chat` 快速模式 / `deepseek-reasoner` 思考模式）
- 前端：React + TypeScript + Vite
- CLI：Python `click`
- 部署：Docker Compose（frontend/backend/worker/redis）

## 本地运行（Docker，推荐）

```bash
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY（留空则使用本地模拟回复）
docker compose up --build
```

- 前端：http://localhost
- 后端 API：http://localhost:8000
- 健康检查：http://localhost:8000/health

## 本地运行（不使用 Docker）

```bash
# 1. 启动 Redis（后端和 worker 都依赖它，务必先启动）
docker run -p 6379:6379 redis:7-alpine

# 2. 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # 填入 LLM_API_KEY
uvicorn main:app --reload --port 8000

# 3. worker（新终端，同样需要能连接到 Redis）
cd backend && source .venv/bin/activate
arq worker.settings.WorkerSettings

# 4. 前端（新终端）
cd frontend
npm install
npm run dev

# 5. CLI（可选，新终端）
cd cli
pip install -e ".[test]"   # 含 pytest；若只需运行 CLI 不跑测试，pip install -e . 即可
ai-app translate --text "Hello" --from en --to zh
```

> 不使用 Docker 时，Redis 是必需的依赖：后端任务队列（`arq`）和任务状态查询都
> 通过 Redis 完成，Redis 未启动时提交任务会失败。

## 运行测试

```bash
cd backend && python -m pytest        # 依赖 requirements.txt 中已包含的 pytest / pytest-asyncio / fakeredis
cd cli && pip install -e ".[test]" && python -m pytest   # [test] extra 含 pytest
cd frontend && npm run test           # 等价于 vitest run
```

## API 接口文档

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/functions` | 返回功能列表 |
| POST | `/api/task` | 提交任务：`{function_type, text, max_points?, mode?}` → `{task_id, status}` |
| GET | `/api/task/{taskId}/stream` | SSE 流式结果 |
| GET | `/api/task/{taskId}` | 查询任务状态 |
| DELETE | `/api/task/{taskId}` | 取消任务 |
| GET | `/api/records?limit=&offset=` | 查询历史调用记录 |

`function_type` 取值：`translate_en2zh` / `translate_zh2en` / `summarize`。
`mode` 取值：`auto`（默认，翻译走快速模式、总结走思考模式）/ `fast` / `think`。

## CLI 使用

```bash
ai-app translate --text "Hello" --from en --to zh
ai-app summarize --text "长文本..." --max-points 3
```

见 `skill.md` 了解如何让 Agent（ClaudeCode/OpenClaw）发现并调用这个 CLI。

## 项目文档

- 设计文档：`docs/superpowers/specs/2026-07-03-ai-text-processing-app-design.md`
- 实现计划：`docs/superpowers/plans/2026-07-03-ai-text-processing-app.md`
- SDD 文档：`agent.md`, `spec/`
