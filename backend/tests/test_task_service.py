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
