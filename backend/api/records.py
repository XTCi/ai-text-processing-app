from fastapi import APIRouter, Depends, Query

from core.deps import get_sqlite_path
from services.record_store import list_records

router = APIRouter()


@router.get("/api/records")
async def get_records(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sqlite_path: str = Depends(get_sqlite_path),
) -> dict:
    records = await list_records(sqlite_path, limit=limit, offset=offset)
    return {"records": records}
