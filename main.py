from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.modules.surplus import models  # noqa: F401 — реєстрація таблиць
from app.modules.surplus.router import router as surplus_router
from app.modules.surplus.seed import seed
from app.shared.auth import AuthMiddleware
from app.shared.auth import router as auth_router
from app.shared.config import get_settings
from app.shared.i18n import LangMiddleware
from app.shared.database import Base, get_engine, get_session

SPA = Path(__file__).parent / "static" / "spa"


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async for db in get_session():
        await seed(db, demo=get_settings().seed_demo)
    yield


app = FastAPI(title="Брухтарня", lifespan=lifespan, docs_url="/api/docs")
# Порядок: мова виставляється першою (зовнішній шар), тож і 401 від входу — потрібною мовою.
app.add_middleware(AuthMiddleware)
app.add_middleware(LangMiddleware)
app.include_router(auth_router)
app.include_router(surplus_router)


@app.get("/api/v1/health", tags=["system"])
async def health():
    return {"ok": True}


if SPA.exists():
    app.mount("/app/assets", StaticFiles(directory=SPA / "assets"), name="assets")

    @app.get("/app/{path:path}", include_in_schema=False)
    async def spa(path: str):
        return FileResponse(SPA / "index.html")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/app/")
