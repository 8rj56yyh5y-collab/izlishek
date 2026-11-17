"""Вхід за спільним паролем (APP_PASSWORD) через екран «Брухтарня».

Після входу браузер отримує HttpOnly-cookie з HMAC-підписом; зміна пароля
автоматично робить усі старі сесії недійсними. Захищено весь ``/api/``, крім
health і самого входу; статика SPA відкрита (там лише код, без даних).
Без APP_PASSWORD захист вимкнено (локальна робота).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.shared.config import get_settings
from app.shared.i18n import L

COOKIE = "bt_session"
MAX_AGE = 60 * 24 * 3600
OPEN_PATHS = {"/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/status", "/api/v1/auth/logout"}


def _token(password: str) -> str:
    return hmac.new(password.encode(), b"brukhtarnia-session-v1", hashlib.sha256).hexdigest()


def _cookie_ok(cookie_header: str, password: str) -> bool:
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return secrets.compare_digest(v, _token(password))
    return False


class AuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        password = get_settings().app_password
        path = scope.get("path", "")
        if scope["type"] != "http" or not password or not path.startswith("/api/") or path in OPEN_PATHS:
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        if _cookie_ok(headers.get("cookie", ""), password):
            return await self.app(scope, receive, send)
        await JSONResponse({"detail": L("Потрібно увійти", "Нужно войти")}, status_code=401)(scope, receive, send)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    password: str


@router.get("/status")
async def status(request: Request):
    password = get_settings().app_password
    return {"required": bool(password),
            "ok": (not password) or _cookie_ok(request.headers.get("cookie", ""), password)}


@router.post("/login")
async def login(data: LoginIn, request: Request, response: Response):
    password = get_settings().app_password
    if password and not secrets.compare_digest(data.password.encode(), password.encode()):
        await asyncio.sleep(0.7)  # гальмуємо перебір
        return JSONResponse({"detail": L("Невірний пароль", "Неверный пароль")}, status_code=401)
    if password:
        secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.set_cookie(COOKIE, _token(password), max_age=MAX_AGE, httponly=True, samesite="lax", secure=secure)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}
