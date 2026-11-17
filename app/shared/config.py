from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    seed_demo: bool


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("IZLISHEK_DB_URL", "sqlite+aiosqlite:///./izlishek.db"),
        seed_demo=os.getenv("IZLISHEK_SEED_DEMO", "1") == "1",
    )
