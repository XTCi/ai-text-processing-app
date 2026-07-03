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
