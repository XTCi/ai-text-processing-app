# cli/tests/test_client.py
import json

import httpx
import pytest

from ai_app.client import cancel_task, stream_task, submit_task


def test_submit_task_posts_and_returns_task_id():
    def handler(request):
        assert request.url.path == "/api/task"
        body = json.loads(request.content)
        assert body == {"function_type": "translate_en2zh", "text": "Hello", "max_points": None, "mode": "auto"}
        return httpx.Response(200, json={"task_id": "abc123", "status": "pending"})

    transport = httpx.MockTransport(handler)
    task_id = submit_task("http://test", "translate_en2zh", "Hello", None, transport=transport)
    assert task_id == "abc123"


def test_stream_task_yields_parsed_events():
    def handler(request):
        assert request.url.path == "/api/task/abc123/stream"
        body = (
            b'data: {"type": "token", "delta": "\xe4\xbd\xa0"}\n\n'
            b'data: {"type": "done", "result": "\xe4\xbd\xa0"}\n\n'
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    events = list(stream_task("http://test", "abc123", transport=transport))
    assert events[0]["type"] == "token"
    assert events[1]["type"] == "done"


def test_stream_task_raises_on_http_error():
    def handler(request):
        return httpx.Response(404, json={"detail": "task not found"})

    transport = httpx.MockTransport(handler)
    with pytest.raises(httpx.HTTPStatusError):
        list(stream_task("http://test", "missing-task", transport=transport))


def test_cancel_task_sends_delete():
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"cancelled": True})

    transport = httpx.MockTransport(handler)
    cancel_task("http://test", "abc123", transport=transport)
    assert calls == ["DELETE"]
