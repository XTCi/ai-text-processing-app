from fastapi import FastAPI

app = FastAPI(title="AI Text Processing App")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
