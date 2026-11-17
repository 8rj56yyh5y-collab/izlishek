from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    seed_demo: bool
    app_password: str | None


def _db_url() -> str:
    # Render дає DATABASE_URL у вигляді postgres://… — переводимо на асинхронний драйвер.
    url = os.getenv("IZLISHEK_DB_URL") or os.getenv("DATABASE_URL") or "sqlite+aiosqlite:///./izlishek.db"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=_db_url(),
        seed_demo=os.getenv("IZLISHEK_SEED_DEMO", "1") == "1",
        app_password=os.getenv("APP_PASSWORD") or None,
    )
