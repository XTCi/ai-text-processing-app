from fastapi.testclient import TestClient

from main import app


def test_startup_initializes_redis_and_arq_pool():
    with TestClient(app) as client:
        assert client.app.state.redis is not None
        assert client.app.state.arq_pool is not None
