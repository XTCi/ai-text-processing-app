import pytest

from models.task import ModelMode
from worker.pipelines import summarize as summarize_pipeline


@pytest.mark.asyncio
async def test_short_text_skips_map_phase(monkeypatch):
    calls = []

    async def fake_stream_completion(messages, mode):
        calls.append((messages, mode))
        for ch in "摘要结果":
            yield ch

    monkeypatch.setattr(summarize_pipeline, "stream_completion", fake_stream_completion)
    monkeypatch.setattr(summarize_pipeline, "chunk_text", lambda text, **kw: [text])

    events = [e async for e in summarize_pipeline.run_summarize("短文本", 3, ModelMode.THINK)]

    assert len(calls) == 1  # only the reduce call, no map calls
    assert calls[0][1] == ModelMode.THINK
    progress_events = [e for e in events if e.type == "progress"]
    assert progress_events == []
    assert events[-1].type == "done"
    assert events[-1].result == "摘要结果"


@pytest.mark.asyncio
async def test_long_text_maps_each_chunk_then_reduces(monkeypatch):
    calls = []

    async def fake_stream_completion(messages, mode):
        calls.append((messages, mode))
        text = "chunk-summary" if len(calls) <= 3 else "final-summary"
        for ch in text:
            yield ch

    monkeypatch.setattr(summarize_pipeline, "stream_completion", fake_stream_completion)
    monkeypatch.setattr(summarize_pipeline, "chunk_text", lambda text, **kw: ["c1", "c2", "c3"])

    events = [e async for e in summarize_pipeline.run_summarize("长文本" * 100, 3, ModelMode.FAST)]

    progress_events = [e for e in events if e.type == "progress"]
    assert [e.chunk_index for e in progress_events] == [1, 2, 3]
    assert [e.chunk_total for e in progress_events] == [3, 3, 3]
    assert len(calls) == 4  # 3 map calls + 1 reduce call
    assert all(mode == ModelMode.FAST for _, mode in calls[:3])  # map always fast
    assert calls[3][1] == ModelMode.FAST  # reduce follows requested mode
    assert events[-1].result == "final-summary"


@pytest.mark.asyncio
async def test_reduce_prompt_includes_max_points(monkeypatch):
    captured = {}

    async def fake_stream_completion(messages, mode):
        captured["messages"] = messages
        yield "ok"

    monkeypatch.setattr(summarize_pipeline, "stream_completion", fake_stream_completion)
    monkeypatch.setattr(summarize_pipeline, "chunk_text", lambda text, **kw: [text])

    [e async for e in summarize_pipeline.run_summarize("text", 5, ModelMode.FAST)]

    joined = " ".join(m["content"] for m in captured["messages"])
    assert "5" in joined
