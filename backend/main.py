from fastapi import FastAPI
from core.errors import register_exception_handlers
from core.logging import TraceIdMiddleware, configure_logging

app = FastAPI(title="AI Text Processing App")

configure_logging()
app.add_middleware(TraceIdMiddleware)
register_exception_handlers(app)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
