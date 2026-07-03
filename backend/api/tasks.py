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


@router.delete("/api/task/{task_id}")
async def cancel_task(task_id: str, redis=Depends(get_redis)) -> dict:
    cancelled = await task_service.request_cancel(redis, task_id)
    if not cancelled:
        raise TaskNotFoundError(f"task {task_id} not found")
    return {"cancelled": True}
