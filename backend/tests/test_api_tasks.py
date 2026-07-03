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
    # Restore app.state so later tests (e.g. test_deps.py) that rely on
    # main.on_startup creating a fresh real redis/arq pool aren't left
    # with this test's fakes (module-level `app` is shared across the suite).
    del app.state.redis
    del app.state.arq_pool


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
