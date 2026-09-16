from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response

DESKTOP_PROTOCOL_VERSION = 1
DESKTOP_PRODUCT = "growwise-core"


def install_desktop_security(app: FastAPI, *, session_token: str) -> None:
    """Protect the desktop sidecar with a per-process bearer token and identity handshake."""

    token = session_token.strip()
    if len(token) < 32:
        raise ValueError("desktop session token must contain at least 32 characters")
    expected = f"Bearer {token}"

    @app.middleware("http")
    async def require_desktop_session(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied, expected):
            return JSONResponse(status_code=401, content={"detail": "desktop_session_required"})
        return await call_next(request)

    @app.get("/_desktop/handshake", include_in_schema=False)
    def desktop_handshake() -> dict[str, str | int]:
        return {
            "product": DESKTOP_PRODUCT,
            "protocol_version": DESKTOP_PROTOCOL_VERSION,
        }
