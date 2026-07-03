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
