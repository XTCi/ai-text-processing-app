from fastapi.testclient import TestClient

from main import app


def test_list_functions():
    client = TestClient(app)
    resp = client.get("/api/functions")
    assert resp.status_code == 200
    body = resp.json()
    ids = {f["id"] for f in body["functions"]}
    assert ids == {"translate_en2zh", "translate_zh2en", "summarize"}
    for f in body["functions"]:
        assert f["name"]
        assert f["description"]
