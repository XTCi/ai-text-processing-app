import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.deps import get_arq_pool, get_redis
from core.errors import TaskNotFoundError
from models.events import TaskEvent
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


@router.delete("/api/task/{task_id}")
async def cancel_task(task_id: str, redis=Depends(get_redis)) -> dict:
    cancelled = await task_service.request_cancel(redis, task_id)
    if not cancelled:
        raise TaskNotFoundError(f"task {task_id} not found")
    return {"cancelled": True}


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
