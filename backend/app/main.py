# backend/app/main.py
from fastapi import FastAPI

from app.core.problem import install_problem_handler

app = FastAPI(title="Hangar", version="0.1.0")

install_problem_handler(app)


@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
