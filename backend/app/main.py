# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="Hangar", version="0.1.0")


@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
