from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.shared import database


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("IZLISHEK_SEED_DEMO", "0")
    from app.shared.config import get_settings
    get_settings.cache_clear()
    database.init_engine("sqlite+aiosqlite:///:memory:")
    from main import app, lifespan
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            yield c
    get_settings.cache_clear()
