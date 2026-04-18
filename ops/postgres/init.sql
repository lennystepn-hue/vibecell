-- ops/postgres/init.sql
-- Runs once on first container start. Alembic manages schema; we only use this
-- for extensions Alembic cannot install.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
