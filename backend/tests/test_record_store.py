# backend/tests/test_record_store.py
import pytest

from models.task import FunctionType, ModelMode, TaskStatus
from services.record_store import init_db, list_records, save_record


@pytest.mark.asyncio
async def test_save_and_list_records(tmp_path):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    await save_record(
        db_path,
        task_id="t1",
        function_type=FunctionType.SUMMARIZE,
        input_text="长文本",
        output_text="摘要",
        model_mode=ModelMode.THINK,
        status=TaskStatus.DONE,
        duration_ms=1234,
    )
    await save_record(
        db_path,
        task_id="t2",
        function_type=FunctionType.TRANSLATE_EN2ZH,
        input_text="Hello",
        output_text="你好",
        model_mode=ModelMode.FAST,
        status=TaskStatus.DONE,
        duration_ms=200,
    )

    records = await list_records(db_path, limit=10, offset=0)

    assert len(records) == 2
    assert records[0]["task_id"] == "t2"  # newest first
    assert records[1]["task_id"] == "t1"
    assert records[0]["duration_ms"] == 200
    assert records[1]["function_type"] == "summarize"
