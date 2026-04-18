# Hangar Backend

FastAPI + SQLAlchemy-async + Alembic + Postgres + Redis.

## Dev

```bash
uv sync
cp .env.example .env    # fill in HANGAR_MASTER_KEY (see below) + others
uv run uvicorn app.main:app --reload --port 8000
```

### Generate a master key

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste into `HANGAR_MASTER_KEY` in `.env`.

## Test

```bash
uv run pytest
```
