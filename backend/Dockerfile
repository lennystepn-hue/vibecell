FROM python:3.12-slim AS builder

# uv from astral.sh — pinned
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install deps first for better caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy app source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN uv sync --frozen --no-dev

# ----

FROM python:3.12-slim AS runtime

# System deps:
# - curl for healthcheck
# - chromium runtime libs needed by playwright's bundled browser
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
    libglib2.0-0 libdbus-1-3 libatspi2.0-0 libwayland-client0 \
    fonts-liberation fonts-noto-color-emoji \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

# Install only chromium — shaves ~300MB vs the full browsers set.
# Must be done as root before the USER switch.
RUN mkdir -p /opt/ms-playwright && \
    playwright install chromium && \
    chmod -R a+rX /opt/ms-playwright

# Pre-create the screenshots volume mount point so a non-root user can write to it.
RUN mkdir -p /var/lib/hangar/screenshots

# Run as non-root
RUN useradd -r -u 1000 -g root hangar && \
    chown -R hangar:root /app /opt/ms-playwright /var/lib/hangar
USER hangar

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
