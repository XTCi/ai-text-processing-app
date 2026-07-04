import redis.asyncio as redis_asyncio
from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI

from core.config import settings
from core.errors import register_exception_handlers
from core.logging import TraceIdMiddleware, configure_logging
from api.functions import router as functions_router
from api.records import router as records_router
from api.tasks import router as tasks_router
from services.record_store import init_db

app = FastAPI(title="AI Text Processing App")

configure_logging()
app.add_middleware(TraceIdMiddleware)
register_exception_handlers(app)
app.include_router(functions_router)
app.include_router(tasks_router)
app.include_router(records_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    app.state.redis = redis_asyncio.from_url(settings.redis_url)
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.sqlite_path = settings.sqlite_path
    await init_db(settings.sqlite_path)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if hasattr(app.state, "redis"):
        await app.state.redis.aclose()
    if hasattr(app.state, "arq_pool"):
        await app.state.arq_pool.aclose()
