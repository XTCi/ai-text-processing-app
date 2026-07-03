from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.logging import TraceIdMiddleware, trace_id_var


def build_app():
    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)

    @app.get("/whoami")
    async def whoami():
        return {"trace_id": trace_id_var.get()}

    return app


def test_middleware_sets_trace_id_and_header():
    client = TestClient(build_app())
    resp = client.get("/whoami")
    assert resp.status_code == 200
    header_trace = resp.headers["x-trace-id"]
    assert resp.json()["trace_id"] == header_trace
    assert len(header_trace) == 12


def test_middleware_generates_unique_trace_ids():
    client = TestClient(build_app())
    first = client.get("/whoami").headers["x-trace-id"]
    second = client.get("/whoami").headers["x-trace-id"]
    assert first != second
