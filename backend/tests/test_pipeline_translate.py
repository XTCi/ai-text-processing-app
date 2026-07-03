import pytest

from models.task import FunctionType, ModelMode
from worker.pipelines import translate as translate_pipeline


async def _fake_stream_factory(responses):
    calls = []

    async def fake_stream_completion(messages, mode):
        calls.append((messages, mode))
        for ch in responses[len(calls) - 1]:
            yield ch

    return fake_stream_completion, calls


@pytest.mark.asyncio
async def test_fast_mode_only_drafts(monkeypatch):
    fake, calls = await _fake_stream_factory(["你好"])
    monkeypatch.setattr(translate_pipeline, "stream_completion", fake)

    events = [e async for e in translate_pipeline.run_translate("Hello", FunctionType.TRANSLATE_EN2ZH, ModelMode.FAST)]

    stages = [e.stage for e in events if e.type == "token"]
    assert stages == ["draft", "draft"]
    assert events[-1].type == "done"
    assert events[-1].result == "你好"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_think_mode_runs_draft_then_review(monkeypatch):
    fake, calls = await _fake_stream_factory(["你好", "你好呀"])
    monkeypatch.setattr(translate_pipeline, "stream_completion", fake)

    events = [e async for e in translate_pipeline.run_translate("Hello", FunctionType.TRANSLATE_EN2ZH, ModelMode.THINK)]

    types_stages = [(e.type, e.stage) for e in events]
    assert ("progress", "review") in types_stages
    review_tokens = [e for e in events if e.type == "token" and e.stage == "review"]
    assert "".join(e.delta for e in review_tokens) == "你好呀"
    assert events[-1].result == "你好呀"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_think_mode_review_can_keep_draft_unchanged(monkeypatch):
    fake, calls = await _fake_stream_factory(["OK", "OK"])
    monkeypatch.setattr(translate_pipeline, "stream_completion", fake)

    events = [e async for e in translate_pipeline.run_translate("hi", FunctionType.TRANSLATE_EN2ZH, ModelMode.THINK)]

    assert events[-1].result == "OK"
