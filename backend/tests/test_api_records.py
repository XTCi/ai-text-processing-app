from fastapi.testclient import TestClient

from main import app
from models.task import FunctionType, ModelMode, TaskStatus
from services.record_store import init_db, save_record


def test_list_records(tmp_path):
    db_path = str(tmp_path / "app.db")
    app.state.sqlite_path = db_path

    import asyncio

    async def seed():
        await init_db(db_path)
        await save_record(
            db_path,
            task_id="t1",
            function_type=FunctionType.SUMMARIZE,
            input_text="in",
            output_text="out",
            model_mode=ModelMode.THINK,
            status=TaskStatus.DONE,
            duration_ms=100,
        )

    asyncio.run(seed())

    client = TestClient(app)
    resp = client.get("/api/records")
    assert resp.status_code == 200
    records = resp.json()["records"]
    assert len(records) == 1
    assert records[0]["task_id"] == "t1"
