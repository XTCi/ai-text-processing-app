import asyncio
from typing import AsyncIterator

from openai import AsyncOpenAI

from core.config import settings
from models.task import ModelMode

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    return _client


async def _mock_stream(messages: list[dict], mode: ModelMode) -> AsyncIterator[str]:
    """No LLM_API_KEY configured: simulate a streaming response locally so the
    full request -> queue -> SSE pipeline still runs end-to-end. The real call
    path above (AsyncOpenAI against an OpenAI-compatible endpoint) is what
    activates once a key is supplied in .env — this is pseudocode standing in
    for it, not a separate code path callers need to know about."""
    last_user_content = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    prefix = "[mock-think] " if mode == ModelMode.THINK else "[mock] "
    simulated = f"{prefix}模拟回复：{last_user_content[:50]}"
    for ch in simulated:
        await asyncio.sleep(0)
        yield ch


async def stream_completion(messages: list[dict], mode: ModelMode) -> AsyncIterator[str]:
    if not settings.llm_api_key:
        async for delta in _mock_stream(messages, mode):
            yield delta
        return

    model = settings.llm_model_think if mode == ModelMode.THINK else settings.llm_model_fast
    client = _get_client()
    stream = await client.chat.completions.create(model=model, messages=messages, stream=True)
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
