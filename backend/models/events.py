from typing import Literal

from pydantic import BaseModel


class TaskEvent(BaseModel):
    type: Literal["token", "progress", "done", "error", "cancelled"]
    stage: str | None = None
    delta: str = ""
    message: str | None = None
    chunk_index: int | None = None
    chunk_total: int | None = None
    result: str | None = None
    duration_ms: int | None = None
