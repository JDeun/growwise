from __future__ import annotations

import os

import uvicorn

from growwise.api.desktop_security import install_desktop_security
from growwise.api.main import app
from growwise.config import Settings

_SESSION_TOKEN_ENV = "GROWWISE_SESSION_TOKEN"


def _session_token() -> str:
    token = os.environ.get(_SESSION_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{_SESSION_TOKEN_ENV} is required for the desktop Core sidecar")
    return token


install_desktop_security(app, session_token=_session_token())


def run() -> None:
    settings = Settings()
    if settings.api_host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("desktop Core must bind to a loopback address")
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, log_level="warning")


if __name__ == "__main__":
    run()
