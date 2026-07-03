from arq.connections import RedisSettings

from core.config import settings
from worker.tasks import execute_task


class WorkerSettings:
    functions = [execute_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = settings.task_timeout_seconds

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        import redis.asyncio as redis_asyncio

        from services.record_store import init_db

        ctx["redis"] = redis_asyncio.from_url(settings.redis_url)
        ctx["sqlite_path"] = settings.sqlite_path
        await init_db(settings.sqlite_path)

    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        await ctx["redis"].aclose()
