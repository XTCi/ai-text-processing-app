from types import SimpleNamespace

import pytest

from core.config import settings
from models.task import ModelMode
from services import llm_client


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeStream:
    def __init__(self, pieces):
        self._pieces = pieces

    def __aiter__(self):
        self._iter = iter(self._pieces)
        return self

    async def __anext__(self):
        try:
            return _FakeChunk(next(self._iter))
        except StopIteration:
            raise StopAsyncIteration


class _FakeCompletions:
    def __init__(self, pieces):
        self._pieces = pieces
        self.last_call = None

    async def create(self, **kwargs):
        self.last_call = kwargs
        return _FakeStream(self._pieces)


class _FakeChat:
    def __init__(self, pieces):
        self.completions = _FakeCompletions(pieces)


class _FakeAsyncOpenAI:
    def __init__(self, pieces):
        self.chat = _FakeChat(pieces)


@pytest.mark.asyncio
async def test_stream_completion_uses_real_client_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    fake_client = _FakeAsyncOpenAI(["你", "好"])
    monkeypatch.setattr(llm_client, "_get_client", lambda: fake_client)

    deltas = [d async for d in llm_client.stream_completion([{"role": "user", "content": "hi"}], ModelMode.FAST)]

    assert deltas == ["你", "好"]
    assert fake_client.chat.completions.last_call["model"] == settings.llm_model_fast
    assert fake_client.chat.completions.last_call["stream"] is True


@pytest.mark.asyncio
async def test_stream_completion_picks_think_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    fake_client = _FakeAsyncOpenAI(["ok"])
    monkeypatch.setattr(llm_client, "_get_client", lambda: fake_client)

    [d async for d in llm_client.stream_completion([{"role": "user", "content": "hi"}], ModelMode.THINK)]

    assert fake_client.chat.completions.last_call["model"] == settings.llm_model_think


@pytest.mark.asyncio
async def test_stream_completion_falls_back_to_mock_without_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")

    deltas = [d async for d in llm_client.stream_completion([{"role": "user", "content": "hi"}], ModelMode.FAST)]

    assert len(deltas) > 0
    assert "".join(deltas)  # non-empty simulated response
