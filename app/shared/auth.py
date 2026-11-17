"""Мінімальний захист для розгортання в інтернеті: один спільний пароль (HTTP Basic).

Вмикається змінною APP_PASSWORD. Логін — будь-який. Браузер запамʼятовує пароль,
тож SPA і API працюють без окремої форми входу. Повноцінні користувачі й ролі —
після перенесення в Gobsek.
"""
from __future__ import annotations

import base64
import binascii
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

OPEN_PATHS = {"/api/v1/health"}


class PasswordMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, password: str):
        super().__init__(app)
        self.password = password.encode()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in OPEN_PATHS or self._ok(request.headers.get("authorization", "")):
            return await call_next(request)
        return Response("Потрібен пароль", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="izlishek", charset="UTF-8"'})

    def _ok(self, header: str) -> bool:
        if not header.lower().startswith("basic "):
            return False
        try:
            _, _, pwd = base64.b64decode(header[6:]).partition(b":")
        except (binascii.Error, ValueError):
            return False
        return secrets.compare_digest(pwd, self.password)
