from fastapi.testclient import TestClient

from main import app


def test_startup_initializes_redis_and_arq_pool():
    with TestClient(app) as client:
        assert client.app.state.redis is not None
        assert client.app.state.arq_pool is not None
        # The redis client's event loop lives in TestClient's background
        # portal thread, so the connectivity check must run there too
        # (awaiting it directly from this thread would attach the
        # connection's futures to the wrong event loop).
        assert client.portal.call(client.app.state.redis.ping) is True
