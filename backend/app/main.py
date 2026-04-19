# backend/app/main.py
from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.github_repos import router as github_repos_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.me import router as me_router
from app.api.v1.project_children import router as project_children_router
from app.api.v1.projects import router as projects_router
from app.api.v1.stack_items import router as stack_items_router
from app.api.v1.tags import router as tags_router
from app.api.v1.workspaces import router as workspaces_router
from app.core.audit import install_audit_listener
from app.core.middleware import install_session_middleware
from app.core.problem import install_problem_handler

app = FastAPI(title="Hangar", version="0.1.0")

install_problem_handler(app)
install_session_middleware(app)
install_audit_listener()

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(workspaces_router)
app.include_router(projects_router)
app.include_router(project_children_router)
app.include_router(stack_items_router)
app.include_router(tags_router)
app.include_router(integrations_router)
app.include_router(github_repos_router)


@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
