from typing import AsyncIterator

from models.events import TaskEvent
from models.task import ModelMode
from services.llm_client import stream_completion
from worker.chunking import chunk_text


def _map_messages(chunk: str) -> list[dict]:
    return [
        {"role": "system", "content": "请用简洁的中文概括以下文本片段的要点，只输出概括内容。"},
        {"role": "user", "content": chunk},
    ]


def _reduce_messages(combined: str, max_points: int) -> list[dict]:
    return [
        {
            "role": "system",
            "content": f"请将以下内容整合为不超过 {max_points} 个要点的总结，用中文分点输出。",
        },
        {"role": "user", "content": combined},
    ]


async def run_summarize(text: str, max_points: int, mode: ModelMode) -> AsyncIterator[TaskEvent]:
    chunks = chunk_text(text)

    if len(chunks) == 1:
        combined = chunks[0]
    else:
        chunk_summaries = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            yield TaskEvent(
                type="progress",
                stage="chunk",
                message=f"正在处理第 {index}/{total} 块",
                chunk_index=index,
                chunk_total=total,
            )
            summary = ""
            async for delta in stream_completion(_map_messages(chunk), ModelMode.FAST):
                summary += delta
            chunk_summaries.append(summary)
        combined = "\n".join(chunk_summaries)

    final_text = ""
    async for delta in stream_completion(_reduce_messages(combined, max_points), mode):
        final_text += delta
        yield TaskEvent(type="token", stage="reduce", delta=delta)

    yield TaskEvent(type="done", result=final_text)
