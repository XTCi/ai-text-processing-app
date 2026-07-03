import os

import aiosqlite

from models.record import CREATE_TABLE_SQL
from models.task import FunctionType, ModelMode, TaskStatus


async def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


async def save_record(
    db_path: str,
    *,
    task_id: str,
    function_type: FunctionType,
    input_text: str,
    output_text: str,
    model_mode: ModelMode,
    status: TaskStatus,
    duration_ms: int,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO call_records
                (task_id, function_type, input_text, output_text, model_mode, status, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                function_type.value,
                input_text,
                output_text,
                model_mode.value,
                status.value,
                duration_ms,
            ),
        )
        await db.commit()


async def list_records(db_path: str, limit: int = 50, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM call_records ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
