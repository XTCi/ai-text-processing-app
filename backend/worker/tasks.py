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
