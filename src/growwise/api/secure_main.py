from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path
from typing import Any

import uvicorn
from starlette.responses import JSONResponse

from growwise.api.main import app as core_app
from growwise.api.main import get_settings

_TOKEN_ENV = "GROWWISE_API_TOKEN"
_TOKEN_FILE_ENV = "GROWWISE_API_TOKEN_FILE"


def _write_session_token(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
            handle.write(token)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)


def bootstrap_desktop_token() -> None:
    """Create a fresh CSPRNG bearer token for the desktop-owned sidecar.

    Standalone Core usage remains possible: when no token-file handoff was requested, this function
    leaves the environment untouched and the wrapper below behaves as an unauthenticated local dev
    server. The packaged Tauri shell always supplies ``GROWWISE_API_TOKEN_FILE``.
    """
    token_file = os.getenv(_TOKEN_FILE_ENV)
    if not token_file:
        return
    token = secrets.token_urlsafe(32)
    os.environ[_TOKEN_ENV] = token
    _write_session_token(Path(token_file), token)


class CoreTokenMiddleware:
    """Pure ASGI bearer-token gate for the desktop sidecar."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        expected_token = os.getenv(_TOKEN_ENV)
        if expected_token:
            supplied = ""
            for raw_name, raw_value in scope.get("headers", []):
                if raw_name.lower() == b"authorization":
                    supplied = raw_value.decode("latin-1")
                    break
            expected = f"Bearer {expected_token}"
            if not hmac.compare_digest(supplied, expected):
                response = JSONResponse(
                    {"detail": "unauthorized_core_client"},
                    status_code=401,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


app = CoreTokenMiddleware(core_app)


def run() -> None:
    bootstrap_desktop_token()
    # Settings may have been instantiated while importing the normal Core module. Refresh after the
    # token handoff so health/diagnostics observe the packaged sidecar environment consistently.
    get_settings.cache_clear()
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
