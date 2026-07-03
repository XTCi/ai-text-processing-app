from fastapi import FastAPI
from core.errors import register_exception_handlers
from core.logging import TraceIdMiddleware, configure_logging
from api.functions import router as functions_router

app = FastAPI(title="AI Text Processing App")

configure_logging()
app.add_middleware(TraceIdMiddleware)
register_exception_handlers(app)
app.include_router(functions_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
