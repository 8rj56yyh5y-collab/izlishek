"""Вхід і ролі.

* **Адміністратор** — пароль ``APP_PASSWORD``. Бачить і робить усе.
* **Приймальник** — PIN свого пункту (задається в «Довідниках»), лише коли в
  налаштуваннях увімкнено «Версію приймальника». Бачить тільки свою здачу,
  свої здачі й свій баланс; ваги складу до звірки не бачить.

Сесія — HttpOnly-cookie з HMAC-підписом:
``a.<sig>`` для адміністратора, ``r.<point_id>.<sig>`` для приймальника.
Підпис залежить від пароля / хешу PIN, тож зміна пароля чи PIN анулює сесії.
Без ``APP_PASSWORD`` (локальна робота) кожен — адміністратор.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.shared.config import get_settings
from app.shared.database import get_session
from app.shared.i18n import L

COOKIE = "bt_session"
MAX_AGE = 60 * 24 * 3600
OPEN_PATHS = {"/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/status", "/api/v1/auth/logout"}
# Що дозволено приймальнику (метод, префікс шляху).
RECEIVER_ALLOWED = (
    ("*", "/api/v1/receiver/"),
    ("GET", "/api/v1/surplus/materials"),
    ("POST", "/api/v1/surplus/recognize"),
)
_SECRET = (os.getenv("SECRET_KEY") or secrets.token_hex(32)).encode()


@dataclass(frozen=True)
class Principal:
    role: str  # admin | receiver
    point_id: int | None = None


def _sign(msg: str) -> str:
    return hmac.new(_SECRET, msg.encode(), hashlib.sha256).hexdigest()


def admin_token(password: str) -> str:
    # Без SECRET_KEY секрет випадковий на кожен запуск; тоді підписуємо самим паролем,
    # щоб сесії адміністратора пережили перезапуск сервера.
    key = os.getenv("SECRET_KEY") or password
    return "a." + hmac.new(key.encode(), f"a:{password}".encode(), hashlib.sha256).hexdigest()


def receiver_token(point_id: int, pin_hash: str) -> str:
    key = os.getenv("SECRET_KEY") or (get_settings().app_password or "")
    return f"r.{point_id}." + hmac.new(key.encode(), f"r:{point_id}:{pin_hash}".encode(), hashlib.sha256).hexdigest()


def _cookie(cookie_header: str) -> str | None:
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return None


async def resolve(cookie_header: str) -> Principal | None:
    password = get_settings().app_password
    if not password:
        return Principal("admin")
    tok = _cookie(cookie_header)
    if not tok:
        return None
    if tok.startswith("a.") and secrets.compare_digest(tok, admin_token(password)):
        return Principal("admin")
    if tok.startswith("r."):
        from app.modules.surplus import service  # лінивий імпорт: модуль залежить від shared

        try:
            point_id = int(tok.split(".")[1])
        except (IndexError, ValueError):
            return None
        async for db in get_session():
            if not await service.receiver_mode(db):
                return None
            from app.modules.surplus.models import SurplusPoint

            p = await db.get(SurplusPoint, point_id)
            if p and p.is_active and p.pin_hash and secrets.compare_digest(tok, receiver_token(p.id, p.pin_hash)):
                return Principal("receiver", p.id)
    return None


def _receiver_may(method: str, path: str) -> bool:
    return any((m == "*" or m == method) and path.startswith(prefix) for m, prefix in RECEIVER_ALLOWED)


class AuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/") or path in OPEN_PATHS:
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        who = await resolve(headers.get("cookie", ""))
        if who is None:
            return await JSONResponse({"detail": L("Потрібно увійти", "Нужно войти")}, status_code=401)(scope, receive, send)
        if who.role == "receiver" and not _receiver_may(scope["method"], path):
            return await JSONResponse({"detail": L("Недостатньо прав", "Недостаточно прав")}, status_code=403)(scope, receive, send)
        scope.setdefault("state", {})["principal"] = who
        await self.app(scope, receive, send)


def _principal(request: Request) -> Principal:
    who = getattr(request.state, "principal", None)
    if who is None:
        raise HTTPException(401, L("Потрібно увійти", "Нужно войти"))
    return who


CurrentPrincipal = Annotated[Principal, Depends(_principal)]


# ── Вхід ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Прості обмеження перебору: не більше 8 невдалих спроб за 10 хв з однієї адреси.
_FAILS: dict[str, list[float]] = defaultdict(list)
_WINDOW, _LIMIT = 600, 8


def _client(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


class LoginIn(BaseModel):
    password: str


@router.get("/status")
async def status(request: Request):
    from app.modules.surplus import service
    from app.modules.surplus.models import SurplusPoint

    who = await resolve(request.headers.get("cookie", ""))
    out: dict = {"required": bool(get_settings().app_password), "ok": who is not None,
                 "role": who.role if who else None}
    async for db in get_session():
        out["receiver_mode"] = await service.receiver_mode(db)
        if who and who.role == "receiver":
            p = await db.get(SurplusPoint, who.point_id)
            out.update(point_id=p.id, point_name=p.name, receiver_name=p.receiver_name)
    return out


@router.post("/login")
async def login(data: LoginIn, request: Request, response: Response):
    from app.modules.surplus import service

    ip = _client(request)
    now = time.monotonic()
    _FAILS[ip] = [x for x in _FAILS[ip] if now - x < _WINDOW]
    if len(_FAILS[ip]) >= _LIMIT:
        return JSONResponse({"detail": L("Забагато спроб. Спробуйте за 10 хвилин.", "Слишком много попыток. Попробуйте через 10 минут.")},
                            status_code=429)

    password = get_settings().app_password
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    token = role = None
    if password and secrets.compare_digest(data.password.encode(), password.encode()):
        token, role = admin_token(password), "admin"
    elif not password and not data.password:
        role = "admin"
    else:
        async for db in get_session():
            if data.password.isdigit() and await service.receiver_mode(db):
                p = await service.point_by_pin(db, data.password)
                if p:
                    token, role = receiver_token(p.id, p.pin_hash), "receiver"
    if role is None:
        _FAILS[ip].append(now)
        await asyncio.sleep(0.7)
        return JSONResponse({"detail": L("Невірний пароль", "Неверный пароль")}, status_code=401)
    _FAILS.pop(ip, None)
    if token:
        response.set_cookie(COOKIE, token, max_age=MAX_AGE, httponly=True, samesite="lax", secure=secure)
    return {"ok": True, "role": role}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}
