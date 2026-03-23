from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings


def _sync_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite:///"):
        return database_url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return database_url


def run_migrations_to_head() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _sync_database_url(settings.database_url))
    command.upgrade(cfg, "head")
