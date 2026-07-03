# AI 文本处理应用 — 设计文档

日期：2026-07-03
状态：已批准（待写实现计划）

## 背景

笔试题要求实现一个 AI 文本处理应用，提供中译英、英译中、文本总结三个功能，需覆盖前端交互、后端流式 SSE 接口、CLI 工具链、Agent 可发现的 `skill.md`，并尽可能覆盖加分项（SDD/TDD、全栈深度优化、异步任务队列、数据闭环、Docker）。原始题目见 `AI Native 开发工程师 笔试题.pdf`。

## 目标与范围

- 三个核心功能：中译英、英译中、文本总结，均支持流式（打字机效果）输出与取消。
- 后端提供真实的异步任务队列（Redis + arq），而不是同步阻塞调用。
- CLI 工具作为后端服务的真实客户端，可被 Agent（ClaudeCode/OpenClaw）通过 `skill.md` 发现并调用。
- 全部加分项都做，但控制实现深度在这个项目体量合理的范围内（例如队列用 arq 而非 Celery，数据库用 SQLite 而非 PostgreSQL）。
- 全部服务通过 `docker-compose` 统一管理、一键启动。

非目标：不做用户认证/多租户；不做多语言（除中英文）；不做生产级别的可观测性（如 Prometheus/Grafana）。

## 整体架构

```
┌─────────────────┐      SSE / REST      ┌──────────────────────┐
│  前端 (React+TS)  │ ◄──────────────────► │  后端 (FastAPI)        │
│  Vite            │                       │  ┌─────────────────┐ │
└─────────────────┘                       │  │ API 层           │ │
                                            │  │ - /api/functions │ │
┌─────────────────┐                       │  │ - /api/task       │ │
│  CLI (Python)    │ ────── HTTP ────────► │  │ - /api/task/{id}  │ │
│  click           │                       │  │ - /api/records    │ │
└─────────────────┘                       │  └────────┬─────────┘ │
                                            │           │ 入队       │
                                            │  ┌────────▼─────────┐ │
                                            │  │ arq worker        │ │
                                            │  │ (异步任务执行)      │ │
                                            │  └────────┬─────────┘ │
                                            │           │           │
                                            └───────────┼───────────┘
                                                         │
                                    ┌────────────────────┼────────────────┐
                                    │                    │                │
                              ┌─────▼─────┐       ┌──────▼──────┐  ┌──────▼──────┐
                              │  Redis     │       │  LLM API     │  │  SQLite     │
                              │ (队列+状态) │       │ (OpenAI兼容格式)│  │ (调用记录)   │
                              └───────────┘       └─────────────┘  └─────────────┘
```

**服务拆分（docker-compose 管理）：** `frontend` / `backend`(API) / `worker`(arq) / `redis`。SQLite 文件通过共享 volume 挂载给 backend + worker。

**核心数据流：** 前端提交任务 → 后端写入 Redis 队列，立即同步返回 `taskId` → 前端用 `EventSource` 连接 SSE 流式接口 → worker 从队列取任务、调用 LLM API（流式）→ 每个 token 通过 Redis pub/sub 转发回 API 层 → API 层通过 SSE 推给前端逐字渲染 → 任务完成后结果和耗时写入 SQLite。

## 接口设计

浏览器原生 `EventSource` 只支持 GET 请求，若让 `POST /api/task` 本身承载 SSE 流式响应，前端将无法使用标准 `EventSource`（会失去自动重连能力，需手写 `fetch` + `ReadableStream` 解析）。因此将"提交任务"与"读取流式结果"拆分为两个独立接口，这是真正的异步解耦设计，也是本设计相对题目原始文字表述的主要取舍：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/functions` | 返回所有功能列表及描述 |
| POST | `/api/task` | 提交任务（功能类型+参数），立即同步返回 `{ taskId, status: "pending" }`，任务写入 Redis 队列 |
| GET | `/api/task/{taskId}/stream` | SSE 流式接口，前端用 `EventSource` 连接，逐 token 收到 worker 输出，原生支持断线重连 |
| GET | `/api/task/{taskId}` | 查询任务当前状态（pending/running/done/failed + 结果），供轮询场景和 CLI 使用 |
| DELETE | `/api/task/{taskId}` | 取消任务：标记 Redis 取消标志，worker 检测到后终止流式调用 |
| GET | `/api/records` | 查询历史调用记录（数据闭环加分项） |

取消是"协作式"的：worker 在流式循环中每收到一个 token 就检查 Redis 里的取消标志，检测到则立即终止对 LLM 的调用并将状态置为 `cancelled`。

## 大模型调用层

DeepSeek 的 API 兼容 OpenAI 的 `chat/completions` 格式，因此直接使用官方 `openai` Python SDK，只需配置 `base_url` 指向 DeepSeek endpoint。这样以后切换到 OpenAI 官方 API 或其他兼容 OpenAI 格式的服务商（如智谱），只需修改 `.env` 配置，代码不用改动，满足题目"大模型调用可使用任意API"的要求。

```
# .env.example
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=                          # 用户自行填写
LLM_MODEL_FAST=deepseek-chat          # 非思考模式
LLM_MODEL_THINK=deepseek-reasoner     # 思考模式
```

```python
# services/llm_client.py
from openai import OpenAI

client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)

def call_model(messages, mode: Literal["fast", "think"], stream=True):
    model = settings.LLM_MODEL_THINK if mode == "think" else settings.LLM_MODEL_FAST
    return client.chat.completions.create(model=model, messages=messages, stream=stream)
```

**思考模式策略：** 默认按功能自动选择 —— 翻译用 `fast`（`deepseek-chat`），文本总结用 `think`（`deepseek-reasoner`，长文本理解质量更好）。前端额外提供手动开关，允许用户覆盖默认选择，适用于全部三个功能。

若 `.env` 未配置 `LLM_API_KEY`，`llm_client` 回退到本地模拟模式（伪代码，注释清楚模拟逻辑），保证在没有真实 Key 的情况下也能跑通完整链路；真实调用链路（HTTP 请求结构、流式解析逻辑）保留不变，用户填入 Key 后即可直接切换为真实调用。

## 核心任务执行架构（翻译 / 总结）

题目对"翻译""总结"的具体实现没有约束，但直接把用户输入拼进一个 prompt 一次性调用模型，无法应对长文本（超出上下文窗口）也体现不出工程深度。这里为两个功能分别设计一个轻量工作流，而不是单次 prompt 调用，也不引入完整的 ReAct/工具调用循环（翻译、总结这两个任务本身不需要模型自主决策调用哪个工具，上 ReAct 属于过度设计）。两个工作流都与已确定的 `fast`/`think` 模式联动，模式不只是"换个模型"，而是真正改变执行路径的深度：

**总结功能 — Map-Reduce 工作流（`pipelines/summarize.py`）**

1. **分块（chunking）**：按 token 数对输入文本切分（如每块 ~3000 tokens，块间保留小段重叠避免语义在边界断裂）；若文本本身未超过单次上下文窗口，跳过分块，直接走单次调用，避免不必要开销。
2. **Map**：对每个分块调用模型生成分块摘要。
3. **Reduce**：拼接所有分块摘要，再调用一次模型生成满足用户"字数/要点数"约束的最终摘要；若拼接后仍然过长，递归再做一轮 Reduce。
4. **模式联动**：Reduce 阶段（决定最终输出质量的一步）用 `think`/`fast` 对应的模型；Map 阶段（只是中间产出）始终用 `fast` 模型，控制成本和延迟。
5. **进度反馈**：每完成一个分块的 Map，通过 SSE 推送一个进度事件（如"正在处理第 2/5 块"），避免长文本处理时前端长时间静默；Reduce 阶段的输出逐 token 流式推送，作为最终结果。

**翻译功能 — Draft + Review 两步链（`pipelines/translate.py`）**

1. **Draft**：调用模型生成初始翻译，逐 token 流式推送给前端/CLI。
2. **Review（仅 `think` 模式）**：把原文+ Draft 一起交给模型，要求检查准确性、遗漏、生硬表达，输出修正版本；若模型判断无需修改，直接复用 Draft 结果，不做无意义的改写。Review 阶段的输出同样流式推送，前端在 Draft 结束、Review 开始前展示一个"精修中…"的过渡状态。
3. **`fast` 模式跳过 Review**：只做 Draft 一次调用，保证短文本/快速场景的低延迟——这也是为什么之前把"思考模式"设计成前端可手动开关的原因，用户可以用它直接控制"要不要多花一次调用换取翻译质量"。

**worker 侧目录结构：**
```
worker/
├── tasks.py               # arq task 入口，按 function_type 路由到对应 pipeline
├── pipelines/
│   ├── summarize.py        # map-reduce 编排逻辑
│   └── translate.py        # draft+review 两步链编排逻辑
└── chunking.py              # 文本分块工具（按 token 数切分 + 重叠）
```

这两个 pipeline 都通过同一套"Redis pub/sub → SSE"机制推送中间与最终结果，对 API 层和前端来说是透明的：不管背后是一次调用还是多阶段工作流，消费方看到的都是同一个 token 流 + 偶尔穿插的进度事件。

## 后端模块

```
backend/
├── api/
│   ├── functions.py      # GET /api/functions
│   ├── tasks.py           # POST/GET/DELETE /api/task...
│   └── records.py         # GET /api/records
├── core/
│   ├── config.py          # 环境变量、LLM Key 读取
│   ├── errors.py          # 统一错误处理（自定义异常 + 全局 handler）
│   └── logging.py         # 结构化日志 + 请求追踪 trace_id
├── models/
│   ├── task.py            # 任务状态机 (pending/running/done/failed/cancelled)
│   └── record.py          # SQLite ORM 模型（调用记录）
├── services/
│   ├── llm_client.py      # LLM API 封装（OpenAI 兼容格式，区分 fast/think 模式）
│   └── task_service.py    # 任务入队、状态查询、取消逻辑
├── worker/
│   ├── tasks.py             # arq task 入口，按 function_type 路由到对应 pipeline
│   ├── pipelines/
│   │   ├── summarize.py      # map-reduce 编排逻辑
│   │   └── translate.py      # draft+review 两步链编排逻辑
│   └── chunking.py            # 文本分块工具（按 token 数切分 + 重叠）
└── tests/                  # pytest，TDD 覆盖 services + api + worker + pipelines
```

**关键设计点：**
- 任务状态写入 Redis（快速查询），任务完成后落盘 SQLite（持久化记录）。
- 超时控制：arq 任务设置 `job_timeout`（如 60s），超时自动标记 `failed`，原因写入记录。
- 统一错误处理：自定义异常类（`ValidationError`/`TaskNotFoundError`/`ModelAPIError`）+ FastAPI 全局异常处理器；请求参数用 Pydantic 校验。
- 日志追踪：每个请求生成 `trace_id`，贯穿 API 层→队列→worker→模型调用。

**数据模型（SQLite，调用记录表 `call_records`）：**

| 字段 | 说明 |
|---|---|
| id, task_id | 主键、任务ID |
| function_type | translate_en2zh / translate_zh2en / summarize |
| input_text | 用户输入 |
| output_text | 模型输出 |
| model_mode | fast / think |
| status | done/failed/cancelled |
| duration_ms | 耗时 |
| created_at | 时间戳 |

## 前端设计

```
src/
├── pages/
│   ├── FunctionList.tsx     # 列表页：拉取 GET /api/functions，卡片展示3个功能
│   ├── TranslatePage.tsx    # 翻译页：输入框、方向选择(中→英/英→中)、结果区
│   └── SummarizePage.tsx    # 总结页：长文本输入、字数/要点数控制、结果区
├── components/
│   ├── StreamingOutput.tsx  # 打字机效果渲染组件，复用于翻译/总结结果区
│   ├── ModeToggle.tsx       # 思考模式开关（自动+手动覆盖）
│   ├── VirtualTextarea.tsx  # 大文本输入的虚拟滚动优化
│   └── ThemeToggle.tsx      # 深/浅主题切换
├── hooks/
│   ├── useSSETask.ts        # 封装：提交任务→建立EventSource→逐token更新state→取消
│   └── useTaskPolling.ts    # 轮询任务状态，SSE 失败时的降级路径
└── styles/theme.css          # CSS variables 实现深浅主题
```

**关键设计点：**
- 流式渲染：`useSSETask` 用 `requestAnimationFrame` 批量更新 state，避免逐字符触发过多重渲染。
- 取消生成："停止生成"按钮调用 `DELETE /api/task/{taskId}` + 前端主动关闭 `EventSource` 连接。
- 虚拟滚动：总结页长文本输入框超过一定行数才启用虚拟滚动，避免大文本卡顿。
- 深浅主题：CSS variables + `prefers-color-scheme` 检测 + 手动切换，状态存 `localStorage`。
- 响应式布局：Flexbox/Grid，窄屏下输入区/结果区改为上下堆叠。
- 轮询降级：SSE 连接多次重连失败后，`useTaskPolling` 接管，改为定时轮询 `GET /api/task/{taskId}` 直到 done/failed。

## CLI 与 Agent 工具链

CLI（Python `click`）通过 HTTP 调用后端 API，而非直接导入后端代码，是后端服务的真实客户端：

```bash
ai-app translate --text "Hello" --from en --to zh
ai-app summarize --text "长文本..." --max-points 3
```

内部流程：`POST /api/task` 拿 `taskId` → 立即连接 `GET /api/task/{taskId}/stream` 消费 SSE（用 `sseclient` 或手写流式 HTTP 读取），逐 token 打印到终端模拟打字机效果，与前端体验一致；`Ctrl+C` 触发 `DELETE /api/task/{taskId}` 取消任务。

`skill.md` 描述该 CLI 工具供 Agent（ClaudeCode/OpenClaw）发现并调用，包含：工具用途描述、命令格式与参数说明、输入输出示例、触发场景描述。Agent 调用截图需在真实 Agent 环境中手动操作产生，作为交付物之一保存到 `docs/`。

## 测试策略

后端 pytest，严格 TDD：`llm_client`（mock 模型调用）、`task_service`（状态流转/取消逻辑）、`pipelines/summarize`（分块边界、Map-Reduce 合并逻辑）、`pipelines/translate`（Draft/Review 分支逻辑）、API 层（`TestClient`）、CLI（`click.testing.CliRunner`，含流式输出）均先写测试再写实现。

前端 Vitest + Testing Library：只覆盖关键组件 —— `useSSETask` 状态流转、`StreamingOutput` 渲染、`ModeToggle` 交互，不追求全覆盖。

## Docker

```yaml
services:
  frontend:   # Vite build + nginx
  backend:    # FastAPI (uvicorn)
  worker:     # arq worker
  redis:      # 官方 redis 镜像
# SQLite 文件通过共享 volume 挂载给 backend + worker
```

`.env.example` 提供 `LLM_API_KEY=` 空位，README 注明"填入你的 DeepSeek Key 后 `docker compose up` 一键启动"。

## SDD 文档结构

```
agent.md              # AI Agent 在本项目开发中的角色、协作方式
spec/
├── requirements.md    # 需求拆分（对应题目基础要求+加分项的任务清单）
├── api-design.md      # 接口设计（含本文档中 SSE 架构取舍说明）
└── ui-prototype.md    # 页面原型描述（列表页/翻译页/总结页的布局与交互）
```

## 交付物清单

1. GitHub 仓库地址
2. `skill.md` + Agent 调用截图（需用户手动操作产生）
3. 加分项文件：`agent.md`、`spec/`、Docker 配置、数据闭环查询页
4. `README.md`：项目介绍、功能演示、技术栈说明、本地运行指南（含 Docker 一键启动步骤）、API 接口文档

## 开放事项

- Agent 调用截图需要用户在真实 Agent 环境（ClaudeCode/OpenClaw）中手动操作完成，无法在实现阶段自动产生。
