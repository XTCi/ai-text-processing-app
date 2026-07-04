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


@pytest.mark.asyncio
async def test_stream_replays_terminal_state_for_already_failed_task(redis):
    task_id = await task_service.create_task(redis, "translate_en2zh", "Hello", None, "auto")
    await task_service.set_status(redis, task_id, TaskStatus.FAILED, error="boom", duration_ms=50)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", f"/api/task/{task_id}/stream") as response:
            events = await asyncio.wait_for(_read_sse_events(response, 1), timeout=2)

    assert events[0]["type"] == "error"
    assert events[0]["message"] == "boom"
