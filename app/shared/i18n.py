"""Дві мови: українська (типово) і російська.

Мова запиту — заголовок ``X-Lang`` (його ставить SPA), або ``?lang=`` (для
посилань на Excel), або ``Accept-Language``. ``L(uk, ru)`` повертає рядок
потрібною мовою в межах поточного запиту.
"""
from __future__ import annotations

from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

LANGS = ("uk", "ru")
_lang: ContextVar[str] = ContextVar("lang", default="uk")


def L(uk: str, ru: str) -> str:
    return ru if _lang.get() == "ru" else uk


def current() -> str:
    return _lang.get()


def _pick(scope: Scope) -> str:
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    q = scope.get("query_string", b"").decode()
    for part in q.split("&"):
        if part.startswith("lang=") and part[5:] in LANGS:
            return part[5:]
    if headers.get("x-lang") in LANGS:
        return headers["x-lang"]
    return "ru" if headers.get("accept-language", "").lower().startswith("ru") else "uk"


class LangMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = _lang.set(_pick(scope))
        try:
            await self.app(scope, receive, send)
        finally:
            _lang.reset(token)
