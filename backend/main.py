from fastapi import FastAPI
from core.errors import register_exception_handlers

app = FastAPI(title="AI Text Processing App")

register_exception_handlers(app)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
