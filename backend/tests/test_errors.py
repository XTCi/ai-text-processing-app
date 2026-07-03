from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.errors import TaskNotFoundError, register_exception_handlers


def build_app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise TaskNotFoundError("task xyz not found")

    return app


def test_app_error_returns_structured_json():
    client = TestClient(build_app())
    resp = client.get("/boom")
    assert resp.status_code == 404
    assert resp.json() == {"error": "TaskNotFoundError", "message": "task xyz not found"}
