# backend/app/main.py
from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.cli import router as cli_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.dev import router as dev_router
from app.api.v1.github_repos import router as github_repos_router
from app.api.v1.groups import router as groups_router
from app.api.v1.ideas import router as ideas_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.launches import router as launches_router
from app.api.v1.lifecycle import router as lifecycle_router
from app.api.v1.me import router as me_router
from app.api.v1.notes import router as notes_router
from app.api.v1.project_children import router as project_children_router
from app.api.v1.projects import router as projects_router
from app.api.v1.secrets import router as secrets_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.ships import router as ships_router
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
app.include_router(secrets_router)
app.include_router(groups_router)
app.include_router(stack_items_router)
app.include_router(tags_router)
app.include_router(integrations_router)
app.include_router(github_repos_router)
app.include_router(cli_router)
app.include_router(dev_router)
# Spec 2 — Ship Loop
app.include_router(sessions_router)
app.include_router(decisions_router)
app.include_router(ideas_router)
app.include_router(ships_router)
app.include_router(launches_router)
app.include_router(lifecycle_router)
app.include_router(notes_router)


@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
