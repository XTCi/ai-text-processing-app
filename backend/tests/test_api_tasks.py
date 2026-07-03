# backend/tests/test_api_tasks.py
from unittest.mock import AsyncMock

import anyio
import pytest
from fakeredis import FakeAsyncRedis
from fastapi.testclient import TestClient

from core.deps import get_arq_pool, get_redis
from main import app


@pytest.fixture
def client():
    fake_redis = FakeAsyncRedis()
    fake_arq_pool = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_arq_pool] = lambda: fake_arq_pool
    c = TestClient(app)
    # Never call `with TestClient(app) as c:` here: entering as a context
    # manager fires the real ASGI lifespan (main.on_startup), which eagerly
    # opens a real Redis connection (arq's create_pool awaits pool.ping())
    # -- exactly what these tests must not require. Instead we hand the
    # client a manually-managed, persistent blocking portal so repeated
    # calls in one test share a single event loop (fakeredis's internal
    # asyncio.Queue binds to whichever loop first touches it and raises
    # "bound to a different event loop" if a later call runs on a new one).
    with anyio.from_thread.start_blocking_portal(**c.async_backend) as portal:
        c.portal = portal
        yield c, fake_arq_pool
    app.dependency_overrides.clear()


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
