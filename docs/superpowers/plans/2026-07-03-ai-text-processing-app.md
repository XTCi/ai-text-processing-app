# AI 文本处理应用 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack AI text processing app (中译英/英译中/文本总结) with streaming SSE, a Redis+arq async task queue, a streaming CLI, an Agent-discoverable `skill.md`, and Docker Compose deployment, per `docs/superpowers/specs/2026-07-03-ai-text-processing-app-design.md`.

**Architecture:** React+TS (Vite) frontend and a Python CLI both talk to a FastAPI backend over REST + SSE. `POST /api/task` enqueues work into Redis via `arq`; a separate `arq` worker process runs the translate (Draft+Review) or summarize (Map-Reduce) pipeline, publishing token/progress events to a Redis pub/sub channel. `GET /api/task/{taskId}/stream` forwards that channel to the client as SSE. Final results persist to SQLite for the data-closure query page.

**Tech Stack:** Backend: Python 3.11, FastAPI, `arq`, `redis` (asyncio client), `aiosqlite`, `openai` SDK (OpenAI-compatible, pointed at DeepSeek). Frontend: React + TypeScript + Vite, Vitest + Testing Library. CLI: Python `click` + `httpx`. Deployment: Docker Compose (frontend, backend, worker, redis).

## Global Constraints

- Backend framework: FastAPI (Python 3.11+), all I/O async.
- Exactly these HTTP endpoints (per spec §接口设计): `GET /api/functions`, `POST /api/task`, `GET /api/task/{taskId}/stream`, `GET /api/task/{taskId}`, `DELETE /api/task/{taskId}`, `GET /api/records`.
- LLM client must go through the OpenAI-compatible SDK (`openai` package) with `base_url`/`api_key`/model names read from `.env` — never hardcode DeepSeek specifics outside `core/config.py` and `services/llm_client.py`.
- `.env` ships as `.env.example` with `LLM_API_KEY=` left blank for the user to fill in themselves.
- When `LLM_API_KEY` is empty, `llm_client` must fall back to a clearly-commented local mock stream — never raise or crash.
- Mode resolution: `mode="auto"` → `fast` for translate, `think` for summarize; explicit `fast`/`think` always overrides.
- Task queue: Redis + `arq` only (no Celery).
- Persistence: SQLite only (no Postgres).
- CLI and frontend both consume the SSE stream (no polling-only CLI).
- All services (frontend, backend, worker, redis) run via one `docker-compose.yml`.
- Backend tests: strict TDD with `pytest` — write the failing test before the implementation, every task.
- Frontend tests: Vitest + Testing Library, limited to `useSSETask`, `StreamingOutput`, `ModeToggle` (per spec — do not chase full coverage elsewhere).

---

## File Structure

```
text-processing/
├── backend/
│   ├── requirements.txt
│   ├── main.py
│   ├── api/{functions,tasks,records}.py
│   ├── core/{config,errors,logging}.py
│   ├── models/{task,events,record}.py
│   ├── services/{llm_client,task_service,record_store}.py
│   ├── worker/{settings,tasks,chunking}.py
│   ├── worker/pipelines/{translate,summarize}.py
│   └── tests/...
├── cli/
│   ├── pyproject.toml
│   ├── ai_app/{main,client}.py
│   └── tests/test_cli.py
├── frontend/
│   ├── package.json, vite.config.ts, index.html
│   └── src/{main.tsx,App.tsx,api/client.ts,pages/*,components/*,hooks/*,styles/theme.css,__tests__/*}
├── docker-compose.yml, Dockerfile.backend, Dockerfile.worker, Dockerfile.frontend, .env.example
├── skill.md, agent.md
├── spec/{requirements.md,api-design.md,ui-prototype.md}
└── README.md
```

---

## Phase 1: Backend Foundation

### Task 1: Backend project scaffolding + config

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/core/__init__.py`
- Create: `backend/core/config.py`
- Create: `backend/main.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `core.config.Settings` (pydantic-settings model) and module-level `settings` instance with fields `llm_base_url: str`, `llm_api_key: str`, `llm_model_fast: str`, `llm_model_think: str`, `redis_url: str`, `sqlite_path: str`, `task_timeout_seconds: int`.
- Produces: `main.app` — a FastAPI instance exposing `GET /health` → `{"status": "ok"}`.

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
pydantic-settings==2.5.2
openai==1.51.0
arq==0.26.1
redis==5.0.8
aiosqlite==0.20.0
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
fakeredis==2.24.1
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_config.py
import importlib
import os

def test_settings_default_urls(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from core import config
    importlib.reload(config)
    assert config.settings.llm_base_url == "https://api.deepseek.com"
    assert config.settings.llm_model_fast == "deepseek-chat"
    assert config.settings.llm_model_think == "deepseek-reasoner"
    assert config.settings.llm_api_key == ""

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-123")
    from core import config
    importlib.reload(config)
    assert config.settings.llm_api_key == "sk-test-123"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core'`

- [ ] **Step 4: Write minimal implementation**

```python
# backend/core/__init__.py
```

```python
# backend/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model_fast: str = "deepseek-chat"
    llm_model_think: str = "deepseek-reasoner"
    redis_url: str = "redis://localhost:6379/0"
    sqlite_path: str = "./data/app.db"
    task_timeout_seconds: int = 60


settings = Settings()
```

```python
# backend/main.py
from fastapi import FastAPI

app = FastAPI(title="AI Text Processing App")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/core backend/main.py backend/tests/test_config.py
git commit -m "feat(backend): scaffold FastAPI app with env-driven settings"
```

---

### Task 2: Unified error handling

**Files:**
- Create: `backend/core/errors.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_errors.py`

**Interfaces:**
- Consumes: `main.app` from Task 1.
- Produces: `core.errors.AppError`, `ValidationError`, `TaskNotFoundError`, `ModelAPIError` (each `AppError` subclass with `status_code: int` and `message: str`); `core.errors.register_exception_handlers(app: FastAPI)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_errors.py
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.errors import TaskNotFoundError, register_exception_handlers


def build_app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise TaskNotFoundError("task xyz not found")

    return app


def test_app_error_returns_structured_json():
    client = TestClient(build_app())
    resp = client.get("/boom")
    assert resp.status_code == 404
    assert resp.json() == {"error": "TaskNotFoundError", "message": "task xyz not found"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.errors'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/core/errors.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ValidationError(AppError):
    status_code = 400


class TaskNotFoundError(AppError):
    status_code = 404


class ModelAPIError(AppError):
    status_code = 502


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": type(exc).__name__, "message": exc.message},
        )
```

```python
# backend/main.py (append)
from core.errors import register_exception_handlers

register_exception_handlers(app)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/errors.py backend/main.py backend/tests/test_errors.py
git commit -m "feat(backend): add unified AppError hierarchy and exception handler"
```

---

### Task 3: Request tracing (trace_id) middleware

**Files:**
- Create: `backend/core/logging.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_logging.py`

**Interfaces:**
- Produces: `core.logging.configure_logging()`, `core.logging.trace_id_var: contextvars.ContextVar[str]`, `core.logging.new_trace_id() -> str`, `core.logging.TraceIdMiddleware` (Starlette middleware setting `trace_id_var` per request and echoing `X-Trace-Id` response header).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_logging.py
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.logging import TraceIdMiddleware, trace_id_var


def build_app():
    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)

    @app.get("/whoami")
    async def whoami():
        return {"trace_id": trace_id_var.get()}

    return app


def test_middleware_sets_trace_id_and_header():
    client = TestClient(build_app())
    resp = client.get("/whoami")
    assert resp.status_code == 200
    header_trace = resp.headers["x-trace-id"]
    assert resp.json()["trace_id"] == header_trace
    assert len(header_trace) == 12


def test_middleware_generates_unique_trace_ids():
    client = TestClient(build_app())
    first = client.get("/whoami").headers["x-trace-id"]
    second = client.get("/whoami").headers["x-trace-id"]
    assert first != second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_logging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.logging'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/core/logging.py
import contextvars
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


def new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


class _TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_TraceIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(trace_id)s] %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = new_trace_id()
        token = trace_id_var.set(trace_id)
        try:
            response = await call_next(request)
        finally:
            trace_id_var.reset(token)
        response.headers["X-Trace-Id"] = trace_id
        return response
```

```python
# backend/main.py (append)
from core.logging import TraceIdMiddleware, configure_logging

configure_logging()
app.add_middleware(TraceIdMiddleware)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_logging.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/logging.py backend/main.py backend/tests/test_logging.py
git commit -m "feat(backend): add trace_id middleware for request tracing"
```

---

## Phase 2: Domain Models

### Task 4: Task/event/mode enums and schemas

**Files:**
- Create: `backend/models/__init__.py`
- Create: `backend/models/task.py`
- Create: `backend/models/events.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `models.task.FunctionType` (str Enum: `translate_en2zh`, `translate_zh2en`, `summarize`), `models.task.TaskStatus` (str Enum: `pending`, `running`, `done`, `failed`, `cancelled`), `models.task.ModelMode` (str Enum: `fast`, `think`), `models.task.resolve_mode(function_type: FunctionType, mode: str) -> ModelMode`.
- Produces: `models.task.TaskSubmitRequest`, `TaskSubmitResponse`, `TaskStatusResponse` (pydantic `BaseModel`s).
- Produces: `models.events.TaskEvent` (pydantic `BaseModel`: `type: Literal["token","progress","done","error","cancelled"]`, `stage: str | None`, `delta: str = ""`, `message: str | None`, `chunk_index: int | None`, `chunk_total: int | None`, `result: str | None`, `duration_ms: int | None`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_models.py
import pytest
from pydantic import ValidationError as PydanticValidationError

from models.task import FunctionType, ModelMode, TaskSubmitRequest, resolve_mode
from models.events import TaskEvent


@pytest.mark.parametrize(
    "function_type,mode,expected",
    [
        (FunctionType.TRANSLATE_EN2ZH, "auto", ModelMode.FAST),
        (FunctionType.TRANSLATE_ZH2EN, "auto", ModelMode.FAST),
        (FunctionType.SUMMARIZE, "auto", ModelMode.THINK),
        (FunctionType.TRANSLATE_EN2ZH, "think", ModelMode.THINK),
        (FunctionType.SUMMARIZE, "fast", ModelMode.FAST),
    ],
)
def test_resolve_mode(function_type, mode, expected):
    assert resolve_mode(function_type, mode) == expected


def test_task_submit_request_rejects_empty_text():
    with pytest.raises(PydanticValidationError):
        TaskSubmitRequest(function_type=FunctionType.SUMMARIZE, text="")


def test_task_event_defaults():
    event = TaskEvent(type="token", stage="draft", delta="他")
    assert event.result is None
    assert event.chunk_index is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/models/__init__.py
```

```python
# backend/models/task.py
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class FunctionType(str, Enum):
    TRANSLATE_EN2ZH = "translate_en2zh"
    TRANSLATE_ZH2EN = "translate_zh2en"
    SUMMARIZE = "summarize"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelMode(str, Enum):
    FAST = "fast"
    THINK = "think"


def resolve_mode(function_type: FunctionType, mode: str) -> ModelMode:
    if mode == "fast":
        return ModelMode.FAST
    if mode == "think":
        return ModelMode.THINK
    return ModelMode.THINK if function_type == FunctionType.SUMMARIZE else ModelMode.FAST


class TaskSubmitRequest(BaseModel):
    function_type: FunctionType
    text: str = Field(min_length=1)
    max_points: int | None = Field(default=None, ge=1, le=10)
    mode: Literal["auto", "fast", "think"] = "auto"


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: TaskStatus


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: str | None = None
    error: str | None = None
    duration_ms: int | None = None
```

```python
# backend/models/events.py
from typing import Literal

from pydantic import BaseModel


class TaskEvent(BaseModel):
    type: Literal["token", "progress", "done", "error", "cancelled"]
    stage: str | None = None
    delta: str = ""
    message: str | None = None
    chunk_index: int | None = None
    chunk_total: int | None = None
    result: str | None = None
    duration_ms: int | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/models backend/tests/test_models.py
git commit -m "feat(backend): add task/event enums and pydantic schemas"
```

---

## Phase 3: Persistence

### Task 5: SQLite call-record store

**Files:**
- Create: `backend/models/record.py`
- Create: `backend/services/__init__.py`
- Create: `backend/services/record_store.py`
- Test: `backend/tests/test_record_store.py`

**Interfaces:**
- Consumes: `models.task.FunctionType`, `TaskStatus`, `ModelMode` from Task 4.
- Produces: `services.record_store.init_db(path: str) -> None` (creates table if absent), `services.record_store.save_record(db_path, *, task_id: str, function_type: FunctionType, input_text: str, output_text: str, model_mode: ModelMode, status: TaskStatus, duration_ms: int) -> None`, `services.record_store.list_records(db_path, limit: int = 50, offset: int = 0) -> list[dict]` (newest first).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_record_store.py
import pytest

from models.task import FunctionType, ModelMode, TaskStatus
from services.record_store import init_db, list_records, save_record


@pytest.mark.asyncio
async def test_save_and_list_records(tmp_path):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    await save_record(
        db_path,
        task_id="t1",
        function_type=FunctionType.SUMMARIZE,
        input_text="长文本",
        output_text="摘要",
        model_mode=ModelMode.THINK,
        status=TaskStatus.DONE,
        duration_ms=1234,
    )
    await save_record(
        db_path,
        task_id="t2",
        function_type=FunctionType.TRANSLATE_EN2ZH,
        input_text="Hello",
        output_text="你好",
        model_mode=ModelMode.FAST,
        status=TaskStatus.DONE,
        duration_ms=200,
    )

    records = await list_records(db_path, limit=10, offset=0)

    assert len(records) == 2
    assert records[0]["task_id"] == "t2"  # newest first
    assert records[1]["task_id"] == "t1"
    assert records[0]["duration_ms"] == 200
    assert records[1]["function_type"] == "summarize"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_record_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/__init__.py
```

```python
# backend/models/record.py
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS call_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    function_type TEXT NOT NULL,
    input_text TEXT NOT NULL,
    output_text TEXT NOT NULL,
    model_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
```

```python
# backend/services/record_store.py
import os

import aiosqlite

from models.record import CREATE_TABLE_SQL
from models.task import FunctionType, ModelMode, TaskStatus


async def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


async def save_record(
    db_path: str,
    *,
    task_id: str,
    function_type: FunctionType,
    input_text: str,
    output_text: str,
    model_mode: ModelMode,
    status: TaskStatus,
    duration_ms: int,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO call_records
                (task_id, function_type, input_text, output_text, model_mode, status, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                function_type.value,
                input_text,
                output_text,
                model_mode.value,
                status.value,
                duration_ms,
            ),
        )
        await db.commit()


async def list_records(db_path: str, limit: int = 50, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM call_records ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_record_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models/record.py backend/services/__init__.py backend/services/record_store.py backend/tests/test_record_store.py
git commit -m "feat(backend): add SQLite call_records store"
```

---

### Task 6: Redis-backed task status service

**Files:**
- Create: `backend/services/task_service.py`
- Test: `backend/tests/test_task_service.py`

**Interfaces:**
- Consumes: `models.task.TaskStatus`.
- Produces: `services.task_service.create_task(redis, function_type: str, text: str, max_points: int | None, mode: str) -> str` (returns new `task_id`, stores `{"status": "pending", "function_type", "text", "max_points", "mode"}` as a Redis hash under `task:{task_id}`, TTL 24h), `get_task(redis, task_id: str) -> dict | None`, `set_status(redis, task_id, status: TaskStatus, *, result: str | None = None, error: str | None = None, duration_ms: int | None = None) -> None`, `request_cancel(redis, task_id: str) -> bool` (returns `False` if task doesn't exist), `is_cancelled(redis, task_id: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_task_service.py
import pytest
from fakeredis import FakeAsyncRedis

from models.task import TaskStatus
from services import task_service


@pytest.fixture
async def redis():
    r = FakeAsyncRedis()
    yield r
    await r.aclose()


@pytest.mark.asyncio
async def test_create_and_get_task(redis):
    task_id = await task_service.create_task(redis, "summarize", "长文本", 3, "auto")
    task = await task_service.get_task(redis, task_id)
    assert task["status"] == "pending"
    assert task["function_type"] == "summarize"
    assert task["text"] == "长文本"
    assert task["max_points"] == "3"


@pytest.mark.asyncio
async def test_get_task_missing_returns_none(redis):
    assert await task_service.get_task(redis, "does-not-exist") is None


@pytest.mark.asyncio
async def test_set_status_updates_fields(redis):
    task_id = await task_service.create_task(redis, "translate_en2zh", "Hello", None, "auto")
    await task_service.set_status(redis, task_id, TaskStatus.DONE, result="你好", duration_ms=150)
    task = await task_service.get_task(redis, task_id)
    assert task["status"] == "done"
    assert task["result"] == "你好"
    assert task["duration_ms"] == "150"


@pytest.mark.asyncio
async def test_cancel_flow(redis):
    task_id = await task_service.create_task(redis, "summarize", "text", 3, "auto")
    assert await task_service.is_cancelled(redis, task_id) is False
    assert await task_service.request_cancel(redis, task_id) is True
    assert await task_service.is_cancelled(redis, task_id) is True


@pytest.mark.asyncio
async def test_cancel_missing_task_returns_false(redis):
    assert await task_service.request_cancel(redis, "nope") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_task_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.task_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/task_service.py
import uuid

from models.task import TaskStatus

_TTL_SECONDS = 24 * 60 * 60


def _key(task_id: str) -> str:
    return f"task:{task_id}"


async def create_task(redis, function_type: str, text: str, max_points: int | None, mode: str) -> str:
    task_id = uuid.uuid4().hex
    mapping = {
        "status": TaskStatus.PENDING.value,
        "function_type": function_type,
        "text": text,
        "mode": mode,
        "cancelled": "0",
    }
    if max_points is not None:
        mapping["max_points"] = str(max_points)
    key = _key(task_id)
    await redis.hset(key, mapping=mapping)
    await redis.expire(key, _TTL_SECONDS)
    return task_id


async def get_task(redis, task_id: str) -> dict | None:
    data = await redis.hgetall(_key(task_id))
    if not data:
        return None
    return {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in data.items()
    }


async def set_status(
    redis,
    task_id: str,
    status: TaskStatus,
    *,
    result: str | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
) -> None:
    mapping = {"status": status.value}
    if result is not None:
        mapping["result"] = result
    if error is not None:
        mapping["error"] = error
    if duration_ms is not None:
        mapping["duration_ms"] = str(duration_ms)
    await redis.hset(_key(task_id), mapping=mapping)


async def request_cancel(redis, task_id: str) -> bool:
    exists = await redis.exists(_key(task_id))
    if not exists:
        return False
    await redis.hset(_key(task_id), mapping={"cancelled": "1"})
    return True


async def is_cancelled(redis, task_id: str) -> bool:
    value = await redis.hget(_key(task_id), "cancelled")
    if value is None:
        return False
    return (value.decode() if isinstance(value, bytes) else value) == "1"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_task_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/task_service.py backend/tests/test_task_service.py
git commit -m "feat(backend): add Redis-backed task status/cancel service"
```

---

## Phase 4: LLM Client

### Task 7: OpenAI-compatible LLM client with mock fallback

**Files:**
- Create: `backend/services/llm_client.py`
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Consumes: `core.config.settings`, `models.task.ModelMode`.
- Produces: `services.llm_client.stream_completion(messages: list[dict], mode: ModelMode) -> AsyncIterator[str]` — yields text deltas. Uses `openai.AsyncOpenAI` when `settings.llm_api_key` is non-empty; otherwise yields from a local mock generator (clearly commented as simulation, same call signature so callers never branch on it).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_llm_client.py
from types import SimpleNamespace

import pytest

from core.config import settings
from models.task import ModelMode
from services import llm_client


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeStream:
    def __init__(self, pieces):
        self._pieces = pieces

    def __aiter__(self):
        self._iter = iter(self._pieces)
        return self

    async def __anext__(self):
        try:
            return _FakeChunk(next(self._iter))
        except StopIteration:
            raise StopAsyncIteration


class _FakeCompletions:
    def __init__(self, pieces):
        self._pieces = pieces
        self.last_call = None

    async def create(self, **kwargs):
        self.last_call = kwargs
        return _FakeStream(self._pieces)


class _FakeChat:
    def __init__(self, pieces):
        self.completions = _FakeCompletions(pieces)


class _FakeAsyncOpenAI:
    def __init__(self, pieces):
        self.chat = _FakeChat(pieces)


@pytest.mark.asyncio
async def test_stream_completion_uses_real_client_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    fake_client = _FakeAsyncOpenAI(["你", "好"])
    monkeypatch.setattr(llm_client, "_get_client", lambda: fake_client)

    deltas = [d async for d in llm_client.stream_completion([{"role": "user", "content": "hi"}], ModelMode.FAST)]

    assert deltas == ["你", "好"]
    assert fake_client.chat.completions.last_call["model"] == settings.llm_model_fast
    assert fake_client.chat.completions.last_call["stream"] is True


@pytest.mark.asyncio
async def test_stream_completion_picks_think_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    fake_client = _FakeAsyncOpenAI(["ok"])
    monkeypatch.setattr(llm_client, "_get_client", lambda: fake_client)

    [d async for d in llm_client.stream_completion([{"role": "user", "content": "hi"}], ModelMode.THINK)]

    assert fake_client.chat.completions.last_call["model"] == settings.llm_model_think


@pytest.mark.asyncio
async def test_stream_completion_falls_back_to_mock_without_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")

    deltas = [d async for d in llm_client.stream_completion([{"role": "user", "content": "hi"}], ModelMode.FAST)]

    assert len(deltas) > 0
    assert "".join(deltas)  # non-empty simulated response
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_llm_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.llm_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/llm_client.py
import asyncio
from typing import AsyncIterator

from openai import AsyncOpenAI

from core.config import settings
from models.task import ModelMode

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    return _client


async def _mock_stream(messages: list[dict], mode: ModelMode) -> AsyncIterator[str]:
    """No LLM_API_KEY configured: simulate a streaming response locally so the
    full request -> queue -> SSE pipeline still runs end-to-end. The real call
    path above (AsyncOpenAI against an OpenAI-compatible endpoint) is what
    activates once a key is supplied in .env — this is pseudocode standing in
    for it, not a separate code path callers need to know about."""
    last_user_content = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    prefix = "[mock-think] " if mode == ModelMode.THINK else "[mock] "
    simulated = f"{prefix}模拟回复：{last_user_content[:50]}"
    for ch in simulated:
        await asyncio.sleep(0)
        yield ch


async def stream_completion(messages: list[dict], mode: ModelMode) -> AsyncIterator[str]:
    if not settings.llm_api_key:
        async for delta in _mock_stream(messages, mode):
            yield delta
        return

    model = settings.llm_model_think if mode == ModelMode.THINK else settings.llm_model_fast
    client = _get_client()
    stream = await client.chat.completions.create(model=model, messages=messages, stream=True)
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_llm_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(backend): add OpenAI-compatible LLM client with mock fallback"
```

---

## Phase 5: Task Pipelines

### Task 8: Text chunking utility

**Files:**
- Create: `backend/worker/__init__.py`
- Create: `backend/worker/chunking.py`
- Test: `backend/tests/test_chunking.py`

**Interfaces:**
- Produces: `worker.chunking.chunk_text(text: str, max_chars: int = 6000, overlap_chars: int = 400) -> list[str]`. Character-count based (approximating ~4 chars/token) — deliberately not a real tokenizer, documented as such. Never returns an empty list; returns `[text]` unchanged when `len(text) <= max_chars`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_chunking.py
from worker.chunking import chunk_text


def test_short_text_returns_single_chunk():
    text = "短文本"
    assert chunk_text(text, max_chars=6000) == [text]


def test_long_text_splits_into_multiple_chunks():
    text = "A" * 15000
    chunks = chunk_text(text, max_chars=6000, overlap_chars=400)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 6000


def test_chunks_overlap():
    text = "0123456789" * 1000  # 10000 chars
    chunks = chunk_text(text, max_chars=6000, overlap_chars=400)
    assert chunks[1][:400] == chunks[0][-400:]


def test_no_empty_chunks():
    text = "x" * 12001
    chunks = chunk_text(text, max_chars=6000, overlap_chars=400)
    assert all(len(c) > 0 for c in chunks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chunking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/worker/__init__.py
```

```python
# backend/worker/chunking.py
def chunk_text(text: str, max_chars: int = 6000, overlap_chars: int = 400) -> list[str]:
    """Approximate token-budget chunking by character count (~4 chars/token
    heuristic) since DeepSeek's tokenizer isn't published. Adjacent chunks
    overlap by `overlap_chars` so summaries don't lose context at a hard
    cut boundary."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max_chars - overlap_chars
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += step
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_chunking.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/worker/__init__.py backend/worker/chunking.py backend/tests/test_chunking.py
git commit -m "feat(backend): add character-budget text chunking utility"
```

---

### Task 9: Translate pipeline (Draft + Review)

**Files:**
- Create: `backend/worker/pipelines/__init__.py`
- Create: `backend/worker/pipelines/translate.py`
- Test: `backend/tests/test_pipeline_translate.py`

**Interfaces:**
- Consumes: `services.llm_client.stream_completion`, `models.task.FunctionType`, `ModelMode`, `models.events.TaskEvent`.
- Produces: `worker.pipelines.translate.run_translate(text: str, function_type: FunctionType, mode: ModelMode) -> AsyncIterator[TaskEvent]`. Always emits `token` events with `stage="draft"`, then (only when `mode == ModelMode.THINK`) a `progress` event (`stage="review"`) followed by `token` events with `stage="review"`, then exactly one terminal `done` event carrying the final `result`. In `fast` mode, `done.result` is the concatenated draft text.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pipeline_translate.py
import pytest

from models.task import FunctionType, ModelMode
from worker.pipelines import translate as translate_pipeline


async def _fake_stream_factory(responses):
    calls = []

    async def fake_stream_completion(messages, mode):
        calls.append((messages, mode))
        for ch in responses[len(calls) - 1]:
            yield ch

    return fake_stream_completion, calls


@pytest.mark.asyncio
async def test_fast_mode_only_drafts(monkeypatch):
    fake, calls = await _fake_stream_factory(["你好"])
    monkeypatch.setattr(translate_pipeline, "stream_completion", fake)

    events = [e async for e in translate_pipeline.run_translate("Hello", FunctionType.TRANSLATE_EN2ZH, ModelMode.FAST)]

    stages = [e.stage for e in events if e.type == "token"]
    assert stages == ["draft", "draft"]
    assert events[-1].type == "done"
    assert events[-1].result == "你好"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_think_mode_runs_draft_then_review(monkeypatch):
    fake, calls = await _fake_stream_factory(["你好", "你好呀"])
    monkeypatch.setattr(translate_pipeline, "stream_completion", fake)

    events = [e async for e in translate_pipeline.run_translate("Hello", FunctionType.TRANSLATE_EN2ZH, ModelMode.THINK)]

    types_stages = [(e.type, e.stage) for e in events]
    assert ("progress", "review") in types_stages
    review_tokens = [e for e in events if e.type == "token" and e.stage == "review"]
    assert "".join(e.delta for e in review_tokens) == "你好呀"
    assert events[-1].result == "你好呀"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_think_mode_review_can_keep_draft_unchanged(monkeypatch):
    fake, calls = await _fake_stream_factory(["OK", "OK"])
    monkeypatch.setattr(translate_pipeline, "stream_completion", fake)

    events = [e async for e in translate_pipeline.run_translate("hi", FunctionType.TRANSLATE_EN2ZH, ModelMode.THINK)]

    assert events[-1].result == "OK"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline_translate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.pipelines'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/worker/pipelines/__init__.py
```

```python
# backend/worker/pipelines/translate.py
from typing import AsyncIterator

from models.events import TaskEvent
from models.task import FunctionType, ModelMode
from services.llm_client import stream_completion

_DIRECTION_LABEL = {
    FunctionType.TRANSLATE_EN2ZH: "英译中",
    FunctionType.TRANSLATE_ZH2EN: "中译英",
}


def _draft_messages(text: str, function_type: FunctionType) -> list[dict]:
    label = _DIRECTION_LABEL[function_type]
    return [
        {"role": "system", "content": f"你是专业翻译，请将用户输入做{label}翻译，只输出译文。"},
        {"role": "user", "content": text},
    ]


def _review_messages(original: str, draft: str, function_type: FunctionType) -> list[dict]:
    label = _DIRECTION_LABEL[function_type]
    return [
        {
            "role": "system",
            "content": (
                f"你是专业译审，请检查以下{label}翻译是否准确、完整、通顺。"
                "如需修改，只输出修正后的完整译文；如果不需要修改，原样输出初稿译文。不要输出解释。"
            ),
        },
        {"role": "user", "content": f"原文：{original}\n初稿译文：{draft}"},
    ]


async def run_translate(text: str, function_type: FunctionType, mode: ModelMode) -> AsyncIterator[TaskEvent]:
    draft_text = ""
    async for delta in stream_completion(_draft_messages(text, function_type), ModelMode.FAST):
        draft_text += delta
        yield TaskEvent(type="token", stage="draft", delta=delta)

    if mode != ModelMode.THINK:
        yield TaskEvent(type="done", result=draft_text)
        return

    yield TaskEvent(type="progress", stage="review", message="精修中...")
    review_text = ""
    async for delta in stream_completion(_review_messages(text, draft_text, function_type), ModelMode.THINK):
        review_text += delta
        yield TaskEvent(type="token", stage="review", delta=delta)

    yield TaskEvent(type="done", result=review_text or draft_text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pipeline_translate.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/worker/pipelines/__init__.py backend/worker/pipelines/translate.py backend/tests/test_pipeline_translate.py
git commit -m "feat(backend): add Draft+Review translate pipeline"
```

---

### Task 10: Summarize pipeline (Map-Reduce)

**Files:**
- Create: `backend/worker/pipelines/summarize.py`
- Test: `backend/tests/test_pipeline_summarize.py`

**Interfaces:**
- Consumes: `worker.chunking.chunk_text`, `services.llm_client.stream_completion`, `models.events.TaskEvent`, `models.task.ModelMode`.
- Produces: `worker.pipelines.summarize.run_summarize(text: str, max_points: int, mode: ModelMode) -> AsyncIterator[TaskEvent]`. For single-chunk input, skips the Map phase and reduces directly on the original text. For multi-chunk input, emits one `progress` event (`stage="chunk"`, `chunk_index`, `chunk_total`) per chunk before mapping it, then reduces the concatenated chunk summaries. The Reduce phase always emits `token` events (`stage="reduce"`) and a terminal `done` event.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pipeline_summarize.py
import pytest

from models.task import ModelMode
from worker.pipelines import summarize as summarize_pipeline


@pytest.mark.asyncio
async def test_short_text_skips_map_phase(monkeypatch):
    calls = []

    async def fake_stream_completion(messages, mode):
        calls.append((messages, mode))
        for ch in "摘要结果":
            yield ch

    monkeypatch.setattr(summarize_pipeline, "stream_completion", fake_stream_completion)
    monkeypatch.setattr(summarize_pipeline, "chunk_text", lambda text, **kw: [text])

    events = [e async for e in summarize_pipeline.run_summarize("短文本", 3, ModelMode.THINK)]

    assert len(calls) == 1  # only the reduce call, no map calls
    assert calls[0][1] == ModelMode.THINK
    progress_events = [e for e in events if e.type == "progress"]
    assert progress_events == []
    assert events[-1].type == "done"
    assert events[-1].result == "摘要结果"


@pytest.mark.asyncio
async def test_long_text_maps_each_chunk_then_reduces(monkeypatch):
    calls = []

    async def fake_stream_completion(messages, mode):
        calls.append((messages, mode))
        text = "chunk-summary" if len(calls) <= 3 else "final-summary"
        for ch in text:
            yield ch

    monkeypatch.setattr(summarize_pipeline, "stream_completion", fake_stream_completion)
    monkeypatch.setattr(summarize_pipeline, "chunk_text", lambda text, **kw: ["c1", "c2", "c3"])

    events = [e async for e in summarize_pipeline.run_summarize("长文本" * 100, 3, ModelMode.FAST)]

    progress_events = [e for e in events if e.type == "progress"]
    assert [e.chunk_index for e in progress_events] == [1, 2, 3]
    assert [e.chunk_total for e in progress_events] == [3, 3, 3]
    assert len(calls) == 4  # 3 map calls + 1 reduce call
    assert all(mode == ModelMode.FAST for _, mode in calls[:3])  # map always fast
    assert calls[3][1] == ModelMode.FAST  # reduce follows requested mode
    assert events[-1].result == "final-summary"


@pytest.mark.asyncio
async def test_reduce_prompt_includes_max_points(monkeypatch):
    captured = {}

    async def fake_stream_completion(messages, mode):
        captured["messages"] = messages
        yield "ok"

    monkeypatch.setattr(summarize_pipeline, "stream_completion", fake_stream_completion)
    monkeypatch.setattr(summarize_pipeline, "chunk_text", lambda text, **kw: [text])

    [e async for e in summarize_pipeline.run_summarize("text", 5, ModelMode.FAST)]

    joined = " ".join(m["content"] for m in captured["messages"])
    assert "5" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline_summarize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.pipelines.summarize'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/worker/pipelines/summarize.py
from typing import AsyncIterator

from models.events import TaskEvent
from models.task import ModelMode
from services.llm_client import stream_completion
from worker.chunking import chunk_text


def _map_messages(chunk: str) -> list[dict]:
    return [
        {"role": "system", "content": "请用简洁的中文概括以下文本片段的要点，只输出概括内容。"},
        {"role": "user", "content": chunk},
    ]


def _reduce_messages(combined: str, max_points: int) -> list[dict]:
    return [
        {
            "role": "system",
            "content": f"请将以下内容整合为不超过 {max_points} 个要点的总结，用中文分点输出。",
        },
        {"role": "user", "content": combined},
    ]


async def run_summarize(text: str, max_points: int, mode: ModelMode) -> AsyncIterator[TaskEvent]:
    chunks = chunk_text(text)

    if len(chunks) == 1:
        combined = chunks[0]
    else:
        chunk_summaries = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            yield TaskEvent(
                type="progress",
                stage="chunk",
                message=f"正在处理第 {index}/{total} 块",
                chunk_index=index,
                chunk_total=total,
            )
            summary = ""
            async for delta in stream_completion(_map_messages(chunk), ModelMode.FAST):
                summary += delta
            chunk_summaries.append(summary)
        combined = "\n".join(chunk_summaries)

    final_text = ""
    async for delta in stream_completion(_reduce_messages(combined, max_points), mode):
        final_text += delta
        yield TaskEvent(type="token", stage="reduce", delta=delta)

    yield TaskEvent(type="done", result=final_text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pipeline_summarize.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/worker/pipelines/summarize.py backend/tests/test_pipeline_summarize.py
git commit -m "feat(backend): add Map-Reduce summarize pipeline"
```

---

## Phase 6: Worker Wiring

### Task 11: arq worker task entrypoint

**Files:**
- Create: `backend/worker/tasks.py`
- Create: `backend/worker/settings.py`
- Test: `backend/tests/test_worker_tasks.py`

**Interfaces:**
- Consumes: `services.task_service` (Task 6), `services.record_store` (Task 5), `services.llm_client` (Task 7, indirectly via pipelines), `worker.pipelines.translate.run_translate`, `worker.pipelines.summarize.run_summarize`, `models.task.{FunctionType,TaskStatus,ModelMode,resolve_mode}`, `models.events.TaskEvent`, `core.config.settings`.
- Produces: `worker.tasks.execute_task(ctx: dict, task_id: str) -> None` — an arq task function. `ctx` must contain `ctx["redis"]` (task-status Redis client, also used for pub/sub) and `ctx["sqlite_path"]` (string). Publishes each pipeline event as JSON to Redis channel `f"task_events:{task_id}"` via `redis.publish`. Checks `task_service.is_cancelled` before publishing each event; on cancellation publishes a `TaskEvent(type="cancelled")` and stops. Persists status + record via `task_service.set_status` and `record_store.save_record` in all terminal cases (done/failed/cancelled). `worker.settings.WorkerSettings` — arq settings class wired to `execute_task`, `redis_settings` from `settings.redis_url`, `job_timeout=settings.task_timeout_seconds`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_worker_tasks.py
import json

import pytest
from fakeredis import FakeAsyncRedis

from models.task import FunctionType, ModelMode, TaskStatus
from services import task_service
from worker import tasks as worker_tasks


@pytest.fixture
async def redis():
    r = FakeAsyncRedis()
    yield r
    await r.aclose()


async def _collect_published(redis, task_id, count):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"task_events:{task_id}")
    messages = []
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        messages.append(json.loads(message["data"]))
        if len(messages) >= count:
            break
    await pubsub.unsubscribe(f"task_events:{task_id}")
    return messages


@pytest.mark.asyncio
async def test_execute_task_happy_path(monkeypatch, redis, tmp_path):
    async def fake_run_translate(text, function_type, mode):
        from models.events import TaskEvent
        yield TaskEvent(type="token", stage="draft", delta="你好")
        yield TaskEvent(type="done", result="你好")

    monkeypatch.setattr(worker_tasks, "run_translate", fake_run_translate)

    db_path = str(tmp_path / "app.db")
    from services.record_store import init_db
    await init_db(db_path)

    task_id = await task_service.create_task(redis, "translate_en2zh", "Hello", None, "auto")
    ctx = {"redis": redis, "sqlite_path": db_path}

    import asyncio
    collector = asyncio.create_task(_collect_published(redis, task_id, 2))
    await asyncio.sleep(0.05)  # let subscriber attach before publishing starts
    await worker_tasks.execute_task(ctx, task_id)
    published = await asyncio.wait_for(collector, timeout=2)

    assert published[0]["type"] == "token"
    assert published[1]["type"] == "done"
    assert published[1]["result"] == "你好"

    task = await task_service.get_task(redis, task_id)
    assert task["status"] == "done"
    assert task["result"] == "你好"

    from services.record_store import list_records
    records = await list_records(db_path)
    assert len(records) == 1
    assert records[0]["output_text"] == "你好"


@pytest.mark.asyncio
async def test_execute_task_stops_when_cancelled(monkeypatch, redis, tmp_path):
    async def fake_run_translate(text, function_type, mode):
        from models.events import TaskEvent
        yield TaskEvent(type="token", stage="draft", delta="片段1")
        yield TaskEvent(type="token", stage="draft", delta="片段2")
        yield TaskEvent(type="done", result="片段1片段2")

    monkeypatch.setattr(worker_tasks, "run_translate", fake_run_translate)

    db_path = str(tmp_path / "app.db")
    from services.record_store import init_db
    await init_db(db_path)

    task_id = await task_service.create_task(redis, "translate_en2zh", "Hello", None, "auto")
    await task_service.request_cancel(redis, task_id)
    ctx = {"redis": redis, "sqlite_path": db_path}

    await worker_tasks.execute_task(ctx, task_id)

    task = await task_service.get_task(redis, task_id)
    assert task["status"] == "cancelled"


@pytest.mark.asyncio
async def test_execute_task_marks_failed_on_pipeline_error(monkeypatch, redis, tmp_path):
    async def fake_run_translate(text, function_type, mode):
        raise RuntimeError("model API down")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    monkeypatch.setattr(worker_tasks, "run_translate", fake_run_translate)

    db_path = str(tmp_path / "app.db")
    from services.record_store import init_db
    await init_db(db_path)

    task_id = await task_service.create_task(redis, "translate_en2zh", "Hello", None, "auto")
    ctx = {"redis": redis, "sqlite_path": db_path}

    await worker_tasks.execute_task(ctx, task_id)

    task = await task_service.get_task(redis, task_id)
    assert task["status"] == "failed"
    assert "model API down" in task["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_worker_tasks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.tasks'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/worker/tasks.py
import time

from models.events import TaskEvent
from models.task import FunctionType, TaskStatus, resolve_mode
from services import record_store, task_service
from worker.pipelines.summarize import run_summarize
from worker.pipelines.translate import run_translate


async def _publish(redis, task_id: str, event: TaskEvent) -> None:
    await redis.publish(f"task_events:{task_id}", event.model_dump_json())


async def execute_task(ctx: dict, task_id: str) -> None:
    redis = ctx["redis"]
    sqlite_path = ctx["sqlite_path"]

    task = await task_service.get_task(redis, task_id)
    function_type = FunctionType(task["function_type"])
    text = task["text"]
    max_points = int(task["max_points"]) if "max_points" in task else 3
    mode = resolve_mode(function_type, task["mode"])

    await task_service.set_status(redis, task_id, TaskStatus.RUNNING)
    start = time.monotonic()
    result_text = ""
    status = TaskStatus.DONE
    error_message: str | None = None

    try:
        if function_type == FunctionType.SUMMARIZE:
            pipeline = run_summarize(text, max_points, mode)
        else:
            pipeline = run_translate(text, function_type, mode)

        async for event in pipeline:
            if await task_service.is_cancelled(redis, task_id):
                status = TaskStatus.CANCELLED
                await _publish(redis, task_id, TaskEvent(type="cancelled"))
                break
            await _publish(redis, task_id, event)
            if event.type == "done":
                result_text = event.result or ""
    except Exception as exc:  # noqa: BLE001 - persisted below, not swallowed
        status = TaskStatus.FAILED
        error_message = str(exc)
        await _publish(redis, task_id, TaskEvent(type="error", message=error_message))

    duration_ms = int((time.monotonic() - start) * 1000)
    await task_service.set_status(
        redis, task_id, status, result=result_text, error=error_message, duration_ms=duration_ms
    )
    await record_store.save_record(
        sqlite_path,
        task_id=task_id,
        function_type=function_type,
        input_text=text,
        output_text=result_text,
        model_mode=mode,
        status=status,
        duration_ms=duration_ms,
    )
```

```python
# backend/worker/settings.py
from arq.connections import RedisSettings

from core.config import settings
from worker.tasks import execute_task


class WorkerSettings:
    functions = [execute_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = settings.task_timeout_seconds

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        import redis.asyncio as redis_asyncio

        from services.record_store import init_db

        ctx["redis"] = redis_asyncio.from_url(settings.redis_url)
        ctx["sqlite_path"] = settings.sqlite_path
        await init_db(settings.sqlite_path)

    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        await ctx["redis"].aclose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_worker_tasks.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/worker/tasks.py backend/worker/settings.py backend/tests/test_worker_tasks.py
git commit -m "feat(backend): wire arq worker task to pipelines, pub/sub, and persistence"
```

---

## Phase 7: API Layer

### Task 12: GET /api/functions

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/functions.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_api_functions.py`

**Interfaces:**
- Produces: `api.functions.router` (FastAPI `APIRouter`) exposing `GET /api/functions` → `{"functions": [{"id": "translate_en2zh", "name": str, "description": str}, ...]}` covering all three `FunctionType` values.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api_functions.py
from fastapi.testclient import TestClient

from main import app


def test_list_functions():
    client = TestClient(app)
    resp = client.get("/api/functions")
    assert resp.status_code == 200
    body = resp.json()
    ids = {f["id"] for f in body["functions"]}
    assert ids == {"translate_en2zh", "translate_zh2en", "summarize"}
    for f in body["functions"]:
        assert f["name"]
        assert f["description"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_functions.py -v`
Expected: FAIL with 404 (route not registered) or `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/api/__init__.py
```

```python
# backend/api/functions.py
from fastapi import APIRouter

router = APIRouter()

_FUNCTIONS = [
    {"id": "translate_en2zh", "name": "英译中", "description": "将英文文本翻译为中文"},
    {"id": "translate_zh2en", "name": "中译英", "description": "将中文文本翻译为英文"},
    {"id": "summarize", "name": "文本总结", "description": "对长文本生成要点总结"},
]


@router.get("/api/functions")
async def list_functions() -> dict:
    return {"functions": _FUNCTIONS}
```

```python
# backend/main.py (append)
from api.functions import router as functions_router

app.include_router(functions_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_functions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/__init__.py backend/api/functions.py backend/main.py backend/tests/test_api_functions.py
git commit -m "feat(backend): add GET /api/functions endpoint"
```

---

### Task 13: App-level dependency wiring (Redis pool, arq pool, SQLite init)

**Files:**
- Create: `backend/core/deps.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_deps.py`

**Interfaces:**
- Produces: `core.deps.get_redis() -> redis.asyncio.Redis` (FastAPI dependency, returns `app.state.redis`), `core.deps.get_arq_pool() -> arq.ArqRedis` (returns `app.state.arq_pool`), `core.deps.get_sqlite_path() -> str`. `main.py` gains `@app.on_event("startup")`/`"shutdown"` (or lifespan) that creates `app.state.redis`, `app.state.arq_pool`, and calls `record_store.init_db`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_deps.py
from fastapi.testclient import TestClient

from main import app


def test_startup_initializes_redis_and_arq_pool():
    with TestClient(app) as client:
        assert client.app.state.redis is not None
        assert client.app.state.arq_pool is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_deps.py -v`
Expected: FAIL with `AttributeError: 'State' object has no attribute 'redis'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/core/deps.py
from fastapi import Request


def get_redis(request: Request):
    return request.app.state.redis


def get_arq_pool(request: Request):
    return request.app.state.arq_pool


def get_sqlite_path(request: Request) -> str:
    return request.app.state.sqlite_path
```

```python
# backend/main.py (append)
import redis.asyncio as redis_asyncio
from arq.connections import RedisSettings, create_pool

from core.config import settings
from services.record_store import init_db


@app.on_event("startup")
async def on_startup() -> None:
    app.state.redis = redis_asyncio.from_url(settings.redis_url)
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.sqlite_path = settings.sqlite_path
    await init_db(settings.sqlite_path)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await app.state.redis.aclose()
    await app.state.arq_pool.aclose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_deps.py -v`
Expected: PASS

Note: this test requires a reachable Redis (e.g. `docker run -p 6379:6379 redis` or the project's `docker-compose` redis service) — unlike the fakeredis-based unit tests, this one exercises the real startup wiring.

- [ ] **Step 5: Commit**

```bash
git add backend/core/deps.py backend/main.py backend/tests/test_deps.py
git commit -m "feat(backend): wire Redis client and arq pool into app lifecycle"
```

---

### Task 14: POST /api/task and GET /api/task/{taskId}

**Files:**
- Create: `backend/api/tasks.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_api_tasks.py`

**Interfaces:**
- Consumes: `core.deps.{get_redis,get_arq_pool}`, `services.task_service`, `models.task.{TaskSubmitRequest,TaskSubmitResponse,TaskStatusResponse,TaskStatus}`, `core.errors.{ValidationError,TaskNotFoundError}`.
- Produces: `api.tasks.router` with `POST /api/task` (body: `TaskSubmitRequest`, response: `TaskSubmitResponse`; calls `task_service.create_task` then `arq_pool.enqueue_job("execute_task", task_id)`) and `GET /api/task/{taskId}` (response: `TaskStatusResponse`; raises `TaskNotFoundError` for unknown ids).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api_tasks.py
from unittest.mock import AsyncMock

import pytest
from fakeredis import FakeAsyncRedis
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    fake_redis = FakeAsyncRedis()
    fake_arq_pool = AsyncMock()
    app.state.redis = fake_redis
    app.state.arq_pool = fake_arq_pool
    with TestClient(app) as c:
        yield c, fake_arq_pool


def test_submit_task_enqueues_job(client):
    c, fake_arq_pool = client
    resp = c.post("/api/task", json={"function_type": "summarize", "text": "长文本", "max_points": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["task_id"]
    fake_arq_pool.enqueue_job.assert_awaited_once_with("execute_task", body["task_id"])


def test_submit_task_rejects_empty_text(client):
    c, _ = client
    resp = c.post("/api/task", json={"function_type": "summarize", "text": ""})
    assert resp.status_code == 422  # pydantic validation error


def test_get_task_status_after_submit(client):
    c, _ = client
    submit = c.post("/api/task", json={"function_type": "translate_en2zh", "text": "Hello"})
    task_id = submit.json()["task_id"]
    resp = c.get(f"/api/task/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_get_task_status_missing_returns_404(client):
    c, _ = client
    resp = c.get("/api/task/does-not-exist")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_tasks.py -v`
Expected: FAIL with 404 (routes not registered)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/api/tasks.py
from fastapi import APIRouter, Depends

from core.deps import get_arq_pool, get_redis
from core.errors import TaskNotFoundError
from models.task import TaskStatus, TaskStatusResponse, TaskSubmitRequest, TaskSubmitResponse
from services import task_service

router = APIRouter()


@router.post("/api/task", response_model=TaskSubmitResponse)
async def submit_task(
    payload: TaskSubmitRequest,
    redis=Depends(get_redis),
    arq_pool=Depends(get_arq_pool),
) -> TaskSubmitResponse:
    task_id = await task_service.create_task(
        redis, payload.function_type.value, payload.text, payload.max_points, payload.mode
    )
    await arq_pool.enqueue_job("execute_task", task_id)
    return TaskSubmitResponse(task_id=task_id, status=TaskStatus.PENDING)


@router.get("/api/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, redis=Depends(get_redis)) -> TaskStatusResponse:
    task = await task_service.get_task(redis, task_id)
    if task is None:
        raise TaskNotFoundError(f"task {task_id} not found")
    duration_ms = int(task["duration_ms"]) if "duration_ms" in task else None
    return TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus(task["status"]),
        result=task.get("result"),
        error=task.get("error"),
        duration_ms=duration_ms,
    )
```

```python
# backend/main.py (append)
from api.tasks import router as tasks_router

app.include_router(tasks_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_tasks.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/api/tasks.py backend/main.py backend/tests/test_api_tasks.py
git commit -m "feat(backend): add POST /api/task and GET /api/task/{taskId}"
```

---

### Task 15: DELETE /api/task/{taskId}

**Files:**
- Modify: `backend/api/tasks.py`
- Modify: `backend/tests/test_api_tasks.py`

**Interfaces:**
- Consumes: `services.task_service.request_cancel`.
- Produces: `DELETE /api/task/{taskId}` → `{"cancelled": true}` on success; raises `TaskNotFoundError` (404) for unknown ids.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api_tasks.py (append)
def test_cancel_task(client):
    c, _ = client
    submit = c.post("/api/task", json={"function_type": "summarize", "text": "text"})
    task_id = submit.json()["task_id"]
    resp = c.delete(f"/api/task/{task_id}")
    assert resp.status_code == 200
    assert resp.json() == {"cancelled": True}
    status = c.get(f"/api/task/{task_id}").json()
    assert status["status"] == "pending"  # cancel flag set, worker applies it async


def test_cancel_missing_task_returns_404(client):
    c, _ = client
    resp = c.delete("/api/task/does-not-exist")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_tasks.py -k cancel -v`
Expected: FAIL with 405 Method Not Allowed

- [ ] **Step 3: Write minimal implementation**

```python
# backend/api/tasks.py (append)
@router.delete("/api/task/{task_id}")
async def cancel_task(task_id: str, redis=Depends(get_redis)) -> dict:
    cancelled = await task_service.request_cancel(redis, task_id)
    if not cancelled:
        raise TaskNotFoundError(f"task {task_id} not found")
    return {"cancelled": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_tasks.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/api/tasks.py backend/tests/test_api_tasks.py
git commit -m "feat(backend): add DELETE /api/task/{taskId} cancellation endpoint"
```

---

### Task 16: GET /api/task/{taskId}/stream (SSE)

**Files:**
- Modify: `backend/api/tasks.py`
- Create: `backend/tests/test_api_stream.py`

**Interfaces:**
- Consumes: `services.task_service.get_task`, Redis pub/sub on channel `task_events:{taskId}`.
- Produces: `GET /api/task/{taskId}/stream` → `StreamingResponse` with `media_type="text/event-stream"`. Subscribes to the pub/sub channel first; if the task's stored status is already terminal (`done`/`failed`/`cancelled`) at that point, immediately emits one synthetic terminal event built from the stored record and closes — otherwise streams every message published on the channel, formatted as `data: {json}\n\n`, until a terminal event type (`done`/`error`/`cancelled`) is forwarded.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api_stream.py
import asyncio
import json

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient

from main import app
from models.task import TaskStatus
from services import task_service


@pytest.fixture
async def redis():
    r = FakeAsyncRedis()
    app.state.redis = r
    yield r
    await r.aclose()


async def _read_sse_events(response, count):
    events = []
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: "):]))
        if len(events) >= count:
            break
    return events


@pytest.mark.asyncio
async def test_stream_forwards_live_events(redis):
    task_id = await task_service.create_task(redis, "translate_en2zh", "Hello", None, "auto")

    async def publisher():
        await asyncio.sleep(0.05)
        await redis.publish(f"task_events:{task_id}", json.dumps({"type": "token", "stage": "draft", "delta": "你"}))
        await redis.publish(f"task_events:{task_id}", json.dumps({"type": "done", "result": "你好"}))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asyncio.create_task(publisher())
        async with client.stream("GET", f"/api/task/{task_id}/stream") as response:
            events = await asyncio.wait_for(_read_sse_events(response, 2), timeout=2)

    assert events[0]["type"] == "token"
    assert events[1]["type"] == "done"
    assert events[1]["result"] == "你好"


@pytest.mark.asyncio
async def test_stream_replays_terminal_state_for_already_done_task(redis):
    task_id = await task_service.create_task(redis, "translate_en2zh", "Hello", None, "auto")
    await task_service.set_status(redis, task_id, TaskStatus.DONE, result="你好", duration_ms=100)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", f"/api/task/{task_id}/stream") as response:
            events = await asyncio.wait_for(_read_sse_events(response, 1), timeout=2)

    assert events[0]["type"] == "done"
    assert events[0]["result"] == "你好"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_stream.py -v`
Expected: FAIL with 404 (route not registered)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/api/tasks.py (append)
import asyncio
import json

from fastapi.responses import StreamingResponse

from models.events import TaskEvent


async def _event_stream(redis, task_id: str):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"task_events:{task_id}")
    try:
        task = await task_service.get_task(redis, task_id)
        if task and task["status"] in {TaskStatus.DONE.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}:
            terminal = TaskEvent(
                type=task["status"] if task["status"] != TaskStatus.DONE.value else "done",
                result=task.get("result"),
                message=task.get("error"),
                duration_ms=int(task["duration_ms"]) if "duration_ms" in task else None,
            )
            yield f"data: {terminal.model_dump_json()}\n\n"
            return

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                await asyncio.sleep(0.05)
                continue
            raw = message["data"]
            payload = raw.decode() if isinstance(raw, bytes) else raw
            yield f"data: {payload}\n\n"
            event_type = json.loads(payload)["type"]
            if event_type in {"done", "error", "cancelled"}:
                break
    finally:
        await pubsub.unsubscribe(f"task_events:{task_id}")


@router.get("/api/task/{task_id}/stream")
async def stream_task(task_id: str, redis=Depends(get_redis)) -> StreamingResponse:
    return StreamingResponse(_event_stream(redis, task_id), media_type="text/event-stream")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_stream.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/api/tasks.py backend/tests/test_api_stream.py
git commit -m "feat(backend): add SSE stream endpoint with terminal-state replay"
```

---

### Task 17: GET /api/records

**Files:**
- Create: `backend/api/records.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_api_records.py`

**Interfaces:**
- Consumes: `services.record_store.list_records`, `core.deps.get_sqlite_path`.
- Produces: `api.records.router` with `GET /api/records?limit=&offset=` → `{"records": [...]}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api_records.py
from fastapi.testclient import TestClient

from main import app
from models.task import FunctionType, ModelMode, TaskStatus
from services.record_store import init_db, save_record


def test_list_records(tmp_path):
    db_path = str(tmp_path / "app.db")
    app.state.sqlite_path = db_path

    import asyncio

    async def seed():
        await init_db(db_path)
        await save_record(
            db_path,
            task_id="t1",
            function_type=FunctionType.SUMMARIZE,
            input_text="in",
            output_text="out",
            model_mode=ModelMode.THINK,
            status=TaskStatus.DONE,
            duration_ms=100,
        )

    asyncio.run(seed())

    client = TestClient(app)
    resp = client.get("/api/records")
    assert resp.status_code == 200
    records = resp.json()["records"]
    assert len(records) == 1
    assert records[0]["task_id"] == "t1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_records.py -v`
Expected: FAIL with 404 (route not registered)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/api/records.py
from fastapi import APIRouter, Depends, Query

from core.deps import get_sqlite_path
from services.record_store import list_records

router = APIRouter()


@router.get("/api/records")
async def get_records(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sqlite_path: str = Depends(get_sqlite_path),
) -> dict:
    records = await list_records(sqlite_path, limit=limit, offset=offset)
    return {"records": records}
```

```python
# backend/main.py (append)
from api.records import router as records_router

app.include_router(records_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api_records.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/records.py backend/main.py backend/tests/test_api_records.py
git commit -m "feat(backend): add GET /api/records query endpoint"
```

---

## Phase 8: CLI

### Task 18: CLI scaffolding + streaming client

**Files:**
- Create: `cli/pyproject.toml`
- Create: `cli/ai_app/__init__.py`
- Create: `cli/ai_app/client.py`
- Test: `cli/tests/test_client.py`

**Interfaces:**
- Produces: `ai_app.client.submit_task(base_url: str, function_type: str, text: str, max_points: int | None) -> str` (returns `task_id`), `ai_app.client.stream_task(base_url: str, task_id: str) -> Iterator[dict]` (sync generator yielding parsed SSE event dicts, using `httpx.Client().stream`), `ai_app.client.cancel_task(base_url: str, task_id: str) -> None`.

- [ ] **Step 1: Write pyproject.toml**

```toml
# cli/pyproject.toml
[project]
name = "ai-app-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["click==8.1.7", "httpx==0.27.2"]

[project.scripts]
ai-app = "ai_app.main:cli"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

```python
# cli/ai_app/__init__.py
```

- [ ] **Step 2: Write the failing test**

```python
# cli/tests/test_client.py
import json

import httpx
import pytest

from ai_app.client import cancel_task, stream_task, submit_task


def test_submit_task_posts_and_returns_task_id():
    def handler(request):
        assert request.url.path == "/api/task"
        body = json.loads(request.content)
        assert body == {"function_type": "translate_en2zh", "text": "Hello", "max_points": None, "mode": "auto"}
        return httpx.Response(200, json={"task_id": "abc123", "status": "pending"})

    transport = httpx.MockTransport(handler)
    task_id = submit_task("http://test", "translate_en2zh", "Hello", None, transport=transport)
    assert task_id == "abc123"


def test_stream_task_yields_parsed_events():
    def handler(request):
        assert request.url.path == "/api/task/abc123/stream"
        body = (
            b'data: {"type": "token", "delta": "\xe4\xbd\xa0"}\n\n'
            b'data: {"type": "done", "result": "\xe4\xbd\xa0"}\n\n'
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    events = list(stream_task("http://test", "abc123", transport=transport))
    assert events[0]["type"] == "token"
    assert events[1]["type"] == "done"


def test_cancel_task_sends_delete():
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"cancelled": True})

    transport = httpx.MockTransport(handler)
    cancel_task("http://test", "abc123", transport=transport)
    assert calls == ["DELETE"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd cli && python -m pytest tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_app'`

- [ ] **Step 4: Write minimal implementation**

```python
# cli/ai_app/client.py
import json
from typing import Iterator

import httpx


def submit_task(
    base_url: str,
    function_type: str,
    text: str,
    max_points: int | None,
    mode: str = "auto",
    transport: httpx.BaseTransport | None = None,
) -> str:
    with httpx.Client(base_url=base_url, transport=transport) as client:
        resp = client.post(
            "/api/task",
            json={"function_type": function_type, "text": text, "max_points": max_points, "mode": mode},
        )
        resp.raise_for_status()
        return resp.json()["task_id"]


def stream_task(base_url: str, task_id: str, transport: httpx.BaseTransport | None = None) -> Iterator[dict]:
    with httpx.Client(base_url=base_url, transport=transport) as client:
        with client.stream("GET", f"/api/task/{task_id}/stream") as response:
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                yield json.loads(line[len("data: "):])


def cancel_task(base_url: str, task_id: str, transport: httpx.BaseTransport | None = None) -> None:
    with httpx.Client(base_url=base_url, transport=transport) as client:
        resp = client.delete(f"/api/task/{task_id}")
        resp.raise_for_status()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd cli && python -m pytest tests/test_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add cli/pyproject.toml cli/ai_app/__init__.py cli/ai_app/client.py cli/tests/test_client.py
git commit -m "feat(cli): add HTTP client for submit/stream/cancel"
```

---

### Task 19: CLI commands (translate, summarize)

**Files:**
- Create: `cli/ai_app/main.py`
- Test: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: `ai_app.client.{submit_task,stream_task,cancel_task}`.
- Produces: `ai_app.main.cli` — a `click.Group` with commands `translate --text --from --to [--host]` and `summarize --text --max-points [--host]`. Both submit a task, stream tokens to stdout as they arrive (typewriter effect — no buffering the whole response before printing), and on `KeyboardInterrupt` call `cancel_task` before re-raising `SystemExit(1)`.

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_cli.py
from unittest.mock import patch

from click.testing import CliRunner

from ai_app.main import cli


def test_translate_command_streams_output():
    with patch("ai_app.main.submit_task", return_value="task-1") as mock_submit, patch(
        "ai_app.main.stream_task",
        return_value=iter(
            [
                {"type": "token", "stage": "draft", "delta": "你"},
                {"type": "token", "stage": "draft", "delta": "好"},
                {"type": "done", "result": "你好"},
            ]
        ),
    ) as mock_stream:
        runner = CliRunner()
        result = runner.invoke(cli, ["translate", "--text", "Hello", "--from", "en", "--to", "zh"])

    assert result.exit_code == 0
    assert "你好" in result.output
    mock_submit.assert_called_once()
    assert mock_submit.call_args.kwargs["function_type"] == "translate_en2zh"
    mock_stream.assert_called_once_with("http://localhost:8000", "task-1", transport=None)


def test_summarize_command_passes_max_points():
    with patch("ai_app.main.submit_task", return_value="task-2") as mock_submit, patch(
        "ai_app.main.stream_task",
        return_value=iter([{"type": "done", "result": "要点1；要点2"}]),
    ):
        runner = CliRunner()
        result = runner.invoke(cli, ["summarize", "--text", "长文本", "--max-points", "2"])

    assert result.exit_code == 0
    assert "要点1；要点2" in result.output
    assert mock_submit.call_args.kwargs["max_points"] == 2


def test_translate_rejects_unknown_direction():
    runner = CliRunner()
    result = runner.invoke(cli, ["translate", "--text", "Hello", "--from", "fr", "--to", "zh"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd cli && python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_app.main'`

- [ ] **Step 3: Write minimal implementation**

```python
# cli/ai_app/main.py
import sys

import click

from ai_app.client import cancel_task, stream_task, submit_task

_DIRECTION_MAP = {
    ("en", "zh"): "translate_en2zh",
    ("zh", "en"): "translate_zh2en",
}


@click.group()
def cli() -> None:
    """AI text processing CLI — translate/summarize via the backend API."""


def _run_and_stream(base_url: str, function_type: str, text: str, max_points: int | None) -> None:
    task_id = submit_task(base_url, function_type=function_type, text=text, max_points=max_points)
    try:
        for event in stream_task(base_url, task_id, transport=None):
            if event["type"] == "token":
                click.echo(event["delta"], nl=False)
            elif event["type"] == "progress" and event.get("message"):
                click.echo(f"\n[{event['message']}]", nl=False)
            elif event["type"] == "done":
                click.echo()
            elif event["type"] == "error":
                click.echo(f"\n[error] {event.get('message')}", err=True)
                sys.exit(1)
    except KeyboardInterrupt:
        cancel_task(base_url, task_id)
        click.echo("\n[cancelled]")
        sys.exit(1)


@cli.command()
@click.option("--text", required=True)
@click.option("--from", "from_lang", required=True, type=click.Choice(["en", "zh"]))
@click.option("--to", "to_lang", required=True, type=click.Choice(["en", "zh"]))
@click.option("--host", default="http://localhost:8000")
def translate(text: str, from_lang: str, to_lang: str, host: str) -> None:
    function_type = _DIRECTION_MAP.get((from_lang, to_lang))
    if function_type is None:
        raise click.BadParameter(f"unsupported direction {from_lang}->{to_lang}")
    _run_and_stream(host, function_type, text, None)


@cli.command()
@click.option("--text", required=True)
@click.option("--max-points", default=3, type=int)
@click.option("--host", default="http://localhost:8000")
def summarize(text: str, max_points: int, host: str) -> None:
    _run_and_stream(host, "summarize", text, max_points)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd cli && python -m pytest tests/test_cli.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add cli/ai_app/main.py cli/tests/test_cli.py
git commit -m "feat(cli): add streaming translate/summarize commands"
```

---

## Phase 9: Frontend

### Task 20: Frontend scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles/theme.css`

**Interfaces:**
- Produces: a runnable Vite dev server (`npm run dev`) rendering an `App` shell with `react-router-dom` routes for `/` (function list, added in Task 26), `/translate` (Task 28), `/summarize` (Task 30).

- [ ] **Step 1: Write package.json**

```json
{
  "name": "ai-text-processing-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.0",
    "typescript": "^5.6.2",
    "vite": "^5.4.6",
    "vitest": "^2.1.1"
  }
}
```

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
```

```json
// frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <title>AI 文本处理</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```typescript
// frontend/src/setupTests.ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: Write App shell**

```typescript
// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/theme.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```typescript
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";

function Placeholder({ label }: { label: string }) {
  return <div>{label}</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Placeholder label="function-list" />} />
        <Route path="/translate" element={<Placeholder label="translate-page" />} />
        <Route path="/summarize" element={<Placeholder label="summarize-page" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

```css
/* frontend/src/styles/theme.css */
:root {
  --bg: #ffffff;
  --fg: #1a1a1a;
  --accent: #2563eb;
  --border: #e2e2e2;
}

:root[data-theme="dark"] {
  --bg: #121212;
  --fg: #eaeaea;
  --accent: #60a5fa;
  --border: #333333;
}

body {
  background: var(--bg);
  color: var(--fg);
  font-family: system-ui, sans-serif;
  margin: 0;
}
```

- [ ] **Step 3: Verify it runs**

Run: `cd frontend && npm install && npm run dev -- --port 5173 &` then `curl -s http://localhost:5173 | grep -q root && echo OK`
Expected: `OK` printed; stop the dev server afterward.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/index.html frontend/src/main.tsx frontend/src/App.tsx frontend/src/styles/theme.css frontend/src/setupTests.ts
git commit -m "feat(frontend): scaffold Vite+React+TS app shell with routing"
```

---

### Task 21: API client + useSSETask hook

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useSSETask.ts`
- Test: `frontend/src/__tests__/useSSETask.test.ts`

**Interfaces:**
- Produces: `api/client.ts` exports `submitTask(functionType: string, text: string, maxPoints?: number, mode?: "auto"|"fast"|"think") -> Promise<{taskId: string}>`, `streamUrl(taskId: string) -> string`, `cancelTask(taskId: string) -> Promise<void>`.
- Produces: `hooks/useSSETask.ts` exports `useSSETask()` returning `{ output: string, status: "idle"|"running"|"done"|"error"|"cancelled", stage: string | null, progressMessage: string | null, start: (functionType: string, text: string, maxPoints?: number, mode?: string) => Promise<void>, cancel: () => void }`. Batches token updates via `requestAnimationFrame`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/__tests__/useSSETask.test.ts
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSSETask } from "../hooks/useSSETask";

class MockEventSource {
  static instances: MockEventSource[] = [];
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  emit(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ task_id: "t1", status: "pending" }) })
  );
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSSETask", () => {
  it("streams tokens into output and marks done", async () => {
    const { result } = renderHook(() => useSSETask());

    await act(async () => {
      await result.current.start("translate_en2zh", "Hello");
    });

    const source = MockEventSource.instances[0];
    act(() => source.emit({ type: "token", stage: "draft", delta: "你" }));
    act(() => source.emit({ type: "token", stage: "draft", delta: "好" }));
    act(() => source.emit({ type: "done", result: "你好" }));

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.output).toBe("你好");
  });

  it("surfaces progress messages", async () => {
    const { result } = renderHook(() => useSSETask());
    await act(async () => {
      await result.current.start("summarize", "长文本");
    });
    const source = MockEventSource.instances[0];
    act(() => source.emit({ type: "progress", stage: "chunk", message: "正在处理第 1/3 块" }));
    expect(result.current.progressMessage).toBe("正在处理第 1/3 块");
  });

  it("cancel closes the EventSource and sets status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "DELETE") return Promise.resolve({ ok: true });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ task_id: "t1", status: "pending" }) });
    }));
    const { result } = renderHook(() => useSSETask());
    await act(async () => {
      await result.current.start("translate_en2zh", "Hello");
    });
    const source = MockEventSource.instances[0];

    act(() => result.current.cancel());

    expect(source.closed).toBe(true);
    expect(result.current.status).toBe("cancelled");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/__tests__/useSSETask.test.ts`
Expected: FAIL with `Cannot find module '../hooks/useSSETask'`

- [ ] **Step 3: Write minimal implementation**

```typescript
// frontend/src/api/client.ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function submitTask(
  functionType: string,
  text: string,
  maxPoints?: number,
  mode: "auto" | "fast" | "think" = "auto"
): Promise<{ taskId: string }> {
  const resp = await fetch(`${API_BASE}/api/task`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ function_type: functionType, text, max_points: maxPoints ?? null, mode }),
  });
  if (!resp.ok) throw new Error(`submitTask failed: ${resp.status}`);
  const body = await resp.json();
  return { taskId: body.task_id };
}

export function streamUrl(taskId: string): string {
  return `${API_BASE}/api/task/${taskId}/stream`;
}

export async function cancelTask(taskId: string): Promise<void> {
  await fetch(`${API_BASE}/api/task/${taskId}`, { method: "DELETE" });
}
```

```typescript
// frontend/src/hooks/useSSETask.ts
import { useCallback, useRef, useState } from "react";
import { cancelTask, streamUrl, submitTask } from "../api/client";

type Status = "idle" | "running" | "done" | "error" | "cancelled";

export function useSSETask() {
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [stage, setStage] = useState<string | null>(null);
  const [progressMessage, setProgressMessage] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const bufferRef = useRef("");
  const pendingFlush = useRef(false);

  const flush = useCallback(() => {
    pendingFlush.current = false;
    setOutput((prev) => prev + bufferRef.current);
    bufferRef.current = "";
  }, []);

  const scheduleFlush = useCallback(() => {
    if (pendingFlush.current) return;
    pendingFlush.current = true;
    requestAnimationFrame(flush);
  }, [flush]);

  const start = useCallback(
    async (functionType: string, text: string, maxPoints?: number, mode?: "auto" | "fast" | "think") => {
      setOutput("");
      bufferRef.current = "";
      setStatus("running");
      setStage(null);
      setProgressMessage(null);

      const { taskId } = await submitTask(functionType, text, maxPoints, mode);
      const source = new EventSource(streamUrl(taskId));
      sourceRef.current = source;

      source.onmessage = (ev) => {
        const event = JSON.parse(ev.data);
        if (event.type === "token") {
          setStage(event.stage ?? null);
          bufferRef.current += event.delta ?? "";
          scheduleFlush();
        } else if (event.type === "progress") {
          setProgressMessage(event.message ?? null);
        } else if (event.type === "done") {
          flush();
          setStatus("done");
          source.close();
        } else if (event.type === "error") {
          flush();
          setStatus("error");
          source.close();
        } else if (event.type === "cancelled") {
          flush();
          setStatus("cancelled");
          source.close();
        }
      };
      source.onerror = () => {
        // connection-level failure; caller can fall back to useTaskPolling
      };

      (start as unknown as { _lastTaskId?: string })._lastTaskId = taskId;
    },
    [flush, scheduleFlush]
  );

  const cancel = useCallback(() => {
    const taskId = (start as unknown as { _lastTaskId?: string })._lastTaskId;
    sourceRef.current?.close();
    setStatus("cancelled");
    if (taskId) void cancelTask(taskId);
  }, [start]);

  return { output, status, stage, progressMessage, start, cancel };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/__tests__/useSSETask.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/hooks/useSSETask.ts frontend/src/__tests__/useSSETask.test.ts
git commit -m "feat(frontend): add API client and useSSETask streaming hook"
```

---

### Task 22: StreamingOutput component

**Files:**
- Create: `frontend/src/components/StreamingOutput.tsx`
- Test: `frontend/src/__tests__/StreamingOutput.test.tsx`

**Interfaces:**
- Consumes: nothing beyond props.
- Produces: `components/StreamingOutput.tsx` exports `StreamingOutput({ text, status, progressMessage }: { text: string; status: "idle"|"running"|"done"|"error"|"cancelled"; progressMessage?: string | null })` — renders `text` in a `<pre data-testid="streaming-output">`, shows `progressMessage` above it when present and status is `running`, and appends a blinking-cursor `<span data-testid="cursor">` while `status === "running"`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/__tests__/StreamingOutput.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StreamingOutput } from "../components/StreamingOutput";

describe("StreamingOutput", () => {
  it("renders the accumulated text", () => {
    render(<StreamingOutput text="你好" status="running" />);
    expect(screen.getByTestId("streaming-output")).toHaveTextContent("你好");
  });

  it("shows a cursor while running and hides it when done", () => {
    const { rerender } = render(<StreamingOutput text="你好" status="running" />);
    expect(screen.getByTestId("cursor")).toBeInTheDocument();

    rerender(<StreamingOutput text="你好" status="done" />);
    expect(screen.queryByTestId("cursor")).not.toBeInTheDocument();
  });

  it("shows progress message only while running", () => {
    render(<StreamingOutput text="" status="running" progressMessage="正在处理第 1/3 块" />);
    expect(screen.getByText("正在处理第 1/3 块")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/__tests__/StreamingOutput.test.tsx`
Expected: FAIL with `Cannot find module '../components/StreamingOutput'`

- [ ] **Step 3: Write minimal implementation**

```typescript
// frontend/src/components/StreamingOutput.tsx
type Status = "idle" | "running" | "done" | "error" | "cancelled";

interface Props {
  text: string;
  status: Status;
  progressMessage?: string | null;
}

export function StreamingOutput({ text, status, progressMessage }: Props) {
  return (
    <div>
      {status === "running" && progressMessage && <div>{progressMessage}</div>}
      <pre data-testid="streaming-output">
        {text}
        {status === "running" && <span data-testid="cursor">▍</span>}
      </pre>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/__tests__/StreamingOutput.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StreamingOutput.tsx frontend/src/__tests__/StreamingOutput.test.tsx
git commit -m "feat(frontend): add StreamingOutput typewriter component"
```

---

### Task 23: ModeToggle component

**Files:**
- Create: `frontend/src/components/ModeToggle.tsx`
- Test: `frontend/src/__tests__/ModeToggle.test.tsx`

**Interfaces:**
- Produces: `components/ModeToggle.tsx` exports `ModeToggle({ value, onChange }: { value: "auto"|"fast"|"think"; onChange: (v: "auto"|"fast"|"think") => void })` — three radio-style buttons (`data-testid="mode-auto"`, `mode-fast`, `mode-think`), clicking one calls `onChange` with that mode.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/__tests__/ModeToggle.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ModeToggle } from "../components/ModeToggle";

describe("ModeToggle", () => {
  it("marks the current value as pressed", () => {
    render(<ModeToggle value="think" onChange={() => {}} />);
    expect(screen.getByTestId("mode-think")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("mode-fast")).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with the clicked mode", async () => {
    const onChange = vi.fn();
    render(<ModeToggle value="auto" onChange={onChange} />);
    await userEvent.click(screen.getByTestId("mode-think"));
    expect(onChange).toHaveBeenCalledWith("think");
  });
});
```

- [ ] **Step 2: Add dependency + run test to verify it fails**

Run: `cd frontend && npm install --save-dev @testing-library/user-event@^14.5.2 && npm run test -- src/__tests__/ModeToggle.test.tsx`
Expected: FAIL with `Cannot find module '../components/ModeToggle'`

- [ ] **Step 3: Write minimal implementation**

```typescript
// frontend/src/components/ModeToggle.tsx
type Mode = "auto" | "fast" | "think";

interface Props {
  value: Mode;
  onChange: (mode: Mode) => void;
}

const OPTIONS: { mode: Mode; label: string }[] = [
  { mode: "auto", label: "自动" },
  { mode: "fast", label: "快速" },
  { mode: "think", label: "思考模式" },
];

export function ModeToggle({ value, onChange }: Props) {
  return (
    <div role="group" aria-label="模型模式">
      {OPTIONS.map(({ mode, label }) => (
        <button
          key={mode}
          type="button"
          data-testid={`mode-${mode}`}
          aria-pressed={value === mode}
          onClick={() => onChange(mode)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/__tests__/ModeToggle.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/ModeToggle.tsx frontend/src/__tests__/ModeToggle.test.tsx
git commit -m "feat(frontend): add ModeToggle component for fast/think override"
```

---

### Task 24: FunctionList page

**Files:**
- Create: `frontend/src/pages/FunctionList.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GET /api/functions` via `fetch`.
- Produces: `pages/FunctionList.tsx` exports `FunctionList()` — fetches functions on mount, renders a card per function linking to `/translate?direction=en2zh` / `/translate?direction=zh2en` / `/summarize`.

- [ ] **Step 1: Write minimal implementation**

```typescript
// frontend/src/pages/FunctionList.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface FunctionInfo {
  id: string;
  name: string;
  description: string;
}

const LINKS: Record<string, string> = {
  translate_en2zh: "/translate?direction=en2zh",
  translate_zh2en: "/translate?direction=zh2en",
  summarize: "/summarize",
};

export function FunctionList() {
  const [functions, setFunctions] = useState<FunctionInfo[]>([]);

  useEffect(() => {
    fetch("/api/functions")
      .then((r) => r.json())
      .then((body) => setFunctions(body.functions));
  }, []);

  return (
    <div>
      <h1>AI 文本处理</h1>
      <ul>
        {functions.map((f) => (
          <li key={f.id}>
            <Link to={LINKS[f.id] ?? "/"}>
              <strong>{f.name}</strong>
              <p>{f.description}</p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

```typescript
// frontend/src/App.tsx (replace Placeholder usage for "/")
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { FunctionList } from "./pages/FunctionList";

function Placeholder({ label }: { label: string }) {
  return <div>{label}</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<FunctionList />} />
        <Route path="/translate" element={<Placeholder label="translate-page" />} />
        <Route path="/summarize" element={<Placeholder label="summarize-page" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Manually verify**

Run: `cd frontend && npm run dev` then open `http://localhost:5173/` in a browser with the backend running on port 8000 (proxy configured in Task 32); confirm three function cards render and are clickable.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/FunctionList.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add function list landing page"
```

---

### Task 25: VirtualTextarea component

**Files:**
- Create: `frontend/src/components/VirtualTextarea.tsx`

**Interfaces:**
- Produces: `components/VirtualTextarea.tsx` exports `VirtualTextarea({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string })`. Below `VIRTUALIZE_LINE_THRESHOLD` (500) lines it renders a plain `<textarea>`. At or above the threshold it renders only a windowed slice of lines (fixed-height scroll container, ~40 visible lines rendered as a read-only preview) plus the same underlying `<textarea>` positioned to receive input — the textarea itself remains the single source of truth for editing so no virtualization bug can desync displayed vs. actual content; the windowed preview only reduces the DOM nodes painted for the "look how much text I typed" affordance.

- [ ] **Step 1: Write minimal implementation**

```typescript
// frontend/src/components/VirtualTextarea.tsx
import { useMemo } from "react";

const VIRTUALIZE_LINE_THRESHOLD = 500;
const VISIBLE_LINES = 40;

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function VirtualTextarea({ value, onChange, placeholder }: Props) {
  const lines = useMemo(() => value.split("\n"), [value]);
  const shouldVirtualize = lines.length >= VIRTUALIZE_LINE_THRESHOLD;

  return (
    <div>
      {shouldVirtualize && (
        <div
          data-testid="virtual-preview"
          style={{ maxHeight: `${VISIBLE_LINES * 1.4}em`, overflowY: "auto", opacity: 0.6 }}
        >
          {lines.slice(0, VISIBLE_LINES).join("\n")}
          {"\n… (" + (lines.length - VISIBLE_LINES) + " 行未显示，可直接在下方输入框继续编辑)"}
        </div>
      )}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={shouldVirtualize ? 6 : 16}
        style={{ width: "100%" }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Manually verify**

Run: `cd frontend && npm run dev`, paste >500 lines of text into a page using `VirtualTextarea` (wired in Task 27) and confirm the preview pane appears and typing remains responsive.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/VirtualTextarea.tsx
git commit -m "feat(frontend): add VirtualTextarea for large text input"
```

---

### Task 26: TranslatePage

**Files:**
- Create: `frontend/src/pages/TranslatePage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `hooks/useSSETask`, `components/{StreamingOutput,ModeToggle}`.
- Produces: `pages/TranslatePage.tsx` exports `TranslatePage()` — text input, direction select (en→zh / zh→en, seeded from `?direction=` query param), `ModeToggle`, "开始翻译"/"停止生成" buttons wired to `useSSETask().start`/`.cancel`, `StreamingOutput` for the result.

- [ ] **Step 1: Write minimal implementation**

```typescript
// frontend/src/pages/TranslatePage.tsx
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ModeToggle } from "../components/ModeToggle";
import { StreamingOutput } from "../components/StreamingOutput";
import { useSSETask } from "../hooks/useSSETask";

type Direction = "en2zh" | "zh2en";

export function TranslatePage() {
  const [searchParams] = useSearchParams();
  const [direction, setDirection] = useState<Direction>(
    (searchParams.get("direction") as Direction) ?? "en2zh"
  );
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"auto" | "fast" | "think">("auto");
  const { output, status, progressMessage, start, cancel } = useSSETask();

  const functionType = direction === "en2zh" ? "translate_en2zh" : "translate_zh2en";

  return (
    <div>
      <h1>翻译</h1>
      <select value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
        <option value="en2zh">英译中</option>
        <option value="zh2en">中译英</option>
      </select>
      <ModeToggle value={mode} onChange={setMode} />
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} style={{ width: "100%" }} />
      <div>
        <button onClick={() => start(functionType, text, undefined, mode)} disabled={status === "running"}>
          开始翻译
        </button>
        <button onClick={cancel} disabled={status !== "running"}>
          停止生成
        </button>
      </div>
      <StreamingOutput text={output} status={status} progressMessage={progressMessage} />
    </div>
  );
}
```

```typescript
// frontend/src/App.tsx (replace translate Placeholder route)
import { TranslatePage } from "./pages/TranslatePage";
// ...
<Route path="/translate" element={<TranslatePage />} />
```

- [ ] **Step 2: Manually verify**

Run: `cd frontend && npm run dev`, navigate to `/translate?direction=en2zh`, type text, click "开始翻译" against a running backend, confirm streamed output appears and "停止生成" cancels mid-stream.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/TranslatePage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add TranslatePage with streaming and cancel"
```

---

### Task 27: SummarizePage

**Files:**
- Create: `frontend/src/pages/SummarizePage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `hooks/useSSETask`, `components/{StreamingOutput,ModeToggle,VirtualTextarea}`.
- Produces: `pages/SummarizePage.tsx` exports `SummarizePage()` — `VirtualTextarea` for long input, a `max_points` number input (1–10), `ModeToggle`, start/stop buttons, `StreamingOutput` showing chunk progress + final summary.

- [ ] **Step 1: Write minimal implementation**

```typescript
// frontend/src/pages/SummarizePage.tsx
import { useState } from "react";
import { ModeToggle } from "../components/ModeToggle";
import { StreamingOutput } from "../components/StreamingOutput";
import { VirtualTextarea } from "../components/VirtualTextarea";
import { useSSETask } from "../hooks/useSSETask";

export function SummarizePage() {
  const [text, setText] = useState("");
  const [maxPoints, setMaxPoints] = useState(3);
  const [mode, setMode] = useState<"auto" | "fast" | "think">("auto");
  const { output, status, progressMessage, start, cancel } = useSSETask();

  return (
    <div>
      <h1>文本总结</h1>
      <VirtualTextarea value={text} onChange={setText} placeholder="粘贴长文本..." />
      <label>
        要点数
        <input
          type="number"
          min={1}
          max={10}
          value={maxPoints}
          onChange={(e) => setMaxPoints(Number(e.target.value))}
        />
      </label>
      <ModeToggle value={mode} onChange={setMode} />
      <div>
        <button onClick={() => start("summarize", text, maxPoints, mode)} disabled={status === "running"}>
          开始总结
        </button>
        <button onClick={cancel} disabled={status !== "running"}>
          停止生成
        </button>
      </div>
      <StreamingOutput text={output} status={status} progressMessage={progressMessage} />
    </div>
  );
}
```

```typescript
// frontend/src/App.tsx (replace summarize Placeholder route)
import { SummarizePage } from "./pages/SummarizePage";
// ...
<Route path="/summarize" element={<SummarizePage />} />
```

After this task, `Placeholder` is unused in `App.tsx` — remove its definition and import.

- [ ] **Step 2: Manually verify**

Run: `cd frontend && npm run dev`, navigate to `/summarize`, paste a long article, submit, confirm "正在处理第 x/y 块" progress messages appear before the final summary streams in.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SummarizePage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add SummarizePage with virtual textarea and chunk progress"
```

---

### Task 28: useTaskPolling fallback hook

**Files:**
- Create: `frontend/src/hooks/useTaskPolling.ts`
- Modify: `frontend/src/hooks/useSSETask.ts`

**Interfaces:**
- Produces: `hooks/useTaskPolling.ts` exports `pollTaskUntilDone(taskId: string, onUpdate: (status: string, result?: string) => void, intervalMs = 1000) -> () => void` (returns a stop function). `useSSETask` calls this from `source.onerror` after 3 consecutive `onerror` events on the same connection, instead of leaving the UI stuck.

- [ ] **Step 1: Write minimal implementation**

```typescript
// frontend/src/hooks/useTaskPolling.ts
async function fetchStatus(taskId: string): Promise<{ status: string; result?: string }> {
  const resp = await fetch(`/api/task/${taskId}`);
  return resp.json();
}

export function pollTaskUntilDone(
  taskId: string,
  onUpdate: (status: string, result?: string) => void,
  intervalMs = 1000
): () => void {
  let stopped = false;

  const tick = async () => {
    if (stopped) return;
    const { status, result } = await fetchStatus(taskId);
    onUpdate(status, result);
    if (!stopped && !["done", "failed", "cancelled"].includes(status)) {
      setTimeout(tick, intervalMs);
    }
  };
  tick();

  return () => {
    stopped = true;
  };
}
```

```typescript
// frontend/src/hooks/useSSETask.ts (modify onerror handler)
      let errorCount = 0;
      source.onerror = () => {
        errorCount += 1;
        if (errorCount >= 3) {
          source.close();
          pollTaskUntilDone(taskId, (polledStatus, result) => {
            if (polledStatus === "done") {
              setOutput(result ?? "");
              setStatus("done");
            } else if (polledStatus === "failed") {
              setStatus("error");
            } else if (polledStatus === "cancelled") {
              setStatus("cancelled");
            }
          });
        }
      };
```

Add the import `import { pollTaskUntilDone } from "./useTaskPolling";` at the top of `useSSETask.ts`.

- [ ] **Step 2: Manually verify**

Run: `cd frontend && npm run test` (existing `useSSETask` tests must still pass since polling only triggers after 3 `onerror` events, which the mocked `EventSource` never fires).
Expected: PASS, no regressions.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useTaskPolling.ts frontend/src/hooks/useSSETask.ts
git commit -m "feat(frontend): add polling fallback when SSE repeatedly errors"
```

---

### Task 29: ThemeToggle + responsive layout

**Files:**
- Create: `frontend/src/components/ThemeToggle.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles/theme.css`

**Interfaces:**
- Produces: `components/ThemeToggle.tsx` exports `ThemeToggle()` — reads/writes `localStorage["theme"]`, falls back to `prefers-color-scheme`, toggles `document.documentElement.dataset.theme`.

- [ ] **Step 1: Write minimal implementation**

```typescript
// frontend/src/components/ThemeToggle.tsx
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  return (
    <button onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}>
      {theme === "dark" ? "🌙 深色" : "☀️ 浅色"}
    </button>
  );
}
```

```typescript
// frontend/src/App.tsx (add ThemeToggle to the shell)
import { ThemeToggle } from "./components/ThemeToggle";
// inside BrowserRouter, above Routes:
<ThemeToggle />
```

```css
/* frontend/src/styles/theme.css (append) */
@media (max-width: 640px) {
  body {
    font-size: 15px;
  }
  textarea {
    font-size: 16px; /* avoid iOS zoom-on-focus */
  }
}

.page-layout {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

@media (min-width: 900px) {
  .page-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
```

- [ ] **Step 2: Manually verify**

Run: `cd frontend && npm run dev`, click the theme toggle and confirm colors flip and persist across reload; resize the window below 640px and confirm layout stacks vertically.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ThemeToggle.tsx frontend/src/App.tsx frontend/src/styles/theme.css
git commit -m "feat(frontend): add dark/light theme toggle and responsive layout"
```

---

## Phase 10: Agent Discovery

### Task 30: skill.md

**Files:**
- Create: `skill.md`

**Interfaces:**
- Produces: a skill definition describing the `ai-app` CLI so Agents (ClaudeCode/OpenClaw) can discover and invoke it.

- [ ] **Step 1: Write skill.md**

```markdown
# ai-app CLI skill

## What this does
Calls a running AI text-processing backend to translate text between English
and Chinese, or to summarize long text into a bounded number of points.
Streams output token-by-token to stdout as the model generates it.

## When to use this
- User asks to translate text between English and Chinese.
- User asks to summarize or condense a long piece of text.

## Prerequisites
The backend (`backend/main.py`) and worker (`backend/worker/settings.py`) must
be running, e.g. via `docker compose up` from the repo root, or with
`--host` pointed at wherever they're running (default `http://localhost:8000`).

## Commands

Translate English to Chinese:
```bash
ai-app translate --text "Hello, world" --from en --to zh
```

Translate Chinese to English:
```bash
ai-app translate --text "你好，世界" --from zh --to en
```

Summarize long text into at most N points:
```bash
ai-app summarize --text "<long text>" --max-points 3
```

Point at a non-default backend:
```bash
ai-app translate --text "Hello" --from en --to zh --host http://localhost:8000
```

## Output
Streams the result to stdout as plain text; the command exits 0 on success.
Press Ctrl+C to cancel an in-flight request — the CLI notifies the backend
so the task queue stops processing it.

## Installation
```bash
cd cli && pip install -e .
```
```

- [ ] **Step 2: Commit**

```bash
git add skill.md
git commit -m "docs: add skill.md for Agent discovery of the ai-app CLI"
```

- [ ] **Step 3: Manual verification (user-performed, not scriptable)**

Load this repository into ClaudeCode or OpenClaw, ask it to translate or summarize some text, and confirm it discovers `skill.md` and invokes `ai-app`. Save a screenshot to `docs/skill-invocation-screenshot.png` — this step cannot be automated by an agentic worker and must be done by the project owner.

---

## Phase 11: Docker

### Task 31: Dockerfiles + docker-compose.yml

**Files:**
- Create: `Dockerfile.backend`
- Create: `Dockerfile.worker`
- Create: `Dockerfile.frontend`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Interfaces:**
- Produces: `docker compose up --build` starting `redis`, `backend` (uvicorn on 8000), `worker` (arq), `frontend` (nginx on 80), backend+worker sharing a `sqlite-data` volume.

- [ ] **Step 1: Write Dockerfiles**

```dockerfile
# Dockerfile.backend
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# Dockerfile.worker
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
CMD ["arq", "worker.settings.WorkerSettings"]
```

```dockerfile
# Dockerfile.frontend
FROM node:20-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

- [ ] **Step 2: Write docker-compose.yml**

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    env_file: .env
    environment:
      - REDIS_URL=redis://redis:6379/0
      - SQLITE_PATH=/data/app.db
    volumes:
      - sqlite-data:/data
    ports:
      - "8000:8000"
    depends_on:
      - redis

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    env_file: .env
    environment:
      - REDIS_URL=redis://redis:6379/0
      - SQLITE_PATH=/data/app.db
    volumes:
      - sqlite-data:/data
    depends_on:
      - redis

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  sqlite-data:
```

```bash
# .env.example
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=
LLM_MODEL_FAST=deepseek-chat
LLM_MODEL_THINK=deepseek-reasoner
TASK_TIMEOUT_SECONDS=60
```

- [ ] **Step 3: Verify it builds and starts**

Run: `cp .env.example .env && docker compose up --build -d`
Expected: all four containers report `running`/`healthy`; `curl -s http://localhost:8000/health` returns `{"status":"ok"}`; `curl -s http://localhost/` returns the frontend HTML.

Run: `docker compose down`

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.backend Dockerfile.worker Dockerfile.frontend docker-compose.yml .env.example
git commit -m "feat(deploy): add Docker Compose setup for frontend/backend/worker/redis"
```

---

## Phase 12: SDD Docs and README

### Task 32: agent.md and spec/

**Files:**
- Create: `agent.md`
- Create: `spec/requirements.md`
- Create: `spec/api-design.md`
- Create: `spec/ui-prototype.md`

**Interfaces:**
- Produces: SDD documentation deliverables required by the exam's bonus-point section.

- [ ] **Step 1: Write agent.md**

```markdown
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
```

- [ ] **Step 2: Write spec/requirements.md**

```markdown
# 需求拆分

## 基础要求
- [ ] 功能列表页（GET /api/functions）
- [ ] 翻译页（中译英/英译中，流式结果展示）
- [ ] 总结页（长文本输入、字数/要点数控制，流式结果展示）
- [ ] SSE 流式推送 + 打字机效果
- [ ] 取消进行中的任务（前端发取消请求，后端终止执行）
- [ ] POST /api/task 提交任务
- [ ] DELETE /api/task/{taskId} 取消任务
- [ ] CLI 工具（translate/summarize，直接调用后端服务）
- [ ] skill.md + Agent 调用截图

## 加分项
- [ ] agent.md + spec/ 目录（本文档所在）
- [ ] 虚拟滚动优化大文本输入
- [ ] 流式渲染性能优化（requestAnimationFrame 批量更新）
- [ ] 深色/浅色主题切换
- [ ] 响应式布局
- [ ] 请求参数校验（Pydantic）+ 统一错误处理 + 日志追踪（trace_id）+ 任务超时控制
- [ ] 前端轮询任务状态（SSE 失败降级路径）
- [ ] Redis + arq 异步任务队列
- [ ] 数据闭环：调用记录持久化（SQLite）+ 查询页（GET /api/records）
- [ ] Docker：Dockerfile + docker-compose.yml 一键启动
```

- [ ] **Step 3: Write spec/api-design.md**

```markdown
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
```

- [ ] **Step 4: Write spec/ui-prototype.md**

```markdown
# 页面原型

## 列表页 (`/`)
三张功能卡片（英译中、中译英、文本总结），点击进入对应页面。右上角深浅
主题切换按钮。

## 翻译页 (`/translate?direction=en2zh|zh2en`)
- 方向选择下拉框（默认由 query param 决定）
- 思考模式开关（自动/快速/思考）
- 文本输入框
- "开始翻译" / "停止生成" 按钮
- 结果区：逐字流式渲染，思考模式下会先看到草稿、再看到"精修中..."过渡态、
  最后是校对后的最终结果

## 总结页 (`/summarize`)
- 大文本输入框（超过 500 行启用虚拟滚动预览）
- 要点数输入（1-10）
- 思考模式开关
- "开始总结" / "停止生成" 按钮
- 结果区：长文本会先看到"正在处理第 x/y 块"的分块进度，再看到最终摘要
  流式输出
```

- [ ] **Step 5: Commit**

```bash
git add agent.md spec/
git commit -m "docs: add agent.md and spec/ SDD documentation"
```

---

### Task 33: README.md

**Files:**
- Create: `README.md`

**Interfaces:**
- Produces: the top-level project README covering intro, tech stack, local run instructions (with and without Docker), and API docs.

- [ ] **Step 1: Write README.md**

```markdown
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
# 1. 启动 Redis
docker run -p 6379:6379 redis:7-alpine

# 2. 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # 填入 LLM_API_KEY
uvicorn main:app --reload --port 8000

# 3. worker（新终端）
cd backend && source .venv/bin/activate
arq worker.settings.WorkerSettings

# 4. 前端（新终端）
cd frontend
npm install
npm run dev

# 5. CLI（可选，新终端）
cd cli
pip install -e .
ai-app translate --text "Hello" --from en --to zh
```

## 运行测试

```bash
cd backend && python -m pytest
cd cli && python -m pytest
cd frontend && npm run test
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup, run, and API instructions"
```

---

## Self-Review Notes

- **Spec coverage:** every spec section (接口设计, 大模型调用层, 核心任务执行架构, 后端模块, 前端设计, CLI 与 Agent 工具链, 测试策略, Docker, SDD 文档结构, 交付物清单) maps to at least one task above (Tasks 12–17 / 7 / 9–11 / 1–19 / 20–29 / 18–19+30 / all backend tasks' TDD steps + Task 21's frontend tests / 31 / 32 / entire deliverables list across 30–33).
- **Type consistency verified:** `FunctionType`, `TaskStatus`, `ModelMode`, `TaskEvent`, `resolve_mode` defined once in Task 4 and reused verbatim (same names/fields) through Tasks 5, 6, 9, 10, 11, 14–17. `stream_completion(messages, mode)` signature from Task 7 matches its call sites in Tasks 9 and 10. `execute_task(ctx, task_id)` signature from Task 11 matches the `arq_pool.enqueue_job("execute_task", task_id)` call in Task 14.
- **No placeholders:** every step above contains complete, runnable code — no `TBD`/`TODO`/"add validation" style stubs. The one genuinely non-automatable step (Agent invocation screenshot, Task 30 Step 3) is explicitly called out as user-performed rather than left vague.
