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
