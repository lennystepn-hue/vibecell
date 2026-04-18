"""foundation

Revision ID: 0001
Revises:
Create Date: 2026-04-18 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- auth ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.String(200)),
        sa.Column("handle", sa.String(50), unique=True),
        sa.Column("passkey_credentials", postgresql.JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("owner_id", sa.String(26), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])

    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="owner"),
    )

    op.create_table(
        "cli_devices",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("paired_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("token_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_cli_devices_token_hash", "cli_devices", ["token_hash"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("op", sa.String(20), nullable=False),
        sa.Column("entity", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(26), nullable=False),
        sa.Column("diff", postgresql.JSONB),
    )
    op.create_index("ix_audit_log_workspace_id", "audit_log", ["workspace_id"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])

    op.create_table(
        "magic_link_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_magic_link_tokens_email", "magic_link_tokens", ["email"])
    op.create_index("ix_magic_link_tokens_token_hash", "magic_link_tokens", ["token_hash"])
    op.create_index("ix_magic_link_tokens_expires_at", "magic_link_tokens", ["expires_at"])

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("emoji", sa.String(16)),
        sa.Column("color", sa.String(20)),
        sa.Column("pitch", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="building"),
        sa.Column("legal_entity_id", sa.String(26)),
        sa.Column("is_public", sa.Integer, nullable=False, server_default="0"),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    # GIN tsvector index for future /search in Spec 2 — low-cost to create now.
    op.execute(
        "CREATE INDEX projects_fts ON projects USING gin "
        "(to_tsvector('english', name || ' ' || coalesce(pitch, '')))"
    )

    op.create_table(
        "active_project",
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("set_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "project_repos",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20)),
        sa.Column("git_url", sa.Text),
        sa.Column("default_branch", sa.String(100), server_default="main"),
        sa.Column("local_path", sa.Text),
        sa.Column("primary_lang", sa.String(50)),
        sa.Column("license", sa.String(50)),
    )
    op.create_index("ix_project_repos_project_id", "project_repos", ["project_id"])

    op.create_table(
        "project_environments",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("env_template_path", sa.Text),
        sa.Column("db_alias", sa.String(100)),
    )
    op.create_index("ix_project_environments_project_id", "project_environments", ["project_id"])

    op.create_table(
        "project_infra",
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("server_alias", sa.String(100)),
        sa.Column("domain_primary", sa.String(255)),
        sa.Column("domains", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("dns_provider", sa.String(50)),
        sa.Column("db_host", sa.String(255)),
        sa.Column("cdn", sa.String(50)),
        sa.Column("object_storage", sa.String(255)),
    )

    op.create_table(
        "project_context",
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("current_focus", sa.Text),
        sa.Column("next_step", sa.Text),
        sa.Column("user_wants", sa.Text),
        sa.Column("open_questions", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("known_issues", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("blocked_by", sa.Text),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "project_links",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(50)),
        sa.Column("label", sa.String(200)),
        sa.Column("url", sa.Text, nullable=False),
    )
    op.create_index("ix_project_links_project_id", "project_links", ["project_id"])
    op.create_index("ix_project_links_kind", "project_links", ["kind"])

    op.create_table(
        "project_commands",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("command", sa.Text, nullable=False),
        sa.Column("run_in", sa.String(20), nullable=False, server_default="terminal"),
        sa.Column("confirm_required", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_project_commands_project_id", "project_commands", ["project_id"])

    # --- catalog ---
    op.create_table(
        "stack_items",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(30)),
        sa.Column("icon_url", sa.Text),
    )
    op.create_index("ix_stack_items_slug", "stack_items", ["slug"])

    op.create_table(
        "project_stack",
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stack_item_id", sa.String(26), sa.ForeignKey("stack_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(20)),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20)),
        sa.UniqueConstraint("workspace_id", "name", name="uq_tags_workspace_name"),
    )
    op.create_index("ix_tags_workspace_id", "tags", ["workspace_id"])

    op.create_table(
        "project_tags",
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.String(26), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    # --- integrations ---
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("token_ciphertext", sa.Text),
        sa.Column("connected_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_integrations_workspace_id", "integrations", ["workspace_id"])
    op.create_index("ix_integrations_kind", "integrations", ["kind"])

    op.create_table(
        "workspace_keys",
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("dek_ciphertext", sa.Text, nullable=False),
        sa.Column("algorithm", sa.String(30), nullable=False, server_default="aes-256-gcm-v1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- seed stack_items ---
    # Canonical catalog of commonly used tech, pre-populated so project_stack
    # chips resolve against shared entities from day one.
    stack_seed = [
        # frontend
        ("nextjs", "Next.js", "frontend"),
        ("react", "React", "frontend"),
        ("vue", "Vue", "frontend"),
        ("svelte", "Svelte", "frontend"),
        ("sveltekit", "SvelteKit", "frontend"),
        ("nuxt", "Nuxt", "frontend"),
        ("remix", "Remix", "frontend"),
        ("astro", "Astro", "frontend"),
        ("tailwind", "Tailwind CSS", "lib"),
        ("shadcn", "shadcn/ui", "lib"),
        ("shadcn-vue", "shadcn-vue", "lib"),
        ("radix", "Radix UI", "lib"),
        ("lucide", "Lucide Icons", "lib"),
        # backend
        ("fastapi", "FastAPI", "backend"),
        ("django", "Django", "backend"),
        ("flask", "Flask", "backend"),
        ("rails", "Rails", "backend"),
        ("express", "Express", "backend"),
        ("hono", "Hono", "backend"),
        ("elysia", "Elysia", "backend"),
        ("nestjs", "NestJS", "backend"),
        ("trpc", "tRPC", "lib"),
        # db
        ("postgres", "Postgres", "db"),
        ("mysql", "MySQL", "db"),
        ("sqlite", "SQLite", "db"),
        ("supabase", "Supabase", "service"),
        ("planetscale", "PlanetScale", "service"),
        ("neon", "Neon", "service"),
        ("turso", "Turso", "service"),
        ("redis", "Redis", "db"),
        # deploy / infra
        ("hetzner", "Hetzner", "deploy"),
        ("vercel", "Vercel", "deploy"),
        ("netlify", "Netlify", "deploy"),
        ("fly", "Fly.io", "deploy"),
        ("railway", "Railway", "deploy"),
        ("cloudflare", "Cloudflare", "service"),
        ("aws", "AWS", "deploy"),
        ("gcp", "Google Cloud", "deploy"),
        ("docker", "Docker", "service"),
        # services
        ("stripe", "Stripe", "service"),
        ("resend", "Resend", "service"),
        ("postmark", "Postmark", "service"),
        ("plausible", "Plausible", "service"),
        ("posthog", "PostHog", "service"),
        ("sentry", "Sentry", "service"),
        ("lemon", "Lemon Squeezy", "service"),
        ("paddle", "Paddle", "service"),
        # AI providers
        ("anthropic", "Anthropic", "service"),
        ("openai", "OpenAI", "service"),
        ("groq", "Groq", "service"),
        ("replicate", "Replicate", "service"),
        ("fireworks", "Fireworks", "service"),
        ("together", "Together", "service"),
        ("openrouter", "OpenRouter", "service"),
        ("perplexity", "Perplexity", "service"),
        # AI models
        ("claude", "Claude", "model"),
        ("claude-opus-4-7", "Claude Opus 4.7", "model"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6", "model"),
        ("gpt-4", "GPT-4", "model"),
        ("gpt-4o", "GPT-4o", "model"),
        ("o1", "o1", "model"),
        ("gemini", "Gemini", "model"),
        ("llama-3", "Llama 3", "model"),
    ]

    # Use the ulid module via python-side import in the migration
    from ulid import ULID

    stack_table = sa.table(
        "stack_items",
        sa.column("id", sa.String),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("kind", sa.String),
    )
    op.bulk_insert(
        stack_table,
        [
            {"id": str(ULID()), "slug": slug, "name": name, "kind": kind}
            for slug, name, kind in stack_seed
        ],
    )


def downgrade() -> None:
    op.drop_table("workspace_keys")
    op.drop_index("ix_integrations_kind", table_name="integrations")
    op.drop_index("ix_integrations_workspace_id", table_name="integrations")
    op.drop_table("integrations")
    op.drop_table("project_tags")
    op.drop_index("ix_tags_workspace_id", table_name="tags")
    op.drop_table("tags")
    op.drop_table("project_stack")
    op.drop_index("ix_stack_items_slug", table_name="stack_items")
    op.drop_table("stack_items")
    op.drop_index("ix_project_commands_project_id", table_name="project_commands")
    op.drop_table("project_commands")
    op.drop_index("ix_project_links_kind", table_name="project_links")
    op.drop_index("ix_project_links_project_id", table_name="project_links")
    op.drop_table("project_links")
    op.drop_table("project_context")
    op.drop_table("project_infra")
    op.drop_index("ix_project_environments_project_id", table_name="project_environments")
    op.drop_table("project_environments")
    op.drop_index("ix_project_repos_project_id", table_name="project_repos")
    op.drop_table("project_repos")
    op.drop_table("active_project")
    op.execute("DROP INDEX IF EXISTS projects_fts")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_magic_link_tokens_expires_at", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_token_hash", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_email", table_name="magic_link_tokens")
    op.drop_table("magic_link_tokens")
    op.drop_index("ix_audit_log_entity_id", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_workspace_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_cli_devices_token_hash", table_name="cli_devices")
    op.drop_table("cli_devices")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
