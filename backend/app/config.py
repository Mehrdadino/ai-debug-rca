from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RCA_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    """Async SQLAlchemy URL. Default: local SQLite file under ./data/"""

    ingest_sync: bool = False
    """If True, write traces in the request handler (201). If False, enqueue and return 202."""

    ingest_queue_maxsize: int = 10_000
    """Max queued traces before POST returns 503 (only when ingest_sync is False)."""

    @property
    def database_path(self) -> Optional[Path]:
        if self.database_url.startswith("sqlite+aiosqlite:///./"):
            return Path(self.database_url.removeprefix("sqlite+aiosqlite:///./"))
        return None


settings = Settings()
